from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QFrame, QPushButton
)
from PySide6.QtCore import Qt

class DownloadsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 40)
        layout.setSpacing(24)

        # Main Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        self.content_container = QWidget()
        
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setAlignment(Qt.AlignTop)
        self.content_layout.setSpacing(24)

        # 1. Header & Global Controls
        header_row = QHBoxLayout()
        self.lbl_active = QLabel("Active Downloads")
        self.lbl_active.setObjectName("MainHeader")
        
        self.btn_pause_all = QPushButton("⏸ Pause All")
        self.btn_pause_all.setObjectName("SecondaryButton")
        self.btn_pause_all.setCursor(Qt.PointingHandCursor)
        
        self.btn_resume_all = QPushButton("▶ Resume All")
        self.btn_resume_all.setObjectName("SecondaryButton")
        self.btn_resume_all.setCursor(Qt.PointingHandCursor)
        
        header_row.addWidget(self.lbl_active)
        header_row.addStretch()
        header_row.addWidget(self.btn_pause_all)
        header_row.addWidget(self.btn_resume_all)
        
        # Hide until there are active downloads
        self.btn_pause_all.hide()
        self.btn_resume_all.hide()
        
        self.content_layout.addLayout(header_row)

        self.active_container = QWidget()
        
        self.active_layout = QVBoxLayout(self.active_container)
        self.active_layout.setAlignment(Qt.AlignTop)
        self.active_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.addWidget(self.active_container)

        # 2. Completed Downloads Section
        self.lbl_completed = QLabel("Completed")
        self.lbl_completed.setObjectName("MainHeader")
        self.content_layout.addWidget(self.lbl_completed)

        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setAlignment(Qt.AlignTop)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        
        # Placeholder
        self.empty_lbl = QLabel("No completed downloads yet.")
        self.empty_lbl.setObjectName("MutedText")
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        self.history_layout.addWidget(self.empty_lbl)
        
        self.content_layout.addWidget(self.history_container)
        
        self.scroll_area.setWidget(self.content_container)
        layout.addWidget(self.scroll_area)

    def set_controls_visible(self, visible):
        """Show/hide the global Pause All / Resume All buttons."""
        if visible:
            self.btn_pause_all.show()
            self.btn_resume_all.show()
        else:
            self.btn_pause_all.hide()
            self.btn_resume_all.hide()

    def add_completed_item(self, title, folder_name):
        self.empty_lbl.hide()
        
        item = QFrame()
        item.setObjectName("WhiteCard")
        item.setProperty("compact", True)
        
        item_layout = QVBoxLayout(item)
        item_layout.setContentsMargins(16, 16, 16, 16)
        
        lbl_title = QLabel(f"✅ {title}")
        lbl_title.setObjectName("CardTitle")
        
        lbl_folder = QLabel(f"Saved to: {folder_name}")
        lbl_folder.setObjectName("MutedText")
        lbl_folder.setStyleSheet("font-size: 11px;")
        
        item_layout.addWidget(lbl_title)
        item_layout.addWidget(lbl_folder)
        
        self.history_layout.insertWidget(0, item)
