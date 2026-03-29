import sys
import os
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

# Keep a global reference to the app to update styles later
_app_instance = None

def apply_theme(is_dark=False):
    global _app_instance
    if not _app_instance: return
    
    filename = "dark_style.qss" if is_dark else "style.qss"
    qss_path = os.path.join(os.path.dirname(__file__), filename)
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            _app_instance.setStyleSheet(f.read())

def launch_app(telegram_worker, version="unknown"):
    global _app_instance
    _app_instance = QApplication(sys.argv)
    
    # Global Icon Setup
    from PySide6.QtGui import QIcon
    icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "logo.ico")
    if os.path.exists(icon_path):
        _app_instance.setWindowIcon(QIcon(icon_path))
    
    apply_theme(is_dark=False)
            
    window = MainWindow(telegram_worker, version)
    window.show()
    
    # Start the worker thread
    telegram_worker.start()
    
    sys.exit(_app_instance.exec())
