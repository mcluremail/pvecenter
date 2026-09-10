"""ClusterCreateDialog (B12b): name validation and params."""

from PySide6.QtWidgets import QDialogButtonBox

from pve_center.ui.cluster_create_dialog import ClusterCreateDialog


def make_dialog(qtbot):
    dlg = ClusterCreateDialog("h1")
    qtbot.addWidget(dlg)
    return dlg


def _ok_button(dlg):
    return dlg._buttons.button(QDialogButtonBox.StandardButton.Ok)


def test_ok_disabled_until_valid_name(qtbot):
    dlg = make_dialog(qtbot)
    assert not _ok_button(dlg).isEnabled()
    dlg._name_edit.setText("prod")
    assert _ok_button(dlg).isEnabled()
    dlg._name_edit.setText("-bad")
    assert not _ok_button(dlg).isEnabled()
    dlg._name_edit.setText("bad-")
    assert not _ok_button(dlg).isEnabled()
    dlg._name_edit.setText("cl-1")
    assert _ok_button(dlg).isEnabled()
    dlg._name_edit.setText("a" * 16)
    assert dlg._name_edit.text() == "a" * 15
    assert _ok_button(dlg).isEnabled()


def test_max_length_15(qtbot):
    dlg = make_dialog(qtbot)
    assert dlg._name_edit.maxLength() == 15


def test_get_params(qtbot):
    dlg = make_dialog(qtbot)
    dlg._name_edit.setText("prod")
    dlg._link_edit.setText("10.0.0.1")
    params = dlg.get_params()
    assert params == {
        "cfg_name": "h1",
        "clustername": "prod",
        "link0": "10.0.0.1",
    }
