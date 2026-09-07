"""
queue_widget.py — Queue list with drag-reorder, edge auto-scroll, smooth scrollbar.
"""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QRect, pyqtSignal as Signal, QSize
)
from PyQt6.QtGui import (
    QPainter, QColor, QPainterPath, QCursor, QFont, QPen, QBrush
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy, QPushButton, QScrollBar, QAbstractScrollArea
)

from app import style as S
from app.ui.widgets.thumbnail import ThumbnailWidget
from app.ui.widgets.equalizer import EqualizerWidget

if TYPE_CHECKING:
    from app.player import Player


# ---------------------------------------------------------------------------
# Smooth custom scrollbar
# ---------------------------------------------------------------------------
class _SmoothScrollBar(QScrollBar):
    """Hover-expanding vertical scrollbar: 3.5px idle → 6px on hover/drag."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(Qt.Orientation.Vertical, parent)
        self._hovered = False
        self._dragging = False
        self._drag_start_y = 0
        self._drag_start_val = 0
        self.setFixedWidth(S.sp(12))
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def _thumb_rect(self) -> QRect:
        rng = self.maximum() - self.minimum()
        if rng <= 0:
            return QRect(0, 0, 0, 0)
        h = self.height()
        page = self.pageStep()
        ratio = page / (rng + page)
        thumb_h = max(S.sp(24), int(ratio * h))
        thumb_y = int((self.value() / max(1, rng)) * (h - thumb_h))
        active = self._hovered or self._dragging
        w = S.sp(6) if active else S.sp(4)
        x = self.width() - w - S.sp(1)
        return QRect(x, thumb_y, w, thumb_h)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self._hovered or self._dragging

        # Track
        track_w = S.sp(6) if active else S.sp(4)
        track_x = self.width() - track_w - S.sp(1)
        track_color = QColor(255, 255, 255, 20 if active else 5)
        path = QPainterPath()
        path.addRoundedRect(track_x, 0, track_w, self.height(), track_w / 2, track_w / 2)
        p.fillPath(path, track_color)

        # Thumb
        tr = self._thumb_rect()
        if tr.isValid():
            if self._dragging:
                thumb_color = S.ACCENT_BRT
            elif self._hovered:
                thumb_color = S.ACCENT
            else:
                thumb_color = QColor(165, 229, 191, 115)
            tpath = QPainterPath()
            tpath.addRoundedRect(tr.x(), tr.y(), tr.width(), tr.height(),
                                 tr.width() / 2, tr.width() / 2)
            p.fillPath(tpath, thumb_color)
        p.end()

    def enterEvent(self, e) -> None:
        self._hovered = True
        self.update()

    def leaveEvent(self, e) -> None:
        self._hovered = False
        self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        tr = self._thumb_rect()
        if tr.contains(e.pos()):
            self._dragging = True
            self._drag_start_y = e.pos().y()
            self._drag_start_val = self.value()
        else:
            # Click on track: jump
            rng = self.maximum() - self.minimum()
            if rng > 0:
                thumb_h = tr.height()
                track_h = self.height() - thumb_h
                if track_h > 0:
                    target_thumb_y = max(0, min(track_h, e.pos().y() - thumb_h // 2))
                    new_val = int((target_thumb_y / track_h) * rng)
                    self.setValue(new_val)
                    self._dragging = True
                    self._drag_start_y = e.pos().y()
                    self._drag_start_val = new_val
        self.update()

    def mouseMoveEvent(self, e) -> None:
        if not self._dragging:
            return
        rng = self.maximum() - self.minimum()
        tr = self._thumb_rect()
        track_h = self.height() - tr.height()
        if track_h > 0 and rng > 0:
            delta = e.pos().y() - self._drag_start_y
            new_val = self._drag_start_val + int((delta / track_h) * rng)
            self.setValue(max(self.minimum(), min(self.maximum(), new_val)))
        self.update()

    def mouseReleaseEvent(self, e) -> None:
        self._dragging = False
        self.update()


# ---------------------------------------------------------------------------
# Queue row
# ---------------------------------------------------------------------------
class _QueueRow(QFrame):
    play_clicked   = Signal(int)
    remove_clicked = Signal(int)
    drag_started   = Signal(int, int)   # index, grip_y_in_list

    def __init__(self, index: int, song: dict, is_current: bool, is_playing: bool,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.row_index = index
        self.song = song
        self._is_current = is_current
        self._is_playing = is_playing
        self._hovered = False
        self._dragging = False
        self._grip_pressed = False
        self._drop_above = False
        self._drop_below = False
        self.setFixedHeight(S.sp(44))
        self.setMouseTracking(True)
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(S.sp(8), 0, S.sp(14), 0)
        layout.setSpacing(S.sp(8))

        # Col 1: index / equalizer (16px)
        self._idx_lbl = QLabel(str(self.row_index + 1))
        self._idx_lbl.setFixedWidth(S.sp(16))
        self._idx_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._idx_lbl.setStyleSheet(
            f"color: {S.hex_(S.TEXT_MUT)}; font-family: monospace; font-size: {S.sp(10)}px;"
        )
        self._eq = EqualizerWidget()
        self._eq.setVisible(self._is_current)
        self._eq.set_playing(self._is_playing)
        self._idx_lbl.setVisible(not self._is_current)

        idx_w = QWidget()
        idx_w.setFixedWidth(S.sp(16))
        il = QHBoxLayout(idx_w)
        il.setContentsMargins(0, 0, 0, 0)
        il.addWidget(self._idx_lbl)
        il.addWidget(self._eq)
        layout.addWidget(idx_w)

        # Col 2: thumbnail (34x34)
        self._thumb = ThumbnailWidget(size=S.sp(34), radius=S.sp(6))
        self._thumb.set_url(self.song.get("thumbnail", ""))
        layout.addWidget(self._thumb)

        # Col 3: title + artist
        info = QWidget()
        info.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        il2 = QVBoxLayout(info)
        il2.setContentsMargins(0, 0, 0, 0)
        il2.setSpacing(S.sp(1))

        self._title = QLabel(self.song.get("title", ""))
        self._title.setStyleSheet(
            f"color: {S.hex_(S.ACCENT_BRT if self._is_current else S.TEXT_PRI)};"
            f"font-size: {S.sp(12)}px;"
            f"font-weight: {'bold' if self._is_current else 'normal'};"
        )
        self._artist = QLabel(self.song.get("artist", ""))
        self._artist.setStyleSheet(
            f"color: {S.hex_(S.TEXT_SEC)}; font-size: {S.sp(10)}px;"
        )
        il2.addWidget(self._title)
        il2.addWidget(self._artist)
        layout.addWidget(info)

        # Col 4: action box (96px) — duration or play/remove buttons
        self._action = QWidget()
        self._action.setFixedWidth(S.sp(64))
        al = QHBoxLayout(self._action)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(S.sp(3))

        self._dur = QLabel(self.song.get("duration", ""))
        self._dur.setStyleSheet(
            f"color: {S.hex_(S.ACCENT if self._is_current else S.TEXT_MUT)};"
            f"font-family: monospace; font-size: {S.sp(10)}px;"
        )
        self._dur.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._play_btn = QPushButton("\U000f040a")  # play icon
        self._play_btn.setFixedSize(S.sp(20), S.sp(20))
        self._play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._play_btn.setStyleSheet(
            f"QPushButton {{ color: {S.hex_(S.TEXT_SEC)}; font-size: {S.sp(11)}px;"
            f"background: transparent; border-radius: 4px; }}"
            f"QPushButton:hover {{ color: {S.hex_(S.ACCENT_BRT)};"
            f"background: {S.hex_(S.SURF_ACTIVE)}; }}"
        )
        self._play_btn.clicked.connect(lambda: self.play_clicked.emit(self.row_index))
        self._play_btn.setVisible(False)

        self._remove_btn = QPushButton("\U000f0156")  # close/remove icon
        self._remove_btn.setFixedSize(S.sp(20), S.sp(20))
        self._remove_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._remove_btn.setStyleSheet(
            f"QPushButton {{ color: {S.hex_(S.TEXT_SEC)}; font-size: {S.sp(11)}px;"
            f"background: transparent; border-radius: 4px; }}"
            f"QPushButton:hover {{ color: {S.hex_(S.URGENT)};"
            f"background: rgba(255,83,69,50); }}"
        )
        self._remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.row_index))
        self._remove_btn.setVisible(False)

        al.addWidget(self._dur)
        al.addWidget(self._play_btn)
        al.addWidget(self._remove_btn)
        layout.addWidget(self._action)

        # Grip handle (rightmost 28px)
        self._grip = QLabel("\U000f07c1")  #  drag handle
        self._grip.setFixedSize(S.sp(28), S.sp(44))
        self._grip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grip.setStyleSheet(
            f"color: {S.hex_(S.TEXT_MUT)}; font-size: {S.sp(14)}px;"
        )
        self._grip.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self._grip.installEventFilter(self)
        layout.addWidget(self._grip)

    def _apply_style(self) -> None:
        if self._dragging:
            bg = S.hex_(S.SURF_ACTIVE)
            border = S.hex_(S.ACCENT_BRT)
            bw = "1.5px"
        elif self._is_current:
            bg = "rgba(124,203,162,28)"
            border = "rgba(165,229,191,56)"
            bw = "1px"
        elif self._hovered:
            bg = S.hex_(S.SURF_HOVER)
            border = "transparent"
            bw = "1px"
        else:
            bg = "transparent"
            border = "transparent"
            bw = "1px"
        self.setStyleSheet(
            f"_QueueRow {{ background: {bg}; border: {bw} solid {border}; border-radius: 8px; }}"
        )

    def set_current(self, is_current: bool, is_playing: bool) -> None:
        self._is_current = is_current
        self._is_playing = is_playing
        self._eq.setVisible(is_current)
        self._eq.set_playing(is_playing)
        self._idx_lbl.setVisible(not is_current)
        color = S.ACCENT_BRT if is_current else S.TEXT_PRI
        self._title.setStyleSheet(
            f"color: {S.hex_(color)};"
            f"font-size: {S.sp(12)}px;"
            f"font-weight: {'bold' if is_current else 'normal'};"
        )
        self._dur.setStyleSheet(
            f"color: {S.hex_(S.ACCENT if is_current else S.TEXT_MUT)};"
            f"font-family: monospace; font-size: {S.sp(10)}px;"
        )
        self._apply_style()

    def set_dragging(self, dragging: bool) -> None:
        self._dragging = dragging
        if dragging:
            self._grip.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            self._grip.setStyleSheet(
                f"color: {S.hex_(S.ACCENT_BRT)}; font-size: {S.sp(14)}px;"
            )
        else:
            self._grip.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            self._grip.setStyleSheet(
                f"color: {S.hex_(S.TEXT_MUT)}; font-size: {S.sp(14)}px;"
            )
        self._apply_style()

    def set_drop_indicator(self, above: bool, below: bool) -> None:
        self._drop_above = above
        self._drop_below = below
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._drop_above or self._drop_below:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QPen(S.ACCENT_BRT, 2))
            if self._drop_above:
                p.drawLine(0, 1, self.width(), 1)
            if self._drop_below:
                p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
            p.end()

    def enterEvent(self, e) -> None:
        self._hovered = True
        self._dur.setVisible(False)
        self._play_btn.setVisible(True)
        self._remove_btn.setVisible(True)
        self._grip.setStyleSheet(
            f"color: {S.hex_(S.ACCENT_BRT)}; font-size: {S.sp(14)}px;"
        )
        self._apply_style()

    def leaveEvent(self, e) -> None:
        self._hovered = False
        self._dur.setVisible(True)
        self._play_btn.setVisible(False)
        self._remove_btn.setVisible(False)
        self._grip.setStyleSheet(
            f"color: {S.hex_(S.TEXT_MUT)}; font-size: {S.sp(14)}px;"
        )
        self._apply_style()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.play_clicked.emit(self.row_index)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._grip:
            from PyQt6.QtCore import QEvent
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                # Map grip position to parent scroll area
                pos_in_list = self.mapToParent(event.pos())
                self.drag_started.emit(self.row_index, pos_in_list.y())
                return True
        return super().eventFilter(obj, event)


# ---------------------------------------------------------------------------
# Queue container widget
# ---------------------------------------------------------------------------
class QueueWidget(QScrollArea):
    """Full queue list with smooth scrollbar and drag-reorder."""

    def __init__(self, player: 'Player', parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._player = player
        self._rows: list[_QueueRow] = []

        # Drag state
        self._dragged_idx   = -1
        self._drop_target   = -1
        self._drag_start_y  = 0   # cursor Y relative to scroll container
        self._grab_offset_y = 0   # where in the row the grip was grabbed

        # Auto-scroll timer (60fps)
        self._auto_scroll = QTimer(self)
        self._auto_scroll.setInterval(16)
        self._auto_scroll.timeout.connect(self._do_auto_scroll)

        # Custom scrollbar
        self._scrollbar = _SmoothScrollBar(self)
        self.setVerticalScrollBar(self._scrollbar)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        # Container
        self._container = QWidget()
        self._container.setMouseTracking(True)
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(S.sp(3))
        self._container_layout.addStretch()
        self.setWidget(self._container)
        self.setMouseTracking(True)

        # Connect player
        player.queue_changed.connect(self._refresh)
        player.current_index_changed.connect(self._update_current)
        player.is_playing_changed.connect(self._on_playing_changed)

    def _refresh(self) -> None:
        # Remove all rows
        for row in self._rows:
            self._container_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        queue = self._player.queue
        current_vid = self._player.current_song.get("videoId", "")
        is_playing = self._player.is_playing

        for i, song in enumerate(queue):
            is_current = (i == self._player.current_index)
            row = _QueueRow(i, song, is_current, is_playing and is_current)
            row.play_clicked.connect(self._player.play_index)
            row.remove_clicked.connect(self._player.remove_from_queue)
            row.drag_started.connect(self._on_drag_started)
            self._container_layout.insertWidget(self._container_layout.count() - 1, row)
            self._rows.append(row)

        # Adjust height
        max_h = min(S.sp(264), len(queue) * S.sp(44))
        if queue:
            self.setFixedHeight(max_h + S.sp(3))  # small bottom padding
        else:
            self.setFixedHeight(0)
        self.setVisible(bool(queue))

    def _update_current(self, _=None) -> None:
        is_playing = self._player.is_playing
        for i, row in enumerate(self._rows):
            is_c = (i == self._player.current_index)
            row.set_current(is_c, is_playing and is_c)

    def _on_playing_changed(self, _=None) -> None:
        self._update_current()

    # ---------------------------------------------------------------- drag

    def _on_drag_started(self, index: int, cursor_y_in_list: int) -> None:
        self._dragged_idx = index
        self._drop_target = index
        # grab_offset = where in the row the grip is (center of row)
        self._grab_offset_y = S.sp(22)  # half row height
        self._drag_start_y = cursor_y_in_list
        if 0 <= index < len(self._rows):
            self._rows[index].set_dragging(True)
        self._auto_scroll.start()
        # Install global mouse tracking
        self._container.installEventFilter(self)
        self.installEventFilter(self)

    def _get_cursor_y_in_scroll(self) -> int:
        """Get cursor Y position relative to the scroll area viewport."""
        from PyQt6.QtGui import QCursor as GCursor
        pos = self.viewport().mapFromGlobal(GCursor.pos())
        return pos.y()

    def _do_auto_scroll(self) -> None:
        if self._dragged_idx < 0:
            self._auto_scroll.stop()
            return

        cursor_y = self._get_cursor_y_in_scroll()
        h = self.viewport().height()
        max_scroll = self._scrollbar.maximum()
        if max_scroll <= 0:
            return

        edge = S.sp(36)
        step = 0
        if cursor_y < edge:
            factor = max(0.2, min(1.0, (edge - cursor_y) / edge))
            step = -max(1, round(1.5 + factor * 3.5))
        elif cursor_y > h - edge:
            factor = max(0.2, min(1.0, (cursor_y - (h - edge)) / edge))
            step = max(1, round(1.5 + factor * 3.5))

        if step != 0:
            new_val = max(0, min(max_scroll, self._scrollbar.value() + step))
            self._scrollbar.setValue(new_val)

        # Update drop target
        content_y = cursor_y + self.verticalScrollBar().value()
        row_h = S.sp(44) + S.sp(3)
        approx = max(0, min(len(self._rows) - 1, int(content_y / row_h)))
        if approx != self._drop_target:
            # Clear old indicator
            if 0 <= self._drop_target < len(self._rows):
                self._rows[self._drop_target].set_drop_indicator(False, False)
            self._drop_target = approx

        # Set new indicator
        if self._dragged_idx >= 0 and 0 <= self._drop_target < len(self._rows):
            dragged = self._dragged_idx
            target  = self._drop_target
            if target != dragged:
                above = dragged > target
                below = dragged < target
                self._rows[target].set_drop_indicator(above, below)

    def mouseMoveEvent(self, e) -> None:
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        if self._dragged_idx >= 0:
            self._finish_drag()
        super().mouseReleaseEvent(e)

    def _finish_drag(self) -> None:
        self._auto_scroll.stop()
        # Clear all indicators
        for row in self._rows:
            row.set_drop_indicator(False, False)
            row.set_dragging(False)

        if (self._dragged_idx >= 0 and self._drop_target >= 0
                and self._dragged_idx != self._drop_target):
            self._player.move_queue_item(self._dragged_idx, self._drop_target)

        self._dragged_idx = -1
        self._drop_target = -1

    def wheelEvent(self, e) -> None:
        # Handle 2-finger touchpad and mouse wheel
        dy = 0
        if e.pixelDelta().y() != 0:
            dy = -e.pixelDelta().y()
        elif e.angleDelta().y() != 0:
            dy = -int(e.angleDelta().y() / 120 * S.sp(64))
        if dy != 0:
            new_val = max(0, min(self._scrollbar.maximum(),
                                  self._scrollbar.value() + dy))
            self._scrollbar.setValue(new_val)
            e.accept()
        else:
            super().wheelEvent(e)
