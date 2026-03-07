# Telegram Bulk Media Downloader

[![GitHub Release](https://img.shields.io/github/v/release/vinodkr494/telegram-media-downloader?style=flat-square)](https://github.com/vinodkr494/telegram-media-downloader/releases/latest)
[![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/vinodkr494/telegram-media-downloader/total?style=flat-square)](https://github.com/vinodkr494/telegram-media-downloader/releases)

Telegram Bulk Media Downloader is a Python-based tool that allows users to download various types of media files (videos, images, PDFs, ZIPs, etc.) from Telegram channels and groups. The downloader supports resumable downloads, batch processing, and progress tracking, making it ideal for managing large volumes of media efficiently.

## Features

-   **Brand New UI (v2.0)**: Modern, sleek CustomTkinter interface with sidebar navigation and beautiful status cards.
-   **Cross-platform Executables**: Standalone executables automatically built via GitHub Actions for Windows, Linux, and macOS.
-   **Persistent Queue**: Your download queue and progress is automatically saved to disk and restored upon restarting the app.
-   **Batch Processing**: Downloads media in configurable batches for better resource management.
-   **Multi-Media Support**: Supports videos, images, PDFs, ZIP files, and more.
-   **Progress Tracking**: Displays detailed itemized progress bars for each download along with speed (KB/s).
-   **Settings Management**: Configure your download folder and active download limits directly from the GUI.
-   **Cross-Platform**: Runs natively on Windows, macOS, and Linux.
-   **Lightweight**: Requires only Python and a few lightweight libraries to run.

## Screenshots

Here are some screenshots demonstrating the new v2.0 Telegram Downloader UI:

![Login Screen](screenshots/app_v2_login.png)
![Phone Number Verification](screenshots/phone_verification.png)
![Home View - Active Queue](screenshots/app_v2.png)

## Requirements

-   Python 3.8+
-   Telegram API credentials (API ID and API Hash)

## Installation

### Method 1: Download the Executable (Recommended)

1. Go to the [Releases](https://github.com/vinodkr494/telegram-media-downloader/releases) page.
2. Download the latest `TGDownloader-vX.X.X-Windows.exe` (or your respective OS version).
3. Run the executable directly. No installation or Python required!

*Note: Windows might show a "Smart App Control" warning because the executable is newly built and unsigned. Click **More info** -> **Run anyway** to launch it.*

### Method 2: Run from Source (For Developers)

1. Clone the repository:

    ```bash
    git clone https://github.com/vinodkr494/telegram-media-downloader.git
    cd telegram-media-downloader
    ```

2. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3. Create a `.env` file and configure it:

    ```env
    API_ID=your_api_id
    API_HASH=your_api_hash
    SESSION_NAME=default_session
    BATCH_SIZE=5
    ```

4. Run the GUI application:
    ```bash
    python src/gui.py
    ```

## Usage

1. **Start the GUI script**:

    ```bash
    python src/gui.py
    ```

    *(Alternatively, you can still use the CLI version with `python src/downloder.py`)*

2. Enter your API credentials and the Telegram channel username or **Channel ID** (e.g. `-100123456789`).

6. Select the type of media to download (e.g., images, videos, audio, PDFs, ZIPs, or all).

7. Click "＋ Add to Queue". If this is your first time connecting, you will be prompted to enter your phone number and the login code sent to your Telegram app.

8. Watch as your files are downloaded with detailed progress bars dynamically in the UI! You can go to the **Downloads** tab to see previously added channels and inspect individual file statuses.

## Advanced Configuration

### Resuming Downloads

The downloader automatically saves the progress of completed files in a `download_state.json` file. To resume downloads, simply restart the script, and it will skip already downloaded files.

### Batch Size

To adjust the number of files downloaded in parallel, update the `BATCH_SIZE` value in the `.env` file.

### Supported Media Types

The tool supports the following media types:

-   Videos
-   Images
-   PDFs
-   ZIP files
-   Any other Telegram media

## Roadmap

### Version 2.1
-   Add support for specific date-range filtering.
-   Add file size limits before downloading.
-   Enhanced error retry mechanisms.

## Contributing

We welcome contributions of all kinds! Please see the [CONTRIBUTING.md](CONTRIBUTING.md) file for details on how to get started.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

-   [Telethon](https://github.com/LonamiWebs/Telethon) - For making Telegram API integration easy.
-   [TQDM](https://github.com/tqdm/tqdm) - For elegant progress bars.
-   [Colorama](https://github.com/tartley/colorama) - For colorful console output.

---

Made with ❤️ by [Vinod Kumar](https://github.com/vinodkr494).
