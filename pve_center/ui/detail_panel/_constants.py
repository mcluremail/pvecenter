from enum import IntEnum

from ..theme import Color

_HEADER_STYLE = "QHeaderView::section { padding: 6px 8px; border: none; border-bottom: 1px solid #f0f1f4; }"

_MAX_WORKERS_DP = 12

try:
    import pyqtgraph as pg
    pg.setConfigOption('background', '#fafafa')
    pg.setConfigOption('foreground', '#6b7280')
    _HAS_PG = True
except ImportError:
    pg = None
    _HAS_PG = False


class TabIndex(IntEnum):
    MONITOR = 0
    HARDWARE = 1
    OPTIONS = 2
    HISTORY = 3
    SUMMARY = 4
    HOST_VMS = 5
    POOL_VMS = 6
    STORAGES = 7
    HOST_STORAGE = 8
    STORAGE_DETAIL = 9
    STORAGE_MONITORING = 10
    BACKUPS = 11
    DISKS_VM = 12
    ISO = 13
    TEMPLATES = 14
    NETWORK = 15
    SERVICES = 16
    HOST_DISKS = 17
    SNAPSHOTS = 18
    HEALTH = 19
    VM_SNAPSHOTS = 20
    VM_BACKUP = 21
    BACKUP_JOBS = 22
    ACCESS = 23
    HA = 24


def _fmt_pveversion(val):
    val = str(val)
    return val.split("/")[1] if "/" in val else val


def _progress_style(value, max_val=100):
    pct = int((value / max_val) * 100) if max_val else 0
    if pct < 0:
        pct = 0
    elif pct > 100:
        pct = 100
    if pct < 50:
        color = Color.STATUS_OK
    elif pct < 80:
        color = Color.STATUS_WARN
    else:
        color = Color.STATUS_ERR
    return (
        f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}"
        f"QProgressBar {{ border: none; border-radius: 3px;"
        f" text-align: center; font-size: 11px; background: {Color.GRAY_100}; }}"
    )
