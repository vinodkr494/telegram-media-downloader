import os
import humanize
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTabWidget, QWidget, QScrollArea,
    QCheckBox, QFrame, QSizePolicy, QLineEdit
)
from PySide6.QtCore import Qt, Signal
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
        if getattr(self.msg, 'photo', None):
            icon_emoji = "🖼️"
        elif getattr(self.msg, 'video', None) or (getattr(self.msg, 'document', None) and self.msg.document.mime_type.startswith('video/')):
            icon_emoji = "🎥"
        elif getattr(self.msg, 'audio', None) or (getattr(self.msg, 'document', None) and self.msg.document.mime_type.startswith('audio/')):
            icon_emoji = "🎵"
        
        self.lbl_icon.setText(icon_emoji)
        layout.addWidget(self.lbl_icon)

        # 2. Information Stack
        info_stack = QVBoxLayout()
        info_stack.setSpacing(6)

        # Row 1: Title
        msg_size = getattr(self.msg, 'document', None) and getattr(self.msg.document, 'size', 0)
        size_str = humanize.naturalsize(msg_size) if msg_size else "0 B"
        date_str = self.msg.date.strftime("%Y-%m-%d %H:%M") if getattr(self.msg, 'date', None) else ""
        
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
    def __init__(self, channel_title, messages_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Media Browser - {channel_title}")
        icon_path = get_resource_path(os.path.join("assets", "logo.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.setMinimumSize(750, 600)
        self.messages = messages_dict
        self.selected_messages = []
        self.rows = {} # tab_name -> list of SelectableMediaRow
        
        self.setup_ui(channel_title)

    def setup_ui(self, channel_title):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Header
        header_lbl = QLabel(f"Browse Media: {channel_title}")
        header_lbl.setObjectName("MainHeader")
        layout.addWidget(header_lbl)

        # 🔍 Search Bar
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        
        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("🔍 Filter files by name...")
        self.inp_search.setMinimumHeight(40)
        self.inp_search.textChanged.connect(self.filter_rows)
        
        search_layout.addWidget(self.inp_search)
        layout.addLayout(search_layout)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setObjectName("MediaTabs")

        self.tab_media = self.build_tab("media")
        self.tab_files = self.build_tab("files")
        self.tab_links = self.build_tab("links")

        self.tabs.addTab(self.tab_media, f"Media ({len(self.messages.get('media', []))})")
        self.tabs.addTab(self.tab_files, f"Files ({len(self.messages.get('files', []))})")
        self.tabs.addTab(self.tab_links, f"Links ({len(self.messages.get('links', []))})")

        layout.addWidget(self.tabs)

        # Bottom Actions
        bottom_layout = QHBoxLayout()
        
        self.lbl_selected_count = QLabel("0 files selected")
        self.lbl_selected_count.setObjectName("DialogStatus")
        
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
        btn_none = QPushButton("Clear All")
        btn_none.setObjectName("SecondaryButton")
        
        btn_all.clicked.connect(lambda: self.set_all_rows(tab_key, True))
        btn_none.clicked.connect(lambda: self.set_all_rows(tab_key, False))
        
        t_layout.addWidget(btn_all)
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
            row.stateChanged.connect(self.update_selected_count)
            self.rows[tab_key].append(row)
            list_layout.addWidget(row)

        scroll.setWidget(list_container)
        layout.addWidget(scroll)
        
        return tab_widget

    def set_all_rows(self, tab_key, state):
        for row in self.rows.get(tab_key, []):
            row.setChecked(state)

    def filter_rows(self, text):
        search_text = text.lower().strip()
        for tab_rows in self.rows.values():
            for row in tab_rows:
                # Basic name matching
                title = row.lbl_title.text().lower()
                row.setVisible(search_text in title)

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
