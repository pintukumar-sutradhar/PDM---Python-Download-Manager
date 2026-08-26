import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
from core.logger import logger

class GenericVideoExtractor:

    @staticmethod
    def extract_videos(url):
        videos = []
        video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.ts', '.m4v')
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            for video in soup.find_all('video'):
                src = video.get('src')
                if src:
                    videos.append(src)
                for source in video.find_all('source'):
                    src = source.get('src')
                    if src:
                        videos.append(src)
            for a in soup.find_all('a'):
                href = a.get('href')
                if href and any((href.lower().split('?')[0].endswith(ext) for ext in video_exts)):
                    videos.append(href)
            for iframe in soup.find_all('iframe'):
                src = iframe.get('src')
                if src and ('.mp4' in src.lower() or 'm3u8' in src.lower()):
                    videos.append(src)
            results = []
            seen_urls = set()
            for v_url in videos:
                full_url = urljoin(url, v_url)
                if full_url not in seen_urls:
                    name = unquote(full_url.split('/')[-1].split('?')[0]) or 'video_file'
                    results.append({'name': name, 'url': full_url})
                    seen_urls.add(full_url)
            return results
        except Exception as e:
            logger.error(f'Generic extraction failed for {url}: {str(e)}')
            return []