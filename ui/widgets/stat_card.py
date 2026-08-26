from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt

class StatCard(QFrame):

    def __init__(self, title, icon=''):
        super().__init__()
        self.setObjectName('stat-card')
        self.setMinimumHeight(110)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(8)
        if icon:
            icon_lbl = QLabel(icon)
            icon_lbl.setObjectName('stat-icon')
            head.addWidget(icon_lbl)
        title_lbl = QLabel(title.upper())
        title_lbl.setObjectName('stat-title')
        head.addWidget(title_lbl)
        head.addStretch()
        layout.addLayout(head)
        self.value_lbl = QLabel('—')
        self.value_lbl.setObjectName('stat-value')
        layout.addWidget(self.value_lbl)
        self.sub_lbl = QLabel('')
        self.sub_lbl.setObjectName('stat-sub')
        layout.addWidget(self.sub_lbl)

    def set_value(self, text):
        self.value_lbl.setText(text)

    def set_sub(self, text):
        self.sub_lbl.setText(text)