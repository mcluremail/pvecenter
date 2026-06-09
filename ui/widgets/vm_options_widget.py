from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, QWidget
from PySide6.QtCore import Qt, Signal
from ..hover import enable_row_hover
from ..vm_config_display import get_options_rows, FIELD_TYPES
from ..vm_config_editor_dialog import VmConfigEditorDialog

_FT = FIELD_TYPES
_KEY_ROLE = Qt.UserRole + 100
_READONLY_ROLE = Qt.UserRole + 101


class VmOptionsWidget(QWidget):
    config_changed = Signal(str, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config_data = {}
        self._host_name = ""
        self._vmid = 0
        self._node = ""

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Параметр", "Значение"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setStyleSheet("QHeaderView::section { padding-left: 4px; }")
        self.table.setAlternatingRowColors(True)
        enable_row_hover(self.table)
        self.table.cellDoubleClicked.connect(self._on_double_click)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.setContentsMargins(0, 0, 0, 0)

    def set_context(self, host_name, vmid, node):
        self._host_name = host_name
        self._vmid = vmid
        self._node = node

    def set_options_data(self, config_data):
        self._config_data = config_data or {}
        self.table.setRowCount(0)
        rows = get_options_rows(config_data)
        if not rows:
            return
        for i, (key, label, value) in enumerate(rows):
            self.table.insertRow(i)
            item = QTableWidgetItem(label)
            item.setData(_KEY_ROLE, key)
            self.table.setItem(i, 0, item)
            self.table.setItem(i, 1, QTableWidgetItem(value))
        self.table.resizeRowsToContents()
        for r in range(self.table.rowCount()):
            if self.table.rowHeight(r) > 22:
                self.table.setRowHeight(r, 22)

    def _on_double_click(self, row, col):
        if not (self._host_name and self._vmid):
            return
        item = self.table.item(row, 0)
        if not item:
            return
        raw_key = item.data(_KEY_ROLE)
        if not raw_key or raw_key not in _FT:
            return

        field_spec = _FT[raw_key]
        if isinstance(field_spec, tuple):
            if field_spec[0] == "readonly":
                return
            ft_type, choices = field_spec[0], field_spec[1]
        else:
            ft_type = field_spec
            choices = None
            if ft_type == "readonly":
                return

        current_value = self._config_data.get(raw_key)
        label = item.text()

        dlg = VmConfigEditorDialog(raw_key, label, ft_type, current_value, choices, self)
        if dlg.exec() != VmConfigEditorDialog.Accepted:
            return
        key, value = dlg.get_raw_value()
        if value is None:
            return
        self.config_changed.emit(self._host_name, str(self._vmid), {key: value})
