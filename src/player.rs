use std::io::{Read, Write};
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlaybackStatus {
    pub position: f64,
    pub duration: f64,
    pub volume: f64,
    pub muted: bool,
    pub is_playing: bool,
}

pub struct Player {
    child: Option<Child>,
    socket_path: PathBuf,
    volume: f64,
    muted: bool,
    is_paused: bool,
}

impl Player {
    pub fn new() -> Self {
        let run_dir = std::env::var("XDG_RUNTIME_DIR")
            .unwrap_or_else(|_| format!("/run/user/{}", unsafe { libc::getuid() }));
        let socket_path = PathBuf::from(run_dir).join("omusic-mpv.sock");
        Self {
            child: None,
            socket_path,
            volume: 100.0,
            muted: false,
            is_paused: false,
        }
    }

    pub fn play(&mut self, video_id: &str) -> Result<(), String> {
        self.stop();

        // Clean old socket
        let _ = std::fs::remove_file(&self.socket_path);

        let socket_str = self.socket_path.to_string_lossy().to_string();
        let mut cmd = Command::new("mpv");
        cmd.args([
            "--no-video",
            "--force-window=no",
            "--really-quiet",
            &format!("--input-ipc-server={}", socket_str),
            "--ytdl-raw-options=extractor-args=youtube:player_client=android",
            "--ytdl-format=bestaudio/best",
            &format!("--volume={}", self.volume as u32),
            &format!("--mute={}", if self.muted { "yes" } else { "no" }),
            &format!("https://music.youtube.com/watch?v={}", video_id),
        ]);

        // KERNEL PROCESS SAFETY: If parent dies, kill mpv instantly
        #[cfg(target_os = "linux")]
        unsafe {
            use std::os::unix::process::CommandExt;
            cmd.pre_exec(|| {
                libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL);
                Ok(())
            });
        }

        let child = cmd.spawn().map_err(|e| format!("Failed to spawn mpv: {}", e))?;
        self.child = Some(child);
        self.is_paused = false;
        Ok(())
    }

    pub fn stop(&mut self) {
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        let _ = std::fs::remove_file(&self.socket_path);
        self.is_paused = true;
    }

    fn send_command(&self, cmd: serde_json::Value) -> Result<serde_json::Value, String> {
        let mut stream = UnixStream::connect(&self.socket_path)
            .map_err(|e| format!("Socket connect error: {}", e))?;
        stream
            .set_read_timeout(Some(Duration::from_millis(500)))
            .map_err(|e| e.to_string())?;
        stream
            .set_write_timeout(Some(Duration::from_millis(500)))
            .map_err(|e| e.to_string())?;

        let payload = format!("{}\n", cmd);
        stream
            .write_all(payload.as_bytes())
            .map_err(|e| e.to_string())?;

        let mut buf = [0u8; 4096];
        let n = stream.read(&mut buf).map_err(|e| e.to_string())?;
        let resp_str = String::from_utf8_lossy(&buf[..n]);
        serde_json::from_str(&resp_str).map_err(|e| e.to_string())
    }

    pub fn pause(&mut self, pause: bool) -> Result<(), String> {
        let cmd = serde_json::json!({
            "command": ["set_property", "pause", pause]
        });
        self.send_command(cmd)?;
        self.is_paused = pause;
        Ok(())
    }

    pub fn toggle_play_pause(&mut self) -> Result<(), String> {
        let new_state = !self.is_paused;
        self.pause(new_state)
    }

    pub fn seek(&mut self, seconds: f64) -> Result<(), String> {
        let cmd = serde_json::json!({
            "command": ["set_property", "time-pos", seconds.max(0.0)]
        });
        self.send_command(cmd).map(|_| ())
    }

    pub fn set_volume(&mut self, volume: f64) -> Result<(), String> {
        let v = volume.clamp(0.0, 100.0);
        self.volume = v;
        let cmd = serde_json::json!({
            "command": ["set_property", "volume", v]
        });
        self.send_command(cmd).map(|_| ())
    }

    pub fn set_muted(&mut self, muted: bool) -> Result<(), String> {
        self.muted = muted;
        let cmd = serde_json::json!({
            "command": ["set_property", "mute", muted]
        });
        self.send_command(cmd).map(|_| ())
    }

    pub fn get_status(&mut self) -> PlaybackStatus {
        let is_running = if let Some(ref mut child) = self.child {
            match child.try_wait() {
                Ok(None) => true,
                _ => false,
            }
        } else {
            false
        };

        if !is_running {
            return PlaybackStatus {
                position: 0.0,
                duration: 0.0,
                volume: self.volume,
                muted: self.muted,
                is_playing: false,
            };
        }

        let pos_cmd = serde_json::json!({"command": ["get_property", "time-pos"]});
        let dur_cmd = serde_json::json!({"command": ["get_property", "duration"]});
        let vol_cmd = serde_json::json!({"command": ["get_property", "volume"]});
        let mut_cmd = serde_json::json!({"command": ["get_property", "mute"]});

        let pos = self
            .send_command(pos_cmd)
            .ok()
            .and_then(|v| v.get("data").and_then(|d| d.as_f64()))
            .unwrap_or(0.0);
        let dur = self
            .send_command(dur_cmd)
            .ok()
            .and_then(|v| v.get("data").and_then(|d| d.as_f64()))
            .unwrap_or(0.0);
        if let Some(v) = self
            .send_command(vol_cmd)
            .ok()
            .and_then(|v| v.get("data").and_then(|d| d.as_f64()))
        {
            self.volume = v;
        }
        if let Some(m) = self
            .send_command(mut_cmd)
            .ok()
            .and_then(|v| v.get("data").and_then(|d| d.as_bool()))
        {
            self.muted = m;
        }

        PlaybackStatus {
            position: pos,
            duration: dur,
            volume: self.volume,
            muted: self.muted,
            is_playing: is_running && !self.is_paused,
        }
    }
}

impl Drop for Player {
    fn drop(&mut self) {
        self.stop();
    }
}

pub type SharedPlayer = Arc<Mutex<Player>>;
