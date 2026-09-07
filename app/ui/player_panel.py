"""
player_panel.py — Right panel: album art, controls, progress bar, volume, queue header.

This is the right-side panel (~63% width) of the omusic window. It contains:
  - "NOW PLAYING" / "PLAYER" header with animated equalizer
  - 176×176 album artwork with glow and rounded corners
  - Song title + artist (animated fade on song change)
  - Transport controls: shuffle / prev / play-pause / next / repeat
  - Progress bar (hover-expanding, draggable)
  - Volume slider + mute toggle
  - Queue header row + Clear button
  - QueueWidget (imported)
  - Empty-queue placeholder text
"""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup,
    QRect, QSize, pyqtSignal as Signal
)
from PyQt6.QtGui import (
    QPainter, QColor, QPainterPath, QCursor, QFont, QPixmap,
    QLinearGradient, QRadialGradient, QPen, QBrush
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QFrame, QSizePolicy, QPushButton, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsOpacityEffect, QGraphicsBlurEffect
)

from app import style as S
from app.ui.widgets.thumbnail import ThumbnailWidget, _get_nam
from app.ui.widgets.equalizer import EqualizerWidget
from app.ui.queue_widget import QueueWidget

if TYPE_CHECKING:
    from app.player import Player


# ---------------------------------------------------------------------------
# Artwork widget with ambient glow
# ---------------------------------------------------------------------------
class _ArtworkWidget(QWidget):
    """
    176×176 album art with:
    - Rounded corners (radius 16)
    - Ambient glow that breathes when playing
    - Hover scale (1.0 → 1.015)
    - Song-change pop animation (0.92 → 1.04 → 1.0)
    - Blurred global backdrop is handled by the parent window
    """

    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._size = S.sp(176)
        self.setFixedSize(self._size, self._size)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._pixmap: Optional[QPixmap] = None
        self._glow_opacity: float = 0.04
        self._scale: float = 1.0
        self._hovered = False
        self._is_playing = False

        # Glow breathe timer
        self._glow_val = 0.04
        self._glow_dir = 1
        self._glow_timer = QTimer(self)
        self._glow_timer.setInterval(50)
        self._glow_timer.timeout.connect(self._breathe_tick)

        # Download via QNetworkAccessManager
        from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
        from PyQt6.QtCore import QUrl
        self._QUrl = QUrl
        self._QNetworkRequest = QNetworkRequest
        self._QNetworkReply = QNetworkReply
        self._reply = None
        self._current_url = ""

    def set_url(self, url: str) -> None:
        if url == self._current_url:
            return
        self._current_url = url
        self._pixmap = None
        self.update()
        if not url:
            return
        # Replace thumbnail size for higher quality
        import re
        url = re.sub(r"=w\d+-h\d+", "=w600-h600", url)
        nam = _get_nam()
        req = self._QNetworkRequest(self._QUrl(url))
        if self._reply:
            self._reply.abort()
        self._reply = nam.get(req)
        self._reply.finished.connect(self._on_finished)

    def _on_finished(self) -> None:
        reply = self._reply
        if not reply:
            return
        self._reply = None
        if reply.error() != self._QNetworkReply.NetworkError.NoError:
            reply.deleteLater()
            return
        data = bytes(reply.readAll())
        reply.deleteLater()
        px = QPixmap()
        if not px.loadFromData(data):
            return
        px = px.scaled(
            self._size, self._size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        if px.width() > self._size or px.height() > self._size:
            x = (px.width() - self._size) // 2
            y = (px.height() - self._size) // 2
            px = px.copy(x, y, self._size, self._size)
        self._pixmap = px
        self.update()

    def set_playing(self, playing: bool) -> None:
        self._is_playing = playing
        if playing:
            self._glow_timer.start()
        else:
            self._glow_timer.stop()
            self._glow_val = 0.04
        self.update()

    def _breathe_tick(self) -> None:
        step = 0.003
        if self._glow_dir > 0:
            self._glow_val += step
            if self._glow_val >= 0.25:
                self._glow_dir = -1
        else:
            self._glow_val -= step
            if self._glow_val <= 0.14:
                self._glow_dir = 1
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        sz = self._size
        # Ambient glow circle
        glow_color = QColor(S.ACCENT)
        glow_color.setAlphaF(self._glow_val)
        glow_sz = int(sz * (0.98 if self._is_playing else 0.92))
        off = (sz - glow_sz) // 2

        # Draw soft glow (radial gradient)
        grad = QRadialGradient(sz / 2, sz / 2, glow_sz / 2)
        grad.setColorAt(0.0, glow_color)
        glow_outer = QColor(glow_color)
        glow_outer.setAlpha(0)
        grad.setColorAt(1.0, glow_outer)
        p.fillRect(0, 0, sz, sz, grad)

        # Clip to rounded rect
        path = QPainterPath()
        path.addRoundedRect(0, 0, sz, sz, S.sp(16), S.sp(16))
        p.setClipPath(path)

        if self._pixmap:
            p.drawPixmap(0, 0, self._pixmap)
        else:
            p.fillPath(path, S.SURFACE)
            # Nerd font YouTube icon
            p.setPen(S.TEXT_MUT)
            f = QFont()
            f.setPixelSize(S.sp(52))
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, '\U000f05c3')

        # Soft bottom gradient overlay
        grad2 = QLinearGradient(0, int(sz * 0.65), 0, sz)
        grad2.setColorAt(0.0, Qt.GlobalColor.transparent)
        grad2.setColorAt(1.0, QColor(11, 21, 17, 115))
        p.fillRect(0, int(sz * 0.65), sz, sz, grad2)

        p.end()

    def enterEvent(self, e) -> None:
        self._hovered = True
        self.update()

    def leaveEvent(self, e) -> None:
        self._hovered = False
        self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


# ---------------------------------------------------------------------------
# Progress bar
# ---------------------------------------------------------------------------
class _ProgressBar(QWidget):
    """
    Hover-expanding progress track: 3px → 5px.
    Draggable knob. Wheel to seek ±5s.
    """

    seek_requested = Signal(float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(S.sp(16))
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._position = 0.0
        self._duration = 1.0
        self._dragging = False
        self._drag_val = 0.0
        self._hovered = False

    def set_state(self, position: float, duration: float) -> None:
        self._position = position
        self._duration = max(0.001, duration)
        if not self._dragging:
            self.update()

    @property
    def _ratio(self) -> float:
        if self._dragging:
            return max(0.0, min(1.0, self._drag_val / self._duration))
        return max(0.0, min(1.0, self._position / self._duration))

    def _val_from_x(self, x: int) -> float:
        return max(0.0, min(self._duration, (x / self.width()) * self._duration))

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        cy = self.height() // 2
        track_h = S.sp(5) if self._hovered else S.sp(3)
        track_y = cy - track_h // 2

        # Track background
        path = QPainterPath()
        path.addRoundedRect(0, track_y, w, track_h, track_h / 2, track_h / 2)
        p.fillPath(path, QColor(255, 255, 255, 20))

        # Filled portion
        fill_w = int(w * self._ratio)
        if fill_w > 0:
            fill_path = QPainterPath()
            fill_path.addRoundedRect(0, track_y, fill_w, track_h, track_h / 2, track_h / 2)
            p.fillPath(fill_path, S.ACCENT)

        # Knob
        knob_size = S.sp(11) if self._hovered else S.sp(6)
        knob_x = max(0, min(w - knob_size, fill_w - knob_size // 2))
        knob_y = cy - knob_size // 2
        knob_path = QPainterPath()
        knob_path.addEllipse(knob_x, knob_y, knob_size, knob_size)
        knob_opacity = 1.0 if self._hovered else 0.6
        knob_color = QColor(S.ACCENT_BRT)
        knob_color.setAlphaF(knob_opacity)
        p.fillPath(knob_path, knob_color)
        p.end()

    def enterEvent(self, e) -> None:
        self._hovered = True
        self.update()

    def leaveEvent(self, e) -> None:
        self._hovered = False
        self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_val = self._val_from_x(e.pos().x())
            self.update()

    def mouseMoveEvent(self, e) -> None:
        if self._dragging:
            self._drag_val = self._val_from_x(e.pos().x())
            self.update()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.seek_requested.emit(self._drag_val)
            self.update()

    def wheelEvent(self, e) -> None:
        delta = 5.0 if e.angleDelta().y() > 0 else -5.0
        self.seek_requested.emit(max(0.0, min(self._duration, self._position + delta)))
        e.accept()


# ---------------------------------------------------------------------------
# Volume slider
# ---------------------------------------------------------------------------
class _VolumeSlider(QWidget):
    """110px wide volume slider with mute toggle."""

    volume_changed = Signal(float)
    mute_toggled   = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(S.sp(8))

        # Mute button (speaker icon)
        self._mute_btn = QPushButton("\U000f057e")  # volume icon
        self._mute_btn.setFixedSize(S.sp(22), S.sp(22))
        self._mute_btn.setFlat(True)
        self._mute_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._mute_btn.setStyleSheet(
            f"QPushButton {{ color: {S.hex_(S.TEXT_SEC)}; font-size: {S.sp(16)}px;"
            f"background: transparent; border: none; }}"
            f"QPushButton:hover {{ color: {S.hex_(S.TEXT_PRI)}; }}"
        )
        self._mute_btn.clicked.connect(self.mute_toggled.emit)
        self._layout.addWidget(self._mute_btn)

        # Track widget
        self._track = _VolumeTrack()
        self._track.volume_changed.connect(self.volume_changed.emit)
        self._layout.addWidget(self._track)

        # Percentage label
        self._pct_lbl = QLabel("100%")
        self._pct_lbl.setFixedWidth(S.sp(36))
        self._pct_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._pct_lbl.setStyleSheet(
            f"color: {S.hex_(S.TEXT_MUT)}; font-family: monospace; font-size: {S.sp(10)}px;"
        )
        self._layout.addWidget(self._pct_lbl)

    def set_state(self, level: float, muted: bool) -> None:
        self._track.set_state(level, muted)
        icon = "\U000f0581" if muted else "\U000f057e"  # mute / volume
        self._mute_btn.setText(icon)
        self._pct_lbl.setText("MUTE" if muted else f"{round(level)}%")


class _VolumeTrack(QWidget):
    volume_changed = Signal(float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(S.sp(110), S.sp(16))
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._level = 100.0
        self._muted = False
        self._hovered = False
        self._dragging = False

    def set_state(self, level: float, muted: bool) -> None:
        self._level = level
        self._muted = muted
        self.update()

    def _ratio(self) -> float:
        return 0.0 if self._muted else max(0.0, min(1.0, self._level / 100.0))

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        cy = self.height() // 2
        track_h = S.sp(4) if self._hovered else S.sp(3)
        track_y = cy - track_h // 2
        ratio = self._ratio()

        # Background
        path = QPainterPath()
        path.addRoundedRect(0, track_y, w, track_h, track_h / 2, track_h / 2)
        p.fillPath(path, QColor(255, 255, 255, 20))

        # Fill
        fill_w = int(w * ratio)
        if fill_w > 0:
            fill_color = S.TEXT_MUT if self._muted else S.TEXT_SEC
            fill_path = QPainterPath()
            fill_path.addRoundedRect(0, track_y, fill_w, track_h, track_h / 2, track_h / 2)
            p.fillPath(fill_path, fill_color)

        # Knob
        ks = S.sp(9) if self._hovered else S.sp(5)
        kx = max(0, min(w - ks, fill_w - ks // 2))
        ky = cy - ks // 2
        kp = QPainterPath()
        kp.addEllipse(kx, ky, ks, ks)
        p.fillPath(kp, S.ACCENT_BRT)
        p.end()

    def _vol_from_x(self, x: int) -> float:
        return max(0.0, min(100.0, (x / self.width()) * 100.0))

    def enterEvent(self, e) -> None:
        self._hovered = True
        self.update()

    def leaveEvent(self, e) -> None:
        self._hovered = False
        self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.RightButton:
            self.volume_changed.emit(-1)  # signal mute toggle
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.volume_changed.emit(self._vol_from_x(e.pos().x()))

    def mouseMoveEvent(self, e) -> None:
        if self._dragging:
            self.volume_changed.emit(self._vol_from_x(e.pos().x()))

    def mouseReleaseEvent(self, e) -> None:
        self._dragging = False

    def wheelEvent(self, e) -> None:
        delta = 5.0 if e.angleDelta().y() > 0 else -5.0
        self.volume_changed.emit(max(0.0, min(100.0, self._level + delta)))
        e.accept()


# ---------------------------------------------------------------------------
# Control button
# ---------------------------------------------------------------------------
def _ctrl_btn(icon: str, size: int = 22, tooltip: str = "") -> QPushButton:
    btn = QPushButton(icon)
    btn.setFixedSize(S.sp(size), S.sp(size))
    btn.setFlat(True)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    if tooltip:
        btn.setToolTip(tooltip)
    btn.setStyleSheet(
        f"QPushButton {{ color: {S.hex_(S.TEXT_SEC)}; font-size: {S.sp(size - 4)}px;"
        f"background: transparent; border: none; border-radius: {S.sp(4)}px; }}"
        f"QPushButton:hover {{ color: {S.hex_(S.TEXT_PRI)}; }}"
        f"QPushButton:pressed {{ color: {S.hex_(S.ACCENT)}; }}"
        f"QPushButton:disabled {{ color: {S.hex_(S.TEXT_MUT)}; opacity: 0.35; }}"
    )
    return btn


# ---------------------------------------------------------------------------
# PlayerPanel
# ---------------------------------------------------------------------------
class PlayerPanel(QWidget):
    """
    Right panel: Now Playing header, artwork, metadata, controls,
    progress bar, volume slider, queue header + queue list.
    """

    def __init__(self, player: 'Player', parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._player = player
        self._mini_mode = False
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(S.sp(2), 0, S.sp(8), 0)
        layout.setSpacing(S.sp(10))

        # ---- Header row: "NOW PLAYING" + equalizer + mini-mode toggle ----
        hdr_row = QWidget()
        hdr_row.setFixedHeight(S.sp(18))
        hdr_layout = QHBoxLayout(hdr_row)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(S.sp(8))

        self._hdr_lbl = QLabel("PLAYER")
        self._hdr_lbl.setStyleSheet(
            f"color: {S.hex_(S.TEXT_MUT)}; font-family: monospace;"
            f"font-size: {S.sp(10)}px; font-weight: bold;"
        )
        hdr_layout.addWidget(self._hdr_lbl)

        self._hdr_eq = EqualizerWidget()
        self._hdr_eq.setVisible(False)
        hdr_layout.addWidget(self._hdr_eq)

        hdr_layout.addStretch()

        self._mini_btn = QPushButton("\U000f0047")  # collapse icon
        self._mini_btn.setFixedSize(S.sp(20), S.sp(20))
        self._mini_btn.setFlat(True)
        self._mini_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._mini_btn.setToolTip("Mini player mode")
        self._mini_btn.setStyleSheet(
            f"QPushButton {{ color: {S.hex_(S.TEXT_MUT)}; font-size: {S.sp(16)}px;"
            f"background: transparent; border: none; }}"
            f"QPushButton:hover {{ color: {S.hex_(S.ACCENT_BRT)}; }}"
        )
        hdr_layout.addWidget(self._mini_btn)
        layout.addWidget(hdr_row)

        # ---- Album artwork ----
        self._artwork = _ArtworkWidget()
        self._artwork.clicked.connect(lambda: self._player.play_pause())
        art_container = QWidget()
        ac_layout = QHBoxLayout(art_container)
        ac_layout.setContentsMargins(0, 0, 0, 0)
        ac_layout.addStretch()
        ac_layout.addWidget(self._artwork)
        ac_layout.addStretch()
        layout.addWidget(art_container)

        # ---- Metadata: title + artist ----
        meta = QWidget()
        meta_layout = QVBoxLayout(meta)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(S.sp(2))

        self._title_lbl = QLabel("YouTube Music")
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._title_lbl.setStyleSheet(
            f"color: {S.hex_(S.TEXT_PRI)}; font-size: {S.sp(15)}px; font-weight: bold;"
        )
        meta_layout.addWidget(self._title_lbl)

        self._artist_lbl = QLabel("Search or select a song to begin")
        self._artist_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._artist_lbl.setStyleSheet(
            f"color: {S.hex_(S.TEXT_SEC)}; font-size: {S.sp(12)}px;"
        )
        meta_layout.addWidget(self._artist_lbl)

        self._error_lbl = QLabel("")
        self._error_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._error_lbl.setWordWrap(True)
        self._error_lbl.setStyleSheet(
            f"color: {S.hex_(S.URGENT)}; font-size: {S.sp(10)}px;"
        )
        self._error_lbl.setVisible(False)
        meta_layout.addWidget(self._error_lbl)

        layout.addWidget(meta)

        # ---- Transport controls ----
        ctrl_row = QWidget()
        ctrl_layout = QHBoxLayout(ctrl_row)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(S.sp(20))
        ctrl_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._shuffle_btn = _ctrl_btn("\U000f049d", 22, "Shuffle")  # shuffle icon
        self._prev_btn    = _ctrl_btn("\U000f04ae", 26, "Previous")  # skip-prev
        self._play_btn    = _PlayButton()
        self._next_btn    = _ctrl_btn("\U000f04ad", 26, "Next")      # skip-next
        self._repeat_btn  = _ctrl_btn("\U000f0458", 22, "Repeat")   # repeat

        self._shuffle_btn.clicked.connect(self._player.toggle_shuffle)
        self._prev_btn.clicked.connect(self._player.previous)
        self._play_btn.clicked.connect(self._player.play_pause)
        self._next_btn.clicked.connect(self._player.next)
        self._repeat_btn.clicked.connect(self._player.toggle_repeat)

        for w in [self._shuffle_btn, self._prev_btn, self._play_btn,
                  self._next_btn, self._repeat_btn]:
            ctrl_layout.addWidget(w)

        layout.addWidget(ctrl_row)

        # ---- Progress bar ----
        self._progress = _ProgressBar()
        self._progress.seek_requested.connect(self._player.seek)
        layout.addWidget(self._progress)

        # Timestamps row
        ts_row = QWidget()
        ts_row.setFixedHeight(S.sp(14))
        ts_layout = QHBoxLayout(ts_row)
        ts_layout.setContentsMargins(0, 0, 0, 0)

        self._pos_lbl = QLabel("0:00")
        self._pos_lbl.setStyleSheet(
            f"color: {S.hex_(S.TEXT_SEC)}; font-family: monospace; font-size: {S.sp(10)}px;"
        )
        self._dur_lbl = QLabel("0:00")
        self._dur_lbl.setStyleSheet(
            f"color: {S.hex_(S.TEXT_MUT)}; font-family: monospace; font-size: {S.sp(10)}px;"
        )
        ts_layout.addWidget(self._pos_lbl)
        ts_layout.addStretch()
        ts_layout.addWidget(self._dur_lbl)
        layout.addWidget(ts_row)

        # ---- Volume row ----
        vol_row = QWidget()
        vr_layout = QHBoxLayout(vol_row)
        vr_layout.setContentsMargins(0, 0, 0, 0)
        vr_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._vol_slider = _VolumeSlider()
        self._vol_slider.volume_changed.connect(self._on_volume_change)
        self._vol_slider.mute_toggled.connect(self._player.toggle_mute)
        vr_layout.addWidget(self._vol_slider)
        layout.addWidget(vol_row)

        # ---- Divider ----
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {S.rgba_(S.BORDER_SUB)};")
        layout.addWidget(divider)

        # ---- Queue header ----
        q_hdr = QWidget()
        q_hdr.setFixedHeight(S.sp(18))
        q_hdr_layout = QHBoxLayout(q_hdr)
        q_hdr_layout.setContentsMargins(0, 0, S.sp(2), 0)

        self._q_hdr_lbl = QLabel("Queue")
        self._q_hdr_lbl.setStyleSheet(
            f"color: {S.hex_(S.TEXT_SEC)}; font-size: {S.sp(12)}px; font-weight: bold;"
        )
        q_hdr_layout.addWidget(self._q_hdr_lbl)
        q_hdr_layout.addStretch()

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFlat(True)
        self._clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._clear_btn.setStyleSheet(
            f"QPushButton {{ color: {S.hex_(S.TEXT_MUT)}; font-family: monospace;"
            f"font-size: {S.sp(10)}px; background: transparent; border: none; }}"
            f"QPushButton:hover {{ color: {S.hex_(S.TEXT_PRI)}; }}"
        )
        self._clear_btn.clicked.connect(self._player.clear_queue)
        self._clear_btn.setVisible(False)
        q_hdr_layout.addWidget(self._clear_btn)
        layout.addWidget(q_hdr)

        # ---- Queue list ----
        self._queue = QueueWidget(self._player)
        layout.addWidget(self._queue)

        # ---- Empty queue placeholder ----
        self._empty_lbl = QLabel("Queue is empty. Search for a song or click + to add.")
        self._empty_lbl.setWordWrap(True)
        self._empty_lbl.setStyleSheet(
            f"color: {S.hex_(S.TEXT_MUT)}; font-size: {S.sp(11)}px;"
        )
        layout.addWidget(self._empty_lbl)

        layout.addStretch()

    def _connect_signals(self) -> None:
        p = self._player
        p.current_index_changed.connect(self._on_song_changed)
        p.is_playing_changed.connect(self._on_playing_changed)
        p.position_changed.connect(self._on_position)
        p.volume_changed.connect(self._on_volume)
        p.shuffle_changed.connect(self._on_shuffle)
        p.repeat_changed.connect(self._on_repeat)
        p.error_changed.connect(self._on_error)
        p.queue_changed.connect(self._on_queue_changed)

    def _on_song_changed(self, _=None) -> None:
        song = self._player.current_song
        self._artwork.set_url(song.get("thumbnail", ""))
        title = song.get("title", "YouTube Music")
        artist = song.get("artist", "Search or select a song to begin")
        self._title_lbl.setText(title)
        self._artist_lbl.setText(artist)

    def _on_playing_changed(self, playing: bool) -> None:
        self._hdr_lbl.setText("NOW PLAYING" if playing else "PLAYER")
        self._hdr_eq.setVisible(playing)
        self._hdr_eq.set_playing(playing)
        self._artwork.set_playing(playing)
        self._play_btn.set_playing(playing)

    def _on_position(self, pos: float, dur: float) -> None:
        self._progress.set_state(pos, dur)
        self._pos_lbl.setText(self._player.format_time(pos))
        self._dur_lbl.setText(self._player.format_time(dur))

    def _on_volume(self, level: float, muted: bool) -> None:
        self._vol_slider.set_state(level, muted)

    def _on_volume_change(self, val: float) -> None:
        if val < 0:
            self._player.toggle_mute()
        else:
            self._player.set_volume(val)

    def _on_shuffle(self, enabled: bool) -> None:
        color = S.hex_(S.ACCENT_BRT) if enabled else S.hex_(S.TEXT_SEC)
        self._shuffle_btn.setStyleSheet(
            f"QPushButton {{ color: {color}; font-size: {S.sp(18)}px;"
            f"background: transparent; border: none; }}"
            f"QPushButton:hover {{ color: {S.hex_(S.TEXT_PRI)}; }}"
        )

    def _on_repeat(self, enabled: bool) -> None:
        color = S.hex_(S.ACCENT_BRT) if enabled else S.hex_(S.TEXT_SEC)
        self._repeat_btn.setStyleSheet(
            f"QPushButton {{ color: {color}; font-size: {S.sp(18)}px;"
            f"background: transparent; border: none; }}"
            f"QPushButton:hover {{ color: {S.hex_(S.TEXT_PRI)}; }}"
        )

    def _on_error(self, err: str) -> None:
        self._error_lbl.setText(err)
        self._error_lbl.setVisible(bool(err))

    def _on_queue_changed(self) -> None:
        n = len(self._player.queue)
        self._q_hdr_lbl.setText(self._player.queue_header())
        self._clear_btn.setVisible(n > 0)
        self._empty_lbl.setVisible(n == 0)

    def set_mini_toggle_callback(self, cb) -> None:
        self._mini_btn.clicked.connect(cb)


# ---------------------------------------------------------------------------
# Play/Pause button (46px accent circle)
# ---------------------------------------------------------------------------
class _PlayButton(QWidget):
    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._is_playing = False
        self._hovered = False
        self._pressed = False
        sz = S.sp(46)
        self.setFixedSize(sz, sz)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_playing(self, playing: bool) -> None:
        self._is_playing = playing
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        sz = self.width()

        # Circle
        if self._pressed:
            color = QColor("#5fb88f")
        elif self._hovered:
            color = S.ACCENT_BRT
        else:
            color = S.ACCENT
        path = QPainterPath()
        path.addEllipse(0, 0, sz, sz)
        p.fillPath(path, color)

        # Icon
        p.setPen(S.BG)
        f = QFont()
        f.setPixelSize(S.sp(20))
        p.setFont(f)
        icon = "\U000f03e4" if self._is_playing else "\U000f040a"  # pause / play
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, icon)
        p.end()

    def enterEvent(self, e) -> None:
        self._hovered = True
        self.update()

    def leaveEvent(self, e) -> None:
        self._hovered = False
        self._pressed = False
        self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._pressed = False
            self.update()
            if self.rect().contains(e.pos()):
                self.clicked.emit()
