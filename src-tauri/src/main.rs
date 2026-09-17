// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, State};

#[derive(Debug, Serialize, Deserialize)]
pub struct ConversionSettingsPayload {
    pub text_size: u32,
    pub paper_size: String,
    pub output_format: String,
    pub routing_mode: String,
    pub page_range: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct InspectResultPayload {
    pub file_path: String,
    pub mime_type: String,
    pub page_count: usize,
    pub detected_type: String,
    pub estimated_duration_seconds: Option<f64>,
}

#[derive(Default)]
pub struct AppSession {
    pub active_job_id: Mutex<Option<String>>,
}

#[tauri::command]
fn health_check() -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({
        "status": "ok",
        "desktop_version": "0.1.0"
    }))
}

#[tauri::command]
async fn inspect_file(file_path: String) -> Result<serde_json::Value, String> {
    // In production, launches "openlargeprint sidecar" with typed InspectCommand
    // Subprocess calls use argument arrays without shell concatenation (SEC-008)
    Ok(serde_json::json!({
        "file_path": file_path,
        "mime_type": "application/pdf",
        "page_count": 6,
        "detected_type": "native_pdf",
        "estimated_duration_seconds": 3.5
    }))
}

#[tauri::command]
async fn start_conversion(
    app: AppHandle,
    session: State<'_, AppSession>,
    file_path: String,
    settings: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let job_id = uuid_short();
    {
        let mut active = session.active_job_id.lock().unwrap();
        *active = Some(job_id.clone());
    }

    // Emit initial progress
    let _ = app.emit(
        "sidecar-progress",
        serde_json::json!({
            "stage": "starting",
            "current_page": 0,
            "total_pages": 6,
            "message": "Starting conversion...",
            "percent": 0.0
        }),
    );

    Ok(serde_json::json!({
        "job_id": job_id,
        "status": "started"
    }))
}

#[tauri::command]
async fn cancel_conversion(session: State<'_, AppSession>) -> Result<serde_json::Value, String> {
    let mut active = session.active_job_id.lock().unwrap();
    *active = None;
    Ok(serde_json::json!({ "status": "cancelled" }))
}

#[tauri::command]
async fn get_review_data(job_id: String) -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({
        "job_id": job_id,
        "flagged_pages": []
    }))
}

#[tauri::command]
async fn retry_page(
    job_id: String,
    page_number: usize,
    max_accuracy: bool,
) -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({
        "job_id": job_id,
        "page_number": page_number,
        "retried": true,
        "max_accuracy": max_accuracy
    }))
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
