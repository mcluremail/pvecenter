"""ClusterJoinDialog — add a node to an existing PVE cluster (B12a).

Runs POST /cluster/config/join on the selected (joinee) node via
ClusterJoinWorker in mainwindow. Peer credentials (hostname + root
password) are passed to the joinee; the app itself talks to the joinee
through its existing API-token config.
"""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from .i18n import tr


class ClusterJoinDialog(QDialog):
    """Collect join parameters for one node joining an existing cluster."""

    def __init__(self, candidates: list[dict], cluster_name: str,
                 peer_host: str = "", parent=None):
        super().__init__(parent)
        # candidates: full host cfg dicts from nodes_cfg (currentData is
        # passed to ClusterJoinWorker as host_cfg).
        self._candidates = candidates
        self.setWindowTitle(tr("Add node to cluster"))
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        warn = QLabel(tr(
            "The node will join cluster \"{cluster}\" and its services will "
            "restart. The node must have no VMs or containers."
        ).format(cluster=cluster_name))
        warn.setWordWrap(True)
        layout.addWidget(warn)

        form = QFormLayout()
        self._node_combo = QComboBox()
        for c in candidates:
            self._node_combo.addItem(
                f"{c.get('node', '')} ({c.get('name', '')})", c)
        form.addRow(tr("Node to add"), self._node_combo)

        self._host_edit = QLineEdit(peer_host)
        self._host_edit.setPlaceholderText(tr("IP or hostname of any cluster member"))
        form.addRow(tr("Cluster member"), self._host_edit)

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.Password)
        self._password_edit.setPlaceholderText(tr("Root password of the cluster member"))
        form.addRow(tr("Root password"), self._password_edit)

        self._fp_edit = QLineEdit()
        self._fp_edit.setPlaceholderText(tr("Optional"))
        form.addRow(tr("Peer fingerprint"), self._fp_edit)

        self._link0_edit = QLineEdit()
        self._link0_edit.setPlaceholderText(tr("Optional"))
        form.addRow(tr("Corosync link0"), self._link0_edit)

        self._votes_edit = QLineEdit()
        self._votes_edit.setPlaceholderText(tr("Default: 1"))
        form.addRow(tr("Votes"), self._votes_edit)
        layout.addLayout(form)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._host_edit.textChanged.connect(self._validate)
        self._password_edit.textChanged.connect(self._validate)
        self._validate()

    def _validate(self):
        ok = bool(self._host_edit.text().strip()) and bool(self._password_edit.text())
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok)

    def get_params(self) -> dict:
        votes_text = self._votes_edit.text().strip()
        return {
            "cfg": self._node_combo.currentData(),
            "hostname": self._host_edit.text().strip(),
            "password": self._password_edit.text(),
            "fingerprint": self._fp_edit.text().strip(),
            "link0": self._link0_edit.text().strip(),
            "votes": int(votes_text) if votes_text.isdigit() else None,
        }
