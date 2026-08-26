from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QFont, QPen
STATUS_COLORS = {'Downloading': (99, 102, 241), 'Queued': (56, 189, 248), 'Paused': (245, 158, 11), 'Completed': (34, 197, 94), 'Failed': (239, 68, 68), 'Retrying': (245, 158, 11), 'Trash': (107, 114, 136)}
STATUS_LABELS = {'Downloading': 'Downloading', 'Queued': 'Queued', 'Paused': 'Paused', 'Completed': 'Completed', 'Failed': 'Failed', 'Retrying': 'Retrying', 'Trash': 'Trash'}

def status_color(status):
    return STATUS_COLORS.get(status, STATUS_COLORS['Trash'])

class StatusBadgeDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        status = index.data(index.model().StatusRole) or 'Trash'
        r, g, b = status_color(status)
        row_h = option.rect.height()
        pill_h = 26.0
        rect = QRectF(option.rect.x() + 12, option.rect.y() + (row_h - pill_h) / 2, option.rect.width() - 24, pill_h)
        base = QColor(r, g, b)
        bg = QColor(r, g, b, 40)
        painter.setPen(QPen(base, 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        font = QFont(option.font)
        if font.pointSizeF() > 0:
            font.setPointSizeF(font.pointSizeF() - 0.5)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(base.lighter(115))
        painter.drawText(rect, Qt.AlignCenter, STATUS_LABELS.get(status, status))
        painter.restore()

    def sizeHint(self, option, index):
        return super().sizeHint(option, index)

class ProgressDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        percent = index.data(index.model().PercentRole) or 0
        percent = max(0, min(100, percent))
        row_h = option.rect.height()
        bar_h = 10.0
        label_w = 46.0
        bar = QRectF(option.rect.x() + 14, option.rect.y() + (row_h - bar_h) / 2, option.rect.width() - 14 - label_w, bar_h)
        track = QColor(255, 255, 255, 20)
        painter.setPen(Qt.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(bar, bar.height() / 2, bar.height() / 2)
        if percent > 0:
            width = bar.width() * percent / 100.0
            fill = QRectF(bar.x(), bar.y(), max(width, bar.height()), bar.height())
            if percent >= 100:
                grad = QColor(34, 197, 94)
            else:
                grad = QColor(99, 102, 241)
            painter.setBrush(grad)
            painter.drawRoundedRect(fill, bar.height() / 2, bar.height() / 2)
        font = QFont(option.font)
        if font.pointSizeF() > 0:
            font.setPointSizeF(font.pointSizeF() - 0.5)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(232, 234, 242))
        label_rect = QRectF(option.rect.right() - label_w, option.rect.y(), label_w - 10, row_h)
        painter.drawText(label_rect, Qt.AlignRight | Qt.AlignVCenter, f'{percent}%')
        painter.restore()