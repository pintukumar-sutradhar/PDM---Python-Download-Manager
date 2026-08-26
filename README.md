<div align="center">

<img src="assets/banner.png" alt="PDM — Python Download Manager" width="100%"/>

# PDM — Python Download Manager

**One desktop app for every download.** Videos, playlists, torrents, direct files and live streams —
PDM picks the right engine automatically and gets out of your way.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Qt](https://img.shields.io/badge/Qt-6%20%2F%20PySide6-41CD52?style=flat-square&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-4c5670?style=flat-square)](#-installation)
[![License](https://img.shields.io/badge/License-MIT-3b82f6?style=flat-square)](LICENSE)

[Features](#-features) · [Installation](#-installation) · [Usage](#-usage) · [Contributing](#-contributing) · [Legal](#-legal-notice)

</div>

---

## Why PDM?

Most download tools do one thing. PDM routes **every** link you throw at it through the engine
that handles it best — automatically:

| You paste… | What happens |
|---|---|
| Video / social media links | Scanned, formats listed, best quality picked — with a visual format picker |
| `magnet:` or `.torrent` | Multi-peer torrent engine with live piece progress |
| Stream pages (`.m3u8` / `.mpd`) | Stream harvesting + a dedicated segmented-stream downloader |
| Plain file URLs | Multi-segment accelerator with resume + integrity checks |
| Sign-in-only sites | The site opens inside PDM — log in once, the session is remembered |

No per-site configuration. One queue, one library.

## ✨ Features

### 🚀 Transfer Engine
- **Multi-segment HTTP(S) accelerator** — parallel byte-range connections, pause/resume, automatic fallback to single-stream, and a byte-integrity gate before anything is marked complete
- **Queue with concurrency limits**, per-download speed caps, retry with backoff
- **Trash-soft delete** — nothing disappears until you empty it

### 🎬 Smart Media Handling
- **Visual format picker** — resolution × fps × codec × size, all in one table
- **Smart naming** — resolution, codec and source baked into clean filenames
- **Audio extraction** to MP3 with one toggle

### 📡 Streams & OTT
- **Stream harvesting** — PDM finds playable `.m3u8` / `.mpd` / `.mp4` payloads hidden in pages, JSON blobs and app bundles
- **Dedicated segmented-stream downloader** with referer/session passthrough, installed automatically by the bootstrap scripts
- **Built-in site login** — sign-in-required sites open inside PDM's own browser; log in once and the session is remembered for scanning and downloading
- **Play-and-catch** — while signed in, any non-encrypted stream the site's player generates appears in a one-click list
- Login-wall and DRM detection with clear messaging — PDM tells you *why* something can't be fetched instead of failing silently

### 🌊 BitTorrent
- Magnet + `.torrent`, sequential or rarest-first, piece-level progress
- Live two-way sync between the Torrents view and your main library
- Metadata-aware renaming once peers resolve the real file name

### ⚙️ Desktop App Polish
- **Landing page** — paste a link straight from the dashboard; live stats, resume-all for paused/failed items and recent activity at a glance
- 14 themes including 12 hand-tuned color schemes, light + dark
- System tray, global shortcuts, clipboard watching, download history
- SQLite storage in **WAL mode** — crash-safe, concurrent-safe

## 📸 Screenshots

<div align="center">
<table>
<tr>
<td align="center" width="50%"><img src="assets/screenshots/home.png" alt="Home dashboard"/><br/><sub><b>Home — paste a link, everything auto-routed</b></sub></td>
<td align="center" width="50%"><img src="assets/screenshots/main_window.png" alt="Download library"/><br/><sub><b>Library — live progress, speed, ETA</b></sub></td>
</tr>
<tr>
<td align="center" width="50%"><img src="assets/screenshots/new_download.png" alt="Format picker"/><br/><sub><b>Format picker — resolution × fps × codec × size</b></sub></td>
<td align="center" width="50%"><img src="assets/screenshots/statistics.png" alt="Statistics"/><br/><sub><b>Bandwidth statistics</b></sub></td>
</tr>
</table>
<p><sub><i>More: <a href="assets/screenshots/add_url.png">scan dialog</a> · <a href="assets/screenshots/settings.png">settings (14 themes, proxy, speed limits)</a></i></sub></p>
</div>

## 🛠 Installation

### Option 1 — One command (recommended)

```bash
git clone https://github.com/pintukumar-sutradhar/PDM---Python-Download-Manager.git
cd PDM---Python-Download-Manager
./run.sh          # Linux — everything automatic
run.bat           # Windows — double-click or run in cmd
```

The bootstrap script prepares everything automatically and launches PDM. Nothing else to configure.

### Option 2 — Just run it

```bash
git clone https://github.com/pintukumar-sutradhar/PDM---Python-Download-Manager.git
cd PDM---Python-Download-Manager
python3 pdm.py
```

On first launch PDM installs its own dependencies automatically (creating a local environment if
your system Python requires one) and then starts. Subsequent launches open instantly.

**Requirements:** Python 3.10+. Everything else installs itself on first run.

## 🚀 Usage

1. **Paste anything** — a video link, a magnet, a stream page URL, a direct file
2. PDM scans it and shows exactly what it found (formats, streams, files)
3. If a site needs sign-in, log in inside PDM's built-in browser — once
4. Pick where to save; hit download
5. Watch progress in the library, or minimize to tray

<details>
<summary><b>⌨️ Keyboard shortcuts</b></summary>

| Shortcut | Action |
|---|---|
| `Ctrl+N` | New download |
| `Ctrl+R` / `Del` | Resume / move to trash selection |
| `Ctrl+Q` | Quit |

</details>

## 🤝 Contributing

PRs welcome — bug fixes, UI polish, new site support. Please open an issue first for large changes.

## 📄 License

[MIT](LICENSE) — free to use, modify and ship.

## ⚠️ Legal Notice

PDM is a download manager. It does **not** bypass DRM or break content protection, and the
authors do not endorse piracy. You are responsible for complying with the terms of service of
any site you download from and with your local laws. Download only what you have the right to
download.

<div align="center">
<sub>PDM — Python Download Manager</sub>
</div>
