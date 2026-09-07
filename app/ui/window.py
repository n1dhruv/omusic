"""
window.py — Main frameless floating window for omusic.

Layout:
  - Full card background: #0b1511 (BG) with blurred album art ambient backdrop
  - Scale + fade open/close animation (matching QML Behavior on opacity/scale)
  - Left panel (270px): SearchPanel
  - Vertical divider (1px, BORDER_SUB)
  - Right panel (~490px): PlayerPanel
  - OR: MiniPlayer (76px, when mini_mode=True)
  - Bottom bar: keyboard shortcut hints
  - Rounded corners (8px), border (1px BORDER)
  - Click-outside-to-close (via QApplication.focusChanged)
  - Center of screen positioning

Keyboard shortcuts (matching QML):
  Space           → Play/Pause
  J / Down arrow  → Navigate queue down
  K / Up arrow    → Navigate queue up
  Enter           → Play selected queue item
  /               → Focus search
  S               → Toggle shuffle
  R               → Toggle repeat
  M               → Toggle mute
  N               → Next
  P               → Previous
  Escape          → Close window
"""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import sys

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    QPoint, QRect, QSize, QUrl, pyqtSignal as Signal
)
from PyQt6.QtGui import (
    QPainter, QColor, QPainterPath, QPen, QBrush, QPixmap,
    QLinearGradient, QKeyEvent, QFont, QIcon
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QApplication,
    QFrame, QSizePolicy, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsOpacityEffect, QGraphicsBlurEffect
)

from app import style as S
from app.ui.search_panel  import SearchPanel
from app.ui.player_panel  import PlayerPanel
from app.ui.mini_player   import MiniPlayer

if TYPE_CHECKING:
    from app.player import Player


# ---------------------------------------------------------------------------
# Blurred pixmap helper
# ---------------------------------------------------------------------------
def _make_blurred_pixmap(src: QPixmap, target_size: QSize, blur: float = 60.0) -> QPixmap:
    """
    Scale src to target_size (filling), apply Gaussian blur, return result.
    Uses QGraphicsScene so it works without PIL.
    """
    scaled = src.scaled(
        target_size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation
    )
    # Crop if needed
    if scaled.width() > target_size.width() or scaled.height() > target_size.height():
        x = (scaled.width()  - target_size.width())  // 2
        y = (scaled.height() - target_size.height()) // 2
        scaled = scaled.copy(x, y, target_size.width(), target_size.height())

    scene = QGraphicsScene()
    item  = QGraphicsPixmapItem(scaled)
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(blur)
    item.setGraphicsEffect(effect)
    scene.addItem(item)

    result = QPixmap(target_size)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    scene.render(painter)
    painter.end()
    return result


# ---------------------------------------------------------------------------
# Bottom bar (keyboard hints)
# ---------------------------------------------------------------------------
class _BottomBar(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(S.sp(18))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S.sp(8))

        hints = [
            ("Space", "Play/Pause"),
            ("J/K",   "Navigate"),
            ("Enter", "Play"),
            ("/",     "Search"),
            ("S",     "Shuffle"),
            ("R",     "Repeat"),
        ]
        for key, desc in hints:
            k = QLabel(key)
            k.setStyleSheet(
                f"color: {S.hex_(S.TEXT_SEC)}; font-family: monospace;"
                f"font-size: {S.sp(10)}px; font-weight: bold;"
            )
            d = QLabel(desc)
            d.setStyleSheet(
                f"color: {S.hex_(S.TEXT_MUT)}; font-size: {S.sp(10)}px;"
            )
            layout.addWidget(k)
            layout.addWidget(d)

        layout.addStretch()

        brand = QLabel("omusic")
        brand.setStyleSheet(
            f"color: {S.hex_(S.TEXT_MUT)}; font-family: monospace; font-size: {S.sp(9)}px;"
        )
        layout.addWidget(brand)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class YtMusicWindow(QWidget):
    """
    Frameless floating window, centered on screen.
    Full width: 760px. Height: auto.
    """

    def __init__(self, player: 'Player', parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, Qt.WindowType.FramelessWindowHint
                                | Qt.WindowType.Tool
                                | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setFixedWidth(S.sp(760))

        self._player = player
        self._is_open = False
        self._mini_mode = False
        self._backdrop_pixmap: Optional[QPixmap] = None
        self._backdrop_opacity: float = 0.0
        self._current_thumb_url: str = ""

        # Network manager for backdrop download
        self._nam = QNetworkAccessManager(self)
        self._reply: Optional[QNetworkReply] = None

        self._build_ui()
        self._connect_signals()
        self._setup_animations()

        # Click-outside-to-close
        QApplication.instance().focusChanged.connect(self._on_focus_changed)

    # ---------------------------------------------------------------- build

    def _build_ui(self) -> None:
        # Outer layout with padding (14px all sides, 28px bottom for bottom bar)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(S.sp(14), S.sp(14), S.sp(14), 0)
        self._outer.setSpacing(S.sp(12))

        # ---- FULL PLAYER ----
        self._full_widget = QWidget()
        self._full_widget.setVisible(True)
        full_layout = QVBoxLayout(self._full_widget)
        full_layout.setContentsMargins(0, 0, 0, 0)
        full_layout.setSpacing(S.sp(12))

        # Main row: search | divider | player
        main_row = QHBoxLayout()
        main_row.setContentsMargins(0, 0, 0, 0)
        main_row.setSpacing(S.sp(14))

        self._search = SearchPanel(self._player)
        main_row.addWidget(self._search)

        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet(f"background: {S.rgba_(S.BORDER_SUB)};")
        divider.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        main_row.addWidget(divider)

        self._player_panel = PlayerPanel(self._player)
        self._player_panel.set_mini_toggle_callback(self._enter_mini)
        main_row.addWidget(self._player_panel, 1)

        full_layout.addLayout(main_row)

        # Bottom bar
        self._bottom_bar = _BottomBar()
        full_layout.addWidget(self._bottom_bar)

        self._outer.addWidget(self._full_widget)

        # ---- MINI PLAYER ----
        self._mini = MiniPlayer(self._player)
        self._mini.expand_clicked.connect(self._exit_mini)
        self._mini.setVisible(False)
        self._outer.addWidget(self._mini)

    def _connect_signals(self) -> None:
        self._player.current_index_changed.connect(self._on_song_changed)
        self._player.is_playing_changed.connect(self._on_playing_changed)

    def _setup_animations(self) -> None:
        # Opacity effect
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(180)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ---------------------------------------------------------------- open/close

    def open(self, tray_geom: Optional[QRect] = None) -> None:
        if self._is_open:
            return
        self._is_open = True
        self._anchor_to_menubar(tray_geom)
        self.show()
        self.raise_()
        self.activateWindow()
        self._fade_anim.stop()
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def close_window(self) -> None:
        if not self._is_open:
            return
        self._is_open = False
        self._fade_anim.stop()
        if self._fade_anim.receivers(self._fade_anim.finished):
            self._fade_anim.finished.disconnect()
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self._on_close_done)
        self._fade_anim.start()

    def _on_close_done(self) -> None:
        try:
            self._fade_anim.finished.disconnect(self._on_close_done)
        except Exception:
            pass
        self.hide()

    def toggle(self, tray_geom: Optional[QRect] = None) -> None:
        if self._is_open:
            self.close_window()
        else:
            self.open(tray_geom)

    _last_tray_geom: Optional[QRect] = None

    def _anchor_to_menubar(self, tray_geom: Optional[QRect] = None) -> None:
        if tray_geom is not None and tray_geom.isValid() and tray_geom.width() > 0:
            self._last_tray_geom = tray_geom
        else:
            tray_geom = self._last_tray_geom

        self.adjustSize()
        screen = QApplication.primaryScreen()
        if not screen:
            return
        sg = screen.availableGeometry()

        w = self.width()
        h = self.height()

        if tray_geom is not None and tray_geom.isValid() and tray_geom.width() > 0:
            # Horizontally align/center with the tray icon
            x = tray_geom.center().x() - w // 2
            # Clamp inside screen margins
            x = max(sg.left() + S.sp(8), min(sg.right() - w - S.sp(8), x))

            # Check if bar is at top or bottom
            if tray_geom.top() < sg.center().y():
                y = tray_geom.bottom() + S.sp(4)
            else:
                y = tray_geom.top() - h - S.sp(4)
        else:
            # Fallback: top right near menu bar
            x = max(sg.left() + S.sp(8), sg.right() - w - S.sp(14))
            y = sg.top() + S.sp(8)

        self.move(x, y)

    # ---------------------------------------------------------------- mini mode

    def _enter_mini(self) -> None:
        self._mini_mode = True
        self._full_widget.setVisible(False)
        self._mini.setVisible(True)
        self.adjustSize()

    def _exit_mini(self) -> None:
        self._mini_mode = False
        self._mini.setVisible(False)
        self._full_widget.setVisible(True)
        self.adjustSize()

    # ---------------------------------------------------------------- backdrop

    def _on_song_changed(self, _=None) -> None:
        song = self._player.current_song
        url = song.get("thumbnail", "")
        if url == self._current_thumb_url:
            return
        self._current_thumb_url = url
        self._backdrop_pixmap = None
        self._backdrop_opacity = 0.0
        self.update()
        if url:
            import re
            url = re.sub(r"=w\d+-h\d+", "=w800-h800", url)
            if self._reply:
                self._reply.abort()
            req = QNetworkRequest(QUrl(url))
            self._reply = self._nam.get(req)
            self._reply.finished.connect(self._on_backdrop_ready)

    def _on_playing_changed(self, playing: bool) -> None:
        target_opacity = 0.22 if playing else 0.09
        # Fade backdrop opacity
        self._backdrop_target = target_opacity
        self._backdrop_fade_timer = QTimer(self)
        self._backdrop_fade_timer.setInterval(20)
        self._backdrop_fade_timer.timeout.connect(self._backdrop_fade_tick)
        self._backdrop_fade_timer.start()

    def _backdrop_fade_tick(self) -> None:
        target = getattr(self, '_backdrop_target', 0.0)
        step = 0.015
        if abs(self._backdrop_opacity - target) < step:
            self._backdrop_opacity = target
            if hasattr(self, '_backdrop_fade_timer'):
                self._backdrop_fade_timer.stop()
        elif self._backdrop_opacity < target:
            self._backdrop_opacity += step
        else:
            self._backdrop_opacity -= step
        self.update()

    def _on_backdrop_ready(self) -> None:
        reply = self._reply
        if not reply:
            return
        self._reply = None
        if reply.error() != QNetworkReply.NetworkError.NoError:
            reply.deleteLater()
            return
        data = bytes(reply.readAll())
        reply.deleteLater()
        src = QPixmap()
        if not src.loadFromData(data):
            return
        size = QSize(self.width() + S.sp(80), self.height() + S.sp(80))
        self._backdrop_pixmap = _make_blurred_pixmap(src, size, blur=60.0)
        target = 0.22 if self._player.is_playing else 0.09
        self._backdrop_opacity = target
        self.update()

    # ---------------------------------------------------------------- paint

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Rounded card background
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, S.sp(10), S.sp(10))

        # Fill background
        p.fillPath(path, S.BG)

        # Blurred ambient backdrop
        if self._backdrop_pixmap and self._backdrop_opacity > 0:
            p.setClipPath(path)
            p.setOpacity(self._backdrop_opacity)
            off = S.sp(40)
            p.drawPixmap(-off, -off, self._backdrop_pixmap)
            p.setOpacity(1.0)
            p.setClipping(False)

            # Dark gradient overlay for contrast
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0.0, QColor(11, 21, 17, 102))  # 0.40 alpha
            grad.setColorAt(0.5, QColor(11, 21, 17, 178))  # 0.70 alpha
            grad.setColorAt(1.0, S.BG)
            p.setClipPath(path)
            p.fillRect(0, 0, w, h, grad)
            p.setClipping(False)

        # Border
        p.setClipping(False)
        p.setPen(QPen(S.BORDER, 1))
        p.drawPath(path)
        p.end()

    # ---------------------------------------------------------------- focus

    def _on_focus_changed(self, old, new) -> None:
        if not self._is_open:
            return
        if new is None:
            return
        # If new widget is not inside this window, close
        w = new
        while w is not None:
            if w is self:
                return
            w = w.parent()
        # Focus went outside — close
        self.close_window()

    # ---------------------------------------------------------------- keyboard

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()

        # If search field has focus, only intercept Escape
        if self._search._input._input.hasFocus():
            if key == Qt.Key.Key_Escape:
                self._search._input._input.clearFocus()
                event.accept()
            return

        if key == Qt.Key.Key_Space:
            self._player.play_pause()
            event.accept()
        elif key in (Qt.Key.Key_J, Qt.Key.Key_Down):
            self._move_queue_selection(1)
            event.accept()
        elif key in (Qt.Key.Key_K, Qt.Key.Key_Up):
            self._move_queue_selection(-1)
            event.accept()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._selected_queue_idx >= 0:
                self._player.play_index(self._selected_queue_idx)
            event.accept()
        elif key == Qt.Key.Key_Slash:
            self._search.focus_search()
            event.accept()
        elif key == Qt.Key.Key_S:
            self._player.toggle_shuffle()
            event.accept()
        elif key == Qt.Key.Key_R:
            self._player.toggle_repeat()
            event.accept()
        elif key == Qt.Key.Key_M:
            self._player.toggle_mute()
            event.accept()
        elif key == Qt.Key.Key_N:
            self._player.next()
            event.accept()
        elif key == Qt.Key.Key_P:
            self._player.previous()
            event.accept()
        elif key == Qt.Key.Key_Escape:
            self.close_window()
            event.accept()
        else:
            super().keyPressEvent(event)

    _selected_queue_idx: int = -1

    def _move_queue_selection(self, direction: int) -> None:
        n = len(self._player.queue)
        if n == 0:
            return
        if self._selected_queue_idx < 0:
            self._selected_queue_idx = self._player.current_index
        self._selected_queue_idx = max(0, min(n - 1, self._selected_queue_idx + direction))
