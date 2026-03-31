import sys
import os
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

# Keep a global reference to the app to update styles later
_app_instance = None


def is_system_dark_mode() -> bool:
    """Detect the OS dark mode preference. Works on Windows, macOS, and Linux."""
    import platform
    system = platform.system()

    if system == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return value == 0  # 0 = dark mode, 1 = light mode
        except Exception:
            return False

    elif system == "Darwin":  # macOS
        try:
            import subprocess
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2
            )
            return result.stdout.strip().lower() == "dark"
        except Exception:
            return False

    else:  # Linux / other
        try:
            # Check GTK theme (works with GNOME, KDE Breeze-Dark, etc.)
            import subprocess
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                capture_output=True, text=True, timeout=2
            )
            return "dark" in result.stdout.strip().lower()
        except Exception:
            pass
        # Fallback: check XDG_CURRENT_DESKTOP / GTK_THEME env vars
        import os as _os
        gtk_theme = _os.environ.get("GTK_THEME", "").lower()
        return "dark" in gtk_theme


from resource_utils import get_resource_path


def apply_theme(is_dark=False):
    global _app_instance
    if not _app_instance:
        return

    # Persist the preference to config
    try:
        from ui.views.settings_view import load_config, save_config
        cfg = load_config()
        cfg["dark_mode"] = is_dark
        save_config(cfg)
    except Exception:
        pass

    filename = "dark_style.qss" if is_dark else "style.qss"
    qss_path = get_resource_path(os.path.join("assets", "styles", filename))
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            _app_instance.setStyleSheet(f.read())


def launch_app(telegram_worker, version="unknown"):
    global _app_instance
    _app_instance = QApplication(sys.argv)

    from PySide6.QtGui import QIcon
    icon_path = get_resource_path(os.path.join("assets", "logo.ico"))
    if os.path.exists(icon_path):
        _app_instance.setWindowIcon(QIcon(icon_path))

    # Determine startup theme:
    #   1. Use saved preference from config.json (if explicitly set by user)
    #   2. Fall back to Windows system dark mode detection
    try:
        from ui.views.settings_view import load_config
        cfg = load_config()
        saved_pref = cfg.get("dark_mode", None)
    except Exception:
        saved_pref = None

    if saved_pref is not None:
        startup_dark = bool(saved_pref)
    else:
        startup_dark = is_system_dark_mode()

    apply_theme(is_dark=startup_dark)

    window = MainWindow(telegram_worker, version)

    # Sync the sidebar Dark Mode toggle button to reflect the startup theme
    window.btn_theme.setChecked(startup_dark)
    if startup_dark:
        window.btn_theme.setText("Light Mode")
        from PySide6.QtGui import QIcon as _QIcon
        icon_p = get_resource_path(os.path.join("assets", "icons", "light-mode.png"))
        if os.path.exists(icon_p):
            window.btn_theme.setIcon(_QIcon(icon_p))

    window.show()

    # Start the worker thread
    telegram_worker.start()

    sys.exit(_app_instance.exec())

