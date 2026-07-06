from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..backend import TokenCreationWorker
from .i18n import tr
from .theme import Color


def _section_title(text):
    lbl = QLabel(text)
    lbl.setObjectName("sectionTitle")
    return lbl


def _section_sep():
    sep = QFrame()
    sep.setObjectName("sectionSep")
    sep.setFrameShape(QFrame.HLine)
    sep.setFixedHeight(1)
    return sep


class AddServerDialog(QDialog):

    def __init__(self, parent=None, context=""):
        super().__init__(parent)
        self._context = context
        title_suffix = {"cluster": tr(" to cluster"), "standalone": tr(" as standalone host")}.get(context, "")
        self.setWindowTitle(tr("Add Server") + title_suffix)
        self.setMinimumSize(520, 660)
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
        layout.setSpacing(16)

        layout.addWidget(_section_title(tr("Connection")))

        conn_grid = QGridLayout()
        conn_grid.setHorizontalSpacing(12)
        conn_grid.setVerticalSpacing(10)

        host_lbl = QLabel(tr("Host:"))
        host_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        conn_grid.addWidget(host_lbl, 0, 0)
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("pve01.example.com")
        conn_grid.addWidget(self.host_input, 0, 1)

        user_lbl = QLabel(tr("User:"))
        user_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        conn_grid.addWidget(user_lbl, 1, 0)
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("username@realm (root@pam, user@ipa...)")
        conn_grid.addWidget(self.user_input, 1, 1)

        pwd_lbl = QLabel(tr("Password:"))
        pwd_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        conn_grid.addWidget(pwd_lbl, 2, 0)
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.Password)
        self.pwd_input.setPlaceholderText("••••••••")
        conn_grid.addWidget(self.pwd_input, 2, 1)

        info_label = QLabel(tr("An API token will be created for the specified user"))
        info_label.setStyleSheet(f"color: {Color.TEXT_SEC}; font-size: 12px;")
        conn_grid.addWidget(info_label, 3, 0, 1, 2)

        self.trust_ssl_cb = QCheckBox(tr("Trust SSL certificate"))
        self.trust_ssl_cb.setChecked(True)
        self.trust_ssl_cb.setToolTip(tr("Accept self-signed certificates. Uncheck for CA-issued certs."))
        conn_grid.addWidget(self.trust_ssl_cb, 4, 0, 1, 2)

        self.auth_btn = QPushButton(tr("Get token"))
        conn_grid.addWidget(self.auth_btn, 5, 0, 1, 2)
        self.auth_btn.clicked.connect(self._on_auth)

        conn_grid.setColumnStretch(1, 1)
        layout.addLayout(conn_grid)
        layout.addWidget(_section_sep())

        layout.addWidget(_section_title(tr("Token")))

        token_grid = QGridLayout()
        token_grid.setHorizontalSpacing(12)
        token_grid.setVerticalSpacing(10)

        tn_lbl = QLabel(tr("Token name:"))
        tn_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        token_grid.addWidget(tn_lbl, 0, 0)
        self.token_name_label = QLabel("—")
        self.token_name_label.setStyleSheet("font-family: monospace;")
        token_grid.addWidget(self.token_name_label, 0, 1)

        tv_lbl = QLabel(tr("Value:"))
        tv_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        token_grid.addWidget(tv_lbl, 1, 0)
        self.token_value_label = QLabel("—")
        self.token_value_label.setStyleSheet(f"font-family: monospace; color: {Color.STATUS_OK};")
        token_grid.addWidget(self.token_value_label, 1, 1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {Color.TEXT_SEC};")
        token_grid.addWidget(self.status_label, 2, 0, 1, 2)

        token_grid.setColumnStretch(1, 1)
        layout.addLayout(token_grid)
        layout.addWidget(_section_sep())

        layout.addWidget(_section_title(tr("Node settings")))

        node_grid = QGridLayout()
        node_grid.setHorizontalSpacing(12)
        node_grid.setVerticalSpacing(10)

        name_lbl = QLabel(tr("Name:"))
        name_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        node_grid.addWidget(name_lbl, 0, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(tr("auto (first part of hostname)"))
        node_grid.addWidget(self.name_input, 0, 1)

        cl_lbl = QLabel(tr("Cluster:"))
        cl_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        node_grid.addWidget(cl_lbl, 1, 0)
        self.cluster_input = QLineEdit()
        self.cluster_input.setPlaceholderText(tr("cluster name (if applicable)"))
        node_grid.addWidget(self.cluster_input, 1, 1)

        self.cluster_rep_cb = QCheckBox(tr("This is a cluster representative"))
        node_grid.addWidget(self.cluster_rep_cb, 2, 0, 1, 2)

        node_grid.setColumnStretch(1, 1)
        layout.addLayout(node_grid)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton(tr("Add"))
        self.add_btn.setObjectName("accentBtn")
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
            self._set_status(tr("Enter host"), Color.STATUS_ERR)
            return
        if not user:
            self._set_status(tr("Enter user"), Color.STATUS_ERR)
            return
        if not password:
            self._set_status(tr("Enter password"), Color.STATUS_ERR)
            return

        self.auth_btn.setEnabled(False)
        self.auth_btn.setText(tr("Connecting..."))
        self._set_status(tr("Connecting and creating token..."), Color.GRAY_500)

        worker = TokenCreationWorker(host, user, password,
                                     trust_ssl=self.trust_ssl_cb.isChecked())
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
        self._set_status(tr("Token created"), Color.STATUS_OK)
        self.auth_btn.setEnabled(True)
        self.auth_btn.setText(tr("Update token"))
        self.add_btn.setEnabled(True)

        if not self.name_input.text().strip():
            self.name_input.setText(self.host_input.text().strip())

    def _on_token_error(self, error):
        self._set_status(error, Color.STATUS_ERR)
        self.auth_btn.setEnabled(True)
        self.auth_btn.setText(tr("Get token"))
        self._token_data = None
        self.add_btn.setEnabled(False)

    def _set_status(self, text, color=Color.GRAY_500):
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
            "trust_ssl": self.trust_ssl_cb.isChecked(),
        }

        if self.cluster_rep_cb.isChecked():
            cfg["cluster_rep"] = True
            cfg["cluster"] = cluster_text or name
        else:
            cfg["cluster"] = cluster_text if cluster_text else False

        return cfg
