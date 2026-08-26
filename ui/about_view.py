from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt
from core.constants import APP_NAME, APP_VERSION, APP_DESCRIPTION, AUTHOR


class AboutView(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName('page-view')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 22, 36, 16)
        lay.setSpacing(16)
        lay.addStretch(1)
        title = QLabel(APP_NAME)
        title.setObjectName('page-header-title')
        title.setAlignment(Qt.AlignCenter)
        ver = QLabel(f'Version {APP_VERSION}')
        ver.setObjectName('page-header-subtitle')
        ver.setAlignment(Qt.AlignCenter)
        desc = QLabel(APP_DESCRIPTION)
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        author = QLabel(f'Developed by {AUTHOR}')
        author.setObjectName('page-header-subtitle')
        author.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        lay.addWidget(ver)
        lay.addWidget(desc)
        lay.addWidget(author)
        lay.addStretch(2)
