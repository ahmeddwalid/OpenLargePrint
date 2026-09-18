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
            return Ok(());
        }

        let sidecar_exe = resolve_sidecar_binary();
        let mut child = Command::new(&sidecar_exe)
            .args(["sidecar"])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| format!("Failed to launch sidecar ({}): {}", sidecar_exe.display(), e))?;

        let stdin = child.stdin.take().ok_or("Failed to open sidecar stdin")?;
        let stdout = child.stdout.take().ok_or("Failed to open sidecar stdout")?;

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
        });

        Ok(())
    }

    pub async fn send_command(&self, json_val: &serde_json::Value) -> Result<(), String> {
        let mut stdin_guard = self.stdin.lock().await;
        if let Some(ref mut stdin) = *stdin_guard {
            let mut data = json_val.to_string();
            data.push('\n');
            stdin
                .write_all(data.as_bytes())
                .await
                .map_err(|e| format!("Failed to write to sidecar: {}", e))?;
            stdin
                .flush()
                .await
                .map_err(|e| format!("Failed to flush sidecar: {}", e))?;
            Ok(())
        } else {
            Err("Sidecar process is not running".to_string())
        }
    }
}

fn resolve_sidecar_binary() -> PathBuf {
    // 1. Check relative to current executable (production bundle)
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            let candidate = exe_dir.join("openlargeprint-sidecar.exe");
            if candidate.exists() {
                return candidate;
            }
            let candidate_named = exe_dir.join("openlargeprint-sidecar-x86_64-pc-windows-msvc.exe");
            if candidate_named.exists() {
                return candidate_named;
            }
            let engine_sub = exe_dir.join("engine").join("openlargeprint-sidecar.exe");
            if engine_sub.exists() {
                return engine_sub;
            }
        }
    }
    // 2. Check development binaries folder
    let dev_bin = PathBuf::from("binaries/openlargeprint-sidecar-x86_64-pc-windows-msvc.exe");
    if dev_bin.exists() {
        return dev_bin;
    }
    let dev_src = PathBuf::from("src-tauri/binaries/openlargeprint-sidecar-x86_64-pc-windows-msvc.exe");
    if dev_src.exists() {
        return dev_src;
    }
    let dist_bin = PathBuf::from("packaging/dist/openlargeprint-sidecar-x86_64-pc-windows-msvc.exe");
    if dist_bin.exists() {
        return dist_bin;
    }
    // 3. Fallback
    PathBuf::from("openlargeprint-sidecar-x86_64-pc-windows-msvc.exe")
}

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

#[tauri::command]
async fn get_system_paths() -> Result<serde_json::Value, String> {
    let user_profile = std::env::var("USERPROFILE").unwrap_or_else(|_| ".".to_string());
    let up = PathBuf::from(&user_profile);
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
async fn open_file_dialog() -> Result<Option<serde_json::Value>, String> {
    tokio::task::spawn_blocking(|| {
        #[cfg(target_os = "windows")]
        {
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
            Ok(None)
        }
    })
    .await
    .map_err(|e| format!("Dialog task error: {}", e))?
}

#[tauri::command]
async fn choose_save_dialog(
    default_name: Option<String>,
    filter_ext: Option<String>,
    initial_dir: Option<String>,
) -> Result<Option<String>, String> {
    tokio::task::spawn_blocking(move || {
        #[cfg(target_os = "windows")]
        {
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
            Ok(None)
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
        std::process::Command::new("explorer")
            .arg(&p)
            .spawn()
            .map_err(|e| format!("Failed to open file: {}", e))?;
        Ok(())
    }
    #[cfg(not(target_os = "windows"))]
    {
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
        std::process::Command::new("explorer")
            .args(["/select,", &p.to_string_lossy()])
            .spawn()
            .map_err(|e| format!("Failed to reveal path: {}", e))?;
        Ok(())
    }
    #[cfg(not(target_os = "windows"))]
    {
        Ok(())
    }
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
            "desktop_version": "0.1.0",
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
    let stem = input_path.file_stem().unwrap_or_default().to_string_lossy();
    let out_fmt = settings.get("outputFormat").and_then(|f| f.as_str()).unwrap_or("pdf");
    let ext = match out_fmt {
        "docx" => "docx",
        "reader" | "html" => "html",
        _ => "pdf",
    };
    let parent_dir = input_path.parent().unwrap_or_else(|| Path::new("."));
    let default_output_path = parent_dir.join(format!("{}-largeprint.{}", stem, ext));

    let output_path = if let Some(custom_path) = settings.get("outputPath").and_then(|p| p.as_str()) {
        let trimmed = custom_path.trim();
        if !trimmed.is_empty() {
            PathBuf::from(trimmed)
        } else {
            default_output_path
        }
    } else {
        default_output_path
    };

    let preset = settings.get("textSize").and_then(|t| t.as_u64()).map(|s| {
        match s {
            18 => "Comfortable",
            20 => "Large",
            24 => "Extra Large",
            28 => "Very Large",
            _ => "Large",
        }
    }).unwrap_or("Large");

    let paper_size = settings.get("paperSize").and_then(|p| p.as_str()).unwrap_or("A4");
    let routing_mode = settings.get("routingMode").and_then(|m| m.as_str()).unwrap_or("maximum_accuracy");

    let convert_cmd = serde_json::json!({
        "id": job_id,
        "command": "convert",
        "file_path": file_path,
        "output_path": output_path.to_string_lossy(),
        "preset": preset,
        "paper_size": paper_size,
        "export_format": out_fmt,
        "routing_mode": routing_mode,
        "include_page_markers": true
    });

    session.send_command(&convert_cmd).await?;

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
    use std::time::{SystemTime, UNIX_EPOCH};
    let ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_millis();
    format!("job-{:x}", ms)
}

fn main() {
    tauri::Builder::default()
        .manage(AppSession::default())
        .invoke_handler(tauri::generate_handler![
            open_file_dialog,
            choose_save_dialog,
            get_system_paths,
            inspect_file_path,
            open_path_in_system,
            reveal_in_folder,
            health_check,
            inspect_file,
            start_conversion,
            cancel_conversion,
            get_review_data,
            retry_page
        ])
        .run(tauri::generate_context!())
        .expect("error while running OpenLargePrint application");
}
