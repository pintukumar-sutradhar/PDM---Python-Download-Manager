import sqlite3
import os
from core.logger import logger

class PDMDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, "database", "pdm_main.db")
        else:
            self.db_path = db_path
        self._initialize_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _initialize_db(self):
        try:
            db_dir = os.path.dirname(self.db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir)

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS downloads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filename TEXT NOT NULL,
                        url TEXT NOT NULL,
                        save_path TEXT NOT NULL,
                        status TEXT NOT NULL,
                        total_size INTEGER DEFAULT 0,
                        downloaded_size INTEGER DEFAULT 0,
                        category TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                """)
                
                # Maintenance: Ensure schema consistency
                try: cursor.execute("ALTER TABLE downloads ADD COLUMN is_audio INTEGER DEFAULT 0")
                except: pass
                
                defaults = [
                    ('max_concurrent_downloads', '8'),
                    ('default_download_path', os.path.expanduser("~/Downloads")),
                    ('theme', 'Abyssal Current'),
                    ('browser_source', 'disabled')
                ]
                cursor.executemany("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", defaults)
                conn.commit()
                logger.info("Core database synchronized.")
        except Exception as e:
            logger.error(f"Database sync failed: {str(e)}")

    def get_setting(self, key, default=None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row[0] if row else default
        except: return default

    def set_setting(self, key, value):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
                conn.commit()
        except Exception as e:
            logger.error(f"Setting update failed ({key}): {str(e)}")

    def add_download(self, filename, url, save_path, category="General"):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO downloads (filename, url, save_path, status, category) VALUES (?, ?, ?, ?, ?)",
                    (filename, url, save_path, "Pending", category)
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Download registration failed: {str(e)}")
            return None

    def update_download_status(self, download_id, status, downloaded_size=None, total_size=None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if downloaded_size is not None and total_size is not None:
                    cursor.execute(
                        "UPDATE downloads SET status = ?, downloaded_size = ?, total_size = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (status, downloaded_size, total_size, download_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE downloads SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (status, download_id)
                    )
                conn.commit()
        except Exception as e:
            logger.error(f"Status update failure for ID {download_id}: {str(e)}")

    def get_all_downloads_including_trash(self):
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM downloads ORDER BY created_at DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Repository fetch failed: {str(e)}")
            return []

    def clear_all_downloads(self):
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM downloads")
                conn.commit()
        except: pass

    def delete_download_permanently(self, download_id):
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM downloads WHERE id = ?", (download_id,))
                conn.commit()
        except: pass
