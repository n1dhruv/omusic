#!/usr/bin/env bash
# ==============================================================================
# omusic installer — universal Linux setup script
# Works on Arch, Debian, Ubuntu, Fedora, openSUSE, and any standard Linux.
# GitHub: https://github.com/n1dhruv/omusic
# ==============================================================================
set -e

REPO_URL="https://github.com/n1dhruv/omusic.git"
INSTALL_DIR="${HOME}/.local/share/omusic"
BIN_DIR="${HOME}/.local/bin"
DESKTOP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"

# Color helpers
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
echo -e "${C_DARK}Universal Cyber-Minimal YouTube Music for Linux${C_RESET}\n"

# 1. Detect environment & repo source
TMP_CLONE=""
if [[ -f "app/main.py" && -f "backend/backend.py" ]]; then
    echo -e "${C_GREEN}✔${C_RESET} Installing from local repository..."
    SRC_DIR="$(pwd)"
else
    echo -e "${C_GREEN}✔${C_RESET} Downloading omusic from GitHub..."
    TMP_CLONE="$(mktemp -d -t omusic-install-XXXXXX)"
    git clone --depth=1 "${REPO_URL}" "${TMP_CLONE}"
    SRC_DIR="${TMP_CLONE}"
fi

cleanup() {
    if [[ -n "${TMP_CLONE}" && -d "${TMP_CLONE}" ]]; then
        rm -rf "${TMP_CLONE}"
    fi
}
trap cleanup EXIT

# 2. Distro Package Installation
echo -e "\n${C_BOLD}[1/4] Checking system dependencies...${C_RESET}"
MISSING_PKGS=()

need_cmd() {
    command -v "$1" >/dev/null 2>&1
}

if ! need_cmd mpv; then MISSING_PKGS+=("mpv"); fi
if ! need_cmd yt-dlp; then MISSING_PKGS+=("yt-dlp"); fi
if ! need_cmd python3; then MISSING_PKGS+=("python3"); fi

if [[ ${#MISSING_PKGS[@]} -gt 0 ]]; then
    echo -e "${C_DARK}Missing packages: ${MISSING_PKGS[*]}${C_RESET}"
    if need_cmd pacman; then
        echo -e "${C_GREEN}→${C_RESET} Installing via pacman..."
        sudo pacman -S --needed --noconfirm "${MISSING_PKGS[@]}" python-pip git
    elif need_cmd apt-get; then
        echo -e "${C_GREEN}→${C_RESET} Installing via apt-get..."
        sudo apt-get update -y
        sudo apt-get install -y "${MISSING_PKGS[@]}" python3-pip python3-venv git
    elif need_cmd dnf; then
        echo -e "${C_GREEN}→${C_RESET} Installing via dnf..."
        sudo dnf install -y "${MISSING_PKGS[@]}" python3-pip git
    elif need_cmd zypper; then
        echo -e "${C_GREEN}→${C_RESET} Installing via zypper..."
        sudo zypper install -y "${MISSING_PKGS[@]}" python3-pip git
    else
        echo -e "${C_RED}Warning:${C_RESET} Unknown package manager. Please ensure mpv, yt-dlp, and python3-venv are installed."
    fi
else
    echo -e "${C_GREEN}✔${C_RESET} All system packages present."
fi

# 3. Copy files to ~/.local/share/omusic
echo -e "\n${C_BOLD}[2/4] Deploying application files...${C_RESET}"
mkdir -p "${INSTALL_DIR}"
rm -rf "${INSTALL_DIR}/app" "${INSTALL_DIR}/backend"
cp -r "${SRC_DIR}/app" "${INSTALL_DIR}/"
cp -r "${SRC_DIR}/backend" "${INSTALL_DIR}/"
cp "${SRC_DIR}/backend/backend.py" "${INSTALL_DIR}/backend.py"
chmod +x "${INSTALL_DIR}/backend.py"

# 4. Set up Python venv
echo -e "\n${C_BOLD}[3/4] Configuring Python environment with PyQt6...${C_RESET}"
if [[ ! -d "${INSTALL_DIR}/venv" ]]; then
    python3 -m venv "${INSTALL_DIR}/venv"
fi
"${INSTALL_DIR}/venv/bin/pip" install --quiet --upgrade pip
"${INSTALL_DIR}/venv/bin/pip" install --quiet -r "${INSTALL_DIR}/backend/requirements.txt"
echo -e "${C_GREEN}✔${C_RESET} Python dependencies installed."

# 5. Install launcher & desktop integration
echo -e "\n${C_BOLD}[4/4] Installing launcher and desktop shortcuts...${C_RESET}"
mkdir -p "${BIN_DIR}" "${DESKTOP_DIR}" "${ICON_DIR}"

cp "${SRC_DIR}/bin/omusic" "${BIN_DIR}/omusic"
chmod +x "${BIN_DIR}/omusic"

cp "${SRC_DIR}/desktop/omusic.desktop" "${DESKTOP_DIR}/omusic.desktop"
cp "${SRC_DIR}/desktop/omusic.svg" "${ICON_DIR}/omusic.svg"

if need_cmd update-desktop-database; then
    update-desktop-database "${DESKTOP_DIR}" >/dev/null 2>&1 || true
fi

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
            echo -e "${C_GREEN}✔${C_RESET} Added ~/.local/bin to PATH in ${SHELL_CONFIG}"
        fi
    fi
fi

echo -e "\n${C_MINT}${C_BOLD}✔ omusic successfully installed!${C_RESET}"
echo -e "${C_DARK}Run ${C_MINT}omusic${C_DARK} in your terminal or launch it from your application launcher.${C_RESET}"
echo -e "\n${C_BOLD}Keybindings & Commands:${C_RESET}"
echo -e "  ${C_MINT}omusic${C_RESET}             Open / toggle player"
echo -e "  ${C_MINT}omusic play-pause${C_RESET}  Toggle playback"
echo -e "  ${C_MINT}omusic next${C_RESET}        Next track"
echo -e "  ${C_MINT}omusic prev${C_RESET}        Previous track"
echo -e "  ${C_MINT}Space${C_RESET}              Play / Pause in window"
echo -e "  ${C_MINT}J / K${C_RESET}              Navigate queue"
echo -e "  ${C_MINT}/${C_RESET}                  Focus search bar"
