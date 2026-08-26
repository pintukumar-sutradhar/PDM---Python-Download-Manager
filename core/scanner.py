from urllib.parse import unquote, urlparse
import yt_dlp
from core.logger import logger
from core.generic_extractor import GenericVideoExtractor
from core.ott_handlers import OTTHandler
from core.database import PDMDatabase
AUTH_HINTS = ('sign in', 'signin', 'sign-in', 'login', 'logged in', 'log in', 'authentication', 'authenticate', 'auth required', 'requires authentication', 'requires an account', 'need an account', 'account required', 'members only', 'member-only', 'private video', 'private', 'premium', 'not available in your country', 'geo', 'access denied', 'unauthorized', '401', '403', 'need to log', 'please log', 'verify you', 'captcha', 'cookies are needed', 'cookies (not necessarily logged in)', '--cookies-from-browser')

def detect_auth_required(error_text):
    text = (error_text or '').lower()
    return any((hint in text for hint in AUTH_HINTS))

class Scanner:
    last_auth_required = False
    last_error = ''

    @staticmethod
    def scan_url(url, cookie_file=None):
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        Scanner.last_auth_required = False
        Scanner.last_error = ''
        db = PDMDatabase()
        results = []
        domain = urlparse(url).netloc.lower()
        video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.ts', '.m4v', '.m3u8')
        if any((url.lower().split('?')[0].endswith(ext) for ext in video_exts)):
            name = unquote(url.split('/')[-1].split('?')[0]) or 'media_file'
            return [{'name': name, 'url': url, 'size': 0}]
        try:
            ott_results = OTTHandler.extract(url)
        except Exception as e:
            Scanner.last_error = str(e)
            if detect_auth_required(str(e)):
                Scanner.last_auth_required = True
            ott_results = None
        if ott_results:
            return ott_results
        cookie_browser = ''
        try:
            cookie_browser = (db.get_setting('cookie_browser', '') or '').strip().lower()
        except Exception:
            pass
        from core.jsruntime import js_runtime_opts
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True, 'nocheckcertificate': True, 'ignoreerrors': False}
        ydl_opts.update(js_runtime_opts())
        if cookie_file:
            ydl_opts['cookiefile'] = cookie_file
        try:
            from core.jsruntime import apply_ydl_env_opts
            apply_ydl_env_opts(ydl_opts)
        except Exception:
            pass
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    if info.get('has_drm'):
                        logger.warning(f'DRM-protected media detected at {url}')
                        return [{'name': f"{info.get('title', 'media')} [DRM-PROTECTED]", 'url': url, 'size': 0, 'drm': True}]
                    if 'entries' in info:
                        for entry in info['entries']:
                            if entry:
                                results.append({'name': f"{entry.get('title', 'video')}.mp4", 'url': entry.get('url') or url, 'size': 0})
                    else:
                        results.append({'name': f"{info.get('title', 'video')}.mp4", 'url': url, 'size': 0})
        except Exception as e:
            Scanner.last_error = str(e)
            if detect_auth_required(str(e)):
                Scanner.last_auth_required = True
            if 'drm' in str(e).lower():
                logger.warning(f'DRM-protected media detected at {url}')
                return [{'name': 'DRM-Protected Media', 'url': url, 'size': 0, 'drm': True}]
            logger.debug(f'Social extraction failed for {url}: {str(e)}')
        if not results:
            try:
                from core.ott_superscan import SuperScan
                from core import weblogin as _wl
                scan = SuperScan.harvest(url, cookie_browser or None, cookie_header=_wl.cookie_header_for(url))
                if scan['streams']:
                    for s in scan['streams'][:12]:
                        if s.get('drm'):
                            continue
                        item = {'name': s['name'], 'url': s['url'], 'size': 0, 'is_ott': True, 'referer': s.get('referer')}
                        if s['kind'] == 'hls':
                            item['is_direct_hls'] = True
                        results.append(item)
                    if scan['drm']:
                        results.insert(0, {'name': 'DRM-protected stream detected on this page (not downloadable)', 'url': url, 'size': 0, 'drm': True})
                    if scan.get('auth_required') or SuperScan.last_auth_required:
                        Scanner.last_auth_required = True
                    return results
                if scan['login_required']:
                    Scanner.last_auth_required = True
                    Scanner.last_error = 'Page requires sign-in'
                    return []
                if scan['drm']:
                    return [{'name': 'DRM-protected content detected on this page', 'url': url, 'size': 0, 'drm': True}]
                if scan['error']:
                    Scanner.last_error = scan['error']
            except Exception as e:
                logger.debug(f'SuperScan failed for {url}: {e}')
        if not results:
            try:
                generic = GenericVideoExtractor.extract_videos(url)
                if generic:
                    results.extend(generic)
            except Exception as e:
                Scanner.last_error = str(e)
                if detect_auth_required(str(e)):
                    Scanner.last_auth_required = True
        return results