import re
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QLineEdit, QSpinBox, QComboBox,
                               QFormLayout, QMessageBox, QGroupBox)
from PySide6.QtCore import Qt


NET_MODELS = ["virtio", "e1000", "rtl8139", "vmxnet3"]

DISK_CACHE = [
    ("none", "Нет"),
    ("writeback", "Write back"),
    ("writethrough", "Write through"),
    ("directsync", "Direct sync"),
    ("unsafe", "Unsafe"),
]


def _parse_net(val):
    """Parse netX string -> dict of components."""
    val = str(val)
    parts = val.split(",")
    result = {"model": "virtio", "mac": "", "bridge": "vmbr0", "tag": "", "queues": ""}
    if not val:
        return result
    first = parts[0]
    if "=" in first:
        result["model"], result["mac"] = first.split("=", 1)
    else:
        result["model"] = first
    for p in parts[1:]:
        if p.startswith("bridge="):
            result["bridge"] = p.split("=", 1)[1]
        elif p.startswith("tag="):
            result["tag"] = p.split("=", 1)[1]
        elif p.startswith("queues="):
            result["queues"] = p.split("=", 1)[1]
    return result


def _build_net(model, mac, bridge, tag, queues):
    parts = [f"{model}={mac}" if mac else model]
    if bridge:
        parts.append(f"bridge={bridge}")
    if tag:
        parts.append(f"tag={tag}")
    if queues:
        parts.append(f"queues={queues}")
    return ",".join(parts)


def _parse_disk(val):
    parts = str(val).split(",")
    result = {"storage": "", "size": "", "format": "", "cache": "none"}
    if not val:
        return result
    first = parts[0]
    if ":" in first:
        result["storage"] = first.split(":")[0]
        result["size"] = first.split(":", 1)[1]
    for p in parts[1:]:
        if p.startswith("cache="):
            result["cache"] = p.split("=", 1)[1]
        elif p.startswith("format="):
            result["format"] = p.split("=", 1)[1]
    return result


def _parse_cdrom(val):
    """Parse ide2 string -> dict."""
    result = {"type": "none", "volid": ""}
    if not val:
        return result
    if val == "/dev/cdrom,media=cdrom":
        result["type"] = "physical"
        return result
    parts = str(val).split(",")
    result["volid"] = parts[0]
    result["type"] = "iso"
    return result


class VmNetworkEditorDialog(QDialog):
    """Редактирование сетевого устройства (net0, net1, ...)."""
    def __init__(self, key, label, current_value, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Редактирование: {label}")
        self.setMinimumWidth(500)
        self._key = key
        self._parsed = _parse_net(current_value)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel(f"<b>{label}</b>")
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(8)

        # Модель
        self._model_combo = QComboBox()
        for m in NET_MODELS:
            self._model_combo.addItem(m, m)
        idx = self._model_combo.findData(self._parsed["model"])
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)
        form.addRow("Модель:", self._model_combo)

        self._mac_edit = QLineEdit(self._parsed["mac"])
        self._mac_edit.setPlaceholderText("оставьте пустым для авто-назначения")
        form.addRow("MAC:", self._mac_edit)

        self._bridge_combo = QComboBox()
        self._bridge_combo.setEditable(True)
        default_bridges = ["vmbr0", "vmbr1", "vmbr2", "vmbr3", "vmbr99"]
        for b in default_bridges:
            self._bridge_combo.addItem(b, b)
        bridge_val = self._parsed["bridge"]
        idx = self._bridge_combo.findData(bridge_val)
        if idx >= 0:
            self._bridge_combo.setCurrentIndex(idx)
        else:
            self._bridge_combo.setEditText(bridge_val)
        form.addRow("Мост:", self._bridge_combo)

        # VLAN
        self._vlan_spin = QSpinBox()
        self._vlan_spin.setRange(0, 4094)
        self._vlan_spin.setSpecialValueText("Нет")
        try:
            self._vlan_spin.setValue(int(self._parsed["tag"]) if self._parsed["tag"] else 0)
        except ValueError:
            self._vlan_spin.setValue(0)
        form.addRow("VLAN тег:", self._vlan_spin)

        # Очереди
        self._queues_spin = QSpinBox()
        self._queues_spin.setRange(0, 64)
        self._queues_spin.setSpecialValueText("Авто")
        try:
            self._queues_spin.setValue(int(self._parsed["queues"]) if self._parsed["queues"] else 0)
        except ValueError:
            self._queues_spin.setValue(0)
        form.addRow("Очередей:", self._queues_spin)

        layout.addLayout(form)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._ok_btn = QPushButton("Сохранить")
        self._ok_btn.setObjectName("accentBtn")
        self._ok_btn.setFixedWidth(120)
        self._ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self._ok_btn)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setFixedWidth(120)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_ok(self):
        self.accept()

    def get_raw_value(self):
        model = self._model_combo.currentData()
        mac = self._mac_edit.text().strip()
        bridge = self._bridge_combo.currentText().strip()
        tag = self._vlan_spin.value()
        queues = self._queues_spin.value()
        net_val = _build_net(model, mac, bridge,
                             str(tag) if tag > 0 else "",
                             str(queues) if queues > 0 else "")
        return (self._key, net_val)


class VmCdromEditorDialog(QDialog):
    """Редактирование CDROM (ide2)."""
    def __init__(self, key, label, current_value, iso_list=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Редактирование: {label}")
        self.setMinimumWidth(500)
        self._key = key
        self._parsed = _parse_cdrom(current_value)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel(f"<b>{label} — оптический привод</b>")
        layout.addWidget(header)

        # Текущее состояние
        current_label = QLabel()
        if self._parsed["type"] == "physical":
            current_label.setText("Текущее: <b>Физический привод</b>")
        elif self._parsed["type"] == "iso":
            current_label.setText(f"Текущее: <b>{self._parsed['volid']}</b>")
        else:
            current_label.setText("Текущее: <b>Нет носителя</b>")
        layout.addWidget(current_label)

        form = QFormLayout()
        form.setSpacing(8)

        self._iso_combo = QComboBox()
        self._iso_combo.setEditable(True)
        self._iso_combo.addItem("— Нет носителя —", "__none__")
        self._iso_combo.addItem("Физический привод (CD/DVD)", "__cdrom__")
        if iso_list:
            for volid in iso_list:
                fname = volid.split("/")[-1] if "/" in volid else volid
                self._iso_combo.addItem(f"{fname}  ({volid})", volid)
        if self._parsed["volid"]:
            idx = self._iso_combo.findData(self._parsed["volid"])
            if idx >= 0:
                self._iso_combo.setCurrentIndex(idx)
            else:
                self._iso_combo.addItem(str(self._parsed["volid"]), self._parsed["volid"])
                self._iso_combo.setCurrentIndex(self._iso_combo.count() - 1)
        form.addRow("Выбор ISO:", self._iso_combo)

        layout.addLayout(form)

        info = QLabel("ISO-образы загружаются из хранилищ узла. "
                      "Если нужного нет в списке, введите вручную volid.")
        info.setStyleSheet("color: #6b7280; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_layout = QHBoxLayout()
        eject_btn = QPushButton("Извлечь (Eject)")
        eject_btn.clicked.connect(self._on_eject)
        btn_layout.addWidget(eject_btn)
        btn_layout.addStretch()
        self._ok_btn = QPushButton("Сохранить")
        self._ok_btn.setObjectName("accentBtn")
        self._ok_btn.setFixedWidth(120)
        self._ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self._ok_btn)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setFixedWidth(120)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_eject(self):
        self._iso_combo.setCurrentIndex(0)

    def _on_ok(self):
        self.accept()

    def get_raw_value(self):
        data = self._iso_combo.currentData()
        if data == "__none__":
            return (self._key, None)  # remove ide2
        elif data == "__cdrom__":
            return (self._key, "/dev/cdrom,media=cdrom")
        elif data:
            return (self._key, f"{data},media=cdrom")
        return (self._key, None)


class VmDiskEditorDialog(QDialog):
    """Редактирование параметров диска (virtio0, scsi0, ...)."""
    def __init__(self, key, label, current_value, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Редактирование: {label}")
        self.setMinimumWidth(450)
        self._key = key
        self._parsed = _parse_disk(current_value)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel(f"<b>{label}</b>")
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(8)

        # Хранилище (только чтение)
        storage_edit = QLineEdit(self._parsed["storage"])
        storage_edit.setReadOnly(True)
        form.addRow("Хранилище:", storage_edit)

        # Размер (только чтение)
        size_edit = QLineEdit(self._parsed["size"])
        size_edit.setReadOnly(True)
        form.addRow("Размер:", size_edit)

        # Формат (только чтение)
        fmt_edit = QLineEdit(self._parsed["format"])
        fmt_edit.setReadOnly(True)
        if not self._parsed["format"]:
            fmt_edit.setPlaceholderText("qcow2 (по умолчанию)")
        form.addRow("Формат:", fmt_edit)

        # Кэш (редактируемый)
        self._cache_combo = QComboBox()
        for val, label_text in DISK_CACHE:
            self._cache_combo.addItem(label_text, val)
        idx = self._cache_combo.findData(self._parsed["cache"])
        if idx >= 0:
            self._cache_combo.setCurrentIndex(idx)
        form.addRow("Кэш:", self._cache_combo)

        layout.addLayout(form)

        info = QLabel("Размер, хранилище и формат диска нельзя изменить "
                      "через этот интерфейс (требуется создание нового диска).")
        info.setStyleSheet("color: #6b7280; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._ok_btn = QPushButton("Сохранить")
        self._ok_btn.setObjectName("accentBtn")
        self._ok_btn.setFixedWidth(120)
        self._ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self._ok_btn)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setFixedWidth(120)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_ok(self):
        self.accept()

    def get_raw_value(self):
        cache = self._cache_combo.currentData()
        if cache == self._parsed["cache"]:
            return (self._key, None)  # no change
        new_val = f"{self._parsed['storage']}:{self._parsed['size']}"
        parts = []
        if self._parsed["format"]:
            parts.append(f"format={self._parsed['format']}")
        if cache and cache != "none":
            parts.append(f"cache={cache}")
        if parts:
            new_val += "," + ",".join(parts)
        return (self._key, new_val)