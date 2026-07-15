from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...domain._format import (
    format_volsize,  # noqa: F401  (re-export)
    safe_pct,  # noqa: F401  (re-export)
)
from ..hover import enable_row_hover
from ..i18n import tr
from ..theme import Color
from ._constants import _HEADER_STYLE

_FILTER_TEXT_ROLE = Qt.UserRole + 42

_LOADING_STYLE = f"color: {Color.GRAY_400}; font-size: 14px;"


def loading_label():
    lbl = QLabel(tr("Loading..."))
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(_LOADING_STYLE)
    return lbl


def make_table(headers, col_specs, sortable=False):
    table = QTableWidget()
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.verticalHeader().hide()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    for col, (mode, width) in enumerate(col_specs):
        table.horizontalHeader().setSectionResizeMode(col, mode)
        if width is not None:
            table.setColumnWidth(col, width)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    table.horizontalHeader().setStyleSheet(_HEADER_STYLE)
    table.setAlternatingRowColors(True)
    if sortable:
        table.setSortingEnabled(True)
    enable_row_hover(table)
    return table


def filter_table(table, text):
    needle = text.lower()
    sort_was = table.isSortingEnabled()
    if sort_was:
        table.setSortingEnabled(False)
    table.blockSignals(True)
    try:
        for row in range(table.rowCount()):
            visible = False
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if not item:
                    continue
                cached = item.data(_FILTER_TEXT_ROLE)
                if cached is None:
                    cached = item.text().lower()
                    item.setData(_FILTER_TEXT_ROLE, cached)
                if needle in cached:
                    visible = True
                    break
            table.setRowHidden(row, not visible)
    finally:
        table.blockSignals(False)
        if sort_was:
            table.setSortingEnabled(True)


def compact_table(table, max_height=22):
    for r in range(table.rowCount()):
        if table.rowHeight(r) > max_height:
            table.setRowHeight(r, max_height)


def set_cell_text(table, row, col, text, fg_color=None):
    item = table.item(row, col)
    if item is None:
        item = QTableWidgetItem(text)
        table.setItem(row, col, item)
    else:
        item.setText(text)
    if fg_color:
        item.setForeground(QBrush(QColor(fg_color)))


def update_progress_bar(bar, value, fmt):
    from ._constants import _progress_style
    bar.setValue(value)
    bar.setFormat(fmt)
    bar.setStyleSheet(_progress_style(value))


def make_filterable_table(table):
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    search = QLineEdit()
    search.setPlaceholderText(tr("Filter"))
    search.setStyleSheet(
        f"QLineEdit {{ font-size: 12px; padding: 4px 8px; border: 1px solid {Color.D1_D5_DB}; "
        f"border-radius: 3px; margin: 4px 4px 0 4px; }}"
    )
    debounce = QTimer(container)
    debounce.setSingleShot(True)
    debounce.setInterval(200)
    debounce.timeout.connect(lambda: filter_table(table, search.text()))
    search.textChanged.connect(debounce.start)
    layout.addWidget(search)
    layout.addWidget(table)
    container._filter_debounce = debounce
    return container


def set_empty_placeholder(table, col_count, text=None):
    if text is None:
        text = tr("No data")
    table.setRowCount(1)
    for c in range(col_count):
        item = QTableWidgetItem(text if c == col_count // 2 else "")
        item.setFlags(Qt.NoItemFlags)
        item.setTextAlignment(Qt.AlignCenter)
        if c == col_count // 2:
            item.setForeground(QBrush(QColor(Color.GRAY_400)))
        table.setItem(0, c, item)
