import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QButtonGroup, QLabel, QFrame
from PySide6.QtCore import Signal, Qt
from core.constants import APP_VERSION

class PDMSidebar(QWidget):
    nav_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName('sidebar')
        self._buttons = {}
        self._counts = {}
        self.init_ui()

    def _brand_block(self):
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 20, 12, 14)
        layout.setSpacing(10)
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'icons', 'app_icon_64.png')
        if os.path.exists(icon_path):
            from PySide6.QtGui import QPixmap
            mark = QLabel()
            mark.setPixmap(QPixmap(icon_path).scaled(38, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            mark.setFixedSize(38, 38)
        else:
            mark = QLabel('PDM')
            mark.setObjectName('brand-logo')
            mark.setAlignment(Qt.AlignCenter)
        layout.addWidget(mark)
        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        title = QLabel('Python Download')
        title.setObjectName('brand-title')
        sub = QLabel('Manager')
        sub.setObjectName('brand-subtitle')
        text_col.addWidget(title)
        text_col.addWidget(sub)
        layout.addLayout(text_col)
        layout.addStretch()
        return frame

    def _section_label(self, text):
        lbl = QLabel(text.upper())
        lbl.setObjectName('sidebar-section')
        return lbl

    def _nav_row(self, text, key):
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 1, 12, 1)
        lay.setSpacing(4)
        btn = QPushButton(text)
        btn.setObjectName('nav-btn')
        btn.setCheckable(True)
        lay.addWidget(btn)
        badge = QLabel('0')
        badge.setObjectName('nav-count')
        badge.setAlignment(Qt.AlignCenter)
        badge.hide()
        lay.addWidget(badge)
        self._counts[key] = badge
        self.btn_group.addButton(btn)
        btn.clicked.connect(lambda chk, k=key: self.nav_changed.emit(k))
        self._buttons[key] = btn
        return row

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._brand_block())
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        nav = QVBoxLayout()
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(2)
        nav.addWidget(self._section_label('Library'))
        for text, key in [('Home', 'home'), ('All Downloads', 'all'), ('Torrents', 'torrents'), ('Trash', 'trash')]:
            nav.addWidget(self._nav_row(text, key))
        self._buttons['home'].setChecked(True)
        nav.addSpacing(10)
        nav.addWidget(self._section_label('General'))
        for text, key in [('Statistics', 'stats'), ('History', 'history'), ('Settings', 'settings'), ('About', 'about')]:
            nav.addWidget(self._nav_row(text, key))
        nav.addStretch(1)
        outer.addLayout(nav, stretch=1)
        ver = QLabel(f'v{APP_VERSION}')
        ver.setAlignment(Qt.AlignCenter)
        ver.setObjectName('sidebar-version')
        outer.addWidget(ver)

    def update_counts(self, counts):
        for key, badge in self._counts.items():
            value = counts.get(key, 0)
            badge.setText(str(value))
            badge.setVisible(value > 0)

    def select_view(self, key):
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)