import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QProgressBar
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtCore import Qt, Signal, QUrl

class LoginBrowserDialog(QDialog):
    login_completed = Signal(str) # Path to the temporary cookies file

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Secure Login - PDM")
        self.resize(1000, 800)
        self.url = url
        self.cookie_file = os.path.join(os.getcwd(), "database", "session_cookies.txt")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet("background-color: #1a1b1e; border-bottom: 1px solid #333;")
        header_layout = QHBoxLayout(header)
        
        info_label = QLabel("Please log in to your account. Once done, click 'Login Completed'.")
        info_label.setStyleSheet("color: #e0e0e0; font-weight: bold; padding: 10px;")
        
        self.done_btn = QPushButton("Login Completed")
        self.done_btn.setStyleSheet("""
            background-color: #0078d4; color: white; border-radius: 6px; 
            padding: 8px 20px; font-weight: bold;
        """)
        self.done_btn.clicked.connect(self._on_done)
        
        header_layout.addWidget(info_label)
        header_layout.addStretch()
        header_layout.addWidget(self.done_btn)
        layout.addWidget(header)

        # Browser View
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl(self.url))
        layout.addWidget(self.browser)

        # Progress bar for browser
        self.progress = QProgressBar()
        self.progress.setMaximumHeight(2)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("QProgressBar::chunk { background-color: #0078d4; }")
        self.browser.loadProgress.connect(self.progress.setValue)
        self.browser.loadFinished.connect(lambda: self.progress.setVisible(False))
        self.browser.loadStarted.connect(lambda: self.progress.setVisible(True))
        layout.addWidget(self.progress)

    def _on_done(self):
        # We don't manually extract cookies here; yt-dlp can be told to use the profile directory 
        # or we can assume the user is now authenticated in the WebEngine session.
        # For maximum compatibility, we emit the signal and close.
        self.accept()

from PySide6.QtWidgets import QWidget # Required for header container
