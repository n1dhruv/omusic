# omusic

<p align="center">
  <img src="desktop/omusic.svg" width="96" height="96" alt="omusic logo" />
</p>

<p align="center">
  <b>A cyber-minimal YouTube Music Menu Bar Applet for Linux.</b><br>
  Sits seamlessly in your top menu bar / system tray. Click to drop down the player.<br>
  Works natively across <b>Arch, Debian, Ubuntu, Fedora, openSUSE</b>, and any modern Linux distribution.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Linux-7ccba2?style=flat-square" alt="Platform Linux" />
  <img src="https://img.shields.io/badge/toolkit-PyQt6-a5e5bf?style=flat-square" alt="PyQt6" />
  <img src="https://img.shields.io/badge/license-MIT-7ccba2?style=flat-square" alt="License MIT" />
</p>

---

## ✨ Features

- 🎨 **Aesthetic Cyber-Dark UI** — Deep charcoal background with emerald & mint accents (`#0b1511` palette).
- 🖼️ **Ambient Album Art Glow** — Dynamic backdrop glow subtly reflecting the currently playing track.
- ⚡ **Ultra-Fast Search & Pagination** — Instant YouTube Music search with "Load more" streaming results.
- 📻 **Auto-Radio Playlist** — Automatically cues related songs based on your selection.
- 🎚️ **Interactive Drag & Drop Queue** — Reorder tracks by grabbing the right-hand grip handle with edge auto-scrolling at 60 FPS.
- 📜 **Silky Smooth Scrollbar** — Hover-expanding reactive scrollbar with 2-finger touchpad gestures.
- 🪟 **Collapsible Mini-Player Mode** — Drop down to a sleek 76px compact bar whenever you need screen space.
- ⌨️ **Vim-Style & Command Keybindings** — Total keyboard navigability.
- 🚀 **Instant CLI & IPC Control** — Single-instance architecture with hotkey support (`omusic toggle`, `omusic next`, etc.).

---

## 📦 Quick Installation

### Universal 1-Line Installer (Recommended)
Open your terminal and run:

```bash
curl -fsSL https://raw.githubusercontent.com/n1dhruv/omusic/main/install.sh | bash
```

The script automatically detects your distribution (Arch, Debian, Ubuntu, Fedora), installs system requirements (`mpv`, `yt-dlp`), sets up an isolated Python venv with PyQt6, creates the launcher at `~/.local/bin/omusic`, and integrates your desktop application menu.

---

### Manual Installation (From Source)

```bash
# 1. Clone the repository
git clone https://github.com/n1dhruv/omusic.git
cd omusic

# 2. Run the installer
chmod +x install.sh
./install.sh
```

---

## 🎮 Usage & CLI Control

You can launch `omusic` from your application runner (Rofi, Wofi, GNOME, KDE) or via terminal:

```bash
omusic               # Launch or toggle player window
```

### Hotkey & Media Control Commands

Bind these to your favorite window manager keys (e.g., Hyprland, Sway, i3):

| Command | Action |
|:---|:---|
| `omusic` or `omusic toggle` | Toggle the player window (open / hide) |
| `omusic play-pause` | Toggle play / pause |
| `omusic next` | Skip to next track |
| `omusic prev` | Go to previous track |
| `omusic mute` | Toggle mute |
| `omusic shuffle` | Toggle shuffle mode |
| `omusic repeat` | Toggle repeat mode |
| `omusic volume 80` | Set volume level (0-100) |
| `omusic quit` | Close background player |

---

## ⌨️ In-App Keyboard Shortcuts

When the player window is active:

| Key | Action |
|:---|:---|
| <kbd>Space</kbd> | Play / Pause |
| <kbd>/</kbd> | Focus search input |
| <kbd>J</kbd> or <kbd>↓</kbd> | Navigate down through queue |
| <kbd>K</kbd> or <kbd>↑</kbd> | Navigate up through queue |
| <kbd>Enter</kbd> | Play selected track |
| <kbd>N</kbd> | Next song |
| <kbd>P</kbd> | Previous song |
| <kbd>S</kbd> | Toggle shuffle |
| <kbd>R</kbd> | Toggle repeat |
| <kbd>M</kbd> | Toggle mute |
| <kbd>Esc</kbd> | Unfocus search / Close player |

---

## 🖥️ Window Manager Integration

### Hyprland (`~/.config/hypr/hyprland.conf`)
```ini
# Toggle omusic window with Super + M
bind = $mainMod, M, exec, omusic toggle

# Media control keys
bindl = , XF86AudioPlay, exec, omusic play-pause
bindl = , XF86AudioNext, exec, omusic next
bindl = , XF86AudioPrev, exec, omusic prev
```

### i3 / Sway (`~/.config/i3/config`)
```ini
bindsym $mod+m exec omusic toggle
bindsym XF86AudioPlay exec omusic play-pause
bindsym XF86AudioNext exec omusic next
bindsym XF86AudioPrev exec omusic prev
```

---

## 🗑️ Uninstallation

To cleanly remove `omusic`:

```bash
cd omusic && ./uninstall.sh
# OR manually:
rm -rf ~/.local/share/omusic ~/.local/bin/omusic ~/.local/share/applications/omusic.desktop
```

---

## 📄 License

Distributed under the [MIT License](LICENSE). Built with Python 3, PyQt6, and mpv.
Made with ❤️ by [Dhruv](https://github.com/n1dhruv).
