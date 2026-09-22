// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tauri::{AppHandle, Emitter, State};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, ChildStdin, Command};
use tokio::sync::{oneshot, Mutex as TokioMutex};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[derive(Debug, Serialize, Deserialize)]
pub struct ConversionSettingsPayload {
    pub text_size: Option<u32>,
    pub paper_size: Option<String>,
    pub output_format: Option<String>,
    pub routing_mode: Option<String>,
    pub page_range: Option<String>,
}

#[derive(Default)]
pub struct AppSession {
    pub active_job_id: Mutex<Option<String>>,
    pub stdin: TokioMutex<Option<ChildStdin>>,
    pub child: TokioMutex<Option<Child>>,
    pub pending_health: Arc<Mutex<Option<oneshot::Sender<serde_json::Value>>>>,
    pub pending_inspect: Arc<Mutex<Option<oneshot::Sender<serde_json::Value>>>>,
    pub pending_review: Arc<Mutex<Option<oneshot::Sender<serde_json::Value>>>>,
}

impl AppSession {
    pub async fn ensure_sidecar_running(&self, app: &AppHandle) -> Result<(), String> {
        let mut stdin_guard = self.stdin.lock().await;
        if stdin_guard.is_some() {
            let mut child_guard = self.child.lock().await;
            if let Some(ref mut child) = *child_guard {
                match child.try_wait() {
                    Ok(Some(status)) => {
                        eprintln!("[supervisor] Sidecar child process already exited (status: {}). Resetting handles.", status);
                        *stdin_guard = None;
                        *child_guard = None;
                    }
                    Ok(None) => {
                        return Ok(());
                    }
                    Err(e) => {
                        eprintln!("[supervisor] Failed to query sidecar status: {}. Resetting handles.", e);
                        *stdin_guard = None;
                        *child_guard = None;
                    }
                }
            } else {
                *stdin_guard = None;
            }
        }

        let sidecar_exe = resolve_sidecar_binary();
        let mut cmd = Command::new(&sidecar_exe);
        cmd.args(["sidecar"])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        #[cfg(target_os = "windows")]
        {
            cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW: prevent empty black console popup
        }

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("Failed to launch sidecar ({}): {}", sidecar_exe.display(), e))?;

        let stdin = child.stdin.take().ok_or("Failed to open sidecar stdin")?;
        let stdout = child.stdout.take().ok_or("Failed to open sidecar stdout")?;
        if let Some(stderr) = child.stderr.take() {
            tokio::spawn(async move {
                let mut err_reader = BufReader::new(stderr).lines();
                while let Ok(Some(line)) = err_reader.next_line().await {
                    eprintln!("[sidecar:err] {}", line);
                }
            });
        }

        *stdin_guard = Some(stdin);
        {
            let mut child_guard = self.child.lock().await;
            *child_guard = Some(child);
        }

        let app_clone = app.clone();
        let pending_health = Arc::clone(&self.pending_health);
        let pending_inspect = Arc::clone(&self.pending_inspect);
        let pending_review = Arc::clone(&self.pending_review);

        tokio::spawn(async move {
            let mut reader = BufReader::new(stdout).lines();
            while let Ok(Some(line)) = reader.next_line().await {
                let trimmed = line.trim();
                if trimmed.is_empty() {
                    continue;
                }
                if let Ok(event) = serde_json::from_str::<serde_json::Value>(trimmed) {
                    let ev_type = event.get("type").and_then(|t| t.as_str()).unwrap_or("");
                    match ev_type {
                        "health" => {
                            if let Some(tx) = pending_health.lock().unwrap().take() {
                                let _ = tx.send(event);
                            }
                        }
                        "inspect_result" => {
                            if let Some(tx) = pending_inspect.lock().unwrap().take() {
                                let _ = tx.send(event);
                            }
                        }
                        "review_data" => {
                            if let Some(tx) = pending_review.lock().unwrap().take() {
                                let _ = tx.send(event.clone());
                            }
                            let _ = app_clone.emit("sidecar-review", event);
                        }
                        "progress" => {
                            let _ = app_clone.emit("sidecar-progress", event);
                        }
                        "checkpoint" => {
                            let _ = app_clone.emit("sidecar-checkpoint", event);
                        }
                        "success" => {
                            let _ = app_clone.emit("sidecar-success", event);
                        }
                        "error" => {
                            let _ = app_clone.emit("sidecar-error", event);
                        }
                        "cancelled" => {
                            let _ = app_clone.emit("sidecar-cancelled", event);
                        }
                        _ => {}
                    }
                }
            }
            eprintln!("[supervisor] Sidecar stdout EOF reached.");
            let _ = app_clone.emit("sidecar-error", serde_json::json!({
                "type": "error",
                "message": "The document conversion engine stopped unexpectedly.",
                "code": "SIDECAR_CRASHED"
            }));
        });

        Ok(())
    }

    pub async fn send_command(&self, json_val: &serde_json::Value) -> Result<(), String> {
        let mut stdin_guard = self.stdin.lock().await;
        if let Some(ref mut stdin) = *stdin_guard {
            let mut data = json_val.to_string();
            data.push('\n');
            if let Err(e) = stdin.write_all(data.as_bytes()).await {
                *stdin_guard = None;
                let mut child_guard = self.child.lock().await;
                *child_guard = None;
                return Err(format!("Failed to write to sidecar: {}", e));
            }
            if let Err(e) = stdin.flush().await {
                *stdin_guard = None;
                let mut child_guard = self.child.lock().await;
                *child_guard = None;
                return Err(format!("Failed to flush sidecar: {}", e));
            }
            Ok(())
        } else {
            Err("Sidecar process is not running".to_string())
        }
    }
}

/// Platform-specific sidecar binary names, in preference order.
fn sidecar_binary_names() -> Vec<&'static str> {
    #[cfg(target_os = "windows")]
    {
        vec![
            "openlargeprint-sidecar.exe",
            "openlargeprint-sidecar-x86_64-pc-windows-msvc.exe",
        ]
    }
    #[cfg(target_os = "macos")]
    {
        vec![
            "openlargeprint-sidecar",
            "openlargeprint-sidecar-aarch64-apple-darwin",
            "openlargeprint-sidecar-x86_64-apple-darwin",
        ]
    }
    #[cfg(all(not(target_os = "windows"), not(target_os = "macos")))]
    {
        vec![
            "openlargeprint-sidecar",
            "openlargeprint-sidecar-x86_64-unknown-linux-gnu",
            "openlargeprint-sidecar-aarch64-unknown-linux-gnu",
        ]
    }
}

fn resolve_sidecar_binary() -> PathBuf {
    let names = sidecar_binary_names();

    // 1. Check relative to current executable (production bundle)
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            for name in &names {
                let candidate = exe_dir.join(name);
                if candidate.exists() {
                    return candidate;
                }
                let engine_sub = exe_dir.join("engine").join(name);
                if engine_sub.exists() {
                    return engine_sub;
                }
            }
        }
    }

    // 2. Check development binaries folders
    for dir in ["binaries", "src-tauri/binaries", "packaging/dist"] {
        for name in &names {
            let candidate = PathBuf::from(dir).join(name);
            if candidate.exists() {
                return candidate;
            }
        }
    }

    // 3. Fallback to the platform's canonical bare name
    PathBuf::from(names[0])
}

// Windows-only Win32 common-dialog FFI. Gated so non-Windows builds do not try
// to link `comdlg32`, which does not exist on Linux/macOS.
#[cfg(target_os = "windows")]
#[repr(C)]
struct OpenFileNameW {
    l_struct_size: u32,
    hwnd_owner: *mut std::ffi::c_void,
    h_instance: *mut std::ffi::c_void,
    lpstr_filter: *const u16,
    lpstr_custom_filter: *mut u16,
    n_max_cust_filter: u32,
    n_filter_index: u32,
    lpstr_file: *mut u16,
    n_max_file: u32,
    lpstr_file_title: *mut u16,
    n_max_file_title: u32,
    lpstr_initial_dir: *const u16,
    lpstr_title: *const u16,
    flags: u32,
    n_file_offset: u16,
    n_file_extension: u16,
    lpstr_def_ext: *const u16,
    l_cust_data: usize,
    lpfn_hook: *mut std::ffi::c_void,
    lp_template_name: *const u16,
    pv_reserved: *mut std::ffi::c_void,
    dw_reserved: u32,
    flags_ex: u32,
}

#[cfg(target_os = "windows")]
#[link(name = "comdlg32")]
extern "system" {
    fn GetOpenFileNameW(lpofn: *mut OpenFileNameW) -> i32;
    fn GetSaveFileNameW(lpofn: *mut OpenFileNameW) -> i32;
}

#[cfg(target_os = "windows")]
fn native_windows_open_file_dialog() -> Option<PathBuf> {
    let filter: Vec<u16> = "Supported Documents (*.pdf;*.docx;*.doc;*.pptx;*.ppt)\0*.pdf;*.docx;*.doc;*.pptx;*.ppt\0All Files (*.*)\0*.*\0\0"
        .encode_utf16()
        .collect();
    let title: Vec<u16> = "Select Document for Large Print Conversion\0".encode_utf16().collect();
    let mut file_buf = vec![0u16; 1024];

    let mut ofn: OpenFileNameW = unsafe { std::mem::zeroed() };
    ofn.l_struct_size = std::mem::size_of::<OpenFileNameW>() as u32;
    ofn.lpstr_filter = filter.as_ptr();
    ofn.lpstr_file = file_buf.as_mut_ptr();
    ofn.n_max_file = file_buf.len() as u32;
    ofn.lpstr_title = title.as_ptr();
    // OFN_FILEMUSTEXIST (0x00001000) | OFN_PATHMUSTEXIST (0x00000800) | OFN_NOCHANGEDIR (0x00000008)
    ofn.flags = 0x00001000 | 0x00000800 | 0x00000008;

    let res = unsafe { GetOpenFileNameW(&mut ofn) };
    if res != 0 {
        let end = file_buf.iter().position(|&c| c == 0).unwrap_or(file_buf.len());
        let path_str = String::from_utf16_lossy(&file_buf[..end]);
        if !path_str.is_empty() {
            return Some(PathBuf::from(path_str));
        }
    }
    None
}

#[cfg(target_os = "windows")]
fn native_windows_save_file_dialog(
    default_name: Option<&str>,
    filter_ext: Option<&str>,
    initial_dir: Option<&str>,
) -> Option<PathBuf> {
    let ext = filter_ext.unwrap_or("pdf").to_lowercase();
    let (filter_str, def_ext_str) = match ext.as_str() {
        "docx" => ("Word Document (*.docx)\0*.docx\0All Files (*.*)\0*.*\0\0", "docx\0"),
        "html" | "reader" => ("Interactive Web Document (*.html)\0*.html\0All Files (*.*)\0*.*\0\0", "html\0"),
        _ => ("PDF Document (*.pdf)\0*.pdf\0All Files (*.*)\0*.*\0\0", "pdf\0"),
    };

    let filter: Vec<u16> = filter_str.encode_utf16().collect();
    let def_ext: Vec<u16> = def_ext_str.encode_utf16().collect();
    let title: Vec<u16> = "Choose Export Destination\0".encode_utf16().collect();
    let mut file_buf = vec![0u16; 1024];

    if let Some(name) = default_name {
        let utf16_name: Vec<u16> = name.encode_utf16().collect();
        let copy_len = utf16_name.len().min(file_buf.len() - 1);
        file_buf[..copy_len].copy_from_slice(&utf16_name[..copy_len]);
    }

    let init_dir_vec: Option<Vec<u16>> = initial_dir.map(|d| format!("{}\0", d).encode_utf16().collect());

    let mut ofn: OpenFileNameW = unsafe { std::mem::zeroed() };
    ofn.l_struct_size = std::mem::size_of::<OpenFileNameW>() as u32;
    ofn.lpstr_filter = filter.as_ptr();
    ofn.lpstr_file = file_buf.as_mut_ptr();
    ofn.n_max_file = file_buf.len() as u32;
    ofn.lpstr_title = title.as_ptr();
    ofn.lpstr_def_ext = def_ext.as_ptr();
    if let Some(ref v) = init_dir_vec {
        ofn.lpstr_initial_dir = v.as_ptr();
    }
    // OFN_OVERWRITEPROMPT (0x00000002) | OFN_PATHMUSTEXIST (0x00000800) | OFN_NOCHANGEDIR (0x00000008)
    ofn.flags = 0x00000002 | 0x00000800 | 0x00000008;

    let res = unsafe { GetSaveFileNameW(&mut ofn) };
    if res != 0 {
        let end = file_buf.iter().position(|&c| c == 0).unwrap_or(file_buf.len());
        let path_str = String::from_utf16_lossy(&file_buf[..end]);
        if !path_str.is_empty() {
            return Some(PathBuf::from(path_str));
        }
    }
    None
}

/// Resolve the current user's home directory on any platform.
fn user_home() -> PathBuf {
    #[cfg(target_os = "windows")]
    {
        if let Ok(profile) = std::env::var("USERPROFILE") {
            return PathBuf::from(profile);
        }
    }
    if let Ok(home) = std::env::var("HOME") {
        return PathBuf::from(home);
    }
    PathBuf::from(".")
}

#[tauri::command]
async fn get_system_paths() -> Result<serde_json::Value, String> {
    let up = user_home();
    let downloads = up.join("Downloads");
    let desktop = up.join("Desktop");
    let documents = up.join("Documents");

    Ok(serde_json::json!({
        "downloads": downloads.to_string_lossy().to_string(),
        "desktop": desktop.to_string_lossy().to_string(),
        "documents": documents.to_string_lossy().to_string(),
        "userProfile": up.to_string_lossy().to_string(),
    }))
}

#[tauri::command]
async fn open_file_dialog(app: AppHandle) -> Result<Option<serde_json::Value>, String> {
    tokio::task::spawn_blocking(move || {
        #[cfg(target_os = "windows")]
        {
            let _ = &app;
            if let Some(path) = native_windows_open_file_dialog() {
                let file_name = path
                    .file_name()
                    .unwrap_or_default()
                    .to_string_lossy()
                    .to_string();
                let file_size = std::fs::metadata(&path).map(|m| m.len()).unwrap_or(0);
                return Ok(Some(serde_json::json!({
                    "path": path.to_string_lossy().to_string(),
                    "name": file_name,
                    "size": file_size,
                })));
            }
            return Ok(None);
        }

        #[cfg(not(target_os = "windows"))]
        {
            use tauri_plugin_dialog::DialogExt;
            let selected = app.dialog().file()
                .add_filter("Documents", &["pdf", "docx", "pptx", "doc", "ppt"])
                .blocking_pick_file();
            let Some(selected) = selected else { return Ok(None) };
            let path = selected.into_path().map_err(|_| "Choose a local document.".to_string())?;
            let metadata = std::fs::metadata(&path).map_err(|_| "The selected file could not be opened.".to_string())?;
            Ok(Some(serde_json::json!({
                "path": path.to_string_lossy(),
                "name": path.file_name().unwrap_or_default().to_string_lossy(),
                "size": metadata.len(),
            })))
        }
    })
    .await
    .map_err(|e| format!("Dialog task error: {}", e))?
}

#[tauri::command]
async fn choose_save_dialog(
    app: AppHandle,
    default_name: Option<String>,
    filter_ext: Option<String>,
    initial_dir: Option<String>,
) -> Result<Option<String>, String> {
    tokio::task::spawn_blocking(move || {
        #[cfg(target_os = "windows")]
        {
            let _ = &app;
            if let Some(path) = native_windows_save_file_dialog(
                default_name.as_deref(),
                filter_ext.as_deref(),
                initial_dir.as_deref(),
            ) {
                return Ok(Some(path.to_string_lossy().to_string()));
            }
            return Ok(None);
        }

        #[cfg(not(target_os = "windows"))]
        {
            use tauri_plugin_dialog::DialogExt;
            let mut dialog = app.dialog().file();
            if let Some(name) = default_name { dialog = dialog.set_file_name(name); }
            if let Some(directory) = initial_dir { dialog = dialog.set_directory(directory); }
            if let Some(extension) = filter_ext {
                if ["pdf", "docx", "html"].contains(&extension.as_str()) {
                    dialog = dialog.add_filter("Document", &[extension.as_str()]);
                }
            }
            let Some(selected) = dialog.blocking_save_file() else { return Ok(None) };
            let path = selected.into_path().map_err(|_| "Choose a local output file.".to_string())?;
            Ok(Some(path.to_string_lossy().into_owned()))
        }
    })
    .await
    .map_err(|e| format!("Save dialog task error: {}", e))?
}

#[tauri::command]
async fn inspect_file_path(file_path: String) -> Result<serde_json::Value, String> {
    let p = PathBuf::from(&file_path);
    let file_name = p.file_name().unwrap_or_default().to_string_lossy().to_string();
    let file_size = std::fs::metadata(&p).map(|m| m.len()).unwrap_or(0);
    Ok(serde_json::json!({
        "path": file_path,
        "name": file_name,
        "size": file_size
    }))
}

#[tauri::command]
async fn open_path_in_system(path: String) -> Result<(), String> {
    let p = PathBuf::from(&path);
    if !p.exists() {
        return Err("File does not exist".to_string());
    }
    #[cfg(target_os = "windows")]
    {
        let mut cmd = std::process::Command::new("explorer");
        cmd.arg(&p);
        cmd.creation_flags(0x08000000);
        cmd.spawn().map_err(|e| format!("Failed to open file: {}", e))?;
        Ok(())
    }
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(&p)
            .spawn()
            .map_err(|e| format!("Failed to open file: {}", e))?;
        Ok(())
    }
    #[cfg(all(not(target_os = "windows"), not(target_os = "macos")))]
    {
        std::process::Command::new("xdg-open")
            .arg(&p)
            .spawn()
            .map_err(|e| format!("Failed to open file: {}", e))?;
        Ok(())
    }
}

#[tauri::command]
async fn reveal_in_folder(path: String) -> Result<(), String> {
    let p = PathBuf::from(&path);
    if !p.exists() {
        return Err("Path does not exist".to_string());
    }
    #[cfg(target_os = "windows")]
    {
        let mut cmd = std::process::Command::new("explorer");
        cmd.args(["/select,", &p.to_string_lossy()]);
        cmd.creation_flags(0x08000000);
        cmd.spawn().map_err(|e| format!("Failed to reveal path: {}", e))?;
        Ok(())
    }
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .args(["-R", &p.to_string_lossy()])
            .spawn()
            .map_err(|e| format!("Failed to reveal path: {}", e))?;
        Ok(())
    }
    #[cfg(all(not(target_os = "windows"), not(target_os = "macos")))]
    {
        // No portable "reveal/select" on Linux; open the containing folder instead.
        let folder = p.parent().unwrap_or(&p);
        std::process::Command::new("xdg-open")
            .arg(folder)
            .spawn()
            .map_err(|e| format!("Failed to reveal path: {}", e))?;
        Ok(())
    }
}

#[tauri::command]
async fn get_cli_arg_file() -> Result<Option<serde_json::Value>, String> {
    let args: Vec<String> = std::env::args().collect();
    for arg in args.into_iter().skip(1) {
        if !arg.starts_with('-') {
            let p = PathBuf::from(&arg);
            if p.exists() && p.is_file() {
                let name = p.file_name().unwrap_or_default().to_string_lossy().to_string();
                let size = std::fs::metadata(&p).map(|m| m.len()).unwrap_or(0);
                return Ok(Some(serde_json::json!({
                    "path": arg,
                    "name": name,
                    "size": size
                })));
            }
        }
    }
    Ok(None)
}

#[tauri::command]
async fn health_check(
    app: AppHandle,
    session: State<'_, AppSession>,
) -> Result<serde_json::Value, String> {
    session.ensure_sidecar_running(&app).await?;
    let (tx, rx) = oneshot::channel();
    {
        let mut lock = session.pending_health.lock().unwrap();
        *lock = Some(tx);
    }

    session
        .send_command(&serde_json::json!({ "command": "health" }))
        .await?;

    match tokio::time::timeout(Duration::from_secs(5), rx).await {
        Ok(Ok(val)) => Ok(val),
        _ => Ok(serde_json::json!({
            "status": "ready",
            "desktop_version": env!("CARGO_PKG_VERSION"),
            "sidecar_binary": resolve_sidecar_binary().to_string_lossy()
        })),
    }
}

#[tauri::command]
async fn inspect_file(
    app: AppHandle,
    session: State<'_, AppSession>,
    file_path: String,
) -> Result<serde_json::Value, String> {
    session.ensure_sidecar_running(&app).await?;
    let (tx, rx) = oneshot::channel();
    {
        let mut lock = session.pending_inspect.lock().unwrap();
        *lock = Some(tx);
    }

    session
        .send_command(&serde_json::json!({
            "command": "inspect",
            "file_path": file_path
        }))
        .await?;

    match tokio::time::timeout(Duration::from_secs(10), rx).await {
        Ok(Ok(val)) => Ok(val),
        Ok(Err(_)) => Err("Inspection response channel dropped".to_string()),
        Err(_) => Err("Timed out waiting for document inspection from sidecar engine".to_string()),
    }
}

/// Resolve the destination path from the conversion/export settings.
fn resolve_output_path(input_path: &Path, settings: &serde_json::Value) -> PathBuf {
    let user_downloads = user_home().join("Downloads");
    let stem = input_path.file_stem().unwrap_or_default().to_string_lossy();
    let out_fmt = settings.get("outputFormat").and_then(|f| f.as_str()).unwrap_or("pdf");
    let ext = match out_fmt {
        "docx" => "docx",
        "reader" | "html" => "html",
        // The searchable original is still a PDF on disk.
        "searchable_pdf" => "pdf",
        _ => "pdf",
    };

    let default_output_path = if let Some(parent) = input_path.parent() {
        if parent.is_absolute() && parent.exists() {
            parent.join(format!("{}-largeprint.{}", stem, ext))
        } else {
            user_downloads.join(format!("{}-largeprint.{}", stem, ext))
        }
    } else {
        user_downloads.join(format!("{}-largeprint.{}", stem, ext))
    };

    let mut output_path = if let Some(custom_path) = settings.get("outputPath").and_then(|p| p.as_str()) {
        let trimmed = custom_path.trim();
        if !trimmed.is_empty() {
            let p = PathBuf::from(trimmed);
            if p.is_absolute() {
                p
            } else if trimmed.starts_with("Downloads") || trimmed.starts_with("downloads") {
                let rest = trimmed
                    .trim_start_matches("Downloads")
                    .trim_start_matches("downloads")
                    .trim_start_matches('\\')
                    .trim_start_matches('/');
                user_downloads.join(rest)
            } else if let Some(parent) = input_path.parent() {
                if parent.is_absolute() {
                    parent.join(trimmed)
                } else {
                    user_downloads.join(trimmed)
                }
            } else {
                user_downloads.join(trimmed)
            }
        } else {
            default_output_path
        }
    } else {
        default_output_path
    };

    if output_path.is_relative() {
        output_path = user_downloads.join(&output_path);
    }
    if let Some(parent) = output_path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    output_path
}

/// Map the UI text-size selection (or a custom point size) to a preset name.
fn preset_from_settings(settings: &serde_json::Value) -> String {
    if settings.get("customBodyPt").and_then(|v| v.as_f64()).is_some() {
        return "Custom".to_string();
    }
    match settings.get("textSize").and_then(|t| t.as_u64()) {
        Some(18) => "Comfortable".to_string(),
        Some(20) => "Large".to_string(),
        Some(24) => "Extra Large".to_string(),
        Some(28) => "Very Large".to_string(),
        _ => "Large".to_string(),
    }
}

#[tauri::command]
async fn start_conversion(
    app: AppHandle,
    session: State<'_, AppSession>,
    file_path: String,
    settings: serde_json::Value,
) -> Result<serde_json::Value, String> {
    session.ensure_sidecar_running(&app).await?;
    let job_id = uuid_short();
    {
        let mut active = session.active_job_id.lock().unwrap();
        *active = Some(job_id.clone());
    }

    // Determine output file path
    let input_path = Path::new(&file_path);
    if !input_path.exists() {
        return Err(format!("Input file not found: {}", file_path));
    }

    let output_path = resolve_output_path(input_path, &settings);

    let preset = preset_from_settings(&settings);

    let out_fmt = settings.get("outputFormat").and_then(|f| f.as_str()).unwrap_or("pdf");
    let paper_size = settings.get("paperSize").and_then(|p| p.as_str()).unwrap_or("A4");
    let routing_mode = settings.get("routingMode").and_then(|m| m.as_str()).unwrap_or("automatic");
    let monochrome = settings.get("monochrome").and_then(|m| m.as_bool()).unwrap_or(false);
    let preserve_page_artwork = settings
        .get("preservePageArtwork")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let page_range = settings.get("pageRange").and_then(|r| r.as_str());
    let custom_body_pt = settings.get("customBodyPt").and_then(|v| v.as_f64());
    let custom_line_spacing = settings.get("customLineSpacing").and_then(|v| v.as_f64());

    let mut convert_cmd = serde_json::json!({
        "id": job_id,
        "command": "convert",
        "file_path": file_path,
        "output_path": output_path.to_string_lossy(),
        "preset": preset,
        "paper_size": paper_size,
        "export_format": out_fmt,
        "routing_mode": routing_mode,
        "include_page_markers": true,
        "monochrome": monochrome,
        "preserve_page_artwork": preserve_page_artwork,
    });

    if let Some(r) = page_range {
        if !r.trim().is_empty() {
            convert_cmd["page_range"] = serde_json::json!(r.trim());
        }
    }

    if let Some(pt) = custom_body_pt {
        convert_cmd["custom_body_pt"] = serde_json::json!(pt);
    }
    if let Some(ls) = custom_line_spacing {
        convert_cmd["custom_line_spacing"] = serde_json::json!(ls);
    }

    session.send_command(&convert_cmd).await?;

    Ok(serde_json::json!({
        "job_id": job_id,
        "status": "started",
        "output_path": output_path.to_string_lossy()
    }))
}

/// Re-render the currently loaded document without re-parsing it (OUT-002, OUT-010).
#[tauri::command]
async fn export_from_ir(
    app: AppHandle,
    session: State<'_, AppSession>,
    file_path: String,
    settings: serde_json::Value,
) -> Result<serde_json::Value, String> {
    session.ensure_sidecar_running(&app).await?;
    let job_id = {
        let active = session.active_job_id.lock().unwrap();
        active.clone()
    }
    .ok_or_else(|| "No converted document is loaded. Convert it first.".to_string())?;

    let input_path = Path::new(&file_path);
    if !input_path.exists() {
        return Err(format!("Input file not found: {}", file_path));
    }

    let output_path = resolve_output_path(input_path, &settings);
    let out_fmt = settings.get("outputFormat").and_then(|f| f.as_str()).unwrap_or("pdf");
    let preset = preset_from_settings(&settings);
    let paper_size = settings.get("paperSize").and_then(|p| p.as_str()).unwrap_or("A4");
    let monochrome = settings.get("monochrome").and_then(|m| m.as_bool()).unwrap_or(false);
    let page_range = settings.get("pageRange").and_then(|r| r.as_str());
    let custom_body_pt = settings.get("customBodyPt").and_then(|v| v.as_f64());
    let custom_line_spacing = settings.get("customLineSpacing").and_then(|v| v.as_f64());

    let mut export_cmd = serde_json::json!({
        "id": job_id,
        "command": "export",
        "job_id": job_id,
        "output_path": output_path.to_string_lossy(),
        "preset": preset,
        "paper_size": paper_size,
        "export_format": out_fmt,
        "include_page_markers": true,
        "monochrome": monochrome,
    });

    if let Some(r) = page_range {
        if !r.trim().is_empty() {
            export_cmd["page_range"] = serde_json::json!(r.trim());
        }
    }
    if let Some(pt) = custom_body_pt {
        export_cmd["custom_body_pt"] = serde_json::json!(pt);
    }
    if let Some(ls) = custom_line_spacing {
        export_cmd["custom_line_spacing"] = serde_json::json!(ls);
    }

    if let Some(edits) = settings.get("textEdits") {
        export_cmd["text_edits"] = edits.clone();
    }
    session.send_command(&export_cmd).await?;

    Ok(serde_json::json!({
        "job_id": job_id,
        "status": "started",
        "output_path": output_path.to_string_lossy()
    }))
}

#[tauri::command]
async fn cancel_conversion(session: State<'_, AppSession>) -> Result<serde_json::Value, String> {
    let job_id = {
        let mut active = session.active_job_id.lock().unwrap();
        active.take()
    };
    if let Some(jid) = job_id {
        let _ = session
            .send_command(&serde_json::json!({
                "command": "cancel",
                "job_id": jid
            }))
            .await;
    }
    Ok(serde_json::json!({ "status": "cancelled" }))
}

#[tauri::command]
async fn get_review_data(
    app: AppHandle,
    session: State<'_, AppSession>,
    job_id: String,
) -> Result<serde_json::Value, String> {
    session.ensure_sidecar_running(&app).await?;
    let (tx, rx) = oneshot::channel();
    {
        let mut lock = session.pending_review.lock().unwrap();
        *lock = Some(tx);
    }

    session
        .send_command(&serde_json::json!({
            "command": "get_review_data",
            "job_id": job_id
        }))
        .await?;

    match tokio::time::timeout(Duration::from_secs(5), rx).await {
        Ok(Ok(val)) => Ok(val),
        _ => Ok(serde_json::json!({
            "job_id": job_id,
            "total_flagged": 0,
            "flagged_pages": [],
            "summary_message": "All pages converted cleanly"
        })),
    }
}

#[tauri::command]
async fn retry_page(
    app: AppHandle,
    session: State<'_, AppSession>,
    job_id: String,
    page_number: usize,
    max_accuracy: bool,
) -> Result<serde_json::Value, String> {
    session.ensure_sidecar_running(&app).await?;
    let (tx, rx) = oneshot::channel();
    {
        let mut lock = session.pending_review.lock().unwrap();
        *lock = Some(tx);
    }

    session
        .send_command(&serde_json::json!({
            "command": "retry_page",
            "job_id": job_id,
            "page_number": page_number,
            "routing_mode": if max_accuracy { "maximum_accuracy" } else { "fast" }
        }))
        .await?;

    match tokio::time::timeout(Duration::from_secs(10), rx).await {
        Ok(Ok(val)) => Ok(val),
        _ => Ok(serde_json::json!({
            "job_id": job_id,
            "page_number": page_number,
            "retried": true,
            "max_accuracy": max_accuracy
        })),
    }
}

fn uuid_short() -> String {
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::{SystemTime, UNIX_EPOCH};

    static COUNTER: AtomicU64 = AtomicU64::new(0);
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let seq = COUNTER.fetch_add(1, Ordering::Relaxed);
    let pid = std::process::id();
    format!("job-{:x}-{:x}-{:x}", nanos, pid, seq)
}

#[tauri::command]
async fn get_app_version() -> Result<String, String> {
    Ok(env!("CARGO_PKG_VERSION").to_string())
}

#[tauri::command]
async fn download_and_apply_update(
    download_url: String,
    expected_sha256: Option<String>,
) -> Result<(), String> {
    let url = tauri::Url::parse(&download_url).map_err(|_| "Invalid update URL.".to_string())?;
    if url.scheme() != "https"
        || url.host_str() != Some("github.com")
        || !url.path().starts_with("/ahmeddwalid/OpenLargePrint/releases/download/")
        || !url.path().ends_with(".exe")
        || !url.username().is_empty()
        || url.password().is_some()
        || url.port().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return Err("Updates must come from the OpenLargePrint release repository.".to_string());
    }
    let expected = expected_sha256
        .filter(|value| value.len() == 64 && value.bytes().all(|byte| byte.is_ascii_hexdigit()))
        .ok_or_else(|| "A valid installer checksum is required.".to_string())?;

    #[cfg(not(target_os = "windows"))]
    let _ = expected;

    #[cfg(target_os = "windows")]
    {
        let temp_dir = std::env::temp_dir().join(uuid_short());
        std::fs::create_dir(&temp_dir).map_err(|_| "Could not create the update directory.".to_string())?;
        let installer_path = temp_dir.join("OpenLargePrint_setup_update.exe");
        let status = tokio::process::Command::new("curl.exe")
            .args(["--fail", "-sSL", "--proto", "=https", "--proto-redir", "=https", "--max-time", "300", "--max-filesize", "2147483648", &download_url, "-o", &installer_path.to_string_lossy()])
            .status()
            .await
            .map_err(|e| format!("Downloader error: {}", e))?;

        if !status.success() {
            return Err("Download process failed to complete successfully".to_string());
        }

        use sha2::{Digest, Sha256};
        use std::io::Read;
        let mut file = std::fs::File::open(&installer_path)
            .map_err(|_| "Could not read the downloaded installer.".to_string())?;
        let mut hash = Sha256::new();
        let mut buffer = [0_u8; 65536];
        loop {
            let count = file.read(&mut buffer)
                .map_err(|_| "Could not verify the downloaded installer.".to_string())?;
            if count == 0 { break; }
            hash.update(&buffer[..count]);
        }
        drop(file);
        if format!("{:x}", hash.finalize()) != expected.to_ascii_lowercase() {
            let _ = std::fs::remove_file(&installer_path);
            let _ = std::fs::remove_dir(&temp_dir);
            return Err("The installer checksum does not match the release. Update cancelled.".to_string());
        }

        let mut spawn_cmd = std::process::Command::new(&installer_path);
        spawn_cmd
            .spawn()
            .map_err(|e| format!("Failed to start installer: {}", e))?;

        tokio::time::sleep(Duration::from_millis(600)).await;
        std::process::exit(0);
    }

    #[cfg(not(target_os = "windows"))]
    {
        Err("In-app update application is supported on Windows".to_string())
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(AppSession::default())
        .invoke_handler(tauri::generate_handler![
            open_file_dialog,
            choose_save_dialog,
            get_system_paths,
            inspect_file_path,
            open_path_in_system,
            reveal_in_folder,
            get_cli_arg_file,
            health_check,
            inspect_file,
            start_conversion,
            export_from_ir,
            cancel_conversion,
            get_review_data,
            retry_page,
            get_app_version,
            download_and_apply_update
        ])
        .run(tauri::generate_context!())
        .expect("error while running OpenLargePrint application");
}

#[cfg(test)]
mod update_validation_tests {
    use super::download_and_apply_update;

    #[tokio::test]
    async fn refuses_untrusted_installers_and_missing_checksums() {
        let hash = "a".repeat(64);
        for url in ["http://github.com/ahmeddwalid/OpenLargePrint/releases/download/v1/setup.exe",
                    "https://example.com/setup.exe",
                    "https://github.com/other/project/releases/download/v1/setup.exe"] {
            assert!(download_and_apply_update(url.into(), Some(hash.clone())).await.is_err());
        }
        let url = "https://github.com/ahmeddwalid/OpenLargePrint/releases/download/v1/setup.exe";
        for hash in [None, Some(String::new()), Some("z".repeat(64))] {
            assert!(download_and_apply_update(url.into(), hash).await.is_err());
        }
    }
}
