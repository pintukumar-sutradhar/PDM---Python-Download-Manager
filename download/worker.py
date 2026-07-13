import os
import requests
import threading
import time
import yt_dlp
import shutil
from PySide6.QtCore import QObject, Signal
from download.segment import DownloadSegment
from core.logger import logger
from core.metadata import MetadataExtractor
from core.database import PDMDatabase

# Static FFmpeg Initialization
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

# Suppress urllib3 warnings globally
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class DownloadWorker(QObject):
    # Signals: percent (int), speed (float MB/s), eta (str), total_size (int), download_id (int), downloaded_bytes (int)
    progress_updated = Signal(int, float, str, int, int, int)
    finished = Signal(int, str)
    failed = Signal(int, str)
    status_changed = Signal(int, str)

    def __init__(self, download_id, url, save_path, num_connections=8, is_audio=False, auth=None):
        super().__init__()
        self.download_id = download_id
        self.url = url
        self.save_path = save_path
        self.num_connections = num_connections
        self.is_audio = is_audio
        self.auth = auth
        self.total_size = 0
        self.downloaded_total = 0
        self.segments = []
        self._is_paused = False
        self._is_cancelled = False
        self.start_time = 0
        self._last_ui_sync = 0
        self.db = PDMDatabase()

    def start_download(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            self.status_changed.emit(self.download_id, "Initializing")
            
            ffmpeg_path = shutil.which("ffmpeg")
            url_low = self.url.lower()
            
            # Detect protocol
            is_hls = ".m3u8" in url_low.split('?')[0]
            is_social = any(d in url_low for d in ['youtube', 'youtu.be', 'facebook', 'instagram', 'tiktok', 'x.com', 'twitter', 'hoichoi', 'binge', 'bioscope'])

            if is_hls or is_social:
                self._download_via_engine(ffmpeg_path is not None)
            else:
                self._download_direct()

        except Exception as e:
            if not self._is_cancelled and not self._is_paused:
                logger.error(f"Worker Error: {str(e)}")
                self.failed.emit(self.download_id, str(e))

    def _download_via_engine(self, has_ffmpeg):
        """Engine for HLS, Social, and Platform extraction."""
        try:
            self.status_changed.emit(self.download_id, "Authenticating")
            self.start_time = time.time()
            browser = self.db.get_setting("browser_source", "disabled")
            
            def hook(d):
                if self._is_cancelled or self._is_paused: raise Exception("Interrupted")
                if d['status'] == 'downloading':
                    now = time.time()
                    if now - self._last_ui_sync > 0.15: # Faster updates for fluid progress
                        self._last_ui_sync = now
                        self._handle_engine_stats(d)

            temp_dir = os.path.dirname(self.save_path)
            temp_id = f"pdm_work_{self.download_id}"
            out_tmpl = os.path.join(temp_dir, f"{temp_id}.%(ext)s")

            ydl_opts = {
                'outtmpl': out_tmpl,
                'progress_hooks': [hook],
                'quiet': True, 'no_warnings': True, 'nocheckcertificate': True,
                'ignoreerrors': True, 'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            if browser != "disabled": ydl_opts['cookiesfrombrowser'] = (browser,)
            if self.auth:
                if self.auth.get('username'): ydl_opts['username'] = self.auth.get('username')
                if self.auth.get('password'): ydl_opts['password'] = self.auth.get('password')
                if self.auth.get('cookies'):
                    c_file = os.path.join(os.getcwd(), "database", f"cookies_{self.download_id}.txt")
                    self._write_netscape_cookies(self.url, self.auth.get('cookies'), c_file)
                    ydl_opts['cookiefile'] = c_file

            if self.is_audio:
                ydl_opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]})
            else:
                if has_ffmpeg: ydl_opts.update({'format': 'bestvideo+bestaudio/best', 'merge_output_format': 'mp4'})
                else: ydl_opts.update({'format': 'best'})

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                if not info: raise Exception("Stream extraction failed")
                raw_file = ydl.prepare_filename(info)
                base = os.path.splitext(raw_file)[0]
                ext = "mp3" if self.is_audio else "mp4"
                final = f"{base}.{ext}"
                if not os.path.exists(final):
                    if os.path.exists(raw_file): final = raw_file
                    else:
                        matches = [f for f in os.listdir(temp_dir) if f.startswith(temp_id)]
                        if matches: final = os.path.join(temp_dir, matches[0])
                        else: raise Exception("Engine data loss during merge.")
                if os.path.exists(self.save_path): os.remove(self.save_path)
                shutil.move(final, self.save_path)

            if not self._is_cancelled: self.finished.emit(self.download_id, self.save_path)
        except Exception as e:
            if not self._is_cancelled: self.failed.emit(self.download_id, str(e))

    def _handle_engine_stats(self, d):
        p_str = d.get('_percent_str', '0%').replace('%','').strip()
        try: p = int(float(p_str))
        except: p = 0
        speed = d.get('speed', 0) / (1024*1024) if d.get('speed') else 0
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or self.total_size
        if total > 0: self.total_size = total
        downloaded = d.get('downloaded_bytes', 0)
        eta = d.get('_eta_str', '--:--:--')
        if not self._is_paused: self.progress_updated.emit(max(0, min(100, p)), speed, str(eta), self.total_size, self.download_id, downloaded)

    def _download_direct(self):
        """Standard high-speed segmented downloader for FTP/HTTP links."""
        try:
            self.status_changed.emit(self.download_id, "Connecting")
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            auth_val = (self.auth.get('username'), self.auth.get('password')) if self.auth else None
            
            # Initial probe for size
            r = requests.head(self.url, headers=headers, auth=auth_val, allow_redirects=True, timeout=10, verify=False)
            self.total_size = int(r.headers.get('content-length', 0))
            if self.total_size == 0:
                r2 = requests.get(self.url, headers={'Range':'bytes=0-0'}, auth=auth_val, allow_redirects=True, timeout=10, verify=False)
                if 'Content-Range' in r2.headers: self.total_size = int(r2.headers.get('Content-Range').split('/')[-1])
            
            if self.total_size == 0:
                self._fallback_stream(auth_val)
                return

            # Pre-allocate
            with open(self.save_path, 'wb') as f:
                f.truncate(self.total_size)

            segment_size = self.total_size // self.num_connections
            self.start_time = time.time()
            for i in range(self.num_connections):
                if self._is_cancelled or self._is_paused: break
                start = i * segment_size
                end = (i + 1) * segment_size - 1 if i < self.num_connections - 1 else self.total_size - 1
                segment = DownloadSegment(self.url, start, end, self.save_path, i, self._on_progress, auth=auth_val)
                self.segments.append(segment)
                segment.start()

            self.status_changed.emit(self.download_id, "Downloading")
            for s in self.segments: s.join()
            
            if not self._is_cancelled: self.finished.emit(self.download_id, self.save_path)
        except Exception as e:
            self._fallback_stream(auth_val)

    def _fallback_stream(self, auth_val):
        try:
            self.status_changed.emit(self.download_id, "Downloading")
            self.start_time = time.time()
            with requests.get(self.url, headers={"User-Agent": "Mozilla/5.0"}, auth=auth_val, stream=True, timeout=15, verify=False) as r:
                r.raise_for_status()
                self.total_size = int(r.headers.get('content-length', 0))
                downloaded = 0
                with open(self.save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=131072):
                        if self._is_cancelled or self._is_paused: break
                        if chunk:
                            f.write(chunk); downloaded += len(chunk)
                            self.downloaded_total = downloaded; self._on_progress(0)
            if not self._is_cancelled: self.finished.emit(self.download_id, self.save_path)
        except Exception as e:
            if not self._is_cancelled: self.failed.emit(self.download_id, str(e))

    def _on_progress(self, chunk_len):
        if self._is_paused or self._is_cancelled: return
        self.downloaded_total += chunk_len
        now = time.time()
        if now - self._last_ui_sync < 0.15: return # Liquid-smooth 7 FPS throttled updates
        self._last_ui_sync = now
        elapsed = now - self.start_time
        if elapsed > 0 and self.total_size > 0:
            speed = (self.downloaded_total / (1024 * 1024)) / elapsed
            percent = int((self.downloaded_total / self.total_size) * 100)
            rem = self.total_size - self.downloaded_total
            byte_speed = self.downloaded_total / elapsed
            if byte_speed > 10:
                eta_sec = rem / byte_speed
                if eta_sec > 31536000: eta_str = "> 1 Year"
                else:
                    try:
                        m, s = divmod(int(eta_sec), 60)
                        h, m = divmod(m, 60)
                        eta_str = f"{h:02d}:{m:02d}:{s:02d}"
                    except: eta_str = "--:--:--"
            else: eta_str = "--:--:--"
            self.progress_updated.emit(max(0, min(100, percent)), speed, eta_str, self.total_size, self.download_id, self.downloaded_total)

    def _write_netscape_cookies(self, url, cookie_str, filepath):
        try:
            domain = url.split('//')[-1].split('/')[0]
            clean_domain = domain if domain.startswith('.') else f".{domain}"
            with open(filepath, "w") as f:
                f.write("# Netscape HTTP Cookie File\n")
                for pair in cookie_str.split(';'):
                    if '=' in pair:
                        n, v = pair.strip().split('=', 1)
                        f.write(f"{clean_domain}\tTRUE\t/\tFALSE\t0\t{n}\t{v}\n")
        except: pass

    def pause(self): self._is_paused = True; [s.stop() for s in self.segments]
    def cancel(self): self._is_cancelled = True; [s.stop() for s in self.segments]
