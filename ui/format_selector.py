from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, QGroupBox, QFrame, QMessageBox, QProgressBar, QCheckBox
from PySide6.QtCore import QThread, Signal, Qt
from core.format_probe import FormatProbe
from core.namer import MediaNamer, sanitize, quality_label, audio_label, video_codec_name

class ProbeWorker(QThread):
    finished = Signal(object)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            result = FormatProbe.probe(self.url)
        except Exception:
            result = None
        self.finished.emit(result)

class FormatSelectorDialog(QDialog):

    def __init__(self, parent=None, url='', title='', prefill_container='mp4', is_audio_only=False):
        super().__init__(parent)
        self.url = url
        self.is_audio_only = is_audio_only
        self.prefill_container = prefill_container
        self.probe_result = None
        self.video_formats = []
        self.audio_formats = []
        self.setWindowTitle('Media Options')
        self.setFixedWidth(720)
        self.setMinimumHeight(560)
        self.init_ui(title)
        self._start_probe()

    def init_ui(self, title):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)
        header = QLabel('Media Options')
        header.setObjectName('dialog-title')
        layout.addWidget(header)
        self.status_box = QFrame()
        self.status_box.setObjectName('settings-card')
        status_l = QVBoxLayout(self.status_box)
        status_l.setContentsMargins(16, 14, 16, 14)
        status_l.setSpacing(10)
        self.status_label = QLabel('Probing available formats...')
        self.status_label.setObjectName('muted-text')
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        status_l.addWidget(self.status_label)
        status_l.addWidget(self.progress_bar)
        layout.addWidget(self.status_box)
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setObjectName('media-title')
        layout.addWidget(self.title_label)
        filename_box = QGroupBox('Output File')
        fn_layout = QVBoxLayout(filename_box)
        fn_layout.setContentsMargins(14, 6, 14, 12)
        fn_layout.setSpacing(10)
        self.filename_input = QLineEdit()
        self.filename_input.setMinimumHeight(42)
        self.auto_name_check = QCheckBox('Automatic name from media metadata')
        self.auto_name_check.setChecked(True)
        self.auto_name_check.toggled.connect(self.filename_input.setEnabled)
        fn_layout.addWidget(self.auto_name_check)
        fn_layout.addWidget(self.filename_input)
        layout.addWidget(filename_box)
        format_box = QGroupBox('Quality')
        fmt_layout = QVBoxLayout(format_box)
        fmt_layout.setContentsMargins(14, 6, 14, 12)
        fmt_layout.setSpacing(14)
        if not self.is_audio_only:
            fmt_layout.addLayout(self._field('VIDEO RESOLUTION', self._make_combo('video')))
            self.video_combo = self._last_combo
        fmt_layout.addLayout(self._field('AUDIO QUALITY', self._make_combo('audio')))
        self.audio_combo = self._last_combo
        fmt_layout.addLayout(self._field('CONTAINER', self._make_container_combo()))
        self.container_combo = self._last_combo
        if not self.is_audio_only:
            self.quality_info = QLabel('')
            self.quality_info.setObjectName('quality-info')
            fmt_layout.addWidget(self.quality_info)
        layout.addWidget(format_box)
        footer = QHBoxLayout()
        footer.setSpacing(12)
        footer.addStretch()
        cancel_btn = QPushButton('Cancel')
        cancel_btn.setObjectName('secondary-btn')
        cancel_btn.setMinimumSize(120, 44)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton('Start Download')
        self.ok_btn.setObjectName('primary-btn')
        self.ok_btn.setMinimumSize(190, 44)
        self.ok_btn.setCursor(Qt.PointingHandCursor)
        self.ok_btn.setEnabled(False)
        self.ok_btn.clicked.connect(self.accept)
        footer.addWidget(cancel_btn)
        footer.addWidget(self.ok_btn)
        layout.addLayout(footer)

    def _make_combo(self, kind):
        combo = QComboBox()
        combo.setMinimumHeight(42)
        combo.currentIndexChanged.connect(lambda _: self._update_filename())
        self._last_combo = combo
        return combo

    def _make_container_combo(self):
        combo = QComboBox()
        combo.setMinimumHeight(42)
        combo.addItem('MP4', 'mp4')
        combo.addItem('MKV', 'mkv')
        if self.prefill_container == 'mkv':
            combo.setCurrentIndex(1)
        combo.currentIndexChanged.connect(lambda _: self._update_filename())
        self._last_combo = combo
        return combo

    @staticmethod
    def _field(label_text, widget):
        box = QVBoxLayout()
        box.setSpacing(6)
        lbl = QLabel(label_text)
        lbl.setObjectName('field-label')
        box.addWidget(lbl)
        box.addWidget(widget)
        return box

    def _start_probe(self):
        self.title_label.setText(self._fallback_title())
        self.worker = ProbeWorker(self.url)
        self.worker.finished.connect(self._on_probe_finished)
        self.worker.start()

    def _fallback_title(self):
        if self.is_audio_only:
            return 'Audio-only extraction'
        return 'Detecting media...'

    def _on_probe_finished(self, result):
        self.probe_result = result
        self.status_box.hide()
        self.ok_btn.setEnabled(True)
        if result is None:
            if FormatProbe.last_auth_required:
                self.title_label.setText('Sign-in required content is not supported')
                self.status_box.show()
                self.status_label.setText('PDM downloads publicly accessible files only.')
                self.progress_bar.setRange(0, 1)
                self.ok_btn.setEnabled(False)
                return
            self.title_label.setText('Best available quality will be used')
            if not self.is_audio_only:
                self.video_combo.addItem('Best Available', None)
                self.quality_info.setText('No detailed format list available for this source.')
            self.audio_combo.addItem('Best Available', None)
            self.filename_input.setText(MediaNamer.build_filename({}, self.url, container=self._container(), video_fmt=None, audio_fmt=None))
            return
        if result.get('drm'):
            self.status_box.show()
            self.status_label.setText('DRM-protected content detected')
            self.progress_bar.setRange(0, 1)
            self.ok_btn.setEnabled(False)
            QMessageBox.warning(self, 'DRM Protected', 'This media is protected by DRM (Widevine/FairPlay/PlayReady).\n\nPDM cannot download DRM-protected content. Please choose content that is not DRM-protected.')
            return
        self.video_formats = result.get('video_formats') or []
        self.audio_formats = result.get('audio_formats') or []
        title = result.get('title') or 'download'
        self.title_label.setText(sanitize(title, 80))
        self._populate_combos()

    def _populate_combos(self):
        self.video_combo.blockSignals(True)
        self.audio_combo.blockSignals(True)
        self.video_combo.clear()
        self.audio_combo.clear()
        self.video_combo.addItem('Best Available', None)
        if self.video_formats:
            best_combined = None
            for fmt in self.video_formats:
                label = self._video_label(fmt)
                self.video_combo.addItem(label, fmt.get('format_id'))
                if best_combined is None or (fmt.get('height') or 0) > (best_combined.get('height') or 0):
                    best_combined = fmt
            self._best_video_id = self.video_combo.itemData(1)
        else:
            self._best_video_id = None
        self.audio_combo.addItem('Best Available', None)
        if self.audio_formats:
            for fmt in self.audio_formats:
                self.audio_combo.addItem(self._audio_label(fmt), fmt.get('format_id'))
            self._best_audio_id = self.audio_combo.itemData(1)
        else:
            self._best_audio_id = None
        if self.video_formats:
            self.video_combo.setCurrentIndex(1)
        if self.audio_formats:
            self.audio_combo.setCurrentIndex(1)
        self.video_combo.blockSignals(False)
        self.audio_combo.blockSignals(False)
        self._update_quality_info()
        self._update_filename()

    def _video_label(self, fmt):
        if fmt.get('combined'):
            return f'{quality_label(fmt)} (combined)'
        fps = int(fmt.get('fps') or 0)
        fps_s = f'{fps}fps' if fps else ''
        codec = video_codec_name(fmt.get('vcodec'))
        size = self._approx_size(fmt)
        bits = [f'{quality_label(fmt)}', fps_s, codec, size]
        return ' - '.join((b for b in bits if b))

    def _audio_label(self, fmt):
        if fmt.get('combined'):
            return f'{audio_label(fmt)} (combined)'
        label = audio_label(fmt)
        abr = int(fmt.get('abr') or 0)
        if 'kbps' not in label and abr:
            label += f' {int(abr)}kbps'
        return label

    def _approx_size(self, fmt):
        size = fmt.get('filesize') or fmt.get('filesize_approx')
        if not size:
            return ''
        for u in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f'~{size:.0f}{u}'
            size /= 1024
        return f'~{size:.1f}GB'

    def _update_quality_info(self):
        if self.is_audio_only:
            return
        idx = self.video_combo.currentIndex()
        fmt = None
        if idx > 0 and idx <= len(self.video_formats):
            fmt = self.video_formats[idx - 1]
        if not fmt:
            self.quality_info.setText('')
            return
        info = []
        if fmt.get('vcodec'):
            info.append(f"Codec: {video_codec_name(fmt.get('vcodec'))}")
        if fmt.get('tbr'):
            info.append(f"~{int(fmt.get('tbr'))} kbps")
        if fmt.get('ext'):
            info.append(f"Container: {fmt.get('ext')}")
        self.quality_info.setText('  |  '.join(info))

    def _update_filename(self):
        if not self.auto_name_check.isChecked():
            return
        video_fmt = self._selected_video_fmt()
        audio_fmt = self._selected_audio_fmt()
        container = 'mp3' if self.is_audio_only else self._container()
        name = MediaNamer.build_filename((self.probe_result or {}).get('info') or {}, self.url, container=container, video_fmt=video_fmt, audio_fmt=audio_fmt)
        self.filename_input.setText(name)

    def _selected_video_fmt(self):
        if self.is_audio_only:
            return None
        idx = self.video_combo.currentIndex()
        if idx <= 0 or idx > len(self.video_formats):
            return None
        return self.video_formats[idx - 1]

    def _selected_audio_fmt(self):
        idx = self.audio_combo.currentIndex()
        if idx <= 0 or idx > len(self.audio_formats):
            return None
        return self.audio_formats[idx - 1]

    def _container(self):
        return self.container_combo.currentData()

    def get_selection(self):
        video_fmt = self._selected_video_fmt()
        audio_fmt = self._selected_audio_fmt()
        return {'video_fmt': video_fmt.get('format_id') if video_fmt else None, 'audio_fmt': audio_fmt.get('format_id') if audio_fmt else None, 'container': 'mp3' if self.is_audio_only else self._container(), 'filename': self.filename_input.text().strip() or 'download', 'video_format': video_fmt, 'audio_format': audio_fmt}