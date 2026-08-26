from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

class DownloadModel(QAbstractTableModel):
    IdRole = Qt.ItemDataRole.UserRole
    PercentRole = Qt.ItemDataRole.UserRole + 1
    StatusRole = Qt.ItemDataRole.UserRole + 2
    RawRowRole = Qt.ItemDataRole.UserRole + 3

    def __init__(self, downloads=None):
        super().__init__()
        self._all = downloads or []
        self._downloads = self._all
        self._filter = ''
        self.headers = ['Filename', 'Size', 'Status', 'Progress', 'Speed', 'ETA', 'Date']
        self._sort_col = 0
        self._sort_order = Qt.SortOrder.AscendingOrder

    def rowCount(self, parent=QModelIndex()):
        return len(self._downloads) if not parent.isValid() else 0

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._downloads):
            return None
        item = self._downloads[index.row()]
        col = index.column()
        if role == self.IdRole:
            return item.get('id')
        if role == self.StatusRole:
            return item.get('status')
        if role == self.RawRowRole:
            return item
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(item)
        if role == Qt.ItemDataRole.UserRole + 1:
            if col == 3:
                st = item.get('status')
                if st in ('Completed', 'Finished'):
                    return 100
                if 'percent' in item:
                    return max(0, min(100, int(item['percent'])))
                ts = item.get('total_size', 0) or 0
                ds = item.get('downloaded_size', 0) or 0
                return max(0, min(100, int(ds / ts * 100))) if ts > 0 else 0
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return item.get('filename') or '—'
            if col == 1:
                ts = item.get('total_size', 0)
                return self._format_size(ts) if ts > 0 else 'Pending…'
            if col == 2:
                return item.get('status')
            if col == 3:
                return ''
            if col == 4:
                return self._format_speed(item.get('speed', 0.0))
            if col == 5:
                return item.get('eta', '--:--:--')
            if col == 6:
                created = item.get('created_at', '')
                return created[:16] if created else ''
        if role == Qt.ItemDataRole.FontRole and col == 0:
            from PySide6.QtGui import QFont
            f = QFont()
            f.setBold(True)
            return f
        if role == Qt.ItemDataRole.ForegroundRole:
            if col == 1 or col == 4 or col == 5 or (col == 6):
                from PySide6.QtGui import QColor
                return QColor(154, 161, 180)
        return None

    def _tooltip(self, item):
        lines = [f"<b>{item.get('filename') or 'Unknown'}</b>", f"Status: {item.get('status')}"]
        if item.get('url'):
            lines.append(f"URL: {item['url'][:120]}")
        if item.get('video_format') or item.get('audio_format'):
            parts = []
            if item.get('video_format'):
                parts.append(f"Video: {item['video_format']}")
            if item.get('audio_format'):
                parts.append(f"Audio: {item['audio_format']}")
            lines.append(' · '.join(parts))
        if item.get('container'):
            lines.append(f"Container: {item['container'].upper()}")
        if item.get('file_path'):
            lines.append(f"File: {item['file_path']}")
        if item.get('error_message'):
            lines.append(f"Error: {item['error_message']}")
        return '<br/>'.join(lines)

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        if role == Qt.ItemDataRole.FontRole and orientation == Qt.Orientation.Horizontal:
            from PySide6.QtGui import QFont
            f = QFont()
            f.setPointSizeF(f.pointSizeF() + 0.4)
            f.setBold(True)
            return f
        return None

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        self.layoutAboutToBeChanged.emit()
        self._sort_col = column
        self._sort_order = order

        def key(item):
            if column == 0:
                return (item.get('filename') or '').lower()
            if column == 1:
                return item.get('total_size', 0)
            if column == 2:
                return item.get('status') or ''
            if column == 3:
                st = item.get('status')
                if st == 'Completed':
                    return 101
                if 'percent' in item:
                    return item['percent']
                return 0
            if column == 4:
                return item.get('speed', 0.0)
            if column == 5:
                return item.get('eta', '')
            return item.get('created_at', '')
        self._downloads.sort(key=key, reverse=order == Qt.SortOrder.DescendingOrder)
        self.layoutChanged.emit()

    def update_task(self, dl_id, data_map):
        for i, task in enumerate(self._downloads):
            if task['id'] == dl_id:
                task.update(data_map)
                self.dataChanged.emit(self.index(i, 0), self.index(i, self.columnCount() - 1))
                break

    def set_all(self, new_list):
        self._all = new_list
        self._apply_filter()

    def set_filter(self, text):
        self._filter = (text or '').strip().lower()
        self._apply_filter()

    def _apply_filter(self):
        if not self._filter:
            self._downloads = list(self._all)
        else:
            self._downloads = [t for t in self._all if self._filter in (t.get('filename') or '').lower()]
        self.sort(self._sort_col, self._sort_order)

    def row(self, row):
        if 0 <= row < len(self._downloads):
            return self._downloads[row]
        return None

    @staticmethod
    def _format_size(b):
        if b <= 0:
            return 'Pending…'
        for u in ['B', 'KB', 'MB', 'GB', 'TB']:
            if b < 1024:
                return f'{b:.2f} {u}'
            b /= 1024
        return f'{b:.2f} PB'

    @staticmethod
    def _format_speed(mbps):
        if not mbps or mbps <= 0:
            return '—'
        if mbps >= 1:
            return f'{mbps:.2f} MB/s'
        return f'{mbps * 1024:.0f} KB/s'