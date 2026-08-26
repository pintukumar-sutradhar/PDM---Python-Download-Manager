import json
import re
import urllib.request
from PySide6.QtCore import QObject, Signal
from core.constants import APP_VERSION

RELEASES_API = 'https://api.github.com/repos/pdm-app/pdm/releases/latest'


def _normalize(v):
    try:
        parts = [int(x) for x in re.findall(r'\d+', str(v))[:3]]
    except Exception:
        parts = []
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


class UpdateChecker(QObject):
    check_finished = Signal(bool, str)

    def run(self):
        try:
            enabled = True
            try:
                from core.database import PDMDatabase
                enabled = PDMDatabase().get_setting('update_checks_enabled', '1') == '1'
            except Exception:
                pass
            if not enabled:
                self.check_finished.emit(False, 'Update checks are disabled in Settings.')
                return
            req = urllib.request.Request(RELEASES_API, headers={'User-Agent': 'PDM-Updater', 'Accept': 'application/vnd.github+json'}, method='GET')
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
            latest = data.get('tag_name') or data.get('name') or ''
            if _normalize(latest) > _normalize(APP_VERSION):
                notes = (data.get('html_url') or '').strip()
                self.check_finished.emit(True, f'New version {latest} available. {notes}'.strip())
            else:
                self.check_finished.emit(False, f'You are up to date (v{APP_VERSION}).')
        except Exception as e:
            self.check_finished.emit(False, f'Could not check for updates: {e}')


def diagnostic_bundle():
    import platform
    import sys
    from core.database import PDMDatabase
    lines = [
        f'PDM version: {APP_VERSION}',
        f'Platform: {platform.platform()}',
        f'Python: {sys.version.split()[0]}',
        f'Session: {platform.node()}',
    ]
    try:
        db = PDMDatabase()
        counts = {}
        for d in db.get_all_downloads_including_trash():
            counts[d.get('status', '?')] = counts.get(d.get('status', '?'), 0) + 1
        lines.append(f'Downloads by status: {counts}')
        lines.append(f'Torrent engine: {"libtorrent" if _lt_available() else "unavailable"}')
    except Exception as e:
        lines.append(f'db error: {e}')
    return '\n'.join(lines)


def _lt_available():
    try:
        import libtorrent
        return True
    except Exception:
        return False
