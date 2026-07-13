import os
import threading
from PySide6.QtCore import QObject, Signal, QTimer
from download.worker import DownloadWorker
from core.database import PDMDatabase
from core.logger import logger
from core.metadata import MetadataExtractor

class DownloadEngine(QObject):
    # id, percentage, speed, eta, total_size, downloaded_bytes
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

    def add_download(self, url, filename=None, save_dir=None, is_audio=False, auth=None):
        if not save_dir:
            save_dir = self.db.get_setting("default_download_path", os.path.expanduser("~/Downloads"))
        
        temp_name = filename or url.split('/')[-1].split('?')[0] or "initializing"
        if is_audio and not temp_name.lower().endswith(".mp3"):
            temp_name = os.path.splitext(temp_name)[0] + ".mp3"
            
        save_path = os.path.join(save_dir, temp_name)
        download_id = self.db.add_download(temp_name, url, save_path)
        if not download_id: return None

        self.start_download(download_id, is_audio=is_audio, auth=auth)
        return (download_id, is_audio)

    def start_download(self, download_id, is_audio=False, auth=None):
        downloads = self.db.get_all_downloads_including_trash()
        dl_data = next((d for d in downloads if d['id'] == download_id), None)
        if not dl_data: return

        self.stop_download(download_id)
        
        worker = DownloadWorker(download_id, dl_data['url'], dl_data['save_path'], is_audio=is_audio, auth=auth)
        worker.progress_updated.connect(lambda p, s, e, ts, di, db: self._handle_progress(di, p, s, e, ts, db))
        worker.finished.connect(self._handle_finished)
        worker.failed.connect(self._handle_failed)
        worker.status_changed.connect(self._handle_status_changed)
        
        self.active_workers[download_id] = worker
        worker.start_download()

    def stop_download(self, download_id):
        if download_id in self.active_workers:
            worker = self.active_workers.pop(download_id)
            worker.pause()
            self._handle_status_changed(download_id, "Paused")

    def cancel_and_delete(self, download_id, permanent=False):
        if download_id in self.active_workers:
            worker = self.active_workers.pop(download_id)
            worker.cancel()
        
        downloads = self.db.get_all_downloads_including_trash()
        dl_data = next((d for d in downloads if d['id'] == download_id), None)
        
        if permanent:
            if dl_data and os.path.exists(dl_data['save_path']):
                try: os.remove(dl_data['save_path'])
                except: pass
            self.db.delete_download_permanently(download_id)
        else:
            self._handle_status_changed(download_id, "Trash")

    def _handle_status_changed(self, dl_id, status):
        self.db.update_download_status(dl_id, status)
        self.status_updated.emit(dl_id, status)

    def _handle_progress(self, dl_id, percent, speed, eta, total_size, downloaded_bytes):
        self.download_progress.emit(dl_id, percent, speed, eta, total_size, downloaded_bytes)
        if total_size > 0:
            # Atomic update to DB only if size found
            self.db.update_download_status(dl_id, "Downloading", total_size=total_size, downloaded_size=downloaded_bytes)

    def _handle_finished(self, dl_id, path):
        size = os.path.getsize(path) if os.path.exists(path) else 0
        self.db.update_download_status(dl_id, "Completed", downloaded_size=size, total_size=size)
        self.active_workers.pop(dl_id, None)
        self.status_updated.emit(dl_id, "Completed")
        self.download_finished.emit(dl_id, path)

    def _handle_failed(self, dl_id, error):
        self.db.update_download_status(dl_id, "Failed")
        self.active_workers.pop(dl_id, None)
        self.status_updated.emit(dl_id, "Failed")
        self.download_failed.emit(dl_id, error)
