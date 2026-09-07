# omusic

<p align="center">
  <img src="icons/tray.png" width="80" height="80" alt="omusic logo" />
</p>

<p align="center">
  <b>A cyber-minimal YouTube Music Menu Bar Drop-Down Tray Applet for Linux (Built in Rust).</b><br>
  Lives purely in your top menu bar / system tray. Zero desktop application files.<br>
  Works seamlessly across <b>Arch, Debian, Ubuntu, Fedora, openSUSE</b>, and modern window managers.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/language-Rust-orange?style=flat-square&logo=rust" alt="Rust" />
  <img src="https://img.shields.io/badge/platform-Linux-7ccba2?style=flat-square" alt="Platform Linux" />
  <img src="https://img.shields.io/badge/framework-Tauri_v2-a5e5bf?style=flat-square" alt="Tauri v2" />
  <img src="https://img.shields.io/badge/license-MIT-7ccba2?style=flat-square" alt="License MIT" />
</p>

---

## ✨ Why omusic?

- 🪟 **Zero Desktop Application Clutter** — Does **not** install `.desktop` files in your app launcher. Rofi, Wofi, GNOME, and KDE will never list it as an application. It lives purely in your menu bar.
- 🎯 **Drop-Down Tray Panel** — Clicking the menu bar icon drops down the player panel directly beneath it. Click outside to dismiss.
- 🛡️ **Linux Kernel Process Safety (`PR_SET_PDEATHSIG`)** — Built in Rust; `mpv` audio playback is tied directly to the parent process via Linux kernel `prctl`. Orphaned audio playback is physically impossible.
- 🎨 **Dark Cyber Aesthetic** — Signature `#0b1511` palette, glowing album artwork, bouncing equalizers, and mint accents (`#7ccba2`, `#a5e5bf`).
- 🎚️ **Interactive Drag & Drop Queue** — Reorder tracks via the right-hand grip handle (`󰇡`) with 60 FPS edge scrolling.
- 📜 **Silky Smooth Scrollbar** — Hover-expanding reactive scrollbar (3.5px → 6px).
- 🗕 **Collapsible Mini-Player Mode** — Drop down to a 76px compact bar whenever you need screen real estate.
- 🚀 **Systemd User Service Autostart** — Automatically starts on login in the background without user intervention.

---

## 📦 1-Line Universal Installation

To install `omusic` directly into your menu bar:

```bash
curl -fsSL https://raw.githubusercontent.com/n1dhruv/omusic/main/install.sh | bash
```

---

## 🎮 Controls

### Menu Bar Interaction
- **Click Tray Icon**: Drop down or dismiss the music player panel.
- **Right-Click Tray Icon**: Quick context menu (*Play / Pause*, *Quit omusic*).

### In-App Keybindings
| Key | Action |
|:---|:---|
| <kbd>Space</kbd> | Play / Pause |
| <kbd>/</kbd> | Focus search bar |
| <kbd>J</kbd> or <kbd>↓</kbd> | Next song in queue |
| <kbd>K</kbd> or <kbd>↑</kbd> | Previous song in queue |
| <kbd>S</kbd> | Toggle shuffle |
| <kbd>R</kbd> | Toggle repeat |
| <kbd>M</kbd> | Toggle mute |
| <kbd>Esc</kbd> | Dismiss dropdown window |

---

## 🗑️ Uninstallation

To cleanly remove `omusic`:

```bash
curl -fsSL https://raw.githubusercontent.com/n1dhruv/omusic/main/uninstall.sh | bash
```

---

## 📄 License

Distributed under the [MIT License](LICENSE). Built with ❤️ by [Dhruv](https://github.com/n1dhruv).
