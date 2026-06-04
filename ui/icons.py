from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter

ICON_SIZE = 16
_C = "#4b5563"
_C2 = "#374151"

def _status_color(status):
    if status in ("online", "running", "OK"):
        return "#22c55e"
    elif status in ("offline", "stopped", "error"):
        return "#ef4444"
    elif status in ("paused", "RUNNING"):
        return "#f59e0b"
    return None

def _make_icon(svg, size=ICON_SIZE):
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)

_CLUSTER = """<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="1" y="1" width="5" height="5" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="10" y="1" width="5" height="5" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="4.5" y="10" width="7" height="5" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<line x1="5.5" y1="4" x2="10.5" y2="4" stroke="{c}" stroke-width="1.3"/>
<line x1="6.5" y1="10" x2="4.5" y2="6.5" stroke="{c}" stroke-width="1.3"/>
<line x1="9.5" y1="10" x2="11.5" y2="6.5" stroke="{c}" stroke-width="1.3"/>
</svg>"""

_HOST = """<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="2" y="1" width="12" height="14" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="4" y="3" width="8" height="1" rx="0" fill="{c}"/>
<rect x="4" y="5" width="3" height="1" rx="0" fill="{c}"/>
<rect x="4" y="7" width="8" height="1" rx="0" fill="{c}"/>
<rect x="4" y="9" width="3" height="1" rx="0" fill="{c}"/>
<circle cx="8" cy="12" r="1.5" fill="{c2}"/>
</svg>"""

_VM = """<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="1" y="1" width="14" height="10" rx="0" fill="none" stroke="{c}" stroke-width="1.5"/>
<rect x="4" y="11" width="8" height="1" rx="0" fill="{c}"/>
<rect x="5.5" y="12" width="5" height="1" rx="0" fill="{c}"/>
<line x1="8" y1="11" x2="8" y2="13" stroke="{c}" stroke-width="1.3"/>
<line x1="4" y1="14" x2="12" y2="14" stroke="{c}" stroke-width="1.5"/>
</svg>"""

_POOL = """<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="2" y="1" width="12" height="4" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="2" y="6" width="12" height="4" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="2" y="11" width="12" height="4" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<line x1="4" y1="3" x2="12" y2="3" stroke="{c}" stroke-width="1"/>
<line x1="4" y1="8" x2="12" y2="8" stroke="{c}" stroke-width="1"/>
<line x1="4" y1="13" x2="12" y2="13" stroke="{c}" stroke-width="1"/>
</svg>"""

_FOLDER = """<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<path d="M1 3 L5 3 L6.5 5 L15 5 L15 14 L1 14 Z" fill="none" stroke="{c}" stroke-width="1.3" stroke-linejoin="miter"/>
<line x1="1" y1="6" x2="15" y2="6" stroke="{c}" stroke-width="1.3"/>
</svg>"""

_APP = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="2" y="2" width="20" height="20" rx="0" fill="none" stroke="{c}" stroke-width="1.5"/>
<rect x="5" y="5" width="14" height="3" rx="0" fill="{c}"/>
<rect x="5" y="10" width="14" height="1" rx="0" fill="{c}"/>
<rect x="5" y="13" width="14" height="1" rx="0" fill="{c}"/>
<rect x="5" y="16" width="14" height="1" rx="0" fill="{c}"/>
<rect x="8" y="22" width="8" height="1" rx="0" fill="{c}"/>
<rect x="11" y="20" width="2" height="2" rx="0" fill="{c}"/>
</svg>"""

_STORAGE = """<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="1" y="2" width="14" height="12" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="3" y="4" width="10" height="3" rx="0" fill="none" stroke="{c}" stroke-width="1"/>
<rect x="3" y="9" width="5" height="3" rx="0" fill="{c}"/>
<circle cx="11" cy="10.5" r="1" fill="{c}"/>
</svg>"""

_REFRESH = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<path d="M1 7a6 6 0 0 1 10.5-4" fill="none" stroke="{c}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
<polyline points="11.5,1 11.5,3.5 9,3.5" fill="none" stroke="{c}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M13 7a6 6 0 0 1-10.5 4" fill="none" stroke="{c}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
<polyline points="2.5,13 2.5,10.5 5,10.5" fill="none" stroke="{c}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

_MONITOR = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="1" y="1" width="12" height="8" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<line x1="4" y1="9" x2="10" y2="9" stroke="{c}" stroke-width="1.3"/>
<line x1="7" y1="9" x2="7" y2="12" stroke="{c}" stroke-width="1.3"/>
<rect x="5" y="2" width="4" height="2" rx="0" fill="{c2}"/>
<rect x="5" y="5" width="3" height="1" rx="0" fill="{c2}"/>
</svg>"""

_HARDWARE = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="1" y="1" width="12" height="12" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="3" y="3" width="8" height="2" rx="0" fill="{c2}"/>
<rect x="3" y="6" width="5" height="1" rx="0" fill="{c2}"/>
<rect x="3" y="8" width="8" height="1" rx="0" fill="{c2}"/>
<rect x="3" y="10" width="5" height="1" rx="0" fill="{c2}"/>
</svg>"""

_OPTIONS = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="5" y="1" width="4" height="3" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="5" y="10" width="4" height="3" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="1" y="5.5" width="3" height="3" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="10" y="5.5" width="3" height="3" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="5.5" y="5.5" width="3" height="3" rx="0" fill="{c2}"/>
</svg>"""

_HISTORY = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="1" y="1" width="12" height="12" rx="6" fill="none" stroke="{c}" stroke-width="1.3"/>
<line x1="7" y1="3" x2="7" y2="7" stroke="{c}" stroke-width="1.3"/>
<line x1="7" y1="7" x2="10" y2="7" stroke="{c}" stroke-width="1.3"/>
</svg>"""

_DISK = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="1" y="2" width="12" height="10" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="3" y="4" width="8" height="2" rx="0" fill="{c2}"/>
<rect x="3" y="7" width="4" height="2" rx="0" fill="{c2}"/>
</svg>"""

_BACKUP = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="2" y="1" width="10" height="12" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<line x1="4" y1="4" x2="10" y2="4" stroke="{c}" stroke-width="1.3"/>
<line x1="4" y1="7" x2="10" y2="7" stroke="{c}" stroke-width="1.3"/>
<rect x="4" y="10" width="3" height="1" rx="0" fill="{c2}"/>
</svg>"""

_ISO = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<circle cx="7" cy="7" r="5.5" fill="none" stroke="{c}" stroke-width="1.3"/>
<circle cx="7" cy="7" r="2.5" fill="none" stroke="{c}" stroke-width="1.3"/>
<line x1="7" y1="1.5" x2="7" y2="4.5" stroke="{c}" stroke-width="1.3"/>
</svg>"""

_TEMPLATE = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="1" y="1" width="12" height="4" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="3" y="5" width="8" height="8" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<line x1="4" y1="3" x2="10" y2="3" stroke="{c}" stroke-width="1"/>
<rect x="5" y="7" width="4" height="2" rx="0" fill="{c2}"/>
</svg>"""

_NETWORK = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="1" y="1" width="5" height="3" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="8" y="1" width="5" height="3" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="8" y="10" width="5" height="3" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<line x1="6" y1="2.5" x2="8" y2="2.5" stroke="{c}" stroke-width="1.3"/>
<line x1="6" y1="2.5" x2="8" y2="11.5" stroke="{c}" stroke-width="1.3"/>
<line x1="8" y1="11.5" x2="10" y2="11.5" stroke="{c}" stroke-width="1.3"/>
</svg>"""

_SERVICES = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="1" y="1" width="12" height="3" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="1" y="5.5" width="12" height="3" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="1" y="10" width="12" height="3" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="3" y="2" width="2" height="1" rx="0" fill="{c2}"/>
<rect x="3" y="6.5" width="2" height="1" rx="0" fill="{c2}"/>
<rect x="3" y="11" width="2" height="1" rx="0" fill="{c2}"/>
</svg>"""

_SNAPSHOT = """<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<rect x="1" y="3" width="12" height="10" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<rect x="4" y="1" width="6" height="2" rx="0" fill="none" stroke="{c}" stroke-width="1.3"/>
<circle cx="7" cy="8" r="2.5" fill="none" stroke="{c}" stroke-width="1.3"/>
<circle cx="7" cy="8" r="1" fill="{c2}"/>
</svg>"""

_EXPAND = """<svg viewBox="0 0 12 12" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<line x1="6" y1="2" x2="6" y2="10" stroke="{c}" stroke-width="1.5"/>
<line x1="2" y1="6" x2="10" y2="6" stroke="{c}" stroke-width="1.5"/>
</svg>"""

_COLLAPSE = """<svg viewBox="0 0 12 12" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<line x1="2" y1="6" x2="10" y2="6" stroke="{c}" stroke-width="1.5"/>
</svg>"""

_ADD = """<svg viewBox="0 0 12 12" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<line x1="6" y1="2" x2="6" y2="10" stroke="{c}" stroke-width="1.5"/>
<line x1="2" y1="6" x2="10" y2="6" stroke="{c}" stroke-width="1.5"/>
</svg>"""

_LOADING = """<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">
<circle cx="8" cy="8" r="5" fill="none" stroke="#e5e7eb" stroke-width="2"/>
<path d="M8 3 A5 5 0 0 1 13 8" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"/>
</svg>"""


def _make_icon_with_dot(template, status):
    dot_color = _status_color(status)
    if dot_color is None:
        return _make_icon(template.format(c=_C, c2=_C2))
    svg = template.format(c=_C, c2=_C2).replace(
        "</svg>",
        f'<circle cx="12.5" cy="12.5" r="4" fill="{dot_color}" stroke="white" stroke-width="1.2"/></svg>'
    )
    return _make_icon(svg, 16)


def _make_loading_icon(angle):
    svg = _LOADING.format(c=_C, c2=_C2).replace(
        '<path d="M8 3',
        f'<path transform="rotate({angle} 8 8)" d="M8 3'
    )
    return _make_icon(svg, 16)

def get_icon(name, status=None):
    if status and name in ("host", "vm", "cluster", "pool"):
        return _make_icon_with_dot(globals()[f"_{name.upper()}"], status)
    if _icons is None:
        init_icons()
    return _icons.get(name)

_icons = None

def init_icons():
    global _icons
    if _icons is not None:
        return
    _icons = {
        "cluster": _make_icon(_CLUSTER.format(c=_C, c2=_C2)),
        "host": _make_icon(_HOST.format(c=_C, c2=_C2)),
        "vm": _make_icon(_VM.format(c=_C, c2=_C2)),
        "pool": _make_icon(_POOL.format(c=_C, c2=_C2)),
        "folder": _make_icon(_FOLDER.format(c=_C, c2=_C2)),
        "storage": _make_icon(_STORAGE.format(c=_C, c2=_C2)),
        "app": _make_icon(_APP.format(c=_C, c2=_C2), 24),
        "refresh": _make_icon(_REFRESH.format(c=_C, c2=_C2), 14),
        "monitor": _make_icon(_MONITOR.format(c=_C, c2=_C2)),
        "hardware": _make_icon(_HARDWARE.format(c=_C, c2=_C2)),
        "options": _make_icon(_OPTIONS.format(c=_C, c2=_C2)),
        "history": _make_icon(_HISTORY.format(c=_C, c2=_C2)),
        "disk": _make_icon(_DISK.format(c=_C, c2=_C2)),
        "backup": _make_icon(_BACKUP.format(c=_C, c2=_C2)),
        "iso": _make_icon(_ISO.format(c=_C, c2=_C2)),
        "template": _make_icon(_TEMPLATE.format(c=_C, c2=_C2)),
        "network": _make_icon(_NETWORK.format(c=_C, c2=_C2)),
        "services": _make_icon(_SERVICES.format(c=_C, c2=_C2)),
        "snapshot": _make_icon(_SNAPSHOT.format(c=_C, c2=_C2)),
        "expand": _make_icon(_EXPAND.format(c=_C, c2=_C2), 12),
        "collapse": _make_icon(_COLLAPSE.format(c=_C, c2=_C2), 12),
        "add": _make_icon(_ADD.format(c=_C, c2=_C2), 12),
    }
