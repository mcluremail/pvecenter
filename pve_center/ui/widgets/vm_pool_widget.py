from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..detail_panel._constants import _progress_style
from ..detail_panel._table_utils import set_empty_placeholder
from ..hover import enable_row_hover
from ..i18n import tr
from ..icons import get_icon
from .metric_card import MetricCard


class VmPoolWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._summary_cards: dict[str, MetricCard] = {}

        summary_layout = QHBoxLayout()
        summary_layout.setContentsMargins(0, 0, 0, 6)
        summary_layout.setSpacing(10)
        for key, title in (
            ("vms", tr("VMs")),
            ("cpu", tr("CPU")),
            ("ram", tr("Memory")),
            ("disk", tr("Disk")),
        ):
            card = MetricCard(title, show_progress=(key in ("cpu", "ram", "disk")))
            summary_layout.addWidget(card)
            self._summary_cards[key] = card
        summary_widget = QWidget()
        summary_widget.setLayout(summary_layout)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            tr("Name"), tr("Type"), tr("Disk %"), tr("RAM %"),
            tr("CPU %"), tr("Uptime")
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setStyleSheet("QHeaderView::section { padding-left: 4px; }")
        self.table.setAlternatingRowColors(True)
        enable_row_hover(self.table)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(summary_widget)
        layout.addWidget(self.table)

    def set_pool_vms(self, vms):
        if not vms:
            set_empty_placeholder(self.table, 5)
            self._update_summary([])
            return
        self.table.setRowCount(len(vms))
        for i, vm in enumerate(vms):
            name_item = QTableWidgetItem(str(vm.get("name", "")))
            name_item.setIcon(get_icon("vm", vm.get("status")))
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, QTableWidgetItem(str(vm.get("type", ""))))

            maxdisk = vm.get("maxdisk", 0)
            disk = vm.get("disk", 0)
            vm_type = vm.get("type", "qemu")
            if vm_type == "lxc" and disk and maxdisk:
                disk_pct = int(max(0, min(100, (disk / maxdisk) * 100)))
                self._set_progress(i, 2, disk_pct)
            elif maxdisk:
                disk_gb = round(maxdisk / (1024**3), 1)
                disk_item = QTableWidgetItem(f"{disk_gb} GiB")
                disk_item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(i, 2, disk_item)

            maxmem = vm.get("maxmem", 0)
            mem = vm.get("mem", 0)
            mem_pct = int(max(0, min(100, (mem / maxmem) * 100))) if maxmem > 0 else 0
            self._set_progress(i, 3, mem_pct)

            cpu_fraction = vm.get("cpu", 0)
            cpu_pct = int(round(cpu_fraction * 100)) if isinstance(cpu_fraction, (int, float)) else 0
            self._set_progress(i, 4, cpu_pct)

            uptime_sec = vm.get("uptime", 0)
            uptime_str = self._fmt_uptime(uptime_sec) if uptime_sec else ''
            self.table.setItem(i, 5, QTableWidgetItem(uptime_str))

        self.table.resizeRowsToContents()
        for r in range(self.table.rowCount()):
            if self.table.rowHeight(r) > 24:
                self.table.setRowHeight(r, 24)

        self._update_summary(vms)

    def _update_summary(self, vms):
        total = len(vms)
        running = sum(1 for v in vms if v.get("status") == "running")
        self._summary_cards["vms"].set_value(f"{running}/{total}")
        self._summary_cards["vms"].set_subtitle(
            f"{total - running} {tr('stopped')}" if total != running else "")
        self._summary_cards["vms"].set_progress(
            int(running / total * 100) if total else 0)

        cpu_sum = sum(v.get("cpu", 0) or 0 for v in vms
                      if isinstance(v.get("cpu"), (int, float)))
        cpu_pct = round(cpu_sum / total * 100, 1) if total else 0
        self._summary_cards["cpu"].set_value(f"{cpu_pct}%")
        self._summary_cards["cpu"].set_progress(cpu_pct)

        mem_total = sum(v.get("maxmem", 0) or 0 for v in vms)
        mem_used = sum(v.get("mem", 0) or 0 for v in vms)
        mem_pct = round(mem_used / mem_total * 100, 1) if mem_total else 0
        mem_gb = round(mem_used / (1024**3), 1) if mem_used else 0
        maxmem_gb = round(mem_total / (1024**3), 1) if mem_total else 0
        self._summary_cards["ram"].set_value(f"{mem_gb}/{maxmem_gb} GiB")
        self._summary_cards["ram"].set_progress(mem_pct)

        disk_total = sum(v.get("maxdisk", 0) or 0 for v in vms)
        disk_used = sum(v.get("disk", 0) or 0 for v in vms)
        disk_pct = round(disk_used / disk_total * 100, 1) if disk_total else 0
        disk_gb = round(disk_used / (1024**3), 1) if disk_used else 0
        maxdisk_gb = round(disk_total / (1024**3), 1) if disk_total else 0
        self._summary_cards["disk"].set_value(f"{disk_gb}/{maxdisk_gb} GiB")
        self._summary_cards["disk"].set_progress(disk_pct)

    def _set_progress(self, row, col, pct):
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(pct)
        bar.setFormat(f"{pct}%")
        bar.setStyleSheet(_progress_style(pct))
        self.table.setCellWidget(row, col, bar)
        di = QTableWidgetItem("")
        di.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(row, col, di)

    @staticmethod
    def _fmt_uptime(seconds):
        if not seconds or seconds <= 0:
            return ""
        days, rem = divmod(int(seconds), 86400)
        hours, rem = divmod(rem, 3600)
        mins, secs = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if mins:
            parts.append(f"{mins}m")
        if secs or not parts:
            parts.append(f"{secs}s")
        return " ".join(parts)
