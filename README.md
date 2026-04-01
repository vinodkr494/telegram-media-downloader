# Telegram Bulk Media Downloader

[![GitHub Release](https://img.shields.io/github/v/release/vinodkr494/telegram-media-downloader?style=flat-square)](https://github.com/vinodkr494/telegram-media-downloader/releases/latest)
[![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/vinodkr494/telegram-media-downloader/total?style=flat-square)](https://github.com/vinodkr494/telegram-media-downloader/releases)

🚀 **Bulk-download videos, images, PDFs, audio & more** from any Telegram channel or group. Features a **Premium PySide6 Dashboard** with high-performance analytics, **Global Queue Tracking** (Total progress % & Session usage), **Advanced Task Management** (Prioritize & Cancel), category browser, real-time search, parallel downloads, smart deduplication, speed limiter, proxy support, and desktop notifications.

---## ✨ What's New in v2.5.0 (UI Polish & QoL Overhaul)

### 🎨 Professional UI Refresh
Replaced legacy emoji-based navigation labels with **professional, high-quality icon assets**. Navigation is now cleaner, perfectly aligned, and uses HSL-tailored colors for better contrast in both Light and Dark modes.

### 📊 Global Queue Analytics
The new **Right-Aligned Status Bar** now tracks your entire session in real-time:
- **Total Progress %**: See the completion percentage of your entire download queue.
- **Session Usage**: Track exactly how much data (MB/GB) you've downloaded in the current session.
- **Unified Speed**: Real-time calculation of total throughput across all active tasks.

### ⚡ Advanced Task Management
Full control over your queue with dedicated buttons on every download card:
- 🗑 **Cancel / Remove**: Stop a task and remove it from the queue with a single click.
- ⬆ / ⬇ **Prioritize Tasks**: Reorder whole batches (cards) in the main queue to decide which entire group or channel downloads next.
- 📂 **Quick Access**: Double-click any card to instantly open its download folder.

### 🔔 Desktop Notifications & Tray Actions
- **Completion Alerts**: Receive a native Windows/macOS/Linux notification when a whole batch is finished.
- **Tray Context Menu**: Right-click the system icon to **Pause All** or **Resume All** without opening the window.

---

## Features

- 💎 **Premium Sidebar** — sleek, icon-based navigation with professional typography
- 📊 **Global Dashboard Status** — real-time session stats, total progress %, and combined speed
- 🔔 **Native Notifications** — system-level alerts when your downloads are ready
- 🖱 **Intuitive Gestures** — double-click cards to open folders; auto-focus search on open
- 🔄 **Queue Prioritization** — move entire download batches up or down to manage your queue
- 🔍 **Media Browser Search** — live filter bar to find any file by name instantly
- ✅ **Selection Counter** — "X of Y files selected" counter updates as you tick boxes
- 📥 **Empty State Screens** — friendly placeholders on Home and Downloads before any tasks are added
- 📂 **Media Browser** — category-based file browser (Media, Files, Music, Links, GIFs)
- ⚡ **Parallel Fetch** — all categories load simultaneously via `asyncio.gather` (~5x faster)
- 🔁 **Smart Deduplication** — skips already-downloaded files by name and size
- ⏸ **Concurrent Downloads** — configurable parallel streams with pause / resume support
- 📊 **Per-file Progress Bars** — live speed display (KB/s / MB/s) per file
- **Speed Limiter** — configurable max download speed in Settings
- **Proxy Support** — SOCKS4, SOCKS5, HTTP, and MTProto configuration
- **Theme Toggle** — Light and Dark mode with persistent session saving
- **Persistent Queue** — saves and restores on restart automatically
- **Cross-Platform** — standalone executables for Windows, Linux, and macOS

---

## Screenshots

<p align="center">
  <img src="screenshots/screenshot_v2.4.1/login-v2.4.1.png" width="400" alt="Login Screen">
  <img src="screenshots/screenshot_v2.4.1/otp-v2.4.1.png" width="400" alt="OTP Verification">
</p>

<p align="center">
  <img src="screenshots/screenshot_v2.4.1/after_login_v2.4.1.png" width="800" alt="Home View">
</p>

---

## Requirements

- Python 3.8+
- Telegram API credentials (API ID and API Hash)

---

## Installation

### Method 1: Download the Executable (Recommended)

1. Go to the [Releases](https://github.com/vinodkr494/telegram-media-downloader/releases) page.
2. Download the latest `TGDownloader-vX.X.X-Windows.exe` (or your OS version).
3. Run directly — no Python or installation required!

> **Note:** Windows may show a "Smart App Control" warning because the executable is unsigned. Click **More info → Run anyway**.

### Method 2: Run from Source

1. Clone the repository:

    ```bash
    git clone https://github.com/vinodkr494/telegram-media-downloader.git
    cd telegram-media-downloader
    ```

2. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3. Create a `.env` file:

    ```env
    API_ID=your_api_id
    API_HASH=your_api_hash
    SESSION_NAME=default_session
    ```

4. Run the GUI:
    ```bash
    python src/gui.py
    ```

## Usage

1. **Log in** with your Telegram API credentials and phone number.
2. On the **Home** tab, enter a channel username (e.g. `@channelname`) or channel ID (e.g. `-100123456789`).
3. Click **🔍 Fetch Media** to open the **Media Browser**.
4. Browse files by category — use **Select All** or check individual files.
5. Click **Download Selected** to add them to your queue.
6. Track live progress, total queue stats, and session throughput in the **Downloads** tab.

### Resuming Downloads

Progress is saved automatically. Restart the app and your queue resumes seamlessly, skipping already-completed files.

### Configure Concurrent Downloads

Go to **Settings → Download Limit** to adjust how many files download simultaneously (default: 5).

---

## Changelog

### v2.5.0
- 🎨 **UI Overhaul** — replaced legacy emoji-based navigation with professional, high-quality icon assets and refined QSS typography.
- 📊 **Global Analytics** — introduced real-time session data, total completion %, and consolidated status bar metrics.
- ⚡ **Queue Mastery** — added Cancel (Remove) and Prioritize (Up/Down) functionality to the download cards.
- 🔔 **Native Feedback** — implemented desktop notifications for task completion and an enhanced tray context menu.
- 🖱 **Ddouble-Click Gestures** — double-click task cards to jump directly to the download folder.
- 🔍 **Search Focus** — auto-focuses the search bar upon opening the Media Browser for faster filtering.

### v2.4.7
- 💾 **Robust Persistence** — centralized all persistent files (`.env`, `config.json`, `download_state.json`, `active_tasks.json`, and `.session`) fixing persistence issues in standalone builds.
- 🌓 **Improved .env Logic** — added automatic quote stripping for `API_ID` and `API_HASH` and persisted `PHONE` for a seamless login experience.
- 🛡️ **Path Resolver Sync** — ensured all UI components and background workers use the centralized `get_project_root` helper.
MainWindow, SettingsView, LoginView) and background workers to use the new centralized `get_project_root` helper.

### v2.4.6

### v2.4.5
- ⏯️ **Pause Reliability** — implemented active task tracking to prevent duplicate background threads; clicking "Pause" now reliably stops all activity for that task immediately
- 📐 **Sidebar Polish** — reduced layout margins and button margins to ensure "Light Mode" and "Dark Mode" labels fit within the 85px sidebar on all displays
- 💾 **Persistent Resume** — fixed a state-management bug that caused paused tasks to auto-resume unexpectedly after a restart

### v2.4.4
- 🔗 **Invite-Link Download Fix** — fixed `FileReferenceExpiredError` for private channels joined via invite links by manually refreshing the message entity on retry
- 🌓 **Cross-Platform Dark Mode Detection** — app now auto-detects OS dark mode at startup (Windows registry, macOS `defaults`, Linux `gsettings`/`$GTK_THEME`)
- 🎨 **Startup Theme Fix** — eliminated black flash on Windows Dark Mode; sidebar toggle button now syncs to the detected theme on launch
- 💾 **Theme Persistence** — user's chosen theme is saved to `config.json` and restored on next launch, overriding the system default

### v2.4.3
- 🆔 **Robust Numeric IDs** — aggressively normalizes private channel numeric IDs (automatically applying `-100` prefixes) to prevent `PeerUser` fetch errors
- 📦 **Deep Dialog Scanning** — automatically requests and searches all `Archived` dialogs if a private channel ID isn't found in the active chat list
- 🛑 **Error Diagnostics** — updated MainWindow status tracking to avoid getting stuck "Fetching..." forever when an ID lookup fundamentally fails

### v2.4.2
- 🎭 **Premium Card UI** — implemented a sleek card-based layout for the media browser tabs
- 💾 **Persistent Themes** — fixed theme restoration bug, ensuring light/dark mode sticks across sessions
- 🧹 **UI Cleanup** — refined empty state logic and dynamic visibility of queue controls
- 🐞 **General Fixes** — resolved several minor layout and focus issues for a more stable experience

### v2.4.1
- 🚀 **Full PySide6 Rewrite** — migrated from CustomTkinter for native performance
- 🏗️ **Modular UI** — sidebar navigation with dedicated views (Home, Queue, Settings)
- 🌑 **Premium Theming** — full QSS-based Light/Dark mode support
- 🔒 **Enhanced Auth** — multi-step Phone/OTP/2FA login flow
- 📊 **Improved Queue** — per-task download cards with robust pause/resume/cancel
- 📁 **Modular Workers** — thread-safe `TelegramWorker` for background operations
- ⚙️ **Config Persistence** — settings now save to `config.json` automatically

### v2.3.0
- ✅ Animated braille spinner on the Fetch Media overlay
- ✅ Real-time search/filter bar inside every Media Browser tab
- ✅ Live `"X of Y files selected"` counter (turns green when files are selected)
- ✅ Toast notification on download queue completion (bottom-right, 3s auto-dismiss)
- ✅ Empty state screens for Home and Downloads views on fresh launch
- ✅ Fixed `Download Selected` modal not closing (tuple unpacking bug from v2.3 refactor)
- ✅ Updated About screen with v2.3 features and responsible-use warning
- ✅ Full `CONTRIBUTING.md` with setup guide, architecture, and PR checklist
- ✅ Legal Disclaimer added to README

### v2.2.0
- ✅ Added **Media Browser** with category tabs (Media, Files, Music, Links, GIFs)
- ✅ Parallel category fetching with `asyncio.gather` (~5x faster)
- ✅ Per-file **deduplication** (skip existing files at correct size)
- ✅ **Speed Limiter** slider in Settings
- ✅ Fixed phantom pause bug (`asyncio.CancelledError` in progress callback)
- ✅ Fixed `sqlite3 database is locked` crash on download start
- ✅ Fixed `Select All` not properly queuing files for download
- ✅ Fixed UI freeze caused by progress event flooding

### v2.1.0
- ✅ Proxy support (SOCKS4/5, HTTP, MTProto)
- ✅ Dark/Light theme toggle
- ✅ Persistent download queue across restarts

### v2.0.0
- ✅ Complete UI rewrite — modern CustomTkinter dashboard
- ✅ Sidebar navigation, download cards, per-file progress bars
- ✅ `cryptg` hardware acceleration for fast Telegram downloads

## Roadmap

Future improvements are tracked as [GitHub Issues](https://github.com/vinodkr494/telegram-media-downloader/issues). Have an idea? Open a feature request!

## ⚠️ Legal Disclaimer

> [!CAUTION]
> **This tool is intended for personal and legitimate use only.**
>
> - Only download content from channels and groups **you own or have explicit permission to access**.
> - Respect Telegram's [Terms of Service](https://telegram.org/tos) at all times.
> - Do **not** use this tool to infringe copyright, redistribute paid content, or violate anyone's privacy.
> - The author and contributors are **not responsible** for any misuse, damages, or legal consequences arising from the use of this software.
> - Use entirely at your own risk.

This software interacts with Telegram's official API via [Telethon](https://github.com/LonamiWebs/Telethon). It does not bypass any Telegram security mechanisms.

---

## Contributing

We welcome contributions of all kinds! Please read the [CONTRIBUTING.md](CONTRIBUTING.md) file for the full guide including:
- Environment setup
- Project architecture
- Commit message conventions
- PR checklist
- Areas that need help

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Telethon](https://github.com/LonamiWebs/Telethon) — Telegram API integration
- [PySide6](https://pypi.org/project/PySide6/) — Native Python bindings for Qt WebEngine/Widgets
- [cryptg](https://github.com/LonamiWebs/cryptg) — C-based crypto for fast downloads
- [Pillow](https://python-pillow.org/) — Image processing

## 🌟 About The Project

**Telegram Bulk Media Downloader** is a high-performance, open-source initiative dedicated to providing a premium, desktop-native solution for archiving and managing Telegram content. 

Our mission is to bridge the gap between complex terminal-based downloaders and the user-friendly experience that modern creators and researchers deserve. By combining the robust [Telethon](https://github.com/LonamiWebs/Telethon) engine with a world-class **PySide6 Dashboard**, we've created a tool that is both incredibly powerful and effortless to use.

---

Made with ❤️ by [Vinod Kumar](https://github.com/vinodkr494).
