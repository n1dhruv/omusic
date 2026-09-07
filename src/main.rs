#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod player;
mod ytmusic;

use player::{PlaybackStatus, Player, SharedPlayer};
use std::sync::{Arc, Mutex};
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Emitter, Manager, PhysicalPosition, PhysicalSize, WebviewWindow,
};
use ytmusic::Song;

struct AppState {
    player: SharedPlayer,
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

fn anchor_window_to_tray(window: &WebviewWindow, tray_rect: Option<tauri::Rect>) {
    let Ok(monitor) = window.current_monitor() else { return };
    let Some(monitor) = monitor else { return };
    let screen_size = monitor.size();
    let window_w = 760;
    let window_h = 530;

    let (pos_x, pos_y) = if let Some(rect) = tray_rect {
        let (rx, ry) = match rect.position {
            tauri::Position::Physical(p) => (p.x, p.y),
            tauri::Position::Logical(l) => (l.x as i32, l.y as i32),
        };
        let (rw, rh) = match rect.size {
            tauri::Size::Physical(s) => (s.width as i32, s.height as i32),
            tauri::Size::Logical(l) => (l.width as i32, l.height as i32),
        };

        let center_x = rx + (rw / 2);
        let mut x = center_x - (window_w / 2);
        x = x.clamp(8, screen_size.width as i32 - window_w - 8);

        let y = if ry < (screen_size.height as i32 / 2) {
            ry + rh + 6
        } else {
            ry - window_h - 6
        };
        (x, y)
    } else {
        // Fallback: top right near menu bar
        let x = (screen_size.width as i32 - window_w - 14).max(8);
        let y = 8;
        (x, y)
    };

    let _ = window.set_size(PhysicalSize::new(window_w as u32, window_h as u32));
    let _ = window.set_position(PhysicalPosition::new(pos_x, pos_y));
}

fn toggle_window(app: &tauri::AppHandle, tray_rect: Option<tauri::Rect>) {
    if let Some(window) = app.get_webview_window("main") {
        if let Ok(is_visible) = window.is_visible() {
            if is_visible {
                let _ = window.hide();
            } else {
                anchor_window_to_tray(&window, tray_rect);
                let _ = window.show();
                let _ = window.set_focus();
            }
        }
    }
}

fn main() {
    let player = Arc::new(Mutex::new(Player::new()));
    let shared_player = player.clone();

    tauri::Builder::default()
        .manage(AppState { player: shared_player })
        .setup(move |app| {
            // Context menu for right-click on tray
            let quit_i = MenuItem::with_id(app, "quit", "Quit omusic", true, None::<&str>)?;
            let pp_i = MenuItem::with_id(app, "play_pause", "Play / Pause", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&pp_i, &quit_i])?;

            // Load tray icon
            let icon = tauri::include_image!("icons/tray.png");

            let app_handle = app.handle().clone();
            let _tray = TrayIconBuilder::new()
                .icon(icon)
                .tooltip("YouTube Music · Menu Bar")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(move |app, event| {
                    match event.id.as_ref() {
                        "quit" => app.exit(0),
                        "play_pause" => {
                            let state = app.state::<AppState>();
                            if let Ok(mut p) = state.player.lock() {
                                let _ = p.toggle_play_pause();
                            };
                        }
                        _ => {}
                    }
                })
                .on_tray_icon_event(move |_tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        rect,
                        ..
                    } = event
                    {
                        toggle_window(&app_handle, Some(rect));
                    }
                })
                .build(app)?;

            // Automatically hide window when clicking outside (focus loss)
            if let Some(window) = app.get_webview_window("main") {
                let win_clone = window.clone();
                window.on_window_event(move |event| {
                    if let tauri::WindowEvent::Focused(false) = event {
                        let _ = win_clone.hide();
                    }
                });
            }

            // Background status polling thread sending updates to webview
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
