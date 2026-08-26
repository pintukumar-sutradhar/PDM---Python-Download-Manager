import os
from urllib.parse import urlparse
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QRadioButton, QButtonGroup, QGroupBox, QPlainTextEdit, QAbstractItemView, QMessageBox
from PySide6.QtCore import Qt, QThread, Signal
from core.scanner import Scanner
from core.database import PDMDatabase
from ui.format_selector import FormatSelectorDialog

class ScanWorker(QThread):
    finished = Signal(list, str, bool)

    def __init__(self, url, cookie_file=None):
        super().__init__()
        self.url = url
        self.cookie_file = cookie_file

    def run(self):
        try:
            files = Scanner.scan_url(self.url, cookie_file=self.cookie_file)
            self.finished.emit(files, Scanner.last_error, Scanner.last_auth_required)
        except Exception as e:
            self.finished.emit([], str(e), False)

class NewDownloadDialog(QDialog):

    def __init__(self, parent=None, initial_url=''):
        super().__init__(parent)
        self.setWindowTitle('New Download · PDM')
        self.resize(1060, 780)
        self.setMinimumSize(960, 700)
        self.found_files = []
        self._selections = None
        self.init_ui(initial_url)

    def init_ui(self, initial_url):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 32, 36, 28)
        outer.setSpacing(18)
        head = QVBoxLayout()
        head.setSpacing(2)
        title = QLabel('New Download')
        title.setObjectName('page-header-title')
        sub = QLabel('Scan any media URL, pick quality, and start the download.')
        sub.setObjectName('page-header-sub')
        head.addWidget(title)
        head.addWidget(sub)
        outer.addLayout(head)
        url_layout = QHBoxLayout()
        url_layout.setSpacing(10)
        self.url_input = QLineEdit(initial_url)
        self.url_input.setPlaceholderText('Paste media URL or magnet link here…')
        self.url_input.setMinimumHeight(46)
        self.scan_btn = QPushButton('Scan Media')
        self.scan_btn.setObjectName('primary-btn')
        self.scan_btn.setMinimumHeight(46)
        self.scan_btn.setFixedWidth(150)
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.clicked.connect(self._start_scan)
        url_layout.addWidget(self.url_input, 1)
        url_layout.addWidget(self.scan_btn)
        outer.addLayout(url_layout)
        content_h = QHBoxLayout()
        content_h.setSpacing(14)
        list_group = QGroupBox('Media List')
        list_v = QVBoxLayout(list_group)
        list_v.setSpacing(10)
        self.table = QTableWidget(0, 2)
        self.table.setObjectName('download-table')
        self.table.setHorizontalHeaderLabels(['', 'Title'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setObjectName('file-table')
        list_v.addWidget(self.table)
        sel_layout = QHBoxLayout()
        self.sel_all = QPushButton('Select All')
        self.sel_all.setObjectName('secondary-btn')
        self.sel_all.setCursor(Qt.PointingHandCursor)
        self.sel_all.clicked.connect(lambda: self._toggle_selection(True))
        self.sel_none = QPushButton('Deselect All')
        self.sel_none.setObjectName('secondary-btn')
        self.sel_none.setCursor(Qt.PointingHandCursor)
        self.sel_none.clicked.connect(lambda: self._toggle_selection(False))
        sel_layout.addWidget(self.sel_all)
        sel_layout.addWidget(self.sel_none)
        sel_layout.addStretch()
        list_v.addLayout(sel_layout)
        content_h.addWidget(list_group, 3)
        config_group = QGroupBox('Configuration')
        config_v = QVBoxLayout(config_group)
        config_v.setSpacing(8)
        config_v.addWidget(QLabel('MEDIA TYPE'))
        self.v_radio = QRadioButton('Video  (MP4 / MKV)')
        self.a_radio = QRadioButton('Audio only  (MP3)')
        self.v_radio.setChecked(True)
        self.mode_grp = QButtonGroup(self)
        self.mode_grp.addButton(self.v_radio)
        self.mode_grp.addButton(self.a_radio)
        config_v.addWidget(self.v_radio)
        config_v.addWidget(self.a_radio)
        config_v.addSpacing(10)
        config_v.addWidget(QLabel('OUTPUT CONTAINER'))
        self.container_combo = QComboBox()
        self.container_combo.addItem('MP4  (best compatibility)', 'mp4')
        self.container_combo.addItem('MKV  (best compatibility + subtitles)', 'mkv')
        config_v.addWidget(self.container_combo)
        config_v.addSpacing(10)
        self.auto_name_check = QCheckBox('Automatic smart naming')
        self.auto_name_check.setChecked(True)
        self.auto_name_check.setToolTip('Name files automatically from media metadata (title, quality, platform).')
        config_v.addWidget(self.auto_name_check)
        config_v.addSpacing(12)
        signin_lbl = QLabel('SITE SIGN-IN')
        signin_lbl.setObjectName('section-title')
        config_v.addWidget(signin_lbl)
        hint = QLabel('Login-required site? Press Scan Media - if sign-in is needed, PDM opens the site right here so you can log in once. The session is remembered.')
        hint.setObjectName('section-sub')
        hint.setWordWrap(True)
        config_v.addWidget(hint)
        config_v.addStretch()
        content_h.addWidget(config_group, 2)
        outer.addLayout(content_h, stretch=1)
        footer = QHBoxLayout()
        self.close_btn = QPushButton('Cancel')
        self.close_btn.setObjectName('secondary-btn')
        self.close_btn.setFixedSize(120, 44)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton('Continue')
        self.ok_btn.setObjectName('primary-btn')
        self.ok_btn.setFixedSize(200, 44)
        self.ok_btn.setCursor(Qt.PointingHandCursor)
        self.ok_btn.clicked.connect(self._confirm_download)
        footer.addStretch()
        footer.addWidget(self.close_btn)
        footer.addWidget(self.ok_btn)
        outer.addLayout(footer)
        try:
            PDMDatabase().get_setting('cookie_browser', '')
        except Exception:
            pass

    def _start_scan(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.information(self, 'URL Required', 'Paste a media URL to scan first.')
            return
        low = url.lower()
        if low.startswith('magnet:') or low.endswith('.torrent'):
            if low.startswith('magnet:') and 'dn=' in low:
                name = url.split('dn=')[-1].split('&')[0].replace('+', ' ').replace('%20', ' ').strip() or 'Torrent download'
            elif low.startswith('magnet:'):
                import re
                m = re.search(r'btih:([A-Za-z0-9]+)', url)
                name = f'Torrent {m.group(1)[:12]}' if m else 'Torrent download'
            else:
                name = os.path.splitext(os.path.basename(url))[0].replace('.', ' ') or 'Torrent download'
            self._selections = {'files': [{'url': url, 'name': name, 'is_torrent': True}], 'path': self._default_download_path(), 'is_audio': False, 'container': 'mp4', 'video_fmt': None, 'audio_fmt': None, 'filename': None, 'auto_name': True}
            self.accept()
            return
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText('Scanning…')
        from core import weblogin as _wl
        self.worker = ScanWorker(url, cookie_file=_wl.cookie_file_for(url))
        self.worker.finished.connect(self._on_scan_finished)
        self.worker.start()

    def _on_scan_finished(self, items, error, auth_required):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText('Scan Media')
        self.found_files = items
        self.table.setRowCount(len(items))
        for i, f in enumerate(items):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(i, 0, check)
            self.table.setItem(i, 1, QTableWidgetItem(f.get('name', 'Unknown')))
        if auth_required:
            self._offer_login_scan(have_items=bool(items))
        elif not items:
            detail = (Scanner.last_error or '').strip()
            msg = 'No media found at this URL.' + (f' Reason: {detail[:140]}' if detail else '')
            self.table.setRowCount(1)
            self.table.setItem(0, 1, QTableWidgetItem(msg))

    def _offer_login_scan(self, have_items=False):
        from core import weblogin as _wl
        url = self.url_input.text().strip()
        host = urlparse(url).hostname or 'the site'
        if _wl.has_cookies(url):
            msg = f'{host} still refuses without a fresh session. Sign in again below, then rescan.'
        else:
            msg = f'{host} needs a sign-in. Open it below, log in, and PDM will remember the session for future downloads.'
        if have_items:
            msg += ' (Streams found above are locked until you sign in.)'
            self.table.insertRow(0)
            self.table.setItem(0, 1, QTableWidgetItem(msg))
        else:
            self.table.setRowCount(1)
            self.table.setItem(0, 1, QTableWidgetItem(msg))
        if not hasattr(self, 'login_btn'):
            from PySide6.QtWidgets import QPushButton, QHBoxLayout
            from ui.login_browser import LoginBrowserDialog
            row = QHBoxLayout()
            row.addStretch(1)
            self.paste_cookie_btn = QPushButton('Paste cookies manually')
            self.paste_cookie_btn.setObjectName('secondary-btn')
            self.paste_cookie_btn.setCursor(Qt.PointingHandCursor)
            self.paste_cookie_btn.clicked.connect(self._paste_cookies)
            self.login_btn = QPushButton('Sign in with browser & rescan')
            self.login_btn.setObjectName('primary-btn')
            self.login_btn.setCursor(Qt.PointingHandCursor)
            self.login_btn.clicked.connect(self._open_login_browser)
            row.addWidget(self.paste_cookie_btn)
            row.addWidget(self.login_btn)
            self.layout().addLayout(row)
        self.login_btn.setVisible(True)
        self.paste_cookie_btn.setVisible(True)

    def _paste_cookies(self):
        from PySide6.QtWidgets import QMessageBox
        from ui.login_browser import CookiePasteDialog
        from core import weblogin as _wl
        from urllib.parse import urlparse as _up
        url = self.url_input.text().strip()
        domain = _up(url).hostname or ''
        if not domain:
            QMessageBox.information(self, 'No URL', 'Enter the site URL first.')
            return
        registrable = _wl._registrable(domain)
        dlg = CookiePasteDialog(registrable, parent=self)
        if dlg.exec():
            cookies = [c for c in dlg.cookies() if c.get('name')]
            if not cookies:
                QMessageBox.warning(self, 'No cookies found', 'Could not parse any cookies from that text.')
                return
            _wl.save_cookies(registrable, cookies)
            self.login_btn.setVisible(False)
            self.paste_cookie_btn.setVisible(False)
            self._start_scan()

    def _open_login_browser(self):
        url = self.url_input.text().strip()
        from ui.login_browser import LoginBrowserDialog
        from core import weblogin as _wl
        dlg = LoginBrowserDialog(url, parent=self)
        dlg.exec()
        if getattr(dlg, 'selected_url', None):
            self.login_btn.setVisible(False)
            self.paste_cookie_btn.setVisible(False)
            self.url_input.setText(dlg.selected_url)
            self._start_scan()
            return
        if dlg._saved and _wl.has_cookies(url):
            self.login_btn.setVisible(False)
            self.paste_cookie_btn.setVisible(False)
            self._start_scan()

    def _toggle_selection(self, state):
        target = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item:
                item.setCheckState(target)

    def _checked_files(self):
        selected = []
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and item.checkState() == Qt.CheckState.Checked and (i < len(self.found_files)):
                selected.append(self.found_files[i])
        return selected

    def _confirm_download(self):
        selected = self._checked_files()
        if not selected:
            QMessageBox.information(self, 'No Selection', 'Select at least one media item to download.')
            return
        import re as _re
        page_like = [f for f in selected if not f.get('is_torrent') and not _re.search(r'\\.(m3u8|mpd|mp4|mkv|webm|mov|avi|ts|m4v|flv|mp3|m4a|aac|ogg|opus|flac|wav|zip|rar|7z|pdf|apk|iso)(\\?|#|$)', (f.get('url') or '').lower(), _re.IGNORECASE)]
        if page_like and not self.found_files:
            QMessageBox.warning(self, 'Nothing downloadable yet', 'That link is a web page, not a media file. Press "Scan Media" first — if it needs sign-in, use the sign-in button.')
            return
        is_audio = self.a_radio.isChecked()
        container = self.container_combo.currentData()
        video_fmt = audio_fmt = None
        filename = None
        auto_name = self.auto_name_check.isChecked()
        if not is_audio:
            dlg = FormatSelectorDialog(self, url=selected[0]['url'], title=selected[0].get('name', ''), prefill_container=container)
            if not dlg.exec():
                return
            sel = dlg.get_selection()
            video_fmt = sel['video_fmt']
            audio_fmt = sel['audio_fmt']
            container = sel['container']
            if not auto_name:
                filename = sel['filename']
        self._selections = {'files': selected, 'path': self._default_download_path(), 'is_audio': is_audio, 'container': container, 'video_fmt': video_fmt, 'audio_fmt': audio_fmt, 'filename': filename, 'auto_name': auto_name}
        self.accept()

    def _default_download_path(self):
        try:
            return PDMDatabase().get_setting('default_download_path', os.path.expanduser('~/Downloads'))
        except Exception:
            return os.path.expanduser('~/Downloads')

    def get_selected_files(self):
        if not self._selections:
            return {'files': [], 'path': os.path.expanduser('~/Downloads')}
        s = self._selections
        files = []
        for i, f_info in enumerate(s['files']):
            entry = f_info.copy()
            entry['is_audio'] = s['is_audio']
            entry['container'] = s['container']
            entry['video_fmt'] = s['video_fmt']
            entry['audio_fmt'] = s['audio_fmt']
            entry['auto_name'] = s['auto_name']
            if s['filename']:
                base, ext = os.path.splitext(s['filename'])
                entry['name'] = f'{base} ({i + 1}){ext}' if i > 0 else s['filename']
            files.append(entry)
        return {'files': files, 'path': s['path']}