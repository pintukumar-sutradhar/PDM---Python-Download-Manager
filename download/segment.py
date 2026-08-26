import requests
import threading
import time
from core.logger import logger

class DownloadSegment(threading.Thread):

    def __init__(self, url, start_byte, end_byte, file_path, segment_id, progress_callback, max_bytes_per_sec=None, headers=None):
        super().__init__()
        self.url = url
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.file_path = file_path
        self.segment_id = segment_id
        self.progress_callback = progress_callback
        self.max_bytes_per_sec = max_bytes_per_sec
        self.extra_headers = dict(headers or {})
        self.downloaded = 0
        self._stop_event = threading.Event()
        self.error = None

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            headers.update(self.extra_headers)
            headers['Range'] = f'bytes={self.start_byte + self.downloaded}-{self.end_byte}'
            response = requests.get(self.url, headers=headers, stream=True, timeout=15, verify=False)
            response.raise_for_status()
            chunk_size = 65536 if self.max_bytes_per_sec else 16384
            with open(self.file_path, 'r+b') as f:
                f.seek(self.start_byte + self.downloaded)
                window_start = time.time()
                window_bytes = 0
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if self._stop_event.is_set():
                        break
                    if chunk:
                        f.write(chunk)
                        self.downloaded += len(chunk)
                        self.progress_callback(len(chunk))
                        if self.max_bytes_per_sec:
                            window_bytes += len(chunk)
                            now = time.time()
                            elapsed = now - window_start
                            budget = self.max_bytes_per_sec * elapsed
                            if window_bytes > budget:
                                deficit = (window_bytes - budget) / self.max_bytes_per_sec
                                if deficit > 0:
                                    self._stop_event.wait(min(deficit, 5.0))
                                    window_start = time.time()
                                    window_bytes = 0
        except Exception as e:
            self.error = str(e)
            logger.error(f'Segment {self.segment_id} error: {self.error}')