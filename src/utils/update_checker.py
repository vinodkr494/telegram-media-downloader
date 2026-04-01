import urllib.request
import json
import re
from PySide6.QtCore import QThread, Signal

class UpdateChecker(QThread):
    update_available = Signal(str, str) # version, url

    def __init__(self, current_version, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.repo_url = "https://api.github.com/repos/vinodkr494/telegram-media-downloader/releases/latest"

    def run(self):
        try:
            # Add a user-agent to avoid 403 from GitHub
            req = urllib.request.Request(self.repo_url, headers={'User-Agent': 'TG-Downloader-Update-Checker'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                latest_tag = data.get("tag_name", "")
                
                # Strip 'v' if present
                latest_clean = latest_tag.lstrip('v')
                current_clean = self.current_version.lstrip('v')
                
                if self.is_newer(latest_clean, current_clean):
                    self.update_available.emit(latest_tag, data.get("html_url", ""))
        except Exception as e:
            print(f"Update check failed: {e}")

    def is_newer(self, latest, current):
        try:
            def parse_v(v):
                return [int(x) for x in re.sub(r'[^0-9.]', '', v).split('.')]
            return parse_v(latest) > parse_v(current)
        except:
            return latest != current
