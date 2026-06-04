from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QLineEdit, QPushButton, QCheckBox,
                               QMessageBox, QGroupBox)
from PySide6.QtCore import Qt
from ..backend import create_admin_token


class AddServerDialog(QDialog):
    """Диалог добавления PVE-хоста с созданием админского API-токена."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить сервер")
        self.setFixedSize(500, 420)

        self._token_data = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ---- Параметры подключения ----
        conn_group = QGroupBox("Подключение")
        conn_grid = QGridLayout(conn_group)

        conn_grid.addWidget(QLabel("Хост:"), 0, 0)
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("pve01.example.com")
        conn_grid.addWidget(self.host_input, 0, 1)

        conn_grid.addWidget(QLabel("Пользователь:"), 1, 0)
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("username@realm (root@pam, user@ipa...)")
        conn_grid.addWidget(self.user_input, 1, 1)

        conn_grid.addWidget(QLabel("Пароль:"), 2, 0)
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.Password)
        self.pwd_input.setPlaceholderText("••••••••")
        conn_grid.addWidget(self.pwd_input, 2, 1)

        info_label = QLabel("Будет создан пользователь pvecenter@pve с ролью Administrator на /")
        info_label.setStyleSheet("color: #6b7280; font-size: 11px;")
        conn_grid.addWidget(info_label, 3, 0, 1, 2)

        self.auth_btn = QPushButton("Получить токен")
        conn_grid.addWidget(self.auth_btn, 4, 0, 1, 2)
        self.auth_btn.clicked.connect(self._on_auth)

        layout.addWidget(conn_group)

        # ---- Результат токена ----
        token_group = QGroupBox("Токен")
        token_grid = QGridLayout(token_group)

        self.token_name_label = QLabel("—")
        self.token_name_label.setStyleSheet("font-family: monospace;")
        token_grid.addWidget(QLabel("Имя токена:"), 0, 0)
        token_grid.addWidget(self.token_name_label, 0, 1)

        self.token_value_label = QLabel("—")
        self.token_value_label.setStyleSheet("font-family: monospace; color: #22c55e;")
        token_grid.addWidget(QLabel("Значение:"), 1, 0)
        token_grid.addWidget(self.token_value_label, 1, 1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #6b7280;")
        token_grid.addWidget(self.status_label, 2, 0, 1, 2)

        layout.addWidget(token_group)

        # ---- Параметры узла ----
        node_group = QGroupBox("Настройки узла")
        node_grid = QGridLayout(node_group)

        node_grid.addWidget(QLabel("Имя:"), 0, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("авто (первая часть хоста)")
        node_grid.addWidget(self.name_input, 0, 1)

        node_grid.addWidget(QLabel("Кластер:"), 1, 0)
        self.cluster_input = QLineEdit()
        self.cluster_input.setPlaceholderText("имя кластера (если есть)")
        node_grid.addWidget(self.cluster_input, 1, 1)

        self.cluster_rep_cb = QCheckBox("Это кластерное представительство")
        node_grid.addWidget(self.cluster_rep_cb, 2, 0, 1, 2)

        layout.addWidget(node_group)

        # ---- Кнопки ----
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Добавить")
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_auth(self):
        host = self.host_input.text().strip()
        user = self.user_input.text().strip()
        password = self.pwd_input.text()

        if not host:
            self._set_status("Введите хост", "#ef4444")
            return
        if not user:
            self._set_status("Введите пользователя", "#ef4444")
            return
        if not password:
            self._set_status("Введите пароль", "#ef4444")
            return

        self.auth_btn.setEnabled(False)
        self.auth_btn.setText("Подключение...")
        self._set_status("Создание пользователя и токена...", "#6b7280")

        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()

        result = create_admin_token(host, user, password)

        if "error" in result:
            self._set_status(result["error"], "#ef4444")
            self.auth_btn.setEnabled(True)
            self.auth_btn.setText("Получить токен")
            self._token_data = None
            self.add_btn.setEnabled(False)
            return

        self._token_data = result
        self.token_name_label.setText(result["token_name"])
        self.token_value_label.setText(result["token_value"])
        self._set_status("Токен создан", "#22c55e")
        self.auth_btn.setEnabled(True)
        self.auth_btn.setText("Обновить токен")
        self.add_btn.setEnabled(True)

        if not self.name_input.text().strip():
            self.name_input.setText(host)

    def _set_status(self, text, color="#6b7280"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color};")

    def get_config(self):
        host = self.host_input.text().strip()
        name = self.name_input.text().strip() or host
        cluster_text = self.cluster_input.text().strip()

        cfg = {
            "name": name,
            "host": host,
            "user": self._token_data["user"],
            "token_name": self._token_data["token_name"],
            "token_value": self._token_data["token_value"],
        }

        if self.cluster_rep_cb.isChecked():
            cfg["cluster_rep"] = True
            cfg["cluster"] = cluster_text or name
        else:
            cfg["cluster"] = cluster_text if cluster_text else False

        return cfg