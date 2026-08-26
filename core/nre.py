import os
import re
import shutil
import subprocess
import time

from core.logger import logger

CANDIDATES = ('N_m3u8DL-RE', 'N_m3u8DL_RE', 'n_m3u8dl-re', 'N_m3u8DL-RE_v3')
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
PCT_RE = re.compile(r'(\d{1,3}(?:\.\d+)?)%')
SPEED_RE = re.compile(r'([0-9.]+)\s*([KMG]?i?B)/s', re.IGNORECASE)


def find_binary():
    for name in CANDIDATES:
        try:
            path = shutil.which(name)
        except Exception:
            path = None
        if path:
            return path
    extras = [
        os.path.expanduser('~/.local/bin/N_m3u8DL-RE'),
        '/usr/local/bin/N_m3u8DL-RE',
        os.path.expanduser('~/Tools/N_m3u8DL-RE'),
    ]
    if os.name == 'nt':
        local = os.environ.get('LOCALAPPDATA', os.path.expanduser('~/AppData/Local'))
        extras += [os.path.join(local, 'PDM', 'bin', 'N_m3u8DL-RE.exe'), os.path.expanduser('~/bin/N_m3u8DL-RE.exe')]
    for extra in extras:
        if os.path.isfile(extra) and os.access(extra, os.X_OK):
            return extra
    return None


def available():
    try:
        return find_binary() is not None
    except Exception:
        return False


def build_cmd(binary, url, output_path, referer=None, num_connections=8, headers=None):
    out_dir = os.path.dirname(output_path) or '.'
    name = os.path.splitext(os.path.basename(output_path))[0]
    cmd = [
        binary, url,
        '--save-dir', out_dir,
        '--save-name', name,
        '--tmp-dir', os.path.join(out_dir, f'.pdm_tmp_{name}'),
        '--thread-count', str(max(1, min(num_connections, 16))),
        '--concurrent-download',
        '--no-log',
        '--auto-select',
        '-M', 'format=mp4',
    ]
    hdrs = {'User-Agent': UA}
    if referer:
        hdrs['Referer'] = referer
    for k, v in (headers or {}).items():
        hdrs[k] = v
    for k, v in hdrs.items():
        cmd.extend(['--header', f'{k}: {v}'])
    return cmd


class NreRun:
    def __init__(self, cmd, cwd=None):
        self.proc = None
        self.cmd = cmd
        self.cwd = cwd

    def start(self):
        self.proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, cwd=self.cwd)
        return self.proc

    def wait_streaming(self, on_progress=None, should_stop=lambda: False, poll=0.5):
        if self.proc is None:
            raise RuntimeError('not started')
        import threading
        buf = {'line': ''}

        def reader(stream):
            for raw in iter(stream.readline, b''):
                try:
                    buf['line'] = raw.decode('utf-8', 'ignore')
                except Exception:
                    pass
        t = threading.Thread(target=reader, args=(self.proc.stdout,), daemon=True)
        self.proc.stdout = None
        t.start()
        while self.proc.poll() is None:
            time.sleep(poll)
            if should_stop():
                try:
                    self.stop()
                except Exception:
                    pass
                return 'stopped'
            if on_progress:
                text = buf.get('line', '')
                m = PCT_RE.search(text)
                pct = float(m.group(1)) if m else None
                sm = SPEED_RE.search(text)
                speed_mb = None
                if sm:
                    val = float(sm.group(1))
                    unit = sm.group(2).upper().replace('I', '')
                    mult = {'B': 1 / 1048576, 'KB': 1 / 1024, 'MB': 1, 'GB': 1024}.get(unit, 1)
                    speed_mb = val * mult
                on_progress(pct, speed_mb)
            buf['line'] = ''
        code = self.proc.returncode
        t.join(timeout=2)
        return 'ok' if code == 0 else f'exit {code}'

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                time.sleep(1.5)
                if self.proc.poll() is None:
                    self.proc.kill()
            except Exception:
                pass


def run_download(url, output_path, referer=None, num_connections=8, headers=None, on_progress=None, should_stop=lambda: False):
    binary = find_binary()
    if not binary:
        return False, 'N_m3u8DL-RE not installed'
    cmd = build_cmd(binary, url, output_path, referer=referer, num_connections=num_connections, headers=headers)
    logger.debug(f"NRE: {' '.join(cmd[:6])}...")
    run = NreRun(cmd)
    proc_err = ''
    try:
        run.start()
    except FileNotFoundError:
        return False, 'N_m3u8DL-RE not executable'
    result = run.wait_streaming(on_progress=on_progress, should_stop=should_stop)
    if result == 'stopped':
        return True, 'stopped'
    if result == 'ok':
        if os.path.exists(output_path) or any(f.startswith(os.path.splitext(output_path)[0]) for f in os.listdir(os.path.dirname(output_path) or '.')):
            return True, 'ok'
        return False, 'output missing'
    return False, result
