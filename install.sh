#!/usr/bin/env bash
# ==============================================================================
# omusic installer — Rust Menu Bar Tray Applet
# Zero desktop application files. Pure drop-down tray.
# GitHub: https://github.com/n1dhruv/omusic
# ==============================================================================
set -e

export PATH="${HOME}/.cargo/bin:${HOME}/.local/bin:${PATH}"

BIN_DIR="${HOME}/.local/bin"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="${SYSTEMD_USER_DIR}/omusic.service"

C_RESET="\033[0m"
C_BOLD="\033[1m"
C_GREEN="\033[38;2;124;203;162m"
C_MINT="\033[38;2;165;229;191m"
C_DARK="\033[38;2;143;152;126m"
C_RED="\033[38;2;224;95;101m"

echo -e "${C_MINT}${C_BOLD}"
cat << "EOF"
  ___  _ __ ___  _   _ ___(_) ___ 
 / _ \| '_ ` _ \| | | / __| |/ __|
| (_) | | | | | | |_| \__ \ | (__ 
 \___/|_| |_| |_|\__,_|___/_|\___|
EOF
echo -e "${C_DARK}Cyber-Minimal YouTube Music Menu Bar Tray for Linux (Rust)${C_RESET}\n"

# 1. Dependency checks
echo -e "${C_BOLD}[1/3] Checking system dependencies...${C_RESET}"
MISSING_PKGS=()

need_cmd() {
    command -v "$1" >/dev/null 2>&1
}

if ! need_cmd mpv; then MISSING_PKGS+=("mpv"); fi
if ! need_cmd yt-dlp; then MISSING_PKGS+=("yt-dlp"); fi

if [[ ${#MISSING_PKGS[@]} -gt 0 ]]; then
    echo -e "${C_DARK}Installing missing packages: ${MISSING_PKGS[*]}${C_RESET}"
    if need_cmd pacman; then
        sudo pacman -S --needed --noconfirm "${MISSING_PKGS[@]}"
    elif need_cmd apt-get; then
        sudo apt-get update -y && sudo apt-get install -y "${MISSING_PKGS[@]}"
    elif need_cmd dnf; then
        sudo dnf install -y "${MISSING_PKGS[@]}"
    elif need_cmd zypper; then
        sudo zypper install -y "${MISSING_PKGS[@]}"
    fi
else
    echo -e "${C_GREEN}✔${C_RESET} All runtime dependencies present (mpv, yt-dlp)."
fi

# Detect if running from local repo or piped from curl
TMP_DIR=""
cleanup() {
    if [[ -n "${TMP_DIR}" && -d "${TMP_DIR}" ]]; then
        rm -rf "${TMP_DIR}"
    fi
}
trap cleanup EXIT

if [[ -f "Cargo.toml" && -d "src" ]]; then
    SRC_DIR="$(pwd)"
else
    TMP_DIR="$(mktemp -d -t omusic-install-XXXXXX)"
    echo -e "${C_DARK}Fetching omusic from GitHub...${C_RESET}"
    git clone --depth=1 "https://github.com/n1dhruv/omusic.git" "${TMP_DIR}"
    SRC_DIR="${TMP_DIR}"
fi

# 2. Binary Installation
echo -e "\n${C_BOLD}[2/3] Installing omusic binary...${C_RESET}"
mkdir -p "${BIN_DIR}"

# Stop any currently running instance so the file is not locked
systemctl --user stop omusic.service 2>/dev/null || true
pkill -9 -f "omusic" 2>/dev/null || true
sleep 0.5
rm -f "${BIN_DIR}/omusic"

if [[ -f "${SRC_DIR}/target/release/omusic" ]]; then
    install -m 755 "${SRC_DIR}/target/release/omusic" "${BIN_DIR}/omusic"
elif [[ -f "${SRC_DIR}/target/debug/omusic" ]]; then
    install -m 755 "${SRC_DIR}/target/debug/omusic" "${BIN_DIR}/omusic"
else
    echo -e "${C_DARK}Downloading pre-built release binary from GitHub...${C_RESET}"
    RELEASE_URL="https://github.com/n1dhruv/omusic/releases/latest/download/omusic-linux-x86_64.tar.gz"
    if curl -fsSL "${RELEASE_URL}" | tar --unlink-first -xz -C "${BIN_DIR}" 2>/dev/null; then
        chmod +x "${BIN_DIR}/omusic"
    elif need_cmd cargo; then
        echo -e "${C_DARK}Compiling release binary with Cargo...${C_RESET}"
        (cd "${SRC_DIR}" && cargo build --release)
        install -m 755 "${SRC_DIR}/target/release/omusic" "${BIN_DIR}/omusic"
    else
        echo -e "${C_RED}Error:${C_RESET} Failed to install omusic binary."
        exit 1
    fi
fi

# PURGE ANY OLD DESKTOP APPLICATION FILES (Ensures zero indexing in Rofi / GNOME / KDE)
rm -f "${HOME}/.local/share/applications/omusic.desktop"
rm -f "${HOME}/.config/autostart/omusic.desktop"

# 3. Systemd User Service (Background tray autostart without desktop files)
echo -e "\n${C_BOLD}[3/3] Configuring menu bar tray service...${C_RESET}"
mkdir -p "${SYSTEMD_USER_DIR}"

cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=omusic — YouTube Music Menu Bar Drop-Down Tray Applet
After=graphical-session.target

[Service]
ExecStart=${BIN_DIR}/omusic
Restart=on-failure
RestartSec=2
Environment="PATH=${PATH}"

[Install]
WantedBy=graphical-session.target
EOF

# Ensure ~/.local/bin is in PATH
SHELL_CONFIG=""
if [[ -n "${ZSH_VERSION:-}" || "${SHELL:-}" == *"zsh"* ]]; then
    SHELL_CONFIG="${HOME}/.zshrc"
elif [[ -n "${BASH_VERSION:-}" || "${SHELL:-}" == *"bash"* ]]; then
    SHELL_CONFIG="${HOME}/.bashrc"
fi

if [[ ":$PATH:" != *":${BIN_DIR}:"* ]]; then
    if [[ -n "${SHELL_CONFIG}" && -f "${SHELL_CONFIG}" ]]; then
        if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "${SHELL_CONFIG}"; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "${SHELL_CONFIG}"
        fi
    fi
fi

# Enable and start systemd user service
systemctl --user daemon-reload
systemctl --user enable --now omusic.service

echo -e "\n${C_MINT}${C_BOLD}✔ omusic is now active in your menu bar!${C_RESET}"
echo -e "${C_DARK}Look at your top menu bar / system tray. Click the icon to drop down the player.${C_RESET}"
echo -e "${C_DARK}Zero desktop application files installed — it lives exclusively in the menu bar.${C_RESET}"
