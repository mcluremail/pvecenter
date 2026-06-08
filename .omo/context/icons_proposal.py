"""
Предложение по редизайну иконок — готовые замены для ui/icons.py
Формат идентичен текущему: SVG-строки с плейсхолдерами {c} и {c2}
_C  = "#4b5563"  (основной цвет)
_C2 = "#374151"  (вторичный/акцент)

Для применения: заменить соответствующие константы в ui/icons.py
"""

# =============================================================================
# ДЕРЕВО — иконки объектов (16×16 viewBox)
# =============================================================================

# Cluster: hub-and-spoke топология, симметричная (было: 3 прямоугольника)
_CLUSTER = """<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
<circle cx="8" cy="8" r="2" fill="{c2}" stroke="{c}" stroke-width="1.2"/>
<circle cx="3" cy="3.5" r="1.5" fill="none" stroke="{c}" stroke-width="1.2"/>
<circle cx="13" cy="3.5" r="1.5" fill="none" stroke="{c}" stroke-width="1.2"/>
<circle cx="3" cy="12.5" r="1.5" fill="none" stroke="{c}" stroke-width="1.2"/>
<circle cx="13" cy="12.5" r="1.5" fill="none" stroke="{c}" stroke-width="1.2"/>
<line x1="8" y1="6" x2="4.1" y2="4.6" stroke="{c}" stroke-width="1"/>
<line x1="8" y1="6" x2="11.9" y2="4.6" stroke="{c}" stroke-width="1"/>
<line x1="8" y1="10" x2="4.1" y2="11.4" stroke="{c}" stroke-width="1"/>
<line x1="8" y1="10" x2="11.9" y2="11.4" stroke="{c}" stroke-width="1"/>
</svg>"""

# Host: rack unit с индикатором (было: прямоугольник с полосками = похож на Disk)
_HOST = """<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
<rect x="2" y="2" width="12" height="12" rx="1" fill="none" stroke="{c}" stroke-width="1.4"/>
<rect x="4" y="4" width="5" height="1.5" rx="0.5" fill="{c}"/>
<rect x="4" y="7" width="8" height="1.5" rx="0.5" fill="{c}"/>
<rect x="4" y="10" width="3" height="1.5" rx="0.5" fill="{c2}"/>
<circle cx="12.5" cy="4.75" r="1.2" fill="{c2}"/>
</svg>"""

# VM: монитор с >_ (терминальный курсор)
_VM = """<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
<rect x="1" y="2" width="14" height="9" rx="1" fill="none" stroke="{c}" stroke-width="1.4"/>
<polyline points="3,8 5,6.5 3,5" fill="none" stroke="{c}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
<line x1="6.5" y1="8" x2="9" y2="8" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<rect x="5.5" y="11" width="5" height="1" rx="0" fill="{c}"/>
<line x1="4" y1="13" x2="12" y2="13" stroke="{c}" stroke-width="1.4" stroke-linecap="round"/>
</svg>"""

# Pool: папка с маленьким монитором (было: три одинаковых прямоугольника)
_POOL = """<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
<path d="M1 5 L4.5 5 L6 3 L15 3 L15 13 L1 13 Z" fill="none" stroke="{c}" stroke-width="1.3" stroke-linejoin="round"/>
<rect x="5" y="7" width="6" height="4" rx="0.5" fill="none" stroke="{c}" stroke-width="1"/>
<line x1="7" y1="11" x2="9" y2="11" stroke="{c}" stroke-width="1"/>
</svg>"""

# Storage: цилиндр — было: прямоугольник с секциями
_STORAGE = """<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
<ellipse cx="8" cy="4" rx="6" ry="2" fill="none" stroke="{c}" stroke-width="1.3"/>
<line x1="2" y1="4" x2="2" y2="12" stroke="{c}" stroke-width="1.3"/>
<line x1="14" y1="4" x2="14" y2="12" stroke="{c}" stroke-width="1.3"/>
<ellipse cx="8" cy="12" rx="6" ry="2" fill="none" stroke="{c}" stroke-width="1.3"/>
<circle cx="11" cy="12" r="1" fill="{c2}"/>
</svg>"""


# =============================================================================
# ВКЛАДКИ ДЕТАЛЕЙ (14×14 viewBox)
# =============================================================================

# Hardware: микросхема (IC) — было: прямоугольник с полосками = неотличим от Disk/Host
_HARDWARE = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg">
<rect x="4" y="4" width="6" height="6" rx="0.5" fill="none" stroke="{c}" stroke-width="1.3"/>
<line x1="5" y1="4" x2="5" y2="2" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<line x1="7" y1="4" x2="7" y2="2" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<line x1="9" y1="4" x2="9" y2="2" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<line x1="5" y1="10" x2="5" y2="12" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<line x1="7" y1="10" x2="7" y2="12" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<line x1="9" y1="10" x2="9" y2="12" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<line x1="4" y1="6" x2="2" y2="6" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<line x1="4" y1="8" x2="2" y2="8" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<line x1="10" y1="6" x2="12" y2="6" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<line x1="10" y1="8" x2="12" y2="8" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<circle cx="7" cy="7" r="1" fill="{c2}"/>
</svg>"""

# Options: три горизонтальных слайдера — было: 4 прямоугольника непонятного смысла
# ВАЖНО: цвет #1f2937 — фон панели, чтобы кружок "прорезал" линию.
# Если тема светлая — заменить на цвет фона.
_OPTIONS = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg">
<line x1="1" y1="3" x2="13" y2="3" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<line x1="1" y1="7" x2="13" y2="7" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<line x1="1" y1="11" x2="13" y2="11" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<circle cx="9" cy="3" r="1.8" fill="#1f2937" stroke="{c}" stroke-width="1.3"/>
<circle cx="4" cy="7" r="1.8" fill="#1f2937" stroke="{c}" stroke-width="1.3"/>
<circle cx="10" cy="11" r="1.8" fill="#1f2937" stroke="{c}" stroke-width="1.3"/>
</svg>"""

# Network: звезда, симметричная — было: асимметричная диагональная линия
_NETWORK = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg">
<circle cx="7" cy="7" r="1.5" fill="{c2}" stroke="{c}" stroke-width="1"/>
<circle cx="2.5" cy="3" r="1.5" fill="none" stroke="{c}" stroke-width="1.2"/>
<circle cx="11.5" cy="3" r="1.5" fill="none" stroke="{c}" stroke-width="1.2"/>
<circle cx="7" cy="12" r="1.5" fill="none" stroke="{c}" stroke-width="1.2"/>
<line x1="7" y1="5.5" x2="3.7" y2="4.2" stroke="{c}" stroke-width="1"/>
<line x1="7" y1="5.5" x2="10.3" y2="4.2" stroke="{c}" stroke-width="1"/>
<line x1="7" y1="8.5" x2="7" y2="10.5" stroke="{c}" stroke-width="1"/>
</svg>"""

# Services: список с точками — было: неотличимо от Pool
_SERVICES = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg">
<line x1="5" y1="3" x2="12" y2="3" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<line x1="5" y1="7" x2="12" y2="7" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<line x1="5" y1="11" x2="12" y2="11" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<circle cx="2.5" cy="3" r="1.2" fill="{c}"/>
<circle cx="2.5" cy="7" r="1.2" fill="{c}"/>
<circle cx="2.5" cy="11" r="1.2" fill="{c2}"/>
</svg>"""

# Snapshot: фотоаппарат
_SNAPSHOT = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg">
<rect x="1" y="4" width="12" height="9" rx="1" fill="none" stroke="{c}" stroke-width="1.3"/>
<path d="M4 4 L5 2 L9 2 L10 4" fill="none" stroke="{c}" stroke-width="1.2" stroke-linejoin="round"/>
<circle cx="7" cy="8.5" r="2.5" fill="none" stroke="{c}" stroke-width="1.2"/>
<circle cx="7" cy="8.5" r="1" fill="{c2}"/>
</svg>"""

# Backup: документ со стрелкой вниз — было: похоже на Template
_BACKUP = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg">
<rect x="2" y="1" width="10" height="12" rx="1" fill="none" stroke="{c}" stroke-width="1.3"/>
<line x1="4.5" y1="4" x2="9.5" y2="4" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<line x1="4.5" y1="6.5" x2="9.5" y2="6.5" stroke="{c2}" stroke-width="1" stroke-linecap="round"/>
<polyline points="7,8.5 7,11 5.5,9.5" fill="none" stroke="{c}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
<line x1="7" y1="11" x2="8.5" y2="9.5" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
</svg>"""

# History: часы с правильными стрелками
_HISTORY = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg">
<circle cx="7" cy="7" r="5.5" fill="none" stroke="{c}" stroke-width="1.3"/>
<polyline points="7,3.5 7,7 9.5,8.5" fill="none" stroke="{c}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


# =============================================================================
# КНОПКИ TOOLBAR ВМ (14×14 viewBox)
# =============================================================================
# Start и Stop используют захардкоженные цвета — цвет несёт смысл.

# Start: заполненный зелёный треугольник
_START = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg">
<polygon points="3,2 12,7 3,12" fill="#22c55e"/>
</svg>"""

# Shutdown: классический символ питания
_SHUTDOWN = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg">
<path d="M4.5 3.5 A5 5 0 1 0 9.5 3.5" fill="none" stroke="{c}" stroke-width="1.5" stroke-linecap="round"/>
<line x1="7" y1="1.5" x2="7" y2="6.5" stroke="{c}" stroke-width="1.5" stroke-linecap="round"/>
</svg>"""

# Reboot: дуга по часовой + стрелка
_REBOOT = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg">
<path d="M2 7 A5 5 0 1 1 7 12" fill="none" stroke="{c}" stroke-width="1.5" stroke-linecap="round"/>
<polyline points="7,12 7,9.5 9.5,12" fill="none" stroke="{c}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

# Reset: МОЛНИЯ — принципиально отличается от Reboot
_RESET = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg">
<polyline points="8.5,1.5 4,7.5 7.5,7.5 5.5,12.5 10,6.5 6.5,6.5 8.5,1.5"
  fill="none" stroke="#f59e0b" stroke-width="1.3" stroke-linejoin="round" stroke-linecap="round"/>
</svg>"""

# Stop: заполненный красный квадрат
_STOP = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg">
<rect x="3" y="3" width="8" height="8" rx="1" fill="#ef4444"/>
</svg>"""

# Console: монитор со скруглёнными углами + >_ курсор
_CONSOLE = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg">
<rect x="1" y="2" width="12" height="8" rx="1" fill="none" stroke="{c}" stroke-width="1.3"/>
<polyline points="3,7.5 4.5,6 3,4.5" fill="none" stroke="{c}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
<line x1="6" y1="7.5" x2="8.5" y2="7.5" stroke="{c}" stroke-width="1.2" stroke-linecap="round"/>
<line x1="5" y1="10" x2="9" y2="10" stroke="{c}" stroke-width="1" stroke-linecap="round"/>
<line x1="7" y1="10" x2="7" y2="12" stroke="{c}" stroke-width="1" stroke-linecap="round"/>
<line x1="4" y1="13" x2="10" y2="13" stroke="{c}" stroke-width="1.3" stroke-linecap="round"/>
</svg>"""

# Resume: двойная стрелка (новая иконка — в оригинале отсутствовала)
_RESUME = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg">
<polygon points="1.5,3 6,7 1.5,11" fill="{c}"/>
<polygon points="7,3 11.5,7 7,11" fill="{c}"/>
</svg>"""


# =============================================================================
# НАВИГАЦИЯ / КОНТРОЛЫ
# =============================================================================

# Add: плюс В КРУЖКЕ — не путать с Expand (было: ОДИНАКОВЫЕ SVG!)
_ADD = """<svg viewBox="0 0 12 12" xmlns="http://www.w3.org/2000/svg">
<circle cx="6" cy="6" r="4.5" fill="none" stroke="{c}" stroke-width="1.3"/>
<line x1="6" y1="3.5" x2="6" y2="8.5" stroke="{c}" stroke-width="1.3" stroke-linecap="round"/>
<line x1="3.5" y1="6" x2="8.5" y2="6" stroke="{c}" stroke-width="1.3" stroke-linecap="round"/>
</svg>"""

# Expand: уголки наружу (полноэкранный режим) — отличается от Add
_EXPAND = """<svg viewBox="0 0 12 12" xmlns="http://www.w3.org/2000/svg">
<polyline points="1,4 1,1 4,1" fill="none" stroke="{c}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
<polyline points="8,1 11,1 11,4" fill="none" stroke="{c}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
<polyline points="1,8 1,11 4,11" fill="none" stroke="{c}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
<polyline points="11,8 11,11 8,11" fill="none" stroke="{c}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

# Collapse: уголки внутрь
_COLLAPSE = """<svg viewBox="0 0 12 12" xmlns="http://www.w3.org/2000/svg">
<polyline points="4,1 1,4 4,4" fill="none" stroke="{c}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
<polyline points="11,4 8,4 8,1" fill="none" stroke="{c}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
<polyline points="4,11 4,8 1,8" fill="none" stroke="{c}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
<polyline points="8,8 11,8 8,11" fill="none" stroke="{c}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


# =============================================================================
# ИЗМЕНЕНИЯ В init_icons() — добавить в словарь:
#   "resume": _make_icon(_RESUME.format(c=_C, c2=_C2)),
# Остальные — заменить на новые константы выше.
# Иконки без изменений: _FOLDER, _APP, _REFRESH, _MONITOR, _DISK, _ISO, _TEMPLATE
# =============================================================================
