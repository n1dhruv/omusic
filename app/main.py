"""
main.py — Entry point for omusic.

Creates the QApplication, system tray icon, Player, and YtMusicWindow.
The tray icon click toggles the window. The app stays running in the
system tray until the user quits from the tray menu.
"""
from __future__ import annotations
import sys
import os

# Ensure the omusic package root is on the path when running directly
_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

import json
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter, QPainterPath
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

SOCKET_NAME = f"omusic-{os.getuid()}"


def _make_tray_icon() -> QIcon:
    """Create a simple 22x22 tray icon (accent-colored music note)."""
    px = QPixmap(22, 22)
    px.fill(Qt.GlobalColor.transparent)
    from app import style as S
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Draw filled circle
    path = QPainterPath()
    path.addEllipse(1, 1, 20, 20)
    p.fillPath(path, S.ACCENT)
    # Draw music note character
    p.setPen(S.BG)
    from PyQt6.QtGui import QFont
    f = QFont()
    f.setPixelSize(14)
    p.setFont(f)
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "♪")
    p.end()
    return QIcon(px)


def main() -> None:
    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("omusic")
    app.setApplicationDisplayName("omusic")
    app.setQuitOnLastWindowClosed(False)  # Stay running in tray

    # Check if another instance is already running
    client_socket = QLocalSocket()
    client_socket.connectToServer(SOCKET_NAME)
    if client_socket.waitForConnected(300):
        # Connected to existing instance — send CLI args or "toggle"
        args = sys.argv[1:] if len(sys.argv) > 1 else ["toggle"]
        payload = json.dumps(args).encode("utf-8") + b"\n"
        client_socket.write(payload)
        client_socket.flush()
        client_socket.waitForBytesWritten(500)
        client_socket.disconnectFromServer()
        sys.exit(0)

    # We are the primary instance — start local server
    QLocalServer.removeServer(SOCKET_NAME)
    server = QLocalServer(app)
    server.listen(SOCKET_NAME)

    # Apply base stylesheet
    from app import style as S
    app.setStyleSheet(S.BASE_QSS)

    # Create player (central state)
    from app.player import Player
    player = Player()

    # Create main window
    from app.ui.window import YtMusicWindow
    window = YtMusicWindow(player)

    # Handle incoming IPC connections from subsequent CLI invocations
    def _on_new_connection():
        sock = server.nextPendingConnection()
        if not sock:
            return

        def _read_data():
            line = bytes(sock.readLine()).decode("utf-8").strip()
            if line:
                try:
                    args = json.loads(line)
                    if isinstance(args, list) and args:
                        _dispatch(args[0].lower(), args[1:], player, window)
                    else:
                        window.toggle()
                except Exception:
                    window.toggle()
            sock.disconnectFromServer()

        sock.readyRead.connect(_read_data)

    server.newConnection.connect(_on_new_connection)

    # System tray
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(_make_tray_icon(), app)
        tray.setToolTip("omusic")

        menu = QMenu()
        toggle_action = menu.addAction("Show / Hide")
        toggle_action.triggered.connect(window.toggle)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(app.quit)
        tray.setContextMenu(menu)

        tray.activated.connect(
            lambda reason: window.toggle()
            if reason == QSystemTrayIcon.ActivationReason.Trigger else None
        )
        tray.show()
    else:
        # No tray — just show the window directly
        window.open()

    # Handle CLI commands if passed for first launch
    _handle_cli_args(sys.argv[1:], player, window)

    sys.exit(app.exec())


def _handle_cli_args(args: list[str], player, window) -> None:
    """Dispatch CLI subcommands immediately after app starts."""
    if not args:
        # Default: open window centered
        QTimer.singleShot(100, window.open)
        return

    cmd = args[0].lower()
    QTimer.singleShot(100, lambda: _dispatch(cmd, args[1:], player, window))


def _dispatch(cmd: str, args: list[str], player, window) -> None:
    if cmd in ("show", "open"):
        window.open()
    elif cmd == "hide":
        window.close_window()
    elif cmd == "toggle":
        window.toggle()
    elif cmd in ("play-pause", "playpause", "pp"):
        player.play_pause()
    elif cmd == "next":
        player.next()
    elif cmd in ("prev", "previous"):
        player.previous()
    elif cmd == "mute":
        player.toggle_mute()
    elif cmd == "shuffle":
        player.toggle_shuffle()
    elif cmd == "repeat":
        player.toggle_repeat()
    elif cmd == "volume" and args:
        try:
            player.set_volume(float(args[0]))
        except ValueError:
            pass
    elif cmd in ("quit", "exit"):
        QApplication.quit()


if __name__ == "__main__":
    main()
