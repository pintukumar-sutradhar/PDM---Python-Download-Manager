from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QFileDialog, QMessageBox
import os
from PySide6.QtCore import Qt


class TorrentsView(QWidget):
    def __init__(self, torrent_engine):
        super().__init__()
        self.engine = torrent_engine
        self.rows = {}
        self.setObjectName('page-view')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 22, 36, 16)
        lay.setSpacing(14)
        header = QLabel('BitTorrent')
        header.setObjectName('page-header-title')
        sub = QLabel(self._availability())
        sub.setObjectName('page-header-subtitle')
        sub.setWordWrap(True)
        controls = QWidget()
        c_lay = QHBoxLayout(controls)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(8)
        self.input = QLineEdit()
        self.input.setObjectName('mono-field')
        self.input.setPlaceholderText('magnet:?xt=... or /path/to/file.torrent')
        add_btn = QPushButton('Add Magnet / Torrent')
        add_btn.setObjectName('primary-btn')
        browse_btn = QPushButton('Browse .torrent…')
        browse_btn.setObjectName('secondary-btn')
        clear_btn = QPushButton('Clear Finished')
        clear_btn.setObjectName('secondary-btn')
        remove_btn = QPushButton('Remove Selected')
        remove_btn.setObjectName('secondary-btn')
        clear_all_btn = QPushButton('Clear All')
        clear_all_btn.setObjectName('secondary-btn')
        self.seq_check = QCheckBox('Sequential download')
        c_lay.addWidget(self.input, stretch=1)
        c_lay.addWidget(browse_btn)
        c_lay.addWidget(add_btn)
        c_lay.addWidget(remove_btn)
        c_lay.addWidget(clear_btn)
        c_lay.addWidget(clear_all_btn)
        add_btn.clicked.connect(self._add)
        browse_btn.clicked.connect(self._browse)
        clear_btn.clicked.connect(self._clear_finished)
        remove_btn.clicked.connect(self._remove_selected)
        clear_all_btn.clicked.connect(self._clear_all)
        self.input.returnPressed.connect(self._add)
        self.seq_check.toggled.connect(self.engine.set_sequential)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['Torrent', 'Downloaded', 'Total', 'Progress', 'Status'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 5):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(i, 120 if i != 4 else 260)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setShowGrid(False)
        lay.addWidget(header)
        lay.addWidget(sub)
        lay.addWidget(controls)
        lay.addWidget(self.table, stretch=1)

    def _availability(self):
        if self.engine.available:
            return 'Add magnet links or .torrent files. PDM downloads only what you supply - no index, no search, no recommendations.'
        return 'libtorrent is not installed in this environment. Install it with "pip install libtorrent" to enable the BitTorrent engine.'

    def _add(self):
        source = self.input.text().strip()
        if source:
            from core.database import PDMDatabase
            save_dir = os.path.expanduser(PDMDatabase().get_setting('default_download_path', '~/Downloads'))
            self.engine.add(source, save_dir)
            self.input.clear()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Select .torrent file', '', 'Torrent files (*.torrent)')
        if path:
            from core.database import PDMDatabase
            save_dir = os.path.expanduser(PDMDatabase().get_setting('default_download_path', '~/Downloads'))
            self.engine.add(path, save_dir)

    def on_metadata(self, old_label, real_name):
        row = self._find_row(old_label)
        if row is None:
            return
        entry = list(self.rows.values())[row]
        entry['label'] = real_name
        self.table.item(row, 0).setText(real_name)

    def _clear_finished(self):
        clearable = [key for key, r in self.rows.items() if r['done'] or r.get('failed')]
        for key in clearable:
            row = self.rows.pop(key)
            self.table.removeRow(row['index'])
            self.engine.remove(row['label'])
        self._reindex()

    def _remove_selected(self):
        selected = sorted({idx.row() for idx in self.table.selectionModel().selectedRows()}, reverse=True)
        if not selected:
            QMessageBox.information(self, 'No Selection', 'Select a torrent row to remove.')
            return
        for row_index in selected:
            entry = next((r for r in self.rows.values() if r['index'] == row_index), None)
            if entry:
                label = entry['label']
                self.rows.pop(id(label), None)
                self.table.removeRow(row_index)
                self.engine.remove(label)
        self._reindex()

    def _clear_all(self):
        if not self.rows:
            return
        confirm = QMessageBox.question(self, 'Clear All Torrents', 'Remove all torrents from the list? Downloaded files on disk are not deleted.', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        self.table.setRowCount(0)
        self.rows.clear()
        self.engine.clear_all()

    def _reindex(self):
        for i, (_, row) in enumerate(sorted(self.rows.items(), key=lambda kv: kv[1]['index'])):
            row['index'] = i

    def on_added(self, label):
        key = id(label)
        r = self.table.rowCount()
        self.table.insertRow(r)
        cells = [QTableWidgetItem(label), QTableWidgetItem('-'), QTableWidgetItem('-'), QTableWidgetItem('0.0%'), QTableWidgetItem('Queued')]
        for col, cell in enumerate(cells):
            if col > 0:
                cell.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, col, cell)
        self.rows[key] = {'index': r, 'label': label, 'done': False}

    def on_progress(self, label, done_bytes, total_bytes, pct, speed_mb, status_text):
        row = self._find_row(label)
        if row is None:
            self.on_added(label)
            row = len(self.rows) - 1
        entry = list(self.rows.values())[row]
        fmt = lambda b: f'{b / (1024 * 1024):.1f} MB' if b < 1024 ** 3 else f'{b / (1024 ** 3):.2f} GB'
        self.table.item(row, 1).setText(fmt(done_bytes))
        self.table.item(row, 2).setText(fmt(total_bytes))
        self.table.item(row, 3).setText(f'{pct:.1f}%')
        self.table.item(row, 4).setText(status_text)

    def on_finished(self, name, path, size_bytes):
        row = self._find_row(name)
        if row is None:
            return
        entry = list(self.rows.values())[row]
        entry['done'] = True
        fmt = lambda b: f'{b / (1024 ** 3):.2f} GB' if b >= 1024 ** 3 else f'{b / (1024 * 1024):.1f} MB'
        self.table.item(row, 0).setText(name)
        self.table.item(row, 2).setText(fmt(size_bytes))
        self.table.item(row, 3).setText('100.0%')
        self.table.item(row, 4).setText('Complete')

    def on_failed(self, label, error):
        row = self._find_row(label)
        if row is None:
            self.on_added(label)
            row = len(self.rows) - 1
        entry = list(self.rows.values())[row]
        entry['failed'] = True
        self.table.item(row, 4).setText(f'Failed · {error}')

    def _find_row(self, label):
        for row in self.rows.values():
            if row['label'] == label:
                return row['index']
        return None
