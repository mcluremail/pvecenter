from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QLineEdit, QPushButton, QCheckBox,
                               QComboBox, QSpinBox, QScrollArea,
                               QWidget, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from ..config import save_ui_state, load_ui_state
import json as _json

VM_SETTINGS_KEY = "create_vm_settings"

# ── Статические константы ─────────────────────────────────────────

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

VGA_TYPES = [
    ("qxl", "qxl (SPICE)"),
    ("std", "std"),
    ("virtio", "virtio"),
    ("vmware", "vmware"),
    ("cirrus", "cirrus"),
    ("serial0", "serial0"),
    ("qxl2", "qxl2 (dual)"),
    ("qxl3", "qxl3 (triple)"),
    ("qxl4", "qxl4 (quad)"),
]

SCSI_CONTROLLERS = [
    ("virtio-scsi-single", "VirtIO SCSI Single"),
    ("virtio-scsi-pci", "VirtIO SCSI PCI"),
    ("megasas", "MegaSAS"),
    ("pvscsi", "VMware PVSCSI"),
    ("lsi", "LSI (legacy)"),
    ("lsi53c810", "LSI 53C810"),
]

DISK_CACHE = [
    ("none", "No cache"),
    ("writeback", "Write back"),
    ("writethrough", "Write through"),
    ("directsync", "Direct sync"),
    ("unsafe", "Unsafe"),
]

CPU_TYPES = [
    ("host", "host (рекомендуется)"),
    ("custom-x86-64-v2-AES", "x86-64-v2-AES"),
    ("custom-x86-64-v3", "x86-64-v3"),
    ("custom-x86-64-v4", "x86-64-v4"),
    ("kvm64", "kvm64"),
    ("qemu64", "qemu64"),
    ("max", "max"),
    ("EPYC", "AMD EPYC"),
    ("EPYC-Rome", "AMD EPYC Rome"),
    ("EPYC-Milan", "AMD EPYC Milan"),
    ("EPYC-Genoa", "AMD EPYC Genoa"),
    ("Nehalem", "Intel Nehalem"),
    ("Westmere", "Intel Westmere"),
    ("SandyBridge", "Intel SandyBridge"),
    ("IvyBridge", "Intel IvyBridge"),
    ("Haswell", "Intel Haswell"),
    ("Broadwell", "Intel Broadwell"),
    ("Skylake-Client", "Intel Skylake"),
    ("Skylake-Server", "Intel Skylake Server"),
    ("Cascadelake-Server", "Intel Cascade Lake"),
]

DISK_BUSES = ["virtio", "scsi", "sata", "ide"]
NET_MODELS = ["virtio", "e1000", "rtl8139", "vmxnet3"]

CHIPSETS = [
    ("q35", "q35"),
    ("i440fx", "i440fx"),
]

BIOS_TYPES = [
    ("seabios", "SeaBIOS"),
    ("ovmf", "OVMF (UEFI)"),
]


def _fmt_size(bytes_val):
    """Форматирует размер в байтах в человекочитаемый вид."""
    try:
        b = int(bytes_val)
    except (TypeError, ValueError):
        return "?"
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if abs(b) < 1024:
            return f"{b}{unit}"
        b //= 1024
    return f"{b}ТБ"


class CreateVmDialog(QDialog):
    def __init__(self, parent=None, nodes=None, storages=None, pools=None, iso_images=None, ha_groups=None):
        super().__init__(parent)
        self.setWindowTitle("Создание виртуальной машины")
        self.setMinimumSize(700, 400)
        self.setMaximumWidth(780)
        self._nodes = nodes or []
        # Кластеры — первыми, затем standalone; внутри групп — по алфавиту
        self._nodes = sorted(nodes or [], key=lambda n: (not n.get("_is_cluster", False),
                                        (n.get("_display_name") or n.get("node", "")).lower()))
        self._storages = storages or []
        self._pools = pools or []
        self._iso_images = iso_images or {}
        self._ha_groups = ha_groups or {}
        self._build_ui()
        self._restore_settings()

    def _save_settings(self):
        data = {
            "cores": self.cores_spin.value(),
            "sockets": self.sockets_spin.value(),
            "memory": self.memory_spin.value(),
            "ostype": self.ostype_combo.currentIndex(),
            "cpu": self.cpu_combo.currentIndex(),
            "vga": self.vga_combo.currentIndex(),
            "chipset": self.chipset_combo.currentIndex(),
            "bios": self.bios_combo.currentIndex(),
            "scsi": self.scsi_combo.currentIndex(),
            "bus": self.bus_combo.currentIndex(),
            "cache": self.cache_combo.currentIndex(),
            "disk_size": self.disk_size_spin.value(),
            "model": self.model_combo.currentIndex(),
            "queues": self.queues_spin.value(),
            "start": int(self.start_check.isChecked()),
            "agent": int(self.agent_check.isChecked()),
        }
        save_ui_state(VM_SETTINGS_KEY, _json.dumps(data))

    def _restore_settings(self):
        raw = load_ui_state(VM_SETTINGS_KEY)
        if not raw:
            return
        try:
            data = _json.loads(raw)
        except (TypeError, ValueError):
            return
        if data.get("cores"):
            self.cores_spin.setValue(data["cores"])
        if data.get("sockets"):
            self.sockets_spin.setValue(data["sockets"])
        if data.get("memory"):
            self.memory_spin.setValue(data["memory"])
        if data.get("ostype"):
            self.ostype_combo.setCurrentIndex(data["ostype"])
        if data.get("cpu"):
            self.cpu_combo.setCurrentIndex(data["cpu"])
        if data.get("vga"):
            self.vga_combo.setCurrentIndex(data["vga"])
        if data.get("chipset"):
            self.chipset_combo.setCurrentIndex(data["chipset"])
        if data.get("bios"):
            self.bios_combo.setCurrentIndex(data["bios"])
        if data.get("scsi"):
            self.scsi_combo.setCurrentIndex(data["scsi"])
        if data.get("bus"):
            self.bus_combo.setCurrentIndex(data["bus"])
        if data.get("cache"):
            self.cache_combo.setCurrentIndex(data["cache"])
        if data.get("disk_size"):
            self.disk_size_spin.setValue(data["disk_size"])
        if data.get("model"):
            self.model_combo.setCurrentIndex(data["model"])
        if data.get("queues"):
            self.queues_spin.setValue(data["queues"])
        if data.get("start") is not None:
            self.start_check.setChecked(bool(data["start"]))
        if data.get("agent") is not None:
            self.agent_check.setChecked(bool(data["agent"]))

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll-область
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        form = QVBoxLayout(content)
        form.setContentsMargins(20, 16, 20, 16)
        form.setSpacing(0)

        # ── Разметка полей: helper ──
        def _grid():
            g = QGridLayout()
            g.setVerticalSpacing(10)
            g.setHorizontalSpacing(12)
            g.setContentsMargins(0, 0, 0, 0)
            return g

        def _add_row(g, row, label, widget, col_span=1):
            lbl = QLabel(label)
            lbl.setObjectName("fieldLabel")
            g.addWidget(lbl, row, 0, Qt.AlignRight | Qt.AlignVCenter)
            g.addWidget(widget, row, 1, 1, col_span)

        def _sep(form):
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setFrameShadow(QFrame.Sunken)
            sep.setObjectName("sectionSep")
            form.addWidget(sep)
            form.addSpacing(6)

        # ================================================================
        #  1. Основное
        # ================================================================
        title1 = QLabel("Основное")
        title1.setObjectName("sectionTitle")
        form.addWidget(title1)
        form.addSpacing(8)

        g1 = _grid()
        g1.addWidget(QLabel("Узел:"), 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.node_combo = QComboBox()
        for n in self._nodes:
            label = n.get("_display_name") or n.get("node", "?")
            self.node_combo.addItem(label, n.get("node", ""))
        self.node_combo.currentIndexChanged.connect(self._on_node_changed)
        g1.addWidget(self.node_combo, 0, 1)
        g1.addWidget(QLabel("VM ID:"), 0, 2, Qt.AlignRight | Qt.AlignVCenter)
        self.vmid_line = QLineEdit()
        self.vmid_line.setPlaceholderText("авто")
        self.vmid_line.setValidator(QIntValidator(100, 999999999, self))
        self.vmid_line.setFixedWidth(120)
        g1.addWidget(self.vmid_line, 0, 3)

        g1.addWidget(QLabel("Имя ВМ:"), 1, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("my-vm")
        g1.addWidget(self.name_input, 1, 1, 1, 3)

        g1.addWidget(QLabel("Тип ОС:"), 2, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.ostype_combo = QComboBox()
        for val, label in VM_OS_TYPES:
            self.ostype_combo.addItem(label, val)
        self.ostype_combo.setCurrentIndex(1)
        g1.addWidget(self.ostype_combo, 2, 1)
        g1.addWidget(QLabel("Пул:"), 2, 2, Qt.AlignRight | Qt.AlignVCenter)
        self.pool_combo = QComboBox()
        self.pool_combo.addItem("— нет —", "")
        for p in self._pools:
            pid = p.get("poolid", "")
            self.pool_combo.addItem(pid, pid)
        g1.addWidget(self.pool_combo, 2, 3)

        self.ha_label = QLabel("HA группа:")
        g1.addWidget(self.ha_label, 3, 2, Qt.AlignRight | Qt.AlignVCenter)
        self.ha_combo = QComboBox()
        self.ha_label.setVisible(False)
        self.ha_combo.setVisible(False)
        g1.addWidget(self.ha_combo, 3, 3)

        form.addLayout(g1)
        form.addSpacing(18)

        # ================================================================
        #  2. CPU и память
        # ================================================================
        _sep(form)

        title2 = QLabel("CPU и память")
        title2.setObjectName("sectionTitle")
        form.addWidget(title2)
        form.addSpacing(8)

        g2 = _grid()
        g2.addWidget(QLabel("Ядер:"), 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.cores_spin = QSpinBox()
        self.cores_spin.setRange(1, 128)
        self.cores_spin.setValue(2)
        g2.addWidget(self.cores_spin, 0, 1)
        g2.addWidget(QLabel("Сокетов:"), 0, 2, Qt.AlignRight | Qt.AlignVCenter)
        self.sockets_spin = QSpinBox()
        self.sockets_spin.setRange(1, 16)
        self.sockets_spin.setValue(1)
        g2.addWidget(self.sockets_spin, 0, 3)

        g2.addWidget(QLabel("Память (МБ):"), 1, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.memory_spin = QSpinBox()
        self.memory_spin.setRange(16, 4194304)
        self.memory_spin.setValue(2048)
        self.memory_spin.setSingleStep(256)
        g2.addWidget(self.memory_spin, 1, 1)

        g2.addWidget(QLabel("Тип CPU:"), 2, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.cpu_combo = QComboBox()
        for val, label in CPU_TYPES:
            self.cpu_combo.addItem(label, val)
        self.cpu_combo.setCurrentIndex(0)
        g2.addWidget(self.cpu_combo, 2, 1, 1, 3)

        form.addLayout(g2)
        form.addSpacing(18)

        # ================================================================
        #  3. Система
        # ================================================================
        _sep(form)

        title3 = QLabel("Система")
        title3.setObjectName("sectionTitle")
        form.addWidget(title3)
        form.addSpacing(8)

        g3 = _grid()
        g3.addWidget(QLabel("VGA:"), 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.vga_combo = QComboBox()
        for val, label in VGA_TYPES:
            self.vga_combo.addItem(label, val)
        self.vga_combo.setCurrentIndex(0)
        g3.addWidget(self.vga_combo, 0, 1)
        g3.addWidget(QLabel("Чипсет:"), 0, 2, Qt.AlignRight | Qt.AlignVCenter)
        self.chipset_combo = QComboBox()
        for val, label in CHIPSETS:
            self.chipset_combo.addItem(label, val)
        self.chipset_combo.setCurrentIndex(0)
        g3.addWidget(self.chipset_combo, 0, 3)

        g3.addWidget(QLabel("BIOS:"), 1, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.bios_combo = QComboBox()
        for val, label in BIOS_TYPES:
            self.bios_combo.addItem(label, val)
        self.bios_combo.setCurrentIndex(0)
        self.bios_combo.currentTextChanged.connect(self._on_bios_changed)
        g3.addWidget(self.bios_combo, 1, 1)
        self.efi_label = QLabel("EFI хранилище:")
        self.efi_label.setVisible(False)
        g3.addWidget(self.efi_label, 1, 2, Qt.AlignRight | Qt.AlignVCenter)
        self.efi_storage_combo = QComboBox()
        self.efi_storage_combo.setVisible(False)
        g3.addWidget(self.efi_storage_combo, 1, 3)

        form.addLayout(g3)
        form.addSpacing(18)

        # ================================================================
        #  4. Диск
        # ================================================================
        _sep(form)

        title4 = QLabel("Диск")
        title4.setObjectName("sectionTitle")
        form.addWidget(title4)
        form.addSpacing(8)

        g4 = _grid()
        g4.addWidget(QLabel("Хранилище:"), 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.storage_combo = QComboBox()
        g4.addWidget(self.storage_combo, 0, 1)
        g4.addWidget(QLabel("Размер (ГБ):"), 0, 2, Qt.AlignRight | Qt.AlignVCenter)
        self.disk_size_spin = QSpinBox()
        self.disk_size_spin.setRange(1, 1048576)
        self.disk_size_spin.setValue(32)
        g4.addWidget(self.disk_size_spin, 0, 3)

        g4.addWidget(QLabel("Шина:"), 1, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.bus_combo = QComboBox()
        for bus in DISK_BUSES:
            self.bus_combo.addItem(bus, bus)
        g4.addWidget(self.bus_combo, 1, 1)
        self.scsi_label = QLabel("SCSI:")
        g4.addWidget(self.scsi_label, 1, 2, Qt.AlignRight | Qt.AlignVCenter)
        self.scsi_combo = QComboBox()
        for val, label in SCSI_CONTROLLERS:
            self.scsi_combo.addItem(label, val)
        self.scsi_combo.setCurrentIndex(0)
        g4.addWidget(self.scsi_combo, 1, 3)

        g4.addWidget(QLabel("Кэш:"), 2, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.cache_combo = QComboBox()
        for val, label in DISK_CACHE:
            self.cache_combo.addItem(label, val)
        self.cache_combo.setCurrentIndex(0)
        g4.addWidget(self.cache_combo, 2, 1)

        g4.addWidget(QLabel("ISO/CDROM:"), 2, 2, Qt.AlignRight | Qt.AlignVCenter)
        self.iso_combo = QComboBox()
        self.iso_combo.addItem("Не использовать носители", "")
        self.iso_combo.setMinimumWidth(200)
        g4.addWidget(self.iso_combo, 2, 3)

        form.addLayout(g4)
        form.addSpacing(18)

        # ================================================================
        #  5. Сеть
        # ================================================================
        _sep(form)

        title5 = QLabel("Сеть")
        title5.setObjectName("sectionTitle")
        form.addWidget(title5)
        form.addSpacing(8)

        g5 = _grid()
        g5.addWidget(QLabel("Мост:"), 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.bridge_input = QLineEdit("vmbr0")
        g5.addWidget(self.bridge_input, 0, 1)
        g5.addWidget(QLabel("Модель:"), 0, 2, Qt.AlignRight | Qt.AlignVCenter)
        self.model_combo = QComboBox()
        for m in NET_MODELS:
            self.model_combo.addItem(m, m)
        g5.addWidget(self.model_combo, 0, 3)

        g5.addWidget(QLabel("VLAN tag:"), 1, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.vlan_input = QLineEdit()
        self.vlan_input.setPlaceholderText("0 — без VLAN")
        self.vlan_input.setValidator(QIntValidator(0, 4094))
        g5.addWidget(self.vlan_input, 1, 1)
        g5.addWidget(QLabel("Очередей:"), 1, 2, Qt.AlignRight | Qt.AlignVCenter)
        self.queues_spin = QSpinBox()
        self.queues_spin.setRange(0, 64)
        self.queues_spin.setValue(0)
        self.queues_spin.setSpecialValueText("авто")
        g5.addWidget(self.queues_spin, 1, 3)

        form.addLayout(g5)
        form.addSpacing(18)

        # ── Футер ──
        footer = QHBoxLayout()
        self.start_check = QCheckBox("Запустить после создания")
        self.start_check.setChecked(False)
        footer.addWidget(self.start_check)
        self.agent_check = QCheckBox("QEMU Agent")
        self.agent_check.setChecked(True)
        footer.addWidget(self.agent_check)
        footer.addStretch()

        self.create_btn = QPushButton("Создать")
        self.create_btn.setFixedWidth(120)
        self.create_btn.setObjectName("accentBtn")
        self.create_btn.clicked.connect(self._on_create)
        footer.addWidget(self.create_btn)

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.clicked.connect(self.reject)
        footer.addWidget(self.cancel_btn)

        form.addLayout(footer)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Заполняем storage/EFI под первый узел
        self._on_node_changed(0)

    # ── Слоты ──────────────────────────────────────────────────────

    def _on_node_changed(self, idx):
        node = self.node_combo.currentData()
        if not node:
            return
        # Оставляем только storage, доступные на этом узле
        node_storages = [s for s in self._storages if s.get("node") == node]
        if not node_storages:
            node_storages = self._storages

        def _fill(combo):
            combo.clear()
            seen = set()
            for s in node_storages:
                name = s.get("storage", "")
                if name not in seen:
                    seen.add(name)
                    combo.addItem(name, name)

        _fill(self.storage_combo)
        _fill(self.efi_storage_combo)

        # Выбираем первый storage, поддерживающий диски ВМ (content содержит "images")
        for i in range(self.storage_combo.count()):
            name = self.storage_combo.itemText(i)
            if any(
                "images" in (s.get("content", "") or "").split(",")
                for s in node_storages if s.get("storage") == name
            ):
                self.storage_combo.setCurrentIndex(i)
                break

        # ISO-образы для выбранного узла
        self._populate_iso_combo(node)

        # HA группы — только для хоста, которому принадлежит узел
        host_name = None
        for n in self._nodes:
            if n.get("node") == node:
                host_name = n.get("host_name")
                break
        self._update_ha_combo(host_name)

    def _on_bios_changed(self, text):
        is_ovmf = text == "OVMF (UEFI)"
        self.efi_label.setVisible(is_ovmf)
        self.efi_storage_combo.setVisible(is_ovmf)
        if is_ovmf and self.chipset_combo.currentData() != "q35":
            self.chipset_combo.setCurrentIndex(0)  # q35 для UEFI

    def _populate_iso_combo(self, node):
        """Заполнить комбобокс ISO образами, доступными на узле."""
        self.iso_combo.clear()
        self.iso_combo.addItem("Не использовать носители", "")
        self.iso_combo.addItem("Физический привод", "__cdrom__")
        if node:
            for iso in self._iso_images.get(node, []):
                volid = iso["volid"]
                fname = volid.split("/")[-1]
                fmt = iso.get("format", "")
                sz_str = _fmt_size(iso.get("size", 0))
                details = []
                if fmt:
                    details.append(fmt)
                if sz_str not in ("?", "0 Б"):
                    details.append(sz_str)
                display = f"{fname}  ({', '.join(details)})" if details else fname
                self.iso_combo.addItem(display, volid)

    def _update_ha_combo(self, host_name):
        """Заполнить комбобокс HA группами для указанного хоста."""
        groups = self._ha_groups.get(host_name, []) if host_name else []
        visible = bool(groups)
        self.ha_label.setVisible(visible)
        self.ha_combo.setVisible(visible)
        self.ha_combo.clear()
        self.ha_combo.addItem("— нет —", "")
        for g in groups:
            self.ha_combo.addItem(g, g)

    def _on_create(self):
        self._save_settings()
        name = self.name_input.text().strip()
        if not name:
            self.name_input.setFocus()
            self.name_input.setStyleSheet("border: 1px solid #ef4444;")
            return
        self.name_input.setStyleSheet("")
        self.create_btn.setEnabled(False)
        self.create_btn.setText("Создание…")
        self.accept()

    # ── Параметры для API ──────────────────────────────────────────

    def get_params(self):
        """Возвращает dict параметров для POST /nodes/{node}/qemu."""
        name = self.name_input.text().strip()
        vmid_text = self.vmid_line.text().strip()
        vmid = int(vmid_text) if vmid_text else 0
        bus = self.bus_combo.currentData()
        slot = 0
        disk_key = f"{bus}{slot}"
        size_gb = self.disk_size_spin.value()
        storage = self.storage_combo.currentData()
        cache = self.cache_combo.currentData()
        disk_val = f"{storage}:{size_gb}" if storage else f"local-lvm:{size_gb}"
        if cache and cache != "none":
            disk_val += f",cache={cache}"

        # Сеть: model=XXX,bridge=YYY [,tag=ZZZ]
        bridge = self.bridge_input.text().strip() or "vmbr0"
        model = self.model_combo.currentData()
        net_parts = [f"model={model},bridge={bridge}"]
        vlan = self.vlan_input.text().strip()
        if vlan:
            try:
                vlan_int = int(vlan)
                if vlan_int > 0:
                    net_parts.append(f"tag={vlan_int}")
            except ValueError:
                pass
        queues = self.queues_spin.value()
        if queues:
            net_parts.append(f"queues={queues}")
        net_val = ",".join(net_parts)

        params = {
            "name": name,
            "ostype": self.ostype_combo.currentData(),
            "cores": self.cores_spin.value(),
            "sockets": self.sockets_spin.value(),
            "memory": self.memory_spin.value(),
            "cpu": self.cpu_combo.currentData(),
            "vga": self.vga_combo.currentData(),
            "machine": self.chipset_combo.currentData(),
            disk_key: disk_val,
            "net0": net_val,
            "start": int(self.start_check.isChecked()),
            "agent": int(self.agent_check.isChecked()),
        }

        # SCSI контроллер (всегда, иначе PVE 8+ ставит LSI 53C895A по умолчанию)
        params["scsihw"] = self.scsi_combo.currentData()

        # BIOS (ovmf / seabios)
        bios_val = self.bios_combo.currentData()
        if bios_val != "seabios":
            params["bios"] = bios_val

        # EFI для UEFI
        if bios_val == "ovmf":
            efi_stor = self.efi_storage_combo.currentText()
            if efi_stor:
                params["efidisk0"] = f"{efi_stor}:4,efitype=4m,format=raw"

        # ISO
        iso = self.iso_combo.currentData()
        if iso:
            if iso == "__cdrom__":
                params["ide2"] = "/dev/cdrom,media=cdrom"
            else:
                params["ide2"] = f"{iso},media=cdrom"

        # Пул
        pool = self.pool_combo.currentData()
        if pool:
            params["pool"] = pool

        # VM ID (0 = авто)
        if vmid > 0:
            params["vmid"] = vmid

        # Убираем None-значения и пустые строки (чтобы не слать лишнего)
        params = {k: v for k, v in params.items() if v is not None and v != ""}

        return params

    def get_node(self):
        return self.node_combo.currentData()

    def get_ha_group(self):
        return self.ha_combo.currentData()
