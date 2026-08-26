import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
                               QPlainTextEdit, QDialogButtonBox, QListWidget, QListWidgetItem, QSplitter)
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

from core.weblogin import save_cookies, _domain_of, _registrable
from core.logger import logger

LOGIN_MARKERS = ('login', 'signin', 'sign-in', 'log-in', 'auth', 'register', 'signup', 'otp', 'password')

CATCH_JS = '''
(function(){
  if (window.__pdmHooked) return; window.__pdmHooked = true;
  var report = function(u){
    try {
      if (!u || typeof u !== 'string') return;
      if (/\\.(m3u8|mpd|mp4)(\\?|#|$)/i.test(u)) { console.log('__PDM__' + u); }
    } catch(e) {}
  };
  if (navigator.requestMediaKeySystemAccess) {
    var ormksa = navigator.requestMediaKeySystemAccess.bind(navigator);
    navigator.requestMediaKeySystemAccess = function(ks, configs){
      try { console.log('__PDM_DRM__' + ks); } catch(e) {}
      return ormksa(ks, configs);
    };
  }
  var of = window.fetch;
  window.fetch = function(){ try { var u = arguments[0]; if (u && u.url) u = u.url; report(u); } catch(e){} return of.apply(this, arguments); };
  var oo = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(m, u){ try { report(u); } catch(e){} return oo.apply(this, arguments); };
  function scanDom(){ try {
    document.querySelectorAll('video[src]').forEach(function(v){ report(v.src); });
    document.querySelectorAll('video source[src]').forEach(function(s){ report(s.src); });
  } catch(e) {} }
  if (document.readyState === 'complete') scanDom(); else window.addEventListener('load', scanDom);
})();
'''


class CatchPage(QWebEnginePage):
    stream_caught = Signal(str)
    drm_detected = Signal(str)

    def javaScriptConsoleMessage(self, level, message, line, source):
        if message.startswith('__PDM_DRM__'):
            self.drm_detected.emit(message[11:])
        elif message.startswith('__PDM__'):
            self.stream_caught.emit(message[7:])


def parse_cookie_text(text, default_domain):
    """Accepts Netscape cookie files, 'k=v; k2=v2' strings or one-per-line pairs."""
    cookies = []
    for raw in (text or '').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '\t' in line:
            parts = line.split('\t')
            if len(parts) == 7:
                cookies.append({'name': parts[5], 'value': parts[6], 'domain': parts[0],
                                'path': parts[2] or '/', 'secure': parts[3] == 'TRUE', 'expiry': None})
                continue
        for pair in line.split(';'):
            if '=' in pair:
                k, _, v = pair.strip().partition('=')
                if k.strip():
                    cookies.append({'name': k.strip(), 'value': v.strip().strip('"'),
                                    'domain': '.' + default_domain, 'path': '/', 'secure': False, 'expiry': None})
    return cookies


class CookiePasteDialog(QDialog):
    def __init__(self, domain, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'Paste cookies · {domain}')
        self.resize(640, 420)
        lay = QVBoxLayout(self)
        tip = QLabel(f'Paste cookies for {domain} — either a cookies.txt export or "name=value; name2=value2" pairs.')
        tip.setWordWrap(True)
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText('name=value; other=value2\n— or —\n# Netscape HTTP Cookie File\n.chorki.com\tTRUE\t/\tTRUE\t0\tsession\tabc123')
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(tip)
        lay.addWidget(self.edit, 1)
        lay.addWidget(buttons)

    def cookies(self):
        return parse_cookie_text(self.edit.toPlainText(), self._domain())

    def _domain(self):
        return self.windowTitle().split('· ')[-1]


class LoginBrowserDialog(QDialog):
    """Opens the site in an embedded browser. Once the user logs in, the
    session cookies for the site are captured and saved for PDM's engines.
    While you browse/play, any plain (non-encrypted) stream the page loads
    is caught and can be sent straight to the downloader."""

    cookies_saved = Signal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Sign in · PDM')
        self.resize(1100, 780)
        self.target_domain = _domain_of(url)
        self.registrable = _registrable(self.target_domain)
        self._collected = {}
        self._saved = False
        self.caught_streams = {}
        self.selected_url = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        bar = QWidget()
        bar.setObjectName('login-bar')
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 10, 12, 10)
        self.status = QLabel(f'Log in to {self.target_domain} — PDM will remember this session.')
        self.status.setStyleSheet('color: #c9d3ea; background: transparent;')
        self.done_btn = QPushButton('Save session & continue')
        self.done_btn.setObjectName('primary-btn')
        self.done_btn.setCursor(Qt.PointingHandCursor)
        self.done_btn.setEnabled(False)
        self.done_btn.clicked.connect(self._save_and_close)
        cancel = QPushButton('Cancel')
        cancel.setObjectName('secondary-btn')
        cancel.clicked.connect(self.reject)
        bl.addWidget(self.status, 1)
        bl.addWidget(self.done_btn)
        bl.addWidget(cancel)
        lay.addWidget(bar)

        self.profile = QWebEngineProfile('pdm-login', self)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.page = CatchPage(self.profile, self)
        self.page.stream_caught.connect(self._on_stream_caught)
        self.page.drm_detected.connect(self._on_drm_detected)
        self.view = QWebEngineView(self)
        self.view.setPage(self.page)
        self.view.loadFinished.connect(self._inject_hook)
        self.view.urlChanged.connect(self._on_url)

        split = QSplitter(Qt.Vertical)
        split.addWidget(self.view)
        catch_box = QWidget()
        cb = QVBoxLayout(catch_box)
        cb.setContentsMargins(12, 6, 12, 8)
        cb.setSpacing(4)
        self.catch_label = QLabel('Streams caught while playing (0)')
        self.catch_label.setStyleSheet('color: #8a94ad; background: transparent;')
        self.catch_list = QListWidget()
        self.catch_list.setMaximumHeight(140)
        self.catch_list.itemDoubleClicked.connect(self._use_caught)
        use_btn = QPushButton('Download selected stream')
        use_btn.setObjectName('secondary-btn')
        use_btn.setCursor(Qt.PointingHandCursor)
        use_btn.clicked.connect(self._use_caught)
        cb.addWidget(self.catch_label)
        cb.addWidget(self.catch_list)
        cb.addWidget(use_btn, 0, Qt.AlignRight)
        catch_box.setLayout(cb)
        split.addWidget(catch_box)
        split.setSizes([560, 190])
        lay.addWidget(split, 1)

        store = self.profile.cookieStore()
        store.cookieAdded.connect(self._on_cookie)
        self.view.load(QUrl(url))

    def done(self, result):
        try:
            self.view.stop()
            self.view.setPage(None)
            self.page.deleteLater()
            self.profile.deleteLater()
        except Exception:
            pass
        super().done(result)

    def _inject_hook(self, ok):
        if ok:
            self.page.runJavaScript(CATCH_JS)

    def _on_drm_detected(self, keysystem):
        self.status.setText(f'🔒 {keysystem} DRM playback detected — this content cannot play or download in any tool without the site\'s license. Non-encrypted streams will still appear below.')
        self.status.setStyleSheet('color: #fbbf24; background: transparent;')
        logger.info(f'DRM playback attempted ({keysystem}) in login browser')

    def _on_stream_caught(self, url):
        if url in self.caught_streams:
            return
        kind = 'DASH' if '.mpd' in url.lower() else ('HLS' if '.m3u8' in url.lower() else 'MP4')
        self.caught_streams[url] = kind
        self.catch_list.addItem(QListWidgetItem(f'[{kind}]  {url[:120]}'))
        self.catch_label.setText(f'Streams caught while playing ({len(self.caught_streams)}) — double-click to use')
        logger.info(f'Caught {kind} stream in login browser: {url[:100]}')

    def _use_caught(self, *args):
        item = self.catch_list.currentItem()
        if not item:
            return
        for u, kind in self.caught_streams.items():
            if item.text().startswith(f'[{kind}]') and u[:120] in item.text():
                self.selected_url = u
                break
        if self._collected:
            self._save_and_close()
        else:
            self.accept()

    def _on_cookie(self, cookie):
        try:
            name = bytes(cookie.name()).decode('utf-8', 'ignore')
            value = bytes(cookie.value()).decode('utf-8', 'ignore')
            domain = (cookie.domain() or '').lower()
            if self.registrable and not (domain == self.registrable or domain.endswith('.' + self.registrable)):
                return
            self._collected[(domain, name, cookie.path() or '/')] = {
                'name': name, 'value': value, 'domain': domain,
                'path': cookie.path() or '/', 'secure': cookie.isSecure(),
                'http_only': cookie.isHttpOnly(), 'expiry': cookie.expirationDate().toSecsSinceEpoch() if cookie.expirationDate().isValid() else None,
            }
        except Exception as e:
            logger.debug(f'cookie capture failed: {e}')

    def _on_url(self, url):
        host = (url.host() or '').lower()
        path = (url.path() or '').lower()
        looks_like_login = any(m in path for m in LOGIN_MARKERS)
        if host.endswith(self.registrable) and self._collected and not looks_like_login:
            self.status.setText('Looks signed in — press “Save session & continue”.')
            self.done_btn.setEnabled(True)
        elif self._collected:
            self.done_btn.setEnabled(True)

    def _save_and_close(self):
        if not self._collected:
            self.reject()
            return
        path = save_cookies(self.registrable, list(self._collected.values()))
        self._saved = bool(path)
        logger.info(f'Login session saved for {self.registrable} ({len(self._collected)} cookies)')
        self.cookies_saved.emit(self.registrable)
        self.accept()

    def reject(self):
        super().reject()
