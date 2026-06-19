from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, QWidget, QMessageBox
from PySide6.QtCore import Qt, Signal
from ..hover import enable_row_hover
from ..vm_config_display import (get_hardware_rows, get_editor_spec,
                                 HW_DEFAULTS, is_net_key, is_cdrom_key, is_disk_key)
from ..vm_config_editor_dialog import VmConfigEditorDialog
from ..vm_device_editors import (VmNetworkEditorDialog, VmCdromEditorDialog,
                                 VmDiskEditorDialog)
from ..i18n import tr
from ..detail_panel._table_utils import set_empty_placeholder

_KEY_ROLE = Qt.UserRole + 100
_READONLY_ROLE = Qt.UserRole + 101


class VmHardwareWidget(QWidget):
    config_changed = Signal(str, str, object)

    _EDITABLE_WHEN_RUNNING = ("ide2", "net0", "net1", "net2", "net3")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config_data = {}
        self._host_name = ""
        self._vmid = 0
        self._node = ""
        self._iso_list = []
        self._vm_status = "stopped"

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels([tr("Parameter"), tr("Value")])
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

    def set_vm_status(self, status):
        self._vm_status = status or "stopped"

    def set_iso_list(self, iso_set):
        self._iso_list = iso_set

    def set_hardware_data(self, config_data, detail_data=None):
        self._config_data = config_data or {}
        self.table.setRowCount(0)
        rows = get_hardware_rows(config_data, detail_data)
        if not rows:
            set_empty_placeholder(self.table, 2)
            return
        for i, (key, label, value) in enumerate(rows):
            self.table.insertRow(i)
            item = QTableWidgetItem(label)
            item.setData(_KEY_ROLE, key)
            ft, _, _ = get_editor_spec(key)
            if ft == "readonly":
                item.setData(_READONLY_ROLE, True)
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
        if not item or item.data(_READONLY_ROLE):
            return
        raw_key = item.data(_KEY_ROLE)
        if not raw_key:
            return

        is_running = self._vm_status == "running"
        if is_running and raw_key not in self._EDITABLE_WHEN_RUNNING:
            QMessageBox.information(self, tr("Cannot be changed on a running VM"),
                                    tr("Stop the VM to edit"))
            return

        current_value = self._config_data.get(raw_key)
        label = item.text()

        if is_net_key(raw_key):
            dlg = VmNetworkEditorDialog(raw_key, label, current_value,
                                        running=is_running, parent=self)
            if dlg.exec() != VmNetworkEditorDialog.Accepted:
                return
            key, value = dlg.get_raw_value()
            if value is not None:
                self.config_changed.emit(self._host_name, str(self._vmid), {key: value})
            return

        if is_cdrom_key(raw_key):
            dlg = VmCdromEditorDialog(raw_key, label, current_value,
                                      self._iso_list, self)
            if dlg.exec() != VmCdromEditorDialog.Accepted:
                return
            key, value = dlg.get_raw_value()
            if value is None:
                self.config_changed.emit(self._host_name, str(self._vmid),
                                         {key: "none"})
            else:
                self.config_changed.emit(self._host_name, str(self._vmid),
                                         {key: value})
            return

        if is_disk_key(raw_key):
            dlg = VmDiskEditorDialog(raw_key, label, current_value, self)
            if dlg.exec() != VmDiskEditorDialog.Accepted:
                return
            key, value = dlg.get_raw_value()
            if value is not None:
                self.config_changed.emit(self._host_name, str(self._vmid), {key: value})
            return

        ft, choices, choice_labels = get_editor_spec(raw_key)
        if ft == "readonly":
            return
        if current_value is None:
            current_value = HW_DEFAULTS.get(raw_key, "")
        dlg = VmConfigEditorDialog(raw_key, label, ft, current_value, choices,
                                   choice_labels, self)
        if dlg.exec() != VmConfigEditorDialog.Accepted:
            return
        key, value = dlg.get_raw_value()
        if value is None:
            return
        self.config_changed.emit(self._host_name, str(self._vmid), {key: value})
