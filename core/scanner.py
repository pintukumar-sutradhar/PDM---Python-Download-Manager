from urllib.parse import urljoin, unquote, urlparse
import requests
import yt_dlp
import os
import time
from core.logger import logger
from core.generic_extractor import GenericVideoExtractor
from core.ott_handlers import OTTHandler
from core.database import PDMDatabase

class Scanner:
    @staticmethod
    def scan_url(url, auth=None):
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        db = PDMDatabase()
        browser = db.get_setting("browser_source", "disabled")
        results = []
        domain = urlparse(url).netloc.lower()
        
        # 1. Fast Mode: Direct Link Detection
        video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.ts', '.m4v', '.m3u8')
        if any(url.lower().split('?')[0].endswith(ext) for ext in video_exts):
            name = unquote(url.split('/')[-1].split('?')[0]) or "media_file"
            return [{'name': name, 'url': url, 'size': 0}]

        # 2. OTT & Premium Script (Custom Handshakes)
        ott_results = OTTHandler.extract(url, cookies=auth.get('cookies') if auth else None)
        if ott_results:
            return ott_results

        # 3. Social Engine (yt-dlp) - Optimized for Speed
        social_domains = ['youtube.com', 'youtu.be', 'facebook.com', 'instagram.com', 'tiktok.com', 'twitter.com', 'x.com']
        if any(d in domain for d in social_domains):
            try:
                ydl_opts = {
                    'quiet': True, 'no_warnings': True, 'extract_flat': True, # Flat for speed
                    'nocheckcertificate': True, 'ignoreerrors': True
                }
                if browser != "disabled": ydl_opts['cookiesfrombrowser'] = (browser,)
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info:
                        if 'entries' in info:
                            for entry in info['entries']:
                                if entry: results.append({'name': f"{entry.get('title', 'video')}.mp4", 'url': entry.get('url') or url, 'size': 0})
                        else:
                            results.append({'name': f"{info.get('title', 'video')}.mp4", 'url': url, 'size': 0})
            except: pass

        # 4. Generic Scraper Fallback
        if not results:
            try:
                generic = GenericVideoExtractor.extract_videos(url)
                if generic: results.extend(generic)
            except: pass

        return results
