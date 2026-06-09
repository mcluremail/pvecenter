from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, QWidget, QProgressBar
from PySide6.QtCore import Qt
from ..hover import enable_row_hover
from ..i18n import tr


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
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 50)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.setColumnWidth(2, 65)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.setColumnWidth(3, 60)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Interactive)
        self.table.setColumnWidth(4, 55)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Interactive)
        self.table.setColumnWidth(5, 80)

        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setStyleSheet("QHeaderView::section { padding-left: 4px; }")
        self.table.setAlternatingRowColors(True)
        enable_row_hover(self.table)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.setContentsMargins(0, 0, 0, 0)

    def set_pool_vms(self, vms):
        self.table.setRowCount(len(vms))
        for i, vm in enumerate(vms):
            self.table.setItem(i, 0, QTableWidgetItem(str(vm.get("name", ""))))
            self.table.setItem(i, 1, QTableWidgetItem(str(vm.get("type", ""))))

            maxdisk = vm.get("maxdisk", 0)
            disk = vm.get("disk", 0)
            disk_pct = int((disk / maxdisk) * 100) if maxdisk > 0 else 0
            self._set_progress(i, 2, disk_pct)

            maxmem = vm.get("maxmem", 0)
            mem = vm.get("mem", 0)
            mem_pct = int((mem / maxmem) * 100) if maxmem > 0 else 0
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
        bar.setStyleSheet(self._pstyle(pct))
        self.table.setCellWidget(row, col, bar)
        di = QTableWidgetItem("")
        di.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(row, col, di)

    @staticmethod
    def _pstyle(pct):
        if pct < 50:
            color = "#22c55e"
        elif pct < 80:
            color = "#f59e0b"
        else:
            color = "#ef4444"
        return (
            f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}"
            f"QProgressBar {{ border: 1px solid #d1d5db; border-radius: 3px;"
            f" text-align: center; font-size: 11px; background: #f3f4f6; }}"
        )

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
