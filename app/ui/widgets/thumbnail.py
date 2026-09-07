"""
thumbnail.py — Async thumbnail loader with rounded corners.
"""
from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import Qt, QUrl, QSize
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPixmap, QFont
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtWidgets import QWidget

from app.style import SURFACE, TEXT_MUT, ACCENT, sp

_nam: Optional[QNetworkAccessManager] = None

def _get_nam() -> QNetworkAccessManager:
    global _nam
    if _nam is None:
        _nam = QNetworkAccessManager()
    return _nam


class ThumbnailWidget(QWidget):
    """Async thumbnail with rounded corners and nerd-font fallback icon."""

    def __init__(self, size: int = 34, radius: int = 6, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._sz = size
        self._radius = radius
        self._pixmap: Optional[QPixmap] = None
        self._url: str = ""
        self._reply: Optional[QNetworkReply] = None
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_url(self, url: str) -> None:
        if url == self._url:
            return
        self._url = url
        self._pixmap = None
        if self._reply:
            self._reply.abort()
            self._reply = None
        self.update()
        if not url:
            return
        req = QNetworkRequest(QUrl(url))
        req.setAttribute(QNetworkRequest.Attribute.CacheLoadControlAttribute, 0)
        self._reply = _get_nam().get(req)
        self._reply.finished.connect(self._on_finished)

    def _on_finished(self) -> None:
        reply = self._reply
        if reply is None:
            return
        self._reply = None
        if reply.error() != QNetworkReply.NetworkError.NoError:
            reply.deleteLater()
            return
        data = bytes(reply.readAll())
        reply.deleteLater()
        px = QPixmap()
        if not px.loadFromData(data):
            return
        # Scale to fill, then crop to exact size
        px = px.scaled(
            self._sz, self._sz,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        if px.width() > self._sz or px.height() > self._sz:
            x = (px.width()  - self._sz) // 2
            y = (px.height() - self._sz) // 2
            px = px.copy(x, y, self._sz, self._sz)
        self._pixmap = px
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self._sz, self._sz, self._radius, self._radius)
        p.setClipPath(path)

        if self._pixmap:
            p.drawPixmap(0, 0, self._pixmap)
        else:
            p.fillPath(path, SURFACE)
            # Fallback icon
            p.setPen(TEXT_MUT)
            icon_size = max(10, self._sz // 2)
            font = QFont()
            font.setPixelSize(icon_size)
            p.setFont(font)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, '\U000f05c3')
        p.end()
