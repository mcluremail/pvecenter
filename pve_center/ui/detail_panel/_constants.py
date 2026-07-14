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
    BACKUPS = 10
    DISKS_VM = 11
    ISO = 12
    TEMPLATES = 13
    NETWORK = 14
    SERVICES = 15
    HOST_DISKS = 16
    SNAPSHOTS = 17
    HEALTH = 18
    VM_SNAPSHOTS = 19
    VM_BACKUP = 20
    BACKUP_JOBS = 21
    ACCESS = 22
    HA = 23


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
