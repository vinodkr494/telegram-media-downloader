import os
import humanize
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTabWidget, QWidget, QScrollArea,
    QCheckBox, QFrame, QSizePolicy, QLineEdit, QDateEdit,
    QGridLayout, QToolButton
)
from PySide6.QtCore import Qt, Signal, QDate, QRegularExpression
from PySide6.QtGui import QIcon
from resource_utils import get_resource_path

class SelectableMediaRow(QWidget):
    stateChanged = Signal(bool)

    def __init__(self, msg, parent=None):
        super().__init__(parent)
        self.msg = msg
        self.setObjectName("SelectableRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        # remove fixed height to allow wrapping if text is long
        self.setMinimumHeight(64)
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # 1. Checkbox
        self.cb = QCheckBox()
        self.cb.setCursor(Qt.PointingHandCursor)
        self.cb.stateChanged.connect(self.on_cb_state_changed)
        layout.addWidget(self.cb)

        # 1.5 Icon/Type Badge
        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedWidth(40)
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        self.lbl_icon.setStyleSheet("font-size: 24px;")
        
        icon_emoji = "📄"
        mime = getattr(self.msg.document, 'mime_type', '') if getattr(self.msg, 'document', None) else ""
        
        if getattr(self.msg, 'photo', None):
            icon_emoji = "🖼️"
        elif getattr(self.msg, 'video', None) or mime.startswith('video/'):
            # Detect Round Video
            if hasattr(self.msg, 'video') and getattr(self.msg.video, 'round', False):
                icon_emoji = "🎬"
            else:
                icon_emoji = "🎥"
        elif getattr(self.msg, 'audio', None) or mime.startswith('audio/'):
            icon_emoji = "🎵"
        elif getattr(self.msg, 'voice', None) or mime.startswith('audio/ogg'):
             icon_emoji = "🎤"
        elif getattr(self.msg, 'gif', None) or mime == 'video/mp4' and 'animated' in str(self.msg.media).lower():
            icon_emoji = "🎞️"
        elif mime in ["application/zip", "application/x-rar-compressed", "application/x-7z-compressed"]:
            icon_emoji = "📦"
        elif getattr(self.msg, 'web_preview', None):
            icon_emoji = "🔗"
            
        self.lbl_icon.setText(icon_emoji)
        layout.addWidget(self.lbl_icon)

        # 2. Information Stack
        info_stack = QVBoxLayout()
        info_stack.setSpacing(6)

        # Better size detection for ALL media types
        msg_size = 0
        if getattr(self.msg, 'file', None):
            msg_size = self.msg.file.size
        elif getattr(self.msg, 'document', None):
            msg_size = self.msg.document.size
        elif getattr(self.msg, 'photo', None):
            # Photos have multiple sizes, pick the largest
            try: msg_size = self.msg.photo.sizes[-1].size
            except: msg_size = 0
            
        size_str = humanize.naturalsize(msg_size) if msg_size else "0 B"
        date_str = ""
        m_date = getattr(self.msg, 'date', None)
        if m_date:
            from datetime import datetime
            if isinstance(m_date, str):
                date_str = m_date[:16] # Use string slice for common format
            else:
                date_str = m_date.strftime("%Y-%m-%d %H:%M")
        
        # Prioritize filename over caption for clearer identification
        title_text = ""
        if getattr(self.msg, 'file', None) and getattr(self.msg.file, 'name', None):
            title_text = self.msg.file.name
        elif self.msg.message:
            title_text = self.msg.message.replace('\n', ' ').strip()
        
        if not title_text:
            title_text = f"Msg #{self.msg.id}"

        self.lbl_title = QLabel(title_text)
        self.lbl_title.setObjectName("MediaItemTitle")
        self.lbl_title.setWordWrap(True) # Ensure long titles wrap properly
        info_stack.addWidget(self.lbl_title)

        # Row 2: Badge & Date
        meta_row = QHBoxLayout()
        meta_row.setSpacing(12)
        
        self.lbl_size = QLabel(size_str)
        self.lbl_size.setObjectName("SizeBadge")
        
        self.lbl_date = QLabel(date_str)
        self.lbl_date.setObjectName("MediaItemMeta")
        
        meta_row.addWidget(self.lbl_size)
        meta_row.addWidget(self.lbl_date)
        meta_row.addStretch()
        
        info_stack.addLayout(meta_row)
        layout.addLayout(info_stack)
        layout.addStretch()

    def on_cb_state_changed(self, state):
        is_checked = (state == Qt.Checked)
        self.setProperty("checked", "true" if is_checked else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.stateChanged.emit(is_checked)

    def mousePressEvent(self, event):
        # Toggle checkbox on click anywhere in row
        self.cb.setChecked(not self.cb.isChecked())
        super().mousePressEvent(event)

    def setChecked(self, state):
        self.cb.setChecked(state)

    def isChecked(self):
        return self.cb.isChecked()

class MediaBrowserDialog(QDialog):
    def __init__(self, channel_title, messages_dict, parent=None, previous_selected_ids=None, is_dark=True):
        super().__init__(parent)
        self.setWindowTitle(f"Media Browser - {channel_title}")
        self.previous_selected_ids = previous_selected_ids or []
        self.is_dark = is_dark
        icon_path = get_resource_path(os.path.join("assets", "logo.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.setMinimumSize(750, 500)
        self.messages = messages_dict
        self.selected_messages = []
        self.rows = {} # tab_name -> list of SelectableMediaRow
        
        self.setup_ui(channel_title)

    def setup_ui(self, channel_title):
        self.setObjectName("MediaBrowserDialog")
        
        # Theme specific colors
        bg_color = "#0F172A" if self.is_dark else "#F1F5F9"
        card_bg = "#111827" if self.is_dark else "#FFFFFF"
        tab_bg = "#1E293B" if self.is_dark else "#E2E8F0"
        tab_text = "#94A3B8" if self.is_dark else "#64748B"
        header_text = "#F8FAFC" if self.is_dark else "#1E293B"
        border_color = "#334155" if self.is_dark else "#CBD5E1"
        input_bg = "#1E293B" if self.is_dark else "#FFFFFF"
        input_text = "#FFFFFF" if self.is_dark else "#1E293B"

        self.setStyleSheet(f"""
            QDialog#MediaBrowserDialog {{ background-color: {bg_color}; }}
            QTabWidget::pane {{ border: 1px solid {border_color}; border-radius: 8px; background-color: {card_bg}; top: -1px; }}
            QTabBar::tab {{ background-color: {tab_bg}; color: {tab_text}; padding: 10px 20px; border-top-left-radius: 8px; border-top-right-radius: 8px; border: 1px solid {border_color}; margin-right: 4px; }}
            QTabBar::tab:selected {{ background-color: #3B82F6; color: white; font-weight: bold; border-bottom: none; }}
            QLineEdit {{ background-color: {input_bg}; color: {input_text}; border: 1px solid {border_color}; border-radius: 8px; padding: 8px 12px; }}
            QLabel#MainHeader {{ color: {header_text}; font-size: 20px; font-weight: bold; }}
            QLabel#DialogStatus {{ color: {tab_text}; }}
            
            /* Calendar/Date Picker Styling */
            QCalendarWidget QWidget#qt_calendar_navigationbar {{ background-color: {tab_bg}; }}
            QCalendarWidget QToolButton {{ color: {input_text}; background-color: transparent; border: none; font-weight: bold; }}
            QCalendarWidget QAbstractItemView:enabled {{ color: {input_text}; background-color: {input_bg}; selection-background-color: #3B82F6; selection-color: white; }}
            QCalendarWidget QAbstractItemView:disabled {{ color: {tab_text}; }}
            QCalendarWidget {{ background-color: {input_bg}; color: {input_text}; border: 1px solid {border_color}; border-radius: 8px; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        # Bottom Actions (Initialize early because tabs depend on them)
        self.lbl_selected_count = QLabel("0 files selected")
        self.lbl_selected_count.setObjectName("DialogStatus")

        # Header
        header_lbl = QLabel(f"Browse Media: {channel_title}")
        header_lbl.setObjectName("MainHeader")
        layout.addWidget(header_lbl)

        # 🔍 Search Bar
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        
        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("🔍 Quick search by name...")
        self.inp_search.setMinimumHeight(40)
        self.inp_search.textChanged.connect(self.filter_rows)
        
        self.btn_toggle_filters = QToolButton()
        self.btn_toggle_filters.setText("⚙️ Advanced Filters")
        self.btn_toggle_filters.setCheckable(True)
        self.btn_toggle_filters.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_toggle_filters.setMinimumHeight(40)
        self.btn_toggle_filters.clicked.connect(self.toggle_filters_area)
        
        search_layout.addWidget(self.inp_search, stretch=1)
        search_layout.addWidget(self.btn_toggle_filters)
        layout.addLayout(search_layout)

        # ⚙️ Advanced Filters Area (Collapsible)
        self.filters_area = QFrame(self)
        self.filters_area.setObjectName("WhiteCard")
        self.filters_area.setVisible(False)
        self.filters_area.setMinimumHeight(140) # Ensure it has enough room
        layout.addWidget(self.filters_area)
        
        # Filter specific theme colors
        f_bg = "#1E293B" if self.is_dark else "#F8FAFC"
        f_lbl = "#F8FAFC" if self.is_dark else "#475569"
        f_inp_bg = "#0F172A" if self.is_dark else "#FFFFFF"
        f_inp_text = "#F8FAFC" if self.is_dark else "#1E293B"
        
        self.filters_area.setStyleSheet(f"""
            QFrame#WhiteCard {{ background-color: {f_bg}; border-radius: 8px; border: 1px solid {border_color}; }}
            QLabel {{ color: {f_lbl} !important; background: transparent; border: none; }}
            QLineEdit, QDateEdit {{ background-color: {f_inp_bg}; color: {f_inp_text}; border: 1px solid {border_color}; padding: 4px; border-radius: 4px; }}
        """)
        
        f_layout = QGridLayout(self.filters_area)
        f_layout.setContentsMargins(16, 16, 16, 16)
        f_layout.setSpacing(12)
        
        # Row 1: Date Range
        lbl_d = QLabel("📅 Date Range:")
        f_layout.addWidget(lbl_d, 0, 0)
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addYears(-10))
        self.date_start.dateChanged.connect(self.filter_rows)
        
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        self.date_end.dateChanged.connect(self.filter_rows)
        
        date_range_layout = QHBoxLayout()
        date_range_layout.addWidget(self.date_start)
        date_range_layout.addWidget(QLabel("to"))
        date_range_layout.addWidget(self.date_end)
        f_layout.addLayout(date_range_layout, 0, 1)
        
        # Row 2: Size Range (MB)
        lbl_s = QLabel("📏 Size (MB):")
        f_layout.addWidget(lbl_s, 1, 0)
        self.size_min = QLineEdit()
        self.size_min.setPlaceholderText("Min MB")
        self.size_min.textChanged.connect(self.filter_rows)
        self.size_max = QLineEdit()
        self.size_max.setPlaceholderText("Max MB")
        self.size_max.textChanged.connect(self.filter_rows)
        
        size_layout = QHBoxLayout()
        size_layout.addWidget(self.size_min)
        size_layout.addWidget(QLabel("-"))
        size_layout.addWidget(self.size_max)
        f_layout.addLayout(size_layout, 1, 1)
        
        # Row 3: Regex
        lbl_r = QLabel("🧩 Regex:")
        f_layout.addWidget(lbl_r, 2, 0)
        self.inp_regex = QLineEdit()
        self.inp_regex.setPlaceholderText(r"e.g. ^IMG_.*\.jpg$")
        self.inp_regex.textChanged.connect(self.filter_rows)
        f_layout.addWidget(self.inp_regex, 2, 1)
        
        # Reset Filters Button
        self.btn_reset_filters = QPushButton("Reset Filters")
        self.btn_reset_filters.setObjectName("SecondaryButton")
        self.btn_reset_filters.clicked.connect(self.reset_filters)
        f_layout.addWidget(self.btn_reset_filters, 2, 2)
        
                # Tabs
        self.tabs = QTabWidget()
        self.tabs.setObjectName("MediaTabs")

        self.tab_all   = self.build_tab("all")
        self.tab_media = self.build_tab("media")
        self.tab_files = self.build_tab("files")
        self.tab_music = self.build_tab("music")
        self.tab_zips  = self.build_tab("zips")
        self.tab_voice = self.build_tab("voice")
        self.tab_links = self.build_tab("links")
        self.tab_gifs  = self.build_tab("gifs")
        self.tab_chat  = self.build_tab("chat")

        self.tabs.addTab(self.tab_all,   f"✨ All ({len(self.messages.get('all', []))})")
        self.tabs.addTab(self.tab_media, f"🎬 Media ({len(self.messages.get('media', []))})")
        self.tabs.addTab(self.tab_files, f"📄 Files ({len(self.messages.get('files', []))})")
        self.tabs.addTab(self.tab_music, f"🎵 Music ({len(self.messages.get('music', []))})")
        self.tabs.addTab(self.tab_zips,  f"📦 ZIPs ({len(self.messages.get('zips', []))})")
        self.tabs.addTab(self.tab_voice, f"🎤 Voice ({len(self.messages.get('voice', []))})")
        self.tabs.addTab(self.tab_links, f"🔗 Links ({len(self.messages.get('links', []))})")
        self.tabs.addTab(self.tab_gifs,  f"🖼️ GIFs ({len(self.messages.get('gifs', []))})")
        self.tabs.addTab(self.tab_chat,  f"💬 Chat ({len(self.messages.get('chat', []))})")

        layout.addWidget(self.tabs, stretch=1)

        # Bottom Actions
        bottom_layout = QHBoxLayout()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("SecondaryButton")
        self.btn_cancel.setFixedWidth(100)
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_download = QPushButton("Download Selected")
        self.btn_download.setObjectName("SuccessButton")
        self.btn_download.clicked.connect(self.accept)

        bottom_layout.addWidget(self.lbl_selected_count)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_cancel)
        bottom_layout.addWidget(self.btn_download)

        layout.addLayout(bottom_layout)
        self.inp_search.setFocus()

    def build_tab(self, tab_key):
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(0, 0, 0, 0) # Tabs should handle their own internal margins
        layout.setSpacing(0)
        
        # Tools bar
        tools = QWidget()
        tools.setFixedHeight(50)
        tools.setStyleSheet("background-color: transparent;")
        t_layout = QHBoxLayout(tools)
        t_layout.setContentsMargins(16, 0, 16, 0)
        
        btn_all = QPushButton("Select All")
        btn_all.setObjectName("SecondaryButton")
        btn_visible = QPushButton("Select Visible")
        btn_visible.setObjectName("SecondaryButton")
        btn_none = QPushButton("Clear All")
        btn_none.setObjectName("SecondaryButton")
        
        btn_all.clicked.connect(lambda: self.set_all_rows(tab_key, True))
        btn_visible.clicked.connect(lambda: self.set_rows_visible(tab_key, True))
        btn_none.clicked.connect(lambda: self.set_all_rows(tab_key, False))
        
        t_layout.addWidget(btn_all)
        t_layout.addWidget(btn_visible)
        t_layout.addWidget(btn_none)
        t_layout.addStretch()
        layout.addWidget(tools)

        # Scrollable list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        list_container = QWidget()
        list_container.setStyleSheet("background: transparent;")
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(16, 16, 16, 16) # Add padding so cards don't touch edges
        list_layout.setSpacing(10) # 10px spacing between cards
        list_layout.setAlignment(Qt.AlignTop)
        
        self.rows[tab_key] = []
        messages = self.messages.get(tab_key, [])
        for msg in messages:
            row = SelectableMediaRow(msg)
            if msg.id in self.previous_selected_ids:
                row.setChecked(True)
            row.stateChanged.connect(self.update_selected_count)
            self.rows[tab_key].append(row)
            list_layout.addWidget(row)
        
        self.update_selected_count()

        scroll.setWidget(list_container)
        layout.addWidget(scroll)
        
        return tab_widget

    def set_all_rows(self, tab_key, state):
        for row in self.rows.get(tab_key, []):
            row.setChecked(state)

    def set_rows_visible(self, tab_key, state):
        for row in self.rows.get(tab_key, []):
            if row.isVisible():
                row.setChecked(state)

    def toggle_filters_area(self, checked):
        self.filters_area.setVisible(checked)
        # Ensure the dialog adjusts its size dynamically, optimized for 768p
        if checked:
            self.setMinimumHeight(650) 
        else:
            self.setMinimumHeight(480)
        self.adjustSize()

    def reset_filters(self):
        self.inp_search.clear()
        self.inp_regex.clear()
        self.size_min.clear()
        self.size_max.clear()
        self.date_start.setDate(QDate.currentDate().addYears(-10))
        self.date_end.setDate(QDate.currentDate())
        self.btn_toggle_filters.setChecked(False)
        self.filters_area.setVisible(False)
        self.filter_rows()

    def filter_rows(self, _=None):
        search_text = self.inp_search.text().lower().strip()
        regex_text = self.inp_regex.text().strip()
        
        # Date limits
        start_date = self.date_start.date().toPython()
        end_date = self.date_end.date().toPython()
        
        # Size limits (Convert MB to Bytes)
        try:
            min_bytes = float(self.size_min.text()) * 1024 * 1024 if self.size_min.text() else 0
        except ValueError: min_bytes = 0
        try:
            max_bytes = float(self.size_max.text()) * 1024 * 1024 if self.size_max.text() else float('inf')
        except ValueError: max_bytes = float('inf')

        regex = None
        if regex_text:
            regex = QRegularExpression(regex_text, QRegularExpression.CaseInsensitiveOption)

        for tab_rows in self.rows.values():
            for row in tab_rows:
                msg = row.msg
                visible = True
                
                # 1. Quick Search Name
                title = row.lbl_title.text().lower()
                if search_text and search_text not in title:
                    visible = False
                    
                # 2. Regex
                if visible and regex:
                    match = regex.match(row.lbl_title.text())
                    if not match.hasMatch():
                        visible = False
                        
                # 3. Date Range
                if visible:
                    m_date = msg.date.date() if hasattr(msg, 'date') else None
                    if m_date:
                        if m_date < start_date or m_date > end_date:
                            visible = False
                            
                # 4. Size Range
                if visible:
                    m_size = 0
                    if getattr(msg, 'file', None):
                        m_size = msg.file.size
                    elif getattr(msg, 'document', None):
                        m_size = msg.document.size
                    elif getattr(msg, 'photo', None):
                        try: m_size = msg.photo.sizes[-1].size
                        except: m_size = 0
                        
                    if m_size < min_bytes or m_size > max_bytes:
                        visible = False
                            
                row.setVisible(visible)

    def update_selected_count(self):
        count = 0
        self.selected_messages.clear()
        
        for tab_rows in self.rows.values():
            for row in tab_rows:
                if row.isChecked():
                    count += 1
                    self.selected_messages.append(row.msg)
                    
        self.lbl_selected_count.setText(f"{count} files selected")

        # Visual feedback: Turn text green if > 0
        if count > 0:
            self.lbl_selected_count.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.lbl_selected_count.setStyleSheet("")

    def get_selected_messages(self):
        return self.selected_messages

    def refresh_content(self, messages_dict):
        """Refreshes the message list while attempting to preserve selection state."""
        # 1. Save current selected IDs
        current_selected = [m.id for m in self.get_selected_messages()]
        if self.previous_selected_ids:
            current_selected.extend(self.previous_selected_ids)
        self.previous_selected_ids = list(set(current_selected))
        
        # 2. Update messages
        self.messages = messages_dict
        
        # 3. Clear existing tabs
        self.tabs.clear()
        self.rows = {}
        
        # 4. Rebuild everything (this is simpler than merging)
        self.tab_all   = self.build_tab("all")
        self.tab_media = self.build_tab("media")
        self.tab_files = self.build_tab("files")
        self.tab_music = self.build_tab("music")
        self.tab_zips  = self.build_tab("zips")
        self.tab_voice = self.build_tab("voice")
        self.tab_links = self.build_tab("links")
        self.tab_gifs  = self.build_tab("gifs")
        self.tab_chat  = self.build_tab("chat")

        self.tabs.addTab(self.tab_all,   f"✨ All ({len(self.messages.get('all', []))})")
        self.tabs.addTab(self.tab_media, f"🎬 Media ({len(self.messages.get('media', []))})")
        self.tabs.addTab(self.tab_files, f"📄 Files ({len(self.messages.get('files', []))})")
        self.tabs.addTab(self.tab_music, f"🎵 Music ({len(self.messages.get('music', []))})")
        self.tabs.addTab(self.tab_zips,  f"📦 ZIPs ({len(self.messages.get('zips', []))})")
        self.tabs.addTab(self.tab_voice, f"🎤 Voice ({len(self.messages.get('voice', []))})")
        self.tabs.addTab(self.tab_links, f"🔗 Links ({len(self.messages.get('links', []))})")
        self.tabs.addTab(self.tab_gifs,  f"🖼️ GIFs ({len(self.messages.get('gifs', []))})")
        self.tabs.addTab(self.tab_chat,  f"💬 Chat ({len(self.messages.get('chat', []))})")
        
        self.update_selected_count()
