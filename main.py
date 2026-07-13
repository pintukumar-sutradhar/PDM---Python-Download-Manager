import os
import sys

# Anchor to project root
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.chdir(BASE_DIR)

# Professional imports
from ui.main_window import PDMMainWindow
from core.logger import logger
from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QTimer

class PDMApplication:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("PDM")
        self.app.setOrganizationName("PDM Technologies")
        self.window = None
        
        # Splash screen
        splash_path = os.path.join(BASE_DIR, "assets", "icons", "splash.png")
        if os.path.exists(splash_path):
            self.splash = QSplashScreen(QPixmap(splash_path), Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.splash = QSplashScreen(QPixmap(), Qt.WindowType.WindowStaysOnTopHint)

    def run(self):
        self.splash.show()
        logger.info("Initializing system components...")
        
        # Smooth launch
        QTimer.singleShot(2000, self.show_main_window)
        return self.app.exec()

    def show_main_window(self):
        try:
            self.window = PDMMainWindow()
            self.window.show()
            self.splash.finish(self.window)
            logger.info("Application ready.")
        except Exception as e:
            logger.error(f"Startup error: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    pdm_app = PDMApplication()
    sys.exit(pdm_app.run())
