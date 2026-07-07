import json
from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from ...config import load_ui_state, save_ui_state
from ..hover import enable_row_hover
from ..i18n import tr
from ..theme import Color

TASK_COL_WIDTHS_KEY = "task_col_widths"


TASK_TYPE_LABELS = {
    # VM
    "qemstart": tr("Start VM"),
    "qmstart": tr("Start VM"),
    "qemstop": tr("Stop VM"),
    "qmstop": tr("Stop VM"),
    "qemshutdown": tr("Shutdown VM"),
    "qmshutdown": tr("Shutdown VM"),
    "qemreboot": tr("Reboot VM"),
    "qmreboot": tr("Reboot VM"),
    "qemreset": tr("Reset VM"),
    "qmreset": tr("Reset VM"),
    "qemsuspend": tr("Suspend VM"),
    "qmgestsuspend": tr("Suspend VM"),
    "qmresume": tr("Resume VM"),
    "qmgestscreenshot": tr("VM Screenshot"),
    "qmgstdstva": tr("VM Task"),
    "spiceproxy": tr("SPICE Console"),
    "vncproxy": tr("VNC Console"),
    "console": tr("Console"),
    # LXC
    "lxc-start": tr("Start Container"),
    "lxc-stop": tr("Stop Container"),
    "lxc-shutdown": tr("Shutdown Container"),
    "lxc-reboot": tr("Reboot Container"),
    "lxc-suspend": tr("Suspend Container"),
    "lxc-resume": tr("Resume Container"),
    "vzstart": tr("Start Container"),
    "vzstop": tr("Stop Container"),
    "vzreboot": tr("Reboot Container"),
    # VM/Container management
    "create": tr("Create"),
    "destroy": tr("Destroy"),
    "clone": tr("Clone"),
    "qmigrate": tr("Migrate"),
    "resize": tr("Resize Disk"),
    "qmmove": tr("Move Disk"),
    "move": tr("Move"),
    "diskread": tr("Disk Read"),
    "diskwrite": tr("Disk Write"),
    "imgdel": tr("Delete Image"),
    "imgcopy": tr("Copy Image"),
    # Snapshots
    "snapshot": tr("Create Snapshot"),
    "snapdestroy": tr("Delete Snapshot"),
    "snaprollback": tr("Rollback to Snapshot"),
    "snapremove": tr("Delete Snapshot"),
    # Backups and restore
    "vzdump": tr("Backup"),
    "restore": tr("Restore"),
    "verify": tr("Verify Backups"),
    "pull": tr("Import Backup"),
    # Storage
    "dfs-migrate": tr("Migrate Storage"),
    "dfs-del": tr("Delete from Storage"),
    # Network
    "sdn-apply": tr("Apply SDN"),
    # Updates
    "pveupdate": tr("Update PVE"),
    "pveproxy": tr("Update Proxy"),
    "apt": tr("APT Operation"),
    # HA
    "ha-manager": tr("HA Manager"),
    "ha-crm": tr("HA CRM"),
    # Security and ACME
    "acmedns": tr("ACME DNS Challenge"),
    "pvefw-logger": tr("PVE Firewall"),
    # Replication
    "repl": tr("Replication"),
    # Ceph
    "ceph-apply": tr("Apply Ceph"),
    "ceph-destroy": tr("Destroy Ceph"),
    "ceph-create-fs": tr("Create Ceph FS"),
    "ceph-install": tr("Install Ceph"),
}

TIMESTAMP_FMT = "%d.%m.%y %H:%M"


def _vmid_from_upid(upid):
    if not upid or not upid.startswith("UPID:"):
        return ""
    parts = upid.split(":")
    if len(parts) < 7:
        return ""
    candidate = parts[6]
    if candidate.isdigit():
        return candidate
    if len(parts) >= 9:
        info = ":".join(parts[8:])
        idx = info.find("--vmid ")
        if idx >= 0:
            rest = info[idx + 7:].lstrip()
            end = rest.find(" ")
            num = rest[:end] if end >= 0 else rest
            if num.isdigit():
                return num
    return ""


class NumericTableItem(QTableWidgetItem):
    def __lt__(self, other):
        if not isinstance(other, QTableWidgetItem):
            return super().__lt__(other)
        a = self.data(Qt.UserRole)
        b = other.data(Qt.UserRole)
        if a is not None and b is not None:
            try:
                return float(a) < float(b)
            except (ValueError, TypeError):
                pass
        return super().__lt__(other)


class ClusterTasksWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.table = QTableWidget()
        self.table.verticalHeader().hide()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            tr("Start time"), tr("End time"), tr("Host"), tr("User"), tr("Description"), tr("Status")
        ])

        h = self.table.horizontalHeader()
        h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        h.setStyleSheet("QHeaderView::section { padding-left: 4px; }")
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setSectionResizeMode(0, QHeaderView.Interactive)
        h.setSectionResizeMode(1, QHeaderView.Interactive)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.Stretch)
        h.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.table.setColumnWidth(0, 155)
        self.table.setColumnWidth(1, 155)

        # Restore column widths (changes saved via sectionResized)
        self._restore_column_widths()
        h.sectionResized.connect(self._save_column_widths)

        self.table.setWordWrap(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        enable_row_hover(self.table)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.setContentsMargins(0, 0, 0, 0)

    def set_tasks(self, tasks):
        was_sorted = self.table.isSortingEnabled()
        if was_sorted:
            self.table.setSortingEnabled(False)

        sort_col = self.table.horizontalHeader().sortIndicatorSection()
        sort_order = self.table.horizontalHeader().sortIndicatorOrder()

        # Block model signals — otherwise ResizeToContents and sorting
        # react to every setItem, causing O(n²) with 500+ rows
        self.table.setUpdatesEnabled(False)
        self.table.model().blockSignals(True)
        self.table.setRowCount(len(tasks))

        for i, task in enumerate(tasks):
            start_ts = task.get('starttime')
            if start_ts:
                try:
                    start_dt = datetime.fromtimestamp(float(start_ts), tz=timezone.utc)
                    start_str = start_dt.strftime(TIMESTAMP_FMT)
                except (ValueError, TypeError):
                    start_str = str(start_ts)
            else:
                start_str = ''
            item0 = NumericTableItem(start_str)
            if start_ts:
                item0.setData(Qt.UserRole, float(start_ts))
            self.table.setItem(i, 0, item0)

            end_ts = task.get('endtime')
            if end_ts:
                try:
                    end_dt = datetime.fromtimestamp(float(end_ts), tz=timezone.utc)
                    end_str = end_dt.strftime(TIMESTAMP_FMT)
                except (ValueError, TypeError):
                    end_str = str(end_ts)
            else:
                end_str = ''
            item1 = NumericTableItem(end_str)
            if end_ts:
                item1.setData(Qt.UserRole, float(end_ts))
            if not end_str:
                item1.setForeground(QColor(Color.STATUS_WARN))
                item1.setText(tr("running..."))
            self.table.setItem(i, 1, item1)

            node = task.get('node', '')
            host_display = task.get('_display_name', node) or node or '—'
            self.table.setItem(i, 2, QTableWidgetItem(host_display))

            user = task.get('user', '')
            self.table.setItem(i, 3, QTableWidgetItem(user))

            task_type = task.get('type', '')
            vmid = task.get('vmid') or task.get('id') or task.get('_vmid') or ''
            if not vmid:
                vmid = _vmid_from_upid(task.get('upid', ''))
            vm_name = task.get('_vm_name', '')
            label = TASK_TYPE_LABELS.get(task_type, task_type)
            if vmid and vm_name:
                desc = f"{label} {vm_name} ({vmid})"
            elif vmid:
                desc = f"{label} {vmid}"
            else:
                desc = label
            item4 = QTableWidgetItem(desc)
            font = item4.font()
            font.setBold(True)
            item4.setFont(font)
            self.table.setItem(i, 4, item4)

            status = task.get('status', '')
            item5 = QTableWidgetItem(status[:30] + '…' if len(status) > 30 else status)
            item5.setToolTip(status if len(status) > 30 else '')
            if status == 'OK':
                item5.setForeground(QColor(Color.STATUS_OK))
            elif status == 'RUNNING':
                item5.setForeground(QColor(Color.STATUS_WARN))
            else:
                item5.setForeground(QColor(Color.STATUS_ERR))
            self.table.setItem(i, 5, item5)

        self.table.resizeRowsToContents()
        for r in range(self.table.rowCount()):
            if self.table.rowHeight(r) > 22:
                self.table.setRowHeight(r, 22)

        self.table.model().blockSignals(False)
        self.table.setUpdatesEnabled(True)

        if was_sorted:
            self.table.setSortingEnabled(True)
            self.table.sortItems(sort_col, sort_order)
        else:
            self.table.setSortingEnabled(True)
            self.table.horizontalHeader().setSortIndicator(0, Qt.DescendingOrder)
            self.table.sortItems(0, Qt.DescendingOrder)

    def set_placeholder(self, text=None):
        if text is None:
            text = tr("Loading tasks...")
        was_sorted = self.table.isSortingEnabled()
        if was_sorted:
            self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.model().blockSignals(True)
        self.table.setRowCount(0)
        self.table.setRowCount(1)
        item = QTableWidgetItem(text)
        item.setForeground(QColor(Color.GRAY_500))
        self.table.setItem(0, 4, item)
        self.table.model().blockSignals(False)
        self.table.setUpdatesEnabled(True)
        if was_sorted:
            self.table.setSortingEnabled(True)

    def _save_column_widths(self):
        widths = [self.table.columnWidth(c) for c in range(self.table.columnCount())]
        save_ui_state(TASK_COL_WIDTHS_KEY, json.dumps(widths))

    def _restore_column_widths(self):
        raw = load_ui_state(TASK_COL_WIDTHS_KEY)
        if not raw:
            return
        try:
            widths = json.loads(raw)
            if isinstance(widths, list) and len(widths) == self.table.columnCount():
                for c, w in enumerate(widths):
                    self.table.setColumnWidth(c, w)
        except (TypeError, ValueError):
            pass
