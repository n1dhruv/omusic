use serde::{Deserialize, Serialize};
use tokio::process::Command;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Song {
    #[serde(rename = "videoId")]
    pub video_id: String,
    pub title: String,
    pub artist: String,
    pub duration: String,
    pub thumbnail: String,
}

pub async fn search_songs(query: &str, limit: usize) -> Result<Vec<Song>, String> {
    let search_arg = format!("ytsearch{}:{}", limit, query);
    let output = Command::new("yt-dlp")
        .args([
            &search_arg,
            "--dump-json",
            "--flat-playlist",
            "--no-warnings",
            "--quiet",
        ])
        .output()
        .await
        .map_err(|e| format!("yt-dlp search error: {}", e))?;

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let mut songs = Vec::new();

    for line in stdout.lines() {
        if line.trim().is_empty() {
            continue;
        }
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(line) {
            let id = val.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
            if id.is_empty() {
                continue;
            }
            let title = val
                .get("title")
                .and_then(|v| v.as_str())
                .unwrap_or("Unknown Title")
                .to_string();
            let artist = val
                .get("channel")
                .or_else(|| val.get("uploader"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let duration = val
                .get("duration_string")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();

            let thumbnail = val
                .get("thumbnails")
                .and_then(|t| t.as_array())
                .and_then(|arr| arr.last())
                .and_then(|t| t.get("url"))
                .and_then(|u| u.as_str())
                .unwrap_or("")
                .to_string();

            songs.push(Song {
                video_id: id,
                title,
                artist,
                duration,
                thumbnail,
            });
        }
    }

    Ok(songs)
}

pub async fn radio_playlist(video_id: &str, limit: usize) -> Result<Vec<Song>, String> {
    let url = format!("https://music.youtube.com/watch?v={}&list=RDAMVM{}", video_id, video_id);
    let output = Command::new("yt-dlp")
        .args([
            &url,
            "--dump-json",
            "--flat-playlist",
            "--playlist-end",
            &limit.to_string(),
            "--no-warnings",
            "--quiet",
        ])
        .output()
        .await
        .map_err(|e| format!("yt-dlp radio error: {}", e))?;

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let mut songs = Vec::new();

    for line in stdout.lines() {
        if line.trim().is_empty() {
            continue;
        }
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(line) {
            let id = val.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
            if id.is_empty() || id == video_id {
                continue;
            }
            let title = val
                .get("title")
                .and_then(|v| v.as_str())
                .unwrap_or("Unknown Title")
                .to_string();
            let artist = val
                .get("channel")
                .or_else(|| val.get("uploader"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let duration = val
                .get("duration_string")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();

            let thumbnail = val
                .get("thumbnails")
                .and_then(|t| t.as_array())
                .and_then(|arr| arr.last())
                .and_then(|t| t.get("url"))
                .and_then(|u| u.as_str())
                .unwrap_or("")
                .to_string();

            songs.push(Song {
                video_id: id,
                title,
                artist,
                duration,
                thumbnail,
            });
        }
    }

    Ok(songs)
}
