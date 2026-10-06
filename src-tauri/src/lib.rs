use std::env;
use std::fs::OpenOptions;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;
use tauri::{Manager, RunEvent};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

/// Windows: 不弹出控制台黑窗
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

const DEFAULT_BACKEND_PORT: u16 = 28147;

struct BackendProcess(Mutex<Option<Child>>);

fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("failed to resolve project root")
        .to_path_buf()
}

fn python_executable(root: &Path) -> PathBuf {
    let venv_python = if cfg!(windows) {
        root.join(".venv").join("Scripts").join("python.exe")
    } else {
        root.join(".venv").join("bin").join("python")
    };

    if venv_python.exists() {
        venv_python
    } else if cfg!(windows) {
        PathBuf::from("python")
    } else {
        PathBuf::from("python3")
    }
}

fn resource_search_dirs(resource_dir: Option<&Path>) -> Vec<PathBuf> {
    let mut dirs = Vec::new();
    if let Some(dir) = resource_dir {
        dirs.push(dir.to_path_buf());
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            dirs.push(parent.to_path_buf());
            dirs.push(parent.join("resources"));
        }
    }
    dirs.push(project_root());
    dirs
}

fn bundled_backend_executable(resource_dir: Option<&Path>) -> Option<PathBuf> {
    for base in resource_search_dirs(resource_dir) {
        let dir = base.join("bin").join("telegram-backend");
        let exe = if cfg!(windows) {
            dir.join("telegram-backend.exe")
        } else {
            dir.join("telegram-backend")
        };
        if exe.exists() {
            return Some(exe);
        }
    }
    None
}

fn read_backend_port_from(path: &Path) -> Option<u16> {
    let text = std::fs::read_to_string(path).ok()?;
    let value: serde_json::Value = serde_json::from_str(&text).ok()?;
    value["backend"]["port"].as_u64().map(|p| p as u16)
}

fn backend_port(resource_dir: Option<&Path>) -> u16 {
    for base in resource_search_dirs(resource_dir) {
        let candidate = base.join("config").join("ports.json");
        if let Some(port) = read_backend_port_from(&candidate) {
            return port;
        }
    }
    DEFAULT_BACKEND_PORT
}

fn backend_is_healthy(port: u16) -> bool {
    let addr: SocketAddr = format!("127.0.0.1:{}", port)
        .parse()
        .unwrap_or_else(|_| {
            format!("127.0.0.1:{}", DEFAULT_BACKEND_PORT)
                .parse()
                .expect("valid fallback address")
        });

    let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(800)) {
        Ok(stream) => stream,
        Err(_) => return false,
    };

    let _ = stream.set_read_timeout(Some(Duration::from_millis(800)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(800)));

    let request = format!(
        "GET /health HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nConnection: close\r\n\r\n",
        port
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }

    let mut response = String::new();
    let mut buffer = [0_u8; 512];
    loop {
        match stream.read(&mut buffer) {
            Ok(0) => break,
            Ok(count) => {
                response.push_str(&String::from_utf8_lossy(&buffer[..count]));
                if response.contains("\r\n\r\n") {
                    break;
                }
            }
            Err(_) => break,
        }
    }

    response.starts_with("HTTP/1.1 200") || response.contains("\"status\"")
}

fn wait_until_healthy(port: u16, attempts: u32) -> bool {
    for _ in 0..attempts {
        if backend_is_healthy(port) {
            return true;
        }
        thread::sleep(Duration::from_millis(400));
    }
    false
}

fn configure_silent(cmd: &mut Command, data_root: &Path) {
    let _ = std::fs::create_dir_all(data_root);
    let log_path = data_root.join("backend-startup.log");
    cmd.stdin(Stdio::null());
    match OpenOptions::new().create(true).append(true).open(&log_path) {
        Ok(file) => match file.try_clone() {
            Ok(clone) => {
                cmd.stdout(Stdio::from(clone)).stderr(Stdio::from(file));
            }
            Err(_) => {
                cmd.stdout(Stdio::null()).stderr(Stdio::from(file));
            }
        },
        Err(_) => {
            cmd.stdout(Stdio::null()).stderr(Stdio::null());
        }
    }

    #[cfg(windows)]
    {
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
}

fn start_backend_with_python(root: &Path, data_root: &Path) -> Option<Child> {
    let python = python_executable(root);
    let mut cmd = Command::new(python);
    cmd.args(["-m", "backend.main"])
        .current_dir(root)
        .env("PAPERWING_DATA", data_root)
        .env("TELEGRAM_TOOLS_DATA", data_root);
    configure_silent(&mut cmd, data_root);
    match cmd.spawn() {
        Ok(child) => Some(child),
        Err(err) => {
            eprintln!("[纸翼] 用 Python 启动后端失败: {err}");
            None
        }
    }
}

fn start_backend_with_bundle(resource_dir: Option<&Path>, data_root: &Path) -> Option<Child> {
    let exe = match bundled_backend_executable(resource_dir) {
        Some(path) => path,
        None => {
            eprintln!("[纸翼] 未找到内嵌后端 telegram-backend.exe");
            return None;
        }
    };
    let work_dir = exe.parent()?.to_path_buf();
    let mut cmd = Command::new(&exe);
    cmd.current_dir(&work_dir)
        .env("PAPERWING_DATA", data_root)
        .env("TELEGRAM_TOOLS_DATA", data_root);
    configure_silent(&mut cmd, data_root);
    match cmd.spawn() {
        Ok(child) => {
            eprintln!("[纸翼] 已静默拉起内嵌后端: {}", exe.display());
            Some(child)
        }
        Err(err) => {
            eprintln!("[纸翼] 启动内嵌后端失败: {err}");
            None
        }
    }
}

fn env_data_dir() -> Option<PathBuf> {
    for key in ["PAPERWING_DATA", "TELEGRAM_TOOLS_DATA"] {
        if let Ok(dir) = env::var(key) {
            let path = PathBuf::from(dir.trim());
            if !path.as_os_str().is_empty() {
                return Some(path);
            }
        }
    }
    None
}

fn resolve_data_root(app_data_dir: Option<PathBuf>) -> PathBuf {
    // debug（tauri dev）：项目 data/，可用环境变量覆盖
    // release（打包安装包）：默认 %AppData%\com.paperwing.app，绝不回退到编译机源码路径
    // 发版多开仍可用 PAPERWING_DATA 指向独立目录
    if cfg!(debug_assertions) {
        return env_data_dir().unwrap_or_else(|| project_root().join("data"));
    }
    if let Some(dir) = env_data_dir() {
        return dir;
    }
    app_data_dir.unwrap_or_else(|| {
        env::current_exe()
            .ok()
            .and_then(|exe| exe.parent().map(|dir| dir.join("data")))
            .unwrap_or_else(|| PathBuf::from("data"))
    })
}

fn start_backend(resource_dir: Option<PathBuf>, data_root: PathBuf) -> Option<Child> {
    let root = project_root();
    let port = backend_port(resource_dir.as_deref());

    if backend_is_healthy(port) {
        eprintln!(
            "[纸翼] Backend already running on http://127.0.0.1:{}/health",
            port
        );
        return None;
    }

    let child = if cfg!(not(debug_assertions)) {
        start_backend_with_bundle(resource_dir.as_deref(), &data_root)
            .or_else(|| start_backend_with_python(&root, &data_root))
    } else {
        start_backend_with_python(&root, &data_root)
            .or_else(|| start_backend_with_bundle(resource_dir.as_deref(), &data_root))
    };

    if child.is_some() {
        if wait_until_healthy(port, 40) {
            eprintln!("[纸翼] 后端已就绪 http://127.0.0.1:{}/health", port);
        } else {
            eprintln!(
                "[纸翼] 后端启动超时，请查看 {}\\backend-startup.log",
                data_root.display()
            );
        }
    }

    child
}

fn stop_backend(state: &BackendProcess) {
    if let Ok(mut guard) = state.0.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let resource_dir = app.path().resource_dir().ok();
            let data_root = resolve_data_root(app.path().app_data_dir().ok());
            eprintln!("[纸翼] 数据目录 {}", data_root.display());
            if let Some(child) = start_backend(resource_dir, data_root) {
                app.manage(BackendProcess(Mutex::new(Some(child))));
            } else {
                // 已有外部后端或启动失败时也挂空状态，避免 Exit 时 panic
                app.manage(BackendProcess(Mutex::new(None)));
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                if let Some(state) = app_handle.try_state::<BackendProcess>() {
                    stop_backend(&state);
                }
            }
        });
}
