import os
from PySide6.QtGui import QFontDatabase

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STYLES_DIR = os.path.join(BASE_DIR, 'ui', 'styles')
FONTS_DIR = os.path.join(BASE_DIR, 'assets', 'fonts')

FONT_FILES = (
    'Rosehot.ttf',
    'Inter-Regular.ttf',
    'Inter-Medium.ttf',
    'Inter-SemiBold.ttf',
    'JetBrainsMono-Regular.ttf',
    'JetBrainsMono-Bold.ttf',
)

THEMES = ('dark', 'light')

FALLBACK_STACKS = {
    'heading': '"Rosehot free version", "Rosehot", "Inter", "Segoe UI", sans-serif',
    'body': '"Inter", "Segoe UI", "SF Pro Display", "Roboto", sans-serif',
    'mono': '"JetBrains Mono", "Consolas", "DejaVu Sans Mono", monospace',
}

_fonts_registered = False


def register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    for name in FONT_FILES:
        path = os.path.join(FONTS_DIR, name)
        if os.path.exists(path):
            QFontDatabase.addApplicationFont(path)
    _fonts_registered = True


def _qss_path(name):
    safe = name if name in THEMES else 'dark'
    return os.path.join(STYLES_DIR, f'{safe}.qss')


def apply_theme(app, name='dark'):
    app.setStyle('Fusion')
    register_fonts()
    path = _qss_path(name)
    if os.path.exists(path):
        with open(path, 'r') as f:
            app.setStyleSheet(f.read())


def set_theme(app, name):
    name = (name or 'dark').lower()
    if name not in THEMES:
        name = 'dark'
    path = _qss_path(name)
    if os.path.exists(path):
        with open(path, 'r') as f:
            app.setStyleSheet(f.read())
    return name
