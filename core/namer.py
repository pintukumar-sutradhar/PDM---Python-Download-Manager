import os
import re
from urllib.parse import urlparse
_ILLEGAL = re.compile('[<>:"/\\\\|?*\\x00-\\x1f]')
_SPACES = re.compile('\\s+')

def sanitize(name, max_len=160):
    if not name:
        return 'download'
    name = _ILLEGAL.sub('', str(name))
    name = _SPACES.sub(' ', name).strip(' .')
    if not name:
        name = 'download'
    return name[:max_len].strip()

def quality_label(video_fmt):
    if not video_fmt:
        return ''
    height = int(video_fmt.get('height') or 0)
    fps = int(video_fmt.get('fps') or 0)
    hdr = bool(video_fmt.get('dynamic_range') in ('HDR', 'HDR10', 'HDR10+', 'DV'))
    bitrate = int(video_fmt.get('tbr') or video_fmt.get('vbr') or 0)
    if height >= 2160:
        label = '2160p'
    elif height >= 1440:
        label = '1440p'
    elif height >= 1080:
        label = '1080p'
    elif height >= 720:
        label = '720p'
    elif height >= 480:
        label = '480p'
    elif height >= 360:
        label = '360p'
    else:
        label = 'SD'
    if fps >= 55:
        label += f'{fps}'
    if hdr:
        label += ' HDR'
    elif bitrate >= 8000 and height >= 1080:
        label += ' High'
    return label
_CODEC_LABELS = {'mp4a.40.2': 'AAC', 'mp4a.40.5': 'HE-AAC', 'mp4a.40.29': 'AAC', 'mp4a.40.3': 'AAC', 'mp4a': 'AAC', 'aac': 'AAC', 'mp4a.40': 'AAC', 'opus': 'Opus', 'vorbis': 'Vorbis', 'flac': 'FLAC', 'mp3': 'MP3', 'ac-3': 'AC3', 'ec-3': 'EAC3', 'ac3': 'AC3', 'eac3': 'EAC3', 'dts': 'DTS', 'truehd': 'TrueHD', 'pcm': 'PCM', 'wav': 'WAV', 'avc1': 'H.264', 'h264': 'H.264', 'h265': 'H.265', 'hevc': 'H.265', 'vp9': 'VP9', 'vp8': 'VP8', 'av01': 'AV1', 'theora': 'Theora'}

def video_codec_name(codec):
    codec = (codec or '').lower()
    if codec in _CODEC_LABELS:
        return _CODEC_LABELS[codec]
    if codec.startswith('avc1'):
        return 'H.264'
    if codec.startswith('hevc'):
        return 'H.265'
    if codec.startswith('vp9'):
        return 'VP9'
    if codec.startswith('av01'):
        return 'AV1'
    parts = codec.split('.')
    return (parts[0] if parts else '').upper()

def _codec_name(codec):
    codec = (codec or '').lower()
    if codec in _CODEC_LABELS:
        return _CODEC_LABELS[codec]
    parts = codec.split('.')
    if len(parts) > 2:
        base = '.'.join(parts[:2])
        if base in _CODEC_LABELS:
            return _CODEC_LABELS[base]
    return (parts[0] if parts else '').upper()

def audio_label(audio_fmt):
    if not audio_fmt:
        return ''
    codec = _codec_name(audio_fmt.get('acodec'))
    abr = int(audio_fmt.get('abr') or 0)
    if abr >= 320:
        abr = 320
    elif abr >= 256:
        abr = 256
    elif abr >= 192:
        abr = 192
    elif abr >= 128:
        abr = 128
    elif abr >= 96:
        abr = 96
    elif abr >= 64:
        abr = 64
    else:
        abr = 0
    label = codec if codec else 'Audio'
    if abr:
        label += f' {abr}kbps'
    return label

def platform_label(url):
    domain = urlparse(url).netloc.lower()
    domain = domain[4:] if domain.startswith('www.') else domain
    parts = domain.split('.')
    core = parts[-2] if len(parts) > 1 else parts[0]
    return core.replace('-', ' ').replace('_', ' ').title()

class MediaNamer:

    @staticmethod
    def build_filename(info, url, container='mp4', video_fmt=None, audio_fmt=None):
        title = (info or {}).get('title') or (info or {}).get('fulltitle') or ''
        base = sanitize(title) if title else 'download'
        year = None
        if info and info.get('year'):
            year = int(info['year'])
        elif info and info.get('release_date'):
            year = str(info['release_date'])[:4]
        elif info and info.get('upload_date'):
            year = str(info['upload_date'])[:4]
        parts = [base]
        if year:
            parts.append(f'({year})')
        tag = quality_label(video_fmt)
        if tag:
            parts.append(f'[{tag}]')
        a_tag = audio_label(audio_fmt)
        if a_tag:
            parts.append(f'[{a_tag}]')
        platform = platform_label(url)
        if platform:
            parts.append(f'[{platform}]')
        name = ' '.join(parts)
        return f'{sanitize(name)}.{container}'

    @staticmethod
    def unique_path(directory, filename):
        path = os.path.join(directory, filename)
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(filename)
        counter = 1
        while True:
            candidate = os.path.join(directory, f'{base} ({counter}){ext}')
            if not os.path.exists(candidate):
                return candidate
            counter += 1