from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QLineEdit, QPushButton, QCheckBox,
                               QComboBox, QGroupBox, QSpinBox)
from PySide6.QtGui import QIntValidator
from .i18n import tr
from .theme import Color


class CloneVMDialog(QDialog):
    def __init__(self, parent=None, vm_info=None, cluster_nodes=None,
                 current_node="", storages=None):
        super().__init__(parent)
        self._vm_info = vm_info or {}
        self._cluster_nodes = cluster_nodes or []
        self._current_node = current_node
        self._storages = storages or []
        self.setWindowTitle(tr("Clone VM"))
        self.setMinimumWidth(450)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info_group = QGroupBox(tr("VM info"))
        info_grid = QGridLayout(info_group)
        vm_name = self._vm_info.get("name", "")
        vmid = self._vm_info.get("vmid", "")
        vm_type = self._vm_info.get("type", "qemu")
        node = self._vm_info.get("node", self._current_node)

        info_grid.addWidget(QLabel(tr("Name:")), 0, 0)
        info_grid.addWidget(QLabel(vm_name), 0, 1)
        info_grid.addWidget(QLabel("VMID:"), 1, 0)
        info_grid.addWidget(QLabel(str(vmid)), 1, 1)
        info_grid.addWidget(QLabel(tr("Type:")), 2, 0)
        type_label = "QEMU" if vm_type == "qemu" else "LXC"
        info_grid.addWidget(QLabel(type_label), 2, 1)
        info_grid.addWidget(QLabel(tr("Source node:")), 3, 0)
        info_grid.addWidget(QLabel(node), 3, 1)
        layout.addWidget(info_group)

        clone_group = QGroupBox(tr("Clone settings"))
        clone_grid = QGridLayout(clone_group)

        clone_grid.addWidget(QLabel(tr("New VMID:")), 0, 0)
        self.newid_input = QLineEdit()
        self.newid_input.setPlaceholderText(tr("auto"))
        self.newid_input.setValidator(QIntValidator(100, 999999999))
        clone_grid.addWidget(self.newid_input, 0, 1)

        clone_grid.addWidget(QLabel(tr("New name:")), 1, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(tr("Copy of {}").format(vm_name))
        clone_grid.addWidget(self.name_input, 1, 1)

        clone_grid.addWidget(QLabel(tr("Target node:")), 2, 0)
        self.target_combo = QComboBox()
        self.target_combo.addItem(self._current_node, self._current_node)
        for n in self._cluster_nodes:
            n_name = n.get("node", "") if isinstance(n, dict) else str(n)
            if n_name and n_name != self._current_node:
                self.target_combo.addItem(n_name, n_name)
        clone_grid.addWidget(self.target_combo, 2, 1)

        clone_grid.addWidget(QLabel(tr("Storage:")), 3, 0)
        self.storage_combo = QComboBox()
        self._fill_storages(self._current_node)
        self.target_combo.currentTextChanged.connect(self._on_target_changed)
        clone_grid.addWidget(self.storage_combo, 3, 1)

        self.full_clone_cb = QCheckBox(tr("Full clone (copy all disks)"))
        self.full_clone_cb.setChecked(True)
        clone_grid.addWidget(self.full_clone_cb, 4, 0, 1, 2)

        layout.addWidget(clone_group)

        btn_layout = QHBoxLayout()
        self.clone_btn = QPushButton(tr("Clone"))
        self.clone_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(tr("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.clone_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _fill_storages(self, node):
        self.storage_combo.clear()
        self.storage_combo.addItem(tr("Same as source"), "")
        seen = set()
        for s in self._storages:
            s_node = s.get("node", "")
            s_name = s.get("storage", "")
            if s_name and s_name not in seen and (not s_node or s_node == node):
                self.storage_combo.addItem(s_name, s_name)
                seen.add(s_name)

    def _on_target_changed(self, text):
        data = self.target_combo.currentData()
        if data:
            self._fill_storages(data)

    def get_params(self):
        newid_text = self.newid_input.text().strip()
        params = {
            "target": self.target_combo.currentData() or self._current_node,
            "full": self.full_clone_cb.isChecked(),
        }
        if newid_text:
            params["newid"] = int(newid_text)
        name = self.name_input.text().strip()
        if name:
            params["name"] = name
        storage = self.storage_combo.currentData()
        if storage:
            params["storage"] = storage
        return params