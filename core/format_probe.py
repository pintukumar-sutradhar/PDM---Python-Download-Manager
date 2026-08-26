import os
import tempfile
import yt_dlp
from core.database import PDMDatabase
from core.logger import logger
from core.scanner import detect_auth_required

class FormatProbe:
    last_auth_required = False
    last_error = ''

    @staticmethod
    @staticmethod
    def _build_opts():
        from core.jsruntime import apply_ydl_env_opts
        opts = {'quiet': True, 'no_warnings': True, 'nocheckcertificate': True, 'ignoreerrors': True, 'skip_download': True}
        apply_ydl_env_opts(opts)
        return opts

    @staticmethod
    def _detect_drm(info, error=None):
        if info and info.get('has_drm'):
            return True
        if error and 'drm' in str(error).lower():
            return True
        if info:
            for fmt in info.get('formats') or []:
                if fmt.get('has_drm') or fmt.get('drm'):
                    return True
                protocol = str(fmt.get('protocol') or '')
                if 'widevine' in protocol.lower() or 'drm' in protocol.lower():
                    return True
        return False

    @staticmethod
    def probe(url):
        FormatProbe.last_auth_required = False
        FormatProbe.last_error = ''
        try:
            opts = FormatProbe._build_opts()
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if not info:
                return None
            if FormatProbe._detect_drm(info):
                return {'title': info.get('title') or 'media', 'video_formats': [], 'audio_formats': [], 'drm': True, 'info': info}
            formats = info.get('formats') or []
            video_formats = []
            audio_formats = []
            seen_video = set()
            seen_audio = set()
            for fmt in formats:
                vcodec = fmt.get('vcodec') or 'none'
                acodec = fmt.get('acodec') or 'none'
                has_video = vcodec != 'none'
                has_audio = acodec != 'none'
                if has_video and (not has_audio):
                    key = (fmt.get('height'), int(fmt.get('fps') or 0), fmt.get('dynamic_range'), fmt.get('vcodec'))
                    if key not in seen_video:
                        seen_video.add(key)
                        video_formats.append(fmt)
                elif has_audio and (not has_video):
                    key = (fmt.get('abr'), fmt.get('acodec'))
                    if key not in seen_audio:
                        seen_audio.add(key)
                        audio_formats.append(fmt)
            if not video_formats and (not audio_formats):
                combined = [f for f in formats if (f.get('vcodec') or 'none') != 'none' and (f.get('acodec') or 'none') != 'none']
                combined.sort(key=lambda f: f.get('height') or 0, reverse=True)
                for fmt in combined:
                    key = (fmt.get('height'), int(fmt.get('fps') or 0))
                    if key not in seen_video:
                        seen_video.add(key)
                        video_formats.append(fmt)
                if combined:
                    best = combined[0]
                    audio_formats.append({'format_id': best['format_id'], 'acodec': best.get('acodec'), 'abr': best.get('abr'), 'ext': best.get('ext'), 'combined': True})
            return {'title': info.get('title') or info.get('fulltitle') or 'download', 'video_formats': video_formats, 'audio_formats': audio_formats, 'drm': False, 'info': info}
        except Exception as e:
            FormatProbe.last_error = str(e)
            FormatProbe.last_auth_required = detect_auth_required(str(e))
            logger.warning(f'Format probe failed for {url}: {str(e)}')
            if FormatProbe._detect_drm(None, error=e):
                return {'title': 'media', 'video_formats': [], 'audio_formats': [], 'drm': True, 'info': None}
            return None