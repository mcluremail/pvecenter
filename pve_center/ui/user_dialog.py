from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from .i18n import tr

_PVE_REALMS = [
    ("pam", "Linux PAM"),
    ("pve", "Proxmox VE"),
    ("ldap", "LDAP"),
    ("ad", "Active Directory"),
]


class UserDialog(QDialog):
    """Dialog for creating or editing a PVE user."""

    def __init__(self, parent=None, user=None, groups=None):
        super().__init__(parent)
        self._user = user or {}
        self._groups = groups or []
        self._is_edit = bool(user)
        self.setWindowTitle(tr("Edit user") if self._is_edit else tr("Add user"))
        self.setMinimumWidth(440)
        self._build_ui()
        if self._is_edit:
            self._fill_from_user()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        form = QFormLayout()
        form.setSpacing(8)

        if self._is_edit:
            self._userid_edit = QLineEdit(self._user.get("userid", ""))
            self._userid_edit.setReadOnly(True)
        else:
            self._userid_edit = QLineEdit()
            self._userid_edit.setPlaceholderText("name@realm")
        form.addRow(tr("User ID:"), self._userid_edit)

        if not self._is_edit:
            self._realm_combo = QComboBox()
            for code, label in _PVE_REALMS:
                self._realm_combo.addItem(label, code)
            form.addRow(tr("Realm:"), self._realm_combo)
        else:
            self._realm_combo = None

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.Password)
        self._password_edit.setPlaceholderText(tr("Initial password"))
        if self._is_edit:
            self._password_edit.setPlaceholderText(tr("Leave blank to keep"))
        form.addRow(tr("Password:"), self._password_edit)

        self._firstname_edit = QLineEdit()
        form.addRow(tr("First name:"), self._firstname_edit)

        self._lastname_edit = QLineEdit()
        form.addRow(tr("Last name:"), self._lastname_edit)

        self._email_edit = QLineEdit()
        self._email_edit.setPlaceholderText("user@example.com")
        form.addRow(tr("Email:"), self._email_edit)

        self._groups_combo = QComboBox()
        self._groups_combo.addItem(tr("None"), "")
        for g in self._groups:
            gid = g.get("groupid", "")
            if gid:
                self._groups_combo.addItem(gid, gid)
        form.addRow(tr("Group:"), self._groups_combo)

        self._enabled_check = QCheckBox(tr("Enabled"))
        self._enabled_check.setChecked(True)
        form.addRow("", self._enabled_check)

        self._expire_spin = QSpinBox()
        self._expire_spin.setRange(0, 2147483647)
        self._expire_spin.setValue(0)
        self._expire_spin.setSpecialValueText(tr("Never"))
        form.addRow(tr("Expire (days):"), self._expire_spin)

        self._comment_edit = QLineEdit()
        form.addRow(tr("Comment:"), self._comment_edit)

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

    def _fill_from_user(self):
        u = self._user
        self._firstname_edit.setText(u.get("firstname", "") or "")
        self._lastname_edit.setText(u.get("lastname", "") or "")
        self._email_edit.setText(u.get("email", "") or "")
        groups_str = u.get("groups", "")
        if isinstance(groups_str, list):
            groups_str = ",".join(groups_str)
        if groups_str:
            idx = self._groups_combo.findData(groups_str.split(",")[0].strip())
            if idx >= 0:
                self._groups_combo.setCurrentIndex(idx)
        enable_val = u.get("enable", 1)
        if isinstance(enable_val, str):
            enable_val = int(enable_val)
        self._enabled_check.setChecked(bool(enable_val))
        expire = u.get("expire", 0)
        if isinstance(expire, str):
            expire = int(expire)
        if expire and expire > 0:
            import time
            remaining = max(0, (expire - int(time.time())) // 86400)
            self._expire_spin.setValue(remaining)
        self._comment_edit.setText(u.get("comment", "") or "")

    def get_params(self):
        params = {}
        if not self._is_edit:
            userid = self._userid_edit.text().strip()
            if not userid:
                return {}
            realm = self._realm_combo.currentData() if self._realm_combo else "pam"
            if "@" not in userid:
                userid = f"{userid}@{realm}"
            params["userid"] = userid
            pwd = self._password_edit.text()
            if pwd:
                params["password"] = pwd
        else:
            pwd = self._password_edit.text()
            if pwd:
                params["password"] = pwd

        firstname = self._firstname_edit.text().strip()
        if firstname:
            params["firstname"] = firstname
        lastname = self._lastname_edit.text().strip()
        if lastname:
            params["lastname"] = lastname
        email = self._email_edit.text().strip()
        if email:
            params["email"] = email

        group = self._groups_combo.currentData()
        if group:
            params["groups"] = group

        params["enable"] = 1 if self._enabled_check.isChecked() else 0

        days = self._expire_spin.value()
        if days > 0:
            import time
            params["expire"] = int(time.time()) + days * 86400
        else:
            params["expire"] = 0

        comment = self._comment_edit.text().strip()
        if comment:
            params["comment"] = comment

        return params
