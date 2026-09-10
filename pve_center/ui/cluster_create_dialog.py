"""Cluster create dialog (B12b): pvecm create on a standalone node."""

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from .i18n import tr

_NAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$")


class ClusterCreateDialog(QDialog):
    """Create a new cluster on the given standalone node (first member)."""

    def __init__(self, cfg_name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.cfg_name = cfg_name
        self.setWindowTitle(tr("Create cluster"))
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        info = QLabel(tr(
            "A new cluster will be created on this node. It becomes the "
            "first member; add other nodes from their context menu."))
        info.setWordWrap(True)
        info.setStyleSheet("color: #b45309;")
        layout.addWidget(info)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self._name_edit = QLineEdit()
        self._name_edit.setMaxLength(15)
        self._name_edit.setPlaceholderText(tr("cluster name"))
        form.addRow(tr("Cluster name"), self._name_edit)
        self._link_edit = QLineEdit()
        self._link_edit.setPlaceholderText(
            tr("optional — defaults to local IP address"))
        form.addRow(tr("Link 0 address"), self._link_edit)
        layout.addLayout(form)

        hint = QLabel(tr(
            "The host's Cluster setting will be updated automatically "
            "after creation."))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._name_edit.textChanged.connect(self._validate)
        self._validate()

    def _validate(self):
        name = self._name_edit.text().strip()
        ok = bool(_NAME_RE.match(name))
        self._buttons.button(
            QDialogButtonBox.StandardButton.Ok).setEnabled(ok)

    def get_params(self) -> dict:
        return {
            "cfg_name": self.cfg_name,
            "clustername": self._name_edit.text().strip(),
            "link0": self._link_edit.text().strip(),
        }
