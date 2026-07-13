import requests
import threading
import os
from core.logger import logger

class DownloadSegment(threading.Thread):
    def __init__(self, url, start_byte, end_byte, file_path, segment_id, progress_callback, auth=None):
        super().__init__()
        self.url = url
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.file_path = file_path
        self.segment_id = segment_id
        self.progress_callback = progress_callback
        self.auth = auth
        self.downloaded = 0
        self._stop_event = threading.Event()
        self.error = None

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            headers = {
                'Range': f'bytes={self.start_byte + self.downloaded}-{self.end_byte}',
                'User-Agent': 'Mozilla/5.0'
            }
            response = requests.get(self.url, headers=headers, auth=self.auth, stream=True, timeout=15, verify=False)
            response.raise_for_status()

            with open(self.file_path, 'r+b') as f:
                f.seek(self.start_byte + self.downloaded)
                for chunk in response.iter_content(chunk_size=16384):
                    if self._stop_event.is_set():
                        break
                    if chunk:
                        f.write(chunk)
                        self.downloaded += len(chunk)
                        self.progress_callback(len(chunk))
        except Exception as e:
            self.error = str(e)
            logger.error(f"Segment {self.segment_id} error: {self.error}")
