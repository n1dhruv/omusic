#!/usr/bin/env bash
# ==============================================================================
# omusic uninstaller — safe cleanup script
# ==============================================================================
set -e

INSTALL_DIR="${HOME}/.local/share/omusic"
BIN_FILE="${HOME}/.local/bin/omusic"
DESKTOP_FILE="${HOME}/.local/share/applications/omusic.desktop"
ICON_FILE="${HOME}/.local/share/icons/hicolor/scalable/apps/omusic.svg"

# Close any running instances
pkill -f "omusic/app/main.py" 2>/dev/null || true

# Remove files
rm -rf "${INSTALL_DIR}"
rm -f "${BIN_FILE}" "${DESKTOP_FILE}" "${ICON_FILE}"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${HOME}/.local/share/applications" >/dev/null 2>&1 || true
fi

echo "✔ omusic has been completely removed from your system."
