import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, 
    QPushButton, QLabel, QFileDialog, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QWidget, QRadioButton, QButtonGroup, QGroupBox,
    QPlainTextEdit, QAbstractItemView
)
from PySide6.QtCore import Qt, QThread, Signal

# Standard local imports
from core.scanner import Scanner

class ScanWorker(QThread):
    finished = Signal(list)
    
    def __init__(self, url, auth=None):
        super().__init__()
        self.url = url
        self.auth = auth

    def run(self):
        try:
            files = Scanner.scan_url(self.url, auth=self.auth)
            self.finished.emit(files)
        except Exception:
            self.finished.emit([])

class NewDownloadDialog(QDialog):
    def __init__(self, parent=None, initial_url=""):
        super().__init__(parent)
        self.setWindowTitle("Task Acquisition")
        self.setFixedWidth(1050)
        self.setMinimumHeight(780)
        self.found_files = []
        self.init_ui(initial_url)

    def init_ui(self, initial_url):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)

        header = QLabel("New Download")
        header.setStyleSheet("font-size: 32px; font-weight: 800; color: #ffffff;")
        layout.addWidget(header)

        # URL Section
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit(initial_url)
        self.url_input.setPlaceholderText("Paste URL here")
        self.url_input.setMinimumHeight(55)
        self.scan_btn = QPushButton("Scan Media")
        self.scan_btn.setObjectName("action-btn")
        self.scan_btn.setMinimumHeight(55); self.scan_btn.setFixedWidth(160)
        self.scan_btn.clicked.connect(self._start_scan)
        url_layout.addWidget(self.url_input); url_layout.addWidget(self.scan_btn)
        layout.addLayout(url_layout)

        content_h = QHBoxLayout()
        
        # Left Panel: Results
        list_group = QGroupBox("Media List")
        list_v = QVBoxLayout(list_group)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["", "Title"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50); self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setStyleSheet("background-color: rgba(0,0,0,0.3); border-radius: 8px;")
        list_v.addWidget(self.table)
        
        # Selection Buttons
        sel_layout = QHBoxLayout()
        self.sel_all = QPushButton("Select All"); self.sel_all.setObjectName("action-btn")
        self.sel_all.clicked.connect(lambda: self._toggle_selection(True))
        self.sel_none = QPushButton("Deselect All"); self.sel_none.setObjectName("action-btn")
        self.sel_none.clicked.connect(lambda: self._toggle_selection(False))
        sel_layout.addWidget(self.sel_all); sel_layout.addWidget(self.sel_none); sel_layout.addStretch()
        list_v.addLayout(sel_layout)
        content_h.addWidget(list_group, 2)

        # Right Panel: Configuration
        config_group = QGroupBox("Configuration")
        config_v = QVBoxLayout(config_group)
        
        config_v.addWidget(QLabel("FORMAT"))
        self.v_radio = QRadioButton("Video (.mp4)"); self.a_radio = QRadioButton("Audio (.mp3)")
        self.v_radio.setChecked(True)
        self.mode_grp = QButtonGroup(self); self.mode_grp.addButton(self.v_radio); self.mode_grp.addButton(self.a_radio)
        config_v.addWidget(self.v_radio); config_v.addWidget(self.a_radio)

        config_v.addSpacing(20)
        config_v.addWidget(QLabel("AUTHENTICATION"))
        self.user_in = QLineEdit(); self.user_in.setPlaceholderText("Email / Phone")
        self.pass_in = QLineEdit(); self.pass_in.setPlaceholderText("Password"); self.pass_in.setEchoMode(QLineEdit.EchoMode.Password)
        config_v.addWidget(self.user_in); config_v.addWidget(self.pass_in)
        
        config_v.addSpacing(10)
        config_v.addWidget(QLabel("COOKIES"))
        self.cookie_in = QPlainTextEdit(); self.cookie_in.setPlaceholderText("Paste cookies here..."); self.cookie_in.setMaximumHeight(100)
        config_v.addWidget(self.cookie_in)

        config_v.addStretch()
        content_h.addWidget(config_group, 1)
        layout.addLayout(content_h)

        # Footer
        footer = QHBoxLayout()
        self.close_btn = QPushButton("Cancel"); self.close_btn.setFixedSize(140, 50)
        self.close_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton("Download"); self.ok_btn.setObjectName("primary-btn"); self.ok_btn.setFixedSize(260, 50)
        self.ok_btn.clicked.connect(self.accept)
        footer.addStretch(); footer.addWidget(self.close_btn); footer.addWidget(self.ok_btn)
        layout.addLayout(footer)

    def _start_scan(self):
        url = self.url_input.text().strip()
        if not url: return
        self.scan_btn.setEnabled(False); self.scan_btn.setText("Scanning...")
        auth = {'username': self.user_in.text(), 'password': self.pass_in.text(), 'cookies': self.cookie_in.toPlainText()}
        self.worker = ScanWorker(url, auth=auth)
        self.worker.finished.connect(self._on_scan_finished); self.worker.start()

    def _on_scan_finished(self, items):
        self.scan_btn.setEnabled(True); self.scan_btn.setText("Scan Media")
        self.found_files = items
        self.table.setRowCount(len(items))
        for i, f in enumerate(items):
            item = QTableWidgetItem(); item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled); item.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(i, 0, item); self.table.setItem(i, 1, QTableWidgetItem(f['name']))

    def _toggle_selection(self, state):
        target = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item: item.setCheckState(target)

    def get_selected_files(self):
        selected = []
        is_audio = self.a_radio.isChecked()
        auth = {'username': self.user_in.text(), 'password': self.pass_in.text(), 'cookies': self.cookie_in.toPlainText()}
        for i in range(self.table.rowCount()):
            if self.table.item(i, 0).checkState() == Qt.CheckState.Checked:
                f_info = self.found_files[i].copy(); f_info['is_audio'] = is_audio; f_info['auth'] = auth
                selected.append(f_info)
        return {"files": selected, "path": os.path.expanduser("~/Downloads")}
