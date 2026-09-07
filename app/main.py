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
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter, QPainterPath, QPen, QBrush
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

SOCKET_NAME = f"omusic-{os.getuid()}"


def _make_tray_icon(is_playing: bool = False) -> QIcon:
    """Create a sleek 24x24 tray icon matching the cyber-emerald palette."""
    px = QPixmap(24, 24)
    px.fill(Qt.GlobalColor.transparent)
    from app import style as S
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Outer squircle
    bg_color = S.SURF_ACTIVE if is_playing else S.SURFACE
    border_color = S.ACCENT_BRT if is_playing else S.BORDER
    path = QPainterPath()
    path.addRoundedRect(1, 1, 22, 22, 6, 6)
    p.fillPath(path, bg_color)
    p.setPen(QPen(border_color, 1))
    p.drawPath(path)

    # YouTube Music style play triangle / note inside
    accent_color = S.ACCENT_BRT if is_playing else S.TEXT_SEC
    p.setPen(accent_color)
    p.setBrush(accent_color)
    tri = QPainterPath()
    tri.moveTo(9, 7)
    tri.lineTo(17, 12)
    tri.lineTo(9, 17)
    tri.closeSubpath()
    p.drawPath(tri)

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
    app.setQuitOnLastWindowClosed(False)  # Pure menubar applet — stay alive in tray

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

    # System tray (Menu bar applet)
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(_make_tray_icon(False), app)
        tray.setToolTip("YouTube Music · Menu Bar")

        menu = QMenu()
        menu.setStyleSheet(
            f"QMenu {{ background: {S.hex_(S.SURFACE)}; color: {S.hex_(S.TEXT_PRI)};"
            f"border: 1px solid {S.rgba_(S.BORDER)}; border-radius: 6px; padding: 4px; }}"
            f"QMenu::item:selected {{ background: {S.hex_(S.SURF_HOVER)}; color: {S.hex_(S.ACCENT_BRT)}; }}"
        )
        toggle_action = menu.addAction("Show / Hide Player")
        toggle_action.triggered.connect(lambda: window.toggle(tray.geometry() if tray else None))

        pp_action = menu.addAction("Play / Pause")
        pp_action.triggered.connect(player.play_pause)

        next_action = menu.addAction("Next Track")
        next_action.triggered.connect(player.next)

        prev_action = menu.addAction("Previous Track")
        prev_action.triggered.connect(player.previous)

        menu.addSeparator()
        quit_action = menu.addAction("Quit omusic")
        quit_action.triggered.connect(app.quit)
        tray.setContextMenu(menu)

        def _on_tray_activated(reason):
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                window.toggle(tray.geometry())

        tray.activated.connect(_on_tray_activated)

        # Update tray icon and tooltip dynamically when song or playback changes
        def _update_tray_state(*_):
            is_playing = player.is_playing
            tray.setIcon(_make_tray_icon(is_playing))
            song = player.current_song
            if is_playing and song.get("title"):
                title = song.get("title", "")
                artist = song.get("artist", "")
                tray.setToolTip(f"{title} — {artist}\nYouTube Music")
            else:
                tray.setToolTip("YouTube Music · Menu Bar")

        player.is_playing_changed.connect(_update_tray_state)
        player.current_index_changed.connect(_update_tray_state)

        tray.show()
    else:
        # Fallback if no system tray available
        window.open()

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
                        _dispatch(args[0].lower(), args[1:], player, window, tray)
                    else:
                        window.toggle(tray.geometry() if tray else None)
                except Exception:
                    window.toggle(tray.geometry() if tray else None)
            sock.disconnectFromServer()

        sock.readyRead.connect(_read_data)

    server.newConnection.connect(_on_new_connection)

    # Handle CLI commands if passed for first launch
    _handle_cli_args(sys.argv[1:], player, window, tray)

    sys.exit(app.exec())


def _handle_cli_args(args: list[str], player, window, tray=None) -> None:
    """Dispatch CLI subcommands immediately after app starts."""
    if not args:
        # Menubar applet default: stay silently in the menubar (tray), don't open popup on boot
        return

    cmd = args[0].lower()
    if cmd in ("--tray", "tray", "daemon"):
        # Explicit background tray mode
        return

    QTimer.singleShot(100, lambda: _dispatch(cmd, args[1:], player, window, tray))


def _dispatch(cmd: str, args: list[str], player, window, tray=None) -> None:
    t_geom = tray.geometry() if tray else None
    if cmd in ("show", "open"):
        window.open(t_geom)
    elif cmd == "hide":
        window.close_window()
    elif cmd == "toggle":
        window.toggle(t_geom)
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
