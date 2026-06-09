"""
i18n — Lightweight translation module.

All UI strings are written in English and wrapped in tr():
    self.setWindowTitle(tr("Add Server"))

Translations are stored in SQLite (translations table). The module
seeds a built-in RU dictionary on first use with that language.
A new language only requires INSERTs into the translations table.
"""

import logging
import threading

logger = logging.getLogger(__name__)

_current_lang = "en"
_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Built-in RU dictionary — seeds the database on first run with ru
# Extracted from the codebase. Key = English msgid, value = Russian msgstr.
# ---------------------------------------------------------------------------
_RU = {
    # Generic UI
    "Parameter": "Параметр",
    "Value": "Значение",
    "Save": "Сохранить",
    "Cancel": "Отмена",
    "Close": "Закрыть",
    "Add": "Добавить",
    "Delete": "Удалить",
    "Edit": "Редактировать",

    # VM actions
    "Start": "Старт",
    "Shutdown": "Выкл",
    "Stop": "Стоп",
    "Reboot": "Перезагр",
    "Reset": "Сброс",
    "Resume": "Возобн",

    # VM status
    "Running": "Работает",
    "Stopped": "Остановлена",
    "Paused": "Приостановлена",
    "Error": "Ошибка",
    "Offline": "Недоступен",
    "Online": "Доступен",
    "Unknown": "Неизвестно",
    "Mounted": "Подключено",

    # Tabs
    "Monitoring": "Мониторинг",
    "Hardware": "Оборудование",
    "Options": "Параметры",
    "History": "История",
    "Summary": "Сводка",
    "Storage": "Хранилище",
    "Storage Detail": "Сводка хранилища",
    "Backups": "Резервные копии",
    "VM Disks": "Диски ВМ",
    "Templates": "Шаблоны",
    "Network": "Сеть",
    "Services": "Сервисы",
    "Disks": "Диски",
    "Snapshots": "Снапшоты",

    # Config labels (hardware tab)
    "Name": "Имя",
    "CPU Type": "Тип CPU",
    "Cores": "Ядра",
    "Sockets": "Сокеты",
    "Memory": "Память",
    "BIOS": "BIOS",
    "Chipset": "Чипсет",
    "SCSI Controller": "SCSI контроллер",
    "VM Generation ID": "VM Generation ID",
    "OS Type": "Тип ОС",
    "ACPI": "ACPI",
    "QEMU Agent": "QEMU Agent",
    "KVM (nested virt)": "KVM (вложенная виртуализация)",
    "USB Tablet": "USB Tablet",
    "Boot": "Загрузка",
    "Boot Disk": "Загрузочный диск",
    "Start on boot": "Автозапуск",
    "Startup order": "Порядок запуска",
    "NUMA": "NUMA",
    "Hotplug": "Горячее подключение",
    "Freeze (pause at start)": "Freeze (приостановка на старте)",
    "Keyboard layout": "Раскладка клавиатуры",
    "Local time": "Локальное время",
    "Protection": "Защита от удаления",
    "Reboot after crash": "Перезагрузка после сбоя",
    "Tags": "Теги",
    "TDF": "TDF",
    "Template": "Шаблон",
    "Virtual CPUs (hotplug)": "Виртуальных CPU (hotplug)",
    "SPICE": "SPICE",
    "SPICE enhancements": "Улучшения SPICE",
    "Extra QEMU args": "Доп. аргументы QEMU",
    "Hook script": "Скрипт-хук",
    "Chipset (running)": "Чипсет (работает)",
    "EFI Disk": "EFI диск",
    "TPM": "TPM",

    # Device labels
    "Optical drive": "Оптический привод",
    "Hard disk": "Жёсткий диск",

    # CPU type labels
    "KVM64 (compatible)": "KVM64 (совместимый)",
    "Host (max)": "Host (максимум)",
    "QEMU64": "QEMU64",
    "Host (max, risky)": "Host (max, рискованно)",
    "x86-64 v2": "x86-64 v2",
    "x86-64 v2 + AES": "x86-64 v2 + AES",
    "x86-64 v3": "x86-64 v3",
    "x86-64 v3 + AES": "x86-64 v3 + AES",
    "x86-64 v4": "x86-64 v4",
    "x86-64 v4 + AES": "x86-64 v4 + AES",

    # BIOS
    "SeaBIOS": "SeaBIOS",
    "OVMF (UEFI)": "OVMF (UEFI)",

    # VGA
    "VGA (standard)": "VGA (стандартный)",
    "QXL (SPICE)": "QXL (SPICE)",
    "VirtIO-GPU": "VirtIO-GPU",
    "VMware": "VMware",
    "Cirrus": "Cirrus",
    "Serial": "Serial",
    "QXL (dual)": "QXL (двойной)",
    "QXL (triple)": "QXL (тройной)",
    "QXL (quad)": "QXL (четверной)",

    # SCSI
    "LSI 53C895A": "LSI 53C895A",
    "LSI 53C810": "LSI 53C810",
    "MegaSAS": "MegaSAS",
    "VMware PVSCSI": "VMware PVSCSI",
    "VirtIO SCSI Single": "VirtIO SCSI Single",
    "VirtIO SCSI PCI": "VirtIO SCSI PCI",

    # OS types
    "Unspecified": "Не указан",
    "Windows XP": "Windows XP",
    "Windows 2000": "Windows 2000",
    "Windows 2003": "Windows 2003",
    "Windows 2008": "Windows 2008",
    "Windows 2012": "Windows 2012",
    "Windows Vista": "Windows Vista",
    "Windows 7": "Windows 7",
    "Windows 8": "Windows 8",
    "Windows 10/11": "Windows 10/11",
    "Linux 2.4": "Linux 2.4",
    "Linux 2.6+": "Linux 2.6+",
    "Solaris": "Solaris",

    # RTC
    "UTC": "UTC",
    "Local": "Локальное",

    # Keyboard
    "Arabic": "Арабская",
    "Danish": "Датская",
    "German": "Немецкая",
    "Swiss (German)": "Швейцарская (нем.)",
    "English (UK)": "Английская (Великобритания)",
    "English (US)": "Английская (США)",
    "Spanish": "Испанская",
    "Finnish": "Финская",
    "French": "Французская",
    "French (Belgium)": "Французская (Бельгия)",
    "French (Canada)": "Французская (Канада)",
    "French (Switzerland)": "Швейцарская (фр.)",
    "Croatian": "Хорватская",
    "Hungarian": "Венгерская",
    "Icelandic": "Исландская",
    "Italian": "Итальянская",
    "Japanese": "Японская",
    "Lithuanian": "Литовская",
    "Macedonian": "Македонская",
    "Dutch": "Нидерландская",
    "Norwegian": "Норвежская",
    "Polish": "Польская",
    "Portuguese": "Португальская",
    "Portuguese (Brazil)": "Португальская (Бразилия)",
    "Russian": "Русская",
    "Slovak": "Словацкая",
    "Slovenian": "Словенская",
    "Swedish": "Шведская",
    "Turkish": "Турецкая",
    "Ukrainian": "Украинская",

    # Hotplug
    "Disabled": "Отключено",
    "All": "Всё",
    "Network": "Сеть",
    "Disks": "Диски",
    "USB": "USB",
    "Network, Disks": "Сеть, Диски",
    "Network, USB": "Сеть, USB",
    "Disks, USB": "Диски, USB",
    "Network, Disks, USB": "Сеть, Диски, USB",

    # Cache modes
    "None": "Нет",
    "Write back": "Write back",
    "Write through": "Write through",
    "Direct sync": "Direct sync",
    "Unsafe": "Unsafe",

    # Dialog titles / messages
    "Add Server": "Добавить сервер",
    "Edit: ": "Редактирование: ",
    "Delete VM": "Удаление ВМ",
    "Create Virtual Machine": "Создание виртуальной машины",
    "VM Console": "SPICE консоль",
    "Authorization": "Авторизация",
    "Password": "Пароль",
    "Master password": "Мастер-пароль",
    "Enter master password:": "Введите мастер-пароль:",
    "Set master password:": "Установите мастер-пароль для шифрования токенов:",

    # Status bar
    "Hosts": "Хостов",
    "VMs": "ВМ",
    "Updated": "Обновлено",

    # Tree panel sections
    "Clusters": "Кластеры",
    "Standalone hosts": "Отдельные хосты",
    "No servers added.": "Нет добавленных серверов.\nНажмите + чтобы добавить",
    "Expand all": "Развернуть всё",
    "Collapse all": "Свернуть всё",

    # Running VM restrictions
    "Cannot be changed on a running VM": "Этот параметр нельзя изменить на работающей ВМ",
    "Stop the VM to edit": "Остановите ВМ для редактирования",
    "On a running VM only the VLAN tag can be changed": "На работающей ВМ можно изменить только VLAN тег",

    # Network editor
    "Model": "Модель",
    "MAC": "MAC",
    "leave empty for auto-assign": "оставьте пустым для авто-назначения",
    "Bridge": "Мост",
    "VLAN tag": "VLAN тег",
    "Queues": "Очередей",
    "Auto": "Авто",

    # CDROM editor
    "No media": "Нет носителя",
    "Current": "Текущее",
    "Physical drive": "Физический привод",
    "Select ISO": "Выбор ISO",
    "No media —": "— Нет носителя —",
    "Physical drive (CD/DVD)": "Физический привод (CD/DVD)",
    "Eject": "Извлечь (Eject)",
    "ISO images are loaded from node storage": "ISO-образы загружаются из хранилищ узла",

    # Disk editor
    "Storage": "Хранилище",
    "Size": "Размер",
    "Format": "Формат",
    "Cache": "Кэш",
    "Disk size, storage and format cannot be changed here": "Размер, хранилище и формат диска нельзя изменить через этот интерфейс",

    # Boot editor
    "Available devices": "Доступные устройства",
    "Boot order": "Порядок загрузки",
    "Move devices between available and boot order": "Перемещайте устройства между доступными и порядком загрузки",
    "Up": "Вверх",
    "Down": "Вниз",
    "Empty boot order — VM may not boot": "Не выбрано ни одного устройства. ВМ может не загрузиться",

    # Startup editor
    "Startup order and delays": "Порядок и задержки запуска",
    "Order": "Порядок",
    "Start delay": "Задержка запуска",
    "Stop delay": "Задержка остановки",
    "sec": "сек",
    "Not set": "Не задан",
    "Lower number starts earlier": "Чем меньше число, тем раньше запустится ВМ",

    # Action buttons
    "Console": "Консоль",
    "Create VM": "Создать ВМ",
    "Confirm deletion": "Подтверждение удаления",
    "I confirm deletion": "Я подтверждаю удаление",
    "Force stop and delete": "Принудительно остановить и удалить",
    "This action is irreversible": "Это действие необратимо. Все диски ВМ будут удалены.",
    "VM is running!": "ВМ запущена!",
    "It will be forcefully stopped and deleted": "Она будет принудительно остановлена и удалена.",

    # Add server dialog
    "Connection": "Подключение",
    "Host": "Хост",
    "User": "Пользователь",
    "Token": "Токен",
    "Token name": "Имя токена",
    "Token ID": "Имя токена",
    "Token value": "Значение",
    "Node settings": "Настройки узла",
    "Cluster": "Кластер",
    "This is a cluster representative": "Это кластерное представительство",
    "Get token": "Получить токен",
    "Refresh token": "Обновить токен",
    "Connecting...": "Подключение...",
    "Create API token for this user": "Будет создан API-токен для указанного пользователя",
    "auto (first part of host)": "авто (первая часть хоста)",
    "cluster name (required for clusters)": "имя кластера (обязательно для кластеров)",
    "leave empty — standalone host": "оставьте пустым — отдельный хост",
    "Token created": "Токен создан",

    # Create VM dialog
    "General": "Основное",
    "CPU & Memory": "CPU и память",
    "System": "Система",
    "Disk": "Диск",
    "Node": "Узел",
    "VM ID": "VM ID",
    "VM Name": "Имя ВМ",
    "Pool": "Пул",
    "HA group": "HA группа",
    "Memory (MB)": "Память (МБ)",
    "CPU type": "Тип CPU",
    "EFI storage": "EFI хранилище",
    "Size (GB)": "Размер (ГБ)",
    "Bus": "Шина",
    "SCSI": "SCSI",
    "ISO/CDROM": "ISO/CDROM",
    "No media": "Не использовать носители",
    "Bridge": "Мост",
    "VLAN tag": "VLAN тег",
    "Start after creation": "Запустить после создания",
    "QEMU Agent": "QEMU Agent",
    "Create": "Создать",
    "Creating...": "Создание…",
    "host (recommended)": "host (рекомендуется)",
    "No pool": "— нет —",
    "No HA group": "— нет —",

    # Task history table
    "Start time": "Начало",
    "End time": "Окончание",
    "Status": "Статус",
    "User": "Пользователь",
    "Description": "Описание",
    "running...": "выполняется...",
    "OK": "OK",
    "RUNNING": "RUNNING",

    # Cluster tasks table
    "Host node": "Хост",
    "Filter tasks...": "Поиск...",

    # VM summary
    "CPU usage (%)": "Использование ЦП (%)",
    "RAM (GiB)": "RAM (GiB)",
    "Disk (GiB)": "Диск (GiB)",
    "Net in (MB)": "Сеть вх (MB)",
    "Net out (MB)": "Сеть исх (MB)",
    "Uptime": "Аптайм",

    # Host summary
    "Host name": "Хост",
    "Address": "Адрес",
    "CPU %": "ЦП %",
    "Uptime": "Аптайм",

    # Storage summary
    "Name": "Имя",
    "Type": "Тип",
    "Content": "Содержимое",
    "Cluster / Node": "Кластер/Узел",
    "Used": "Занято",
    "Total": "Всего",
    "Usage": "Использование",

    # Storage detail
    "Nodes": "Узлов",
    "Per node": "По узлам",

    # History table (VM)
    "Start": "Начало",
    "End": "Окончание",
    "Status": "Статус",
    "User": "Пользователь",
    "Description": "Описание",

    # Metrics
    "CPU": "ЦП",
    "RAM": "ОЗУ",
    "Metric": "Метрика",
    "Interval": "Интервал",
    "hour": "час",
    "day": "день",
    "week": "неделя",
    "month": "месяц",
    "year": "год",

    # VM pool table
    "Name": "Имя",
    "Type": "Тип",
    "Disk %": "Диск %",
    "RAM %": "ОЗУ %",
    "CPU %": "ЦП %",
    "Uptime": "Аптайм",

    # Host table
    "Virtual Machines": "Виртуальные машины",
    "VM type": "Тип",

    # Error messages
    "Invalid login or password": "Неверный логин или пароль",
    "Cannot connect to ": "Не удалось подключиться к ",
    "PVE API unavailable (connection refused)": "PVE API недоступен (соединение отклонено)",
    "Host not responding (timeout)": "Хост не отвечает (таймаут соединения)",
    "Cannot resolve DNS name": "Не удаётся разрешить DNS-имя хоста",
    "PVE permission denied": "Недостаточно прав PVE",
    "API token authorization error (401)": "Ошибка авторизации API-токена (401)",
    "SPICE not supported for this VM": "SPICE не поддерживается для этой ВМ",
    "PVE permission denied for SPICE (requires VM.Console)": "Недостаточно прав PVE для SPICE (требуется VM.Console)",
    "remote-viewer not found. Install virt-viewer": "remote-viewer не найден. Установите пакет virt-viewer:\n  apt install virt-viewer",

    # Notifications
    "is unavailable": "недоступен",
    "is back online": "снова в сети",
    "is online": "онлайн",
    "parameter changed": "параметр изменён",

    # Config dialog hints
    "Format: model=MAC,bridge=vmbr0,tag=10": "Формат: модель=MAC,bridge=vmbr0,tag=10",
    "Format: storage:size,format=qcow2": "Формат: storage:size,format=qcow2",
    "This parameter cannot be changed via API": "Этот параметр нельзя изменить через API",
    "Read only": "Только чтение",
    "Empty value": "Пустое значение",
    "Are you sure you want to set an empty value?": "Вы уверены, что хотите установить пустое значение?",

    # Storage plot
    "Fill level": "Заполнение",

    # Misc UI
    "Select object in tree": "Выберите объект в дереве",
    "Loading...": "Загрузка...",
    "No data": "Нет данных",
    "Filter": "Поиск",
    "Config": "Конфигурация",
    "Delete host": "Удалить хост",
    "Delete cluster": "Удалить кластер",
    "Remove all hosts from": "Удалить все хосты из",
    "Refresh token": "Создать токен заново",

    # SPICE console
    "SPICE console launched": "SPICE консоль запущена",
    "Opening SPICE console...": "Открытие SPICE консоли...",

    # Boot order
    "Order: ": "Порядок: ",
    "Start delay: ": "Ожидание: ",
    "Stop delay: ": "Остановка: ",
    "Boot order: ": "Порядок: ",
    "second": "с",

    # PVE version
    "PVE version": "Версия PVE",
    "Kernel": "Ядро",

    # Empty states
    "No hosts configured": "Нет настроенных хостов",
    "Loading tasks...": "Загрузка задач...",
    "No tasks": "Нет задач",

    # Disk bus labels for tree
    "IDE": "IDE",
    "SATA": "SATA",
    "SCSI": "SCSI",
    "VirtIO": "VirtIO",
    "Network ": "Сеть ",
}


# ---------------------------------------------------------------------------
# Other UN language dictionaries (minimal — UI terms only)
# These are compact: only the most common UI strings.
# Full translations would be contributed by the community as SQL INSERTs.
# ---------------------------------------------------------------------------

_AR = {
    # UN official language: Arabic
    "Edit: ": "تحرير: ",
    "Save": "حفظ",
    "Cancel": "إلغاء",
    "Start": "بدء",
    "Shutdown": "إيقاف التشغيل",
    "Stop": "إيقاف",
    "Reboot": "إعادة تشغيل",
    "Reset": "إعادة ضبط",
    "Resume": "استئناف",
    "Name": "الاسم",
    "Status": "الحالة",
    "CPU": "المعالج",
    "Memory": "الذاكرة",
    "Disk": "القرص",
    "Network": "الشبكة",
    "Host": "المضيف",
    "Cluster": "المجموعة",
    "Storage": "التخزين",
    "Uptime": "مدة التشغيل",
    "Create": "إنشاء",
    "Delete": "حذف",
    "Add": "إضافة",
    "User": "المستخدم",
    "Password": "كلمة المرور",
    "Error": "خطأ",
    "Online": "متصل",
    "Offline": "غير متصل",
    "Running": "يعمل",
    "Stopped": "متوقف",
    "Unknown": "غير معروف",
}

_ZH = {
    # UN official language: Chinese Simplified
    "Edit: ": "编辑: ",
    "Save": "保存",
    "Cancel": "取消",
    "Start": "启动",
    "Shutdown": "关机",
    "Stop": "停止",
    "Reboot": "重启",
    "Reset": "重置",
    "Resume": "恢复",
    "Name": "名称",
    "Status": "状态",
    "CPU": "CPU",
    "Memory": "内存",
    "Disk": "磁盘",
    "Network": "网络",
    "Host": "主机",
    "Cluster": "集群",
    "Storage": "存储",
    "Uptime": "运行时间",
    "Create": "创建",
    "Delete": "删除",
    "Add": "添加",
    "User": "用户",
    "Password": "密码",
    "Error": "错误",
    "Online": "在线",
    "Offline": "离线",
    "Running": "运行中",
    "Stopped": "已停止",
    "Unknown": "未知",
}

_FR = {
    # UN official language: French
    "Edit: ": "Modifier : ",
    "Save": "Enregistrer",
    "Cancel": "Annuler",
    "Start": "Démarrer",
    "Shutdown": "Arrêter",
    "Stop": "Forcer l'arrêt",
    "Reboot": "Redémarrer",
    "Reset": "Réinitialiser",
    "Resume": "Reprendre",
    "Name": "Nom",
    "Status": "Statut",
    "CPU": "CPU",
    "Memory": "Mémoire",
    "Disk": "Disque",
    "Network": "Réseau",
    "Host": "Hôte",
    "Cluster": "Cluster",
    "Storage": "Stockage",
    "Uptime": "Disponibilité",
    "Create": "Créer",
    "Delete": "Supprimer",
    "Add": "Ajouter",
    "User": "Utilisateur",
    "Password": "Mot de passe",
    "Error": "Erreur",
    "Online": "En ligne",
    "Offline": "Hors ligne",
    "Running": "En cours",
    "Stopped": "Arrêté",
    "Unknown": "Inconnu",
}

_ES = {
    # UN official language: Spanish
    "Edit: ": "Editar: ",
    "Save": "Guardar",
    "Cancel": "Cancelar",
    "Start": "Iniciar",
    "Shutdown": "Apagar",
    "Stop": "Detener",
    "Reboot": "Reiniciar",
    "Reset": "Restablecer",
    "Resume": "Reanudar",
    "Name": "Nombre",
    "Status": "Estado",
    "CPU": "CPU",
    "Memory": "Memoria",
    "Disk": "Disco",
    "Network": "Red",
    "Host": "Host",
    "Cluster": "Cluster",
    "Storage": "Almacenamiento",
    "Uptime": "Tiempo activo",
    "Create": "Crear",
    "Delete": "Eliminar",
    "Add": "Agregar",
    "User": "Usuario",
    "Password": "Contraseña",
    "Error": "Error",
    "Online": "En línea",
    "Offline": "Fuera de línea",
    "Running": "Ejecutando",
    "Stopped": "Detenido",
    "Unknown": "Desconocido",
}

# Map of language codes to their built-in dictionaries
_BUILTIN = {
    "ru": _RU,
    "ar": _AR,
    "zh": _ZH,
    "fr": _FR,
    "es": _ES,
}


_SUPPORTED_LANGUAGES = {
    "en": "English",
    "ru": "Русский",
    "ar": "العربية",
    "zh": "中文",
    "fr": "Français",
    "es": "Español",
}


def set_language(lang: str):
    """Set current language (e.g. 'en', 'ru').
    Seeds built-in translations into DB on first use for non-English languages.
    """
    global _current_lang
    _current_lang = lang
    if lang in _BUILTIN:
        from ..config import seed_translations
        seed_translations(lang, _BUILTIN[lang])
    logger.info("Language set to %s", lang)


def get_language() -> str:
    return _current_lang


def supported_languages() -> dict[str, str]:
    """Return dict of language code -> native name."""
    return dict(_SUPPORTED_LANGUAGES)


def tr(text: str) -> str:
    """Translate a string to the current language.
    Falls back to the original English text if no translation exists.
    """
    if _current_lang == "en":
        return text
    if _current_lang in _BUILTIN:
        return _BUILTIN[_current_lang].get(text, text)
    return text


def get_builtin_dict(lang: str) -> dict:
    """Return the embedded dictionary for a language, or empty dict."""
    return dict(_BUILTIN.get(lang, {}))
