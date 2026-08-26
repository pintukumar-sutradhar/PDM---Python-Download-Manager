import os
import threading
import time
from PySide6.QtCore import QObject, Signal

from core.logger import logger

try:
    import libtorrent as lt
    HAS_LIBTORRENT = True
except Exception:
    lt = None
    HAS_LIBTORRENT = False


class TorrentEngine(QObject):
    torrent_added = Signal(str)
    metadata_resolved = Signal(str, str)
    progress = Signal(str, float, float, float, float, str)
    finished = Signal(str, str, float)
    failed = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session = None
        self._handles = {}
        self._results = {}
        self._stop_flag = threading.Event()
        self._thread = None
        self._sequential = False
        self._last_loop_error = ''
        self._rates = {}

    @property
    def available(self):
        return HAS_LIBTORRENT

    def _ensure_session(self):
        if self._session is None:
            self._session = lt.session({'listen_interfaces': '0.0.0.0:6881', 'alert_mask': lt.alert.category_t.error_notification | lt.alert.category_t.status_notification})
            self._session.add_dht_node(('router.bittorrent.com', 6881))
            self._session.add_dht_node(('dht.transmissionbt.com', 6881))
        return self._session

    def add(self, source, save_dir):
        import os as _os
        save_dir = _os.path.expanduser(save_dir or '~/Downloads')
        if not HAS_LIBTORRENT:
            self.failed.emit(source, 'BitTorrent support unavailable: libtorrent not installed')
            return False
        if source.startswith('magnet:') or os.path.exists(source):
            try:
                ses = self._ensure_session()
                if source.startswith('magnet:'):
                    atp = lt.parse_magnet_uri(source)
                else:
                    atp = lt.add_torrent_params()
                    atp.ti = lt.torrent_info(source)
                atp.save_path = os.path.expanduser(save_dir or '~/Downloads')
                label = atp.name or os.path.basename(source)
                flags = atp.flags | lt.torrent_flags.duplicate_is_error | lt.torrent_flags.auto_managed
                if self._sequential:
                    flags |= lt.torrent_flags.sequential_download
                atp.flags = flags
                handle = ses.add_torrent(atp)
                self._handles[handle.info_hashes().v1] = {'handle': handle, 'label': label, 'resolved': not source.startswith('magnet:'), 'save_path': atp.save_path}
                try:
                    from core.database import PDMDatabase
                    PDMDatabase().add_torrent_record(source, label, atp.save_path)
                except Exception:
                    pass
                self.torrent_added.emit(label)
                self._start_loop()
                return True
            except Exception as e:
                msg = str(e) or type(e).__name__
                self.failed.emit(source, msg if 'duplicate' not in msg.lower() else 'Torrent already added')
                return False
        self.failed.emit(source, 'Not a magnet link or .torrent file')
        return False

    def set_sequential(self, enabled):
        self._sequential = bool(enabled)
        for entry in self._handles.values():
            try:
                h = entry['handle']
                h.unset_flags(lt.torrent_flags.sequential_download) if not self._sequential else h.set_flags(lt.torrent_flags.sequential_download)
            except Exception:
                pass

    def pause_all(self):
        for entry in self._handles.values():
            try:
                entry['handle'].pause()
            except Exception:
                pass

    def resume_all(self):
        for entry in self._handles.values():
            try:
                entry['handle'].resume()
            except Exception:
                pass

    def _find_key_by_label(self, label):
        for key, entry in self._handles.items():
            if entry['label'] == label:
                return key
        return None

    def remove(self, label):
        key = self._find_key_by_label(label)
        if key is None:
            return False
        entry = self._handles.pop(key, None)
        if entry and self._session is not None:
            try:
                self._session.remove_torrent(entry['handle'])
            except Exception:
                pass
        self._results.pop(key, None)
        try:
            from core.database import PDMDatabase
            PDMDatabase().delete_torrent_record(label)
        except Exception:
            pass
        return True

    def clear_all(self):
        for key in list(self._handles.keys()):
            entry = self._handles.pop(key, None)
            if entry and self._session is not None:
                try:
                    self._session.remove_torrent(entry['handle'])
                except Exception:
                    pass
        self._results.clear()
        try:
            from core.database import PDMDatabase
            PDMDatabase().delete_all_torrent_records()
        except Exception:
            pass

    def remove_finished(self):
        for key in list(self._results.keys()):
            entry = self._handles.pop(key, None)
            if entry:
                try:
                    self._session.remove_torrent(entry['handle'])
                except Exception:
                    pass
                try:
                    from core.database import PDMDatabase
                    PDMDatabase().delete_torrent_record(entry['label'])
                except Exception:
                    pass
            self._results.pop(key, None)

    def _start_loop(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        last_emit = 0.0
        while not self._stop_flag.is_set():
            time.sleep(0.5)
            if self._session is None:
                break
            for key in list(self._handles.keys()):
                entry = self._handles.get(key)
                if not entry:
                    continue
                try:
                    st = entry['handle'].status()
                    now = time.time()
                    state_map = {lt.torrent_status.downloading: 'Downloading', lt.torrent_status.downloading_metadata: 'Fetching metadata', lt.torrent_status.finished: 'Seeding', lt.torrent_status.seeding: 'Seeding', lt.torrent_status.checking_files: 'Checking', lt.torrent_status.checking_resume_data: 'Checking resume data', lt.torrent_status.allocating: 'Allocating'}
                    state = state_map.get(st.state, 'Queued')
                    if bool(st.flags & lt.torrent_flags.paused):
                        state = 'Paused'
                    elif state == 'Queued' and st.num_peers == 0:
                        state = f'Connecting · {st.num_pieces} pieces'
                    total = max(1, st.total_wanted)
                    pct = max(0.0, min(100.0, st.progress * 100.0))
                    speed_mb = st.download_payload_rate / (1024 * 1024)
                    self._rates[entry['label']] = speed_mb
                    if (not entry.get('resolved')) and entry['handle'].torrent_file():
                        real_name = entry['handle'].torrent_file().name()
                        entry['resolved'] = True
                        old_label = entry['label']
                        entry['label'] = real_name
                        self._rates[real_name] = self._rates.pop(old_label, 0.0)
                        try:
                            from core.database import PDMDatabase
                            PDMDatabase().rename_torrent_record(old_label, real_name)
                        except Exception:
                            pass
                        self.metadata_resolved.emit(old_label, real_name)
                    if pct >= 99.999 and key not in self._results:
                        tf = entry['handle'].torrent_file()
                        final_name = tf.name() if tf else entry['label']
                        self._results[key] = final_name
                        size_bytes = int(st.total_wanted)
                        try:
                            from core.database import PDMDatabase
                            PDMDatabase().complete_torrent_record(final_name, size_bytes)
                        except Exception:
                            pass
                        self.finished.emit(final_name, final_name, float(size_bytes))
                    elif now - last_emit > 0.9:
                        self.progress.emit(entry['label'], float(min(st.total_wanted_done, total)), float(total), pct, speed_mb, f'{state} · {speed_mb:.2f} MB/s · peers {st.num_peers}')
                        try:
                            from core.database import PDMDatabase
                            PDMDatabase().update_torrent_progress(entry['label'], int(st.total_wanted_done), int(total))
                        except Exception:
                            pass
                        last_emit = now
                except Exception as e:
                    err_key = f'{type(e).__name__}: {e}'
                    if self._last_loop_error != err_key:
                        self._last_loop_error = err_key
                        logger.error(f'Torrent poll error: {err_key}')

    def aggregate_rate(self):
        return sum(self._rates.values())

    def shutdown(self):
        self._rates.clear()
        self._stop_flag.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
