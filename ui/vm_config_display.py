"""
vm_config_display.py — Human-readable VM config display.

PVE API returns only modified (non-default) values from config endpoint.
This module fills in known defaults and translates values to human-readable
Russian labels and formatted strings.
"""
# Labels for config keys (Russian)
HW_LABELS = {
    "name": "Имя",
    "cpu": "Тип CPU",
    "cores": "Ядра",
    "sockets": "Сокеты",
    "memory": "Память",
    "bios": "BIOS",
    "machine": "Чипсет",
    "vga": "VGA",
    "scsihw": "SCSI контроллер",
    "vmgenid": "VM Generation ID",
    "ostype": "Тип ОС",
    "acpi": "ACPI",
    "agent": "QEMU Agent",
    "kvm": "KVM (вложенная виртуализация)",
    "tablet": "USB Tablet",
    "boot": "Загрузка",
    "bootdisk": "Загрузочный диск",
    "onboot": "Автозапуск",
    "startup": "Порядок запуска",
    "numa": "NUMA",
    "hotplug": "Горячее подключение",
    "freeze": "Freeze (приостановка на старте)",
    "keyboard": "Раскладка клавиатуры",
    "localtime": "Локальное время",
    "protection": "Защита от удаления",
    "reboot": "Перезагрузка после сбоя",
    "rtc": "RTC",
    "smbios1": "SMBIOS",
    "tags": "Теги",
    "tdf": "TDF",
    "template": "Шаблон",
    "vcpus": "Виртуальных CPU (hotplug)",
    "spice": "SPICE",
    "spice_enhancements": "Улучшения SPICE",
    "args": "Доп. аргументы QEMU",
    "hookscript": "Скрипт-хук",
    "running-machine": "Чипсет (работает)",
    "efidisk0": "EFI диск",
    "tpmstate0": "TPM",
}

_DEVICE_PREFIX_LABELS = {
    "net": "Сеть",
    "ide": "IDE",
    "sata": "SATA",
    "scsi": "SCSI",
    "virtio": "Жёсткий диск",
    "efidisk": "EFI диск",
    "tpmstate": "TPM",
}


def _device_label(key):
    prefix = key.rstrip("0123456789")
    num = key[len(prefix):]
    base = _DEVICE_PREFIX_LABELS.get(prefix, prefix)
    if prefix == "ide" and num == "2":
        return "Оптический привод"
    if prefix in ("virtio", "scsi", "sata", "ide"):
        if num:
            return f"{base} ({prefix}{num})"
        return base
    if num:
        return f"{base} {num}"
    return base


CHOICE_LABELS = {
    "cpu": {
        "kvm64": "KVM64 (совместимый)",
        "host": "Host (максимум)",
        "qemu64": "QEMU64",
        "max": "Host (max, рискованно)",
        "x86-64-v2": "x86-64 v2",
        "x86-64-v2-AES": "x86-64 v2 + AES",
        "x86-64-v3": "x86-64 v3",
        "x86-64-v3-AES": "x86-64 v3 + AES",
        "x86-64-v4": "x86-64 v4",
        "x86-64-v4-AES": "x86-64 v4 + AES",
    },
    "bios": {
        "seabios": "SeaBIOS",
        "ovmf": "OVMF (UEFI)",
    },
    "machine": {
        "i440fx": "i440fx",
        "q35": "Q35",
    },
    "vga": {
        "std": "VGA (стандартный)",
        "qxl": "QXL (SPICE)",
        "virtio": "VirtIO-GPU",
        "vmware": "VMware",
        "cirrus": "Cirrus",
        "serial0": "Serial",
        "qxl2": "QXL (двойной)",
        "qxl3": "QXL (тройной)",
        "qxl4": "QXL (четверной)",
    },
    "scsihw": {
        "lsi": "LSI 53C895A",
        "lsi53c810": "LSI 53C810",
        "megasas": "MegaSAS",
        "pvscsi": "VMware PVSCSI",
        "virtio-scsi-single": "VirtIO SCSI Single",
        "virtio-scsi-pci": "VirtIO SCSI PCI",
    },
    "ostype": {
        "other": "Не указан",
        "wxp": "Windows XP",
        "w2k": "Windows 2000",
        "w2k3": "Windows 2003",
        "w2k8": "Windows 2008",
        "w2k12": "Windows 2012",
        "wvista": "Windows Vista",
        "win7": "Windows 7",
        "win8": "Windows 8",
        "win10": "Windows 10/11",
        "l24": "Linux 2.4",
        "l26": "Linux 2.6+",
        "solaris": "Solaris",
    },
    "rtc": {
        "utc": "UTC",
        "localtime": "Локальное",
    },
    "keyboard": {
        "ar": "Арабская",
        "da": "Датская",
        "de": "Немецкая",
        "de-ch": "Швейцарская (нем.)",
        "en-gb": "Английская (Великобритания)",
        "en-us": "Английская (США)",
        "es": "Испанская",
        "fi": "Финская",
        "fr": "Французская",
        "fr-be": "Французская (Бельгия)",
        "fr-ca": "Французская (Канада)",
        "fr-ch": "Швейцарская (фр.)",
        "hr": "Хорватская",
        "hu": "Венгерская",
        "is": "Исландская",
        "it": "Итальянская",
        "ja": "Японская",
        "lt": "Литовская",
        "mk": "Македонская",
        "nl": "Нидерландская",
        "no": "Норвежская",
        "pl": "Польская",
        "pt": "Португальская",
        "pt-br": "Португальская (Бразилия)",
        "ru": "Русская",
        "sk": "Словацкая",
        "sl": "Словенская",
        "sv": "Шведская",
        "tr": "Турецкая",
        "ua": "Украинская",
    },
    "hotplug": {
        "0": "Отключено",
        "1": "Всё",
        "network": "Сеть",
        "disk": "Диски",
        "usb": "USB",
        "network,disk": "Сеть, Диски",
        "network,usb": "Сеть, USB",
        "disk,usb": "Диски, USB",
        "network,disk,usb": "Сеть, Диски, USB",
        "networkdisk,usb": "Сеть, Диски, USB",
    },
}

# Device keys that can be edited as raw strings
_EDITABLE_DEVICE_PREFIXES = {"net", "ide", "sata", "scsi", "virtio", "efidisk", "tpmstate"}


def _key_prefix(key):
    return key.rstrip("0123456789")


def is_net_key(key):
    return _key_prefix(key) == "net"


def is_cdrom_key(key):
    return key == "ide2"


def is_disk_key(key):
    pfx = _key_prefix(key)
    return pfx in ("virtio", "scsi", "sata") or (pfx == "ide" and key != "ide2")

# PVE defaults for keys absent from config API (hardware tab)
HW_DEFAULTS = {
    "cores": 1,
    "sockets": 1,
    "memory": 512,
    "cpu": "kvm64",
    "bios": "seabios",
    "machine": "i440fx",
    "vga": "std",
    "scsihw": "lsi",
}

# PVE defaults for keys absent from config API (options tab)
OPT_DEFAULTS = {
    "ostype": "l26",
    "acpi": 1,
    "agent": 0,
    "spice": 0,
    "spice_enhancements": 0,
    "kvm": 1,
    "tablet": 1,
    "keyboard": "en-us",
    "boot": "order=ide2;ide0;scsi0;virtio0;net0",
    "onboot": 0,
    "numa": 0,
    "hotplug": "networkdisk,usb",
    "freeze": 0,
    "localtime": 0,
    "protection": 0,
    "reboot": 1,
    "rtc": "utc",
    "tdf": 0,
    "template": 0,
    "smbios1": "type=1,uuid=auto",
    "vcpus": 0,
}

# Config keys not shown in either tab
SERVICE_KEYS = {
    "digest", "description", "meta",
    "hookscript", "parent", "template",
    "searchdomain", "hostname", "password", "sshkeys",
    "ciuser", "cipassword", "cicustom",
    "running-machine", "running-qemu", "vmgenid",
}

# Editor type and choices for each editable config key
# Types: bool, int, string, choice (with choices list), readonly
FIELD_TYPES = {
    "name": "string",
    "cpu": ("choice", [
        "kvm64", "host", "qemu64", "max",
        "x86-64-v2", "x86-64-v2-AES",
        "x86-64-v3", "x86-64-v3-AES",
        "x86-64-v4", "x86-64-v4-AES",
    ]),
    "cores": "int",
    "sockets": "int",
    "memory": "int",
    "bios": ("choice", ["seabios", "ovmf"]),
    "machine": ("choice", ["i440fx", "q35"]),
    "vga": ("choice", ["std", "qxl", "virtio", "vmware", "cirrus", "serial0", "qxl2", "qxl3", "qxl4"]),
    "scsihw": ("choice", ["lsi", "lsi53c810", "megasas", "pvscsi", "virtio-scsi-single", "virtio-scsi-pci"]),
    "ostype": ("choice", [
        "other", "wxp", "w2k", "w2k3", "w2k8", "w2k12",
        "wvista", "win7", "win8", "win10",
        "l24", "l26", "solaris",
    ]),
    "acpi": "bool",
    "agent": "bool",
    "spice": "bool",
    "spice_enhancements": "bool",
    "kvm": "bool",
    "tablet": "bool",
    "onboot": "bool",
    "numa": "bool",
    "freeze": "bool",
    "localtime": "bool",
    "protection": "bool",
    "reboot": "bool",
    "tdf": "bool",
    "boot": "string",
    "bootdisk": "string",
    "hotplug": ("choice", ["0", "1", "network", "disk", "usb", "network,disk", "network,usb", "disk,usb", "networkdisk,usb"]),
    "startup": "string",
    "rtc": ("choice", ["utc", "localtime"]),
    "keyboard": ("choice", [
        "ar", "da", "de", "de-ch", "en-gb", "en-us",
        "es", "fi", "fr", "fr-be", "fr-ca", "fr-ch",
        "hr", "hu", "is", "it", "ja", "lt", "mk",
        "nl", "no", "pl", "pt", "pt-br", "ru",
        "sk", "sl", "sv", "tr", "ua",
    ]),
    "smbios1": "string",
    "tags": "string",
    "vcpus": "int",
    "args": "string",
}

# Reverse map: from raw PVE value to form widget value
FIELD_REVERSE = {
    "bool": lambda v: v in (1, "1", True),
}

# Ordered groups for options tab
_OPT_SECTIONS = [
    ("os",           ["ostype"]),
    ("boot",         ["boot", "bootdisk", "startup", "onboot"]),
    ("video",        ["vga", "spice", "spice_enhancements", "tablet", "keyboard"]),
    ("system",       ["acpi", "kvm", "numa", "tdf", "rtc", "localtime"]),
    ("hotplug",      ["hotplug", "vcpus"]),
    ("behaviour",    ["agent", "freeze", "protection", "reboot"]),
    ("misc",         ["tags", "smbios1", "args"]),
]

_HW_SECTIONS = [
    ("identity",       ["name"]),
    ("cpu",            ["cpu", "cores", "sockets"]),
    ("memory",         ["memory"]),
    ("system",         ["bios", "machine", "vga", "scsihw"]),
    ("network",        [f"net{i}" for i in range(32)]),
    ("storage",        [f"ide{i}" for i in range(4)] +
                        [f"sata{i}" for i in range(6)] +
                        [f"scsi{i}" for i in range(31)] +
                        [f"virtio{i}" for i in range(16)] +
                        ["efidisk0", "tpmstate0"]),
]

# Formatter helpers
# ---------------------------------------------------------------------------

def _fmt_memory(val):
    try:
        mb = int(val)
        if mb >= 1024:
            gb = mb / 1024
            if mb % 1024 == 0:
                return f"{mb // 1024} ГБ"
            return f"{gb:.1f} ГБ ({mb} МБ)"
        return f"{mb} МБ"
    except (ValueError, TypeError):
        return str(val)


def _fmt_ostype(val):
    return {
        "other": "Не указан",
        "wxp": "Windows XP",
        "w2k": "Windows 2000",
        "w2k3": "Windows 2003",
        "w2k8": "Windows 2008",
        "w2k12": "Windows 2012",
        "wvista": "Windows Vista",
        "win7": "Windows 7",
        "win8": "Windows 8",
        "win10": "Windows 10/11",
        "l24": "Linux 2.4",
        "l26": "Linux 2.6+",
        "solaris": "Solaris",
    }.get(str(val), str(val))


def _fmt_bool(val):
    return "Да" if val in (1, "1", True) else "Нет"


def _fmt_agent(val):
    return "Включён" if val in (1, "1", True) else "Выключен"


def _fmt_boot(val):
    val = str(val)
    if val.startswith("order="):
        parts = val[6:].split(";")
        return "Порядок: " + ", ".join(parts)
    if val == "cdn":
        return "CDN (сеть)"
    return val


def _fmt_hotplug(val):
    return {
        "networkdisk,usb": "Сеть, Диски, USB",
        "network,disk,usb": "Сеть, Диски, USB",
        "network,disk": "Сеть, Диски",
        "network,usb": "Сеть, USB",
        "disk,usb": "Диски, USB",
        "network": "Сеть",
        "disk": "Диски",
        "usb": "USB",
        "1": "Всё",
        "0": "Отключено",
    }.get(val, val)


def _fmt_startup(val):
    parts = str(val).split(",")
    out = []
    for p in parts:
        if p.startswith("order="):
            out.append(f"Порядок: {p[6:]}")
        elif p.startswith("up="):
            out.append(f"Ожидание: {p[3:]}с")
        elif p.startswith("down="):
            out.append(f"Остановка: {p[5:]}с")
    return " | ".join(out) if out else str(val)


def _fmt_keyboard(val):
    return {
        "ar": "Арабская", "da": "Датская", "de": "Немецкая",
        "de-ch": "Швейцарская (нем.)", "en-gb": "Английская (Великобритания)",
        "en-us": "Английская (США)", "es": "Испанская", "fi": "Финская",
        "fr": "Французская", "fr-be": "Французская (Бельгия)",
        "fr-ca": "Французская (Канада)", "fr-ch": "Швейцарская (фр.)",
        "hr": "Хорватская", "hu": "Венгерская", "is": "Исландская",
        "it": "Итальянская", "ja": "Японская", "lt": "Литовская",
        "mk": "Македонская", "nl": "Нидерландская", "no": "Норвежская",
        "pl": "Польская", "pt": "Португальская",
        "pt-br": "Португальская (Бразилия)", "ru": "Русская",
        "sk": "Словацкая", "sl": "Словенская", "sv": "Шведская",
        "tr": "Турецкая", "ua": "Украинская",
    }.get(val, val)


def _fmt_cpu(val):
    val = str(val)
    if val.startswith("custom-"):
        return f"x86-64 {val[7:]} (PVE custom)"
    return {
        "kvm64": "KVM64 (совместимый)",
        "host": "Host (максимум)",
        "qemu64": "QEMU64",
        "x86-64-v2": "x86-64 v2",
        "x86-64-v2-AES": "x86-64 v2 + AES",
        "x86-64-v3": "x86-64 v3",
        "x86-64-v3-AES": "x86-64 v3 + AES",
        "x86-64-v4": "x86-64 v4",
        "x86-64-v4-AES": "x86-64 v4 + AES",
        "max": "Host (max, рискованно)",
    }.get(val, val)


def _fmt_scsihw(val):
    return {
        "lsi": "LSI 53C895A",
        "lsi53c810": "LSI 53C810",
        "megasas": "MegaSAS",
        "pvscsi": "VMware PVSCSI",
        "virtio-scsi-single": "VirtIO SCSI Single",
        "virtio-scsi-pci": "VirtIO SCSI PCI",
    }.get(val, val)


def _fmt_vga(val):
    return {
        "std": "VGA",
        "qxl": "QXL (SPICE)",
        "virtio": "VirtIO-GPU",
        "vmware": "VMware",
        "cirrus": "Cirrus",
        "serial0": "Serial",
        "qxl2": "QXL (dual)",
        "qxl3": "QXL (triple)",
        "qxl4": "QXL (quad)",
    }.get(val, val)


def _fmt_bios(val):
    return {"seabios": "SeaBIOS", "ovmf": "OVMF (UEFI)"}.get(val, val)


def _fmt_machine(val):
    return {"i440fx": "i440fx", "q35": "Q35"}.get(val, val) if val else val


def _fmt_rtc(val):
    return {"utc": "UTC", "localtime": "Локальное"}.get(val, val)


def _fmt_smbios(val):
    parts = str(val).split(",")
    filtered = [p for p in parts if not p.startswith("uuid=")]
    return ", ".join(filtered) if filtered else "Задан"


def _fmt_vcpus(val):
    return str(val) if val not in (0, "0") else "Не задано"


def _fmt_net(val):
    """Распарсить строку сетевого устройства: virtio=MAC,bridge=vmbr0,tag=10"""
    val = str(val)
    parts = val.split(",")
    first = parts[0]

    if "=" in first:
        model, mac = first.split("=", 1)
    else:
        model, mac = first, ""

    bridge = ""
    tag = ""
    for p in parts[1:]:
        if p.startswith("bridge="):
            bridge = p.split("=", 1)[1]
        elif p.startswith("tag="):
            tag = p.split("=", 1)[1]

    out = model
    if bridge:
        out += f" | {bridge}"
    if tag:
        out += f" | VLAN {tag}"
    if mac and mac != "none":
        out += f" | {mac}"
    return out


def _fmt_disk(val):
    """Распарсить строку диска: storage:size,format=qcow2,cache=writeback,..."""
    val = str(val)
    parts = val.split(",")
    storage_part = parts[0]

    if ":" in storage_part:
        storage = storage_part.split(":")[0]
        size = storage_part.split(":", 1)[1]
    else:
        storage = storage_part
        size = ""

    fmt = ""
    cache = ""
    for p in parts[1:]:
        if p.startswith("cache="):
            cache = p.split("=", 1)[1]
        elif p.startswith("format="):
            fmt = p.split("=", 1)[1]

    _cache_labels = {"none": "Нет", "writeback": "Write back",
                     "writethrough": "Write through",
                     "directsync": "Direct sync", "unsafe": "Unsafe"}
    cache = _cache_labels.get(cache, cache)

    out = storage
    if size:
        out += f" | {size}"
    if fmt:
        out += f" | {fmt}"
    if cache:
        out += f" | Кэш: {cache}"
    return out


# Formatter registry: key prefix -> callable(value) -> str
_FORMATTERS = {
    "memory": _fmt_memory,
    "ostype": _fmt_ostype,
    "acpi": _fmt_bool,
    "spice": _fmt_bool,
    "spice_enhancements": _fmt_bool,
    "kvm": _fmt_bool,
    "tablet": _fmt_bool,
    "onboot": _fmt_bool,
    "numa": _fmt_bool,
    "freeze": _fmt_bool,
    "localtime": _fmt_bool,
    "protection": _fmt_bool,
    "reboot": _fmt_bool,
    "tdf": _fmt_bool,
    "template": _fmt_bool,
    "agent": _fmt_agent,
    "boot": _fmt_boot,
    "hotplug": _fmt_hotplug,
    "startup": _fmt_startup,
    "rtc": _fmt_rtc,
    "keyboard": _fmt_keyboard,
    "cpu": _fmt_cpu,
    "scsihw": _fmt_scsihw,
    "vga": _fmt_vga,
    "bios": _fmt_bios,
    "machine": _fmt_machine,
    "smbios1": _fmt_smbios,
    "vcpus": _fmt_vcpus,
    "sockets": str,
    "cores": str,
}

# Disk and network device prefixes
_DISK_PREFIXES = {"ide", "sata", "scsi", "virtio", "efidisk", "tpmstate"}
_NET_PREFIXES = {"net"}


def format_value(key, value):
    if key in _FORMATTERS:
        return _FORMATTERS[key](value)
    prefix = key.rstrip("0123456789")
    if prefix in _DISK_PREFIXES:
        return _fmt_disk(value)
    if prefix in _NET_PREFIXES:
        return _fmt_net(value)
    return str(value)


def get_editor_spec(key):
    """Return (field_type, choices, display_labels) for a config key."""
    if key in FIELD_TYPES:
        spec = FIELD_TYPES[key]
        if isinstance(spec, tuple):
            ft, choices = spec[0], spec[1]
            labels = CHOICE_LABELS.get(key, {})
            return (ft, choices, labels)
        return (spec, None, None)
    prefix = key.rstrip("0123456789")
    if prefix in _EDITABLE_DEVICE_PREFIXES:
        return ("string", None, None)
    return ("readonly", None, None)


# Public API
# ---------------------------------------------------------------------------


def get_hardware_rows(config_data, detail_data=None):
    config = dict(config_data) if config_data else {}
    for key, default in HW_DEFAULTS.items():
        if key not in config:
            config[key] = default
    rows = []
    seen = set()
    for _section_name, keys in _HW_SECTIONS:
        for key in keys:
            if key in config:
                seen.add(key)
                label = HW_LABELS.get(key) or _device_label(key)
                value = format_value(key, config[key])
                rows.append((key, label, value))
    if detail_data:
        rm = detail_data.get("running-machine")
        if rm:
            label = HW_LABELS.get("running-machine", "running-machine")
            rows.append(("running-machine", label, rm))
    return rows


def get_options_rows(config_data):
    config = dict(config_data) if config_data else {}
    for key, default in OPT_DEFAULTS.items():
        if key not in config:
            config[key] = default
    hw_keys = set()
    for _section_name, keys in _HW_SECTIONS:
        for key in keys:
            hw_keys.add(key)
    opt_keys = set()
    for _section_name, keys in _OPT_SECTIONS:
        for key in keys:
            opt_keys.add(key)
    # Collect extra keys not in any section
    extra = set()
    for key in config:
        if key not in hw_keys and key not in SERVICE_KEYS and key not in opt_keys:
            extra.add(key)
    rows = []
    for _section_name, keys in _OPT_SECTIONS:
        for key in keys:
            if key in config:
                label = HW_LABELS.get(key) or _device_label(key)
                formatted = format_value(key, config[key])
                rows.append((key, label, formatted))
    for key in sorted(extra):
        label = HW_LABELS.get(key) or _device_label(key)
        formatted = format_value(key, config[key])
        rows.append((key, label, formatted))
    return rows