import hashlib
from core.logger import logger

class PDMVerifier:
    """Verifies file integrity using various hash algorithms."""
    
    @staticmethod
    def calculate_hash(filepath, algorithm='sha256'):
        try:
            hash_func = hashlib.new(algorithm)
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
        except Exception as e:
            logger.error(f"Verification failed: {str(e)}")
            return None

    @staticmethod
    def verify(filepath, expected_hash, algorithm='sha256'):
        actual = PDMVerifier.calculate_hash(filepath, algorithm)
        return actual == expected_hash.lower() if actual else False
