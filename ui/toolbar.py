from PySide6.QtWidgets import QToolBar, QPushButton, QHBoxLayout, QWidget, QSizePolicy
from PySide6.QtCore import Qt, Signal, QSize

class PDMToolbar(QToolBar):
    add_clicked = Signal()
    pause_clicked = Signal()
    resume_clicked = Signal()
    delete_clicked = Signal()
    clear_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setMovable(False)
        self.setIconSize(QSize(20, 20))
        self.init_ui()

    def init_ui(self):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)

        self.add_btn = QPushButton("+ New Download")
        self.add_btn.setObjectName("primary-btn")
        self.add_btn.clicked.connect(self.add_clicked.emit)
        
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setObjectName("action-btn")
        self.pause_btn.clicked.connect(self.pause_clicked.emit)

        self.resume_btn = QPushButton("Resume")
        self.resume_btn.setObjectName("action-btn")
        self.resume_btn.clicked.connect(self.resume_clicked.emit)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("action-btn")
        self.delete_btn.clicked.connect(self.delete_clicked.emit)

        self.clear_btn = QPushButton("Clear List")
        self.clear_btn.setObjectName("action-btn")
        self.clear_btn.setStyleSheet("color: #ff4444;")
        self.clear_btn.clicked.connect(self.clear_clicked.emit)

        layout.addWidget(self.add_btn)
        layout.addWidget(self.pause_btn)
        layout.addWidget(self.resume_btn)
        layout.addWidget(self.delete_btn)
        layout.addWidget(self.clear_btn)
        layout.addStretch()

        self.addWidget(container)
