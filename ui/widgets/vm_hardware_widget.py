from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, QWidget
from ..hover import enable_row_hover

class VmHardwareWidget(QWidget):
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

    def set_hardware_data(self, config_data, detail_data=None):
        self.table.setRowCount(0)
        if not config_data:
            return

        # Ключи, которые мы хотим увидеть (в порядке приоритета)
        hw_keys = [
            'name', 'cpu', 'cores', 'sockets', 'memory',
            'bios', 'machine',
            'vmgenid', 'vga', 'scsihw',
            'net0', 'net1', 'net2', 'net3',
            'ide0', 'ide1', 'ide2', 'ide3',
            'sata0', 'sata1', 'sata2', 'sata3',
            'scsi0', 'scsi1', 'scsi2', 'scsi3',
            'virtio0', 'virtio1', 'virtio2', 'virtio3',
        ]

        # Значения по умолчанию для BIOS и Machine (используются, если API ничего не вернул)
        DEFAULT_VALUES = {
            'bios': 'SeaBIOS',
            'machine': 'i440fx',
        }

        rows = []
        for key in hw_keys:
            # 1) Конфигурация
            value = config_data.get(key)
            # 2) Детальный статус (если нет в конфигурации)
            if value is None and detail_data:
                value = detail_data.get(key)
            # 3) Для machine – fallback на running-machine
            if key == 'machine' and value is None and detail_data:
                rm = detail_data.get('running-machine')
                if rm:
                    value = rm
            # 4) Подставляем умолчания только для BIOS и Machine
            if value is None:
                if key in DEFAULT_VALUES:
                    value = DEFAULT_VALUES[key]
                else:
                    continue   # не показываем строку, если нет данных

            # Преобразуем списки
            if isinstance(value, list):
                value = ', '.join(value)
            rows.append((key, str(value)))

        # Добавляем поля из статуса, которые не дублируются и не попали в hw_keys
        if detail_data:
            for extra in ['running-machine', 'running-qemu']:
                if extra in detail_data:
                    # Не дублируем machine, если он уже был выведен (в т.ч. через running-machine)
                    if extra == 'running-machine':
                        # Проверим, есть ли уже machine в строках (первый элемент кортежа)
                        if 'machine' in [r[0] for r in rows]:
                            continue
                    rows.append((extra, detail_data[extra]))

        for i, (param, val) in enumerate(rows):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(param))
            self.table.setItem(i, 1, QTableWidgetItem(val))

        self.table.resizeRowsToContents()
        for r in range(self.table.rowCount()):
            if self.table.rowHeight(r) > 22:
                self.table.setRowHeight(r, 22)
