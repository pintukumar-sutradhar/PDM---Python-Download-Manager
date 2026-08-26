import os
import sys
import time
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QTableView, QApplication, QStackedWidget, QMessageBox, QHeaderView, QAbstractItemView, QMenu, QSystemTrayIcon, QLabel, QPushButton
from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QIcon, QDesktopServices, QKeySequence, QShortcut
from ui.sidebar import PDMSidebar
from ui.toolbar import PDMToolbar
from ui.dialogs import NewDownloadDialog
from ui.tray import PDMTrayIcon
from ui.delegates import StatusBadgeDelegate, ProgressDelegate
from ui.widgets.settings_view import PDMSettingsView
from ui.widgets.stats_view import PDMStatsView
from ui.torrents_view import TorrentsView
from ui.history_view import HistoryView
from ui.about_view import AboutView
from download.torrent_engine import TorrentEngine
from ui.models.download_model import DownloadModel
from core.database import PDMDatabase
from core.download_engine import DownloadEngine
from core.constants import APP_NAME, APP_VERSION, ACTIVE_STATES
FILTER_KEYS = ('all', 'trash')


def has_danger_style():
    try:
        qss_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'styles')
        return os.path.exists(os.path.join(qss_dir, 'dark.qss'))
    except Exception:
        return False

class PDMMainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setObjectName('pdm-main')
        self.setWindowTitle(f'PDM v{APP_VERSION}')
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_path = os.path.dirname(self.base_dir)
        icon_path = os.path.join(self.root_path, 'assets', 'icons', 'app_icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1320, 860)
        self._closing = False
        self.db = PDMDatabase()
        self.engine = DownloadEngine()
        self.torrent_engine = TorrentEngine(self)
        self.model = DownloadModel()
        self.nav_filter = 'all'
        self._last_ui_sync = 0
        self._speed_acc = 0.0
        self._speed_count = 0
        self.init_ui()
        self.setup_signals()
        self.load_downloads()
        self._setup_shortcuts()
        self._setup_tray()

    def init_ui(self):
        central = QWidget()
        central.setObjectName('central-widget')
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.sidebar = PDMSidebar()
        self.sidebar.nav_changed.connect(self._on_nav_changed)
        layout.addWidget(self.sidebar)
        self.content_stack = QStackedWidget()
        self.downloads_view = QWidget()
        dl_layout = QVBoxLayout(self.downloads_view)
        dl_layout.setContentsMargins(0, 0, 0, 0)
        dl_layout.setSpacing(0)
        self.toolbar = PDMToolbar()
        self.toolbar.add_clicked.connect(self._add_task)
        self.toolbar.pause_clicked.connect(self._pause_selected)
        self.toolbar.resume_clicked.connect(self._resume_selected)
        self.toolbar.delete_clicked.connect(self._delete_selected)
        self.toolbar.search_changed.connect(self._on_search)
        dl_layout.addWidget(self.toolbar)
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(36, 22, 36, 16)
        page_layout.setSpacing(14)
        self.download_table = QTableView()
        self.download_table.setObjectName('download-table')
        self.download_table.setModel(self.model)
        self.download_table.setItemDelegateForColumn(2, StatusBadgeDelegate())
        self.download_table.setItemDelegateForColumn(3, ProgressDelegate())
        self.download_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.download_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.download_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.download_table.setShowGrid(False)
        self.download_table.setAlternatingRowColors(True)
        self.download_table.verticalHeader().setVisible(False)
        self.download_table.verticalHeader().setDefaultSectionSize(56)
        self.download_table.setSortingEnabled(True)
        self.download_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.download_table.customContextMenuRequested.connect(self._show_context_menu)
        self.download_table.doubleClicked.connect(self._open_selected_file)
        header = self.download_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setMinimumSectionSize(60)
        self.download_table.setColumnWidth(1, 100)
        self.download_table.setColumnWidth(2, 122)
        self.download_table.setColumnWidth(3, 190)
        self.download_table.setColumnWidth(4, 110)
        self.download_table.setColumnWidth(5, 100)
        self.download_table.setColumnWidth(6, 140)
        page_layout.addWidget(self.download_table)
        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.addStretch(1)
        self.clear_all_btn = QPushButton('Clear All')
        self.clear_all_btn.setObjectName('secondary-btn')
        self.clear_all_btn.setCursor(Qt.PointingHandCursor)
        self.clear_all_btn.clicked.connect(self._clear_all_records)
        self.empty_trash_btn = QPushButton('Empty Trash')
        self.empty_trash_btn.setObjectName('danger-btn' if has_danger_style() else 'secondary-btn')
        self.empty_trash_btn.setCursor(Qt.PointingHandCursor)
        self.empty_trash_btn.clicked.connect(self._empty_trash)
        self.empty_trash_btn.setVisible(False)
        actions_row.addWidget(self.clear_all_btn)
        actions_row.addWidget(self.empty_trash_btn)
        page_layout.addLayout(actions_row)
        dl_layout.addWidget(page, stretch=1)
        self.content_stack.addWidget(self.downloads_view)
        self.stats_view = PDMStatsView()
        self.content_stack.addWidget(self.stats_view)
        self.settings_view = PDMSettingsView()
        self.settings_view.save_clicked.connect(self._handle_save_settings)
        self.content_stack.addWidget(self.settings_view)
        self.torrents_view = TorrentsView(self.torrent_engine)
        self.content_stack.addWidget(self.torrents_view)
        self.history_view = HistoryView()
        self.content_stack.addWidget(self.history_view)
        self.about_view = AboutView()
        self.content_stack.addWidget(self.about_view)
        from ui.widgets.home_view import PDMHomeView
        self.home_view = PDMHomeView()
        self.home_view.navigate.connect(self._on_nav_changed)
        self.home_view.url_submitted.connect(self._home_download)
        self.home_view.resume_all_requested.connect(self._resume_all_home)
        self.content_stack.addWidget(self.home_view)
        layout.addWidget(self.content_stack, 1)
        self._setup_status_bar()
        self._setup_inbox_watcher()
        self._wire_torrent_signals()
        self._setup_bulk_actions_timer()
        QTimer.singleShot(0, lambda: self._on_nav_changed('home'))

    def _view_index(self):
        return {'downloads': 0, 'stats': 1, 'settings': 2, 'torrents': 3, 'history': 4, 'about': 5, 'home': 6}

    def _setup_bulk_actions_timer(self):
        from PySide6.QtCore import QTimer as _QTimer
        self._torrent_stats_timer = _QTimer(self)
        self._torrent_stats_timer.setInterval(1000)
        self._torrent_stats_timer.timeout.connect(self._poll_torrent_speed)
        self._torrent_stats_timer.start()

    def _poll_torrent_speed(self):
        rate = self.torrent_engine.aggregate_rate()
        if rate > 0:
            self.status_speed.setText(self._fmt_speed(rate))
            self.stats_view.update_speed(rate)

    def _wire_torrent_signals(self):
        self._torrent_ids = {}
        self._last_torrent_db_write = {}
        self.torrent_engine.torrent_added.connect(self.torrents_view.on_added)
        self.torrent_engine.torrent_added.connect(lambda label: self._invalidate_torrent_ids())
        self.torrent_engine.metadata_resolved.connect(self.torrents_view.on_metadata)
        self.torrent_engine.metadata_resolved.connect(lambda old, new: self.load_downloads())
        self.torrent_engine.progress.connect(self._on_torrent_progress)
        self.torrent_engine.progress.connect(self.torrents_view.on_progress)
        self.torrent_engine.finished.connect(self.torrents_view.on_finished)
        self.torrent_engine.finished.connect(lambda name, path, size: self.load_downloads())
        self.torrent_engine.failed.connect(self.torrents_view.on_failed)

    def _on_torrent_progress(self, label, done, total, pct, speed_mb, status_text):
        tid = self._torrent_id_for(label)
        if tid is None:
            return
        if speed_mb and speed_mb > 0:
            remaining = max(0.0, total - done)
            secs = int(remaining / (speed_mb * 1024 * 1024))
            eta = f'{secs // 3600:02d}:{secs % 3600 // 60:02d}:{secs % 60:02d}'
        else:
            eta = '--:--:--'
        done_i = int(min(done, total))
        pct_c = max(0.0, min(100.0, pct))
        now = time.time()
        if now - getattr(self, '_last_torrent_db_write', {}).get(tid, 0) >= 1.0:
            self._last_torrent_db_write[tid] = now
            try:
                self.db.update_download_status(tid, 'Downloading', done_i, int(total))
            except Exception:
                pass
        self.model.update_task(tid, {'percent': pct_c, 'speed': speed_mb or 0.0, 'eta': eta, 'total_size': total, 'downloaded_size': min(done, total)})

    def _torrent_id_for(self, label):
        if not hasattr(self, '_torrent_ids'):
            self._torrent_ids = {}
        if not self._torrent_ids:
            for row in self.db.get_all_downloads_including_trash():
                if row.get('container') == 'torrent':
                    self._torrent_ids[row['filename']] = row['id']
                    if '%' in (row.get('url') or ''):
                        dn = row['url'].split('dn=')[-1].split('&')[0].replace('+', ' ').replace('%20', ' ')
                        if dn:
                            self._torrent_ids[dn] = row['id']
        return self._torrent_ids.get(label)

    def _invalidate_torrent_ids(self):
        if hasattr(self, '_torrent_ids'):
            self._torrent_ids.clear()
        if hasattr(self, '_last_torrent_db_write'):
            self._last_torrent_db_write.clear()

    def _clear_all_records(self):
        active = list(self.engine.active_workers.keys())
        for dl_id in active:
            self.engine.stop_download(dl_id)
        self.engine.queue.clear()
        try:
            self.torrent_engine.pause_all()
            self.torrent_engine.clear_all()
        except Exception:
            pass
        ok = self.db.clear_all_downloads()
        self.load_downloads()
        if ok:
            self.statusBar().showMessage('All records cleared, including Trash. Files on disk were not touched.', 5000)
        else:
            QMessageBox.warning(self, 'Busy', 'Database was busy — please click Clear All again.')

    def _empty_trash(self):
        trashed = [d['id'] for d in self.db.get_all_downloads_including_trash() if d.get('status') == 'Trash']
        for rec_id in trashed:
            self.db.delete_download_permanently(rec_id)
        self.load_downloads()
        self.statusBar().showMessage(f'Trash emptied ({len(trashed)} records). Files on disk were not touched.', 5000)

    def _setup_inbox_watcher(self):
        from PySide6.QtCore import QFileSystemWatcher
        inbox = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'database', 'inbox')
        inbox = os.path.normpath(inbox)
        os.makedirs(inbox, exist_ok=True)
        self._inbox_path = inbox
        self._inbox_watcher = QFileSystemWatcher(self)
        self._inbox_watcher.addPath(inbox)
        self._inbox_watcher.directoryChanged.connect(self._drain_inbox)
        self._drain_inbox()

    def _drain_inbox(self):
        try:
            import json
            for name in sorted(os.listdir(self._inbox_path)):
                if not name.endswith('.json'):
                    continue
                path = os.path.join(self._inbox_path, name)
                try:
                    with open(path) as fh:
                        job = json.load(fh)
                    url = (job.get('url') or '').strip()
                    if not url:
                        continue
                    save_dir = os.path.expanduser(job.get('save_dir') or PDMDatabase().get_setting('default_download_path', '~/Downloads'))
                    self.engine.add_download(url, job.get('filename'), os.path.expanduser(save_dir), auto_name=not job.get('filename'))
                    os.remove(path)
                except Exception:
                    continue
        except Exception:
            pass

    def _setup_status_bar(self):
        sb = self.statusBar()
        self.status_active = QLabel('No active downloads')
        self.status_active.setObjectName('status-active')
        self.status_speed = QLabel('↓ 0 KB/s')
        self.status_speed.setObjectName('status-speed')
        self.status_total = QLabel('')
        self.status_total.setObjectName('status-total')
        sb.addWidget(self.status_active)
        sb.addPermanentWidget(self.status_total)
        sb.addPermanentWidget(self.status_speed)

    @staticmethod
    def _fmt_speed(mbps):
        if not mbps or mbps <= 0:
            return '↓ 0 KB/s'
        if mbps >= 1:
            return f'↓ {mbps:.2f} MB/s'
        return f'↓ {mbps * 1024:.0f} KB/s'

    @staticmethod
    def _fmt_size(num_bytes):
        for unit in ('B', 'KB', 'MB', 'GB'):
            if num_bytes < 1024:
                return f'{num_bytes:.1f} {unit}' if unit != 'B' else f'{int(num_bytes)} B'
            num_bytes /= 1024
        return f'{num_bytes:.2f} TB'

    def _setup_shortcuts(self):
        QShortcut(QKeySequence('Ctrl+N'), self, activated=self._add_task)
        QShortcut(QKeySequence('Ctrl+P'), self, activated=self._pause_selected)
        QShortcut(QKeySequence('Ctrl+R'), self, activated=self._resume_selected)
        QShortcut(QKeySequence('Delete'), self, activated=self._delete_selected)
        QShortcut(QKeySequence('F5'), self, activated=self.load_downloads)

    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = PDMTrayIcon(self)
        self.tray.show_window.connect(self._show_from_tray)
        self.tray.quit_app.connect(self._quit_app)
        self.tray.show()

    def _show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_app(self):
        self._closing = True
        self.torrent_engine.shutdown()
        QApplication.instance().quit()


    def _check_updates(self):
        from core.updater import UpdateChecker
        if not hasattr(self, '_update_checker'):
            self._update_checker = UpdateChecker(self)
            self._update_checker.check_finished.connect(lambda found, msg: self.statusBar().showMessage(msg, 8000))
        self.statusBar().showMessage('Checking for updates...')
        QTimer.singleShot(0, self._update_checker.run)

    def _copy_diagnostics(self):
        from core.updater import diagnostic_bundle
        QApplication.clipboard().setText(diagnostic_bundle())
        self.statusBar().showMessage('Diagnostic bundle copied to clipboard (no personal data).', 5000)

    def closeEvent(self, event):
        if self._closing or not hasattr(self, 'tray'):
            event.accept()
            return
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            event.ignore()
        else:
            event.accept()

    def setup_signals(self):
        self.engine.download_progress.connect(self._on_progress)
        self.engine.download_finished.connect(lambda i, p: self.load_downloads())
        self.engine.status_updated.connect(lambda i, s: self.load_downloads())
        self.engine.metadata_updated.connect(lambda i, s: self.load_downloads())
        self.engine.speed_sampled.connect(self._on_speed_sampled)

    def _on_speed_sampled(self, mbps):
        self._speed_acc += mbps
        self._speed_count += 1
        now = time.time()
        if now - self._last_ui_sync < 0.2:
            return
        self._last_ui_sync = now
        avg = self._speed_acc / max(1, self._speed_count)
        self.status_speed.setText(self._fmt_speed(avg))
        self.stats_view.update_speed(avg)
        self._speed_acc = 0.0
        self._speed_count = 0

    def _on_progress(self, dl_id, percent, speed, eta, total, downloaded):
        self.model.update_task(dl_id, {'percent': percent, 'speed': speed, 'eta': eta, 'total_size': total, 'downloaded_size': downloaded})

    def _on_nav_changed(self, key):
        if key == 'home':
            self.sidebar.select_view('home')
            self.content_stack.setCurrentIndex(self._view_index()['home'])
            self._refresh_home()
            return
        if key in ('all', 'trash'):
            self.nav_filter = key
            self.sidebar.select_view(key)
            self.content_stack.setCurrentIndex(0)
            self.load_downloads()
            return
        idx = self._view_index().get(key)
        if idx is None:
            return
        self.sidebar.select_view(key)
        self.content_stack.setCurrentIndex(idx)
        if key in FILTER_KEYS:
            self.nav_filter = key
            self.sidebar.select_view(key)
            self.content_stack.setCurrentIndex(0)
            self.load_downloads()

    def _on_search(self, text):
        self.model.set_filter(text)

    def _handle_save_settings(self, data):
        from PySide6.QtWidgets import QApplication
        from ui.theme import set_theme
        self.db.set_setting('ui_theme', set_theme(QApplication.instance(), data.get('theme', 'dark')))
        self.db.set_setting('default_download_path', os.path.expanduser(data.get('path', os.path.expanduser('~/Downloads'))))
        self.db.set_setting('cookie_browser', data.get('cookie_browser', '') or '')
        self.db.set_setting('max_concurrent_downloads', data.get('threads', '3 Connections'))
        self.db.set_setting('proxy_enabled', '1' if data.get('proxy') else '0')
        self.db.set_setting('proxy_address', data.get('proxy_addr', ''))
        self.db.set_setting('speed_limit', str(data.get('speed_limit', 0)))
        self.db.set_setting('default_container', data.get('container', 'mp4'))
        self.db.set_setting('auto_retry', str(data.get('auto_retry', 2)))
        self.engine._reload_settings()

    def load_downloads(self):
        self._invalidate_torrent_ids()
        if hasattr(self, 'empty_trash_btn'):
            trashed_count = sum(1 for d in self.db.get_all_downloads_including_trash() if d.get('status') == 'Trash')
            self.empty_trash_btn.setVisible(self.nav_filter == 'trash')
            self.empty_trash_btn.setText(f'Empty Trash ({trashed_count})' if trashed_count else 'Empty Trash')
        self.download_table.setUpdatesEnabled(False)
        all_tasks = self.db.get_all_downloads_including_trash()
        non_trash = [t for t in all_tasks if t['status'] != 'Trash']
        data = non_trash if self.nav_filter == 'all' else [t for t in all_tasks if t['status'] == 'Trash']
        self.model.set_all(data)
        self.model.set_filter(self.toolbar.search_box.text())
        self.download_table.setUpdatesEnabled(True)
        self.sidebar.update_counts({'all': len(non_trash), 'trash': len(all_tasks) - len(non_trash)})
        self._update_status_bar(all_tasks)

    def _update_status_bar(self, all_tasks):
        running = len([t for t in all_tasks if t['status'] in ACTIVE_STATES])
        queued = len([t for t in all_tasks if t['status'] in ('Queued', 'Pending')])
        if running and queued:
            self.status_active.setText(f'{running} active · {queued} queued')
        elif running:
            self.status_active.setText(f'{running} active download' + ('s' if running > 1 else ''))
        elif queued:
            self.status_active.setText(f'{queued} queued')
        else:
            self.status_active.setText('No active downloads')
        total_bytes = sum((t.get('downloaded_size', 0) or 0 for t in all_tasks if t['status'] != 'Trash'))
        self.status_total.setText(f'Library: {self._fmt_size(total_bytes)}')

    def _home_download(self, url):
        if url.startswith(('magnet:',)) or (url.endswith('.torrent') and os.path.exists(url)):
            self.torrent_engine.add(url, self.engine.db.get_setting('default_download_path', os.path.expanduser('~/Downloads')))
            self.load_downloads()
            self._on_nav_changed('torrents')
            return
        dlg = NewDownloadDialog(self, initial_url=url)
        if not dlg.exec():
            return
        data = dlg.get_selected_files()
        for f in data['files']:
            if f.get('is_torrent'):
                self.torrent_engine.add(f['url'], data['path'])
                self._on_nav_changed('torrents')
                continue
            kind = 'hls' if f.get('is_direct_hls') or f.get('stream_kind') == 'hls' else f.get('stream_kind')
            self.engine.add_download(f['url'], f.get('name'), data['path'], is_audio=f.get('is_audio', False), video_fmt=f.get('video_fmt'), audio_fmt=f.get('audio_fmt'), container=f.get('container'), auto_name=f.get('auto_name', True), referer=f.get('referer'), stream_kind=kind)
        self.load_downloads()

    def _resume_all_home(self):
        for t in self.engine.db.get_all_downloads_including_trash():
            if t['status'] == 'Paused':
                self.engine.start_download(t['id'])
        self.load_downloads()

    def _refresh_home(self):
        try:
            tasks = self.engine.db.get_all_downloads_including_trash()
            non_trash = [t for t in tasks if t['status'] != 'Trash']
            active = sum(1 for t in non_trash if t['status'] in ('Downloading', 'Connecting', 'Merging', 'Queued'))
            completed = sum(1 for t in non_trash if t['status'] == 'Completed')
            paused = sum(1 for t in non_trash if t['status'] == 'Paused')
            failed = sum(1 for t in non_trash if t['status'] == 'Failed')
            library = sum((t.get('total_size', 0) or 0) for t in non_trash)
            torrent_n = len(getattr(self.torrent_engine, 'list_torrents', lambda: [])())
            self.home_view.set_stats(active=active, completed=completed, library=self._fmt_size(library), torrents=torrent_n)
            self.home_view.set_attention(paused=paused, failed=failed)
            status_order = {'Downloading': 0, 'Connecting': 1, 'Merging': 2, 'Queued': 3, 'Paused': 4, 'Completed': 5, 'Failed': 6}
            recent = sorted(non_trash, key=lambda t: (status_order.get(t['status'], 9), -(t.get('updated_at') and 1 or 0)))[:5]
            self.home_view.set_recent([(t.get('filename') or t.get('url', ''), t['status'], self._fmt_size(t.get('total_size', 0) or 0)) for t in recent])
        except Exception:
            pass

    def _add_task(self):
        dlg = NewDownloadDialog(self)
        if dlg.exec():
            data = dlg.get_selected_files()
            has_torrent = False
            for f in data['files']:
                if f.get('is_torrent'):
                    self.torrent_engine.add(f['url'], data['path'])
                    has_torrent = True
                    continue
                kind = 'hls' if f.get('is_direct_hls') or f.get('stream_kind') == 'hls' else f.get('stream_kind')
                self.engine.add_download(f['url'], f.get('name'), data['path'], is_audio=f.get('is_audio', False), video_fmt=f.get('video_fmt'), audio_fmt=f.get('audio_fmt'), container=f.get('container'), auto_name=f.get('auto_name', True), referer=f.get('referer'), stream_kind=kind)
            self.load_downloads()
            self._on_nav_changed('torrents' if has_torrent else 'all')

    def _get_selected_ids(self):
        selected = self.download_table.selectionModel().selectedRows()
        return list(set((idx.data(DownloadModel.IdRole) for idx in selected)))

    def _pause_selected(self):
        for i in self._get_selected_ids():
            self.engine.stop_download(i)
        self.load_downloads()

    def _resume_selected(self):
        for i in self._get_selected_ids():
            self.engine.start_download(i)
        self.load_downloads()

    def _delete_selected(self):
        ids = self._get_selected_ids()
        if not ids:
            return
        to_trash = self.nav_filter != 'trash'
        message = 'Move selected downloads to Trash?' if to_trash else 'Permanently delete selected downloads?'
        action = QMessageBox.question(self, 'Delete', message)
        if action == QMessageBox.StandardButton.Yes:
            for i in ids:
                self.engine.cancel_and_delete(i, permanent=not to_trash)
            self.load_downloads()

    def _empty_trash(self):
        prompt = 'Permanently delete everything in Trash?'
        if QMessageBox.question(self, 'Empty Trash', prompt) == QMessageBox.StandardButton.Yes:
            for t in self.db.get_all_downloads_including_trash():
                if t['status'] == 'Trash':
                    self.engine.cancel_and_delete(t['id'], permanent=True)
            self.load_downloads()

    def _selected_row_dicts(self):
        return [self.model.row(idx.row()) for idx in self.download_table.selectionModel().selectedRows()]

    def _show_context_menu(self, pos):
        index = self.download_table.indexAt(pos)
        if not index.isValid():
            if self.nav_filter == 'trash':
                menu = QMenu(self)
                act_empty = menu.addAction('Empty Trash')
                if menu.exec(self.download_table.viewport().mapToGlobal(pos)) == act_empty:
                    self._empty_trash()
            return
        rows = self._selected_row_dicts()
        menu = QMenu(self)
        row = rows[0] if rows else self.model.row(index.row())
        if row and row.get('file_path') and os.path.exists(row['file_path']):
            act_open = menu.addAction('Open File')
            act_folder = menu.addAction('Open Containing Folder')
        else:
            act_open = act_folder = None
            if row and row.get('file_path'):
                menu.addAction('File missing on disk')
        menu.addSeparator()
        act_pause = menu.addAction('Pause')
        act_resume = menu.addAction('Resume')
        act_retry = menu.addAction('Retry')
        menu.addSeparator()
        act_copy = menu.addAction('Copy URL')
        menu.addSeparator()
        act_del = menu.addAction('Delete')
        chosen = menu.exec(self.download_table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == act_open and row:
            QDesktopServices.openUrl(QUrl.fromLocalFile(row['file_path']))
        elif chosen == act_folder and row:
            path = row['file_path']
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path) or path))
        elif chosen == act_pause:
            for r in rows:
                self.engine.stop_download(r['id'])
        elif chosen == act_resume:
            for r in rows:
                self.engine.start_download(r['id'])
        elif chosen == act_retry:
            for r in rows:
                self.engine.start_download(r['id'])
        elif chosen == act_copy:
            QApplication.clipboard().setText(row.get('url', ''))
        elif chosen == act_del:
            ids = [r['id'] for r in rows]
            to_trash = self.nav_filter != 'trash'
            for i in ids:
                self.engine.cancel_and_delete(i, permanent=not to_trash)
        self.load_downloads()

    def _open_selected_file(self, index):
        row = self.model.row(index.row())
        if row and row.get('file_path') and os.path.exists(row['file_path']):
            QDesktopServices.openUrl(QUrl.fromLocalFile(row['file_path']))
if __name__ == '__main__':
    app = QApplication(sys.argv)
    from ui.theme import apply_theme
    apply_theme(app)
    window = PDMMainWindow()
    window.show()
    sys.exit(app.exec())