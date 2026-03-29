import os
import humanize
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTabWidget, QWidget, QScrollArea,
    QCheckBox, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

class MediaBrowserDialog(QDialog):
    def __init__(self, channel_title, messages_dict, parent=None):
        """
        messages_dict: {
            "media": [message_objects...],
            "files": [message_objects...],
            "links": [message_objects...]
        }
        """
        super().__init__(parent)
        self.setWindowTitle(f"Media Browser - {channel_title}")
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "logo.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.setMinimumSize(600, 500)
        self.setObjectName("WhiteCard")
        # Ensure dialog uses the white card styling implicitly
        self.setStyleSheet("QDialog { background-color: #F8FAFC; }")

        self.messages = messages_dict
        self.selected_messages = []
        
        # Store references to all checkboxes so we can "Select All"
        self.checkboxes = {} # tab_name -> list of QCheckBox
        
        self.setup_ui(channel_title)

    def setup_ui(self, channel_title):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                background: #E2E8F0;
                color: #64748B;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: bold;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: #2BA5E4;
                color: #FFFFFF;
            }
            QTabWidget::pane {
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                background: #FFFFFF;
            }
        """)

        # Build tabs
        self.tab_media = self.build_tab("media")
        self.tab_files = self.build_tab("files")
        self.tab_links = self.build_tab("links")

        self.tabs.addTab(self.tab_media, f"Media ({len(self.messages.get('media', []))})")
        self.tabs.addTab(self.tab_files, f"Files ({len(self.messages.get('files', []))})")
        self.tabs.addTab(self.tab_links, f"Links ({len(self.messages.get('links', []))})")

        layout.addWidget(self.tabs)

        # Bottom Status & Action Row
        bottom_layout = QHBoxLayout()
        
        self.lbl_selected_count = QLabel("0 files selected")
        self.lbl_selected_count.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px;")
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_download = QPushButton("Download Selected")
        self.btn_download.setObjectName("SuccessButton")
        self.btn_download.clicked.connect(self.accept)

        bottom_layout.addWidget(self.lbl_selected_count)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_cancel)
        bottom_layout.addWidget(self.btn_download)

        layout.addLayout(bottom_layout)

    def build_tab(self, tab_key):
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Tools row
        tools_layout = QHBoxLayout()
        btn_select_all = QPushButton("Select All")
        btn_select_all.setObjectName("PrimaryButton")
        btn_clear_all = QPushButton("Clear All")
        btn_clear_all.setObjectName("PrimaryButton")
        
        btn_select_all.clicked.connect(lambda: self.set_all_checkboxes(tab_key, True))
        btn_clear_all.clicked.connect(lambda: self.set_all_checkboxes(tab_key, False))
        
        tools_layout.addWidget(btn_select_all)
        tools_layout.addWidget(btn_clear_all)
        tools_layout.addStretch()
        layout.addLayout(tools_layout)

        # Scrollable list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QWidget#list_bg { background-color: #FFFFFF; }")
        
        list_container = QWidget()
        list_container.setObjectName("list_bg")
        list_layout = QVBoxLayout(list_container)
        list_layout.setAlignment(Qt.AlignTop)
        
        self.checkboxes[tab_key] = []
        
        messages = self.messages.get(tab_key, [])
        for msg in messages:
            msg_size = getattr(msg, 'document', None) and getattr(msg.document, 'size', 0)
            size_str = humanize.naturalsize(msg_size) if msg_size else "Unknown size"
            date_str = msg.date.strftime("%Y-%m-%d %H:%M") if getattr(msg, 'date', None) else ""
            
            # Use message ID or text preview as title
            title = f"Message ID: {msg.id}"
            if msg.message:
                title = msg.message[:50] + "..." if len(msg.message) > 50 else msg.message
            elif getattr(msg, 'file', None) and getattr(msg.file, 'name', None):
                title = msg.file.name
                
            cb_text = f"{title} ({size_str})\n{date_str}"
            cb = QCheckBox(cb_text)
            cb.setStyleSheet("QCheckBox { font-size: 12px; color: #334155; margin-bottom: 8px; }")
            cb.setProperty("msg_obj", msg) # Store the actual telethon message object
            cb.stateChanged.connect(self.update_selected_count)
            
            self.checkboxes[tab_key].append(cb)
            list_layout.addWidget(cb)
            
            # Divider
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            line.setStyleSheet("background-color: #F1F5F9;")
            list_layout.addWidget(line)

        scroll.setWidget(list_container)
        layout.addWidget(scroll)
        
        return tab_widget

    def set_all_checkboxes(self, tab_key, state):
        for cb in self.checkboxes.get(tab_key, []):
            cb.setChecked(state)

    def update_selected_count(self):
        count = 0
        self.selected_messages.clear()
        
        for tab_boxes in self.checkboxes.values():
            for cb in tab_boxes:
                if cb.isChecked():
                    count += 1
                    self.selected_messages.append(cb.property("msg_obj"))
                    
        self.lbl_selected_count.setText(f"{count} files selected")

    def get_selected_messages(self):
        return self.selected_messages
