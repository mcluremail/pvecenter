from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from .i18n import tr


class TokenDialog(QDialog):
    """Dialog for creating or editing an API token."""

    def __init__(self, parent=None, userid="", token=None, users=None):
        super().__init__(parent)
        self._userid = userid
        self._token = token or {}
        self._is_edit = bool(token)
        self._users = users or []
        self.setWindowTitle(tr("Edit token") if self._is_edit else tr("Add token"))
        self.setMinimumWidth(440)
        self._build_ui()
        if self._is_edit:
            self._fill_from_token()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        form = QFormLayout()
        form.setSpacing(8)

        if not self._is_edit:
            self._user_combo = QComboBox()
            for u in self._users:
                uid = u.get("userid", "")
                if uid:
                    self._user_combo.addItem(uid, uid)
            if self._userid:
                idx = self._user_combo.findData(self._userid)
                if idx >= 0:
                    self._user_combo.setCurrentIndex(idx)
            form.addRow(tr("User:"), self._user_combo)
        else:
            self._user_combo = None
            lbl = QLabel(self._userid)
            form.addRow(tr("User:"), lbl)

        if self._is_edit:
            self._tokenid_edit = QLineEdit(self._token.get("tokenid", ""))
            self._tokenid_edit.setReadOnly(True)
        else:
            self._tokenid_edit = QLineEdit()
            self._tokenid_edit.setPlaceholderText("e.g. my-token")
        form.addRow(tr("Token ID:"), self._tokenid_edit)

        self._comment_edit = QLineEdit()
        form.addRow(tr("Comment:"), self._comment_edit)

        self._privsep_check = QCheckBox(tr("Privilege separation"))
        self._privsep_check.setChecked(True)
        self._privsep_check.setToolTip(
            tr("If enabled, the token has separate ACLs. "
               "If disabled, it inherits the user's privileges.")
        )
        form.addRow("", self._privsep_check)

        self._expire_spin = QSpinBox()
        self._expire_spin.setRange(0, 2147483647)
        self._expire_spin.setValue(0)
        self._expire_spin.setSpecialValueText(tr("Never"))
        form.addRow(tr("Expire (days):"), self._expire_spin)

        if self._is_edit:
            self._regenerate_check = QCheckBox(tr("Regenerate token value"))
            self._regenerate_check.setChecked(False)
            form.addRow("", self._regenerate_check)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._ok_btn = QPushButton(tr("Save"))
        self._ok_btn.setObjectName("accentBtn")
        self._ok_btn.setFixedWidth(120)
        self._ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(tr("Cancel"))
        cancel_btn.setFixedWidth(120)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _fill_from_token(self):
        t = self._token
        self._comment_edit.setText(t.get("comment", "") or "")
        privsep = t.get("privsep", 1)
        if isinstance(privsep, str):
            privsep = int(privsep)
        self._privsep_check.setChecked(bool(privsep))
        expire = t.get("expire", 0)
        if isinstance(expire, str):
            expire = int(expire)
        if expire and expire > 0:
            import time
            remaining = max(0, (expire - int(time.time())) // 86400)
            self._expire_spin.setValue(remaining)

    def get_userid(self):
        if self._user_combo:
            return self._user_combo.currentData() or ""
        return self._userid

    def get_tokenid(self):
        return self._tokenid_edit.text().strip()

    def get_params(self):
        params = {}
        comment = self._comment_edit.text().strip()
        if comment:
            params["comment"] = comment
        params["privsep"] = 1 if self._privsep_check.isChecked() else 0
        days = self._expire_spin.value()
        if days > 0:
            import time
            params["expire"] = int(time.time()) + days * 86400
        else:
            params["expire"] = 0
        if self._is_edit and hasattr(self, "_regenerate_check"):
            if self._regenerate_check.isChecked():
                params["regenerate"] = 1
        return params


class TokenValueDialog(QDialog):
    """Dialog showing a newly created/regenerated API token value.

    The token value is shown once and cannot be retrieved later.
    Includes a Copy button for convenience.
    """

    def __init__(self, parent=None, full_tokenid="", value=""):
        super().__init__(parent)
        self.setWindowTitle(tr("API Token Value"))
        self.setMinimumWidth(520)
        self._full = full_tokenid
        self._value = value
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        warn = QLabel(
            "<b>" + tr("Save this value — it cannot be retrieved later!") + "</b>"
        )
        warn.setStyleSheet("color: #dc2626;")
        warn.setWordWrap(True)
        layout.addWidget(warn)

        form = QFormLayout()
        form.setSpacing(8)

        full_edit = QLineEdit(self._full)
        full_edit.setReadOnly(True)
        form.addRow(tr("Token ID:"), full_edit)

        value_edit = QLineEdit(self._value)
        value_edit.setReadOnly(True)
        form.addRow(tr("Token value:"), value_edit)

        auth_edit = QLineEdit(f"{self._full}={self._value}")
        auth_edit.setReadOnly(True)
        form.addRow(tr("Auth string:"), auth_edit)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        copy_btn = QPushButton(tr("Copy auth string"))
        copy_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(
            f"{self._full}={self._value}"
        ))
        btn_layout.addWidget(copy_btn)
        close_btn = QPushButton(tr("Close"))
        close_btn.setObjectName("accentBtn")
        close_btn.setFixedWidth(120)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
