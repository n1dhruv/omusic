"""
search_panel.py — Left search panel (270px) for omusic.

Contains: search input box, results list, load-more button, placeholder states.
"""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, pyqtSignal as Signal
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QCursor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QScrollArea, QFrame, QSizePolicy, QPushButton, QApplication
)

from app import style as S
from app.ui.widgets.thumbnail import ThumbnailWidget
from app.ui.widgets.equalizer import EqualizerWidget

if TYPE_CHECKING:
    from app.player import Player


# ---------------------------------------------------------------------------
# Single search result row
# ---------------------------------------------------------------------------
class _SearchRow(QFrame):
    """Single search result row, 46px tall."""

    play_clicked      = Signal(int)
    queue_clicked     = Signal(int)
    play_next_clicked = Signal(int)

    def __init__(self, index: int, song: dict, is_current: bool, is_playing: bool,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.row_index = index
        self.song      = song
        self._is_current = is_current
        self._is_playing = is_playing
        self._hovered = False
        self.setFixedHeight(S.sp(46))
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._build()
        self._apply_style()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(S.sp(8), 0, S.sp(8), 0)
        layout.setSpacing(S.sp(8))

        # ---- Column 1: index number / equalizer (16px) ----
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
        idx_l = QHBoxLayout(idx_w)
        idx_l.setContentsMargins(0, 0, 0, 0)
        idx_l.addWidget(self._idx_lbl)
        idx_l.addWidget(self._eq)
        layout.addWidget(idx_w)

        # ---- Column 2: thumbnail (36x36) ----
        self._thumb = ThumbnailWidget(size=S.sp(36), radius=S.sp(6))
        self._thumb.set_url(self.song.get("thumbnail", ""))
        layout.addWidget(self._thumb)

        # ---- Column 3: title + artist ----
        info = QWidget()
        info.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        info_l = QVBoxLayout(info)
        info_l.setContentsMargins(0, 0, 0, 0)
        info_l.setSpacing(S.sp(1))

        self._title_lbl = QLabel(self.song.get("title", ""))
        self._title_lbl.setStyleSheet(
            f"color: {S.hex_(S.ACCENT_BRT if self._is_current else S.TEXT_PRI)};"
            f"font-size: {S.sp(12)}px; font-weight: {'bold' if self._is_current else 'normal'};"
        )
        self._artist_lbl = QLabel(self.song.get("artist", ""))
        self._artist_lbl.setStyleSheet(
            f"color: {S.hex_(S.TEXT_SEC)}; font-size: {S.sp(10)}px;"
        )
        info_l.addWidget(self._title_lbl)
        info_l.addWidget(self._artist_lbl)
        layout.addWidget(info)

        # ---- Column 4: duration / action buttons ----
        self._action = QWidget()
        self._action.setFixedWidth(S.sp(54))
        act_l = QHBoxLayout(self._action)
        act_l.setContentsMargins(0, 0, 0, 0)
        act_l.setSpacing(S.sp(3))

        self._dur_lbl = QLabel(self.song.get("duration", ""))
        self._dur_lbl.setStyleSheet(
            f"color: {S.hex_(S.TEXT_MUT)}; font-family: monospace; font-size: {S.sp(10)}px;"
        )
        self._dur_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._next_btn = QPushButton("\U000f04ad")   # skip-next icon
        self._next_btn.setFixedSize(S.sp(22), S.sp(22))
        self._next_btn.setToolTip("Play next")
        self._next_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._next_btn.setStyleSheet(
            f"QPushButton {{ color: {S.hex_(S.TEXT_SEC)}; font-size: {S.sp(12)}px;"
            f"background: transparent; border-radius: 4px; }}"
            f"QPushButton:hover {{ color: {S.hex_(S.ACCENT_BRT)};"
            f"background: {S.hex_(S.SURF_ACTIVE)}; }}"
        )
        self._next_btn.clicked.connect(lambda: self.play_next_clicked.emit(self.row_index))

        self._queue_btn = QPushButton("+")
        self._queue_btn.setFixedSize(S.sp(22), S.sp(22))
        self._queue_btn.setToolTip("Add to queue")
        self._queue_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._queue_btn.setStyleSheet(
            f"QPushButton {{ color: {S.hex_(S.TEXT_SEC)}; font-size: {S.sp(13)}px;"
            f"background: transparent; border-radius: 4px; font-weight: bold; }}"
            f"QPushButton:hover {{ color: {S.hex_(S.ACCENT_BRT)};"
            f"background: {S.hex_(S.SURF_ACTIVE)}; }}"
        )
        self._queue_btn.clicked.connect(lambda: self.queue_clicked.emit(self.row_index))

        act_l.addWidget(self._dur_lbl)
        act_l.addWidget(self._next_btn)
        act_l.addWidget(self._queue_btn)
        layout.addWidget(self._action)

        self._next_btn.setVisible(False)
        self._queue_btn.setVisible(False)

    def _apply_style(self) -> None:
        if self._is_current:
            bg     = "rgba(124,203,162,30)"
            border = "rgba(165,229,191,61)"
        elif self._hovered:
            bg     = S.hex_(S.SURF_HOVER)
            border = "transparent"
        else:
            bg     = "transparent"
            border = "transparent"
        self.setStyleSheet(
            f"_SearchRow {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}"
        )

    def set_current(self, is_current: bool, is_playing: bool) -> None:
        self._is_current = is_current
        self._is_playing = is_playing
        self._eq.setVisible(is_current)
        self._eq.set_playing(is_playing)
        self._idx_lbl.setVisible(not is_current)
        color = S.ACCENT_BRT if is_current else S.TEXT_PRI
        self._title_lbl.setStyleSheet(
            f"color: {S.hex_(color)}; font-size: {S.sp(12)}px;"
            f"font-weight: {'bold' if is_current else 'normal'};"
        )
        self._apply_style()

    def enterEvent(self, _) -> None:
        self._hovered = True
        self._dur_lbl.setVisible(False)
        self._next_btn.setVisible(True)
        self._queue_btn.setVisible(True)
        self._apply_style()

    def leaveEvent(self, _) -> None:
        self._hovered = False
        self._dur_lbl.setVisible(True)
        self._next_btn.setVisible(False)
        self._queue_btn.setVisible(False)
        self._apply_style()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.play_clicked.emit(self.row_index)


# ---------------------------------------------------------------------------
# Search input box
# ---------------------------------------------------------------------------
class _SearchInput(QFrame):
    """Styled search box: icon + TextInput + clear button."""

    submitted    = Signal(str)
    cleared      = Signal()
    text_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(S.sp(38))
        self._busy = False
        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(60)
        self._spin_timer.timeout.connect(self._spin_tick)
        self._spin_state = 0
        self._spin_chars = ["|", "/", "—", "\\"]
        self._build()
        self._idle_style()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(S.sp(10), 0, S.sp(10), 0)
        layout.setSpacing(S.sp(8))

        self._icon = QLabel("🔍")
        self._icon.setFixedWidth(S.sp(16))
        self._icon.setStyleSheet(f"font-size: {S.sp(12)}px;")
        layout.addWidget(self._icon)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Search YouTube Music...")
        self._input.returnPressed.connect(self._on_submit)
        self._input.textChanged.connect(self.text_changed.emit)
        self._input.textChanged.connect(self._on_text_changed)
        self._input.setStyleSheet(
            f"QLineEdit {{ background: transparent; color: {S.hex_(S.TEXT_PRI)};"
            f"font-size: {S.sp(12)}px; border: none;"
            f"selection-background-color: rgba(124,203,162,90); }}"
        )
        layout.addWidget(self._input, 1)

        self._clear_btn = QPushButton("✕")
        self._clear_btn.setFixedSize(S.sp(16), S.sp(16))
        self._clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._clear_btn.setStyleSheet(
            f"QPushButton {{ color: {S.hex_(S.TEXT_MUT)}; font-size: {S.sp(11)}px;"
            f"background: transparent; border: none; }}"
            f"QPushButton:hover {{ color: {S.hex_(S.TEXT_PRI)}; }}"
        )
        self._clear_btn.clicked.connect(self._on_clear)
        self._clear_btn.setVisible(False)
        layout.addWidget(self._clear_btn)

    def _on_text_changed(self, text: str) -> None:
        self._clear_btn.setVisible(bool(text))

    def _on_submit(self) -> None:
        self.submitted.emit(self._input.text().strip())

    def _on_clear(self) -> None:
        self._input.clear()
        self.cleared.emit()

    def _spin_tick(self) -> None:
        self._spin_state = (self._spin_state + 1) % len(self._spin_chars)
        self._icon.setText(self._spin_chars[self._spin_state])
        self._icon.setStyleSheet(
            f"color: {S.hex_(S.ACCENT_BRT)}; font-size: {S.sp(13)}px; font-weight: bold;"
        )

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            self._spin_timer.start()
        else:
            self._spin_timer.stop()
            self._icon.setText("🔍")
            self._icon.setStyleSheet(f"font-size: {S.sp(12)}px;")

    def _idle_style(self) -> None:
        self.setStyleSheet(
            f"_SearchInput {{ background: {S.hex_(S.SURFACE)};"
            f"border: 1px solid {S.rgba_(S.BORDER)}; border-radius: 9px; }}"
        )

    def focusInEvent(self, e) -> None:
        self.setStyleSheet(
            f"_SearchInput {{ background: {S.hex_(S.SURF_HOVER)};"
            f"border: 1px solid {S.rgba_(S.BORDER_FOC)}; border-radius: 9px; }}"
        )
        super().focusInEvent(e)

    def focusOutEvent(self, e) -> None:
        self._idle_style()
        super().focusOutEvent(e)

    def text(self) -> str:
        return self._input.text()


# ---------------------------------------------------------------------------
# SearchPanel
# ---------------------------------------------------------------------------
class SearchPanel(QWidget):
    """Left panel — 270px fixed width."""

    def __init__(self, player: 'Player', parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._player = player
        self._results: list[dict] = []
        self._rows: list[_SearchRow] = []
        self._show_results = False
        self._last_query = ""
        self.setFixedWidth(S.sp(270))
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S.sp(8))

        # 'SEARCH' header
        hdr = QLabel("SEARCH")
        hdr.setStyleSheet(
            f"color: {S.hex_(S.TEXT_MUT)}; font-family: monospace;"
            f"font-size: {S.sp(10)}px; font-weight: bold;"
        )
        hdr.setFixedHeight(S.sp(18))
        layout.addWidget(hdr)

        # Search input
        self._input = _SearchInput()
        self._input.submitted.connect(self._on_search)
        self._input.cleared.connect(self._on_cleared)
        self._input.text_changed.connect(self._on_input_text_changed)
        layout.addWidget(self._input)

        # Keyboard hints
        hint = QLabel("Enter  Search  ·  Click song to play")
        hint.setStyleSheet(
            f"color: {S.hex_(S.TEXT_MUT)}; font-size: {S.sp(10)}px;"
        )
        layout.addWidget(hint)

        # Results header
        self._results_hdr = QLabel("RESULTS (0)")
        self._results_hdr.setStyleSheet(
            f"color: {S.hex_(S.TEXT_MUT)}; font-family: monospace;"
            f"font-size: {S.sp(10)}px; font-weight: bold;"
        )
        self._results_hdr.setFixedHeight(S.sp(16))
        self._results_hdr.setVisible(False)
        layout.addWidget(self._results_hdr)

        # Scroll area for results
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._scroll.setVisible(False)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(S.sp(3))
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list_container)
        layout.addWidget(self._scroll)

        # Load more button
        self._load_more_btn = QPushButton("+ Load more songs")
        self._load_more_btn.setFixedHeight(S.sp(32))
        self._load_more_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._load_more_btn.setStyleSheet(
            f"QPushButton {{ background: {S.hex_(S.SURFACE)};"
            f"color: {S.hex_(S.TEXT_SEC)}; border: 1px solid {S.rgba_(S.BORDER_SUB)};"
            f"border-radius: 6px; font-size: {S.sp(11)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {S.hex_(S.SURF_HOVER)};"
            f"color: {S.hex_(S.TEXT_PRI)}; border-color: {S.hex_(S.ACCENT)}; }}"
        )
        self._load_more_btn.clicked.connect(self._on_load_more)
        self._load_more_btn.setVisible(False)
        layout.addWidget(self._load_more_btn)

        # Placeholder
        self._placeholder = QLabel("Type a query and press Enter to search.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._placeholder.setStyleSheet(
            f"color: {S.hex_(S.TEXT_MUT)}; font-size: {S.sp(11)}px;"
        )
        self._placeholder.setFixedHeight(S.sp(100))
        layout.addWidget(self._placeholder)

        layout.addStretch()

    def _connect_signals(self) -> None:
        p = self._player
        p.search_results_ready.connect(self._on_results)
        p.search_busy_changed.connect(self._input.set_busy)
        p.search_busy_changed.connect(self._on_search_busy)
        p.load_more_busy_changed.connect(self._on_load_more_busy)
        p.has_more_search_changed.connect(self._on_has_more)
        p.current_index_changed.connect(self._refresh_current)
        p.is_playing_changed.connect(self._on_playing_changed)

    def _on_search(self, query: str) -> None:
        if not query:
            return
        self._last_query = query
        self._show_results = True
        self._results = []
        self._refresh_list()
        self._player.search(query)

    def _on_cleared(self) -> None:
        self._show_results = False
        self._results = []
        self._last_query = ""
        self._refresh_list()

    def _on_input_text_changed(self, text: str) -> None:
        if not text:
            self._on_cleared()

    def _on_search_busy(self, busy: bool) -> None:
        if busy:
            self._placeholder.setText("⟳  Searching YouTube Music…")
        elif self._show_results and not self._results:
            self._placeholder.setText("No tracks found.")
        else:
            self._placeholder.setText("Type a query and press Enter to search.")

    def _on_load_more_busy(self, busy: bool) -> None:
        self._load_more_btn.setText("Loading…" if busy else "+ Load more songs")
        self._load_more_btn.setEnabled(not busy)

    def _on_has_more(self, has_more: bool) -> None:
        self._load_more_btn.setVisible(
            has_more and self._show_results and len(self._results) >= 10
        )

    def _on_results(self, results: list) -> None:
        self._results = results
        self._show_results = True
        self._refresh_list()

    def _refresh_list(self) -> None:
        # Remove old rows
        for row in self._rows:
            self._list_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        has = self._show_results and bool(self._results)
        self._results_hdr.setVisible(has)
        self._scroll.setVisible(has)
        self._placeholder.setVisible(not has)
        self._load_more_btn.setVisible(
            has and len(self._results) >= 10 and self._player.has_more_search
        )

        if not has:
            return

        self._results_hdr.setText(f"RESULTS ({len(self._results)})")
        current_vid = self._player.current_song.get("videoId", "")
        is_playing  = self._player.is_playing

        for i, song in enumerate(self._results):
            is_current = bool(current_vid) and song.get("videoId") == current_vid
            row = _SearchRow(i, song, is_current, is_playing and is_current)
            row.play_clicked.connect(self._on_play)
            row.queue_clicked.connect(self._on_queue)
            row.play_next_clicked.connect(self._on_play_next)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._rows.append(row)

        max_h = min(S.sp(460), len(self._results) * S.sp(49))
        self._scroll.setFixedHeight(max_h)

    def _refresh_current(self, _=None) -> None:
        current_vid = self._player.current_song.get("videoId", "")
        is_playing  = self._player.is_playing
        for row in self._rows:
            is_c = bool(current_vid) and row.song.get("videoId") == current_vid
            row.set_current(is_c, is_playing and is_c)

    def _on_playing_changed(self, _=None) -> None:
        self._refresh_current()

    def _on_play(self, index: int) -> None:
        if 0 <= index < len(self._results):
            self._player.select_search_result(self._results[index])

    def _on_queue(self, index: int) -> None:
        if 0 <= index < len(self._results):
            self._player.queue_search_result(self._results[index])

    def _on_play_next(self, index: int) -> None:
        if 0 <= index < len(self._results):
            self._player.play_next_search_result(self._results[index])

    def _on_load_more(self) -> None:
        if self._last_query:
            self._player.load_more_search(self._last_query)

    def focus_search(self) -> None:
        self._input._input.setFocus()
        self._input._input.selectAll()
