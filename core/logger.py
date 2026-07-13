import logging
import os
from datetime import datetime

class PDMLogger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PDMLogger, cls).__new__(cls)
            cls._instance._setup_logger()
        return cls._instance

    def _setup_logger(self):
        # Anchor logs to the application directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(base_dir, "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_file = os.path.join(log_dir, f"pdm_{datetime.now().strftime('%Y%m%d')}.log")
        
        self.logger = logging.getLogger("PDM")
        self.logger.setLevel(logging.DEBUG)

        # File Handler
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)

        # Console Handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def debug(self, msg):
        self.logger.debug(msg)

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def critical(self, msg):
        self.logger.critical(msg)

logger = PDMLogger()
