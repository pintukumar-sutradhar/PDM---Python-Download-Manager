from core.logger import logger

class OTTHandler:

    @staticmethod
    def extract(url):
        if url.lower().split('?')[0].endswith('.m3u8'):
            logger.debug(f'Direct manifest detected: {url}')
            return [{'name': 'Direct_Stream', 'url': url, 'is_direct_hls': True}]
        return []