import os
import sys
import threading
import time
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QTableView, QProgressBar, QLabel, QFrame,
    QApplication, QStackedWidget, QGraphicsOpacityEffect, QMessageBox,
    QHeaderView, QAbstractItemView, QStyledItemDelegate, QStyle, QStyleOptionProgressBar
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QIcon, QPixmap

# Standard internal imports
from ui.sidebar import PDMSidebar
from ui.toolbar import PDMToolbar
from ui.dialogs import NewDownloadDialog
from ui.tray import PDMTrayIcon
from ui.widgets.settings_view import PDMSettingsView
from ui.widgets.stats_view import PDMStatsView
from ui.models.download_model import DownloadModel
from core.database import PDMDatabase
from core.download_engine import DownloadEngine
from core.logger import logger

class ProgressBarDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if index.column() == 3: # Progress
            progress = index.data(Qt.ItemDataRole.UserRole + 1) or 0
            opts = QStyleOptionProgressBar()
            opts.rect = option.rect.adjusted(10, 8, -10, -8)
            opts.minimum = 0; opts.maximum = 100; opts.progress = progress
            opts.text = f"{progress}%"; opts.textVisible = True
            QApplication.style().drawControl(QStyle.ControlElement.CE_ProgressBar, opts, painter)
        else:
            super().paint(painter, option, index)

class PDMMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("pdm-main")
        self.setWindowTitle("PDM - Python Download Manager v1.0.0")
        
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_path = os.path.dirname(self.base_dir)
        icon_path = os.path.join(self.root_path, "assets", "icons", "app_icon.png")
        self.setWindowIcon(QIcon(icon_path))
        
        # 1. Hardware-Accelerated Static Background (Anti-Flicker)
        self.bg_label = QLabel(self)
        self.bg_label.setScaledContents(True)
        self.bg_label.stackUnder(self)
        self.resize(1300, 850)
        
        self.db = PDMDatabase()
        self.engine = DownloadEngine()
        self.model = DownloadModel()
        
        self.current_filter = "all"
        self._last_ui_sync = 0
        self._sync_pending = False
        
        self.init_ui()
        self._load_styles()
        self.setup_signals()
        self.load_downloads()
        
        theme = self.db.get_setting("theme", "Abyssal Current")
        self._update_background(theme)

    def _load_styles(self):
        # Strictly call once to prevent CSS-reload flicker
        qss_path = os.path.join(self.base_dir, "styles", "modern.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r") as f:
                self.setStyleSheet(f.read())

    def _update_background(self, theme_name):
        theme_files = {
            "Abyssal Current": "abyssal_current.png", "Biolume Depths": "biolume_depths.png", "Celestial Void": "celestial_void.png",
            "Crimson": "crimson.png", "Cyber Blue": "cyber_blue.png", "Deep Forest": "deep_forest.png", "Emerald": "emerald.png",
            "Midnight Glacier": "midnight_glacier.png", "Obsidian": "obsidian.png", "Ocean Depths": "ocean_depths.png",
            "Royal Purple": "royal_purple.png", "Royal Velvet": "royal_velvet.png", "Volcanic Abyss": "volcanic_abyss.png"
        }
        filename = theme_files.get(theme_name, "abyssal_current.png")
        path = os.path.join(self.root_path, "assets", "themes", filename)
        if os.path.exists(path):
            self.bg_label.setPixmap(QPixmap(path))

    def setup_signals(self):
        self.engine.download_progress.connect(self._on_progress)
        self.engine.download_finished.connect(lambda: self.load_downloads_throttled())
        self.engine.status_updated.connect(lambda id, status: self.load_downloads_throttled())
        self.engine.metadata_updated.connect(lambda id, sz: self.load_downloads_throttled())

    def init_ui(self):
        central = QWidget(); central.setObjectName("central-widget")
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)

        self.sidebar = PDMSidebar()
        self.sidebar.nav_changed.connect(self._on_nav_changed)
        layout.addWidget(self.sidebar)

        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background: transparent;")
        
        self.downloads_view = QWidget()
        dl_layout = QVBoxLayout(self.downloads_view)
        dl_layout.setContentsMargins(0, 0, 0, 0); dl_layout.setSpacing(0)
        
        self.toolbar = PDMToolbar()
        self.toolbar.add_clicked.connect(self._add_task)
        self.toolbar.clear_clicked.connect(self._clear_list)
        self.toolbar.pause_clicked.connect(self._pause_selected)
        self.toolbar.resume_clicked.connect(self._resume_selected)
        self.toolbar.delete_clicked.connect(self._delete_selected)
        dl_layout.addWidget(self.toolbar)
        
        container = QWidget()
        c_layout = QVBoxLayout(container); c_layout.setContentsMargins(40, 40, 40, 40)
        self.header_label = QLabel("All Downloads")
        self.header_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #ffffff; margin-bottom: 25px;")
        c_layout.addWidget(self.header_label)
        
        self.table_view = QTableView()
        self.table_view.setModel(self.model)
        self.table_view.setItemDelegate(ProgressBarDelegate())
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_view.setShowGrid(False); self.table_view.setAlternatingRowColors(True)
        self.table_view.verticalHeader().setVisible(False)
        
        h = self.table_view.horizontalHeader(); h.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table_view.setColumnWidth(0, 450); self.table_view.setColumnWidth(1, 100)
        self.table_view.setColumnWidth(2, 120); self.table_view.setColumnWidth(4, 120)
        self.table_view.setColumnWidth(5, 120); self.table_view.setColumnWidth(6, 150)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        c_layout.addWidget(self.table_view); dl_layout.addWidget(container)
        self.content_stack.addWidget(self.downloads_view)
        self.content_stack.addWidget(PDMStatsView())
        self.content_stack.addWidget(PDMSettingsView())
        layout.addWidget(self.content_stack, 1)

    def _on_progress(self, dl_id, percent, speed, eta, total):
        # Strictly throttle UI refreshes to prevent flickering
        now = time.time()
        if now - self._last_ui_sync < 0.15: return 
        self._last_ui_sync = now
        self.model.update_task(dl_id, {'percent': percent, 'speed': speed, 'eta': eta, 'total_size': total})

    def _on_nav_changed(self, key):
        self.current_filter = key
        if key == "settings": self.content_stack.setCurrentIndex(2)
        elif key == "stats": self.content_stack.setCurrentIndex(1)
        else:
            self.content_stack.setCurrentIndex(0)
            titles = {"all": "All Downloads", "downloading": "Downloading", "completed": "Completed", "queued": "Queued", "trash": "Trash"}
            self.header_label.setText(titles.get(key, "Downloads"))
            self.load_downloads(key)

    def _add_task(self):
        dlg = NewDownloadDialog(self)
        if dlg.exec():
            data = dlg.get_selected_files()
            for f in data['files']:
                self.engine.add_download(f['url'], f['name'], data['path'], is_audio=f.get('is_audio'), auth=f.get('auth'))
            self.load_downloads_throttled()

    def _get_selected_ids(self):
        return list(set(idx.data(Qt.ItemDataRole.UserRole) for idx in self.table_view.selectionModel().selectedRows()))

    def _pause_selected(self):
        for i in self._get_selected_ids(): self.engine.stop_download(i)
        self.load_downloads_throttled()

    def _resume_selected(self):
        for i in self._get_selected_ids(): self.engine.start_download(i)
        self.load_downloads_throttled()

    def _delete_selected(self):
        ids = self._get_selected_ids()
        if not ids: return
        is_trash = (self.current_filter != "trash")
        if QMessageBox.question(self, "Delete", "Move to Trash?" if is_trash else "Delete permanently?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            for i in ids: self.engine.cancel_and_delete(i, permanent=not is_trash)
            self.load_downloads_throttled()

    def _clear_list(self):
        if QMessageBox.question(self, "Clear", "Clear history?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.db.clear_all_downloads(); self.load_downloads_throttled()

    def _handle_save_settings(self, data):
        self.db.set_setting("theme", data['theme'])
        self._update_background(data['theme'])

    def load_downloads_throttled(self):
        if self._sync_pending: return
        self._sync_pending = True
        QTimer.singleShot(300, self._perform_load)

    def _perform_load(self):
        self._sync_pending = False
        self.load_downloads(self.current_filter)

    def load_downloads(self, filter="all"):
        # Use updatesEnabled to prevent visual glitches during sync
        self.table_view.setUpdatesEnabled(False)
        all_tasks = self.db.get_all_downloads_including_trash()
        if filter == "downloading": data = [t for t in all_tasks if t['status'] == "Downloading"]
        elif filter == "completed": data = [t for t in all_tasks if t['status'] == "Completed"]
        elif filter == "trash": data = [t for t in all_tasks if t['status'] == "Trash"]
        elif filter == "queued": data = [t for t in all_tasks if t['status'] in ["Pending", "Paused"]]
        else: data = [t for t in all_tasks if t['status'] != "Trash"]
        self.model.refresh_all(data)
        self.table_view.setUpdatesEnabled(True)

    def resizeEvent(self, event):
        self.bg_label.setGeometry(self.rect())
        super().resizeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PDMMainWindow()
    window.show()
    sys.exit(app.exec())
