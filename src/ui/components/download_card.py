from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QProgressBar, QSizePolicy, QFrame, QScrollArea
)
from PySide6.QtCore import Qt
import os

_BTN_STYLE = (
    "QPushButton { background-color: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 5px;"
    " color: #334155; font-size: 12px; padding: 4px 10px; }"
    "QPushButton:hover { background-color: #E2E8F0; }"
    "QPushButton:disabled { color: #94A3B8; }"
)

_BATCH_BAR_DEFAULT = (
    "QProgressBar { background-color: #E2E8F0; border: none; border-radius: 5px;"
    " color: white; font-weight: bold; font-size: 12px; }"
    "QProgressBar::chunk { background-color: #2BA5E4; border-radius: 5px; }"
)
_BATCH_BAR_PAUSED = (
    "QProgressBar { background-color: #E2E8F0; border: none; border-radius: 5px;"
    " color: white; font-weight: bold; font-size: 12px; }"
    "QProgressBar::chunk { background-color: #94A3B8; border-radius: 5px; }"
)
_BATCH_BAR_DONE = (
    "QProgressBar { background-color: #E2E8F0; border: none; border-radius: 5px;"
    " color: white; font-weight: bold; font-size: 12px; }"
    "QProgressBar::chunk { background-color: #10B981; border-radius: 5px; }"
)


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
        self.setup_ui(media_type)
        self.populate_files()

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
        self.card_main.setStyleSheet(
            "QFrame { background-color:#FFFFFF; border-radius:10px;"
            " border:1px solid #E2E8F0; }")

        ml = QHBoxLayout(self.card_main)
        ml.setContentsMargins(18, 16, 18, 16)
        ml.setSpacing(16)

        # badge
        badge_text = {1:"IMG",2:"VID",3:"PDF",4:"ZIP",5:"AUD",6:"ALL"}.get(media_type,"ALL")
        badge = QLabel(badge_text)
        badge.setFixedSize(60, 60)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            "background:#2BA5E4; border-radius:30px; color:#fff;"
            " font-size:13px; font-weight:700;")
        ml.addWidget(badge, alignment=Qt.AlignTop)

        # right column
        rc = QVBoxLayout()
        rc.setSpacing(8)

        # row 1 – title + status badge
        tr = QHBoxLayout()
        self.lbl_title = QLabel(self.title)
        self.lbl_title.setStyleSheet("font-weight:700; font-size:14px; color:#1E293B;")
        self.lbl_title.setWordWrap(True)

        self.lbl_status_text = QLabel("Downloading…")
        self.lbl_status_text.setStyleSheet(
            "color:#F59E0B; font-weight:700; font-size:11px; padding:2px 6px;"
            " background:#FEF3C7; border-radius:4px;")

        tr.addWidget(self.lbl_title, stretch=1)
        tr.addWidget(self.lbl_status_text)
        rc.addLayout(tr)

        # row 2 – media pill
        pr = QHBoxLayout()
        pill_label = {1:"◈ Images",2:"◈ Videos",3:"◈ PDFs",
                      4:"◈ ZIPs",5:"◈ Audio",6:"◈ All Media"}.get(media_type,"◈ All Media")
        lbl_pill = QLabel(pill_label)
        lbl_pill.setStyleSheet(
            "background:#E0F2FE; color:#0284C7; border-radius:4px;"
            " padding:3px 8px; font-size:11px; font-weight:600;")
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
        self.batch_progress_bar.setStyleSheet(_BATCH_BAR_DEFAULT)
        rc.addWidget(self.batch_progress_bar)

        self.lbl_status = QLabel(f"Downloaded {self.completed} out of {self.total_items} items")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("color:#475569; font-size:12px;")
        rc.addWidget(self.lbl_status)

        # row 4 – action buttons
        ar = QHBoxLayout()
        ar.setSpacing(6)

        self.btn_pause = QPushButton("▶ Resume" if self.is_paused else "⏸ Pause")
        self.btn_pause.setStyleSheet(_BTN_STYLE)
        self.btn_pause.clicked.connect(self.toggle_pause)

        self.btn_folder = QPushButton("📂 Folder")
        self.btn_folder.setStyleSheet(_BTN_STYLE)
        self.btn_folder.clicked.connect(self.open_folder)

        self.btn_trash = QPushButton("🗑 Remove")
        self.btn_trash.setStyleSheet(_BTN_STYLE)

        ar.addWidget(self.btn_pause)
        ar.addWidget(self.btn_folder)
        ar.addWidget(self.btn_trash)
        ar.addStretch()

        self.btn_up = QPushButton("⬆")
        self.btn_up.setFixedWidth(30)
        self.btn_up.setStyleSheet(_BTN_STYLE)
        self.btn_up.setToolTip("Move queue item UP")

        self.btn_down = QPushButton("⬇")
        self.btn_down.setFixedWidth(30)
        self.btn_down.setStyleSheet(_BTN_STYLE)
        self.btn_down.setToolTip("Move queue item DOWN")

        self.btn_expand = QPushButton("▼ Files")
        self.btn_expand.setStyleSheet(
            "QPushButton { color:#2BA5E4; font-weight:700; font-size:12px;"
            " background:transparent; border:none; padding:4px 8px; }"
            "QPushButton:hover { text-decoration: underline; }")
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
        ea_layout.setContentsMargins(12, 10, 12, 10)
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

        self.expand_area.setStyleSheet("""
        #expandArea {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-top: none;
            border-bottom-left-radius: 12px;
            border-bottom-right-radius: 12px;
        }

        #queueHeader {
            color: #94a3b8;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1px;
            padding: 2px 2px 2px 2px;
            background: transparent;
            border: none;
        }

        #queueScroll {
            background: transparent;
            border: none;
        }

        #queueScroll > QWidget > QWidget {
            background: transparent;
        }

        #filesContainer {
            background: transparent;
        }

        QScrollBar:vertical {
            background: transparent;
            width: 10px;
            margin: 2px 0 2px 0;
        }

        QScrollBar::handle:vertical {
            background: #cbd5e1;
            border-radius: 5px;
            min-height: 24px;
        }

        QScrollBar::handle:vertical:hover {
            background: #94a3b8;
        }

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {
            background: none;
            border: none;
        }
        """)

        outer.addWidget(self.expand_area)

        # apply paused state
        if self.is_paused:
            self.is_paused = False
            self.toggle_pause()
            self.batch_progress_bar.setValue(self.completed)

    # ──────────────────────────────────────────────────────────────────────────
    # Slots
    # ──────────────────────────────────────────────────────────────────────────
    def toggle_expand(self):
        self.is_expanded = not self.is_expanded
        self.expand_area.setVisible(self.is_expanded)
        self.btn_expand.setText("▲ Files" if self.is_expanded else "▼ Files")

    def refresh_from_metadata(self, title, total_items, completed, files_metadata):
        self.title         = title
        self.total_items   = total_items
        self.completed     = completed
        self.files_metadata= files_metadata or []
        self.lbl_title.setText(title)
        self.batch_progress_bar.setMaximum(max(total_items, 1))
        self.batch_progress_bar.setValue(completed)
        self.lbl_status.setText(f"Downloaded {completed} out of {total_items} items")
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
        self.lbl_status.setText(f"Downloaded {current} out of {total} items")
        if current >= total:
            self._set_completed_style()
            self.btn_pause.setEnabled(False)

    def _set_completed_style(self):
        self.lbl_status_text.setText("Completed ✓")
        self.lbl_status_text.setStyleSheet(
            "color:#10B981; font-weight:700; font-size:11px; padding:2px 6px;"
            " background:#D1FAE5; border-radius:4px;")
        self.batch_progress_bar.setStyleSheet(_BATCH_BAR_DONE)

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
        self.lbl_status_text.setStyleSheet(
            "color:#F59E0B; font-weight:700; font-size:11px; padding:2px 6px;"
            " background:#FEF3C7; border-radius:4px;")
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
            self.lbl_status_text.setStyleSheet(
                "color:#EF4444; font-weight:700; font-size:11px; padding:2px 6px;"
                " background:#FEE2E2; border-radius:4px;")
            self.batch_progress_bar.setStyleSheet(_BATCH_BAR_PAUSED)
        else:
            channel_input = self.task_id.split('_')[0]
            media_id      = int(self.task_id.split('_')[1])
            self.parent_worker.start_download(
                channel_input=channel_input, media_id=media_id,
                download_path=self.download_path, download_limit=self.download_limit,
                max_speed_kb=self.max_speed_kb)
            self.btn_pause.setText("⏸ Pause")
            self.lbl_status_text.setText("Downloading…")
            self.lbl_status_text.setStyleSheet(
                "color:#F59E0B; font-weight:700; font-size:11px; padding:2px 6px;"
                " background:#FEF3C7; border-radius:4px;")
            self.batch_progress_bar.setStyleSheet(_BATCH_BAR_DEFAULT)

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
        self.msg_id = msg_id
        bg = "#F8FAFC" if row_index % 2 == 0 else "#FFFFFF"
        self.setStyleSheet(f"QWidget {{ background:{bg}; border:none; }}")
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 10, 0)
        layout.setSpacing(8)

        self.icon = QLabel("⏳")
        self.icon.setFixedWidth(18)
        self.icon.setStyleSheet("border:none; font-size:12px;")

        self.lbl_name = QLabel(filename)
        self.lbl_name.setStyleSheet(
            "border:none; font-size:12px; color:#334155;")

        self.lbl_size = QLabel(size_str)
        self.lbl_size.setFixedWidth(58)
        self.lbl_size.setStyleSheet(
            "border:none; font-size:11px; color:#94A3B8;")
        self.lbl_size.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.bar = QProgressBar()
        self.bar.setFixedHeight(5)
        self.bar.setFixedWidth(100)
        self.bar.setTextVisible(False)
        self.bar.setMaximum(100)
        self.bar.setValue(0)
        self.bar.setStyleSheet(
            "QProgressBar { background:#E2E8F0; border:none; border-radius:2px; }"
            "QProgressBar::chunk { background:#CBD5E1; border-radius:2px; }")

        layout.addWidget(self.icon)
        layout.addWidget(self.lbl_name, stretch=3)
        layout.addWidget(self.lbl_size)
        layout.addWidget(self.bar)

    def set_progress(self, current, total):
        if total:
            pct = int(current * 100 / total)
            self.bar.setValue(pct)
        self.bar.setStyleSheet(
            "QProgressBar { background:#E2E8F0; border:none; border-radius:3px; }"
            "QProgressBar::chunk { background:#2BA5E4; border-radius:3px; }")
        self.icon.setText("⬇️")

    def set_completed(self):
        self.bar.setValue(100)
        self.bar.setStyleSheet(
            "QProgressBar { background:#E2E8F0; border:none; border-radius:3px; }"
            "QProgressBar::chunk { background:#10B981; border-radius:3px; }")
        self.icon.setText("✅")
