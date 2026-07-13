import os
import threading
import time
import requests
import m3u8
import shutil
import subprocess
from core.logger import logger

class HLSStreamEngine:
    """Proprietary PDM module for handling M3U8 stream acquisition and merging."""
    
    def __init__(self, url, save_path, auth=None, progress_callback=None):
        self.url = url
        self.save_path = save_path
        self.auth = auth
        self.progress_callback = progress_callback
        self.is_cancelled = False
        self.temp_dir = os.path.join(os.path.dirname(save_path), ".pdm_cache")

    def start(self):
        try:
            if not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            }
            if self.auth and self.auth.get('cookies'):
                headers['Cookie'] = self.auth.get('cookies')

            # 1. Parse Playlist
            response = requests.get(self.url, headers=headers, timeout=15, verify=False)
            playlist = m3u8.loads(response.text)
            
            # If master playlist, pick best variant
            if playlist.is_variant:
                best_variant = max(playlist.playlists, key=lambda p: p.stream_info.bandwidth or 0)
                variant_url = urljoin(self.url, best_variant.uri)
                response = requests.get(variant_url, headers=headers, timeout=15, verify=False)
                playlist = m3u8.loads(response.text)

            segments = playlist.segments
            total_segments = len(segments)
            
            # 2. Download Segments
            segment_files = []
            for i, segment in enumerate(segments):
                if self.is_cancelled: break
                
                seg_url = urljoin(self.url, segment.uri)
                seg_file = os.path.join(self.temp_dir, f"seg_{i}.ts")
                
                with requests.get(seg_url, headers=headers, stream=True, timeout=10, verify=False) as r:
                    with open(seg_file, 'wb') as f:
                        shutil.copyfileobj(r.raw, f)
                
                segment_files.append(seg_file)
                
                if self.progress_callback:
                    percent = int(((i + 1) / total_segments) * 100)
                    # Throttled progress call
                    self.progress_callback(percent, 0.0, "Merging...")

            # 3. Merge Segments using FFmpeg
            if not self.is_cancelled:
                self._merge_ffmpeg(segment_files)
                
            # 4. Cleanup
            shutil.rmtree(self.temp_dir)
            return True

        except Exception as e:
            logger.error(f"HLS Engine Failure: {str(e)}")
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
            return False

    def _merge_ffmpeg(self, files):
        list_file = os.path.join(self.temp_dir, "list.txt")
        with open(list_file, "w") as f:
            for file in files:
                f.write(f"file '{os.path.abspath(file)}'\n")
        
        ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
        cmd = [
            ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", 
            "-i", list_file, "-c", "copy", self.save_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)

    def cancel(self):
        self.is_cancelled = True

from urllib.parse import urljoin
