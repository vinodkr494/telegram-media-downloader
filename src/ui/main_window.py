import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QStackedWidget, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QLineEdit, QScrollArea, QFrame,
    QMessageBox, QToolButton, QSizePolicy, QSystemTrayIcon, QMenu, QStatusBar
)
from PySide6.QtCore import Qt, QSize, QUrl, QTimer
from PySide6.QtGui import QIcon, QPixmap, QDesktopServices
from ui.components.download_card import DownloadCard
from ui.components.media_browser import MediaBrowserDialog
from ui.components import auth_dialogs
from ui.views.settings_view import SettingsView
from ui.views.downloads_view import DownloadsView
from ui.views.login_view import LoginView
from PySide6.QtGui import QCloseEvent, QAction
from resource_utils import get_resource_path
from utils.update_checker import UpdateChecker

class MainWindow(QMainWindow):
    def __init__(self, telegram_worker, version="unknown"):
        super().__init__()
        print("DEBUG: MainWindow __init__ started")
        self.worker = telegram_worker
        self.version = version
        self.setWindowTitle(f"TG Media Downloader v{version} (PySide6)")
        self.resize(1100, 700)
        self.setMinimumSize(750, 500)
        self._is_authenticating = False
        self._tasks_loaded = False
        self._reselect_task_id = None # Current task being re-selected
        self._active_media_browser = None # Current open browser dialog
        
        print("DEBUG: Setting up UI")
        self.setup_ui()
        print("DEBUG: Connecting signals")
        self.connect_signals()
        print("DEBUG: Setting up tray")
        self.setup_tray()
        self._session_downloaded = 0
        self._last_speed_check = 0
        print("DEBUG: Checking for updates")
        self.check_for_updates()
        print("DEBUG: MainWindow __init__ DONE")

    def check_for_updates(self):
        self.update_checker = UpdateChecker(self.version, self)
        self.update_checker.update_available.connect(self.show_update_notification)
        self.update_checker.start()

    def show_update_notification(self, latest_version, download_url):
        # We'll just show a tray message and update the About button text maybe?
        self.tray_icon.showMessage(
            "New Update Available!",
            f"Version {latest_version} is now available on GitHub.\nClick here to download.",
            QSystemTrayIcon.Information,
            5000
        )
        self.tray_icon.messageClicked.connect(lambda: QDesktopServices.openUrl(QUrl(download_url)))
        
        # Also update the About item to have an exclamation
        self.btn_about.setText("About 🆕")
        self.btn_about.setToolTip(f"A new version ({latest_version}) is available!")

    def show_about_dialog(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("About TG Media Downloader")
        
        # Premium/Rich look with HTML
        text = f"""
        <h2 style='color: #2196F3;'>TG Media Downloader</h2>
        <p><b>Version:</b> v{self.version}</p>
        <p>A modern, high-performance Telegram media downloader built with PySide6 and Telethon.</p>
        <ul style='color: #555; padding-left: 20px;'>
            <li>✨ <b>Instant Loading:</b> Zero-wait cached media browsing.</li>
            <li>⚡ <b>Byte-Range Resuming:</b> Flawless pause & resume via explicit offsets.</li>
            <li>🗄️ <b>SQLite Persistence:</b> Robust, crash-proof active queues.</li>
        </ul>
        <hr/>
        <p>Enjoying the app? Consider supporting development by starring our repository!</p>
        <p><a href='https://github.com/vinodkr494/telegram-media-downloader' style='color: #FFC107; font-weight: bold; font-size: 14px;'>⭐ Star on GitHub</a></p>
        <br/>
        <p style='font-size: 10px; color: #888;'>&copy; 2026 Vinodkr494. Licensed under MIT.</p>
        """
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        icon_path = get_resource_path(os.path.join("assets", "logo.ico"))
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        
        # Tray Menu
        tray_menu = QMenu(self)
        action_show = tray_menu.addAction("📂 Restore Window")
        action_show.triggered.connect(self.showNormal)
        action_show.triggered.connect(self.activateWindow)
        
        tray_menu.addSeparator()
        action_pause = tray_menu.addAction("⏸ Pause All")
        action_pause.triggered.connect(self.pause_all_downloads)
        action_resume = tray_menu.addAction("▶ Resume All")
        action_resume.triggered.connect(self.resume_all_downloads)

        tray_menu.addSeparator()
        action_quit = tray_menu.addAction("❌ Quit App")
        action_quit.triggered.connect(self.force_quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def changeEvent(self, event):
        if event.type() == event.Type.WindowStateChange:
            if self.isMinimized():
                # Minimize to tray logic
                self.hide()
                self.tray_icon.showMessage(
                    "TG Downloader",
                    "Application minimized to tray. Double-click icon to restore.",
                    QSystemTrayIcon.Information,
                    2000
                )
        super().changeEvent(event)

    def force_quit(self):
        self.tray_icon.hide()
        self.close()

    def closeEvent(self, event: QCloseEvent):
        # 🟢 Optional: Warn if tasks are active
        if self.card_widgets:
            reply = QMessageBox.question(self, "Exit", "Downloads are still in progress. Are you sure you want to exit?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                event.ignore()
                return

        # 🟢 Clean up Update Checker
        if hasattr(self, 'update_checker') and self.update_checker.isRunning():
            self.update_checker.wait(500)
            if self.update_checker.isRunning():
                self.update_checker.terminate()
            
        if self.worker:
            self.worker.stop()
            if not self.worker.wait(2000):
                pass 
                
        event.accept()

    def setup_ui(self):
        main_widget = QWidget()
        main_widget.setObjectName("CentralWidget")
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------------------------------------------------
        # Sidebar
        # ---------------------------------------------------------
        # ---------------------------------------------------------
        # Sidebar Navigation (Refactored to QToolButtons for better styling)
        # ---------------------------------------------------------
        self.sidebarWidget = QWidget()
        self.sidebarWidget.setObjectName("Sidebar")
        self.sidebarWidget.setFixedWidth(85)
        
        sidebar_layout = QVBoxLayout(self.sidebarWidget)
        sidebar_layout.setContentsMargins(4, 20, 4, 15)
        sidebar_layout.setSpacing(8)

        # 1. Logo
        self.logo_container = QWidget()
        logo_layout = QVBoxLayout(self.logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 10)
        
        self.lbl_logo_img = QLabel()
        logo_png_path = get_resource_path(os.path.join("assets", "logo.png"))
        if os.path.exists(logo_png_path):
            pixmap = QPixmap(logo_png_path).scaled(42, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_logo_img.setPixmap(pixmap)
        self.lbl_logo_img.setAlignment(Qt.AlignCenter)
        logo_layout.addWidget(self.lbl_logo_img)
        sidebar_layout.addWidget(self.logo_container)

        # 2. Nav Buttons (Now using original icons from assets)
        self.btn_home = self._create_nav_button("Home", "home.png", True)
        self.btn_queue = self._create_nav_button("Queue", "download.png")
        self.btn_settings = self._create_nav_button("Settings", "setting.png")
        self.btn_about = self._create_nav_button("About", "info.png")

        self.btn_home.clicked.connect(lambda: self.switch_page("Home", 0))
        self.btn_queue.clicked.connect(lambda: self.switch_page("Queue", 1))
        self.btn_settings.clicked.connect(lambda: self.switch_page("Settings", 2))
        self.btn_about.clicked.connect(lambda: self.switch_page("About", -1))

        sidebar_layout.addWidget(self.btn_home)
        sidebar_layout.addWidget(self.btn_queue)
        sidebar_layout.addWidget(self.btn_settings)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(self.btn_about)

        # 3. Theme & Logout (Now using consistent sizing with nav buttons)
        self.btn_theme = self._create_nav_button("Theme", "light-mode.png")
        self.btn_theme.setAutoExclusive(False) # Theme toggle isn't part of nav group
        self.btn_theme.setCheckable(False)
        self.btn_theme.clicked.connect(self.toggle_theme)
        self.update_theme_icon() # Set initial icon
        sidebar_layout.addWidget(self.btn_theme)

        self.btn_logout = self._create_nav_button("Logout", "logout.png")
        self.btn_logout.setObjectName("LogoutBtn")
        self.btn_logout.setAutoExclusive(False)
        self.btn_logout.setCheckable(False)
        self.btn_logout.clicked.connect(self.logout)
        sidebar_layout.addWidget(self.btn_logout)
        
        # Window Icon
        icon_path = get_resource_path(os.path.join("assets", "logo.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # ---------------------------------------------------------
        # Main Content Layout
        # ---------------------------------------------------------
        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Top Header Area
        self.header = QFrame()
        self.header.setFixedHeight(60)
        self.header.setStyleSheet("background-color: transparent;")
        h_layout = QHBoxLayout(self.header)
        h_layout.setContentsMargins(40, 20, 24, 0)
        
        lbl_header = QLabel("Add Download")
        lbl_header.setObjectName("MainHeader")
        h_layout.addWidget(lbl_header)
        h_layout.addStretch()

        content_layout.addWidget(self.header)

        # Stacked Pages
        self.stacked_widget = QStackedWidget()
        self.setup_home_page()
        
        self.page_queue = DownloadsView()
        self.page_settings = SettingsView()
        self.page_login = LoginView()
        
        self.stacked_widget.addWidget(self.page_home)   # Index 0
        self.stacked_widget.addWidget(self.page_queue)  # Index 1
        self.stacked_widget.addWidget(self.page_settings) # Index 2
        self.stacked_widget.addWidget(self.page_login)  # Index 3
        
        # Connect Login signals
        self.page_login.login_started.connect(self.worker.start_login)
        self.page_login.code_submitted.connect(self.worker.submit_code)
        self.page_login.password_submitted.connect(self.worker.submit_password)
        
        # Connect Queue Global Buttons
        self.page_queue.btn_pause_all.clicked.connect(self.pause_all_downloads)
        self.page_queue.btn_resume_all.clicked.connect(self.resume_all_downloads)
        self.page_queue.reFetchRequested.connect(self.re_fetch_from_history)
        
        content_layout.addWidget(self.stacked_widget)

        # Build Main View
        main_layout.addWidget(self.sidebarWidget)
        main_layout.addWidget(content_wrapper)
        
        # 🟢 Global Status Bar (Refined for right alignment and styling)
        self.status_bar = QStatusBar()
        self.status_bar.setObjectName("GlobalStatusBar")
        self.setStatusBar(self.status_bar)
        
        self.lbl_status_msg = QLabel("Ready")
        self.status_bar.addPermanentWidget(self.lbl_status_msg)

    def _create_nav_button(self, text, icon_name=None, is_checked=False):
        btn = QToolButton()
        btn.setText(text)
        if icon_name:
            icon_path = get_resource_path(os.path.join("assets", "icons", icon_name))
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
        btn.setIconSize(QSize(24, 24))
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.setChecked(is_checked)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return btn

    def setup_home_page(self):
        self.page_home = QWidget()
        layout = QVBoxLayout(self.page_home)
        layout.setContentsMargins(40, 20, 40, 40)
        layout.setSpacing(24)

        # Search Area Card
        search_card = QWidget()
        search_card.setObjectName("WhiteCard")
        sc_layout = QVBoxLayout(search_card)
        sc_layout.setContentsMargins(24, 24, 24, 24)
        sc_layout.setSpacing(12)
        
        lbl_search_title = QLabel("Channel / Group")
        lbl_search_title.setObjectName("SectionHeader")
        
        search_input_layout = QHBoxLayout()
        self.input_channel = QLineEdit()
        self.input_channel.setPlaceholderText("Enter username or channel ID...")
        self.input_channel.setMinimumHeight(44)
        
        self.btn_fetch = QPushButton("🔍 Fetch Media")
        self.btn_fetch.setObjectName("PrimaryButton")
        self.btn_fetch.setMinimumHeight(44)
        self.btn_fetch.clicked.connect(self.on_fetch_clicked)
        
        search_input_layout.addWidget(self.input_channel, stretch=1)
        search_input_layout.addWidget(self.btn_fetch)
        
        lbl_hint = QLabel("Tip: enter @username, https://t.me/username, or the numeric channel ID")
        lbl_hint.setObjectName("MutedText")
        lbl_hint.setWordWrap(True)
        
        sc_layout.addWidget(lbl_search_title)
        sc_layout.addLayout(search_input_layout)
        sc_layout.addWidget(lbl_hint)

        layout.addWidget(search_card)

        # Bottom stretch to keep search card at top
        layout.addStretch()
        
        self.card_widgets = {} # task_id -> DownloadCard

    def on_sidebar_changed(self, current_btn):
        # This was for QListWidget, we can keep it empty or remove it.
        # Buttons now use connected switch_page calls directly.
        pass

    def switch_page(self, item_text, index):
        # Update button states visually if needed (AutoExclusive handles checking)
        if "Home" in item_text:
            self.header.show()
            self.stacked_widget.setCurrentIndex(0)
            self.btn_home.setChecked(True)
        elif "Queue" in item_text:
            self.header.hide()
            self.stacked_widget.setCurrentIndex(1)
            self.btn_queue.setChecked(True)
        elif "Settings" in item_text:
            self.header.hide()
            self.stacked_widget.setCurrentIndex(2)
            self.btn_settings.setChecked(True)
        elif "About" in item_text:
            self.show_about_dialog()
            # Restore previous check state
            curr = self.stacked_widget.currentIndex()
            if curr == 0: self.btn_home.setChecked(True)
            elif curr == 1: self.btn_queue.setChecked(True)
            elif curr == 2: self.btn_settings.setChecked(True)
        else:
            self.header.hide()

    def toggle_theme(self):
        # 🛡️ Optimization: Block signals to avoid massive redraw cascades while QSS is applying
        self.setUpdatesEnabled(False)
        try:
            import ui.app as main_app
            from ui.views.settings_view import load_config
            cfg = load_config()
            is_dark = not cfg.get("dark_mode", False)
            main_app.apply_theme(is_dark)
            self.update_theme_icon()
        finally:
            self.setUpdatesEnabled(True)
            self.repaint() # Force a clean refresh at the end

    def update_theme_icon(self):
        from ui.views.settings_view import load_config
        cfg = load_config()
        is_dark = cfg.get("dark_mode", False)
        icon_name = "dark-mode.png" if is_dark else "light-mode.png"
        icon_path = get_resource_path(os.path.join("assets", "icons", icon_name))
        if os.path.exists(icon_path):
            self.btn_theme.setIcon(QIcon(icon_path))
            self.btn_theme.setText("Dark" if is_dark else "Light")

    # ---------------------------------------------------------
    # Actions & Signals
    # ---------------------------------------------------------
    def connect_signals(self):
        self.worker.signals.auth_needed.connect(self.prompt_login)
        self.worker.signals.code_needed.connect(self.prompt_code)
        self.worker.signals.password_needed.connect(self.prompt_password)
        self.worker.signals.auth_success.connect(self.on_auth_success)
        self.worker.signals.auth_error.connect(self.show_auth_error)
        
        self.worker.signals.media_list_fetched.connect(self.show_media_browser)
        self.worker.signals.channel_fetched.connect(self.add_download_card)
        self.worker.signals.download_progress.connect(self.update_progress)
        self.worker.signals.file_progress.connect(self.update_file_progress)
        self.worker.signals.file_completed.connect(self.on_file_completed)
        self.worker.signals.download_completed.connect(self.on_download_completed)
        self.worker.signals.error_occurred.connect(self.on_fetch_error)
        
        self.page_settings.logoutRequested.connect(self.logout)
        # sidebar signals are now handled by button connects

    def on_download_completed(self, task_id, folder_name):
        if task_id in self.card_widgets:
            card = self.card_widgets[task_id]
            title = card.lbl_title.text()
            self.page_queue.active_layout.removeWidget(card)
            card.deleteLater()
            del self.card_widgets[task_id]
            self.page_queue.add_completed_item(title, folder_name, task_id)
            
            # Tray notification
            self.tray_icon.showMessage(
                "Download Completed ✅",
                f"Successfully downloaded: {title}",
                QSystemTrayIcon.Information,
                3000
            )

    def prompt_login(self):
        self._is_authenticating = True
        self.sidebarWidget.hide()
        self.page_login.reset_to_start()
        self.stacked_widget.setCurrentWidget(self.page_login)

    def prompt_code(self, phone):
        self.page_login.show_otp_step()

    def prompt_password(self):
        self.page_login.show_pwd_step()
        
    def show_auth_error(self, err_msg):
        auth_dialogs.show_auth_error(self, err_msg)
        self.page_login.reset_to_start()
            
    def on_auth_success(self):
        if self._is_authenticating:
            self.sidebarWidget.show()
            self.switch_page("Home", 0)
            self._is_authenticating = False
            auth_dialogs.show_auth_success(self)
        self.load_active_tasks_from_worker()
        
    def load_active_tasks_from_worker(self):
        print("DEBUG: load_active_tasks_from_worker started")
        if self._tasks_loaded:
            print("DEBUG: tasks already loaded, skipping")
            return
        self._tasks_loaded = True
        
        try:
            from core_downloader import load_active_tasks, save_active_tasks
            tasks = load_active_tasks()
            if not isinstance(tasks, list):
                print(f"Warning: active_tasks.json is not a list. Type: {type(tasks)}")
                tasks = []
                
            # Initial deduplication
            seen = set()
            deduped = []
            for t in tasks:
                if not isinstance(t, dict): continue
                key = (str(t.get("channel_input")), t.get("media_id"))
                if key not in seen:
                    seen.add(key)
                    deduped.append(t)
            
            if len(deduped) != len(tasks):
                save_active_tasks(deduped)
                tasks = deduped
            
            # 🟢 Smart Startup Loader
            for i, t in enumerate(tasks):
                if not isinstance(t, dict): continue
                chan = t.get("channel_input")
                media = t.get("media_id", 6)
                print(f"DEBUG: Processing task {i}: {chan}_{media}")
                if not chan: continue
                
                is_paused = bool(t.get("paused", True))
                
                # If it's paused, just show the card (no network)
                if is_paused:
                    # In UI, we don't 'clean' the ID anymore, we use what's in the task
                    # but ensure we handle the -100 prefix consistently.
                    ch_id_full = str(chan)
                    m_id = t.get('media_id', 6)
                    self.add_download_card({
                        "task_id": f"{ch_id_full}_{m_id}",
                        "title": t.get("title") or f"Saved Task: {chan}",
                        "is_paused": True,
                        "download_path": t.get("download_path", "downloads"),
                        "download_limit": t.get("download_limit", 5),
                        "max_speed_kb": t.get("max_speed_kb", 0),
                        "media_type": m_id,
                        "completed": t.get("completed", 0),
                        "folder_name": t.get("folder_name") or t.get("download_path", "downloads")
                    }, t.get("total_items", 0))
                else:
                    # Stagger starts to avoid UI choking
                    def delayed_start(t_data=t):
                        try:
                            self.worker.start_download(
                                channel_input=t_data.get("channel_input"),
                                media_id=t_data.get("media_id", 6),
                                download_path=t_data.get("download_path", "downloads"),
                                download_limit=t_data.get("download_limit", 5),
                                max_speed_kb=t_data.get("max_speed_kb", 0),
                                is_paused=False,
                                selected_message_ids=t_data.get("selected_message_ids", None)
                            )
                        except Exception as e:
                            print(f"Startup task error: {e}")
                            
                    QTimer.singleShot(max(10, i * 500), delayed_start)
                    
        except Exception as startup_err:
            print(f"Critical startup loading error: {startup_err}")
            import traceback
            traceback.print_exc()
        
    def on_fetch_clicked(self):
        channel = self.input_channel.text().strip()
        if not channel: return
        
        self.btn_fetch.setText("Fetching...")
        self.btn_fetch.setEnabled(False)
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
        # 🚀 Instant Load from Cache to "WOW" the user
        from database import get_cached_media
        cached = get_cached_media(channel)
        if cached:
            # Reconstruct categorized dict from DB rows
            c_dict = {k.lower(): [] for k in ["Media", "Files", "ZIPs", "Music", "Voice", "Links", "GIFs", "Chat", "All"]}
            import collections
            MockMsg = collections.namedtuple('MockMsg', ['id', 'message', 'date', 'size', 'media_type', 'is_mock'])
            for row in cached:
                m = MockMsg(id=row["msg_id"], message=row["title"], date=row["date"], size=row["size"], media_type=row["media_type"], is_mock=True)
                cat = row["media_type"].lower()
                if cat in c_dict:
                    c_dict[cat].append(m)
                
                # ZIPs also belong in Files
                if cat == 'zips':
                    c_dict['files'].append(m)
                    
                c_dict["all"].append(m)
                
            for k in c_dict:
                c_dict[k].sort(key=lambda x: x.id, reverse=True)
            
            # Show dialog immediately with cached data
            # To avoid blocking the background fetch signal, we use a single shot timer
            QTimer.singleShot(0, lambda: self.show_media_browser(channel, None, c_dict))

        self.worker.fetch_media_list(channel)

    def show_media_browser(self, channel_input, channel_obj, messages_dict):
        # 🔄 Update existing dialog if it's already open (Instant Loading Flow)
        if self._active_media_browser and self._active_media_browser.isVisible():
            self._active_media_browser.refresh_content(messages_dict)
            return

        # 🔄 Selection Persistence Reset
        if self._reselect_task_id and self._reselect_task_id in self.card_widgets:
            self.card_widgets[self._reselect_task_id].set_reselect_loading(False)
            
        self.btn_fetch.setText("🔍 Fetch Media")
        self.btn_fetch.setEnabled(True)
        self.input_channel.clear()
        
        # If we came from cache, channel_obj might be None
        if not channel_obj:
            title = str(channel_input)
        else:
            title = getattr(channel_obj, 'title', str(channel_obj.id))
        
        # 🌙 Theme Support
        from ui.views.settings_view import load_config
        cfg = load_config()
        is_dark = cfg.get("dark_mode", False)

        # 🔄 Selection Persistence for Re-select from SQLite
        existing_ids = []
        if self._reselect_task_id:
            from database import get_task_db
            try:
                ch_in, m_id_str = self._reselect_task_id.rsplit('_', 1)
                task_data = get_task_db(ch_in, int(m_id_str))
                if task_data:
                    existing_ids = task_data.get("selected_message_ids", [])
            except: pass
            
        dialog = MediaBrowserDialog(title, messages_dict, self, previous_selected_ids=existing_ids, is_dark=is_dark)
        self._active_media_browser = dialog
        
        if dialog.exec():
            selected_msgs = dialog.get_selected_messages()
            if not selected_msgs:
                self._active_media_browser = None
                return # they selected nothing
                
            selected_ids = [m.id for m in selected_msgs]
            
            # If re-selecting, we use existing task_id
            target_task_id = self._reselect_task_id
            self._reselect_task_id = None # Clear context
            
            self.worker.start_download(
                channel_input=channel_input, 
                media_id=6, # 6 is ALL
                download_path=cfg.get("download_path", "downloads"), 
                download_limit=cfg.get("download_limit", 5), 
                max_speed_kb=cfg.get("max_speed_kb", 0),
                selected_message_ids=selected_ids,
                task_id=target_task_id # If this is set, worker will update existing task
            )
        
        self._active_media_browser = None

    def on_fetch_error(self, channel, err_msg):
        if self._reselect_task_id and self._reselect_task_id in self.card_widgets:
            self.card_widgets[self._reselect_task_id].set_reselect_loading(False)
            self._reselect_task_id = None
            
        self.btn_fetch.setText("🔍 Fetch Media")
        self.btn_fetch.setEnabled(True)
        QMessageBox.critical(self, "Fetch Error", f"Failed to fetch content for {channel}:\n{err_msg}")

    def add_download_card(self, data, total_items):
        task_id = data["task_id"]
        
        # 🛡️ SMART LOOKUP: If we can't find by task_id, look for a 'ghost' card that was
        # started by username/input but now has this resolved ID.
        if task_id not in self.card_widgets:
            ch_resolved = str(data.get("channel_input", ""))
            original_in = str(data.get("original_input", ""))
            m_id = data.get("media_id", 6)
            
            for old_id, card in list(self.card_widgets.items()):
                old_chan = old_id.rsplit('_', 1)[0]
                # Match by original user input OR by numeric ID if it was partially resolved
                # We also check for -100 stripped versions to be super safe.
                if (old_chan == original_in or 
                    old_chan == ch_resolved or 
                    old_chan.replace('-100', '', 1) == ch_resolved.replace('-100', '', 1)):
                    
                    print(f"DEBUG: Successfully hijacked ghost card {old_id} -> {task_id}")
                    # Re-map the card in our tracking dict
                    del self.card_widgets[old_id]
                    self.card_widgets[task_id] = card
                    card.task_id = task_id # Update card's own property
                    break

        if task_id in self.card_widgets:
            # Refresh placeholder card with real metadata
            card = self.card_widgets[task_id]
            card.refresh_from_metadata(
                title=data["title"],
                total_items=total_items,
                completed=data.get("completed", 0),
                files_metadata=data.get("files_metadata", []),
                is_paused=data.get("is_paused", card.is_paused) # Maintain local state if not provided
            )
            return
            
        print(f"DEBUG: Creating new card for {task_id}")
        is_paused = data.get("is_paused", False)
        card = DownloadCard(
            task_id=task_id,
            title=data["title"],
            total_items=total_items,
            folder_name=data.get("folder_name", "downloads"),
            media_type=data.get("media_type", 6),
            parent_worker=self.worker,
            completed=data.get("completed", 0),
            is_paused=is_paused,
            download_path=data.get("download_path", "downloads"),
            download_limit=data.get("download_limit", 5),
            max_speed_kb=data.get("max_speed_kb", 0),
            files_metadata=data.get("files_metadata", [])
        )
        self.page_queue.active_layout.addWidget(card)
        self.card_widgets[task_id] = card
        self.page_queue.set_controls_visible(True)
        
        # Connect reselect signal
        card.reselectRequested.connect(self.reselect_task_media)

    def move_card(self, card, direction):
        """direction: -1 (up), 1 (down)"""
        layout = self.page_queue.active_layout
        idx = layout.indexOf(card)
        new_idx = idx + direction
        if 0 <= new_idx < layout.count():
            layout.removeWidget(card)
            layout.insertWidget(new_idx, card)

    def update_progress(self, task_id, current, total):
        if task_id in self.card_widgets:
            self.card_widgets[task_id].update_progress(current, total)
            self.refresh_global_status()

    def update_file_progress(self, task_id, msg_id, current_bytes, total_bytes, speed_str):
        if task_id in self.card_widgets:
            self.card_widgets[task_id].update_file_progress(msg_id, current_bytes, total_bytes, speed_str)
            
            # Update session stats (rough estimate based on speed * interval if we had a timer, 
            # but worker emits current_bytes. We'll use a better approach: track per-file delta)
            # Actually, for session stats, let's just track completed items' total size or use a simpler counter.
            
            self.refresh_global_status()

    def refresh_global_status(self):
        # Global status update
        import humanize
        all_speeds = [c.last_speed_val for c in self.card_widgets.values() if hasattr(c, 'last_speed_val')]
        total_speed = sum(all_speeds)
        speed_text = f"{humanize.naturalsize(total_speed*1024)}/s" if total_speed > 0 else "0 B/s"
        
        # Calculate overall progress
        total_items = sum(c.total_items for c in self.card_widgets.values())
        total_completed = sum(c.completed for c in self.card_widgets.values())
        progress_pct = (total_completed * 100 / total_items) if total_items > 0 else 0
        
        # Session stats
        session_text = f" | Session: {humanize.naturalsize(self._session_downloaded)}" if self._session_downloaded > 0 else ""
        
        status_text = f"🟢 Speed: {speed_text}{session_text} | Total Progress: {progress_pct:.1f}% | Queue: {len(self.card_widgets)} tasks"
        self.lbl_status_msg.setText(status_text)
        
        # 🟢 Tray Tooltip
        tray_tip = f"TG Downloader - {speed_text}\nProgress: {progress_pct:.1f}% ({total_completed}/{total_items})"
        if len(self.card_widgets) > 1:
            tray_tip += f"\nQueue: {len(self.card_widgets)} active tasks"
        self.tray_icon.setToolTip(tray_tip)

    def on_file_completed(self, task_id, msg_id):
        if task_id in self.card_widgets:
            # Add to session downloaded
            card = self.card_widgets[task_id]
            if msg_id in card.file_rows:
                # We need the size of the completed file. 
                # Let's extract it from metadata if available.
                for meta in card.files_metadata:
                    if meta["id"] == msg_id:
                        self._session_downloaded += meta.get("size", 0)
                        break
            
            self.card_widgets[task_id].mark_file_completed(msg_id)
            self.refresh_global_status()

    def remove_task(self, task_id):
        if task_id in self.card_widgets:
            reply = QMessageBox.question(self, "Remove Task", "Are you sure you want to remove this task from the queue?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
                
            card = self.card_widgets[task_id]
            # 1. Stop if running
            self.worker.pause_download(task_id)
            # 2. Remove from worker tracking & files
            from core_downloader import load_active_tasks, save_active_tasks
            tasks = load_active_tasks()
            tasks = [t for t in tasks if f"{t.get('channel_input')}_{t.get('media_id')}" != task_id]
            save_active_tasks(tasks)
            # 3. Final cleanup from UI
            card.deleteLater()
            del self.card_widgets[task_id]
            
            if not self.card_widgets:
                self.page_queue.set_controls_visible(False)

    def move_task_up(self, task_id):
        if task_id in self.card_widgets:
            card = self.card_widgets[task_id]
            idx = self.page_queue.active_layout.indexOf(card)
            if idx > 0:
                self.page_queue.active_layout.removeWidget(card)
                self.page_queue.active_layout.insertWidget(idx - 1, card)

    def move_task_down(self, task_id):
        if task_id in self.card_widgets:
            card = self.card_widgets[task_id]
            idx = self.page_queue.active_layout.indexOf(card)
            # Count includes the stretch item at the end
            if idx < self.page_queue.active_layout.count() - 2: 
                self.page_queue.active_layout.removeWidget(card)
                self.page_queue.active_layout.insertWidget(idx + 1, card)

    def reselect_task_media(self, task_id):
        # 1. Extract channel name/ID from task_id (format: ID_mediaID)
        try:
            self._reselect_task_id = task_id # Set context for the upcoming browser
            if task_id in self.card_widgets:
                self.card_widgets[task_id].set_reselect_loading(True)
                
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            
            channel_input, media_id_str = task_id.rsplit('_', 1)
            # 2. Trigger a normal fetch for this channel
            self.input_channel.setText(channel_input)
            self.on_fetch_clicked()
        except Exception as e:
            self._reselect_task_id = None
            print(f"Reselect error: {e}")

    def pause_all_downloads(self):
        for task_id, card in self.card_widgets.items():
            if not card.is_paused:
                card.toggle_pause()

    def resume_all_downloads(self):
        for task_id, card in self.card_widgets.items():
            if card.is_paused:
                card.toggle_pause()

    def re_fetch_from_history(self, channel_id):
        self.input_channel.setText(str(channel_id))
        self.switch_page("Home", 0)
        self.on_fetch_clicked()

    def logout(self):
        reply = QMessageBox.question(self, "Logout", "Are you sure you want to log out? This will pause all downloads and clear your session.", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.pause_all_downloads()
            # Clear all current cards from memory/UI
            for task_id in list(self.card_widgets.keys()):
                self.remove_task(task_id)
                
            self.worker.logout()
            
            # Clear persistent queue safely
            try:
                from core_downloader import save_active_tasks
                save_active_tasks([])
            except Exception:
                pass
                
            self.worker.signals.auth_needed.emit()
