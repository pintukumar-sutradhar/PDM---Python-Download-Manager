import os
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon
from PySide6.QtCore import Signal

class PDMTrayIcon(QSystemTrayIcon):
    show_window = Signal()
    quit_app = Signal()

    def __init__(self, parent=None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, 'assets', 'icons', 'app_icon.png')
        icon = QIcon(icon_path)
        super().__init__(icon, parent)
        self.setToolTip('PDM')
        self.init_menu()

    def init_menu(self):
        menu = QMenu()
        show_action = menu.addAction('Open PDM')
        show_action.triggered.connect(self.show_window.emit)
        menu.addSeparator()
        quit_action = menu.addAction('Exit Application')
        quit_action.triggered.connect(self.quit_app.emit)
        self.setContextMenu(menu)