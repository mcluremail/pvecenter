from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, QWidget
from ..hover import enable_row_hover

class VmOptionsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Параметр", "Значение"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        enable_row_hover(self.table)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.setContentsMargins(0, 0, 0, 0)

    def set_options_data(self, config_data):
        """Заполняет таблицу всеми ключами config_data, которых нет в списке аппаратных ключей."""
        self.table.setRowCount(0)
        if not config_data:
            return

        # Ключи, которые уже отображаются на вкладке «Оборудование» (не дублируем)
        hardware_keys = {
            'name', 'cpu', 'cores', 'sockets', 'memory',
            'bios', 'machine',
            'vmgenid', 'vga', 'scsihw',
            'net0', 'net1', 'net2', 'net3',
            'ide0', 'ide1', 'ide2', 'ide3',
            'sata0', 'sata1', 'sata2', 'sata3',
            'scsi0', 'scsi1', 'scsi2', 'scsi3',
            'virtio0', 'virtio1', 'virtio2', 'virtio3',
        }

        # Дополнительные служебные ключи, которые не стоит показывать
        service_keys = {
            'digest', 'description', 'meta',
            'hookscript', 'parent', 'template',
            'searchdomain', 'hostname', 'password', 'sshkeys',
            'ciuser', 'cipassword', 'cicustom',
        }

        rows = []
        for key, value in sorted(config_data.items()):
            if key in hardware_keys or key in service_keys:
                continue
            if isinstance(value, list):
                value = ', '.join(value)
            rows.append((key, str(value)))

        for i, (param, val) in enumerate(rows):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(param))
            self.table.setItem(i, 1, QTableWidgetItem(val))

        self.table.resizeRowsToContents()
        for r in range(self.table.rowCount()):
            if self.table.rowHeight(r) > 22:
                self.table.setRowHeight(r, 22)
