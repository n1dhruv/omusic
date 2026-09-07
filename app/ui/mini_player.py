"""
mini_player.py — Collapsed 76px mini-player mode.

Shows: thumbnail + title + artist + time position + prev/play/next + expand button.
Progress shown as a thin 2px line at the bottom of the widget.
"""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, pyqtSignal as Signal
from PyQt6.QtGui import QPainter, QColor, QCursor, QFont, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSizePolicy
)

from app import style as S
from app.ui.widgets.thumbnail import ThumbnailWidget

if TYPE_CHECKING:
    from app.player import Player


class MiniPlayer(QWidget):
    """
    Compact 76px mini-player.
    Emits expand_clicked when user wants to return to full mode.
    """

    expand_clicked = Signal()

    def __init__(self, player: 'Player', parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._player = player
        self._position = 0.0
        self._duration = 1.0
        self.setFixedHeight(S.sp(76))
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(S.sp(12), 0, S.sp(14), 0)
        outer.setSpacing(S.sp(10))

        # ---- Thumbnail (44x44) ----
        self._thumb = ThumbnailWidget(size=S.sp(44), radius=S.sp(8))
        self._thumb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._thumb.mousePressEvent = lambda e: self.expand_clicked.emit()
        outer.addWidget(self._thumb)

        # ---- Title + artist + time ----
        info = QWidget()
        info.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(S.sp(2))

        self._title = QLabel("YouTube Music")
        self._title.setStyleSheet(
            f"color: {S.hex_(S.TEXT_PRI)}; font-size: {S.sp(12)}px; font-weight: bold;"
        )
        self._title.setMaximumWidth(S.sp(240))

        self._sub = QLabel("Idle")
        self._sub.setStyleSheet(
            f"color: {S.hex_(S.TEXT_SEC)}; font-family: monospace; font-size: {S.sp(10)}px;"
        )
        self._sub.setMaximumWidth(S.sp(240))

        info_layout.addWidget(self._title)
        info_layout.addWidget(self._sub)
        outer.addWidget(info)

        # ---- Controls: prev / play / next ----
        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(0, 0, 0, 0)
        ctrl.setSpacing(S.sp(8))

        self._prev_btn = _MiniBtn("\U000f04ae", 20)  # skip-prev
        self._play_btn = _MiniPlayBtn()
        self._next_btn = _MiniBtn("\U000f04ad", 20)  # skip-next

        self._prev_btn.clicked.connect(self._player.previous)
        self._play_btn.clicked.connect(self._player.play_pause)
        self._next_btn.clicked.connect(self._player.next)

        ctrl.addWidget(self._prev_btn)
        ctrl.addWidget(self._play_btn)
        ctrl.addWidget(self._next_btn)

        ctrl_w = QWidget()
        ctrl_w.setLayout(ctrl)
        outer.addWidget(ctrl_w)

        # ---- Expand button ----
        self._expand_btn = QPushButton("\U000f009e")  # expand/arrow up icon
        self._expand_btn.setFixedSize(S.sp(26), S.sp(26))
        self._expand_btn.setFlat(True)
        self._expand_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._expand_btn.setToolTip("Expand player")
        self._expand_btn.setStyleSheet(
            f"QPushButton {{ color: {S.hex_(S.TEXT_MUT)}; font-size: {S.sp(16)}px;"
            f"background: transparent; border: 1px solid transparent; border-radius: 6px; }}"
            f"QPushButton:hover {{ color: {S.hex_(S.ACCENT_BRT)};"
            f"background: {S.hex_(S.SURF_HOVER)}; border-color: {S.rgba_(S.BORDER)}; }}"
        )
        self._expand_btn.clicked.connect(self.expand_clicked.emit)
        outer.addWidget(self._expand_btn)

    def _connect_signals(self) -> None:
        p = self._player
        p.current_index_changed.connect(self._on_song_changed)
        p.is_playing_changed.connect(self._on_playing_changed)
        p.position_changed.connect(self._on_position)

    def _on_song_changed(self, _=None) -> None:
        song = self._player.current_song
        self._thumb.set_url(song.get("thumbnail", ""))
        self._title.setText(song.get("title", "YouTube Music"))
        self._update_sub()

    def _on_playing_changed(self, playing: bool) -> None:
        self._play_btn.set_playing(playing)
        self._update_prev_next()

    def _on_position(self, pos: float, dur: float) -> None:
        self._position = pos
        self._duration = dur
        self._update_sub()
        self.update()  # repaint progress line

    def _update_sub(self) -> None:
        song = self._player.current_song
        artist = song.get("artist", "Idle")
        pos_str = self._player.format_time(self._position)
        dur_str = self._player.format_time(self._duration)
        self._sub.setText(f"{artist} · {pos_str} / {dur_str}")

    def _update_prev_next(self) -> None:
        has_prev = self._player.current_index > 0
        has_next = (self._player.current_index >= 0
                    and self._player.current_index + 1 < len(self._player.queue))
        self._prev_btn.setEnabled(has_prev)
        self._next_btn.setEnabled(has_next)

    def paintEvent(self, event) -> None:
        # Draw progress line at bottom
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        # Track
        p.fillRect(0, h - 2, w, 2, QColor(255, 255, 255, 20))

        # Fill
        dur = max(1.0, self._duration)
        ratio = max(0.0, min(1.0, self._position / dur))
        fill_w = int(w * ratio)
        if fill_w > 0:
            p.fillRect(0, h - 2, fill_w, 2, S.ACCENT)
        p.end()


class _MiniBtn(QPushButton):
    def __init__(self, icon: str, size: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(icon, parent)
        self.setFixedSize(S.sp(size + 8), S.sp(size + 8))
        self.setFlat(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet(
            f"QPushButton {{ color: {S.hex_(S.TEXT_SEC)}; font-size: {S.sp(size)}px;"
            f"background: transparent; border: none; }}"
            f"QPushButton:hover {{ color: {S.hex_(S.TEXT_PRI)}; }}"
            f"QPushButton:disabled {{ color: {S.hex_(S.TEXT_MUT)}; }}"
        )


class _MiniPlayBtn(QWidget):
    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._playing = False
        self._hovered = False
        sz = S.sp(34)
        self.setFixedSize(sz, sz)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_playing(self, p: bool) -> None:
        self._playing = p
        self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        sz = self.width()
        color = S.ACCENT_BRT if self._hovered else S.ACCENT
        circ = QPainterPath()
        circ.addEllipse(0, 0, sz, sz)
        p.fillPath(circ, color)
        p.setPen(S.BG)
        f = QFont()
        f.setPixelSize(S.sp(15))
        p.setFont(f)
        icon = "\U000f03e4" if self._playing else "\U000f040a"
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, icon)
        p.end()

    def enterEvent(self, e):
        self._hovered = True
        self.update()

    def leaveEvent(self, e):
        self._hovered = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
