from datetime import datetime, timezone
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from ..hover import enable_row_hover


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
            "Начало", "Окончание", "Хост", "Пользователь", "Описание", "Статус"
        ])

        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setSectionResizeMode(0, QHeaderView.Interactive)
        h.setSectionResizeMode(1, QHeaderView.Interactive)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.Stretch)
        h.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.table.setColumnWidth(0, 155)
        self.table.setColumnWidth(1, 155)

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

        self.table.setRowCount(len(tasks))
        for i, task in enumerate(tasks):
            start_ts = task.get('starttime')
            if start_ts:
                try:
                    start_dt = datetime.fromtimestamp(float(start_ts), tz=timezone.utc)
                    start_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
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
                    end_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    end_str = str(end_ts)
            else:
                end_str = ''
            item1 = NumericTableItem(end_str)
            if end_ts:
                item1.setData(Qt.UserRole, float(end_ts))
            if not end_str:
                item1.setForeground(QColor("#f59e0b"))
                item1.setText("выполняется...")
            self.table.setItem(i, 1, item1)

            node = task.get('node', '')
            host_display = task.get('_display_name', node) or node or '—'
            self.table.setItem(i, 2, QTableWidgetItem(host_display))

            user = task.get('user', '')
            self.table.setItem(i, 3, QTableWidgetItem(user))

            task_type = task.get('type', '')
            vmid = task.get('vmid') or ''
            upid = task.get('upid', '')
            if vmid:
                desc = f"{task_type}: VM {vmid}"
            elif upid:
                desc = f"{task_type} ({upid})"
            else:
                desc = task_type
            self.table.setItem(i, 4, QTableWidgetItem(desc))

            status = task.get('status', '')
            item5 = QTableWidgetItem(status)
            if status == 'OK':
                item5.setForeground(QColor("#22c55e"))
            elif status == 'RUNNING':
                item5.setForeground(QColor("#f59e0b"))
            else:
                item5.setForeground(QColor("#ef4444"))
            self.table.setItem(i, 5, item5)

        self.table.resizeRowsToContents()
        for r in range(self.table.rowCount()):
            if self.table.rowHeight(r) > 22:
                self.table.setRowHeight(r, 22)

        if was_sorted:
            self.table.setSortingEnabled(True)
            self.table.sortItems(sort_col, sort_order)
        else:
            self.table.sortItems(0, Qt.DescendingOrder)
            self.table.setSortingEnabled(True)
