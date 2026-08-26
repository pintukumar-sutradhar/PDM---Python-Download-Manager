#!/usr/bin/env python3
"""PDM self-test: verifies every module of this install.

Usage:
    python scripts/selftest.py          # offline checks (fast)
    python scripts/selftest.py --live   # also runs network tests (YouTube scan+download probe, HLS fetch, magnet DHT)

Exit code 0 = all passed.
"""
import os
import sys
import tempfile
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('PDM_VERBOSE', '1')

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def run(only_live=False):
    failed = []
    for name, fn in RESULTS:
        live = getattr(fn, 'live', False)
        if only_live and not live:
            continue
        if not only_live and live and '--live' not in sys.argv:
            print(f'[SKIP] {name} (needs --live)')
            continue
        try:
            fn()
            print(f'[PASS] {name}')
        except Exception as e:
            print(f'[FAIL] {name}: {type(e).__name__}: {e}')
            failed.append(name)
    return failed


def live(fn):
    fn.live = True
    return fn


@check('imports: core modules')
def _():
    import core.database, core.scanner, core.ott_superscan, core.nre, core.jsruntime, core.categories  # noqa
    import core.ott_handlers, core.generic_extractor, core.namer, core.format_probe  # noqa


@check('imports: download modules')
def _():
    import download.worker, download.torrent_engine, download.segment  # noqa


@check('imports: ui modules')
def _():
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtWidgets import QApplication
    global _qapp
    _qapp = QApplication([])
    import ui.main_window, ui.dialogs, ui.about_view, ui.history_view  # noqa
    from ui.widgets.settings_view import PDMSettingsView  # noqa


@check('database: crud + categories + wal')
def _():
    from core.database import PDMDatabase
    db = PDMDatabase()
    conn = db._get_connection()
    assert conn.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
    conn.close()
    i = db.add_download('t.mp4', 'https://x/t.mp4', '/tmp/t.mp4')
    row = next(r for r in db.get_all_downloads_including_trash() if r['id'] == i)
    assert row['filename'] == 't.mp4'
    db.update_download_status(i, 'Finished', 5, 10)
    cats = db.get_categories()
    assert any(c['name'] == 'Video' for c in cats), 'categories not seeded'
    db.delete_download_permanently(i)


@check('database: torrent record lifecycle')
def _():
    from core.database import PDMDatabase
    db = PDMDatabase()
    tid = db.add_torrent_record('magnet:?xt=urn:btih:AB', 'Selftest Torrent', '/tmp/st')
    assert tid
    db.rename_torrent_record('Selftest Torrent', 'Selftest2.mkv')
    db.update_torrent_progress('Selftest2.mkv', 500, 1000)
    row = next(r for r in db.get_all_downloads_including_trash() if r['id'] == tid)
    assert row['status'] == 'Downloading' and row['total_size'] == 1000
    db.complete_torrent_record('Selftest2.mkv', 1000)
    row = next(r for r in db.get_all_downloads_including_trash() if r['id'] == tid)
    assert row['status'] == 'Finished' and row['category'] == 'Torrents'
    db.delete_torrent_record('Selftest2.mkv')
    assert not any(r['id'] == tid for r in db.get_all_downloads_including_trash())


@check('scanner: direct media URL passthrough')
def _():
    from core.scanner import Scanner
    items = Scanner.scan_url('https://cdn.example.com/video/clip.mp4?tok=1')
    assert items and items[0]['name'].startswith('clip'), items


@check('superscan: hls harvest + login wall + drm (mocked http)')
def _():
    import requests
    from core.ott_superscan import SuperScan
    html = '<html><script>var c={"file":"https:\\/\\/cdn.t.com\\/ep\\/index.m3u8?t=1"};</script></html>'

    class FR:
        status_code = 200
        text = html
        url = ''

    requests.Session.get = lambda self, url, **kw: FR()
    res = SuperScan.harvest('https://ott.example/watch')
    assert len(res['streams']) == 1 and res['streams'][0]['kind'] == 'hls', res

    FR.text = '<form action="/account/login"><input type="password"></form>'
    res2 = SuperScan.harvest('https://ott.example/login')
    assert res2['login_required']

    FR.text = '<script>var u="https://c.x.com/v/s.mpd";var l="widevine";</script>'
    res3 = SuperScan.harvest('https://ott.example/drm')
    assert res3['drm']


@check('scanner order: yt-dlp first, superscan only on failure')
def _():
    import yt_dlp
    import core.ott_superscan as oss

    class FakeYdl:
        def __init__(self, o):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return {'title': 'OK Video', 'formats': []}

    real_ydl = yt_dlp.YoutubeDL
    real_harvest = oss.SuperScan.__dict__['harvest']
    calls = {'n': 0}

    def spy(url, cb=None):
        calls['n'] += 1
        return {'streams': [], 'login_required': False, 'drm': False, 'error': ''}

    try:
        yt_dlp.YoutubeDL = FakeYdl
        oss.SuperScan.harvest = staticmethod(spy)
        from core.scanner import Scanner
        items = Scanner.scan_url('https://youtu.be/xyz123')
        assert items and items[0]['name'] == 'OK Video.mp4', items
        assert calls['n'] == 0, 'superscan ran despite ytdlp success'
    finally:
        yt_dlp.YoutubeDL = real_ydl
        oss.SuperScan.harvest = staticmethod(real_harvest)


@check('nre: binary detect + cmd build + progress parse')
def _():
    from core import nre
    cmd = nre.build_cmd('/usr/bin/N_m3u8DL-RE', 'https://c.x/a.m3u8?t=1', '/d/show.mp4', referer='https://p.example/w')
    joined = ' '.join(cmd)
    assert '--save-name show' in joined and 'Referer: https://p.example/w' in joined
    assert nre.PCT_RE.search('(HLS) 42.7% 3.1MB/s').group(1) == '42.7'


@check('worker routing table compiles (hls/dash/media/engine)')
def _():
    import inspect
    from download.worker import DownloadWorker
    src = inspect.getsource(DownloadWorker._run)
    for token in ('is_ott_stream', '_download_via_nre', '_download_native_hls', '_download_direct', '_download_via_engine'):
        assert token in src, f'missing {token}'
    sig = inspect.signature(DownloadWorker.__init__)
    assert 'referer' in sig.parameters and 'stream_kind' in sig.parameters


@check('engine: add_download category + stream meta plumbing')
def _():
    from core.download_engine import DownloadEngine
    eng = DownloadEngine()
    eng.start_download = lambda *a, **k: None
    r = eng.add_download('https://x.com/song.mp3', 'a.mp3', tempfile.mkdtemp(), auto_name=False)
    row = next(x for x in eng.db.get_all_downloads_including_trash() if x['id'] == r[0])
    assert row['category'] == 'Audio', row['category']
    eng.db.delete_download_permanently(r[0])


@check('jsruntime: detection + opts merge')
def _():
    from core.jsruntime import js_runtime_opts, cookie_browser_opts, apply_ydl_env_opts
    opts = apply_ydl_env_opts({'quiet': True})
    assert 'logger' in opts
    js_runtime_opts()
    cookie_browser_opts()


@check('ui: main window boots, nav, bulk buttons')
def _():
    from PySide6.QtWidgets import QApplication
    from ui.main_window import PDMMainWindow
    w = PDMMainWindow()
    for key in ('all', 'trash', 'torrents', 'history', 'about', 'stats', 'settings'):
        w._on_nav_changed(key)
    assert hasattr(w, 'clear_all_btn') and hasattr(w, 'empty_trash_btn')


@check('ui: settings roundtrip incl browse btn')
def _():
    from PySide6.QtWidgets import QApplication, QPushButton
    from ui.widgets.settings_view import PDMSettingsView
    sv = PDMSettingsView()
    assert any('Browse' in b.text() for b in sv.findChildren(QPushButton))
    assert not hasattr(sv, 'cookie_combo'), 'external-browser cookie dropdown should be gone (embedded login is the path)'
    data_probe = sv.download_path.text()
    assert data_probe and not data_probe.startswith('~')


@check('ui: dialog magnet routing + embedded sign-in hint')
def _():
    from PySide6.QtWidgets import QApplication
    from ui.dialogs import NewDownloadDialog
    d = NewDownloadDialog()
    d.url_input.setText('magnet:?xt=urn:btih:94E41EA241F81152982422B24E5C25A097424331&dn=Mutiny+2026')
    d._start_scan()
    sel = d.get_selected_files()['files'][0]
    assert sel.get('is_torrent') and 'Mutiny' in sel['name']
    assert not hasattr(d, 'cookie_combo'), 'external-browser cookie dropdown should be gone'


@check('themes: dark + light apply cleanly')
def _():
    from PySide6.QtWidgets import QApplication
    from ui.theme import set_theme
    app = QApplication.instance()
    for theme in ('dark', 'light'):
        applied = set_theme(app, theme)
        assert applied in ('dark', 'light')


@check('torrents view: buttons + failed-clear logic')
def _():
    from PySide6.QtWidgets import QPushButton
    from download.torrent_engine import TorrentEngine
    te = TorrentEngine()
    from ui.torrents_view import TorrentsView
    v = TorrentsView(te)
    texts = [b.text() for b in v.findChildren(QPushButton)]
    for want in ('Remove Selected', 'Clear Finished', 'Clear All'):
        assert want in texts, texts
    te.shutdown()


@live
@check('LIVE: youtube scan via yt-dlp')
def _():
    from core.scanner import Scanner
    items = Scanner.scan_url('https://youtu.be/i-FzRpKd7UE')
    assert items, f"scan failed: {Scanner.last_error}"
    assert 'No media' not in str(items[0].get('name'))


@live
@check('LIVE: public HLS stream via native engine')
def _():
    import time
    import threading
    import download.native_engine as ne
    out_dir = tempfile.mkdtemp()
    target = os.path.join(out_dir, 'test.ts')
    inst = None
    for name in ('NativeHlsDownloader',):
        if hasattr(ne, name):
            inst = getattr(ne, name)('https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8', target, num_connections=4)
            break
    assert inst is not None, f'no downloader class in native_engine: {[n for n in dir(ne) if not n.startswith("_")]}'
    runner = getattr(inst, 'start', None) or getattr(inst, 'run')
    threading.Thread(target=runner, daemon=True).start()
    end = time.time() + 60
    while time.time() < end and not os.path.exists(target):
        time.sleep(0.5)
    time.sleep(2)
    assert os.path.exists(target), 'hls produced no file'
    assert os.path.getsize(target) > 100000, f'hls output too small: {os.path.getsize(target)}'


def threading_start(inst):
    import threading
    threading.Thread(target=inst.start if callable(getattr(inst, 'start', None)) else inst.run, daemon=True).start()


def wait_for(cond_fn, timeout):
    import time
    end = time.time() + timeout
    while time.time() < end:
        if cond_fn():
            return True
        time.sleep(0.5)
    return cond_fn()


@live
@check('LIVE: full youtube download through worker')
def _():
    from PySide6.QtCore import QCoreApplication
    app = QCoreApplication.instance() or QCoreApplication([])
    from core.download_engine import DownloadEngine
    eng = DownloadEngine()
    out_dir = tempfile.mkdtemp()
    res = eng.add_download('https://youtu.be/i-FzRpKd7UE', None, out_dir)
    dl_id = res[0]
    end = __import__('time').time() + 120
    while __import__('time').time() < end:
        app.processEvents()
        __import__('time').sleep(0.4)
        row = next((r for r in eng.db.get_all_downloads_including_trash() if r['id'] == dl_id), None)
        if row and row['status'] in ('Completed', 'Failed'):
            break
    row = next((r for r in eng.db.get_all_downloads_including_trash() if r['id'] == dl_id), None)
    eng.stop_download(dl_id)
    assert row and row['status'] == 'Completed', f"status={row['status'] if row else None}"
    assert row['downloaded_size'] > 1000000


if __name__ == '__main__':
    print('PDM Self-Test')
    print('=' * 50)
    offline_fail = run(only_live='--live-only' in sys.argv)
    print('=' * 50)
    if offline_fail:
        print(f'FAILED ({len(offline_fail)}): {", ".join(offline_fail)}')
        sys.exit(1)
    print('ALL PASSED')
