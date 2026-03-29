from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QCheckBox, QComboBox, 
    QFrame, QFileDialog, QSpinBox, QMessageBox
)
from PySide6.QtCore import Qt
import json
import os

CONFIG_FILE = "config.json"

def load_config():
    default_config = {
        "download_path": "downloads",
        "download_limit": 5,
        "max_speed_kb": 0,
        "proxy": {
            "enabled": False,
            "type": "SOCKS5",
            "host": "",
            "port": "",
            "user": "",
            "pass": ""
        }
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception as e:
            print(f"Error loading config: {e}")
    return default_config

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

class SettingsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)

        # Header
        lbl_header = QLabel("Application Settings")
        lbl_header.setStyleSheet("color: #1E293B; font-weight: bold; font-size: 24px;")
        layout.addWidget(lbl_header)

        # Card Container
        card = QFrame()
        card.setObjectName("WhiteCard")
        clayout = QVBoxLayout(card)
        clayout.setContentsMargins(24, 24, 24, 24)
        clayout.setSpacing(16)

        # 1. Download Path
        lbl_path = QLabel("Default Download Path")
        lbl_path.setObjectName("SectionHeader")
        
        path_row = QHBoxLayout()
        self.input_path = QLineEdit("downloads")
        self.input_path.setReadOnly(True)
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.setObjectName("PrimaryButton")
        self.btn_browse.clicked.connect(self.browse_path)
        path_row.addWidget(self.input_path)
        path_row.addWidget(self.btn_browse)
        
        clayout.addWidget(lbl_path)
        clayout.addLayout(path_row)

        # Divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.HLine)
        div1.setStyleSheet("background-color: #E2E8F0;")
        clayout.addWidget(div1)

        # 2. Proxy Settings
        lbl_proxy = QLabel("Proxy Configuration")
        lbl_proxy.setObjectName("SectionHeader")
        clayout.addWidget(lbl_proxy)
        
        self.chk_enable_proxy = QCheckBox("Enable Proxy")
        clayout.addWidget(self.chk_enable_proxy)

        proxy_form = QVBoxLayout()
        proxy_row1 = QHBoxLayout()
        
        self.combo_proxy_type = QComboBox()
        self.combo_proxy_type.addItems(["SOCKS5", "SOCKS4", "HTTP"])
        self.input_proxy_host = QLineEdit()
        self.input_proxy_host.setPlaceholderText("Host/IP")
        self.input_proxy_port = QLineEdit()
        self.input_proxy_port.setPlaceholderText("Port")
        
        proxy_row1.addWidget(self.combo_proxy_type)
        proxy_row1.addWidget(self.input_proxy_host)
        proxy_row1.addWidget(self.input_proxy_port)
        proxy_form.addLayout(proxy_row1)
        
        proxy_row2 = QHBoxLayout()
        self.input_proxy_user = QLineEdit()
        self.input_proxy_user.setPlaceholderText("Username (Optional)")
        self.input_proxy_pass = QLineEdit()
        self.input_proxy_pass.setPlaceholderText("Password (Optional)")
        self.input_proxy_pass.setEchoMode(QLineEdit.Password)
        
        proxy_row2.addWidget(self.input_proxy_user)
        proxy_row2.addWidget(self.input_proxy_pass)
        proxy_form.addLayout(proxy_row2)
        
        clayout.addLayout(proxy_form)

        # Divider
        div2 = QFrame()
        div2.setFrameShape(QFrame.HLine)
        div2.setStyleSheet("background-color: #E2E8F0;")
        clayout.addWidget(div2)

        # 3. Download Limits
        lbl_limits = QLabel("Download Limits")
        lbl_limits.setObjectName("SectionHeader")
        clayout.addWidget(lbl_limits)
        
        limit_form = QVBoxLayout()
        limit_row1 = QHBoxLayout()
        self.lbl_limit_desc = QLabel("Concurrent Downloads:")
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(1, 100)
        self.spin_limit.setValue(5)
        limit_row1.addWidget(self.lbl_limit_desc)
        limit_row1.addWidget(self.spin_limit)
        limit_row1.addStretch()
        
        limit_row2 = QHBoxLayout()
        self.lbl_speed_desc = QLabel("Max Speed (KB/s, 0=unlimited):")
        self.spin_speed = QSpinBox()
        self.spin_speed.setRange(0, 999999)
        self.spin_speed.setValue(0)
        limit_row2.addWidget(self.lbl_speed_desc)
        limit_row2.addWidget(self.spin_speed)
        limit_row2.addStretch()
        
        limit_form.addLayout(limit_row1)
        limit_form.addLayout(limit_row2)
        clayout.addLayout(limit_form)

        # Divider
        div3 = QFrame()
        div3.setFrameShape(QFrame.HLine)
        div3.setStyleSheet("background-color: #E2E8F0;")
        clayout.addWidget(div3)

        # 4. Save Button
        save_row = QHBoxLayout()
        self.btn_save = QPushButton("Save Config")
        self.btn_save.setObjectName("SuccessButton")
        self.btn_save.clicked.connect(self.save_settings)
        save_row.addStretch()
        save_row.addWidget(self.btn_save)
        clayout.addLayout(save_row)

        layout.addWidget(card)
        layout.addStretch()
        
        self.load_settings()

    def load_settings(self):
        config = load_config()
        self.input_path.setText(config.get("download_path", "downloads"))
        self.spin_limit.setValue(config.get("download_limit", 5))
        self.spin_speed.setValue(config.get("max_speed_kb", 0))
        
        proxy = config.get("proxy", {})
        self.chk_enable_proxy.setChecked(proxy.get("enabled", False))
        self.combo_proxy_type.setCurrentText(proxy.get("type", "SOCKS5"))
        self.input_proxy_host.setText(proxy.get("host", ""))
        self.input_proxy_port.setText(str(proxy.get("port", "")))
        self.input_proxy_user.setText(proxy.get("user", ""))
        self.input_proxy_pass.setText(proxy.get("pass", ""))

    def save_settings(self):
        config = {
            "download_path": self.input_path.text(),
            "download_limit": self.spin_limit.value(),
            "max_speed_kb": self.spin_speed.value(),
            "proxy": {
                "enabled": self.chk_enable_proxy.isChecked(),
                "type": self.combo_proxy_type.currentText(),
                "host": self.input_proxy_host.text(),
                "port": self.input_proxy_port.text(),
                "user": self.input_proxy_user.text(),
                "pass": self.input_proxy_pass.text()
            }
        }
        save_config(config)
        # Notify user it was saved properly
        QMessageBox.information(self, "Settings Saved", "Configuration saved successfully!")

    def browse_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Directory")
        if folder:
            self.input_path.setText(folder)
