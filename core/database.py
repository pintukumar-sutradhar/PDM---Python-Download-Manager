import sqlite3
import os
from core.logger import logger

class PDMDatabase:
    _initialized_paths = set()
    _seeded_categories = False

    def __init__(self, db_path=None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, 'database', 'pdm_main.db')
        else:
            self.db_path = db_path
        if os.path.abspath(self.db_path) not in PDMDatabase._initialized_paths:
            self._initialize_db()
            PDMDatabase._initialized_paths.add(os.path.abspath(self.db_path))
        if not PDMDatabase._seeded_categories:
            PDMDatabase._seeded_categories = True
            try:
                from core.categories import ensure_default_categories
                ensure_default_categories()
            except Exception:
                pass

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=5)
        try:
            conn.execute('PRAGMA busy_timeout = 4000')
            conn.execute('PRAGMA journal_mode = WAL')
        except Exception:
            pass
        return conn

    def _initialize_db(self):
        try:
            db_dir = os.path.dirname(self.db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('\n                    CREATE TABLE IF NOT EXISTS downloads (\n                        id INTEGER PRIMARY KEY AUTOINCREMENT,\n                        filename TEXT NOT NULL,\n                        url TEXT NOT NULL,\n                        save_path TEXT NOT NULL,\n                        status TEXT NOT NULL,\n                        total_size INTEGER DEFAULT 0,\n                        downloaded_size INTEGER DEFAULT 0,\n                        category TEXT,\n                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n                    )\n                ')
                cursor.execute('\n                    CREATE TABLE IF NOT EXISTS settings (\n                        key PRIMARY KEY,\n                        value TEXT NOT NULL\n                    )\n                ')
                cursor.execute('CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, extensions TEXT DEFAULT \'\', save_folder TEXT DEFAULT \'\')')
                cursor.execute('CREATE TABLE IF NOT EXISTS rules (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, domain TEXT DEFAULT \'\', extension TEXT DEFAULT \'\', filename_contains TEXT DEFAULT \'\', min_size_mb REAL DEFAULT 0, max_size_mb REAL DEFAULT 0, action_category TEXT DEFAULT \'\', action_folder TEXT DEFAULT \'\', priority INTEGER DEFAULT 0, enabled INTEGER DEFAULT 1)')
                cursor.execute('CREATE TABLE IF NOT EXISTS schedules (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, days TEXT DEFAULT \'0123456\', start_time TEXT DEFAULT \'00:00\', end_time TEXT DEFAULT \'23:59\', enabled INTEGER DEFAULT 1)')
                migrations = ['ALTER TABLE downloads ADD COLUMN is_audio INTEGER DEFAULT 0', "ALTER TABLE downloads ADD COLUMN container TEXT DEFAULT 'mp4'", 'ALTER TABLE downloads ADD COLUMN video_format TEXT', 'ALTER TABLE downloads ADD COLUMN audio_format TEXT', 'ALTER TABLE downloads ADD COLUMN retries INTEGER DEFAULT 0', 'ALTER TABLE downloads ADD COLUMN error_message TEXT', 'ALTER TABLE downloads ADD COLUMN auto_name INTEGER DEFAULT 1']
                for statement in migrations:
                    try:
                        cursor.execute(statement)
                    except sqlite3.OperationalError:
                        pass
                defaults = [('max_concurrent_downloads', '3'), ('default_download_path', os.path.expanduser('~/Downloads')), ('ui_theme', 'dark'), ('default_container', 'mp4'), ('speed_limit', '0'), ('auto_retry', '2'), ('proxy_enabled', '0'), ('proxy_address', '')]
                cursor.executemany('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', defaults)
                conn.commit()
                logger.info('Core database synchronized.')
        except Exception as e:
            logger.error(f'Database sync failed: {str(e)}')

    def get_setting(self, key, default=None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
                row = cursor.fetchone()
                return row[0] if row else default
        except Exception:
            return default

    def set_setting(self, key, value):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
                conn.commit()
        except Exception as e:
            logger.error(f'Setting update failed ({key}): {str(e)}')

    def add_download(self, filename, url, save_path, category='General', container='mp4', video_format=None, audio_format=None, is_audio=False, auto_name=True):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO downloads (filename, url, save_path, status, category, container, video_format, audio_format, is_audio, auto_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (filename, url, save_path, 'Pending', category, container, video_format, audio_format, int(is_audio), int(auto_name)))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f'Download registration failed: {str(e)}')
            return None

    def update_download_path(self, download_id, filename, save_path):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE downloads SET filename = ?, save_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (filename, save_path, download_id))
                conn.commit()
        except Exception as e:
            logger.error(f'Path update failed for ID {download_id}: {str(e)}')

    def update_download_status(self, download_id, status, downloaded_size=None, total_size=None):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if downloaded_size is not None and total_size is not None:
                    cursor.execute('UPDATE downloads SET status = ?, downloaded_size = ?, total_size = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (status, downloaded_size, total_size, download_id))
                else:
                    cursor.execute('UPDATE downloads SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (status, download_id))
                conn.commit()
        except Exception as e:
            logger.error(f'Status update failed for ID {download_id}: {str(e)}')

    def get_all_downloads_including_trash(self):
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM downloads ORDER BY created_at DESC')
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f'Failed to load downloads: {str(e)}')
            return []

    def clear_all_downloads(self):
        import time as _time
        for attempt in range(4):
            try:
                with self._get_connection() as conn:
                    conn.execute('DELETE FROM downloads')
                    conn.commit()
                return True
            except Exception as e:
                if attempt == 3:
                    logger.error(f'Clear all failed: {str(e)}')
                    return False
                _time.sleep(0.35 * (attempt + 1))

    def delete_download_permanently(self, download_id):
        try:
            with self._get_connection() as conn:
                conn.execute('DELETE FROM downloads WHERE id = ?', (download_id,))
                conn.commit()
        except Exception:
            pass
    def update_torrent_progress(self, filename, downloaded, total):
        try:
            done = int(max(0, downloaded))
            tot = int(max(done, total))
            with self._get_connection() as conn:
                conn.execute("UPDATE downloads SET downloaded_size = ?, total_size = ?, status = 'Downloading' WHERE container = 'torrent' AND filename = ?", (done, tot, filename))
        except Exception as e:
            logger.error(f'Torrent progress update failed: {str(e)}')

    def delete_torrent_record(self, filename):
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM downloads WHERE container = 'torrent' AND (filename = ? OR filename LIKE ?)", (filename, filename + '%'))
        except Exception as e:
            logger.error(f'Failed to delete torrent record: {str(e)}')

    def delete_all_torrent_records(self):
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM downloads WHERE container = 'torrent'")
        except Exception as e:
            logger.error(f'Failed to clear torrent records: {str(e)}')

    def get_categories(self):
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute('SELECT * FROM categories ORDER BY id').fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f'Failed to load categories: {str(e)}')
            return []

    def add_category(self, name, extensions='', save_folder=''):
        with self._get_connection() as conn:
            conn.execute('INSERT OR IGNORE INTO categories (name, extensions, save_folder) VALUES (?, ?, ?)', (name, extensions, save_folder))
            conn.commit()

    def update_category(self, cat_id, extensions, save_folder):
        with self._get_connection() as conn:
            conn.execute('UPDATE categories SET extensions = ?, save_folder = ? WHERE id = ?', (extensions, save_folder, cat_id))
            conn.commit()

    def delete_category(self, cat_id):
        with self._get_connection() as conn:
            conn.execute('DELETE FROM categories WHERE id = ?', (cat_id,))
            conn.commit()

    def get_rules(self):
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute('SELECT * FROM rules WHERE enabled = 1 ORDER BY priority DESC, id').fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f'Failed to load rules: {str(e)}')
            return []

    def get_all_rules(self):
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute('SELECT * FROM rules ORDER BY priority DESC, id').fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []

    def add_rule(self, name, domain='', extension='', filename_contains='', min_size_mb=0.0, max_size_mb=0.0, action_category='', action_folder='', priority=0, enabled=1):
        with self._get_connection() as conn:
            cur = conn.execute('INSERT INTO rules (name, domain, extension, filename_contains, min_size_mb, max_size_mb, action_category, action_folder, priority, enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (name, domain, extension, filename_contains, min_size_mb, max_size_mb, action_category, action_folder, priority, enabled))
            conn.commit()
            return cur.lastrowid

    def toggle_rule(self, rule_id, enabled):
        with self._get_connection() as conn:
            conn.execute('UPDATE rules SET enabled = ? WHERE id = ?', (enabled, rule_id))
            conn.commit()

    def delete_rule(self, rule_id):
        with self._get_connection() as conn:
            conn.execute('DELETE FROM rules WHERE id = ?', (rule_id,))
            conn.commit()

    def get_schedules(self, only_enabled=True):
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                q = 'SELECT * FROM schedules' + (' WHERE enabled = 1' if only_enabled else '') + ' ORDER BY id'
                rows = conn.execute(q).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f'Failed to load schedules: {str(e)}')
            return []

    def add_schedule(self, name, days='0123456', start_time='00:00', end_time='23:59', enabled=1):
        with self._get_connection() as conn:
            cur = conn.execute('INSERT INTO schedules (name, days, start_time, end_time, enabled) VALUES (?, ?, ?, ?, ?)', (name, days, start_time, end_time, enabled))
            conn.commit()
            return cur.lastrowid

    def toggle_schedule(self, sched_id, enabled):
        with self._get_connection() as conn:
            conn.execute('UPDATE schedules SET enabled = ? WHERE id = ?', (enabled, sched_id))
            conn.commit()

    def delete_schedule(self, sched_id):
        with self._get_connection() as conn:
            conn.execute('DELETE FROM schedules WHERE id = ?', (sched_id,))
            conn.commit()

    def add_torrent_record(self, url, filename, save_path):
        try:
            with self._get_connection() as conn:
                dupes = [r[0] for r in conn.execute("SELECT id FROM downloads WHERE container = 'torrent' AND (filename = ? OR ? LIKE filename || '%')", (filename, filename)).fetchall()]
                for d_id in dupes:
                    conn.execute('DELETE FROM downloads WHERE id = ?', (d_id,))
                cur = conn.execute('INSERT INTO downloads (filename, url, save_path, status, total_size, category, container) VALUES (?, ?, ?, ?, 0, ?, ?)', (filename, url[:500], os.path.join(save_path, filename), 'Downloading', 'Torrents', 'torrent'))
                conn.commit()
                return cur.lastrowid
        except Exception as e:
            logger.error(f'Torrent record failed: {e}')
            return None

    def rename_torrent_record(self, old_name, new_name):
        try:
            with self._get_connection() as conn:
                conn.execute('UPDATE downloads SET filename = ?, updated_at = CURRENT_TIMESTAMP WHERE filename = ? AND container = ?', (new_name, old_name, 'torrent'))
                conn.commit()
        except Exception as e:
            logger.error(f'Torrent rename failed: {e}')

    def complete_torrent_record(self, final_name, size_bytes):
        try:
            with self._get_connection() as conn:
                row = conn.execute('SELECT id FROM downloads WHERE filename = ? AND container = ? ORDER BY id DESC LIMIT 1', (final_name, 'torrent')).fetchone()
                if row:
                    conn.execute("UPDATE downloads SET status = 'Finished', total_size = ?, downloaded_size = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (size_bytes, size_bytes, row[0]))
                    conn.commit()
        except Exception as e:
            logger.error(f'Torrent complete failed: {e}')
