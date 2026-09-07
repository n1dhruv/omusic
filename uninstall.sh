#!/usr/bin/env bash
# ==============================================================================
# omusic uninstaller — safe cleanup script
# ==============================================================================
set -e

# Stop and disable systemd user service
systemctl --user disable --now omusic.service 2>/dev/null || true
rm -f "${HOME}/.config/systemd/user/omusic.service"
systemctl --user daemon-reload 2>/dev/null || true

# Terminate processes
pkill -9 -f "omusic" 2>/dev/null || true
pkill -9 -f "omusic-mpv.sock" 2>/dev/null || true

# Remove binaries and any old files
rm -f "${HOME}/.local/bin/omusic"
rm -f "${HOME}/.local/share/applications/omusic.desktop"
rm -f "${HOME}/.config/autostart/omusic.desktop"
rm -f "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"/omusic*

echo "✔ omusic has been completely removed from your menu bar and system."
