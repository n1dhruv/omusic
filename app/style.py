"""
style.py — Color palette & spacing constants for omusic.
Exact match to the QML color definitions in youtube-music.qml.
"""
from PyQt6.QtGui import QColor, QFont


# ---------------------------------------------------------------------------
# Color palette (exact hex match to QML)
# ---------------------------------------------------------------------------
BG           = QColor("#0b1511")
SURFACE      = QColor("#101d17")
SURF_HOVER   = QColor("#17271f")
SURF_ACTIVE  = QColor("#1c3228")
TEXT_PRI     = QColor("#e7e3c5")
TEXT_SEC     = QColor("#8f987e")
TEXT_MUT     = QColor("#5f6d61")
ACCENT       = QColor("#7ccba2")
ACCENT_BRT   = QColor("#a5e5bf")
URGENT       = QColor("#e05f65")

# Semi-transparent border colours (alpha=0..255)
BORDER      = QColor(165, 229, 191, 30)    # 0.12 alpha
BORDER_FOC  = QColor(165, 229, 191, 89)    # 0.35 alpha
BORDER_SUB  = QColor(165, 229, 191, 20)    # 0.08 alpha

# Playback glow overlay (for blurred backdrop)
GLOW_BG     = QColor(11, 21, 17, 180)      # #0b1511 @ 70%

# ---------------------------------------------------------------------------
# Hex helpers (for QSS strings)
# ---------------------------------------------------------------------------
def hex_(c: QColor) -> str:
    return c.name()


def rgba_(c: QColor) -> str:
    return f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha()})"


# ---------------------------------------------------------------------------
# Spacing — identity mapping; Qt handles HiDPI device pixel ratios.
# ---------------------------------------------------------------------------
def sp(px: int | float) -> int:
    return max(1, round(px))


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------
FONT_MONO = "monospace"
FONT_UI   = "sans-serif"   # overridden at runtime from system Nerd Font


def font(size: int, mono: bool = False, bold: bool = False) -> QFont:
    f = QFont(FONT_MONO if mono else FONT_UI)
    f.setPixelSize(sp(size))
    f.setBold(bold)
    return f


# ---------------------------------------------------------------------------
# Global stylesheet (base resets applied to QApplication)
# ---------------------------------------------------------------------------
BASE_QSS = f"""
QWidget {{
    background: transparent;
    color: {hex_(TEXT_PRI)};
    font-family: {FONT_UI};
    font-size: 13px;
    border: none;
    outline: none;
}}
QScrollBar:vertical {{
    width: 0px;
    background: transparent;
}}
QScrollBar::handle:vertical {{ background: transparent; }}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{ height: 0px; }}
QToolTip {{
    background: {hex_(SURFACE)};
    color: {hex_(TEXT_PRI)};
    border: 1px solid {rgba_(BORDER)};
    padding: 4px 8px;
    border-radius: 6px;
}}
"""
