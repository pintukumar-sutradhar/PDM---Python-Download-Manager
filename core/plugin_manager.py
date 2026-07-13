import os
import importlib
import inspect
from core.logger import logger

class PDMPluginManager:
    """Manages dynamic loading of download engines and post-processing tools."""
    def __init__(self):
        self.engines = {}
        self.processors = {}
        self._load_plugins()

    def _load_plugins(self):
        # We define built-in engines
        # In a real app, this would scan a 'plugins' folder
        logger.info("Initializing plugin sub-system...")
        
        # Internal Multi-threaded Engine
        self.engines['internal'] = {
            'name': 'Segmented Multi-thread',
            'desc': 'High-speed segmented downloader for direct links.',
            'class': 'InternalDownloader'
        }
        
        # Platform Engine (yt-dlp based)
        self.engines['platform'] = {
            'name': 'Media Extraction Engine',
            'desc': 'Specialized engine for OTT and Social Media.',
            'class': 'PlatformDownloader'
        }

    def get_engine(self, engine_id):
        return self.engines.get(engine_id)

    def register_processor(self, name, func):
        self.processors[name] = func
        logger.info(f"Registered post-processor: {name}")

plugin_manager = PDMPluginManager()
