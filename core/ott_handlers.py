import requests
import re
import json
import os
from urllib.parse import urlparse, urljoin
from core.logger import logger

class OTTHandler:
    """Internal PDM module for standalone media extraction without yt-dlp."""
    
    @staticmethod
    def extract(url, cookies=None):
        domain = urlparse(url).netloc.lower()
        
        # Professional standard headers to bypass bot detection
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Referer': url,
            'Origin': f"{urlparse(url).scheme}://{domain}",
            'Accept': '*/*',
        }
        
        if cookies:
            headers['Cookie'] = cookies

        # Site-specific logic
        if 'hoichoi' in domain:
            return OTTHandler._handle_hoichoi(url, headers)
        if 'bioscope' in domain:
            return OTTHandler._handle_bioscope(url, headers)
        if 'binge' in domain:
            return OTTHandler._handle_binge(url, headers)

        # Direct M3U8 probe (Generic)
        if url.lower().split('?')[0].endswith('.m3u8'):
            return [{'name': 'Direct_Stream', 'url': url, 'is_direct_hls': True}]

        return []

    @staticmethod
    def _handle_hoichoi(url, headers):
        """Custom Hoichoi Logic: Handles direct CDNs and session keys."""
        try:
            logger.info(f"Custom Hoichoi script probing: {url}")
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            
            # 1. Search for M3U8 links in the response
            # Some CDNs return 401 if Referer or SessionID is missing in the sub-requests
            matches = re.findall(r'https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*', response.text)
            
            # 2. Extract Title from metadata if possible
            title = "Hoichoi_Media"
            title_match = re.search(r'<title>(.*?)</title>', response.text)
            if title_match:
                title = title_match.group(1).split('|')[0].strip()

            results = []
            for m in set(matches):
                stream_url = m.replace('\\', '')
                results.append({
                    'name': title, 
                    'url': stream_url, 
                    'is_direct_hls': True,
                    'headers': headers # Pass headers for the downloader to use
                })
            
            # 3. Handle direct CDN links (the ones user pastes)
            if not results and '.m3u8' in url.lower():
                 results.append({'name': 'Hoichoi_CDN_Stream', 'url': url, 'is_direct_hls': True, 'headers': headers})

            return results
        except Exception as e:
            logger.error(f"Hoichoi script failed: {str(e)}")
            return []

    @staticmethod
    def _handle_bioscope(url, headers):
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=False)
            match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', response.text)
            if match:
                state = json.loads(match.group(1))
                details = state.get('video', {}).get('details', {})
                src = details.get('video_url')
                if src:
                    return [{
                        'name': details.get('title', 'Bioscope_Video'), 
                        'url': src, 
                        'is_direct_hls': src.endswith('.m3u8'),
                        'headers': headers
                    }]
            return []
        except Exception:
            return []

    @staticmethod
    def _handle_binge(url, headers):
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=False)
            matches = re.findall(r'https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*', response.text)
            return [{'name': 'Binge_Stream', 'url': m, 'is_direct_hls': True, 'headers': headers} for m in set(matches)]
        except Exception:
            return []
