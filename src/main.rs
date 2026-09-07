#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod player;
mod ytmusic;

use ksni::{menu::*, Tray, TrayMethods};
use player::{PlaybackStatus, Player, SharedPlayer};
use std::io::{Read, Write};
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::Instant;
use tauri::{
    Emitter, LogicalPosition, LogicalSize, Manager, WebviewWindow,
};
use ytmusic::Song;

const TRAY_ICON_BYTES: &[u8] = include_bytes!("../icons/tray.png");

struct AppState {
    player: SharedPlayer,
    #[allow(dead_code)]
    last_shown: Arc<Mutex<Instant>>,
}

fn get_home_dir() -> PathBuf {
    std::env::var("HOME").map(PathBuf::from).unwrap_or_else(|_| PathBuf::from("/home/dhruv"))
}

fn get_data_dir() -> PathBuf {
    std::env::var("XDG_DATA_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| get_home_dir().join(".local/share"))
}

fn get_sock_path() -> PathBuf {
    std::env::var("XDG_RUNTIME_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/tmp"))
        .join("omusic.sock")
}

#[tauri::command]
fn play_track(video_id: String, state: tauri::State<AppState>) -> Result<(), String> {
    let mut p = state.player.lock().map_err(|e| e.to_string())?;
    p.play(&video_id)
}

#[tauri::command]
fn toggle_play_pause(state: tauri::State<AppState>) -> Result<(), String> {
    let mut p = state.player.lock().map_err(|e| e.to_string())?;
    p.toggle_play_pause()
}

#[tauri::command]
fn pause_playback(pause: bool, state: tauri::State<AppState>) -> Result<(), String> {
    let mut p = state.player.lock().map_err(|e| e.to_string())?;
    p.pause(pause)
}

#[tauri::command]
fn seek_playback(seconds: f64, state: tauri::State<AppState>) -> Result<(), String> {
    let mut p = state.player.lock().map_err(|e| e.to_string())?;
    p.seek(seconds)
}

#[tauri::command]
fn set_volume(volume: f64, state: tauri::State<AppState>) -> Result<(), String> {
    let mut p = state.player.lock().map_err(|e| e.to_string())?;
    p.set_volume(volume)
}

#[tauri::command]
fn set_muted(muted: bool, state: tauri::State<AppState>) -> Result<(), String> {
    let mut p = state.player.lock().map_err(|e| e.to_string())?;
    p.set_muted(muted)
}

#[tauri::command]
fn get_playback_status(state: tauri::State<AppState>) -> Result<PlaybackStatus, String> {
    let mut p = state.player.lock().map_err(|e| e.to_string())?;
    Ok(p.get_status())
}

#[tauri::command]
async fn search_music(query: String, limit: Option<usize>) -> Result<Vec<Song>, String> {
    let lim = limit.unwrap_or(10);
    ytmusic::search_songs(&query, lim).await
}

#[tauri::command]
async fn get_radio(video_id: String, limit: Option<usize>) -> Result<Vec<Song>, String> {
    let lim = limit.unwrap_or(20);
    ytmusic::radio_playlist(&video_id, lim).await
}

#[tauri::command]
fn hide_window(window: WebviewWindow) -> Result<(), String> {
    window.hide().map_err(|e| e.to_string())
}

#[tauri::command]
fn quit_app(app_handle: tauri::AppHandle) {
    app_handle.exit(0);
}

fn toggle_window(
    app: &tauri::AppHandle,
    click_x: i32,
    click_y: i32,
    last_shown: &Arc<Mutex<Instant>>,
    has_focused: &Arc<Mutex<bool>>,
) {
    if let Some(window) = app.get_webview_window("main") {
        match window.is_visible() {
            Ok(true) => {
                let _ = window.hide();
                if let Ok(mut hf) = has_focused.lock() {
                    *hf = false;
                }
            }
            _ => {
                // Record activation time to prevent instant auto-hide from spurious events
                if let Ok(mut t) = last_shown.lock() {
                    *t = Instant::now();
                }
                if let Ok(mut hf) = has_focused.lock() {
                    *hf = false;
                }

                let window_w = 760;
                let window_h = 530;

                let (pos_x, pos_y) = if let Ok(Some(monitor)) = window.current_monitor() {
                    let screen_size = monitor.size();
                    let scale = monitor.scale_factor();
                    let s_w = (screen_size.width as f64 / scale) as i32;
                    let s_h = (screen_size.height as f64 / scale) as i32;

                    if click_x > 0 || click_y > 0 {
                        let cx_logical = if click_x > s_w { (click_x as f64 / scale) as i32 } else { click_x };
                        let cy_logical = if click_y > s_h { (click_y as f64 / scale) as i32 } else { click_y };

                        let cx = (cx_logical - window_w / 2).clamp(10, (s_w - window_w - 10).max(10));
                        let cy = if cy_logical < s_h / 2 {
                            // Top bar: drop down below icon
                            (cy_logical + 8).clamp(8, (s_h - window_h - 8).max(8))
                        } else {
                            // Bottom bar: pop up above icon
                            (cy_logical - window_h - 8).clamp(8, (s_h - window_h - 8).max(8))
                        };
                        (cx, cy)
                    } else {
                        // Fallback position
                        let cx = (s_w - window_w - 16).max(10);
                        let cy = 8;
                        (cx, cy)
                    }
                } else {
                    (50, 50)
                };

                let _ = window.set_size(LogicalSize::new(window_w as f64, window_h as f64));
                let _ = window.set_position(LogicalPosition::new(pos_x as f64, pos_y as f64));
                let _ = window.show();
                let _ = window.set_focus();
            }
        }
    }
}

struct OmusicTray {
    app: tauri::AppHandle,
    player: SharedPlayer,
    last_shown: Arc<Mutex<Instant>>,
    has_focused: Arc<Mutex<bool>>,
    icon_path: String,
}

impl Tray for OmusicTray {
    // Crucial: False means StatusNotifierItem hosts call activate() on left click!
    const MENU_ON_ACTIVATE: bool = false;

    fn id(&self) -> String {
        "omusic".into()
    }

    fn title(&self) -> String {
        "YouTube Music".into()
    }

    fn icon_name(&self) -> String {
        self.icon_path.clone()
    }

    fn icon_theme_path(&self) -> String {
        get_data_dir().join("icons").to_string_lossy().into()
    }

    fn activate(&mut self, x: i32, y: i32) {
        let app = self.app.clone();
        let last_shown = self.last_shown.clone();
        let has_focused = self.has_focused.clone();
        let _ = self.app.run_on_main_thread(move || {
            toggle_window(&app, x, y, &last_shown, &has_focused);
        });
    }

    fn menu(&self) -> Vec<MenuItem<Self>> {
        let app_handle = self.app.clone();
        let last_shown = self.last_shown.clone();
        let has_focused = self.has_focused.clone();
        let player = self.player.clone();

        vec![
            StandardItem {
                label: "Open / Close Player".into(),
                activate: Box::new(move |_| {
                    let app = app_handle.clone();
                    let ls = last_shown.clone();
                    let hf = has_focused.clone();
                    let _ = app_handle.run_on_main_thread(move || {
                        toggle_window(&app, 0, 0, &ls, &hf);
                    });
                }),
                ..Default::default()
            }
            .into(),
            StandardItem {
                label: "Play / Pause".into(),
                activate: Box::new(move |_| {
                    if let Ok(mut p) = player.lock() {
                        let _ = p.toggle_play_pause();
                    }
                }),
                ..Default::default()
            }
            .into(),
            MenuItem::Separator,
            StandardItem {
                label: "Quit omusic".into(),
                activate: Box::new(|this: &mut Self| {
                    this.app.exit(0);
                }),
                ..Default::default()
            }
            .into(),
        ]
    }
}

fn ensure_icon_file() -> PathBuf {
    let icon_dir = get_data_dir().join("icons");
    let _ = std::fs::create_dir_all(&icon_dir);
    let icon_path = icon_dir.join("omusic.png");
    if !icon_path.exists() {
        let _ = std::fs::write(&icon_path, TRAY_ICON_BYTES);
    }
    icon_path
}

fn main() {
    let sock_path = get_sock_path();

    // 1. Single-instance check: if another instance is already running, send toggle and exit
    if let Ok(mut stream) = UnixStream::connect(&sock_path) {
        let _ = stream.write_all(b"toggle\n");
        std::process::exit(0);
    }

    // Clean up dead socket if present
    let _ = std::fs::remove_file(&sock_path);

    let player = Arc::new(Mutex::new(Player::new()));
    let shared_player = player.clone();
    let last_shown = Arc::new(Mutex::new(Instant::now()));
    let last_shown_clone = last_shown.clone();
    let has_focused = Arc::new(Mutex::new(false));
    let has_focused_clone = has_focused.clone();

    let icon_path = ensure_icon_file();
    let icon_path_str = icon_path.to_string_lossy().to_string();

    tauri::Builder::default()
        .manage(AppState {
            player: shared_player,
            last_shown: last_shown_clone.clone(),
        })
        .setup(move |app| {
            let app_handle = app.handle().clone();

            // 2. Spawn native StatusNotifierItem tray via ksni
            let tray = OmusicTray {
                app: app_handle.clone(),
                player: player.clone(),
                last_shown: last_shown_clone.clone(),
                has_focused: has_focused_clone.clone(),
                icon_path: icon_path_str,
            };

            tauri::async_runtime::spawn(async move {
                match tray.spawn().await {
                    Ok(_handle) => {
                        println!("[omusic] Native StatusNotifierItem registered on DBus.");
                        loop {
                            tokio::time::sleep(tokio::time::Duration::from_secs(3600)).await;
                        }
                    }
                    Err(e) => {
                        eprintln!("[omusic] Failed to register SNI tray: {e}");
                    }
                }
            });

            // 3. Single-instance Unix socket listener
            if let Ok(listener) = UnixListener::bind(&sock_path) {
                let app_h = app.handle().clone();
                let ls = last_shown_clone.clone();
                let hf = has_focused_clone.clone();
                std::thread::spawn(move || {
                    for stream in listener.incoming() {
                        if let Ok(mut s) = stream {
                            let mut buf = [0u8; 16];
                            if let Ok(n) = s.read(&mut buf) {
                                if &buf[..n] == b"toggle\n" {
                                    let app = app_h.clone();
                                    let ls = ls.clone();
                                    let hf = hf.clone();
                                    let _ = app_h.run_on_main_thread(move || {
                                        toggle_window(&app, 0, 0, &ls, &hf);
                                    });
                                }
                            }
                        }
                    }
                });
            }

            // 4. Auto-hide when focus is lost (clicking outside the player after interaction)
            if let Some(window) = app.get_webview_window("main") {
                let win_clone = window.clone();
                let ls = last_shown_clone.clone();
                let hf = has_focused_clone.clone();
                window.on_window_event(move |event| {
                    match event {
                        tauri::WindowEvent::Focused(true) => {
                            if let Ok(mut h) = hf.lock() {
                                *h = true;
                            }
                        }
                        tauri::WindowEvent::Focused(false) => {
                            let is_hf = hf.lock().map(|h| *h).unwrap_or(false);
                            let elapsed = ls.lock().map(|t| t.elapsed().as_millis()).unwrap_or(0);
                            if is_hf && elapsed > 1000 {
                                let _ = win_clone.hide();
                                if let Ok(mut h) = hf.lock() {
                                    *h = false;
                                }
                            }
                        }
                        _ => {}
                    }
                });
            }

            // 5. Background playback status polling for webview
            let bg_player = player.clone();
            let bg_app = app.handle().clone();
            std::thread::spawn(move || loop {
                std::thread::sleep(std::time::Duration::from_millis(1000));
                if let Ok(mut p) = bg_player.lock() {
                    let status = p.get_status();
                    let _ = bg_app.emit("playback-status", status);
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            play_track,
            toggle_play_pause,
            pause_playback,
            seek_playback,
            set_volume,
            set_muted,
            get_playback_status,
            search_music,
            get_radio,
            hide_window,
            quit_app
        ])
        .run(tauri::generate_context!())
        .expect("error while running omusic");
}
