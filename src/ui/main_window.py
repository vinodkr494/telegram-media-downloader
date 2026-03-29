import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QStackedWidget, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QLineEdit, QScrollArea, QFrame,
    QMessageBox, QToolButton, QSizePolicy
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from ui.components.download_card import DownloadCard
from ui.components.media_browser import MediaBrowserDialog
from ui.components import auth_dialogs
from ui.views.settings_view import SettingsView
from ui.views.downloads_view import DownloadsView
from ui.views.login_view import LoginView
from PySide6.QtGui import QCloseEvent

class MainWindow(QMainWindow):
    def __init__(self, telegram_worker, version="unknown"):
        super().__init__()
        self.worker = telegram_worker
        self.version = version
        self.setWindowTitle(f"TG Media Downloader v{version} (PySide6)")
        self.resize(1100, 750)
        self._is_authenticating = False
        
        self.setup_ui()
        self.connect_signals()

    def closeEvent(self, event: QCloseEvent):
        if self.worker:
            self.worker.stop()
            self.worker.quit()
            self.worker.wait(1000)
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
        self.sidebarWidget = QWidget()
        self.sidebarWidget.setObjectName("Sidebar")
        self.sidebarWidget.setFixedWidth(85)
        sidebar_layout = QVBoxLayout(self.sidebarWidget)
        sidebar_layout.setContentsMargins(5, 20, 5, 20)
        sidebar_layout.setSpacing(10)
        
        # Window Icon
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "logo.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Custom Sidebar Logo
        self.logo_container = QWidget()
        logo_layout = QVBoxLayout(self.logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 20)
        logo_layout.setSpacing(5)
        
        self.lbl_logo_img = QLabel()
        logo_png_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png"))
        if os.path.exists(logo_png_path):
            pixmap = QPixmap(logo_png_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_logo_img.setPixmap(pixmap)
        self.lbl_logo_img.setAlignment(Qt.AlignCenter)
        
        logo_layout.addWidget(self.lbl_logo_img)
        sidebar_layout.addWidget(self.logo_container)
        
        # Nav Buttons
        def create_nav_btn(text, icon_name):
            btn = QToolButton()
            btn.setText(text)
            icon_p = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", icon_name))
            if os.path.exists(icon_p):
                btn.setIcon(QIcon(icon_p))
                btn.setIconSize(QSize(24, 24))
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setMinimumHeight(65)
            btn.setCursor(Qt.PointingHandCursor)
            return btn

        self.btn_home = create_nav_btn("Home", "home.png")
        self.btn_home.setChecked(True)
        self.btn_queue = create_nav_btn("Queue", "download.png")
        self.btn_config = create_nav_btn("Settings", "setting.png")
        self.btn_about = create_nav_btn("About", "info.png")

        sidebar_layout.addWidget(self.btn_home)
        sidebar_layout.addWidget(self.btn_queue)
        sidebar_layout.addWidget(self.btn_config)
        sidebar_layout.addWidget(self.btn_about)
        sidebar_layout.addStretch()
        
        # Theme Toggle
        self.btn_theme = create_nav_btn("Dark Mode", "dark-mode.png") # Re-using setting icon for prototype
        self.btn_theme.setCheckable(True)
        self.btn_theme.clicked.connect(self.toggle_theme)
        sidebar_layout.addWidget(self.btn_theme)
        
        self.btn_logout = create_nav_btn("Logout", "logout.png")
        self.btn_logout.setObjectName("LogoutBtn")
        self.btn_logout.clicked.connect(self.logout)
        sidebar_layout.addWidget(self.btn_logout)

        # Connect nav logic simply (Mutually exclusive manual group for dark styling)
        for btn, idx in [(self.btn_home, 0), (self.btn_queue, 1), (self.btn_config, 2), (self.btn_about, 3)]:
            btn.clicked.connect(lambda checked, b=btn, i=idx: self.switch_page(b, i))

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
        lbl_header.setStyleSheet("color: #1E293B; font-weight: bold; font-size: 20px;")
        h_layout.addWidget(lbl_header)
        h_layout.addStretch()

        content_layout.addWidget(self.header)

        # Stacked Pages
        self.stacked_widget = QStackedWidget()
        self.setup_home_page()
        
        self.page_queue = DownloadsView()
        self.page_settings = SettingsView()
        self.page_login = LoginView()
        
        self.page_about = QWidget()
        about_layout = QVBoxLayout(self.page_about)
        about_layout.setContentsMargins(40, 40, 40, 40)
        about_layout.setSpacing(24)
        
        lbl_about_header = QLabel("About Telegram Bulk Media Downloader")
        lbl_about_header.setStyleSheet("color: #1E293B; font-weight: bold; font-size: 24px;")
        about_layout.addWidget(lbl_about_header)
        
        about_card = QFrame()
        about_card.setObjectName("WhiteCard")
        ac_layout = QVBoxLayout(about_card)
        ac_layout.setContentsMargins(24, 24, 24, 24)
        ac_layout.setSpacing(16)
        
        lbl_version = QLabel(f"Version: {self.version} (PySide6)")
        lbl_version.setObjectName("SectionHeader")
        ac_layout.addWidget(lbl_version)
        
        lbl_desc = QLabel(
            "A fast, modern Telegram bulk media downloader with proxy support, speed limits, "
            "and persistent queueing.\n\n"
            "By Vinod Kumar."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #475569; font-size: 14px; line-height: 1.5;")
        ac_layout.addWidget(lbl_desc)
        
        ac_layout.addWidget(QLabel("")) # Spacer
        
        lbl_disclaimer = QLabel("⚠️ Legal Disclaimer")
        lbl_disclaimer.setObjectName("SectionHeader")
        lbl_disclaimer.setStyleSheet("color: #EF4444;")
        ac_layout.addWidget(lbl_disclaimer)
        
        lbl_disclaimer_text = QLabel(
            "This tool is intended for personal and legitimate use only.\n"
            "Only download content from channels you own or have permission to access.\n"
            "Do not use this tool to infringe copyright or violate Terms of Service."
        )
        lbl_disclaimer_text.setWordWrap(True)
        lbl_disclaimer_text.setObjectName("MutedText")
        ac_layout.addWidget(lbl_disclaimer_text)
        
        about_layout.addWidget(about_card)
        about_layout.addStretch()
        
        self.stacked_widget.addWidget(self.page_home)   # Index 0
        self.stacked_widget.addWidget(self.page_queue)  # Index 1
        self.stacked_widget.addWidget(self.page_settings) # Index 2
        self.stacked_widget.addWidget(self.page_about)  # Index 3
        self.stacked_widget.addWidget(self.page_login)  # Index 4
        
        # Connect Login signals
        self.page_login.login_started.connect(self.worker.start_login)
        self.page_login.code_submitted.connect(self.worker.submit_code)
        self.page_login.password_submitted.connect(self.worker.submit_password)
        
        # Connect Queue Global Buttons
        self.page_queue.btn_pause_all.clicked.connect(self.pause_all_downloads)
        self.page_queue.btn_resume_all.clicked.connect(self.resume_all_downloads)
        
        content_layout.addWidget(self.stacked_widget)

        # Build Main View
        main_layout.addWidget(self.sidebarWidget)
        main_layout.addWidget(content_wrapper)

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
        
        search_input_layout.addWidget(self.input_channel)
        search_input_layout.addWidget(self.btn_fetch)
        
        lbl_hint = QLabel("Tip: enter @username, https://t.me/username, or the numeric channel ID")
        lbl_hint.setObjectName("MutedText")
        lbl_hint.setStyleSheet("font-size: 11px;")
        
        sc_layout.addWidget(lbl_search_title)
        sc_layout.addLayout(search_input_layout)
        sc_layout.addWidget(lbl_hint)

        layout.addWidget(search_card)

        layout.addWidget(search_card)

        # Bottom stretch to keep search card at top
        layout.addStretch()
        
        self.card_widgets = {} # task_id -> DownloadCard

    def switch_page(self, clicked_btn, index):
        self.btn_home.setChecked(False)
        self.btn_queue.setChecked(False)
        self.btn_config.setChecked(False)
        self.btn_about.setChecked(False)
        clicked_btn.setChecked(True)
        self.stacked_widget.setCurrentIndex(index)
        
        # Toggle 'Add Download' header visibility
        if index == 0:
            self.header.show()
        else:
            self.header.hide()

    def toggle_theme(self):
        import ui.app as main_app
        is_dark = self.btn_theme.isChecked()
        if is_dark:
            self.btn_theme.setText("Light Mode")
            icon_name = "light-mode.png"
        else:
            self.btn_theme.setText("Dark Mode")
            icon_name = "dark-mode.png"
            
        icon_p = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", icon_name))
        if os.path.exists(icon_p):
            self.btn_theme.setIcon(QIcon(icon_p))
            
        main_app.apply_theme(is_dark)

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
        self.worker.signals.error_occurred.connect(lambda ch, e: QMessageBox.critical(self, "Download Error", f"Error in {ch}:\n{e}"))

    def on_download_completed(self, task_id, folder_name):
        if task_id in self.card_widgets:
            card = self.card_widgets[task_id]
            title = card.lbl_title.text()
            self.page_queue.active_layout.removeWidget(card)
            card.deleteLater()
            del self.card_widgets[task_id]
            self.page_queue.add_completed_item(title, folder_name)

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
            self.switch_page(self.btn_home, 0)
            self._is_authenticating = False
            auth_dialogs.show_auth_success(self)
        self.load_active_tasks_from_worker()
        
    def load_active_tasks_from_worker(self):
        from core_downloader import load_active_tasks
        tasks = load_active_tasks()
        for t in tasks:
            self.worker.start_download(
                channel_input=t.get("channel_input"),
                media_id=t.get("media_id", 6),
                download_path=t.get("download_path", "downloads"),
                download_limit=t.get("download_limit", 5),
                max_speed_kb=t.get("max_speed_kb", 0),
                is_paused=t.get("paused", True),
                selected_message_ids=t.get("selected_message_ids", None)
            )
        
    def on_fetch_clicked(self):
        channel = self.input_channel.text().strip()
        if not channel: return
        
        self.btn_fetch.setText("Fetching...")
        self.btn_fetch.setEnabled(False)
        self.worker.fetch_media_list(channel)

    def show_media_browser(self, channel_input, channel_obj, messages_dict):
        self.btn_fetch.setText("🔍 Fetch Media")
        self.btn_fetch.setEnabled(True)
        self.input_channel.clear()
        
        title = getattr(channel_obj, 'title', str(channel_obj.id))
        dialog = MediaBrowserDialog(title, messages_dict, self)
        
        if dialog.exec():
            selected_msgs = dialog.get_selected_messages()
            if not selected_msgs:
                return # they selected nothing
                
            selected_ids = [m.id for m in selected_msgs]
            from ui.views.settings_view import load_config
            cfg = load_config()
            self.worker.start_download(
                channel_input=channel_input, 
                media_id=6, # 6 is ALL
                download_path=cfg.get("download_path", "downloads"), 
                download_limit=cfg.get("download_limit", 5), 
                max_speed_kb=cfg.get("max_speed_kb", 0),
                selected_message_ids=selected_ids
            )

    def add_download_card(self, data, total_items):
        task_id = data["task_id"]
        if task_id in self.card_widgets:
            # Refresh placeholder card with real metadata
            card = self.card_widgets[task_id]
            card.refresh_from_metadata(
                title=data["title"],
                total_items=total_items,
                completed=data.get("completed", 0),
                files_metadata=data.get("files_metadata", [])
            )
            return
            
        card = DownloadCard(
            task_id=task_id, 
            title=data["title"], 
            total_items=total_items, 
            folder_name=data["folder_name"],
            media_type=data["media_id"],
            parent_worker=self.worker,
            completed=data.get("completed", 0),
            is_paused=data.get("is_paused", False),
            download_path=data.get("download_path", "downloads"),
            download_limit=data.get("download_limit", 5),
            max_speed_kb=data.get("max_speed_kb", 0),
            files_metadata=data.get("files_metadata", [])
        )
        # Connect Trash button securely
        card.btn_trash.clicked.connect(lambda _, c=card: self.remove_card(c))
        # Connect Priority buttons securely
        card.btn_up.clicked.connect(lambda _, c=card: self.move_card(c, -1))
        card.btn_down.clicked.connect(lambda _, c=card: self.move_card(c, 1))
        
        self.page_queue.active_layout.addWidget(card)
        self.card_widgets[task_id] = card
        self.page_queue.set_controls_visible(True)

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

    def update_file_progress(self, task_id, msg_id, current_bytes, total_bytes, speed_str):
        if task_id in self.card_widgets:
            self.card_widgets[task_id].update_file_progress(msg_id, current_bytes, total_bytes, speed_str)

    def on_file_completed(self, task_id, msg_id):
        if task_id in self.card_widgets:
            self.card_widgets[task_id].mark_file_completed(msg_id)

    def pause_all_downloads(self):
        for task_id, card in self.card_widgets.items():
            if not card.is_paused:
                card.toggle_pause()

    def resume_all_downloads(self):
        for task_id, card in self.card_widgets.items():
            if card.is_paused:
                card.toggle_pause()

    def remove_card(self, card_widget):
        self.worker.cancel_download(card_widget.task_id)
        self.page_queue.active_layout.removeWidget(card_widget)
        card_widget.setParent(None)
        card_widget.deleteLater()
        if card_widget.task_id in self.card_widgets:
            del self.card_widgets[card_widget.task_id]
        self.page_queue.set_controls_visible(len(self.card_widgets) > 0)

    def logout(self):
        reply = QMessageBox.question(self, "Logout", "Are you sure you want to log out? This will pause all downloads and clear your session.", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.pause_all_downloads()
            for task_id in list(self.card_widgets.keys()):
                self.remove_card(self.card_widgets[task_id])
            self.worker.logout()
            
            # Clear persistent queue safely
            try:
                from core_downloader import save_active_tasks
                save_active_tasks([])
            except Exception:
                pass
                
            self.worker.signals.auth_needed.emit()
