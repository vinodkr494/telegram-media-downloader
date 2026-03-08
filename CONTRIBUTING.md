# Contributing to Telegram Bulk Media Downloader

Thank you for your interest in contributing! This project is open-source and welcomes contributions of all kinds — bug fixes, new features, documentation, translations, or any improvements that make the tool better.

---

## ⚠️ Code of Conduct

By contributing, you agree to:
- Respect Telegram's Terms of Service
- Not submit code that enables unauthorized access, spamming, or copyright infringement
- Treat all contributors respectfully

---

## 🚀 Getting Started

### 1. Fork and Clone

```bash
git clone https://github.com/vinodkr494/telegram-media-downloader.git
cd telegram-media-downloader
```

### 2. Set up the Environment

```bash
# Create a virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure your credentials

Create a `.env` file in the project root:

```env
API_ID=your_api_id
API_HASH=your_api_hash
SESSION_NAME=dev_session
```

Get your API credentials at [my.telegram.org](https://my.telegram.org).

### 4. Run the App

```bash
python src/gui.py
```

---

## 🗂️ Project Structure

```
telegram-media-downloader/
├── src/
│   ├── gui.py              # Main application window and all UI
│   ├── core_downloader.py  # Download logic, Telethon wrappers, batching
│   └── assets/             # Icons, logo
├── requirements.txt
├── .env                    # API credentials (gitignored)
├── README.md
└── CONTRIBUTING.md
```

| File | Purpose |
|------|---------|
| `gui.py` | All CustomTkinter UI, navigation, modals, and task management |
| `core_downloader.py` | All async Telethon logic: fetch channel, get messages, batch download |

---

## 🐛 Reporting Bugs

1. Check [existing issues](https://github.com/vinodkr494/telegram-media-downloader/issues) first
2. Open a new issue using the **Bug Report** template
3. Include:
   - OS and Python version
   - Steps to reproduce
   - Full error traceback (from terminal)
   - Expected vs. actual behavior

---

## 💡 Suggesting Features

1. Open a [Feature Request](https://github.com/vinodkr494/telegram-media-downloader/issues/new) issue
2. Describe the use case and why it would benefit other users
3. If you want to build it yourself, comment on the issue first so we can coordinate

---

## 🔧 Making Changes

### Branch Naming

| Type | Example |
|------|---------|
| Feature | `feat/search-filter` |
| Bug fix | `fix/modal-not-closing` |
| Docs | `docs/update-contributing` |
| Refactor | `refactor/download-batch` |

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add real-time search filter in Media Browser
fix: modal not closing after clicking Download Selected
docs: update CONTRIBUTING with project structure
refactor: replace raise CancelledError with flag in progress callback
```

### Pull Request Checklist

Before opening a PR, make sure:

- [ ] Your code runs without errors (`python src/gui.py`)
- [ ] You have tested the feature/fix manually
- [ ] You have not committed `.env`, `.session`, or `active_tasks.json`
- [ ] Your changes work on both Light and Dark mode
- [ ] The PR description explains what and why

---

## 🧱 Architecture Notes

### Threading Model

The app runs two execution contexts:
- **Tkinter main thread** — all UI updates (`self.after(0, ...)` for thread-safe callbacks)
- **Background asyncio loop** — all Telethon network calls (`asyncio.run_coroutine_threadsafe(...)`)

> ⚠️ Never call Telethon methods directly from the Tkinter thread. Always use `asyncio.run_coroutine_threadsafe(coro, self.loop)`.

### Download Pipeline

```
on_fetch_media_start()
  └─ run_fetch_media_thread()           # background thread
       └─ async_fetch_media_flow()      # async, runs on self.loop
            ├─ fetch_channel()
            ├─ fetch_categorized_media() # parallel asyncio.gather
            └─ show_media_browser_modal() → user selects files
                 └─ run_async_download_selected()
                      └─ async_download_selected_flow()
                           └─ download_in_batches_headless()
                                └─ download_single_file()
```

---

## 📋 Areas That Need Help

| Area | Description |
|------|-------------|
| 🌐 i18n | Make the UI translatable |
| 🧪 Tests | Add automated tests for `core_downloader.py` |
| 🏎️ Performance | Improve large-channel (10,000+ messages) handling |
| 🖥️ macOS / Linux | Test and fix platform-specific UI quirks |
| 📄 Docs | Improve setup guides and add wiki pages |

---

## 📄 License

By contributing, you agree that your code will be licensed under the [MIT License](LICENSE).

---

Made with ❤️ by [Vinod Kumar](https://github.com/vinodkr494). Contributions welcome!
