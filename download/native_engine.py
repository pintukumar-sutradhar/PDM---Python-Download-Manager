import os
import time
import shutil
import queue
import threading
import subprocess
import requests
from core.logger import logger
from core.constants import USER_AGENT
try:
    import m3u8
except ImportError:
    m3u8 = None
CHUNK_SIZE = 131072

class NativeUnsupportedError(Exception):
    pass

class StopFlags:

    def __init__(self):
        self.cancelled = False
        self.paused = False

def _wait_if_paused(stop):
    while stop.paused and (not stop.cancelled):
        time.sleep(0.15)

def fetch_segment(url, dest_path, headers=None, stop=None, retries=3):
    headers = headers or {'User-Agent': USER_AGENT}
    tmp = dest_path + '.part'
    last_err = None
    for attempt in range(retries):
        if stop and stop.cancelled:
            return False
        try:
            with requests.get(url, headers=headers, stream=True, timeout=(10, 30), verify=False) as r:
                r.raise_for_status()
                with open(tmp, 'wb') as f:
                    for chunk in r.iter_content(CHUNK_SIZE):
                        if stop and stop.cancelled:
                            raise InterruptedError
                        if stop and stop.paused:
                            _wait_if_paused(stop)
                        if chunk:
                            f.write(chunk)
            os.replace(tmp, dest_path)
            return True
        except InterruptedError:
            raise
        except Exception as e:
            last_err = e
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f'segment failed after {retries} attempts: {last_err}')

class NativeHlsDownloader:

    def __init__(self, url, output_path, num_connections=6, ratelimit=None, stop=None, on_bytes=None, on_status=None, extra_headers=None):
        self.url = url
        self.output_path = output_path
        self.num_connections = max(1, num_connections)
        self.ratelimit = ratelimit
        self.stop = stop or StopFlags()
        self.on_bytes = on_bytes
        self.on_status = on_status
        self.headers = {'User-Agent': USER_AGENT}
        for k, v in (extra_headers or {}).items():
            self.headers[k] = v
        self.work_dir = output_path + '_parts'
        self.est_total_bytes = 0

    def _status(self, text):
        if self.on_status:
            self.on_status(text)

    def _load_playlist(self):
        if m3u8 is None:
            raise NativeUnsupportedError('m3u8 library unavailable')
        r = requests.get(self.url, headers=self.headers, timeout=15, verify=False)
        r.raise_for_status()
        pl = m3u8.loads(r.text)
        if pl.is_variant:
            best = max(pl.playlists, key=lambda p: p.stream_info.bandwidth or 0)
            variant_url = _absolute(self.url, best.uri)
            r2 = requests.get(variant_url, headers=self.headers, timeout=15, verify=False)
            r2.raise_for_status()
            pl = m3u8.loads(r2.text)
            base = variant_url
            bandwidth = best.stream_info.bandwidth or 0
        else:
            base = self.url
            bandwidth = 0
        if any((k and (k.method or 'NONE') != 'NONE' for k in pl.keys)):
            raise NativeUnsupportedError('encrypted HLS stream')
        segments = [_absolute(base, s.uri) for s in pl.segments]
        duration = sum((s.duration or 0 for s in pl.segments))
        if bandwidth and duration:
            self.est_total_bytes = int(duration * bandwidth / 8)
        return (segments, pl)

    def run(self):
        segments, _ = self._load_playlist()
        if not segments:
            raise RuntimeError('empty HLS manifest')
        os.makedirs(self.work_dir, exist_ok=True)
        self._status('Downloading')
        q = queue.Queue()
        for idx, seg_url in enumerate(segments):
            q.put((idx, seg_url))
        errors = []
        lock = threading.Lock()

        def worker():
            while not q.empty() and (not self.stop.cancelled):
                try:
                    idx, seg_url = q.get_nowait()
                except queue.Empty:
                    return
                part = os.path.join(self.work_dir, f'{idx:06d}.ts')
                if os.path.exists(part):
                    q.task_done()
                    continue
                _wait_if_paused(self.stop)
                try:
                    fetch_segment(seg_url, part, self.headers, self.stop)
                    if self.on_bytes:
                        try:
                            self.on_bytes(os.path.getsize(part))
                        except OSError:
                            pass
                except InterruptedError:
                    with lock:
                        errors.append('cancelled')
                    return
                except Exception as e:
                    with lock:
                        errors.append(str(e))
                    return
                finally:
                    q.task_done()
        threads = [threading.Thread(target=worker, daemon=True) for _ in range(min(self.num_connections, len(segments)))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if self.stop.cancelled:
            raise InterruptedError
        if errors:
            raise RuntimeError(f'HLS segments failed: {errors[0]}')
        self._assemble(segments)

    def _assemble(self, segments):
        self._status('Merging')
        merged_ts = self.output_path
        with open(merged_ts, 'wb') as out:
            for idx in range(len(segments)):
                part = os.path.join(self.work_dir, f'{idx:06d}.ts')
                with open(part, 'rb') as pf:
                    shutil.copyfileobj(pf, out, CHUNK_SIZE)
        shutil.rmtree(self.work_dir, ignore_errors=True)

    def cleanup(self):
        shutil.rmtree(self.work_dir, ignore_errors=True)

def remux_to_container(input_ts, output_path, container='mp4'):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        return False
    cmd = [ffmpeg, '-y', '-loglevel', 'error', '-i', input_ts, '-c', 'copy', '-movflags', '+faststart', output_path]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        return result.returncode == 0 and os.path.exists(output_path)
    except (subprocess.TimeoutExpired, OSError):
        return False

def _absolute(base_url, uri):
    if not uri:
        return base_url
    if uri.startswith('http://') or uri.startswith('https://'):
        return uri
    if uri.startswith('/'):
        from urllib.parse import urlparse
        p = urlparse(base_url)
        return f'{p.scheme}://{p.netloc}{uri}'
    return base_url.rsplit('/', 1)[0] + '/' + uri
logger.debug('native download core initialized')