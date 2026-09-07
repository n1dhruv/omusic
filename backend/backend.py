#!/usr/bin/env python3
# omusic backend — portable, works on any distro.
# Auto re-exec inside venv if ytmusicapi is not available.
import sys, os

_data_dir = os.path.expanduser("~/.local/share/omusic")
_venv_py  = os.path.join(_data_dir, "venv", "bin", "python3")
if os.path.isfile(_venv_py) and os.path.abspath(sys.executable) != os.path.abspath(_venv_py):
    os.execv(_venv_py, [_venv_py] + sys.argv)

import json
import socket


def compact(song):
    artists = ", ".join(a.get("name", "") for a in song.get("artists", []) if a.get("name"))
    thumbnails = song.get("thumbnails") or song.get("thumbnail") or []
    return {
        "videoId": song.get("videoId", ""),
        "title": song.get("title", "Unknown title"),
        "artist": artists,
        "duration": song.get("duration") or song.get("length", ""),
        "thumbnail": thumbnails[-1].get("url", "") if thumbnails else "",
    }


def mpv(command, reply=False):
    run_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    path = os.path.join(run_dir, "omusic-mpv.sock")
    payload = json.dumps({"command": command}).encode() + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        client.connect(path)
        client.sendall(payload)
        if reply:
            response = b""
            while b"\n" not in response:
                response += client.recv(4096)
            return json.loads(response.split(b"\n", 1)[0])


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in {"search", "radio", "pause", "status", "seek", "volume", "mute"}:
        raise SystemExit("usage: backend.py search QUERY | radio VIDEO_ID | pause BOOL | status | seek SECONDS | volume 0-100 | mute BOOL")

    if sys.argv[1] == "pause":
        mpv(["set_property", "pause", sys.argv[2] == "true"])
        return
    if sys.argv[1] == "seek":
        mpv(["set_property", "time-pos", max(0, float(sys.argv[2]))])
        return
    if sys.argv[1] == "volume":
        mpv(["set_property", "volume", max(0, min(100, float(sys.argv[2])))])
        return
    if sys.argv[1] == "mute":
        mpv(["set_property", "mute", sys.argv[2] == "true"])
        return
    if sys.argv[1] == "status":
        position = mpv(["get_property", "time-pos"], True).get("data") or 0
        duration = mpv(["get_property", "duration"], True).get("data") or 0
        volume = mpv(["get_property", "volume"], True).get("data")
        muted = mpv(["get_property", "mute"], True).get("data")
        print(json.dumps({
            "position": position,
            "duration": duration,
            "volume": volume if volume is not None else 100,
            "muted": bool(muted) if muted is not None else False,
        }))
        return

    if len(sys.argv) < 3:
        raise SystemExit("missing query or video ID")

    from ytmusicapi import YTMusic
    music = YTMusic()
    if sys.argv[1] == "search":
        limit = 10
        query_parts = list(sys.argv[2:])
        if len(query_parts) >= 2 and query_parts[-2] == "--limit" and query_parts[-1].isdigit():
            limit = int(query_parts[-1])
            query_parts = query_parts[:-2]
        songs = music.search(" ".join(query_parts), filter="songs", limit=limit)[:limit]
    else:
        songs = music.get_watch_playlist(videoId=sys.argv[2], radio=True, limit=20).get("tracks", [])[:20]

    print(json.dumps([compact(song) for song in songs if song.get("videoId")], ensure_ascii=False))


if __name__ == "__main__":
    main()
