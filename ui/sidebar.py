from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QButtonGroup, QLabel
from PySide6.QtCore import Signal

class PDMSidebar(QWidget):
    nav_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 30, 0, 30)
        layout.setSpacing(5)

        brand = QLabel("PDM")
        brand.setStyleSheet("color: #0078d4; font-size: 24px; font-weight: 800; padding: 0 30px 20px 30px;")
        layout.addWidget(brand)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        items = [
            ("Downloads", "all"),
            ("Statistics", "stats"),
            ("Downloading", "downloading"),
            ("Completed", "completed"),
            ("Trash", "trash"),
        ]

        for text, key in items:
            btn = QPushButton(text)
            btn.setObjectName("nav-btn")
            btn.setCheckable(True)
            if key == "all": btn.setChecked(True)
            self.btn_group.addButton(btn)
            layout.addWidget(btn)
            btn.clicked.connect(lambda chk, k=key: self.nav_changed.emit(k))

        layout.addStretch()
        self.set_btn = QPushButton("Settings")
        self.set_btn.setObjectName("nav-btn")
        self.set_btn.setCheckable(True)
        self.btn_group.addButton(self.set_btn)
        layout.addWidget(self.set_btn)
        self.set_btn.clicked.connect(lambda: self.nav_changed.emit("settings"))
