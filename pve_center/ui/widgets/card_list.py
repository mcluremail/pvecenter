"""CardList — list of card rows (replaces QTableWidget for list views).

Each row is a horizontal card: optional status dot, optional icon,
title, and a flexible set of field slots. Supports filtering and
a double-click signal for future editing.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ..theme import Color

_DOT_COLORS = {
    "ok": Color.STATUS_OK,
    "warn": Color.STATUS_WARN,
    "err": Color.STATUS_ERR,
    "off": Color.TEXT_DIM,
}


def _status_dot(status):
    s = (status or "").lower()
    if s in ("running", "online"):
        return "ok"
    if s in ("stopped", "offline"):
        return "off"
    if s in ("error", "unknown"):
        return "warn"
    return None


class CardRow(QFrame):
    """Single card row in a CardList."""

    doubleClicked = Signal(object)  # emits the row's data dict

    def __init__(self, data, columns, parent=None):
        super().__init__(parent)
        self.setObjectName("cardRow")
        self._data = data
        self._columns = columns
        self._dot_label = None
        self._field_labels = []
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        dot_color_key = self._columns.get("dot")
        if dot_color_key:
            self._dot_label = QLabel("●")
            self._dot_label.setFixedWidth(14)
            self._dot_label.setAlignment(Qt.AlignCenter)
            self._dot_label.setStyleSheet(f"color: {_DOT_COLORS.get(dot_color_key, Color.TEXT_DIM)}; font-size: 10px;")
            layout.addWidget(self._dot_label)

        title_key = self._columns.get("title")
        if title_key:
            self._title_label = QLabel(str(self._data.get(title_key, "")))
            self._title_label.setStyleSheet(f"font-weight: 500; color: {Color.TEXT};")
            self._title_label.setMinimumWidth(80)
            layout.addWidget(self._title_label)

        fields = self._columns.get("fields", [])
        for fkey, fwidth in fields:
            val = self._data.get(fkey, "")
            lbl = QLabel(str(val) if val is not None else "—")
            lbl.setStyleSheet(f"color: {Color.TEXT_SEC};")
            if fwidth:
                lbl.setFixedWidth(fwidth)
            self._field_labels.append((fkey, lbl))
            layout.addWidget(lbl)

        layout.addStretch()

    def update_fields(self, data):
        self._data.update(data)
        if self._dot_label:
            color_key = _status_dot(self._data.get("status", ""))
            if color_key:
                self._dot_label.setStyleSheet(f"color: {_DOT_COLORS.get(color_key, Color.TEXT_DIM)}; font-size: 10px;")
        title_key = self._columns.get("title")
        if title_key and self._title_label:
            self._title_label.setText(str(self._data.get(title_key, "")))
        for fkey, lbl in self._field_labels:
            val = self._data.get(fkey, "")
            lbl.setText(str(val) if val is not None else "—")

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit(self._data)
        super().mouseDoubleClickEvent(event)


class CardList(QWidget):
    """Scrollable list of CardRow widgets with optional filter."""

    cardDoubleClicked = Signal(object)

    def __init__(self, columns, filterable=False, parent=None):
        super().__init__(parent)
        self._columns = columns
        self._rows = []
        self._key_field = columns.get("key", "name")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if filterable:
            self._filter = QLineEdit()
            self._filter.setPlaceholderText("Filter")
            self._filter.textChanged.connect(self._apply_filter)
            layout.addWidget(self._filter)
        else:
            self._filter = None

        self._container = QFrame()
        self._container.setObjectName("cardList")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(0)
        self._container_layout.addStretch()

        self._scroll = QVBoxLayout()
        layout.addWidget(self._container)

        self._empty_label = QLabel("No data")
        self._empty_label.setStyleSheet(f"color: {Color.TEXT_DIM}; padding: 40px; font-size: 13px;")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._container_layout.insertWidget(0, self._empty_label)

    def set_items(self, items):
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows = []

        if not items:
            self._empty_label.show()
            return
        self._empty_label.hide()

        for item in items:
            row = CardRow(item, self._columns)
            row.doubleClicked.connect(self._on_row_double_click)
            self._container_layout.insertWidget(self._container_layout.count() - 1, row)
            self._rows.append(row)

    def update_item(self, key, data):
        for row in self._rows:
            if str(row._data.get(self._key_field, "")) == str(key):
                row.update_fields(data)
                return

    def update_all(self, items):
        key_to_data = {str(it.get(self._key_field, "")): it for it in items}
        for row in self._rows:
            key = str(row._data.get(self._key_field, ""))
            if key in key_to_data:
                row.update_fields(key_to_data[key])

    def clear(self):
        self.set_items([])

    def _apply_filter(self, text):
        text = text.strip().lower()
        for row in self._rows:
            visible = not text
            if not visible:
                for fkey, _ in [(self._columns.get("title", ""), None)] + self._columns.get("fields", []):
                    val = str(row._data.get(fkey, "")).lower()
                    if text in val:
                        visible = True
                        break
            row.setVisible(visible)

    def _on_row_double_click(self, data):
        self.cardDoubleClicked.emit(data)