"""
equalizer.py — Animated 3-bar equalizer indicator.
Matches the SequentialAnimation bounce in the original QML.
"""
from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import (
    Qt, QTimer, QEasingCurve, QVariantAnimation, QAbstractAnimation
)
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QWidget

from app.style import ACCENT_BRT, sp


class EqualizerWidget(QWidget):
    """
    Three bars bouncing between min and max heights.
    Durations: 410ms, 560ms, 470ms (matching QML).
    When not playing, bars sit at their minimum height.
    """

    _BARS = [
        (sp(3), sp(11), 410),
        (sp(5), sp(12), 560),
        (sp(2), sp(9),  470),
    ]
    _BAR_W  = sp(2)
    _GAP    = sp(2)
    _RADIUS = 1

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        total_w = len(self._BARS) * self._BAR_W + (len(self._BARS) - 1) * self._GAP
        total_h = max(m for _, m, _ in self._BARS)
        self.setFixedSize(total_w, total_h)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._heights = [b[0] for b in self._BARS]  # current heights
        self._anims: list[QVariantAnimation] = []
        self._playing = False

        for i, (min_h, max_h, dur) in enumerate(self._BARS):
            anim = QVariantAnimation(self)
            anim.setDuration(dur)
            anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            anim.setLoopCount(-1)  # infinite handled manually via direction flip
            # We'll do sequential bounce manually via finished signal
            anim.setStartValue(float(min_h))
            anim.setEndValue(float(max_h))
            idx = i
            anim.valueChanged.connect(lambda v, i=idx: self._on_value(i, v))
            anim.finished.connect(lambda a=anim: self._on_bar_finished(a))
            self._anims.append(anim)

    def _on_value(self, i: int, v: float) -> None:
        self._heights[i] = int(v)
        self.update()

    def _on_bar_finished(self, anim: QVariantAnimation) -> None:
        if not self._playing:
            return
        # Flip direction
        sv = anim.startValue()
        ev = anim.endValue()
        anim.setStartValue(ev)
        anim.setEndValue(sv)
        anim.setLoopCount(1)
        anim.start()

    def set_playing(self, playing: bool) -> None:
        if playing == self._playing:
            return
        self._playing = playing
        if playing:
            for i, (min_h, max_h, dur) in enumerate(self._BARS):
                a = self._anims[i]
                a.setStartValue(float(self._heights[i]))
                a.setEndValue(float(max_h))
                a.setLoopCount(1)
                a.start()
        else:
            for anim in self._anims:
                anim.stop()
            for i, (min_h, _, _) in enumerate(self._BARS):
                self._heights[i] = min_h
            self.update()

    def paintEvent(self, _event) -> None:
        from PyQt6.QtCore import Qt
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        total_h = self.height()
        x = 0
        for i, h in enumerate(self._heights):
            y = total_h - h
            p.fillRect(x, y, self._BAR_W, h, ACCENT_BRT)
            x += self._BAR_W + self._GAP
        p.end()
