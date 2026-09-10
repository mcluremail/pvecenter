"""StorageConfigDialog tests (B4)."""

from __future__ import annotations

import pytest

from pve_center.ui.storage_config_dialog import StorageConfigDialog


@pytest.fixture
def dialog(qtbot):
    dlg = StorageConfigDialog()
    qtbot.addWidget(dlg)
    return dlg


class TestStorageConfigDialog:
    def test_create_mode_defaults(self, dialog):
        assert dialog.windowTitle() == "Create storage…"
        assert dialog._id_edit.isEnabled()
        assert dialog._type_combo.isEnabled()
        assert dialog.get_storage_type() == "dir"

    def test_edit_mode_locks_id_and_type(self, qtbot):
        dlg = StorageConfigDialog({"storage": "local", "type": "dir", "path": "/x"})
        qtbot.addWidget(dlg)
        assert not dlg._id_edit.isEnabled()
        assert not dlg._type_combo.isEnabled()
        assert dlg.get_storage_id() == "local"
        assert dlg._type_edits["path"].text() == "/x"

    def test_get_params_content_and_nodes(self, dialog):
        dialog._id_edit.setText("mystorage")
        dialog._type_edits["path"].setText("/mnt/data")
        dialog._content_checks["iso"].setChecked(True)
        dialog._content_checks["backup"].setChecked(True)
        dialog._nodes_edit.setText("n1,n2")
        params = dialog.get_params()
        assert params["content"] == "iso,backup"
        assert params["nodes"] == "n1,n2"
        assert params["enable"] == 1
        assert params["path"] == "/mnt/data"

    def test_get_params_disabled(self, dialog):
        dialog._enable_check.setChecked(False)
        assert dialog.get_params()["enable"] == 0

    def test_get_params_omits_empty_fields(self, dialog):
        dialog._id_edit.setText("x")
        params = dialog.get_params()
        assert "nodes" not in params
        assert "content" not in params

    def test_type_fields_rebuild(self, dialog):
        dialog._type_combo.setCurrentIndex(dialog._type_combo.findData("nfs"))
        assert "server" in dialog._type_edits and "export" in dialog._type_edits
        dialog._type_combo.setCurrentIndex(dialog._type_combo.findData("cifs"))
        assert "share" in dialog._type_edits and "password" in dialog._type_edits

    def test_validate_rejects_empty_id(self, dialog):
        assert dialog._validate() != ""

    def test_validate_rejects_bad_id(self, dialog):
        dialog._id_edit.setText("bad id!")
        assert dialog._validate() != ""

    def test_validate_rejects_missing_path(self, dialog):
        dialog._id_edit.setText("ok1")
        assert dialog._validate() != ""

    def test_validate_ok(self, dialog):
        dialog._id_edit.setText("ok1")
        dialog._type_edits["path"].setText("/mnt/x")
        assert dialog._validate() == ""
