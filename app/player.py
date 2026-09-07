"""
player.py — Central state manager for omusic.

All application state lives here.  UI panels connect to the signals emitted
by this object.  The mpv process, status-polling timer, and backend subprocess
calls are all managed here.
"""
from __future__ import annotations

import json
import math
import os
import random
import time
from typing import Optional

from PyQt6.QtCore import (
    QObject, QProcess, QTimer, Qt, pyqtSignal as Signal, QCoreApplication
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _backend_path() -> str:
    """Return the absolute path to backend.py, checking installed and local repo paths."""
    # 1. Check user install directory
    installed = os.path.expanduser("~/.local/share/omusic/backend.py")
    if os.path.isfile(installed):
        return installed

    # 2. Check repo sibling directory
    repo_backend = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "backend", "backend.py"
    )
    if os.path.isfile(repo_backend):
        return repo_backend

    # Fallback to installed path
    return installed


def _socket_path() -> str:
    run = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return os.path.join(run, "omusic-mpv.sock")


def _format_time(seconds: float) -> str:
    v = max(0, int(seconds))
    return f"{v // 60}:{v % 60:02d}"


def _duration_secs(s: str) -> int:
    parts = (s or "").split(":")
    total = 0
    for p in parts:
        total = total * 60 + (int(p) if p.isdigit() else 0)
    return total


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

class Player(QObject):
    """
    Central state object.  All state mutations emit signals so UI can react.
    """

    # ---- signals -----------------------------------------------------------
    queue_changed         = Signal()
    current_index_changed = Signal(int)
    is_playing_changed    = Signal(bool)
    position_changed      = Signal(float, float)   # pos, duration
    volume_changed        = Signal(float, bool)    # level, muted
    shuffle_changed       = Signal(bool)
    repeat_changed        = Signal(bool)
    error_changed         = Signal(str)
    search_results_ready  = Signal(list)           # list of song dicts
    search_busy_changed   = Signal(bool)
    radio_busy_changed    = Signal(bool)
    load_more_busy_changed= Signal(bool)
    has_more_search_changed= Signal(bool)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

        # ---- playback state ----
        self.queue:           list[dict] = []
        self.current_index:   int   = -1
        self.pending_index:   int   = -1
        self._paused:         bool  = True
        self._stopping:       bool  = False
        self.play_start_stamp:float = 0.0
        self.consec_failures: int   = 0
        self.play_error:      str   = ""

        # ---- UI state ----
        self.shuffle_enabled: bool  = False
        self.repeat_enabled:  bool  = False
        self.volume_level:    float = 100.0
        self.muted:           bool  = False
        self.playback_position:float= 0.0
        self.playback_duration:float= 0.0

        # ---- search state ----
        self.search_limit:    int   = 10
        self.has_more_search: bool  = True
        self._search_busy:    bool  = False
        self._radio_busy:     bool  = False
        self._load_more_busy: bool  = False
        self._search_results: list[dict] = []

        # ---- backend (mpv) process ----
        self._mpv = QProcess(self)
        self._mpv.finished.connect(self._on_mpv_finished)

        # ---- status poll timer ----
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1000)
        self._status_timer.timeout.connect(self._poll_status)
        self._status_proc: Optional[QProcess] = None

        # ---- search process ----
        self._search_proc:    Optional[QProcess] = None
        self._load_more_proc: Optional[QProcess] = None
        self._radio_proc:     Optional[QProcess] = None
        self._radio_for_id:   str = ""

        # ---- control procs ----
        self._control_proc:   Optional[QProcess] = None
        self._seek_proc:      Optional[QProcess] = None
        self._vol_proc:       Optional[QProcess] = None

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property
    def current_song(self) -> dict:
        if 0 <= self.current_index < len(self.queue):
            return self.queue[self.current_index]
        return {}

    @property
    def is_playing(self) -> bool:
        return (self._mpv.state() == QProcess.ProcessState.Running
                and not self._paused)

    @property
    def search_busy(self) -> bool:
        return self._search_busy

    @property
    def radio_busy(self) -> bool:
        return self._radio_busy

    @property
    def load_more_busy(self) -> bool:
        return self._load_more_busy

    # -----------------------------------------------------------------------
    # Queue manipulation
    # -----------------------------------------------------------------------

    def add_to_queue(self, song: dict) -> None:
        self.queue.append(song)
        self.queue_changed.emit()

    def insert_after_current(self, song: dict) -> None:
        idx = self.current_index + 1 if self.current_index >= 0 else len(self.queue)
        self.queue.insert(max(0, idx), song)
        self.queue_changed.emit()

    def remove_from_queue(self, index: int) -> None:
        if index < 0 or index >= len(self.queue):
            return
        was_current = (index == self.current_index)
        self.queue.pop(index)

        if not self.queue:
            self.stop_playback()
            self.current_index = -1
            self.playback_position = 0.0
            self.queue_changed.emit()
            self.current_index_changed.emit(self.current_index)
            return

        if self.current_index > index:
            self.current_index -= 1
        if self.pending_index > index:
            self.pending_index -= 1
        elif self.pending_index == index:
            self.pending_index = -1

        self.queue_changed.emit()

        if was_current:
            if index < len(self.queue):
                self.play_index(index)
            else:
                self.stop_playback()
                self.current_index = -1
                self.playback_position = 0.0
                self.current_index_changed.emit(self.current_index)

    def move_queue_item(self, from_idx: int, to_idx: int) -> None:
        n = len(self.queue)
        if not (0 <= from_idx < n and 0 <= to_idx < n and from_idx != to_idx):
            return

        # Adjust currentIndex
        ci = self.current_index
        if ci == from_idx:
            ci = to_idx
        elif from_idx < to_idx and from_idx < ci <= to_idx:
            ci -= 1
        elif from_idx > to_idx and to_idx <= ci < from_idx:
            ci += 1

        pi = self.pending_index
        if pi == from_idx:
            pi = to_idx
        elif from_idx < to_idx and from_idx < pi <= to_idx:
            pi -= 1
        elif from_idx > to_idx and to_idx <= pi < from_idx:
            pi += 1

        item = self.queue.pop(from_idx)
        self.queue.insert(to_idx, item)
        self.current_index = ci
        self.pending_index = pi
        self.queue_changed.emit()
        self.current_index_changed.emit(self.current_index)

    def clear_queue(self) -> None:
        self.stop_playback()
        self.queue.clear()
        self.current_index = -1
        self.pending_index = -1
        self.playback_position = 0.0
        self.play_error = ""
        self.queue_changed.emit()
        self.current_index_changed.emit(self.current_index)

    # -----------------------------------------------------------------------
    # Playback control
    # -----------------------------------------------------------------------

    def play_index(self, index: int) -> None:
        if index < 0 or index >= len(self.queue):
            return
        self.consec_failures = 0
        self.pending_index = index
        if self._mpv.state() == QProcess.ProcessState.Running:
            self._paused = False
            self._mpv.kill()
        else:
            self._start_pending()

    def _start_pending(self) -> None:
        if self.pending_index < 0 or self.pending_index >= len(self.queue):
            return
        self.current_index = self.pending_index
        self.pending_index = -1
        self._paused = False
        self.play_error = ""
        self.play_start_stamp = time.time()
        song = self.queue[self.current_index]

        args = [
            "--no-video", "--force-window=no", "--really-quiet",
            f"--input-ipc-server={_socket_path()}",
            "--ytdl-raw-options=extractor-args=youtube:player_client=android",
            "--ytdl-format=bestaudio/best",
            f"--volume={round(self.volume_level)}",
            f"--mute={'yes' if self.muted else 'no'}",
            f"https://music.youtube.com/watch?v={song['videoId']}"
        ]
        self._mpv.start("mpv", args)
        self._status_timer.start()
        self.current_index_changed.emit(self.current_index)
        self.is_playing_changed.emit(True)
        self.error_changed.emit("")

    def play_pause(self) -> None:
        if self.current_index < 0:
            if self.queue:
                self.play_index(0)
            return
        if self._mpv.state() != QProcess.ProcessState.Running:
            self.play_index(self.current_index)
            return
        target_pause = not self._paused
        proc = QProcess(self)
        proc.start(_backend_path(), ["pause", "true" if target_pause else "false"])
        proc.finished.connect(lambda code, _: self._on_pause_finished(code, target_pause, proc))

    def _on_pause_finished(self, code: int, requested: bool, proc: QProcess) -> None:
        proc.deleteLater()
        if code == 0:
            self._paused = requested
            self.is_playing_changed.emit(self.is_playing)

    def stop_playback(self) -> None:
        self.pending_index = -1
        self.consec_failures = 0
        if self._mpv.state() == QProcess.ProcessState.Running:
            self._stopping = True
            self._mpv.kill()

    def previous(self) -> None:
        if self.current_index > 0:
            self.play_index(self.current_index - 1)

    def _next_index(self) -> int:
        if len(self.queue) <= 1:
            return -1
        if self.shuffle_enabled:
            idx = self.current_index
            attempts = 0
            while idx == self.current_index and attempts < 20:
                idx = random.randrange(len(self.queue))
                attempts += 1
            return idx
        nxt = self.current_index + 1
        return nxt if nxt < len(self.queue) else -1

    def next(self) -> None:
        idx = self._next_index()
        if idx >= 0:
            self.play_index(idx)

    def seek(self, seconds: float) -> None:
        if self._mpv.state() != QProcess.ProcessState.Running:
            return
        proc = QProcess(self)
        proc.start(_backend_path(), ["seek", str(max(0.0, seconds))])
        proc.finished.connect(proc.deleteLater)

    def set_volume(self, value: float) -> None:
        v = max(0.0, min(100.0, round(value)))
        self.volume_level = v
        self.volume_changed.emit(v, self.muted)
        if self._mpv.state() != QProcess.ProcessState.Running:
            return
        proc = QProcess(self)
        proc.start(_backend_path(), ["volume", str(v)])
        proc.finished.connect(proc.deleteLater)

    def set_muted(self, m: bool) -> None:
        self.muted = m
        self.volume_changed.emit(self.volume_level, m)
        if self._mpv.state() != QProcess.ProcessState.Running:
            return
        proc = QProcess(self)
        proc.start(_backend_path(), ["mute", "true" if m else "false"])
        proc.finished.connect(proc.deleteLater)

    def toggle_mute(self) -> None:
        self.set_muted(not self.muted)

    def toggle_shuffle(self) -> None:
        self.shuffle_enabled = not self.shuffle_enabled
        self.shuffle_changed.emit(self.shuffle_enabled)

    def toggle_repeat(self) -> None:
        self.repeat_enabled = not self.repeat_enabled
        self.repeat_changed.emit(self.repeat_enabled)

    # -----------------------------------------------------------------------
    # Status polling
    # -----------------------------------------------------------------------

    def _poll_status(self) -> None:
        if self._status_proc and self._status_proc.state() == QProcess.ProcessState.Running:
            return
        proc = QProcess(self)
        proc.setReadChannel(QProcess.ProcessChannel.StandardOutput)
        buf = bytearray()

        def _read():
            buf.extend(bytes(proc.readAllStandardOutput()))

        def _done(code, _):
            proc.deleteLater()
            if code != 0 or not buf:
                return
            try:
                s = json.loads(bytes(buf).decode())
                self.playback_position = float(s.get("position") or 0)
                self.playback_duration = float(s.get("duration") or 0)
                vol = s.get("volume")
                if vol is not None:
                    self.volume_level = max(0.0, min(100.0, float(vol)))
                muted = s.get("muted")
                if muted is not None:
                    self.muted = bool(muted)
                self.position_changed.emit(self.playback_position, self.playback_duration)
                self.volume_changed.emit(self.volume_level, self.muted)
            except Exception:
                pass

        proc.readyReadStandardOutput.connect(_read)
        proc.finished.connect(_done)
        proc.start(_backend_path(), ["status"])
        self._status_proc = proc

    # -----------------------------------------------------------------------
    # mpv process exit handler
    # -----------------------------------------------------------------------

    def _on_mpv_finished(self, exit_code: int, exit_status) -> None:
        self._status_timer.stop()
        self.is_playing_changed.emit(False)

        if self._stopping:
            self._stopping = False
            self._paused = True
            self.playback_position = 0.0
            self.consec_failures = 0
            self.position_changed.emit(0.0, self.playback_duration)
            return

        if self.pending_index >= 0:
            self.consec_failures = 0
            QTimer.singleShot(50, self._start_pending)
            return

        lived = time.time() - self.play_start_stamp
        failed = self.current_index >= 0 and lived < 5.0
        if failed:
            self.consec_failures += 1
        else:
            self.consec_failures = 0

        if failed and self.consec_failures >= 3:
            self._paused = True
            self.playback_position = 0.0
            self.play_error = "Couldn't play these songs (YouTube or network issue). Stopped."
            self.error_changed.emit(self.play_error)
            return

        if not failed and exit_code == 0 and self.repeat_enabled and self.current_index >= 0:
            self.pending_index = self.current_index
            QTimer.singleShot(50, self._start_pending)
            return

        idx = self._next_index()
        if idx >= 0:
            self.pending_index = idx
            QTimer.singleShot(50, self._start_pending)
        else:
            self.playback_position = 0.0
            self.position_changed.emit(0.0, self.playback_duration)

    # -----------------------------------------------------------------------
    # Search / radio
    # -----------------------------------------------------------------------

    def search(self, query: str, limit: int = 10) -> None:
        if not query or self._search_busy:
            return
        self._search_busy = True
        self.search_limit = limit
        self.has_more_search = True
        self._search_results = []
        self.search_busy_changed.emit(True)

        proc = QProcess(self)
        buf = bytearray()
        proc.readyReadStandardOutput.connect(lambda: buf.extend(bytes(proc.readAllStandardOutput())))

        def _done(code, _):
            proc.deleteLater()
            self._search_busy = False
            self.search_busy_changed.emit(False)
            if code == 0 and buf:
                try:
                    songs = json.loads(bytes(buf).decode())
                    self._search_results = songs
                    self.search_results_ready.emit(songs)
                except Exception:
                    pass

        proc.finished.connect(_done)
        proc.start(_backend_path(), ["search", query, "--limit", str(limit)])

    def load_more_search(self, query: str) -> None:
        if not query or self._load_more_busy or not self.has_more_search:
            return
        self._load_more_busy = True
        self.search_limit += 10
        self.load_more_busy_changed.emit(True)

        proc = QProcess(self)
        buf = bytearray()
        proc.readyReadStandardOutput.connect(lambda: buf.extend(bytes(proc.readAllStandardOutput())))

        existing_ids = {s["videoId"] for s in self._search_results}

        def _done(code, _):
            proc.deleteLater()
            self._load_more_busy = False
            self.load_more_busy_changed.emit(False)
            if code == 0 and buf:
                try:
                    songs = json.loads(bytes(buf).decode())
                    new_songs = [s for s in songs if s["videoId"] not in existing_ids]
                    added = len(new_songs)
                    if added > 0:
                        self._search_results.extend(new_songs)
                    if added == 0 or len(songs) < self.search_limit:
                        self.has_more_search = False
                        self.has_more_search_changed.emit(False)
                    self.search_results_ready.emit(self._search_results)
                except Exception:
                    pass

        proc.finished.connect(_done)
        proc.start(_backend_path(), ["search", query, "--limit", str(self.search_limit)])

    def start_radio(self, video_id: str) -> None:
        if not video_id or self._radio_busy:
            return
        self._radio_busy = True
        self._radio_for_id = video_id
        self.radio_busy_changed.emit(True)

        proc = QProcess(self)
        buf = bytearray()
        proc.readyReadStandardOutput.connect(lambda: buf.extend(bytes(proc.readAllStandardOutput())))

        def _done(code, _):
            proc.deleteLater()
            self._radio_busy = False
            self.radio_busy_changed.emit(False)
            if code == 0 and buf:
                try:
                    songs = json.loads(bytes(buf).decode())
                    if self.current_song.get("videoId") != self._radio_for_id:
                        return
                    for s in songs:
                        if s["videoId"] != self._radio_for_id:
                            self.queue.append(s)
                    self.queue_changed.emit()
                except Exception:
                    pass

        proc.finished.connect(_done)
        proc.start(_backend_path(), ["radio", video_id])

    def select_search_result(self, song: dict) -> None:
        """Play immediately and start radio for it."""
        self.queue.clear()
        self.queue.append(song)
        self.queue_changed.emit()
        self.play_index(0)
        self.start_radio(song["videoId"])

    def queue_search_result(self, song: dict) -> None:
        self.add_to_queue(song)

    def play_next_search_result(self, song: dict) -> None:
        if self.current_index >= 0:
            self.queue.insert(self.current_index + 1, song)
            self.queue_changed.emit()
        else:
            self.add_to_queue(song)
            self.play_index(len(self.queue) - 1)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def format_time(seconds: float) -> str:
        return _format_time(seconds)

    def queue_total_secs(self) -> int:
        return sum(_duration_secs(s.get("duration", "")) for s in self.queue)

    def queue_header(self) -> str:
        n = len(self.queue)
        s = f"Queue · {n} {'song' if n == 1 else 'songs'}"
        if n > 0:
            total = self.queue_total_secs()
            h = total // 3600
            m = (total % 3600) // 60
            if h:
                s += f" · {h}h {m}m"
            elif m:
                s += f" · {m}m"
            else:
                s += f" · {total}s"
        return s
