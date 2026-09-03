"""Global search dialog: quick jump to VMs, hosts, pools and storages.

Type a query (VMID, name, tag, pool, node, storage...) — results from
the domain repositories appear live (debounced).  Selecting a result
jumps to the corresponding item in the tree panel.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ..domain.search import SearchResult, global_search
from .i18n import tr
from .icons import get_icon

KEY_ROLE = Qt.UserRole + 1
_DEBOUNCE_MS = 200

_KIND_LABELS = {
    "vm": "QEMU / LXC",
    "host": "Host",
    "pool": "Pool",
    "storage": "Storage",
}


class GlobalSearchDialog(QDialog):
    """Modal search dialog emitting the tree key of the chosen object."""

    object_selected = Signal(tuple)

    def __init__(self, repos_provider: Callable, parent=None):
        super().__init__(parent)
        self._repos_provider = repos_provider
        self._results: list[SearchResult] = []
        self._build_ui()
        self._run_search()

    def _build_ui(self):
        self.setWindowTitle(tr("Global search"))
        self.setMinimumSize(520, 420)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 12)

        self._input = QLineEdit()
        self._input.setPlaceholderText(tr("Search VMs, hosts, pools, storages..."))
        self._input.setClearButtonEnabled(True)
        self._input.returnPressed.connect(self._select_first)
        layout.addWidget(self._input)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels([tr("Type"), tr("Name"), tr("Location")])
        self._tree.setRootIsDecorated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setAllColumnsShowFocus(True)
        self._tree.itemActivated.connect(self._select_item)
        self._tree.itemDoubleClicked.connect(self._select_item)
        layout.addWidget(self._tree, 1)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #6b7280;")
        layout.addWidget(self._count_label)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._run_search)
        self._input.textChanged.connect(lambda _t: self._debounce.start())

        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._input.setFocus)

        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self._tree.header().setSectionResizeMode(2, QHeaderView.Stretch)

        self._input.setFocus()

    def _run_search(self):
        query = self._input.text()
        node_repo, vm_repo, storage_repo, pool_repo = self._repos_provider()
        self._results = global_search(
            query, node_repo, vm_repo, storage_repo, pool_repo,
        )
        self._tree.clear()
        for result in self._results:
            item = QTreeWidgetItem(
                [_KIND_LABELS.get(result.kind, result.kind), result.label, result.detail],
            )
            item.setIcon(0, get_icon(result.kind))
            item.setData(0, KEY_ROLE, result.key)
            self._tree.addTopLevelItem(item)
        if self._results:
            self._tree.setCurrentItem(self._tree.topLevelItem(0))
            self._count_label.setText(tr("{} results").format(len(self._results)))
        else:
            self._count_label.setText(
                tr("No results") if query.strip() else ""
            )

    def _select_first(self):
        if self._results:
            item = self._tree.currentItem() or self._tree.topLevelItem(0)
            self._select_item(item, 0)

    def _select_item(self, item, _column=0):
        key = item.data(0, KEY_ROLE)
        if key is None:
            return
        self.object_selected.emit(key)
        self.accept()
