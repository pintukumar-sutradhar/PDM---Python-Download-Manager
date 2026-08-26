import os
import time
import threading
from PySide6.QtCore import QObject, Signal, QTimer
from download.worker import DownloadWorker
from core.database import PDMDatabase
from core.logger import logger

class DownloadEngine(QObject):
    download_progress = Signal(int, int, float, str, int, int)
    download_finished = Signal(int, str)
    download_failed = Signal(int, str)
    status_updated = Signal(int, str)
    metadata_updated = Signal(int, int)
    speed_sampled = Signal(float)

    def __init__(self):
        super().__init__()
        self.db = PDMDatabase()
        self.active_workers = {}
        self.queue = []
        self.retry_count = {}
        self._retry_lock = threading.Lock()
        self.max_concurrent = self._parse_int(self.db.get_setting('max_concurrent_downloads', '3'), 3)
        self.auto_retry = self._parse_int(self.db.get_setting('auto_retry', '2'), 2)
        self.speed_limit = self._parse_int(self.db.get_setting('speed_limit', '0'), 0)
        self._live_speeds = {}
        self._last_speed_emit = 0.0
        self._db_sync = {}

    @staticmethod
    def _parse_int(value, default):
        try:
            return int(str(value).replace(' Connections', '').strip())
        except Exception:
            return default

    def _reload_settings(self):
        self.max_concurrent = self._parse_int(self.db.get_setting('max_concurrent_downloads', '3'), 3)
        self.auto_retry = self._parse_int(self.db.get_setting('auto_retry', '2'), 2)
        self.speed_limit = self._parse_int(self.db.get_setting('speed_limit', '0'), 0)

    def add_download(self, url, filename=None, save_dir=None, is_audio=False, video_fmt=None, audio_fmt=None, container=None, auto_name=True, referer=None, stream_kind=None):
        if not save_dir:
            save_dir = os.path.expanduser(self.db.get_setting('default_download_path', os.path.expanduser('~/Downloads')))
        container = container or self.db.get_setting('default_container', 'mp4')
        if is_audio:
            container = 'mp3'
        elif container not in ('mp4', 'mkv'):
            container = 'mp4'
        temp_name = filename or url.split('/')[-1].split('?')[0] or 'initializing'
        if is_audio and (not temp_name.lower().endswith('.mp3')):
            temp_name = os.path.splitext(temp_name)[0] + '.mp3'
        elif not is_audio and (not os.path.splitext(temp_name)[1]):
            temp_name = f'{temp_name}.{container}'
        save_path = os.path.join(save_dir, temp_name)
        ext = os.path.splitext(temp_name)[1].lower().lstrip('.')
        category = None
        try:
            for cat_row in self.db.get_categories():
                exts = [e.strip().lstrip('.').lower() for e in str(cat_row.get('extensions') or '').replace(',', ' ').replace(';', ' ').split() if e.strip()]
                if ext and ext in exts:
                    category = cat_row.get('name')
                    break
        except Exception:
            category = None
        if not hasattr(self, 'stream_meta'):
            self.stream_meta = {}
        self.stream_meta[save_path] = {'referer': referer, 'stream_kind': stream_kind}
        download_id = self.db.add_download(temp_name, url, save_path, category=category or 'General', container=container, video_format=video_fmt, audio_format=audio_fmt, is_audio=is_audio, auto_name=auto_name)
        if not download_id:
            return None
        self.start_download(download_id, is_audio=is_audio, video_fmt=video_fmt, audio_fmt=audio_fmt, container=container, auto_name=auto_name)
        return (download_id, is_audio)



    def start_download(self, download_id, is_audio=None, video_fmt=None, audio_fmt=None, container=None, auto_name=None):
        downloads = self.db.get_all_downloads_including_trash()
        dl_data = next((d for d in downloads if d['id'] == download_id), None)
        if not dl_data:
            return
        if download_id in self.active_workers:
            return
        if len(self.active_workers) >= self.max_concurrent:
            self._mark_queued(download_id)
            if download_id not in self.queue:
                self.queue.append(download_id)
            return
        self._reload_settings()
        container = container or dl_data.get('container') or self.db.get_setting('default_container', 'mp4')
        if video_fmt is None:
            video_fmt = dl_data.get('video_format')
        if audio_fmt is None:
            audio_fmt = dl_data.get('audio_format')
        if is_audio is None:
            is_audio = bool(dl_data.get('is_audio'))
        if auto_name is None:
            auto_name = bool(dl_data.get('auto_name', 1))
        meta = getattr(self, 'stream_meta', {}).pop(dl_data['save_path'], {}) or {}
        worker = DownloadWorker(download_id, dl_data['url'], dl_data['save_path'], is_audio=is_audio, video_fmt=video_fmt, audio_fmt=audio_fmt, container=container, ratelimit=self.speed_limit * 1024 * 1024 if self.speed_limit else None, auto_name=auto_name, referer=meta.get('referer'), stream_kind=meta.get('stream_kind'))
        worker.progress_updated.connect(lambda p, s, e, ts, di, db: self._handle_progress(di, p, s, e, ts, db))
        worker.finished.connect(self._handle_finished)
        worker.failed.connect(self._handle_failed)
        worker.status_changed.connect(self._handle_status_changed)
        self.active_workers[download_id] = worker
        worker.start_download()

    def _mark_queued(self, download_id):
        self.db.update_download_status(download_id, 'Queued')
        self.status_updated.emit(download_id, 'Queued')

    def _process_queue(self):
        while self.queue and len(self.active_workers) < self.max_concurrent:
            next_id = self.queue.pop(0)
            if next_id in self.active_workers:
                continue
            self.start_download(next_id)

    def stop_download(self, download_id):
        if download_id in self.active_workers:
            worker = self.active_workers.pop(download_id)
            worker.pause()
            self._handle_status_changed(download_id, 'Paused')
        elif download_id in self.queue:
            self.queue.remove(download_id)
            self._handle_status_changed(download_id, 'Paused')

    def cancel_and_delete(self, download_id, permanent=False):
        if download_id in self.active_workers:
            worker = self.active_workers.pop(download_id)
            worker.cancel()
        if download_id in self.queue:
            self.queue.remove(download_id)
        downloads = self.db.get_all_downloads_including_trash()
        dl_data = next((d for d in downloads if d['id'] == download_id), None)
        if permanent:
            if dl_data and os.path.exists(dl_data['save_path']):
                try:
                    os.remove(dl_data['save_path'])
                except OSError:
                    pass
            self.db.delete_download_permanently(download_id)
        else:
            self._handle_status_changed(download_id, 'Trash')

    def _handle_status_changed(self, dl_id, status):
        self.db.update_download_status(dl_id, status)
        self.status_updated.emit(dl_id, status)

    def _handle_progress(self, dl_id, percent, speed, eta, total_size, downloaded_bytes):
        now = time.time()
        self._live_speeds[dl_id] = max(0.0, float(speed or 0))
        if now - self._last_speed_emit >= 0.25:
            self._last_speed_emit = now
            self.speed_sampled.emit(sum(self._live_speeds.values()))
        self.download_progress.emit(dl_id, percent, speed, eta, total_size, downloaded_bytes)
        if total_size > 0 and now - self._db_sync.get(dl_id, 0) >= 1.0:
            self._db_sync[dl_id] = now
            self.db.update_download_status(dl_id, 'Downloading', total_size=total_size, downloaded_size=downloaded_bytes)

    def _handle_finished(self, dl_id, path):
        self._live_speeds.pop(dl_id, None)
        self._db_sync.pop(dl_id, None)
        size = os.path.getsize(path) if os.path.exists(path) else 0
        self.db.update_download_status(dl_id, 'Completed', downloaded_size=size, total_size=size)
        self.active_workers.pop(dl_id, None)
        self.retry_count.pop(dl_id, None)
        self.status_updated.emit(dl_id, 'Completed')
        self.download_finished.emit(dl_id, path)
        self._process_queue()

    def _handle_failed(self, dl_id, error):
        self._live_speeds.pop(dl_id, None)
        self._db_sync.pop(dl_id, None)
        self.active_workers.pop(dl_id, None)
        with self._retry_lock:
            attempts = self.retry_count.get(dl_id, 0)
        if attempts < self.auto_retry:
            attempts += 1
            self.retry_count[dl_id] = attempts
            self.db.update_download_status(dl_id, 'Retrying')
            self.status_updated.emit(dl_id, 'Retrying')
            logger.warning(f'Download {dl_id} failed ({error}); retry {attempts}/{self.auto_retry}')
            delay = min(15, 3 * attempts)

            def _retry():
                rows = self.db.get_all_downloads_including_trash()
                cur = next((d for d in rows if d['id'] == dl_id), None)
                if cur and cur['status'] not in ('Trash', 'Completed'):
                    self.start_download(dl_id)
            QTimer.singleShot(delay * 1000, _retry)
        else:
            self.retry_count.pop(dl_id, None)
            self.db.update_download_status(dl_id, 'Failed')
            self.status_updated.emit(dl_id, 'Failed')
            self.download_failed.emit(dl_id, error)
            self._process_queue()