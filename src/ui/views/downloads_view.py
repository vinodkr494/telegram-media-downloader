from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QFrame, QPushButton
)
from PySide6.QtCore import Qt

class CompletedDownloadRow(QFrame):
    def __init__(self, title, folder_name, parent_view):
        super().__init__()
        self.title = title
        self.folder_name = folder_name
        self.parent_view = parent_view
        self.setObjectName("WhiteCard")
        self.setProperty("compact", True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        
        lbl_title = QLabel(f"✅ {self.title}")
        lbl_title.setObjectName("CardTitle")
        
        lbl_folder = QLabel(f"Saved to: {self.folder_name}")
        lbl_folder.setObjectName("MutedText")
        lbl_folder.setStyleSheet("font-size: 8.5pt;")
        
        btn_layout = QHBoxLayout()
        btn_open = QPushButton("📂 Open Folder")
        btn_open.setObjectName("PrimaryRowButton")
        btn_open.setCursor(Qt.PointingHandCursor)
        btn_open.clicked.connect(lambda: self.parent_view.open_folder(self.folder_name))
        
        btn_layout.addWidget(btn_open)
        btn_layout.addStretch()
        
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_folder)
        layout.addLayout(btn_layout)

    def show_context_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction, QClipboard
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        
        menu = QMenu(self)
        action_open = menu.addAction("📂 Open Folder")
        action_copy = menu.addAction("📋 Copy Full Path")
        menu.addSeparator()
        action_remove = menu.addAction("🗑 Clear from History")
        
        action = menu.exec(self.mapToGlobal(pos))
        
        if action == action_open:
            self.parent_view.open_folder(self.folder_name)
        elif action == action_copy:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(os.path.abspath(self.folder_name))
        elif action == action_remove:
            self.deleteLater()
            # If it was the last row, show the empty label
            # We check if this is the only child of parent's history_layout
            if self.parent_view.history_layout.count() <= 1:
                self.parent_view.empty_lbl.show()

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
        completed_header_row = QHBoxLayout()
        self.lbl_completed = QLabel("Completed")
        self.lbl_completed.setObjectName("MainHeader")
        
        self.btn_clear_history = QPushButton("🗑 Clear History")
        self.btn_clear_history.setObjectName("SecondaryButton")
        self.btn_clear_history.setCursor(Qt.PointingHandCursor)
        self.btn_clear_history.clicked.connect(self.clear_history)
        
        completed_header_row.addWidget(self.lbl_completed)
        completed_header_row.addStretch()
        completed_header_row.addWidget(self.btn_clear_history)
        
        self.content_layout.addLayout(completed_header_row)

        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setAlignment(Qt.AlignTop)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        
        # Placeholder
        self.empty_lbl = QLabel("No completed downloads yet.")
        self.empty_lbl.setObjectName("MutedText")
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.empty_lbl)
        
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
        row = CompletedDownloadRow(title, folder_name, self)
        self.history_layout.insertWidget(0, row)

    def open_folder(self, path):
        import os
        if os.path.exists(path):
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))

    def clear_history(self):
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.empty_lbl.show()
