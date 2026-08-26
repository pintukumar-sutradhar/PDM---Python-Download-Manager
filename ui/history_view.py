from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt


class HistoryView(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName('page-view')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 22, 36, 16)
        lay.setSpacing(14)
        header = QLabel('History')
        header.setObjectName('page-header-title')
        sub = QLabel('Every download ever recorded, including trashed items.')
        sub.setObjectName('page-header-subtitle')
        top = QHBoxLayout()
        top.addWidget(header, stretch=1)
        refresh = QPushButton('Refresh')
        refresh.setObjectName('secondary-btn')
        refresh.clicked.connect(self.reload)
        top.addWidget(refresh)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['File', 'Category', 'Status', 'Size', 'Added', 'Last Updated'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(i, 130)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setShowGrid(False)
        lay.addLayout(top)
        lay.addWidget(sub)
        lay.addWidget(self.table, stretch=1)

    def showEvent(self, event):
        super().showEvent(event)
        self.reload()

    def reload(self):
        try:
            from core.database import PDMDatabase
            rows = PDMDatabase().get_all_downloads_including_trash()
        except Exception:
            rows = []
        self.table.setRowCount(len(rows))
        for i, d in enumerate(rows):
            size = int(d.get('total_size') or 0)
            size_s = f'{size / (1024 * 1024):.1f} MB' if size < 1024 ** 3 and size > 0 else (f'{size / (1024 ** 3):.2f} GB' if size >= 1024 ** 3 else ('-' if size == 0 else f'{size} B'))
            values = [d.get('filename', ''), d.get('category') or 'General', d.get('status', ''), size_s, str(d.get('created_at', '')), str(d.get('updated_at', ''))]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col in (2, 3, 4, 5):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, col, item)
