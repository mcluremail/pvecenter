from PySide6.QtCore import QEvent, Qt, QObject
from PySide6.QtGui import QColor, QBrush

HOVER_COLOR = "#e5e7eb"
ALT_COLOR = "#f3f4f6"
WARN_COLOR = "#fef3c7"
WARN_ROLE = Qt.UserRole + 10

class _RowHoverFilter(QObject):
    def __init__(self, table):
        super().__init__(table)
        self.table = table
        self._prev_row = -1
        table.setMouseTracking(True)
        table.viewport().setMouseTracking(True)
        table.cellEntered.connect(self._on_cell_entered)
        table.viewport().installEventFilter(self)

    def _on_cell_entered(self, row, col):
        self._clear_row(self._prev_row)
        self._highlight_row(row)
        self._prev_row = row

    def _highlight_row(self, row):
        for c in range(self.table.columnCount()):
            item = self.table.item(row, c)
            if item and not item.isSelected():
                item.setBackground(QColor(HOVER_COLOR))

    def _clear_row(self, row):
        if row < 0:
            return
        for c in range(self.table.columnCount()):
            item = self.table.item(row, c)
            if item:
                if item.data(WARN_ROLE):
                    item.setBackground(QColor(WARN_COLOR))
                elif row % 2 == 1:
                    item.setBackground(QColor(ALT_COLOR))
                else:
                    item.setBackground(QBrush())

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Leave:
            self._clear_row(self._prev_row)
            self._prev_row = -1
        return super().eventFilter(obj, event)

def enable_row_hover(table):
    _RowHoverFilter(table)
