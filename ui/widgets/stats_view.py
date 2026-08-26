from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QGridLayout
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QPen, QPainterPath
from core.database import PDMDatabase
from ui.widgets.stat_card import StatCard

class BandwidthGraph(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('card')
        self.setMinimumHeight(220)
        self.points = [0] * 80
        self._max_history = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(500)

    def add_point(self, value):
        self.points.pop(0)
        self.points.append(value)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = (self.width(), self.height())
        pad = 34
        area = QRectF(pad, 14, w - pad * 2, h - 34)
        painter.setPen(QPen(QColor(255, 255, 255, 12), 1))
        for i in range(1, 5):
            y = area.top() + area.height() * i / 5
            painter.drawLine(area.left(), y, area.right(), y)
        max_val = max(self.points)
        if max_val <= 0:
            max_val = 1
        self._max_history = max(self._max_history, max_val)
        path = QPainterPath()
        n = len(self.points)
        for i in range(n):
            x = area.left() + i * (area.width() / (n - 1))
            y = area.bottom() - self.points[i] / self._max_history * area.height()
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        pen = QPen(QColor(14, 165, 233), 2.4)
        painter.setPen(pen)
        painter.drawPath(path)
        fill = QPainterPath(path)
        fill.lineTo(area.right(), area.bottom())
        fill.lineTo(area.left(), area.bottom())
        fill.closeSubpath()
        grad = QLinearGradient(area.left(), area.top(), area.left(), area.bottom())
        grad.setColorAt(0, QColor(99, 102, 241, 110))
        grad.setColorAt(1, QColor(14, 165, 233, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawPath(fill)
        painter.setPen(QColor(91, 98, 117))
        painter.drawText(QRectF(0, area.bottom() + 4, w, 22), Qt.AlignCenter, 'last 80 samples')

    def current(self):
        return self.points[-1] if self.points else 0

class PDMStatsView(QWidget):

    def __init__(self):
        super().__init__()
        self.db = PDMDatabase()
        self.init_ui()
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._refresh_totals)
        self.update_timer.start(3000)

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 30, 36, 22)
        outer.setSpacing(18)
        head = QVBoxLayout()
        head.setSpacing(2)
        title = QLabel('Statistics')
        title.setObjectName('page-header-title')
        sub = QLabel('Live network and library insights.')
        sub.setObjectName('page-header-sub')
        head.addWidget(title)
        head.addWidget(sub)
        outer.addLayout(head)
        grid = QGridLayout()
        grid.setSpacing(14)
        self.cards = {}
        definitions = [('speed', 'Current Speed', '⚡', ''), ('peak', 'Peak Speed', '▲', 'Highest throughput this session'), ('total', 'Total Downloaded', '◈', 'Accumulated size on disk'), ('active', 'Active Sessions', '⬇', 'Downloads currently running')]
        for i, (key, title, icon, sub) in enumerate(definitions):
            card = StatCard(title, icon)
            card.set_sub(sub)
            grid.addWidget(card, i // 4, i % 4)
            self.cards[key] = card
        outer.addLayout(grid)
        graph_head = QVBoxLayout()
        graph_head.setSpacing(2)
        gh = QLabel('Live Bandwidth Throughput')
        gh.setObjectName('section-title')
        gs = QLabel('Real-time network activity across all active downloads')
        gs.setObjectName('section-sub')
        graph_head.addWidget(gh)
        graph_head.addWidget(gs)
        outer.addLayout(graph_head)
        self.graph = BandwidthGraph()
        outer.addWidget(self.graph, stretch=1)
        self._refresh_totals()

    def _refresh_totals(self):
        downloads = self.db.get_all_downloads_including_trash()
        total_bytes = sum((d.get('downloaded_size', 0) for d in downloads))
        active_count = len([d for d in downloads if d['status'] == 'Downloading'])
        self.cards['total'].set_value(self._format_size(total_bytes))
        self.cards['active'].set_value(str(active_count))

    def update_speed(self, speed):
        self.cards['speed'].set_value(f'{speed:.2f} MB/s')
        self.graph.add_point(speed)
        peak = max(self.graph.points)
        self.cards['peak'].set_value(f'{peak:.2f} MB/s')

    @staticmethod
    def _format_size(size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if size_bytes < 1024:
                return f'{size_bytes:.2f} {unit}'
            size_bytes /= 1024
        return f'{size_bytes:.2f} EB'