from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QLineEdit, QPushButton, QCheckBox,
                               QComboBox, QSpinBox, QGroupBox)
from PySide6.QtCore import Qt


VM_OS_TYPES = [
    ("other", "Other"),
    ("l26", "Linux 2.6+ / 3.x / 4.x"),
    ("l24", "Linux 2.4"),
    ("win10", "Windows 10/11"),
    ("win11", "Windows 11"),
    ("win8", "Windows 8"),
    ("win7", "Windows 7"),
    ("w2k8", "Windows Server 2008"),
    ("w2k3", "Windows Server 2003"),
    ("w2k", "Windows 2000"),
    ("wvista", "Windows Vista"),
    ("wxp", "Windows XP"),
    ("solaris", "Solaris"),
]

DISK_BUSES = ["virtio", "scsi", "sata", "ide"]
NET_MODELS = ["virtio", "e1000", "rtl8139", "vmxnet3"]


class CreateVmDialog(QDialog):
    def __init__(self, parent=None, nodes=None, storages=None):
        super().__init__(parent)
        self.setWindowTitle("Создание виртуальной машины")
        self.setFixedSize(520, 580)
        self._nodes = nodes or []
        self._storages = storages or []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # --- Основное ---
        general = QGroupBox("Основное")
        g_grid = QGridLayout(general)

        g_grid.addWidget(QLabel("Узел:"), 0, 0)
        self.node_combo = QComboBox()
        node_labels = {}
        for n in self._nodes:
            label = n.get("_display_name") or n.get("node", "?")
            self.node_combo.addItem(label, n.get("node", ""))
            node_labels[n.get("node", "")] = label
        g_grid.addWidget(self.node_combo, 0, 1)

        g_grid.addWidget(QLabel("VM ID:"), 1, 0)
        self.vmid_spin = QSpinBox()
        self.vmid_spin.setRange(0, 999999999)
        self.vmid_spin.setValue(0)
        self.vmid_spin.setSpecialValueText("авто")
        g_grid.addWidget(self.vmid_spin, 1, 1)

        g_grid.addWidget(QLabel("Имя ВМ:"), 2, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("my-vm")
        g_grid.addWidget(self.name_input, 2, 1)

        g_grid.addWidget(QLabel("Тип ОС:"), 3, 0)
        self.ostype_combo = QComboBox()
        for val, label in VM_OS_TYPES:
            self.ostype_combo.addItem(label, val)
        self.ostype_combo.setCurrentIndex(1)  # l26
        g_grid.addWidget(self.ostype_combo, 3, 1)

        layout.addWidget(general)

        # --- Система ---
        system = QGroupBox("Система")
        s_grid = QGridLayout(system)

        s_grid.addWidget(QLabel("Ядер:"), 0, 0)
        self.cores_spin = QSpinBox()
        self.cores_spin.setRange(1, 128)
        self.cores_spin.setValue(2)
        s_grid.addWidget(self.cores_spin, 0, 1)

        s_grid.addWidget(QLabel("Сокетов:"), 0, 2)
        self.sockets_spin = QSpinBox()
        self.sockets_spin.setRange(1, 16)
        self.sockets_spin.setValue(1)
        s_grid.addWidget(self.sockets_spin, 0, 3)

        s_grid.addWidget(QLabel("Память (МБ):"), 1, 0)
        self.memory_spin = QSpinBox()
        self.memory_spin.setRange(16, 4194304)
        self.memory_spin.setValue(2048)
        self.memory_spin.setSingleStep(256)
        s_grid.addWidget(self.memory_spin, 1, 1)

        self.start_check = QCheckBox("Запустить после создания")
        self.start_check.setChecked(True)
        s_grid.addWidget(self.start_check, 1, 2, 1, 2)

        layout.addWidget(system)

        # --- Диск ---
        disk = QGroupBox("Диск")
        d_grid = QGridLayout(disk)

        d_grid.addWidget(QLabel("Хранилище:"), 0, 0)
        self.storage_combo = QComboBox()
        seen_storages = set()
        for s in self._storages:
            name = s.get("storage", "")
            if name not in seen_storages:
                seen_storages.add(name)
                self.storage_combo.addItem(name, name)
        d_grid.addWidget(self.storage_combo, 0, 1)

        d_grid.addWidget(QLabel("Размер (ГБ):"), 0, 2)
        self.disk_size_spin = QSpinBox()
        self.disk_size_spin.setRange(1, 1048576)
        self.disk_size_spin.setValue(16)
        d_grid.addWidget(self.disk_size_spin, 0, 3)

        d_grid.addWidget(QLabel("Шина:"), 1, 0)
        self.bus_combo = QComboBox()
        for bus in DISK_BUSES:
            self.bus_combo.addItem(bus, bus)
        self.bus_combo.setCurrentIndex(0)  # virtio
        d_grid.addWidget(self.bus_combo, 1, 1)

        layout.addWidget(disk)

        # --- Сеть ---
        network = QGroupBox("Сеть")
        n_grid = QGridLayout(network)

        n_grid.addWidget(QLabel("Мост:"), 0, 0)
        self.bridge_input = QLineEdit("vmbr0")
        n_grid.addWidget(self.bridge_input, 0, 1)

        n_grid.addWidget(QLabel("Модель:"), 0, 2)
        self.model_combo = QComboBox()
        for m in NET_MODELS:
            self.model_combo.addItem(m, m)
        n_grid.addWidget(self.model_combo, 0, 3)

        layout.addWidget(network)

        # --- Кнопки ---
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_btn)

        self.create_btn = QPushButton("Создать")
        self.create_btn.setFixedWidth(120)
        self.create_btn.setStyleSheet(
            "QPushButton { background: #2563eb; color: white; font-weight: 600; border: none; }"
            "QPushButton:hover { background: #1d4ed8; }"
        )
        self.create_btn.clicked.connect(self._on_create)
        buttons.addWidget(self.create_btn)

        layout.addLayout(buttons)

    def _on_create(self):
        name = self.name_input.text().strip()
        if not name:
            self.name_input.setFocus()
            self.name_input.setStyleSheet("border: 1px solid #ef4444;")
            return
        self.name_input.setStyleSheet("")
        self.accept()

    def get_params(self):
        """Возвращает dict параметров для CreateVmWorker."""
        vmid = self.vmid_spin.value()
        bus = self.bus_combo.currentData()
        slot = 0
        disk_key = f"{bus}{slot}"
        size_gb = self.disk_size_spin.value()

        storage = self.storage_combo.currentData()
        if storage:
            disk_val = f"{storage}:{size_gb}"
        else:
            disk_val = f"local-lvm:{size_gb}"

        bridge = self.bridge_input.text().strip() or "vmbr0"
        model = self.model_combo.currentData()
        net_val = f"model={model},bridge={bridge}"

        params = {
            "name": self.name_input.text().strip(),
            "ostype": self.ostype_combo.currentData(),
            "cores": self.cores_spin.value(),
            "sockets": self.sockets_spin.value(),
            "memory": self.memory_spin.value(),
            "net0": net_val,
            disk_key: disk_val,
            "start": int(self.start_check.isChecked()),
        }
        if vmid > 0:
            params["vmid"] = vmid

        return params

    def get_node(self):
        return self.node_combo.currentData()
