from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QLineEdit, QPushButton, QCheckBox,
                               QMessageBox, QGroupBox)
from PySide6.QtCore import Qt, QThreadPool
from ..backend import TokenCreationWorker
from .i18n import tr


class AddServerDialog(QDialog):

    def __init__(self, parent=None, context=""):
        super().__init__(parent)
        self._context = context
        title_suffix = {"cluster": tr(" to cluster"), "standalone": tr(" as standalone host")}.get(context, "")
        self.setWindowTitle(tr("Add Server") + title_suffix)
        self.setFixedSize(500, 420)
        self._token_data = None
        self._active_workers = set()
        self._build_ui()
        self._apply_context()

    def closeEvent(self, event):
        for w in list(self._active_workers):
            try:
                w.signals.token_ready.disconnect()
                w.signals.token_error.disconnect()
            except (RuntimeError, TypeError):
                pass
        self._active_workers.clear()
        super().closeEvent(event)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        conn_group = QGroupBox(tr("Connection"))
        conn_grid = QGridLayout(conn_group)

        conn_grid.addWidget(QLabel(tr("Host:")), 0, 0)
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("pve01.example.com")
        conn_grid.addWidget(self.host_input, 0, 1)

        conn_grid.addWidget(QLabel(tr("User:")), 1, 0)
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("username@realm (root@pam, user@ipa...)")
        conn_grid.addWidget(self.user_input, 1, 1)

        conn_grid.addWidget(QLabel(tr("Password:")), 2, 0)
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.Password)
        self.pwd_input.setPlaceholderText("••••••••")
        conn_grid.addWidget(self.pwd_input, 2, 1)

        info_label = QLabel(tr("An API token will be created for the specified user"))
        info_label.setStyleSheet("color: #6b7280; font-size: 11px;")
        conn_grid.addWidget(info_label, 3, 0, 1, 2)

        self.auth_btn = QPushButton(tr("Get token"))
        conn_grid.addWidget(self.auth_btn, 4, 0, 1, 2)
        self.auth_btn.clicked.connect(self._on_auth)

        layout.addWidget(conn_group)

        token_group = QGroupBox(tr("Token"))
        token_grid = QGridLayout(token_group)

        self.token_name_label = QLabel("—")
        self.token_name_label.setStyleSheet("font-family: monospace;")
        token_grid.addWidget(QLabel(tr("Token name:")), 0, 0)
        token_grid.addWidget(self.token_name_label, 0, 1)

        self.token_value_label = QLabel("—")
        self.token_value_label.setStyleSheet("font-family: monospace; color: #22c55e;")
        token_grid.addWidget(QLabel(tr("Value:")), 1, 0)
        token_grid.addWidget(self.token_value_label, 1, 1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #6b7280;")
        token_grid.addWidget(self.status_label, 2, 0, 1, 2)

        layout.addWidget(token_group)

        node_group = QGroupBox(tr("Node settings"))
        node_grid = QGridLayout(node_group)

        node_grid.addWidget(QLabel(tr("Name:")), 0, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(tr("auto (first part of hostname)"))
        node_grid.addWidget(self.name_input, 0, 1)

        node_grid.addWidget(QLabel(tr("Cluster:")), 1, 0)
        self.cluster_input = QLineEdit()
        self.cluster_input.setPlaceholderText(tr("cluster name (if applicable)"))
        node_grid.addWidget(self.cluster_input, 1, 1)

        self.cluster_rep_cb = QCheckBox(tr("This is a cluster representative"))
        node_grid.addWidget(self.cluster_rep_cb, 2, 0, 1, 2)

        layout.addWidget(node_group)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton(tr("Add"))
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(tr("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _apply_context(self):
        ctx = self._context
        if ctx == "cluster":
            self.cluster_input.setPlaceholderText(tr("cluster name (required for clusters)"))
            self.cluster_rep_cb.setChecked(True)
        elif ctx == "standalone":
            self.cluster_input.setPlaceholderText(tr("leave empty — standalone host"))
            self.cluster_rep_cb.setChecked(False)

    def _on_auth(self):
        host = self.host_input.text().strip()
        user = self.user_input.text().strip()
        password = self.pwd_input.text()

        if not host:
            self._set_status(tr("Enter host"), "#ef4444")
            return
        if not user:
            self._set_status(tr("Enter user"), "#ef4444")
            return
        if not password:
            self._set_status(tr("Enter password"), "#ef4444")
            return

        self.auth_btn.setEnabled(False)
        self.auth_btn.setText(tr("Connecting..."))
        self._set_status(tr("Connecting and creating token..."), "#6b7280")

        worker = TokenCreationWorker(host, user, password)
        self._active_workers.add(worker)
        worker.signals.token_ready.connect(self._on_token_ready)
        worker.signals.token_error.connect(self._on_token_error)
        def _cleanup(w=worker):
            self._active_workers.discard(w)
        worker.signals.finished.connect(_cleanup)
        QThreadPool.globalInstance().start(worker)

    def _on_token_ready(self, result):
        self._token_data = result
        self.token_name_label.setText(result["token_name"])
        self.token_value_label.setText(result["token_value"])
        self._set_status(tr("Token created"), "#22c55e")
        self.auth_btn.setEnabled(True)
        self.auth_btn.setText(tr("Update token"))
        self.add_btn.setEnabled(True)

        if not self.name_input.text().strip():
            self.name_input.setText(self.host_input.text().strip())

    def _on_token_error(self, error):
        self._set_status(error, "#ef4444")
        self.auth_btn.setEnabled(True)
        self.auth_btn.setText(tr("Get token"))
        self._token_data = None
        self.add_btn.setEnabled(False)

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
