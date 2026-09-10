"""StorageMoveDialog move/copy mode tests (B4)."""

from __future__ import annotations

import pytest

from pve_center.domain.storage import Storage
from pve_center.ui.storage_actions import StorageMoveDialog


def _mk_storage(name):
    return Storage(storage=name, node="n1", host_name="h1", cluster="",
                   storage_type="dir", content="iso", used_bytes=0,
                   total_bytes=0, avail_bytes=0, shared=False)


@pytest.fixture
def storages():
    return [_mk_storage("fast"), _mk_storage("big")]


class TestMoveMode:
    def test_move_defaults(self, qtbot, storages):
        dlg = StorageMoveDialog("local:iso/t.iso", storages, is_disk=False)
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() == "Move volume"
        assert not dlg._delete_check.isHidden()
        dlg._delete_check.setChecked(True)
        assert dlg.get_params()["delete_source"] is True

    def test_move_target(self, qtbot, storages):
        dlg = StorageMoveDialog("local:iso/t.iso", storages, is_disk=False)
        qtbot.addWidget(dlg)
        dlg._target_combo.setCurrentIndex(1)
        assert dlg.get_params()["target_storage"] == "big"


class TestCopyMode:
    def test_copy_title_and_hidden_delete(self, qtbot, storages):
        dlg = StorageMoveDialog("local:iso/t.iso", storages, is_disk=False, mode="copy")
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() == "Copy volume"
        assert dlg._delete_check.isHidden()
        dlg._delete_check.setChecked(True)
        assert dlg.get_params()["delete_source"] is False

    def test_copy_mode_invalid_falls_back(self, qtbot, storages):
        dlg = StorageMoveDialog("local:iso/t.iso", storages, is_disk=False, mode="bogus")
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() == "Move volume"
