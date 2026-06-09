from datetime import datetime, timezone
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from ..hover import enable_row_hover

class VmTaskHistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.table = QTableWidget()
        self.table.verticalHeader().hide()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Начало", "Окончание", "Статус", "Пользователь", "Описание"
        ])
        # Колонки времени и статуса — по содержимому, описание — Stretch
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setStyleSheet("QHeaderView::section { padding-left: 4px; }")

        self.table.setWordWrap(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        enable_row_hover(self.table)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.setContentsMargins(0, 0, 0, 0)

    def set_tasks(self, tasks):
        """tasks – список словарей, возвращённых /nodes/{node}/tasks"""
        self.table.setRowCount(len(tasks))
        for i, task in enumerate(tasks):
            # Начало
            start_ts = task.get('starttime')
            if start_ts:
                try:
                    start_dt = datetime.fromtimestamp(float(start_ts))
                    start_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    start_str = str(start_ts)
            else:
                start_str = ''
            self.table.setItem(i, 0, QTableWidgetItem(start_str))

            # Окончание
            end_ts = task.get('endtime')
            if end_ts:
                try:
                    end_dt = datetime.fromtimestamp(float(end_ts))
                    end_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    end_str = str(end_ts)
            else:
                end_str = ''
            end_item = QTableWidgetItem(end_str)
            if not end_str:
                end_item.setForeground(QColor("#f59e0b"))
                end_item.setText("выполняется...")
            self.table.setItem(i, 1, end_item)

            # Статус
            status = task.get('status', '')
            status_item = QTableWidgetItem(status)
            if status == 'OK':
                status_item.setForeground(QColor("#22c55e"))
            elif status == 'RUNNING':
                status_item.setForeground(QColor("#f59e0b"))
            else:
                status_item.setForeground(QColor("#ef4444"))
            self.table.setItem(i, 2, status_item)

            # Пользователь
            user = task.get('user', '')
            self.table.setItem(i, 3, QTableWidgetItem(user))

            # Описание (тип + VMID + узел, без разбора upid)
            task_type = task.get('type', '')
            node = task.get('node') or ''
            vmid = task.get('vmid') or task.get('id') or ''
            upid = task.get('upid', '')

            if vmid and node:
                desc = f"{task_type}: VM {vmid} на {node}"
            elif vmid:
                desc = f"{task_type}: VM {vmid}"
            elif node:
                desc = f"{task_type} на {node}"
            elif upid:
                desc = f"{task_type} ({upid})"
            else:
                desc = task_type

            self.table.setItem(i, 4, QTableWidgetItem(desc))

        self.table.resizeRowsToContents()
        for r in range(self.table.rowCount()):
            if self.table.rowHeight(r) > 22:
                self.table.setRowHeight(r, 22)
