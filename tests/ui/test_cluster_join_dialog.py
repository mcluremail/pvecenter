"""ClusterJoinDialog (B12a): candidate combo, validation gate, params."""

from PySide6.QtWidgets import QDialogButtonBox

from pve_center.ui.cluster_join_dialog import ClusterJoinDialog

CANDIDATES = [
    {"cfg_name": "pve2", "node_name": "n2"},
    {"cfg_name": "pve3", "node_name": "n3"},
]


def _ok_button(dlg):
    return dlg._buttons.button(QDialogButtonBox.StandardButton.Ok)


def make_dialog(qtbot):
    dlg = ClusterJoinDialog(CANDIDATES, "cl1", peer_host="10.0.0.1")
    qtbot.addWidget(dlg)
    return dlg


def test_initial_state(qtbot):
    dlg = make_dialog(qtbot)
    assert dlg._node_combo.count() == 2
    assert dlg._node_combo.currentText() == "n2 (pve2)"
    assert dlg._host_edit.text() == "10.0.0.1"
    # Ok disabled until host + password are filled; host prefilled -> only
    # password missing.
    assert not _ok_button(dlg).isEnabled()


def test_validation_requires_host_and_password(qtbot):
    dlg = ClusterJoinDialog(CANDIDATES, "cl1")
    qtbot.addWidget(dlg)
    ok = _ok_button(dlg)
    assert not ok.isEnabled()
    dlg._host_edit.setText("10.0.0.1")
    assert not ok.isEnabled()
    dlg._password_edit.setText("secret")
    assert ok.isEnabled()
    dlg._host_edit.setText("   ")
    assert not ok.isEnabled()


def test_get_params(qtbot):
    dlg = make_dialog(qtbot)
    dlg._password_edit.setText("secret")
    dlg._fp_edit.setText("AA:BB")
    dlg._votes_edit.setText("2")
    params = dlg.get_params()
    assert params["cfg"] == CANDIDATES[0]
    assert params["hostname"] == "10.0.0.1"
    assert params["password"] == "secret"
    assert params["fingerprint"] == "AA:BB"
    assert params["link0"] == ""
    assert params["votes"] == 2


def test_get_params_votes_invalid_means_none(qtbot):
    dlg = make_dialog(qtbot)
    dlg._password_edit.setText("secret")
    dlg._votes_edit.setText("abc")
    assert dlg.get_params()["votes"] is None
    dlg._votes_edit.setText("")
    assert dlg.get_params()["votes"] is None
