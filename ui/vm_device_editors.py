import re
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QLineEdit, QSpinBox, QComboBox,
                               QFormLayout, QMessageBox, QGroupBox,
                               QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt
from .i18n import tr


NET_MODELS = ["virtio", "e1000", "rtl8139", "vmxnet3"]

DISK_CACHE = [
    ("none", tr("None")),
    ("writeback", tr("Write back")),
    ("writethrough", tr("Write through")),
    ("directsync", tr("Direct sync")),
    ("unsafe", tr("Unsafe")),
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
    def __init__(self, key, label, current_value, running=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Edit: ") + label)
        self.setMinimumWidth(500)
        self._key = key
        self._parsed = _parse_net(current_value)
        self._running = running

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel(f"<b>{label}</b>")
        layout.addWidget(header)

        if running:
            warn = QLabel(tr("On a running VM only the VLAN tag can be changed"))
            warn.setStyleSheet("color: #d97706; font-size: 11px;")
            warn.setWordWrap(True)
            layout.addWidget(warn)

        form = QFormLayout()
        form.setSpacing(8)

        self._model_combo = QComboBox()
        for m in NET_MODELS:
            self._model_combo.addItem(m, m)
        idx = self._model_combo.findData(self._parsed["model"])
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)
        self._model_combo.setEnabled(not running)
        form.addRow(tr("Model:"), self._model_combo)

        self._mac_edit = QLineEdit(self._parsed["mac"])
        self._mac_edit.setPlaceholderText(tr("leave empty for auto-assign"))
        self._mac_edit.setReadOnly(True)
        form.addRow(tr("MAC:"), self._mac_edit)

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
        self._bridge_combo.setEnabled(not running)
        form.addRow(tr("Bridge:"), self._bridge_combo)

        self._vlan_spin = QSpinBox()
        self._vlan_spin.setRange(0, 4094)
        self._vlan_spin.setSpecialValueText(tr("None"))
        try:
            self._vlan_spin.setValue(int(self._parsed["tag"]) if self._parsed["tag"] else 0)
        except ValueError:
            self._vlan_spin.setValue(0)
        form.addRow(tr("VLAN tag:"), self._vlan_spin)

        self._queues_spin = QSpinBox()
        self._queues_spin.setRange(0, 64)
        self._queues_spin.setSpecialValueText(tr("Auto"))
        try:
            self._queues_spin.setValue(int(self._parsed["queues"]) if self._parsed["queues"] else 0)
        except ValueError:
            self._queues_spin.setValue(0)
        form.addRow(tr("Queues:"), self._queues_spin)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._ok_btn = QPushButton(tr("Save"))
        self._ok_btn.setObjectName("accentBtn")
        self._ok_btn.setFixedWidth(120)
        self._ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self._ok_btn)
        cancel_btn = QPushButton(tr("Cancel"))
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
    """CDROM (ide2) editor."""
    def __init__(self, key, label, current_value, iso_list=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Edit: ") + label)
        self.setMinimumWidth(500)
        self._key = key
        self._parsed = _parse_cdrom(current_value)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel(f"<b>{label} — {tr('Optical drive')}</b>")
        layout.addWidget(header)

        current_label = QLabel()
        if self._parsed["type"] == "physical":
            current_label.setText(tr("Current:") + f" <b>{tr('Physical drive')}</b>")
        elif self._parsed["type"] == "iso":
            current_label.setText(tr("Current:") + f" <b>{self._parsed['volid']}</b>")
        else:
            current_label.setText(tr("Current:") + f" <b>{tr('No media')}</b>")
        layout.addWidget(current_label)

        form = QFormLayout()
        form.setSpacing(8)

        self._iso_combo = QComboBox()
        self._iso_combo.setEditable(True)
        self._iso_combo.addItem(tr("No media —"), "__none__")
        self._iso_combo.addItem(tr("Physical drive (CD/DVD)"), "__cdrom__")
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
        form.addRow(tr("Select ISO:"), self._iso_combo)

        layout.addLayout(form)

        info = QLabel(tr("ISO images are loaded from node storage"))
        info.setStyleSheet("color: #6b7280; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_layout = QHBoxLayout()
        eject_btn = QPushButton(tr("Eject"))
        eject_btn.clicked.connect(self._on_eject)
        btn_layout.addWidget(eject_btn)
        btn_layout.addStretch()
        self._ok_btn = QPushButton(tr("Save"))
        self._ok_btn.setObjectName("accentBtn")
        self._ok_btn.setFixedWidth(120)
        self._ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self._ok_btn)
        cancel_btn = QPushButton(tr("Cancel"))
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
            return (self._key, None)
        elif data == "__cdrom__":
            return (self._key, "/dev/cdrom,media=cdrom")
        elif data:
            return (self._key, f"{data},media=cdrom")
        return (self._key, None)


class VmDiskEditorDialog(QDialog):
    """Disk parameter editor (virtio0, scsi0, ...)."""
    def __init__(self, key, label, current_value, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Edit: ") + label)
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

        storage_edit = QLineEdit(self._parsed["storage"])
        storage_edit.setReadOnly(True)
        form.addRow(tr("Storage:"), storage_edit)

        size_edit = QLineEdit(self._parsed["size"])
        size_edit.setReadOnly(True)
        form.addRow(tr("Size:"), size_edit)

        fmt_edit = QLineEdit(self._parsed["format"])
        fmt_edit.setReadOnly(True)
        if not self._parsed["format"]:
            fmt_edit.setPlaceholderText("qcow2 (default)")
        form.addRow(tr("Format:"), fmt_edit)

        self._cache_combo = QComboBox()
        for val, label_text in DISK_CACHE:
            self._cache_combo.addItem(label_text, val)
        idx = self._cache_combo.findData(self._parsed["cache"])
        if idx >= 0:
            self._cache_combo.setCurrentIndex(idx)
        form.addRow(tr("Cache:"), self._cache_combo)

        layout.addLayout(form)

        info = QLabel(tr("Disk size, storage and format cannot be changed here"))
        info.setStyleSheet("color: #6b7280; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._ok_btn = QPushButton(tr("Save"))
        self._ok_btn.setObjectName("accentBtn")
        self._ok_btn.setFixedWidth(120)
        self._ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self._ok_btn)
        cancel_btn = QPushButton(tr("Cancel"))
        cancel_btn.setFixedWidth(120)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_ok(self):
        self.accept()

    def get_raw_value(self):
        cache = self._cache_combo.currentData()
        if cache == self._parsed["cache"]:
            return (self._key, None)
        new_val = f"{self._parsed['storage']}:{self._parsed['size']}"
        parts = []
        if self._parsed["format"]:
            parts.append(f"format={self._parsed['format']}")
        if cache and cache != "none":
            parts.append(f"cache={cache}")
        if parts:
            new_val += "," + ",".join(parts)
        return (self._key, new_val)


class VmBootEditorDialog(QDialog):
    _DEVICE_TYPES = ("ide", "sata", "scsi", "virtio", "net")

    def __init__(self, key, label, current_value, config_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Edit: ") + label)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self._key = key
        self._config_data = config_data or {}

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel(f"<b>{label}</b>")
        layout.addWidget(header)

        info = QLabel(tr("Move devices between available and boot order"))
        info.setStyleSheet("color: #6b7280; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        avail_label = QLabel(tr("Available devices:"))
        avail_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(avail_label)
        self._avail = QListWidget()
        self._avail.itemDoubleClicked.connect(self._to_order)
        layout.addWidget(self._avail)

        move_row = QHBoxLayout()
        to_order_btn = QPushButton(">")
        to_order_btn.setFixedWidth(40)
        to_order_btn.clicked.connect(self._add_selected)
        move_row.addWidget(to_order_btn)
        to_avail_btn = QPushButton("<")
        to_avail_btn.setFixedWidth(40)
        to_avail_btn.clicked.connect(self._remove_selected)
        move_row.addWidget(to_avail_btn)
        move_row.addStretch()
        layout.addLayout(move_row)

        order_label = QLabel(tr("Boot order:"))
        order_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(order_label)
        self._order = QListWidget()
        self._order.itemDoubleClicked.connect(self._to_avail)
        layout.addWidget(self._order)

        order_btn_row = QHBoxLayout()
        up_btn = QPushButton(tr("Up"))
        up_btn.setFixedWidth(80)
        up_btn.clicked.connect(self._move_up)
        order_btn_row.addWidget(up_btn)
        down_btn = QPushButton(tr("Down"))
        down_btn.setFixedWidth(80)
        down_btn.clicked.connect(self._move_down)
        order_btn_row.addWidget(down_btn)
        order_btn_row.addStretch()
        layout.addLayout(order_btn_row)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton(tr("Save"))
        ok_btn.setObjectName("accentBtn")
        ok_btn.setFixedWidth(120)
        ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(ok_btn)
        cancel_btn = QPushButton(tr("Cancel"))
        cancel_btn.setFixedWidth(120)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self._fill(current_value)

    def _collect_devices(self):
        devices = set()
        for key in (self._config_data or {}):
            for pfx in self._DEVICE_TYPES:
                if key.startswith(pfx):
                    devices.add(key)
        return sorted(devices)

    def _fill(self, val):
        raw = str(val or "")
        if raw.startswith("order="):
            order_parts = [p.strip() for p in raw[6:].split(";") if p.strip()]
        elif raw:
            order_parts = [p.strip() for p in raw.split(";") if p.strip()]
        else:
            order_parts = []
        order_set = set(order_parts)
        for d in order_parts:
            self._order.addItem(QListWidgetItem(d))
        for d in self._collect_devices():
            if d not in order_set:
                self._avail.addItem(QListWidgetItem(d))

    def _add_selected(self):
        item = self._avail.currentItem()
        if item:
            self._to_order(item)

    def _remove_selected(self):
        item = self._order.currentItem()
        if item:
            self._to_avail(item)

    def _to_order(self, item):
        self._order.addItem(QListWidgetItem(item.text()))
        self._avail.takeItem(self._avail.row(item))

    def _to_avail(self, item):
        self._avail.addItem(QListWidgetItem(item.text()))
        self._order.takeItem(self._order.row(item))

    def _move_up(self):
        r = self._order.currentRow()
        if r > 0:
            it = self._order.takeItem(r)
            self._order.insertItem(r - 1, it)
            self._order.setCurrentRow(r - 1)

    def _move_down(self):
        r = self._order.currentRow()
        if r >= 0 and r < self._order.count() - 1:
            it = self._order.takeItem(r)
            self._order.insertItem(r + 1, it)
            self._order.setCurrentRow(r + 1)

    def _on_ok(self):
        if self._order.count() == 0:
            ret = QMessageBox.question(
                self, tr("Empty boot order"),
                tr("Empty boot order — VM may not boot") + "\n" + tr("Continue?"),
                QMessageBox.Yes | QMessageBox.No
            )
            if ret != QMessageBox.Yes:
                return
        self.accept()

    def get_raw_value(self):
        parts = [self._order.item(i).text() for i in range(self._order.count())]
        return (self._key, f"order={';'.join(parts)}")


class VmBootdiskEditorDialog(QDialog):
    _DEVICE_TYPES = ("ide", "sata", "scsi", "virtio", "net", "efidisk")

    def __init__(self, key, label, current_value, config_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Edit: ") + label)
        self.setMinimumWidth(400)
        self._key = key

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel(f"<b>{label} — {tr('Boot Disk')}</b>")
        layout.addWidget(header)

        devices = set()
        for k in (config_data or {}):
            for pfx in self._DEVICE_TYPES:
                if k.startswith(pfx):
                    devices.add(k)

        self._combo = QComboBox()
        self._combo.addItem(tr("— none —"), "")
        for d in sorted(devices):
            self._combo.addItem(d, d)
        idx = self._combo.findData(str(current_value or ""))
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        else:
            self._combo.setEditText(str(current_value or ""))
        form = QFormLayout()
        form.addRow(tr("Device:"), self._combo)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton(tr("Save"))
        ok_btn.setObjectName("accentBtn")
        ok_btn.setFixedWidth(120)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        cancel_btn = QPushButton(tr("Cancel"))
        cancel_btn.setFixedWidth(120)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_raw_value(self):
        val = self._combo.currentData()
        return (self._key, val if val else None)


class VmStartupEditorDialog(QDialog):
    def __init__(self, key, label, current_value, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Edit: ") + label)
        self.setMinimumWidth(400)
        self._key = key

        parsed = {"order": "", "up": "", "down": ""}
        if current_value:
            for part in str(current_value).split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    parsed[k] = v

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel(f"<b>{label} — {tr('Startup order and delays')}</b>")
        layout.addWidget(header)

        form = QFormLayout()

        self._order_spin = QSpinBox()
        self._order_spin.setRange(0, 9999)
        self._order_spin.setSpecialValueText(tr("Not set"))
        try:
            self._order_spin.setValue(int(parsed.get("order", 0) or 0))
        except ValueError:
            self._order_spin.setValue(0)
        form.addRow(tr("Order:"), self._order_spin)

        self._up_spin = QSpinBox()
        self._up_spin.setRange(0, 99999)
        self._up_spin.setSuffix(" " + tr("sec"))
        self._up_spin.setSpecialValueText(tr("Not set"))
        try:
            self._up_spin.setValue(int(parsed.get("up", 0) or 0))
        except ValueError:
            self._up_spin.setValue(0)
        form.addRow(tr("Start delay:"), self._up_spin)

        self._down_spin = QSpinBox()
        self._down_spin.setRange(0, 99999)
        self._down_spin.setSuffix(" " + tr("sec"))
        self._down_spin.setSpecialValueText(tr("Not set"))
        try:
            self._down_spin.setValue(int(parsed.get("down", 0) or 0))
        except ValueError:
            self._down_spin.setValue(0)
        form.addRow(tr("Stop delay:"), self._down_spin)

        layout.addLayout(form)

        info = QLabel(tr("Lower number starts earlier"))
        info.setStyleSheet("color: #6b7280; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton(tr("Save"))
        ok_btn.setObjectName("accentBtn")
        ok_btn.setFixedWidth(120)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        cancel_btn = QPushButton(tr("Cancel"))
        cancel_btn.setFixedWidth(120)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_raw_value(self):
        parts = []
        if self._order_spin.value() > 0:
            parts.append(f"order={self._order_spin.value()}")
        if self._up_spin.value() > 0:
            parts.append(f"up={self._up_spin.value()}")
        if self._down_spin.value() > 0:
            parts.append(f"down={self._down_spin.value()}")
        return (self._key, ",".join(parts) if parts else None)
