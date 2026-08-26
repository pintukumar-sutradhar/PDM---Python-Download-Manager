import re
import json
from urllib.parse import urlparse, urljoin

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'

STREAM_RE = re.compile(r'https?(?::\\?/\\?/)[^"\'\s<>]+?\.(?:m3u8|mpd|mp4)(?:\?[^"\'\s<>]*)?', re.IGNORECASE)
LOGIN_MARKERS = ('login', 'sign-in', 'signin', 'log-in', 'auth/login', '/account/login')
DRM_HINTS = ('widevine', 'playready', 'fairplay', 'drm', 'license_server', 'getlicense')
STREAM_EXTS = ('.m3u8', '.mpd', '.mp4')


class SuperScan:
    last_login_required = False
    last_drm = False
    last_auth_required = False
    last_error = ''

    @staticmethod
    def _session(cookie_browser=None, cookie_header=''):
        sess = requests.Session()
        sess.headers.update({'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9'})
        if cookie_browser:
            try:
                import yt_dlp
                with yt_dlp.YoutubeDL({'quiet': True, 'cookiesfrombrowser': (cookie_browser,)}) as ydl:
                    sess.cookies.update(ydl.cookiejar)
            except Exception:
                pass
        if cookie_header:
            sess.headers['Cookie'] = cookie_header
        sess.verify = False
        return sess

    @staticmethod
    def harvest(url, cookie_browser=None, cookie_header=''):
        out = {'streams': [], 'login_required': False, 'drm': False, 'error': ''}
        SuperScan.last_login_required = False
        SuperScan.last_drm = False
        SuperScan.last_auth_required = False
        SuperScan.last_error = ''
        host = urlparse(url).netloc
        try:
            sess = SuperScan._session(cookie_browser, cookie_header)
            resp = sess.get(url, timeout=20, allow_redirects=True, headers={'Referer': url})
        except Exception as e:
            SuperScan.last_error = str(e)
            out['error'] = str(e)
            return out

        final_url = resp.url or url
        page = resp.text or ''
        lowered = page.lower()

        if resp.status_code in (401, 403) or any(m in final_url.lower() for m in LOGIN_MARKERS):
            SuperScan.last_login_required = True
            out['login_required'] = True
        if not out['login_required'] and not STREAM_HITS(page) and any(m in lowered[:6000] for m in LOGIN_MARKERS) and ('password' in lowered or 'otp' in lowered):
            SuperScan.last_login_required = True
            out['login_required'] = True

        candidates = collect_streams(page, final_url)
        for script_src in linked_scripts(page, final_url)[:6]:
            try:
                r2 = sess.get(script_src, timeout=15, headers={'Referer': final_url})
                if r2.status_code == 200:
                    candidates |= collect_streams(r2.text, script_src)
            except Exception:
                continue

        seen = set()
        for stream_url in candidates:
            key = stream_url.split('?')[0]
            if key in seen:
                continue
            seen.add(key)
            low = stream_url.lower()
            kind = 'hls' if '.m3u8' in low else ('dash' if '.mpd' in low else 'mp4')
            drm_here = kind == 'dash' or any(h in low for h in ('widevine', 'drm', 'playready')) or any(h in lowered and kind == 'dash' for h in DRM_HINTS)
            name = build_name(stream_url, host, kind)
            out['streams'].append({'name': name, 'url': stream_url, 'kind': kind, 'referer': final_url, 'drm': bool(drm_here)})
            if drm_here:
                SuperScan.last_drm = True
                out['drm'] = True
        if not out['streams'] and not out['error']:
            SuperScan.last_error = ''
        if out['streams']:
            locked = SuperScan._probe_locked(sess, out['streams'], final_url)
            if locked:
                SuperScan.last_auth_required = True
                out['auth_required'] = True
        return out

    @staticmethod
    def _probe_locked(sess, streams, referer):
        """Verify harvested manifests are genuinely downloadable. Walks
        manifest -> first variant -> first segment; any 401/403 (or an HTML
        page pretending to be a manifest) means the site only serves real
        files to signed-in sessions."""
        tried = 0
        for s in streams:
            if tried >= 2:
                break
            if s.get('drm'):
                continue
            tried += 1
            try:
                if SuperScan._stream_locked(sess, s['url'], referer):
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _stream_locked(sess, url, referer):
        r = sess.get(url, timeout=8, headers={'Referer': referer})
        if r.status_code in (401, 403):
            return True
        body = (r.text or '')[:262144]
        stripped = body.lstrip().lower()
        if stripped.startswith('<!doctype') or stripped.startswith('<html'):
            return True
        if '.mpd' in url.lower():
            return False
        try:
            import m3u8 as m3u8_lib
            parsed = m3u8_lib.loads(body)
        except Exception:
            return False
        if getattr(parsed, 'is_variant', False) and parsed.playlists:
            variant = urljoin(url, parsed.playlists[0].uri)
            r2 = sess.get(variant, timeout=8, headers={'Referer': referer})
            if r2.status_code in (401, 403):
                return True
            base = variant
            try:
                parsed = m3u8_lib.loads(r2.text or '')
            except Exception:
                return False
        else:
            base = url
        segments = list(getattr(parsed, 'segments', []) or [])
        keys = [k for k in (getattr(parsed, 'keys', None) or []) if k and getattr(k, 'method', '') not in (None, 'NONE', '')]
        if not keys and segments:
            keys = [s.key for s in segments if s.key and s.key.method not in (None, 'NONE', '')]
        if keys and keys[0].uri:
            kurl = keys[0].uri
            if not kurl.startswith('http'):
                kurl = urljoin(base, kurl)
            try:
                rk = sess.get(kurl, timeout=8, headers={'Referer': referer})
                if rk.status_code in (401, 403):
                    return True
            except Exception:
                return True
        segments = list(getattr(parsed, 'segments', []) or [])
        if segments:
            seg_uri = segments[0].uri
            seg_url = seg_uri if seg_uri.startswith('http') else urljoin(base, seg_uri)
            init = getattr(segments[0], 'init_section', None)
            checks = [seg_url]
            if init is not None:
                init_uri = getattr(init, 'uri', None) or (init.get('uri') if isinstance(init, dict) else None)
                if init_uri:
                    checks.insert(0, init_uri if init_uri.startswith('http') else urljoin(base, init_uri))
            for check_url in checks:
                r3 = sess.get(check_url, timeout=8, headers={'Referer': referer, 'Range': 'bytes=0-0'})
                if r3.status_code in (401, 403):
                    return True
        return False


def STREAM_HITS(text):
    return STREAM_RE.findall(text or '')


def collect_streams(text, base_url):
    hits = set()
    for match in STREAM_RE.findall(text or ''):
        cleaned = match.replace('\\/', '/').replace('\\u0026', '&').strip()
        if cleaned.startswith('http'):
            hits.add(cleaned)
        else:
            hits.add(urljoin(base_url, '/' + cleaned.lstrip('/')))
    try:
        data = json.loads(_first_json_blob(text)) if _first_json_blob(text) else None
        for _, val in _walk(data or {}):
            if isinstance(val, str) and val.lower().split('?')[0].endswith(STREAM_EXTS):
                hits.add(val if val.startswith('http') else urljoin(base_url, val))
    except Exception:
        pass
    return hits


def linked_scripts(html, base_url):
    srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html or '', re.IGNORECASE)
    out = []
    for s in srcs:
        full = urljoin(base_url, s)
        if any(k in full.lower() for k in ('app.', 'main.', 'config', 'player', 'bundle')):
            out.append(full)
    return out + [u for u in (urljoin(base_url, s) for s in srcs) if u not in out]


def _first_json_blob(text):
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    for i in range(start, min(len(text), start + 400000)):
        ch = text[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _walk(obj, depth=0):
    if depth > 12:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            yield from _walk(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v, depth + 1)


def build_name(stream_url, host, kind):
    label = urlparse(stream_url).path.rstrip('/').split('/')[-1] or 'stream'
    label = re.sub(r'\.(m3u8|mpd|mp4)$', '', label, flags=re.IGNORECASE)
    label = re.sub(r'[^A-Za-z0-9._-]+', '_', label)[:60] or 'stream'
    tag = {'hls': 'HLS', 'dash': 'DASH[DRM?]', 'mp4': 'MP4'}[kind]
    site = host.replace('www.', '').split('.')[0].title()
    return f'{site} · {label} [{tag}]'
