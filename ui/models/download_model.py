from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
import time

class DownloadModel(QAbstractTableModel):
    """Enterprise-grade model for high-frequency updates with zero flickering."""
    def __init__(self, downloads=None):
        super().__init__()
        self._downloads = downloads or []
        self.headers = ["Filename", "Size", "Status", "Progress", "Speed", "ETA", "Date"]

    def rowCount(self, parent=QModelIndex()): return len(self._downloads)
    def columnCount(self, parent=QModelIndex()): return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._downloads): return None
        
        item = self._downloads[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0: return item.get('filename')
            if col == 1: 
                ts = item.get('total_size', 0)
                return self._format_size(ts) if ts > 0 else "Pending..."
            if col == 2: return item.get('status')
            if col == 3: return "" # Rendered by Delegate
            if col == 4: return f"{item.get('speed', 0.0):.2f} MB/s"
            if col == 5: return item.get('eta', '--:--:--')
            if col == 6: return item.get('created_at')
        
        if role == Qt.ItemDataRole.UserRole:
            return item.get('id')

        # Progress Calculation Logic (FIXED)
        if role == Qt.ItemDataRole.UserRole + 1: # Percentage Role
            if col == 3:
                # 1. Check if status is Completed
                if item.get('status') == "Completed":
                    return 100
                # 2. Use live percent from engine if available
                if 'percent' in item:
                    return item['percent']
                # 3. Fallback to DB sizes
                ts = item.get('total_size', 0)
                ds = item.get('downloaded_size', 0)
                if ts > 0:
                    return int((ds / ts) * 100)
                return 0

        return None

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def update_task(self, dl_id, data_map):
        """High-performance atomic update of a single row."""
        for i, task in enumerate(self._downloads):
            if task['id'] == dl_id:
                task.update(data_map)
                # Emit change only for the affected row to avoid full list flicker
                self.dataChanged.emit(self.index(i, 0), self.index(i, self.columnCount()-1))
                break

    def refresh_all(self, new_list):
        """Full data synchronization."""
        self.beginResetModel()
        self._downloads = new_list
        self.endResetModel()

    def _format_size(self, b):
        if b <= 0: return "Pending..."
        for u in ['B','KB','MB','GB','TB']:
            if b < 1024: return f"{b:.2f} {u}"
            b /= 1024
        return f"{b:.2f} PB"
