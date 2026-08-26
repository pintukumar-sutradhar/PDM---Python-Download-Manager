import os
import requests
import threading
import time
import yt_dlp
import shutil
from PySide6.QtCore import QObject, Signal
from download.segment import DownloadSegment
from download.native_engine import NativeHlsDownloader, NativeUnsupportedError, StopFlags, remux_to_container
from core.logger import logger
from core.namer import MediaNamer
from core.database import PDMDatabase
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from core.constants import USER_AGENT
DIRECT_MEDIA_EXTS = ('.mp4', '.mkv', '.webm', '.mov', '.avi', '.ts', '.m2ts', '.m4v', '.flv', '.mp3', '.m4a', '.aac', '.ogg', '.opus', '.flac', '.wav', '.zip', '.rar', '.7z', '.pdf', '.apk', '.iso')

class DownloadWorker(QObject):
    progress_updated = Signal(int, float, str, int, int, int)
    finished = Signal(int, str)
    failed = Signal(int, str)
    status_changed = Signal(int, str)

    def __init__(self, download_id, url, save_path, num_connections=8, is_audio=False, video_fmt=None, audio_fmt=None, container='mp4', ratelimit=None, auto_name=True, referer=None, stream_kind=None):
        super().__init__()
        self.download_id = download_id
        self.url = url
        self.save_path = save_path
        self.num_connections = num_connections
        self.is_audio = is_audio
        self.video_fmt = video_fmt
        self.audio_fmt = audio_fmt
        self.container = container or 'mp4'
        self.ratelimit = ratelimit
        self.auto_name = auto_name
        self.referer = referer
        self.stream_kind = stream_kind
        self.total_size = 0
        self.downloaded_total = 0
        self.segments = []
        self._is_paused = False
        self._is_cancelled = False
        self._streaming_started = False
        self.start_time = 0
        self._last_ui_sync = 0
        self._progress_lock = threading.Lock()
        self.db = PDMDatabase()

    def _set_status(self, status, error_message=None):
        self.status_changed.emit(self.download_id, status)
        try:
            self.db.update_download_status(self.download_id, status)
            if error_message is not None:
                with self.db._get_connection() as conn:
                    conn.execute('UPDATE downloads SET error_message = ? WHERE id = ?', (error_message, self.download_id))
                    conn.commit()
        except Exception:
            pass

    def start_download(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            self._set_status('Initializing')
            ffmpeg_path = shutil.which('ffmpeg')
            if not ffmpeg_path:
                try:
                    from static_ffmpeg_paths import get_ffmpeg_paths
                    fdir = os.path.dirname(get_ffmpeg_paths()[0])
                    os.environ['PATH'] = fdir + os.pathsep + os.environ.get('PATH', '')
                    ffmpeg_path = shutil.which('ffmpeg') or get_ffmpeg_paths()[0]
                except Exception:
                    pass
            url_low = self.url.lower()
            is_hls = '.m3u8' in url_low.split('?')[0]
            is_dash = '.mpd' in url_low.split('?')[0]
            is_direct_media = url_low.split('?')[0].endswith(DIRECT_MEDIA_EXTS)
            is_ott_stream = bool(self.stream_kind in ('hls', 'dash')) or is_hls or is_dash
            from core.nre import available as nre_available
            if is_ott_stream and nre_available():
                self._download_via_nre()
            elif is_hls:
                self._download_native_hls()
            elif is_dash:
                self._download_via_engine(ffmpeg_path is not None)
            elif is_direct_media:
                self._download_direct()
            else:
                self._download_via_engine(ffmpeg_path is not None)
        except Exception as e:
            if not self._is_cancelled and (not self._is_paused):
                logger.error(f'Worker Error: {str(e)}')
                self._set_status('Failed', str(e))
                self.failed.emit(self.download_id, str(e))

    def _download_via_engine(self, has_ffmpeg):
        self._extraction_succeeded = False
        try:
            import yt_dlp as _ydl_mod
            from core.jsruntime import detect_js_runtime
            logger.info(f'Download {self.download_id} start: ytdlp={_ydl_mod.version.__version__} js={detect_js_runtime()} ffmpeg={has_ffmpeg} url={self.url[:90]}')
            self.start_time = time.time()
            self._set_status('Connecting')

            def hook(d):
                if self._is_cancelled or self._is_paused:
                    raise Exception('Interrupted')
                if d['status'] == 'downloading':
                    if not self._streaming_started:
                        self._streaming_started = True
                        self._set_status('Downloading')
                    now = time.time()
                    if now - self._last_ui_sync > 0.15:
                        self._last_ui_sync = now
                        self._handle_engine_stats(d)
                elif d['status'] == 'finished':
                    self._set_status('Merging')
            temp_dir = os.path.dirname(self.save_path)
            temp_id = f'pdm_work_{self.download_id}'
            out_tmpl = os.path.join(temp_dir, f'{temp_id}.%(ext)s')
            ydl_opts = {'outtmpl': out_tmpl, 'progress_hooks': [hook], 'quiet': True, 'no_warnings': True, 'noprogress': True, 'nocheckcertificate': True, 'ignoreerrors': False, 'retries': 3, 'fragment_retries': 3, 'concurrent_fragment_downloads': min(max(1, self.num_connections), 8)}
            from core.jsruntime import apply_ydl_env_opts
            apply_ydl_env_opts(ydl_opts)
            from core import weblogin as _wl
            saved_cookie_file = _wl.cookie_file_for(self.url)
            if saved_cookie_file:
                ydl_opts['cookiefile'] = saved_cookie_file
                logger.info(f'Using saved login session for {self.url.split("/")[2]}')
            if self.ratelimit:
                ydl_opts['ratelimit'] = int(self.ratelimit)
            if self.is_audio:
                ydl_opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]})
            else:
                if self.video_fmt:
                    fmt = f"{self.video_fmt}+{self.audio_fmt or 'bestaudio'}/{self.video_fmt}/best"
                    ydl_opts['format'] = fmt
                elif has_ffmpeg:
                    ydl_opts.update({'format': 'bestvideo+bestaudio/best', 'merge_output_format': self.container})
                else:
                    ydl_opts.update({'format': 'best'})
                if has_ffmpeg and (not self.is_audio):
                    ydl_opts['merge_output_format'] = self.container

            def run_engine(opts):
                with yt_dlp.YoutubeDL(opts) as ydl:
                    inf = ydl.extract_info(self.url, download=True)
                if not inf:
                    raise Exception('Stream extraction failed')
                return inf
            hls_only = 'bestvideo[protocol*=m3u8]+bestaudio[protocol*=m3u8]/best[protocol*=m3u8]/bestvideo+bestaudio/best'
            ydl_opts['cachedir'] = False
            stages = [('default streams', {}), ('HLS variants', {'format': hls_only})]
            info = None
            last_err = None
            for attempt_round in range(3):
                for label, patch in stages:
                    if self._is_cancelled or self._is_paused:
                        raise Exception('Interrupted')
                    opts_try = dict(ydl_opts)
                    opts_try.update(patch)
                    try:
                        info = run_engine(opts_try)
                        break
                    except Exception as stage_err:
                        msg = str(stage_err)
                        if '403' not in msg and 'forbidden' not in msg.lower():
                            raise
                        logger.warning(f'Media stream blocked (403) on {label}; rotating strategy')
                        last_err = stage_err
                if info is not None:
                    break
                cool = 4 * (attempt_round + 1)
                logger.warning(f'All strategies blocked; cooling down {cool}s for fresh media tokens')
                time.sleep(cool)
            if info is None:
                raise last_err
            self._extraction_succeeded = True
            final = self._locate_output(info, temp_dir, temp_id)
            self._apply_smart_name(final, info)
            if not self._is_cancelled:
                self._set_status('Finished')
                self.finished.emit(self.download_id, self.save_path)
        except Exception as e:
            self._cleanup_partials(os.path.dirname(self.save_path), f'pdm_work_{self.download_id}')
            if not self._is_cancelled:
                err = str(e)
                logger.error(f'Engine download failed ({err})')
                self._set_status('Failed', err)
                self.failed.emit(self.download_id, err)

    def _cleanup_partials(self, temp_dir, temp_id):
        try:
            for f in os.listdir(temp_dir):
                if f.startswith(temp_id):
                    try:
                        os.remove(os.path.join(temp_dir, f))
                    except OSError:
                        pass
        except OSError:
            pass

    def _cleanup_nre_tmp(self, final_path):
        base = os.path.splitext(os.path.basename(final_path))[0]
        tmp_dir = os.path.join(os.path.dirname(final_path), f'.pdm_tmp_{base}')
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        self._cleanup_partials(os.path.dirname(final_path), os.path.basename(base))

    def _locate_output(self, info, temp_dir, temp_id):
        ext = info.get('ext') or 'ext'
        raw_file = os.path.join(temp_dir, f'{temp_id}.{ext}')
        base = os.path.splitext(raw_file)[0]
        ext = 'mp3' if self.is_audio else self.container
        final = f'{base}.{ext}'
        if os.path.exists(final):
            return final
        if os.path.exists(raw_file):
            return raw_file
        matches = [f for f in os.listdir(temp_dir) if f.startswith(temp_id)]
        if matches:
            return os.path.join(temp_dir, matches[0])
        raise Exception('Engine data loss during merge.')

    def _apply_smart_name(self, final, info):
        if not self.auto_name:
            if os.path.exists(self.save_path):
                os.remove(self.save_path)
            shutil.move(final, self.save_path)
        else:
            actual_video = None
            actual_audio = None
            if info and (not self.is_audio):
                if (info.get('vcodec') or 'none') != 'none':
                    actual_video = {'height': info.get('height'), 'fps': info.get('fps'), 'vcodec': info.get('vcodec'), 'dynamic_range': info.get('dynamic_range'), 'tbr': info.get('tbr')}
                if (info.get('acodec') or 'none') != 'none':
                    actual_audio = {'acodec': info.get('acodec'), 'abr': info.get('abr')}
            if not self.is_audio and actual_video is None:
                actual_video = self._find_format(info, self.video_fmt)
            if actual_audio is None:
                actual_audio = self._find_audio_format(info, self.audio_fmt)
            if self.is_audio and actual_audio is None and info:
                actual_audio = {'acodec': 'MP3', 'abr': 192}
            new_name = MediaNamer.build_filename(info, self.url, container='mp3' if self.is_audio else self.container, video_fmt=actual_video, audio_fmt=actual_audio)
            target = MediaNamer.unique_path(os.path.dirname(self.save_path), new_name)
            if os.path.abspath(final) != os.path.abspath(target):
                if os.path.exists(target):
                    os.remove(target)
                shutil.move(final, target)
            self.save_path = target
        self.db.update_download_path(self.download_id, os.path.basename(self.save_path), self.save_path)

    def _find_format(self, info, format_id):
        if not info:
            return None
        for fmt in info.get('formats') or []:
            if fmt.get('format_id') == format_id:
                return fmt
        best = None
        for fmt in info.get('formats') or []:
            if (fmt.get('vcodec') or 'none') != 'none' and (fmt.get('acodec') or 'none') == 'none':
                if best is None or (fmt.get('height') or 0) > (best.get('height') or 0):
                    best = fmt
        return best

    def _find_audio_format(self, info, format_id):
        if not info:
            return None
        for fmt in info.get('formats') or []:
            if fmt.get('format_id') == format_id:
                return fmt
        best = None
        for fmt in info.get('formats') or []:
            if (fmt.get('acodec') or 'none') != 'none' and (fmt.get('vcodec') or 'none') == 'none':
                if best is None or (fmt.get('abr') or 0) > (best.get('abr') or 0):
                    best = fmt
        return best

    def _handle_engine_stats(self, d):
        downloaded = d.get('downloaded_bytes') or 0
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or self.total_size
        if total > 0:
            self.total_size = total
        p = int(downloaded * 100 / total) if total > 0 else 0
        speed = (d.get('speed') or 0) / (1024 * 1024)
        eta_raw = d.get('eta')
        if isinstance(eta_raw, (int, float)) and eta_raw >= 0:
            m, s = divmod(int(eta_raw), 60)
            h, m = divmod(m, 60)
            eta = f'{h:02d}:{m:02d}:{s:02d}'
        else:
            eta = '--:--:--'
        if not self._is_paused:
            self.progress_updated.emit(max(0, min(100, p)), speed, eta, self.total_size, self.download_id, downloaded)

    def _download_via_nre(self):
        from core import nre
        self.start_time = time.time()
        self._set_status('Connecting')
        stop = StopFlags()
        self._hls_stop = stop
        temp_dir = os.path.dirname(self.save_path)
        final_path = self.save_path
        last = {'t': 0.0}

        def on_progress(pct, speed_mb):
            if pct is None:
                return
            now = time.time()
            if now - last['t'] < 0.2 and pct < 100:
                return
            last['t'] = now
            if not self._streaming_started:
                self._streaming_started = True
                self._set_status('Downloading')
            total = self.total_size or 0
            done_bytes = int(total * pct / 100) if total else 0
            speed = speed_mb or 0.0
            eta = '--:--:--'
            if speed > 0 and total:
                secs = int(max(0, total - done_bytes) / (speed * 1048576))
                h, rem = divmod(secs, 3600)
                m, sec = divmod(rem, 60)
                eta = f'{h:02d}:{m:02d}:{sec:02d}'
            if not self._is_paused and not self._is_cancelled:
                self.progress_updated.emit(max(0, min(100, int(pct))), speed, eta, total, self.download_id, done_bytes)

        ok, info = nre.run_download(self.url, final_path, referer=self.referer, num_connections=self.num_connections, on_progress=on_progress, should_stop=lambda: self._is_cancelled or self._is_paused, headers=self._session_headers())
        if self._is_cancelled:
            self._cleanup_nre_tmp(final_path)
            raise Exception('Interrupted')
        if self._is_paused:
            self._set_status('Paused')
            return
        if ok:
            located = None
            base = os.path.splitext(final_path)[0]
            for cand in (final_path, base + '.mp4', base + '.mkv', base + '.ts'):
                if os.path.exists(cand):
                    located = cand
                    break
            if not located:
                for f in sorted(os.listdir(temp_dir)):
                    if f.startswith(os.path.basename(base)):
                        located = os.path.join(temp_dir, f)
                        break
            if not located:
                raise Exception('N_m3u8DL-RE produced no output')
            size = os.path.getsize(located)
            if located != final_path:
                try:
                    os.replace(located, final_path)
                except Exception:
                    final_path = located
            self.downloaded_total = size
            self.total_size = size or self.total_size
            self._set_status('Completed')
            self.finished.emit(self.download_id, final_path)
        else:
            logger.warning(f'NRE failed ({info}); falling back')
            ffmpeg_path = shutil.which('ffmpeg')
            if '.m3u8' in self.url.lower().split('?')[0]:
                self._download_native_hls()
            else:
                self._download_via_engine(ffmpeg_path is not None)

    def _session_headers(self):
        hdrs = {}
        if self.referer:
            hdrs['Referer'] = self.referer
        try:
            from core import weblogin as _wl
            ck = _wl.cookie_header_for(self.url)
            if self.referer:
                page_ck = _wl.cookie_header_for(self.referer)
                if page_ck:
                    seen = {p.split('=', 1)[0] for p in ck.split('; ') if '=' in p}
                    extra = [p for p in page_ck.split('; ') if '=' in p and p.split('=', 1)[0] not in seen]
                    ck = '; '.join([ck] + extra) if ck else '; '.join(extra)
            if ck:
                hdrs['Cookie'] = ck
        except Exception:
            pass
        return hdrs

    def _download_native_hls(self):
        stop = StopFlags()
        self._hls_stop = stop
        self.start_time = time.time()
        temp_dir = os.path.dirname(self.save_path)
        merged_ts = os.path.join(temp_dir, f'pdm_work_{self.download_id}.ts')

        def on_status(text):
            self.status_changed.emit(self.download_id, text)

        def on_bytes(n):
            with self._progress_lock:
                self.downloaded_total += n
            now = time.time()
            if now - self._last_ui_sync < 0.15:
                return
            self._last_ui_sync = now
            elapsed = max(now - self.start_time, 0.001)
            speed = self.downloaded_total / (1024 * 1024) / elapsed
            total = self.total_size
            percent = min(99, int(self.downloaded_total / total * 100)) if total else 0
            byte_speed = self.downloaded_total / elapsed
            eta_str = '--:--:--'
            if total and byte_speed > 10:
                m, s = divmod(max(0, int((total - self.downloaded_total) / byte_speed)), 60)
                h, m = divmod(m, 60)
                eta_str = f'{h:02d}:{m:02d}:{s:02d}'
            self.progress_updated.emit(max(0, percent), speed, eta_str, total, self.download_id, self.downloaded_total)
        try:
            self._set_status('Connecting')
            engine = NativeHlsDownloader(self.url, merged_ts, num_connections=self.num_connections, ratelimit=self.ratelimit, stop=stop, on_bytes=on_bytes, on_status=on_status, extra_headers=self._session_headers())
            self._hls_engine = engine
            engine.run()
            if engine.est_total_bytes:
                self.total_size = engine.est_total_bytes
            if self._is_cancelled:
                return
            if self._is_paused:
                self._set_status('Paused')
                return
            if not self._finalize_hls(merged_ts):
                raise RuntimeError('HLS assembly failed')
            self.finished.emit(self.download_id, self.save_path)
        except NativeUnsupportedError:
            logger.info('Native engine unsupported for this stream; using extraction fallback')
            self._cleanup_partials(temp_dir, f'pdm_work_{self.download_id}')
            self._download_via_engine(shutil.which('ffmpeg') is not None)
        except Exception as e:
            engine = getattr(self, '_hls_engine', None)
            if engine:
                engine.cleanup()
            self._cleanup_partials(temp_dir, f'pdm_work_{self.download_id}')
            if not self._is_cancelled and (not self._is_paused):
                self.failed.emit(self.download_id, str(e))

    def _finalize_hls(self, merged_ts):
        container = (self.container or 'mp4').lower()
        target_ext = 'mp3' if self.is_audio else container
        base = os.path.splitext(self.save_path)[0]
        final = f'{base}.{target_ext}'
        if not self.is_audio and container in ('mp4', 'mkv'):
            if remux_to_container(merged_ts, final, container):
                os.remove(merged_ts)
                self.save_path = final
                self.db.update_download_path(self.download_id, os.path.basename(final), final)
                return True
        if os.path.exists(merged_ts):
            if os.path.abspath(merged_ts) != os.path.abspath(self.save_path):
                if os.path.exists(self.save_path):
                    os.remove(self.save_path)
                shutil.move(merged_ts, self.save_path)
            return True
        return False

    def _download_direct(self):
        try:
            self._set_status('Connecting')
            headers = {'User-Agent': USER_AGENT}
            if self.referer:
                headers['Referer'] = self.referer
            r = requests.head(self.url, headers=headers, allow_redirects=True, timeout=10, verify=False)
            ctype = (r.headers.get('content-type') or '').lower()
            if 'text/html' in ctype:
                raise ValueError('URL is a web page, not a direct media link')
            self.total_size = int(r.headers.get('content-length', 0))
            if self.total_size == 0:
                r2 = requests.get(self.url, headers={'Range': 'bytes=0-0', **headers}, allow_redirects=True, timeout=10, verify=False)
                if 'Content-Range' in r2.headers:
                    self.total_size = int(r2.headers.get('Content-Range').split('/')[-1])
            if self.total_size == 0:
                self._fallback_stream()
                return
            num_conn = max(1, min(self.num_connections, self.total_size // 1048576 or 1))
            segment_size = self.total_size // num_conn
            if segment_size == 0:
                self._fallback_stream()
                return
            with open(self.save_path, 'wb') as f:
                f.truncate(self.total_size)
            per_seg_limit = None
            if self.ratelimit:
                per_seg_limit = max(8192, int(self.ratelimit) // num_conn)
            self.start_time = time.time()
            for i in range(num_conn):
                if self._is_cancelled or self._is_paused:
                    break
                start = i * segment_size
                end = (i + 1) * segment_size - 1 if i < num_conn - 1 else self.total_size - 1
                segment = DownloadSegment(self.url, start, end, self.save_path, i, self._on_progress, max_bytes_per_sec=per_seg_limit, headers=headers)
                self.segments.append(segment)
                segment.start()
            self._set_status('Downloading')
            for s in self.segments:
                s.join()
            if self._is_cancelled:
                return
            if self._is_paused:
                self._set_status('Paused')
                return
            if self.total_size and self.downloaded_total < self.total_size * 0.999:
                raise ValueError(f'Incomplete download ({self.downloaded_total}/{self.total_size} bytes); segments failed')
            self._set_status('Finished')
            self.finished.emit(self.download_id, self.save_path)
        except Exception:
            self._fallback_stream()

    def _fallback_stream(self):
        try:
            self._set_status('Downloading')
            self.start_time = time.time()
            headers = {'User-Agent': USER_AGENT}
            if self.referer:
                headers['Referer'] = self.referer
            with requests.get(self.url, headers=headers, stream=True, timeout=15, verify=False) as r:
                r.raise_for_status()
                ctype = (r.headers.get('content-type') or '').lower()
                if 'text/html' in ctype:
                    raise ValueError('URL is a web page, not a direct media link')
                self.total_size = int(r.headers.get('content-length', 0))
                downloaded = 0
                window_start = time.time()
                window_bytes = 0
                with open(self.save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=131072):
                        if self._is_cancelled or self._is_paused:
                            break
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            self.downloaded_total = downloaded
                            self._on_progress(len(chunk))
                            if self.ratelimit:
                                window_bytes += len(chunk)
                                now = time.time()
                                budget = self.ratelimit * (now - window_start)
                                if window_bytes > budget:
                                    deficit = (window_bytes - budget) / self.ratelimit
                                    time.sleep(min(deficit, 5.0))
                                    window_start = time.time()
                                    window_bytes = 0
            if not self._is_cancelled and not self._is_paused:
                self._set_status('Finished')
                self.finished.emit(self.download_id, self.save_path)
            elif self._is_paused:
                self._set_status('Paused')
        except Exception as e:
            if not self._is_cancelled:
                self.failed.emit(self.download_id, str(e))

    def _on_progress(self, chunk_len):
        if self._is_paused or self._is_cancelled:
            return
        with self._progress_lock:
            self.downloaded_total += chunk_len
        now = time.time()
        if now - self._last_ui_sync < 0.15:
            return
        self._last_ui_sync = now
        elapsed = now - self.start_time
        if elapsed > 0 and self.total_size > 0:
            speed = self.downloaded_total / (1024 * 1024) / elapsed
            percent = int(self.downloaded_total / self.total_size * 100)
            rem = self.total_size - self.downloaded_total
            byte_speed = self.downloaded_total / elapsed
            if byte_speed > 10:
                eta_sec = rem / byte_speed
                if eta_sec > 31536000:
                    eta_str = '> 1 Year'
                else:
                    try:
                        m, s = divmod(int(eta_sec), 60)
                        h, m = divmod(m, 60)
                        eta_str = f'{h:02d}:{m:02d}:{s:02d}'
                    except ValueError:
                        eta_str = '--:--:--'
            else:
                eta_str = '--:--:--'
            self.progress_updated.emit(max(0, min(100, percent)), speed, eta_str, self.total_size, self.download_id, self.downloaded_total)

    def pause(self):
        self._is_paused = True
        for s in self.segments:
            s.stop()
        stop = getattr(self, '_hls_stop', None)
        if stop:
            stop.paused = True

    def cancel(self):
        self._is_cancelled = True
        for s in self.segments:
            s.stop()
        stop = getattr(self, '_hls_stop', None)
        if stop:
            stop.cancelled = True