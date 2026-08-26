import shutil

_RUNTIME = None
_CHECKED = False


def detect_js_runtime():
    global _RUNTIME, _CHECKED
    if not _CHECKED:
        _CHECKED = True
        for name in ('deno', 'node', 'quickjs'):
            if shutil.which(name):
                _RUNTIME = name
                break
    return _RUNTIME


def js_runtime_opts():
    runtime = detect_js_runtime()
    if runtime:
        return {'js_runtimes': {runtime: {}}}
    return {}


def cookie_browser_opts():
    try:
        from core.database import PDMDatabase
        browser = (PDMDatabase().get_setting('cookie_browser', '') or '').strip().lower()
    except Exception:
        return {}
    if not browser:
        return {}
    return {'cookiesfrombrowser': (browser,)}


def apply_ydl_env_opts(ydl_opts):
    ydl_opts.update(js_runtime_opts())
    ydl_opts.update(cookie_browser_opts())
    ydl_opts.setdefault('logger', _YdlQuietLogger())
    return ydl_opts


class _YdlQuietLogger:
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def runtime_status_text():
    runtime = detect_js_runtime()
    if runtime:
        return f'JavaScript runtime: {runtime} (full YouTube support)'
    return 'No JavaScript runtime found (deno/node). YouTube may fail to extract or download - install Node.js or Deno.'
