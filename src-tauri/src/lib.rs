use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::{Emitter, Manager, WindowEvent};

struct PythonBackend {
    child: Mutex<Option<Child>>,
    started: Mutex<bool>,
}

/// Project root = parent of src-tauri (where Cargo.toml lives).
fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("no parent dir")
        .to_path_buf()
}

/// Start the Python FastAPI backend as a sidecar process.
fn start_backend() -> Option<Child> {
    let python = if cfg!(target_os = "windows") {
        "python"
    } else {
        "python3"
    };

    match Command::new(python)
        .current_dir(project_root())
        .args([
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--log-level",
            "warning",
        ])
        .spawn()
    {
        Ok(child) => {
            log::info!("Python backend started (pid: {})", child.id());
            Some(child)
        }
        Err(e) => {
            log::error!("Failed to start Python backend: {}", e);
            None
        }
    }
}

/// Kill the Python backend process.
fn stop_backend(child: &mut Option<Child>) {
    if let Some(ref mut c) = child {
        let _ = c.kill();
        let _ = c.wait();
        log::info!("Python backend stopped");
    }
}

// ── Tauri Commands ──

#[tauri::command]
fn read_file_content(path: String) -> Result<String, String> {
    std::fs::read_to_string(&path).map_err(|e| format!("Failed to read {}: {}", path, e))
}

#[tauri::command]
fn file_exists(path: String) -> bool {
    std::path::Path::new(&path).exists()
}

#[tauri::command]
fn is_backend_running(state: tauri::State<PythonBackend>) -> bool {
    *state.started.lock().unwrap()
}

#[tauri::command]
fn restart_backend(state: tauri::State<PythonBackend>) -> Result<(), String> {
    let mut child = state.child.lock().unwrap();
    stop_backend(&mut child);
    *child = start_backend();
    Ok(())
}

#[tauri::command]
fn start_folder_watch(
    path: String,
    app: tauri::AppHandle,
) -> Result<(), String> {
    use notify::{Config, Event, EventKind, RecommendedWatcher, RecursiveMode, Watcher};
    use std::path::PathBuf;

    let watch_path = PathBuf::from(&path);
    if !watch_path.exists() {
        return Err(format!("Path does not exist: {}", path));
    }

    let (tx, mut rx) = tokio::sync::mpsc::channel(32);

    let mut watcher = RecommendedWatcher::new(
        move |res: Result<Event, notify::Error>| {
            if let Ok(event) = res {
                match event.kind {
                    EventKind::Create(_) | EventKind::Modify(_) => {
                        for p in &event.paths {
                            let _ = tx.blocking_send(p.to_string_lossy().to_string());
                        }
                    }
                    _ => {}
                }
            }
        },
        Config::default(),
    )
    .map_err(|e| e.to_string())?;

    watcher
        .watch(&watch_path, RecursiveMode::NonRecursive)
        .map_err(|e| e.to_string())?;

    // Spawn async handler that emits events to frontend
    tauri::async_runtime::spawn(async move {
        while let Some(file_path) = rx.recv().await {
            let _ = app.emit("folder:change", file_path);
        }
        drop(watcher);
    });

    log::info!("Started watching folder: {}", path);
    Ok(())
}

// ── Application Entry ──

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            // Configure logging in debug mode
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Start Python backend
            let child = start_backend();
            let started = child.is_some();

            app.manage(PythonBackend {
                child: Mutex::new(child),
                started: Mutex::new(started),
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::Destroyed = event {
                let state = window.state::<PythonBackend>();
                let mut child = state.child.lock().unwrap();
                stop_backend(&mut child);
            }
        })
        .invoke_handler(tauri::generate_handler![
            read_file_content,
            file_exists,
            is_backend_running,
            restart_backend,
            start_folder_watch,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
