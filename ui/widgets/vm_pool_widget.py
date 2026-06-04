from PySide6.QtWidgets import (QTableWidget, QTableWidgetItem, QHeaderView,
                               QVBoxLayout, QWidget, QProgressBar)
from PySide6.QtCore import Qt
from ..hover import enable_row_hover

class VmPoolWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Имя", "Тип", "Диск %", "ОЗУ %", "ЦП %", "Аптайм"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        enable_row_hover(self.table)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.setContentsMargins(0, 0, 0, 0)

    def _format_uptime(self, seconds):
        if seconds <= 0:
            return '0'
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
        return ' '.join(parts)

    def set_pool_vms(self, vms):
        self.table.setRowCount(len(vms))
        for i, vm in enumerate(vms):
            self.table.setItem(i, 0, QTableWidgetItem(str(vm.get("name", ""))))
            self.table.setItem(i, 1, QTableWidgetItem(str(vm.get("type", ""))))

            # Disk %
            maxdisk = vm.get("maxdisk", 0)
            disk = vm.get("disk", 0)
            disk_pct = int((disk / maxdisk) * 100) if maxdisk > 0 else 0
            disk_bar = QProgressBar()
            disk_bar.setRange(0, 100)
            disk_bar.setValue(disk_pct)
            disk_bar.setFormat(f"{disk_pct}%")
            self.table.setCellWidget(i, 2, disk_bar)
            di = QTableWidgetItem("")
            di.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(i, 2, di)

            # Mem %
            maxmem = vm.get("maxmem", 0)
            mem = vm.get("mem", 0)
            mem_pct = int((mem / maxmem) * 100) if maxmem > 0 else 0
            mem_bar = QProgressBar()
            mem_bar.setRange(0, 100)
            mem_bar.setValue(mem_pct)
            mem_bar.setFormat(f"{mem_pct}%")
            self.table.setCellWidget(i, 3, mem_bar)
            mi = QTableWidgetItem("")
            mi.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(i, 3, mi)

            # ЦП %
            cpu_fraction = vm.get("cpu", 0)
            cpu_pct = int(round(cpu_fraction * 100)) if isinstance(cpu_fraction, (int, float)) else 0
            cpu_bar = QProgressBar()
            cpu_bar.setRange(0, 100)
            cpu_bar.setValue(cpu_pct)
            cpu_bar.setFormat(f"{cpu_pct}%")
            self.table.setCellWidget(i, 4, cpu_bar)
            ci = QTableWidgetItem("")
            ci.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(i, 4, ci)

            # Uptime
            uptime_sec = vm.get("uptime", 0)
            uptime_str = self._format_uptime(uptime_sec) if uptime_sec else ''
            self.table.setItem(i, 5, QTableWidgetItem(uptime_str))

        self.table.resizeRowsToContents()
        for r in range(self.table.rowCount()):
            if self.table.rowHeight(r) > 24:
                self.table.setRowHeight(r, 24)
