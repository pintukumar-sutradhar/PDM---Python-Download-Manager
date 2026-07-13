import os
import requests
import mimetypes
from urllib.parse import unquote
import yt_dlp
from core.logger import logger

class MetadataExtractor:
    """Probes URLs for filenames and sizes using HTTP handshakes and specialized engines."""
    @staticmethod
    def get_info(url):
        # 1. Social Domain Check
        social_domains = ['youtube.com', 'youtu.be', 'facebook.com', 'instagram.com', 'tiktok.com', 'twitter.com', 'x.com']
        if any(d in url.lower() for d in social_domains):
            try:
                ydl_opts = {'quiet': True, 'no_warnings': True, 'nocheckcertificate': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    return {
                        "filename": f"{info.get('title', 'download')}.mp4",
                        "size": info.get('filesize') or info.get('filesize_approx') or 0,
                        "is_social": True
                    }
            except: pass

        # 2. Advanced HTTP Probing
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            r = requests.head(url, headers=headers, allow_redirects=True, timeout=5, verify=False)
            
            size = int(r.headers.get('Content-Length', 0))
            if size == 0:
                headers['Range'] = 'bytes=0-0'
                r2 = requests.get(url, headers=headers, allow_redirects=True, timeout=5, verify=False)
                if 'Content-Range' in r2.headers:
                    size = int(r2.headers.get('Content-Range').split('/')[-1])

            filename = ""
            cd = r.headers.get('Content-Disposition')
            if cd and 'filename=' in cd:
                filename = cd.split('filename=')[-1].strip('"').strip("'")
            
            if not filename:
                filename = unquote(url.split('/')[-1].split('?')[0]) or "media_file"
            
            if '.' not in filename:
                ext = mimetypes.guess_extension(r.headers.get('Content-Type', '').split(';')[0]) or ".mp4"
                filename += ext

            return {
                "filename": filename,
                "size": size,
                "is_social": False
            }
        except Exception:
            return None
