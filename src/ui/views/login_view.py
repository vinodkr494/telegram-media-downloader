from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, 
    QLineEdit, QPushButton, QStackedWidget, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QIcon
import os

class LoginView(QWidget):
    login_started = Signal(str, str, str)   # api_id, api_hash, phone
    code_submitted = Signal(str)            # code
    password_submitted = Signal(str)        # password

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_env_defaults()

    def setup_ui(self):
        self.setStyleSheet("background-color: #F1F5F9;")
        
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignCenter)

        # ── card ────────────────────────────────────────────────────────────
        self.card = QFrame()
        self.card.setObjectName("WhiteCard")
        self.card.setFixedWidth(420)
        self.card.setMaximumHeight(520)
        self.card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(36, 28, 36, 32)
        card_layout.setSpacing(0)

        # ── logo + app name ─────────────────────────────────────────────────
        logo_row = QVBoxLayout()
        logo_row.setAlignment(Qt.AlignCenter)
        logo_row.setSpacing(6)

        logo_lbl = QLabel()
        logo_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..", "assets", "logo.png"))
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
        logo_lbl.setAlignment(Qt.AlignCenter)

        lbl_app = QLabel("Telegram Downloader")
        lbl_app.setStyleSheet(
            "font-size: 17px; font-weight: 700; color: #1E293B; letter-spacing: 0.3px;")
        lbl_app.setAlignment(Qt.AlignCenter)

        logo_row.addWidget(logo_lbl)
        logo_row.addWidget(lbl_app)
        card_layout.addLayout(logo_row)
        card_layout.addSpacing(16)

        # ── divider ─────────────────────────────────────────────────────────
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #E2E8F0;")
        card_layout.addWidget(divider)
        card_layout.addSpacing(16)

        # ── step stack ──────────────────────────────────────────────────────
        self.stack = QStackedWidget()

        # Step 1 – credentials + phone
        page1 = QWidget()
        l1 = QVBoxLayout(page1)
        l1.setContentsMargins(0, 0, 0, 0)
        l1.setSpacing(8)

        def _lbl(text):
            lb = QLabel(text)
            lb.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569;")
            return lb

        self.inp_api_id   = QLineEdit(); self.inp_api_id.setPlaceholderText("e.g. 12345678")
        self.inp_api_hash = QLineEdit(); self.inp_api_hash.setPlaceholderText("32-char hex string")
        self.inp_phone    = QLineEdit(); self.inp_phone.setPlaceholderText("+91 98765 43210")

        for w in (self.inp_api_id, self.inp_api_hash, self.inp_phone):
            w.setMinimumHeight(38)

        self.btn_send_code = QPushButton("Send Verification Code")
        self.btn_send_code.setStyleSheet(
            "QPushButton { background-color: #2BA5E4; color: white; border: none; "
            "border-radius: 6px; font-size: 14px; font-weight: bold; padding: 0 16px; }"
            "QPushButton:hover { background-color: #1A96D5; }"
            "QPushButton:disabled { background-color: #94A3B8; }")
        self.btn_send_code.setMinimumHeight(42)
        self.btn_send_code.clicked.connect(self.on_send_code)

        l1.addWidget(_lbl("API ID"))
        l1.addWidget(self.inp_api_id)
        l1.addWidget(_lbl("API Hash"))
        l1.addWidget(self.inp_api_hash)
        l1.addWidget(_lbl("Phone Number (with country code)"))
        l1.addWidget(self.inp_phone)
        l1.addSpacing(12)
        l1.addWidget(self.btn_send_code)

        # Step 2 – OTP
        page2 = QWidget()
        l2 = QVBoxLayout(page2)
        l2.setContentsMargins(0, 0, 0, 0)
        l2.setSpacing(8)

        hint2 = QLabel("📲 Check your Telegram app for the code.")
        hint2.setStyleSheet("font-size: 13px; color: #64748B;")
        hint2.setWordWrap(True)

        self.inp_code = QLineEdit()
        self.inp_code.setPlaceholderText("Enter 5-digit code")
        self.inp_code.setMinimumHeight(38)

        self.btn_submit_code = QPushButton("Verify & Login")
        self.btn_submit_code.setStyleSheet(
            "QPushButton { background-color: #2BA5E4; color: white; border: none; "
            "border-radius: 6px; font-size: 14px; font-weight: bold; padding: 0 16px; }"
            "QPushButton:hover { background-color: #1A96D5; }"
            "QPushButton:disabled { background-color: #94A3B8; }")
        self.btn_submit_code.setMinimumHeight(42)
        self.btn_submit_code.clicked.connect(self.on_submit_code)

        self.btn_back = QPushButton("← Back")
        self.btn_back.setStyleSheet(
            "background: transparent; border: none; color: #2BA5E4; font-weight: 600;")
        self.btn_back.clicked.connect(self.reset_to_start)

        l2.addWidget(hint2)
        l2.addSpacing(8)
        l2.addWidget(_lbl("Verification Code"))
        l2.addWidget(self.inp_code)
        l2.addSpacing(12)
        l2.addWidget(self.btn_submit_code)
        l2.addWidget(self.btn_back)

        # Step 3 – 2FA
        page3 = QWidget()
        l3 = QVBoxLayout(page3)
        l3.setContentsMargins(0, 0, 0, 0)
        l3.setSpacing(8)

        hint3 = QLabel("🔐 Two-step verification is enabled.")
        hint3.setStyleSheet("font-size: 13px; color: #64748B;")

        self.inp_pwd = QLineEdit()
        self.inp_pwd.setEchoMode(QLineEdit.Password)
        self.inp_pwd.setPlaceholderText("Your 2FA password")
        self.inp_pwd.setMinimumHeight(38)

        self.btn_submit_pwd = QPushButton("Submit Password")
        self.btn_submit_pwd.setStyleSheet(
            "QPushButton { background-color: #2BA5E4; color: white; border: none; "
            "border-radius: 6px; font-size: 14px; font-weight: bold; padding: 0 16px; }"
            "QPushButton:hover { background-color: #1A96D5; }"
            "QPushButton:disabled { background-color: #94A3B8; }")
        self.btn_submit_pwd.setMinimumHeight(42)
        self.btn_submit_pwd.clicked.connect(self.on_submit_pwd)

        l3.addWidget(hint3)
        l3.addSpacing(8)
        l3.addWidget(_lbl("2FA Password"))
        l3.addWidget(self.inp_pwd)
        l3.addSpacing(12)
        l3.addWidget(self.btn_submit_pwd)

        self.stack.addWidget(page1)
        self.stack.addWidget(page2)
        self.stack.addWidget(page3)

        card_layout.addWidget(self.stack)
        outer.addWidget(self.card)

    # ── helpers ────────────────────────────────────────────────────────────

    def load_env_defaults(self):
        api_id   = os.getenv('API_ID')
        api_hash = os.getenv('API_HASH')
        if api_id:   self.inp_api_id.setText(api_id)
        if api_hash: self.inp_api_hash.setText(api_hash)

    def on_send_code(self):
        api_id   = self.inp_api_id.text().strip()
        api_hash = self.inp_api_hash.text().strip()
        phone    = self.inp_phone.text().strip()
        if not api_id or not api_hash or not phone:
            return
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
        try:
            with open(env_path, "w") as f:
                f.write(f"API_ID={api_id}\nAPI_HASH={api_hash}\n")
        except Exception:
            pass
        self.btn_send_code.setEnabled(False)
        self.btn_send_code.setText("Connecting…")
        self.login_started.emit(api_id, api_hash, phone)

    def on_submit_code(self):
        code = self.inp_code.text().strip()
        if code:
            self.btn_submit_code.setEnabled(False)
            self.code_submitted.emit(code)

    def on_submit_pwd(self):
        pwd = self.inp_pwd.text().strip()
        if pwd:
            self.btn_submit_pwd.setEnabled(False)
            self.password_submitted.emit(pwd)

    def show_otp_step(self):
        self.inp_code.clear()
        self.btn_submit_code.setEnabled(True)
        self.stack.setCurrentIndex(1)

    def show_pwd_step(self):
        self.inp_pwd.clear()
        self.btn_submit_pwd.setEnabled(True)
        self.stack.setCurrentIndex(2)

    def reset_to_start(self):
        self.btn_send_code.setEnabled(True)
        self.btn_send_code.setText("Send Verification Code")
        self.stack.setCurrentIndex(0)
