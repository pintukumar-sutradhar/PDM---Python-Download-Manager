import os
import sys
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PY = os.path.join(BASE_DIR, '.venv', 'bin', 'python')
VENV_PY_WIN = os.path.join(BASE_DIR, '.venv', 'Scripts', 'python.exe')


def _ensure_project_runtime():
    expected = os.path.realpath(os.path.join(BASE_DIR, '.venv'))
    if os.path.realpath(sys.prefix) == expected:
        return
    venv_py = VENV_PY if os.path.exists(VENV_PY) else (VENV_PY_WIN if os.path.exists(VENV_PY_WIN) else None)
    if not venv_py:
        return
    if os.environ.get('PDM_REEXEC') == '1':
        return
    env = dict(os.environ)
    env['PDM_REEXEC'] = '1'
    os.execve(venv_py, [venv_py] + sys.argv, env)


_ensure_project_runtime()

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)


def _install_missing_dependencies():
    try:
        import PySide6, yt_dlp, requests, m3u8, urllib3  # noqa
        return
    except Exception:
        pass
    req = os.path.join(BASE_DIR, 'requirements.txt')
    if not os.path.exists(req):
        return
    import subprocess
    print('First run: installing dependencies (one time, a few minutes)...')
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', req])
    except Exception:
        print('System Python is externally managed - creating a local .venv instead...')
        try:
            subprocess.check_call([sys.executable, '-m', 'venv', os.path.join(BASE_DIR, '.venv')])
        except Exception as e:
            print(f'Could not create a virtual environment ({e}).')
            print('Install manually:  python3 -m pip install -r requirements.txt')
            sys.exit(1)
        venv_py = VENV_PY if os.path.exists(VENV_PY) else VENV_PY_WIN
        env = dict(os.environ)
        env['PDM_REEXEC'] = '1'
        os.execve(venv_py, [venv_py] + sys.argv, env)
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'libtorrent>=2.0'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        print('Note: torrent support unavailable for this Python (no libtorrent wheel) - all other features work.')
    print('Dependencies installed. Starting PDM...')


_install_missing_dependencies()

VERBOSE = os.environ.get('PDM_VERBOSE', '') == '1'

NOISE_PATTERNS = (
    'Release of profile requested',
    'CreateCommandBuffer',
    'GpuControl',
    'DawnWebGPU',
    'VulkanInstance',
    'propagateSizeHints',
    'disk_cache',
    'ContextResult',
    'Failed to send GpuControl',
)


def _install_stderr_noise_filter():
    """C++/Qt writes warnings straight to fd 2; filter at the descriptor level."""
    import threading
    try:
        saved_fd = os.dup(2)
        r, w = os.pipe()
        os.dup2(w, 2)
        os.close(w)

        def drain():
            buf = b''
            while True:
                try:
                    chunk = os.read(r, 8192)
                    if not chunk:
                        break
                    buf += chunk
                    while b'\n' in buf:
                        line, buf = buf.split(b'\n', 1)
                        text = line.decode('utf-8', 'ignore')
                        if any(n in text for n in NOISE_PATTERNS):
                            continue
                        os.write(saved_fd, (text + '\n').encode('utf-8', 'ignore'))
                except Exception:
                    continue

        threading.Thread(target=drain, daemon=True).start()
    except Exception:
        pass


if not VERBOSE:
    _install_stderr_noise_filter()

os.environ.setdefault('QT_LOGGING_RULES', 'qt.text.font.db=false;qt.accessibility.*=false;qt.qpa.*=false')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu --disable-software-rasterizer-vsync')
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen
from core.constants import APP_NAME, APP_SHORT_NAME, APP_VERSION, ORG_NAME
from core.logger import logger
from ui.main_window import PDMMainWindow
from ui.theme import apply_theme

class PDMApplication:

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName(APP_SHORT_NAME)
        self.app.setApplicationDisplayName(APP_NAME)
        self.app.setOrganizationName(ORG_NAME)
        self.app.setApplicationVersion(APP_VERSION)
        apply_theme(self.app, self._startup_theme())
        self.window = None
        splash_path = os.path.join(BASE_DIR, 'assets', 'icons', 'splash.png')
        if os.path.exists(splash_path):
            self.splash = QSplashScreen(QPixmap(splash_path), Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.splash = QSplashScreen(QPixmap(), Qt.WindowType.WindowStaysOnTopHint)

    def _startup_theme(self):
        from core.database import PDMDatabase
        try:
            return (PDMDatabase().get_setting('ui_theme', 'dark') or 'dark').lower()
        except Exception:
            return 'dark'

    def run(self):
        self.splash.show()
        logger.info('Initializing system components...')
        QTimer.singleShot(600, self.show_main_window)
        return self.app.exec()

    def show_main_window(self):
        try:
            self.window = PDMMainWindow()
            self.window.show()
            self.splash.finish(self.window)
            logger.info('Application ready.')
        except Exception as e:
            logger.error(f'Startup error: {str(e)}')
            import traceback
            traceback.print_exc()
            sys.exit(1)

def main():
    pdm_app = PDMApplication()
    try:
        sys.exit(pdm_app.run())
    except KeyboardInterrupt:
        print('PDM closed.')
        sys.exit(0)
if __name__ == '__main__':
    main()
