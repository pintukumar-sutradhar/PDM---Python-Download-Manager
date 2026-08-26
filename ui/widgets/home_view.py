from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QLineEdit, QSizePolicy
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class StatBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('card')
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(24, 14, 24, 14)
        self._lay.setSpacing(28)
        self._values = {}
        for key, label in (('active', 'active now'), ('completed', 'completed'), ('library', 'library'), ('torrents', 'torrents')):
            box = QHBoxLayout()
            box.setSpacing(7)
            v = QLabel('0')
            f = QFont()
            f.setBold(True)
            f.setPointSize(12)
            v.setFont(f)
            v.setStyleSheet('color: #eef1f9; background: transparent; border: none;')
            c = QLabel(label)
            c.setStyleSheet('color: #7f8aa5; background: transparent; border: none;')
            dot = QLabel()
            dot.setFixedSize(5, 5)
            dot.setStyleSheet('background: #6366f1; border-radius: 2px; border: none;')
            box.addWidget(dot)
            box.addWidget(v)
            box.addWidget(c)
            self._lay.addLayout(box)
            self._values[key] = v
        self._lay.addStretch(1)

    def set_stats(self, active=0, completed=0, library='0 B', torrents=0):
        self._values['active'].setText(str(active))
        self._values['completed'].setText(str(completed))
        self._values['library'].setText(str(library))
        self._values['torrents'].setText(str(torrents))


class UrlCard(QFrame):
    submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('card')
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        lay = QHBoxLayout()
        lay.setContentsMargins(18, 16, 16, 8)
        lay.setSpacing(10)
        self.input = QLineEdit()
        self.input.setPlaceholderText('Paste a video, playlist, torrent or stream link…')
        self.input.setObjectName('home-url-input')
        self.input.returnPressed.connect(self._fire)
        self.btn = QPushButton('Download')
        self.btn.setObjectName('primary-btn')
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(self._fire)
        lay.addWidget(self.input, 1)
        lay.addWidget(self.btn)
        hint = QLabel('Engine auto-selected — yt-dlp · torrent · HLS · direct')
        hint.setStyleSheet('color: #667089; background: transparent; border: none;')
        row2 = QHBoxLayout()
        row2.setContentsMargins(20, 0, 0, 12)
        row2.addWidget(hint)
        row2.addStretch(1)
        outer.addLayout(lay)
        outer.addLayout(row2)

    def _fire(self):
        url = self.input.text().strip()
        if url:
            self.submitted.emit(url)
            self.input.clear()


class AttentionStrip(QFrame):
    resume_all = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('attention-strip')
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.hide()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 12, 12, 12)
        self.text = QLabel()
        self.text.setStyleSheet('color: #fbbf24; background: transparent; border: none; font-weight: bold;')
        btn = QPushButton('Resume all')
        btn.setObjectName('secondary-btn')
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.resume_all)
        lay.addWidget(self.text)
        lay.addStretch(1)
        lay.addWidget(btn)

    def set_counts(self, paused=0, failed=0):
        parts = []
        if paused:
            parts.append(f'{paused} paused')
        if failed:
            parts.append(f'{failed} failed')
        if not parts:
            self.hide()
            return
        self.text.setText(' · '.join(parts) + ' — pick up where you left off')
        self.show()


class RecentRow(QFrame):
    def __init__(self, name, status, size_text, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 9, 14, 9)
        name_l = QLabel(name)
        name_l.setStyleSheet('color: #dfe5f1; background: transparent; border: none;')
        status_colors = {'Completed': '#34d399', 'Downloading': '#60a5fa', 'Failed': '#f87171', 'Paused': '#fbbf24'}
        color = status_colors.get(status, '#8a94ad')
        st = QLabel(status)
        st.setStyleSheet(f'color: {color}; background: transparent; border: none; font-weight: bold;')
        sz = QLabel(size_text)
        sz.setStyleSheet('color: #7f8aa5; background: transparent; border: none;')
        lay.addWidget(name_l, 1)
        lay.addWidget(sz)
        lay.addSpacing(18)
        lay.addWidget(st)


class PDMHomeView(QWidget):
    navigate = Signal(str)
    url_submitted = Signal(str)
    resume_all_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(34, 30, 34, 28)
        outer.setSpacing(16)

        title = QLabel('What are we grabbing today?')
        f = QFont()
        f.setPointSize(22)
        f.setBold(True)
        title.setFont(f)
        title.setStyleSheet('color: #f2f5fc; background: transparent;')
        sub = QLabel('Paste any link below — PDM scans it, picks the right engine and starts pulling.')
        sub.setStyleSheet('color: #8a94ad; background: transparent;')
        outer.addWidget(title)
        outer.addWidget(sub)
        outer.addSpacing(4)

        self.url_card = UrlCard()
        self.url_card.submitted.connect(self.url_submitted)
        outer.addWidget(self.url_card)

        self.attention = AttentionStrip()
        self.attention.resume_all.connect(self.resume_all_requested)
        outer.addWidget(self.attention)

        self.stats = StatBar()
        outer.addWidget(self.stats)

        recent_header = QHBoxLayout()
        rh = QLabel('Recent activity')
        rh.setStyleSheet('color: #b9c2d8; font-weight: bold; background: transparent;')
        see_all = QPushButton('View all downloads')
        see_all.setObjectName('secondary-btn')
        see_all.setCursor(Qt.PointingHandCursor)
        see_all.clicked.connect(lambda: self.navigate.emit('all'))
        recent_header.addWidget(rh)
        recent_header.addStretch(1)
        recent_header.addWidget(see_all)
        outer.addLayout(recent_header)

        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(6)
        holder = QFrame()
        holder.setObjectName('card')
        holder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        holder.setLayout(self.recent_box)
        outer.addWidget(holder)
        outer.addStretch(1)

    def set_stats(self, active=0, completed=0, library='0 B', torrents=0):
        self.stats.set_stats(active=active, completed=completed, library=library, torrents=torrents)

    def set_attention(self, paused=0, failed=0):
        self.attention.set_counts(paused=paused, failed=failed)

    def set_recent(self, rows):
        while self.recent_box.count():
            item = self.recent_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not rows:
            empty = QLabel('Nothing yet — paste a link above and it will show up here.')
            empty.setStyleSheet('color: #667089; background: transparent; padding: 10px 4px;')
            self.recent_box.addWidget(empty)
            return
        for name, status, size_text in rows[:5]:
            self.recent_box.addWidget(RecentRow(name, status, size_text))
