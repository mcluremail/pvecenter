from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QLineEdit, QSpinBox, QComboBox,
                               QCheckBox, QFormLayout, QMessageBox)
from PySide6.QtCore import Qt, Signal


class VmConfigEditorDialog(QDialog):
    """Модальный диалог для редактирования одного параметра VM."""
    def __init__(self, key, label, field_type, current_value, choices=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Редактирование: {label}")
        self.setMinimumWidth(400)
        self.setMinimumHeight(120)

        self._key = key
        self._field_type = field_type

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Заголовок
        header = QLabel(f"<b>{label}</b>")
        layout.addWidget(header)

        form = QFormLayout()

        if field_type == "bool":
            self._editor = QCheckBox("Включено")
            self._editor.setChecked(current_value in (1, "1", True))
            form.addRow("Значение:", self._editor)

        elif field_type == "int":
            self._editor = QSpinBox()
            self._editor.setRange(0, 999999)
            self._editor.setValue(int(current_value) if current_value else 0)
            form.addRow("Значение:", self._editor)

        elif field_type == "choice":
            self._editor = QComboBox()
            for c in (choices or []):
                self._editor.addItem(c, c)
            # Выбираем текущее значение
            idx = self._editor.findData(current_value)
            if idx >= 0:
                self._editor.setCurrentIndex(idx)
            else:
                # Если текущего нет в списке — добавляем как кастом
                self._editor.addItem(str(current_value), current_value)
                self._editor.setCurrentIndex(self._editor.count() - 1)
            form.addRow("Значение:", self._editor)

        elif field_type == "string":
            self._editor = QLineEdit(str(current_value) if current_value is not None else "")
            form.addRow("Значение:", self._editor)

        elif field_type == "readonly":
            self._editor = QLabel(str(current_value) if current_value is not None else "")
            self._editor.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow("Только чтение:", self._editor)
            readonly_warning = QLabel("Этот параметр нельзя изменить через API")
            readonly_warning.setStyleSheet("color: #d97706; font-size: 11px;")
            form.addRow(readonly_warning)

        else:
            self._editor = QLineEdit(str(current_value) if current_value is not None else "")
            form.addRow("Значение:", self._editor)

        layout.addLayout(form)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._ok_btn = QPushButton("Сохранить")
        self._ok_btn.setObjectName("accentBtn")
        self._ok_btn.setFixedWidth(120)
        self._ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self._ok_btn)

        self._cancel_btn = QPushButton("Отмена")
        self._cancel_btn.setFixedWidth(120)
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        layout.addLayout(btn_layout)

        if field_type == "bool":
            self._ok_btn.setFocus()
        else:
            self._editor.setFocus()

    def _on_ok(self):
        # Валидация перед закрытием
        val = self.get_raw_value()
        if val == "" and self._field_type in ("string", "int"):
            ret = QMessageBox.question(
                self, "Пустое значение",
                "Вы уверены, что хотите установить пустое значение?",
                QMessageBox.Yes | QMessageBox.No
            )
            if ret != QMessageBox.Yes:
                return
        self.accept()

    def get_raw_value(self):
        """Возвращает сырое значение для отправки в API (key, value)."""
        ft = self._field_type
        if ft == "bool":
            return (self._key, 1 if self._editor.isChecked() else 0)
        elif ft == "int":
            return (self._key, self._editor.value())
        elif ft == "choice":
            return (self._key, self._editor.currentData())
        elif ft == "string":
            return (self._key, self._editor.text().strip())
        elif ft == "readonly":
            return (self._key, None)  # нельзя сохранить
        return (self._key, self._editor.text().strip())