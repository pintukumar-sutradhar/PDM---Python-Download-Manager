import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, QLineEdit, QPushButton, QHBoxLayout, QComboBox, QCheckBox
from PySide6.QtCore import Qt, Signal, QTimer
from core.constants import APP_VERSION

class PDMSettingsView(QWidget):
    save_clicked = Signal(dict)

    def __init__(self):
        super().__init__()
        self.db = None
        try:
            from core.database import PDMDatabase
            self.db = PDMDatabase()
        except Exception:
            pass
        self.init_ui()
        self._load_current_settings()

    def _load_current_settings(self):
        if not self.db:
            return
        try:
            path = self.db.get_setting('default_download_path', os.path.expanduser('~/Downloads'))
            self.download_path.setText(path)
            threads = self.db.get_setting('max_concurrent_downloads', '3')
            try:
                idx = max(0, int(str(threads)) - 1)
                if idx < self.concurrent_limit.count():
                    self.concurrent_limit.setCurrentIndex(idx)
            except Exception:
                pass
            container = self.db.get_setting('default_container', 'mp4')
            idx = self.container_combo.findData(container)
            if idx >= 0:
                self.container_combo.setCurrentIndex(idx)
            speed = self.db.get_setting('speed_limit', '0')
            try:
                speed_mb = int(speed) // (1024 * 1024)
                idx = self.speed_limit.findData(speed_mb)
                if idx >= 0:
                    self.speed_limit.setCurrentIndex(idx)
            except Exception:
                pass
            retry = self.db.get_setting('auto_retry', '2')
            idx = self.retry_combo.findData(int(str(retry)))
            if idx >= 0:
                self.retry_combo.setCurrentIndex(idx)
            saved_theme = (self.db.get_setting('ui_theme', 'dark') or 'dark').lower()
            t_idx = self.theme_combo.findData(saved_theme)
            if t_idx >= 0:
                self.theme_combo.setCurrentIndex(t_idx)
            proxy_enabled = self.db.get_setting('proxy_enabled', '0') == '1'
            proxy_addr = self.db.get_setting('proxy_address', '')
            self.use_proxy.setChecked(proxy_enabled)
            self.proxy_addr.setText(proxy_addr)
            cookie_browser = (self.db.get_setting('cookie_browser', '') or '').strip().lower()
            c_idx = self.cookie_combo.findData(cookie_browser)
            if c_idx >= 0:
                self.cookie_combo.setCurrentIndex(c_idx)
        except Exception:
            pass

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 30, 36, 22)
        outer.setSpacing(18)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        header = QLabel('Settings')
        header.setObjectName('page-header-title')
        sub = QLabel('Tune downloads, networking and session handling.')
        sub.setObjectName('page-header-sub')
        titles.addWidget(header)
        titles.addWidget(sub)
        head.addLayout(titles)
        head.addStretch()
        self.version_label = QLabel(f'v{APP_VERSION}')
        self.version_label.setObjectName('stat-sub')
        head.addWidget(self.version_label)
        outer.addLayout(head)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(16)
        container_layout.setContentsMargins(0, 0, 12, 0)
        self.download_path = QLineEdit(os.path.expanduser('~/Downloads'))
        self.download_path.setObjectName('mono-field')
        self.download_path.setMinimumWidth(280)
        from PySide6.QtWidgets import QFileDialog
        path_row = QWidget()
        path_row.setObjectName('fluid-row')
        path_lay = QHBoxLayout(path_row)
        path_lay.setContentsMargins(0, 0, 0, 0)
        path_lay.setSpacing(8)
        browse_btn = QPushButton('Browse…')
        browse_btn.setObjectName('secondary-btn')
        browse_btn.setCursor(Qt.PointingHandCursor)

        def _browse_path():
            start = self.download_path.text().strip() or os.path.expanduser('~/Downloads')
            chosen = QFileDialog.getExistingDirectory(self, 'Choose Download Folder', start if os.path.isdir(start) else os.path.expanduser('~/'))
            if chosen:
                self.download_path.setText(chosen)
        browse_btn.clicked.connect(_browse_path)
        path_lay.addWidget(self.download_path, stretch=1)
        path_lay.addWidget(browse_btn)
        self.concurrent_limit = QComboBox()
        self.concurrent_limit.addItems(['1 Connection', '2 Connections', '3 Connections', '4 Connections', '8 Connections', '16 Connections', '32 Connections', '64 Connections'])
        self.concurrent_limit.setCurrentIndex(2)
        self.container_combo = QComboBox()
        self.container_combo.addItem('MP4  (best compatibility)', 'mp4')
        self.container_combo.addItem('MKV  (best compatibility + subtitles)', 'mkv')
        self.speed_limit = QComboBox()
        for lbl, val in [('Unlimited', 0), ('1 MB/s', 1), ('2 MB/s', 2), ('5 MB/s', 5), ('10 MB/s', 10), ('25 MB/s', 25)]:
            self.speed_limit.addItem(lbl, val)
        self.retry_combo = QComboBox()
        for lbl, val in [('No automatic retry', 0), ('Retry 1 time', 1), ('Retry 2 times', 2), ('Retry 3 times', 3), ('Retry 5 times', 5)]:
            self.retry_combo.addItem(lbl, val)
        container_layout.addWidget(self._create_section('Downloads', [('Download Path', path_row, 'Where finished files are saved.'), ('Concurrent Downloads', self.concurrent_limit, 'How many files download at once. Extra tasks queue automatically.'), ('Default Output Container', self.container_combo, 'MP4 for compatibility, MKV for subtitles and advanced streams.'), ('Speed Limit', self.speed_limit, 'Throttle every download to avoid saturating your connection.'), ('Automatic Retry', self.retry_combo, 'Retry failed downloads automatically with backoff.')]))
        self.theme_combo = QComboBox()
        self.theme_combo.addItem('Dark', 'dark')
        self.theme_combo.addItem('Light', 'light')
        container_layout.addWidget(self._create_section('Appearance', [('Theme', self.theme_combo, 'Switch instantly — no restart needed.')]))
        self.use_proxy = QCheckBox('Use Proxy')
        self.proxy_addr = QLineEdit()
        self.proxy_addr.setPlaceholderText('http://127.0.0.1:8080')
        self.cookie_combo = QComboBox()
        for lbl, val in [('Disabled', ''), ('Firefox', 'firefox'), ('Chrome', 'chrome'), ('Chromium', 'chromium'), ('Brave', 'brave'), ('Edge', 'edge'), ('Opera', 'opera'), ('Vivaldi', 'vivaldi')]:
            self.cookie_combo.addItem(lbl, val)
        container_layout.addWidget(self._create_section('Network', [('Proxy', self.use_proxy, 'Route downloads through an HTTP/SOCKS proxy.'), ('Address', self.proxy_addr, 'Proxy endpoint, e.g. http://127.0.0.1:8080.'), ('Browser Cookies', self.cookie_combo, 'Reuse a logged-in browser profile for sites that require sign-in. Read-only; PDM never stores passwords. Close the browser while downloading.')] ))
        container_layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll, stretch=1)
        footer = QHBoxLayout()
        self.status_msg = QLabel('')
        self.status_msg.setObjectName('save-status')
        footer.addWidget(self.status_msg)
        footer.addStretch()
        self.save_btn = QPushButton('Save Settings')
        self.save_btn.setObjectName('primary-btn')
        self.save_btn.setFixedSize(190, 44)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self._on_save)
        footer.addWidget(self.save_btn)
        outer.addLayout(footer)

    def _create_section(self, title, items):
        group = QFrame()
        group.setObjectName('card')
        layout = QVBoxLayout(group)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 18, 22, 18)
        label = QLabel(title.upper())
        label.setObjectName('panel-title')
        layout.addWidget(label)
        for name, widget, desc in items:
            row = QHBoxLayout()
            row.setSpacing(14)
            col = QVBoxLayout()
            col.setSpacing(2)
            lbl = QLabel(name)
            lbl.setObjectName('section-title')
            dsc = QLabel(desc)
            dsc.setWordWrap(True)
            dsc.setObjectName('section-sub')
            col.addWidget(lbl)
            col.addWidget(dsc)
            row.addLayout(col, 1)
            if widget.objectName() != 'fluid-row':
                widget.setFixedWidth(360)
            row.addWidget(widget, 1 if widget.objectName() == 'fluid-row' else 0)
            layout.addLayout(row)
        return group

    def _on_save(self):
        self.save_btn.setEnabled(False)
        self.save_btn.setText('Saving…')
        data = {'path': self.download_path.text(), 'threads': self.concurrent_limit.currentText(), 'proxy': self.use_proxy.isChecked(), 'proxy_addr': self.proxy_addr.text(), 'theme': self.theme_combo.currentData(), 'container': self.container_combo.currentData(), 'speed_limit': self.speed_limit.currentData(), 'auto_retry': self.retry_combo.currentData(), 'cookie_browser': self.cookie_combo.currentData() or ''}
        self.save_clicked.emit(data)
        QTimer.singleShot(500, self._show_confirmation)

    def _show_confirmation(self):
        self.save_btn.setEnabled(True)
        self.save_btn.setText('Save Settings')
        self.status_msg.setText('✓ Settings saved')
        QTimer.singleShot(3000, lambda: self.status_msg.setText(''))