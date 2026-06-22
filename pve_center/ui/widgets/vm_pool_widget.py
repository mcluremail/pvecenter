from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, QWidget, QProgressBar
from PySide6.QtCore import Qt
from ..hover import enable_row_hover
from ..i18n import tr
from ..icons import get_icon
from ..detail_panel._constants import _progress_style
from ..detail_panel._table_utils import set_empty_placeholder
from ..theme import Color


class VmPoolWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
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
        layout.addWidget(self.table)
        layout.setContentsMargins(0, 0, 0, 0)

    def set_pool_vms(self, vms):
        if not vms:
            set_empty_placeholder(self.table, 5)
            return
        self.table.setRowCount(len(vms))
        for i, vm in enumerate(vms):
            name_item = QTableWidgetItem(str(vm.get("name", "")))
            name_item.setIcon(get_icon("vm", vm.get("status")))
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, QTableWidgetItem(str(vm.get("type", ""))))

            maxdisk = vm.get("maxdisk", 0)
            disk = vm.get("disk", 0)
            disk_pct = int(max(0, min(100, (disk / maxdisk) * 100))) if maxdisk > 0 else 0
            self._set_progress(i, 2, disk_pct)

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
