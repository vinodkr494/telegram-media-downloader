from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QProgressBar, QSizePolicy, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QSize
import os

# Styles are now moved to dark_style.qss and style.qss


class DownloadCard(QWidget):
    def __init__(self, task_id, title, total_items, folder_name, media_type, parent_worker,
                 completed=0, is_paused=False, download_path="downloads", download_limit=5,
                 max_speed_kb=0, files_metadata=None):
        super().__init__()
        self.task_id       = task_id
        self.title         = title
        self.total_items   = total_items
        self.folder_name   = folder_name
        self.parent_worker = parent_worker
        self.completed     = completed
        self.download_path = download_path
        self.download_limit= download_limit
        self.max_speed_kb  = max_speed_kb
        self.files_metadata= files_metadata or []
        self.file_rows     = {}
        self.is_expanded   = False
        self.is_paused     = is_paused
        self.last_speed_val= 0 # KB/s
        
        self.setup_ui(media_type)
        self.populate_files()
        self.connect_buttons()

    def connect_buttons(self):
        self.btn_trash.clicked.connect(lambda checked=False: self.removeRequested.emit(self.task_id))
        self.btn_up.clicked.connect(lambda checked=False: self.moveUpRequested.emit(self.task_id))
        self.btn_down.clicked.connect(lambda checked=False: self.moveDownRequested.emit(self.task_id))

    removeRequested = Signal(str)
    moveUpRequested = Signal(str)
    moveDownRequested = Signal(str)
    reselectRequested = Signal(str)

    # ──────────────────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────────────────
    def setup_ui(self, media_type):
        self.setAttribute(Qt.WA_StyledBackground, True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 8)
        outer.setSpacing(0)

        # ── main card frame ─────────────────────────────────────────────────
        self.card_main = QFrame()
        self.card_main.setObjectName("DownloadCardFrame")

        ml = QHBoxLayout(self.card_main)
        ml.setContentsMargins(18, 16, 18, 16)
        ml.setSpacing(16)

        # badge
        badge_text = {1:"IMG",2:"VID",3:"PDF",4:"ZIP",5:"AUD",6:"ALL"}.get(media_type,"ALL")
        badge = QLabel(badge_text)
        badge.setObjectName("MediaTypeBadge")
        badge.setAlignment(Qt.AlignCenter)
        ml.addWidget(badge, alignment=Qt.AlignTop)

        # right column
        rc = QVBoxLayout()
        rc.setSpacing(8)

        # row 1 – title + status badge
        tr = QHBoxLayout()
        self.lbl_title = QLabel(self.title)
        self.lbl_title.setObjectName("CardTitle")
        self.lbl_title.setWordWrap(True)

        self.lbl_status_text = QLabel("Downloading…")
        self.lbl_status_text.setObjectName("StatusBadge")
        self.lbl_status_text.setProperty("state", "active")

        tr.addWidget(self.lbl_title, stretch=1)
        tr.addWidget(self.lbl_status_text)
        rc.addLayout(tr)

        # row 2 – media pill
        pr = QHBoxLayout()
        pill_label = {1:"◈ Images",2:"◈ Videos",3:"◈ PDFs",
                      4:"◈ ZIPs",5:"◈ Audio",6:"◈ All Media"}.get(media_type,"◈ All Media")
        lbl_pill = QLabel(pill_label)
        lbl_pill.setObjectName("TypePill")
        pr.addWidget(lbl_pill)
        pr.addStretch()
        rc.addLayout(pr)

        # row 3 – batch progress bar + count label
        self.batch_progress_bar = QProgressBar()
        self.batch_progress_bar.setFixedHeight(20)
        self.batch_progress_bar.setAlignment(Qt.AlignCenter)
        self.batch_progress_bar.setFormat("%p%")
        self.batch_progress_bar.setMaximum(max(self.total_items, 1))
        self.batch_progress_bar.setValue(self.completed)
        self.batch_progress_bar.setProperty("state", "active")
        rc.addWidget(self.batch_progress_bar)

        self.lbl_status = QLabel(f"Downloaded {self.completed} out of {self.total_items} items")
        self.lbl_status.setObjectName("MutedText")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        rc.addWidget(self.lbl_status)

        # row 3.5 - verify status (hidden by default)
        self.lbl_verify_status = QLabel("")
        self.lbl_verify_status.setObjectName("MutedText")
        self.lbl_verify_status.setAlignment(Qt.AlignCenter)
        self.lbl_verify_status.setStyleSheet("color: #FBBF24; font-weight: bold;")
        self.lbl_verify_status.setVisible(False)
        rc.addWidget(self.lbl_verify_status)

        # row 4 – action buttons
        ar = QHBoxLayout()
        ar.setSpacing(6)

        self.btn_pause = QPushButton("▶ Resume" if self.is_paused else "⏸ Pause")
        self.btn_pause.setObjectName("CardButton")
        self.btn_pause.clicked.connect(self.toggle_pause)

        self.btn_folder = QPushButton("📂 Folder")
        self.btn_folder.setObjectName("CardButton")
        self.btn_folder.clicked.connect(self.open_folder)

        self.btn_verify = QPushButton("🛡️ Verify")
        self.btn_verify.setObjectName("CardButton")
        self.btn_verify.clicked.connect(self.run_health_check)

        self.btn_trash = QPushButton("🗑 Remove")
        self.btn_trash.setObjectName("CardButton")

        self.btn_reselect = QPushButton("🔄 Re-select")
        self.btn_reselect.setObjectName("CardButton")
        self.btn_reselect.setToolTip("Add or remove files for this specific task")
        self.btn_reselect.clicked.connect(lambda checked=False: self.reselectRequested.emit(self.task_id))

        ar.addWidget(self.btn_pause)
        ar.addWidget(self.btn_folder)
        ar.addWidget(self.btn_verify)
        ar.addWidget(self.btn_reselect)
        ar.addWidget(self.btn_trash)
        ar.addStretch()

        self.btn_up = QPushButton("⬆")
        self.btn_up.setFixedWidth(30)
        self.btn_up.setObjectName("CardButtonCompact")
        self.btn_up.setToolTip("Move queue item UP")

        self.btn_down = QPushButton("⬇")
        self.btn_down.setFixedWidth(30)
        self.btn_down.setObjectName("CardButtonCompact")
        self.btn_down.setToolTip("Move queue item DOWN")

        self.btn_expand = QPushButton("▼ Files")
        self.btn_expand.setObjectName("ExpandButton")
        self.btn_expand.setCursor(Qt.PointingHandCursor)
        self.btn_expand.clicked.connect(self.toggle_expand)

        ar.addWidget(self.btn_up)
        ar.addWidget(self.btn_down)
        ar.addWidget(self.btn_expand)

        rc.addLayout(ar)
        ml.addLayout(rc, stretch=1)
        outer.addWidget(self.card_main)

        # ── expand area ─────────────────────────────────────────────────────
        self.expand_area = QFrame()
        self.expand_area.setVisible(False)
        self.expand_area.setObjectName("expandArea")

        ea_layout = QVBoxLayout(self.expand_area)
        ea_layout.setContentsMargins(12, 4, 12, 4)
        ea_layout.setSpacing(8)

        hdr = QLabel("FILES IN THIS QUEUE")
        hdr.setObjectName("queueHeader")
        ea_layout.addWidget(hdr)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setMaximumHeight(260)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setObjectName("queueScroll")

        self.files_container = QWidget()
        self.files_container.setObjectName("filesContainer")

        self.files_layout = QVBoxLayout(self.files_container)
        self.files_layout.setContentsMargins(0, 0, 0, 0)
        self.files_layout.setSpacing(6)
        self.files_layout.addStretch()

        self.scroll.setWidget(self.files_container)
        ea_layout.addWidget(self.scroll)

        # Styles are now controlled by object names in QSS

        outer.addWidget(self.expand_area)

        # apply initial state visually
        if self.is_paused:
            self.btn_pause.setText("▶ Resume")
            self.lbl_status_text.setText("Paused")
            self.lbl_status_text.setProperty("state", "paused")
            self.batch_progress_bar.setProperty("state", "paused")
        else:
            self.btn_pause.setText("⏸ Pause")
            self.lbl_status_text.setText("Downloading…")
            self.lbl_status_text.setProperty("state", "active")
            self.batch_progress_bar.setProperty("state", "active")

        # Initial style application
        self.lbl_status_text.style().unpolish(self.lbl_status_text)
        self.lbl_status_text.style().polish(self.lbl_status_text)
        self.batch_progress_bar.style().unpolish(self.batch_progress_bar)
        self.batch_progress_bar.style().polish(self.batch_progress_bar)

    # ──────────────────────────────────────────────────────────────────────────
    # Slots
    # ──────────────────────────────────────────────────────────────────────────
    def toggle_expand(self):
        self.is_expanded = not self.is_expanded
        self.expand_area.setVisible(self.is_expanded)
        self.btn_expand.setText("▲ Files" if self.is_expanded else "▼ Files")

    def mouseDoubleClickEvent(self, event):
        self.open_folder()
        super().mouseDoubleClickEvent(event)

    def refresh_from_metadata(self, title, total_items, completed, files_metadata, is_paused=None):
        if total_items is None:
            total_items = 0
            
        self.title         = title
        self.total_items   = total_items
        self.completed     = completed
        self.files_metadata= files_metadata or []
        self.lbl_title.setText(title)
        self.batch_progress_bar.setMaximum(max(total_items, 1))
        self.batch_progress_bar.setValue(completed)
        self.lbl_status.setText(f"Downloaded {completed} out of {total_items} items")
        
        # Sync pause/completed status if we now have pending items
        if total_items > completed:
            state_val = "active"
            if is_paused is not None:
                self.is_paused = is_paused
                self.btn_pause.setText("▶ Resume" if is_paused else "⏸ Pause")
                self.lbl_status_text.setText("Paused" if is_paused else "Downloading…")
                state_val = "paused" if is_paused else "active"
            
            self.btn_pause.setEnabled(True)
            self.lbl_status_text.setProperty("state", state_val)
            self.batch_progress_bar.setProperty("state", state_val)
        elif total_items > 0 and completed >= total_items:
            self._set_completed_style()
            self.btn_pause.setEnabled(False)
        
        # Force style refresh for properties
        self.lbl_status_text.style().unpolish(self.lbl_status_text)
        self.lbl_status_text.style().polish(self.lbl_status_text)
        self.batch_progress_bar.style().unpolish(self.batch_progress_bar)
        self.batch_progress_bar.style().polish(self.batch_progress_bar)

        for i in reversed(range(self.files_layout.count())):
            w = self.files_layout.itemAt(i).widget()
            if w:
                w.setParent(None); w.deleteLater()
        self.file_rows.clear()
        self.populate_files()

    def update_progress(self, current, total):
        if total != self.total_items:
            self.total_items = total
            self.batch_progress_bar.setMaximum(max(total, 1))
        self.batch_progress_bar.setValue(current)
        self.completed = current
        self.lbl_status.setText(f"Downloaded {current} out of {total} items")
        
        # Only mark as completed if total > 0 (it may be 0 while still loading metadata)
        if total > 0 and current >= total:
            self._set_completed_style()
            self.btn_pause.setEnabled(False)

    def _set_completed_style(self):
        self.lbl_status_text.setText("Completed ✓")
        self.lbl_status_text.setProperty("state", "completed")
        self.batch_progress_bar.setProperty("state", "completed")
        self.lbl_status_text.style().unpolish(self.lbl_status_text)
        self.lbl_status_text.style().polish(self.lbl_status_text)
        self.batch_progress_bar.style().unpolish(self.batch_progress_bar)
        self.batch_progress_bar.style().polish(self.batch_progress_bar)

    def populate_files(self):
        def fmt(size):
            if size == 0: return "—"
            for unit in ["B","KB","MB","GB"]:
                if size < 1024: return f"{size:.1f} {unit}"
                size /= 1024
            return f"{size:.1f} GB"
        for idx, meta in enumerate(self.files_metadata):
            row = FileRow(meta["id"], meta["name"], fmt(meta["size"]), idx)
            if meta.get("completed"):
                row.set_completed()
            self.files_layout.addWidget(row)
            self.file_rows[meta["id"]] = row

    def update_file_progress(self, msg_id, current_bytes, total_bytes, speed_str):
        self.lbl_status_text.setText(f"⬇ {speed_str}")
        
        # Extract numeric speed for global stats (e.g. "450 KB/s" -> 450)
        import re
        match = re.search(r'([\d.]+)\s*([KMG]?B/s)', speed_str)
        if match:
            val = float(match.group(1))
            unit = match.group(2)
            if 'MB/s' in unit: val *= 1024
            elif 'GB/s' in unit: val *= 1024 * 1024
            self.last_speed_val = val
        else:
            self.last_speed_val = 0

        self.lbl_status_text.setProperty("state", "active")
        self.lbl_status_text.style().unpolish(self.lbl_status_text)
        self.lbl_status_text.style().polish(self.lbl_status_text)
        if msg_id in self.file_rows:
            self.file_rows[msg_id].set_progress(current_bytes, total_bytes)

    def mark_file_completed(self, msg_id):
        if msg_id in self.file_rows:
            self.file_rows[msg_id].set_completed()

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.parent_worker.pause_download(self.task_id)
            self.btn_pause.setText("▶ Resume")
            self.lbl_status_text.setText("Paused")
            self.lbl_status_text.setProperty("state", "paused")
            self.batch_progress_bar.setProperty("state", "paused")
        else:
            parts = self.task_id.split('_')
            topic_id = None
            if len(parts) == 3:
                channel_input, topic_id_str, media_id_str = parts
                channel_input = f"{channel_input}_{topic_id_str}"
                media_id = int(media_id_str)
            else:
                channel_input, media_id_str = parts
                media_id = int(media_id_str)
                
            self.parent_worker.start_download(
                channel_input=channel_input, media_id=media_id,
                download_path=self.download_path, download_limit=self.download_limit,
                max_speed_kb=self.max_speed_kb, task_id=self.task_id)
            self.btn_pause.setText("⏸ Pause")
            self.lbl_status_text.setText("Downloading…")
            self.lbl_status_text.setProperty("state", "active")
            self.batch_progress_bar.setProperty("state", "active")
        
        # Force style refresh for properties
        self.lbl_status_text.style().unpolish(self.lbl_status_text)
        self.lbl_status_text.style().polish(self.lbl_status_text)
        self.batch_progress_bar.style().unpolish(self.batch_progress_bar)
        self.batch_progress_bar.style().polish(self.batch_progress_bar)

    def run_health_check(self):
        self.btn_verify.setEnabled(False)
        self.btn_verify.setText("🛡️ Verifying...")
        self.lbl_verify_status.setVisible(True)
        self.lbl_verify_status.setText("Checking file integrity...")
        
        # We'll do a basic size check first locally
        corrupt = 0
        missing = 0
        valid = 0
        
        for msg_id, row in self.file_rows.items():
            # Find metadata
            meta = next((m for m in self.files_metadata if m["id"] == msg_id), None)
            if not meta: continue
            
            fpath = os.path.join(self.folder_name, meta["name"])
            if not os.path.exists(fpath):
                missing += 1
                row.icon.setText("❓")
                row.bar.setProperty("state", "idle")
            else:
                actual_size = os.path.getsize(fpath)
                if meta["size"] > 0 and actual_size != meta["size"]:
                    corrupt += 1
                    row.icon.setText("⚠️")
                    row.bar.setProperty("state", "paused")
                else:
                    valid += 1
                    row.icon.setText("✅")
                    row.bar.setProperty("state", "completed")
            row.bar.style().unpolish(row.bar)
            row.bar.style().polish(row.bar)
            
        if corrupt > 0 or missing > 0:
            self.lbl_verify_status.setText(f"Done: {valid} OK, {corrupt} Corrupt, {missing} Missing")
            self.lbl_verify_status.setStyleSheet("color: #EF4444;") # Red
            self.btn_verify.setText("🛡️ Fix 0%?") # Mock button text change
        else:
            self.lbl_verify_status.setText("All files verified successfully!")
            self.lbl_verify_status.setStyleSheet("color: #10B981;") # Green
            
        self.btn_verify.setEnabled(True)
        self.btn_verify.setText("🛡️ Verify")

    def set_reselect_loading(self, loading):
        if loading:
            self.btn_reselect.setText("⏳ Loading...")
            self.btn_reselect.setEnabled(False)
        else:
            self.btn_reselect.setText("🔄 Re-select")
            self.btn_reselect.setEnabled(True)

    def open_folder(self):
        if os.path.exists(self.folder_name):
            if os.name == 'nt':
                os.startfile(self.folder_name)
            else:
                os.system(f"xdg-open '{self.folder_name}'")


# ──────────────────────────────────────────────────────────────────────────────
# FileRow – shown in the expand area
# ──────────────────────────────────────────────────────────────────────────────
class FileRow(QWidget):
    def __init__(self, msg_id, filename, size_str, row_index=0):
        super().__init__()
        self.setObjectName("FileRow")
        self.setProperty("alt", row_index % 2 == 1)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(34) # Slightly taller for better readability

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 10, 0)
        layout.setSpacing(8)

        self.icon = QLabel("⏳")
        self.icon.setFixedWidth(18)
        self.icon.setObjectName("FileRowIcon")

        self.lbl_name = QLabel(filename)
        self.lbl_name.setObjectName("FileRowName")

        self.lbl_size = QLabel(size_str)
        self.lbl_size.setFixedWidth(58)
        self.lbl_size.setObjectName("FileRowSize")
        self.lbl_size.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.bar = QProgressBar()
        self.bar.setFixedHeight(5)
        self.bar.setFixedWidth(100)
        self.bar.setTextVisible(False)
        self.bar.setMaximum(100)
        self.bar.setValue(0)
        self.bar.setObjectName("FileProgressBar")
        self.bar.setProperty("state", "idle")

        layout.addWidget(self.icon)
        layout.addWidget(self.lbl_name, stretch=3)
        layout.addWidget(self.lbl_size)
        layout.addWidget(self.bar)

    def set_progress(self, current, total):
        if total:
            pct = int(current * 100 / total)
            self.bar.setValue(pct)
        self.bar.setProperty("state", "active")
        self.bar.style().unpolish(self.bar)
        self.bar.style().polish(self.bar)
        self.icon.setText("⬇️")

    def set_completed(self):
        self.bar.setValue(100)
        self.bar.setProperty("state", "completed")
        self.bar.style().unpolish(self.bar)
        self.bar.style().polish(self.bar)
        self.icon.setText("✅")
