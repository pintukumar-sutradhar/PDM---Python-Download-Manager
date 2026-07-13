import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, 
    QLineEdit, QPushButton, QHBoxLayout, QComboBox, QCheckBox,
    QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer

class PDMSettingsView(QWidget):
    save_clicked = Signal(dict)

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(30)

        header_layout = QHBoxLayout()
        header = QLabel("Core Settings")
        header.setStyleSheet("font-size: 36px; font-weight: bold; color: #ffffff;")
        header_layout.addWidget(header)
        
        self.version_label = QLabel("Version 1.0.0")
        self.version_label.setStyleSheet("color: #888888; font-size: 14px; margin-top: 15px;")
        header_layout.addStretch()
        header_layout.addWidget(self.version_label)
        layout.addLayout(header_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(35)
        container_layout.setContentsMargins(0, 0, 15, 0)

        # General Section
        self.download_path = QLineEdit(os.path.expanduser("~/Downloads"))
        self.concurrent_limit = QComboBox()
        self.concurrent_limit.addItems([
            "2 Connections", 
            "4 Connections", 
            "8 Connections", 
            "16 Connections", 
            "32 Connections",
            "64 Connections"
        ])
        self.concurrent_limit.setCurrentIndex(2)

        container_layout.addWidget(self._create_section("General", [
            ("Download Path", self.download_path),
            ("Connections", self.concurrent_limit),
        ]))
        
        # Authentication & Cookies
        self.browser_cookies = QComboBox()
        self.browser_cookies.addItems([
            "Disabled",
            "Chrome",
            "Firefox",
            "Edge",
            "Brave",
            "Opera",
            "Vivaldi",
            "Safari"
        ])
        
        container_layout.addWidget(self._create_section("Authentication", [
            ("Import Cookies From", self.browser_cookies),
        ]))

        # Appearance Section
        self.theme_mode = QComboBox()
        self.theme_mode.addItems([
            "Abyssal Current", 
            "Biolume Depths", 
            "Celestial Void", 
            "Crimson", 
            "Cyber Blue", 
            "Deep Forest", 
            "Emerald", 
            "Midnight Glacier", 
            "Obsidian", 
            "Ocean Depths", 
            "Royal Purple", 
            "Royal Velvet", 
            "Volcanic Abyss"
        ])
        
        container_layout.addWidget(self._create_section("Appearance", [
            ("Theme", self.theme_mode),
        ]))

        # Network Section
        self.use_proxy = QCheckBox("Use Proxy")
        self.proxy_addr = QLineEdit()
        self.proxy_addr.setPlaceholderText("http://127.0.0.1:8080")

        container_layout.addWidget(self._create_section("Network", [
            ("Proxy", self.use_proxy),
            ("Address", self.proxy_addr),
        ]))

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Footer
        footer_layout = QHBoxLayout()
        self.status_msg = QLabel("")
        self.status_msg.setStyleSheet("color: #00ffaa; font-weight: bold;")
        footer_layout.addWidget(self.status_msg)
        
        footer_layout.addStretch()
        
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setObjectName("primary-btn")
        self.save_btn.setFixedWidth(200)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self._on_save)
        
        footer_layout.addWidget(self.save_btn)
        layout.addLayout(footer_layout)

    def _create_section(self, title, items):
        group = QFrame()
        group.setObjectName("settings-card")
        layout = QVBoxLayout(group)
        layout.setSpacing(20)
        
        label = QLabel(title)
        label.setStyleSheet("font-size: 18px; font-weight: bold; color: #0078d4; margin-bottom: 10px;")
        layout.addWidget(label)

        for name, widget in items:
            row = QHBoxLayout()
            lbl = QLabel(name)
            lbl.setStyleSheet("color: #cccccc;")
            row.addWidget(lbl)
            row.addStretch()
            widget.setFixedWidth(400)
            row.addWidget(widget)
            layout.addLayout(row)
        
        return group

    def _on_save(self):
        self.save_btn.setEnabled(False)
        self.save_btn.setText("Saving...")
        
        data = {
            "path": self.download_path.text(),
            "threads": self.concurrent_limit.currentText(),
            "proxy": self.use_proxy.isChecked(),
            "proxy_addr": self.proxy_addr.text(),
            "theme": self.theme_mode.currentText(),
            "browser": self.browser_cookies.currentText().lower()
        }
        
        # Emit signal
        self.save_clicked.emit(data)
        
        # Confirmation
        QTimer.singleShot(600, self._show_confirmation)

    def _show_confirmation(self):
        self.save_btn.setEnabled(True)
        self.save_btn.setText("Save Settings")
        self.status_msg.setText("Settings saved successfully")
        QTimer.singleShot(3000, lambda: self.status_msg.setText(""))
