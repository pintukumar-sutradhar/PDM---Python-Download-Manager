import os
from urllib.parse import urlparse, unquote

DEFAULT_CATEGORIES = [
    ('Video', '.mp4 .mkv .avi .mov .webm .flv .wmv .m4v .ts .3gp'),
    ('Audio', '.mp3 .m4a .flac .wav .ogg .opus .aac .wma'),
    ('Documents', '.pdf .doc .docx .xls .xlsx .ppt .pptx .txt .md .epub .csv'),
    ('Archives', '.zip .rar .7z .tar .gz .bz2 .xz .iso'),
    ('Programs', '.exe .msi .deb .rpm .dmg .pkg .appimage .apk .flatpak'),
    ('Images', '.jpg .jpeg .png .gif .webp .bmp .svg .tiff'),
]


def ensure_default_categories():
    from core.database import PDMDatabase
    db = PDMDatabase()
    existing = {c['name'] for c in db.get_categories()}
    for name, exts in DEFAULT_CATEGORIES:
        if name not in existing:
            folder = os.path.join(os.path.expanduser('~/Downloads'), name)
            db.add_category(name, exts, folder)


def _extension_of(filename):
    return os.path.splitext(filename)[1].lower()


def classify(filename, url=''):
    from core.database import PDMDatabase
    if not filename:
        filename = unquote(urlparse(url).path) or ''
    ext = _extension_of(filename)
    try:
        cats = PDMDatabase().get_categories()
    except Exception:
        cats = [(n, e, '') for n, e in DEFAULT_CATEGORIES]
        cats = [{'name': n, 'extensions': e, 'save_folder': ''} for n, e, _ in cats]
    for cat in cats:
        known = [e.strip().lower() for e in (cat.get('extensions') or '').split() if e.strip()]
        if ext and ext in known:
            return cat.get('name'), cat.get('save_folder') or None
    return 'General', None


def category_folder(category):
    from core.database import PDMDatabase
    try:
        for c in PDMDatabase().get_categories():
            if c['name'] == category and (c.get('save_folder') or '').strip():
                return os.path.expanduser(c['save_folder'])
    except Exception:
        pass
    return None
