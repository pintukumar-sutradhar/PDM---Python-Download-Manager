import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPen
from core.database import PDMDatabase

class BandwidthGraph(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.points = [0] * 60
        # Use a lower frequency for timer to prevent flickering
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(500)

    def add_point(self, value):
        self.points.pop(0)
        self.points.append(value)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # Grid
        painter.setPen(QPen(QColor(255, 255, 255, 10), 1))
        for i in range(1, 5):
            y = int(h * i / 5)
            painter.drawLine(0, y, w, y)

        # Line
        painter.setPen(QPen(QColor(0, 163, 255), 2))
        max_val = max(self.points) or 1
        
        for i in range(len(self.points) - 1):
            x1 = int(i * (w / (len(self.points)-1)))
            y1 = int(h - (self.points[i] / max_val * h * 0.7))
            x2 = int((i + 1) * (w / (len(self.points)-1)))
            y2 = int(h - (self.points[i+1] / max_val * h * 0.7))
            painter.drawLine(x1, y1, x2, y2)

class PDMStatsView(QWidget):
    def __init__(self):
        super().__init__()
        self.db = PDMDatabase()
        self.init_ui()
        
        # Real-time update for totals
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._refresh_totals)
        self.update_timer.start(5000)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(40)

        header = QLabel("Network Insights")
        header.setStyleSheet("font-size: 36px; font-weight: 800; color: #ffffff;")
        layout.addWidget(header)

        # Dynamic Stats Cards
        self.cards_layout = QHBoxLayout()
        self.speed_card = self._create_stat_card("Current Speed", "0.00 MB/s", "#00a3ff")
        self.total_card = self._create_stat_card("Total Downloaded", "Calculating...", "#00ffa3")
        self.active_card = self._create_stat_card("Active Sessions", "0", "#ffaa00")
        
        self.cards_layout.addWidget(self.speed_card)
        self.cards_layout.addWidget(self.total_card)
        self.cards_layout.addWidget(self.active_card)
        layout.addLayout(self.cards_layout)

        layout.addWidget(QLabel("Live Bandwidth Throughput"))
        self.graph = BandwidthGraph()
        layout.addWidget(self.graph)

        layout.addStretch()
        self._refresh_totals()

    def _create_stat_card(self, title, value, color):
        card = QFrame()
        card.setStyleSheet(f"background-color: rgba(25, 26, 30, 0.8); border-radius: 12px; border-left: 4px solid {color};")
        l = QVBoxLayout(card)
        t = QLabel(title); t.setStyleSheet("color: #888888; font-size: 11px; font-weight: 800; text-transform: uppercase;")
        v = QLabel(value); v.setStyleSheet("color: #ffffff; font-size: 28px; font-weight: 800;")
        v.setObjectName("value-label")
        l.addWidget(t); l.addWidget(v)
        return card

    def _refresh_totals(self):
        downloads = self.db.get_all_downloads_including_trash()
        total_bytes = sum(d.get('downloaded_size', 0) for d in downloads)
        active_count = len([d for d in downloads if d['status'] == "Downloading"])
        
        # Update labels
        self.total_card.findChild(QLabel, "value-label").setText(self._format_size(total_bytes))
        self.active_card.findChild(QLabel, "value-label").setText(str(active_count))

    def update_speed(self, speed):
        self.speed_card.findChild(QLabel, "value-label").setText(f"{speed:.2f} MB/s")
        self.graph.add_point(speed)

    def _format_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if size_bytes < 1024: return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} EB"
