"""Tests for AddServerDialog PBS mode (B17 stage 2)."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialog

from pve_center.ui import add_server_dialog as asd_mod
from pve_center.ui.add_server_dialog import AddServerDialog


@pytest.fixture
def dialog(qtbot):
    d = AddServerDialog()
    qtbot.addWidget(d)
    d.show()
    return d


class TestTypeSwitch:
    def test_default_is_pve(self, dialog):
        assert dialog.type_combo.currentData() == "pve"
        assert not dialog._is_pbs()
        assert not dialog.add_btn.isEnabled()

    def test_switch_to_pbs_shows_port_hides_token_flow(self, dialog):
        idx = dialog.type_combo.findData("pbs")
        dialog.type_combo.setCurrentIndex(idx)
        assert dialog._is_pbs()
        assert dialog.port_input.isVisible()
        assert not dialog.auth_btn.isVisible()
        assert not dialog.token_name_label.isVisible()
        assert not dialog.cluster_rep_cb.isVisible()
        assert dialog.add_btn.isEnabled()

    def test_switch_back_to_pve_disables_add_without_token(self, dialog):
        dialog.type_combo.setCurrentIndex(dialog.type_combo.findData("pbs"))
        dialog.type_combo.setCurrentIndex(dialog.type_combo.findData("pve"))
        assert not dialog._is_pbs()
        assert not dialog.add_btn.isEnabled()

    def test_switch_back_to_pve_keeps_add_with_token(self, dialog):
        dialog._token_data = {"user": "u", "token_name": "t",
                              "token_value": "v"}
        dialog.type_combo.setCurrentIndex(dialog.type_combo.findData("pbs"))
        dialog.type_combo.setCurrentIndex(dialog.type_combo.findData("pve"))
        assert dialog.add_btn.isEnabled()


class TestGetConfigPbs:
    def test_minimal(self, dialog):
        dialog.type_combo.setCurrentIndex(dialog.type_combo.findData("pbs"))
        dialog.name_input.setText("MyPBS")
        dialog.host_input.setText("pbs.local")
        dialog.user_input.setText("root@pam")
        dialog.pwd_input.setText("secret")
        cfg = dialog.get_config()
        assert cfg == {
            "name": "MyPBS", "type": "pbs", "host": "pbs.local",
            "port": 8007, "user": "root@pam", "token_name": "",
            "token_value": "secret", "trust_ssl": False,
        }

    def test_custom_port_and_trust_ssl(self, dialog):
        dialog.type_combo.setCurrentIndex(dialog.type_combo.findData("pbs"))
        dialog.host_input.setText("pbs.local")
        dialog.port_input.setText("8008")
        dialog.trust_ssl_cb.setChecked(True)
        dialog.pwd_input.setText("pw")
        cfg = dialog.get_config()
        assert cfg["port"] == 8008
        assert cfg["trust_ssl"] is True
        assert cfg["name"] == "pbs.local"  # name falls back to host

    def test_empty_password_add_blocked(self, dialog, monkeypatch):
        dialog.type_combo.setCurrentIndex(dialog.type_combo.findData("pbs"))
        dialog.host_input.setText("pbs.local")
        created = []
        monkeypatch.setattr(
            asd_mod, "PbsApiWorker",
            lambda *a, **kw: created.append((a, kw)),
        )
        dialog._on_add()
        assert created == []
        assert dialog.status_label.text() != ""


class TestValidationFlow:
    def test_on_add_spawns_validate_worker(self, dialog, monkeypatch):
        created = {}

        class FakeSignals:
            def __init__(self):
                self.connected = []
                self.done = self
                self.failed = self

            def connect(self, slot):
                self.connected.append(slot)

        class FakeWorker:
            def __init__(self, cfg, method, tag=None):
                created["cfg"] = cfg
                created["method"] = method
                created["tag"] = tag
                self.signals = FakeSignals()

        monkeypatch.setattr(asd_mod, "PbsApiWorker", FakeWorker)
        monkeypatch.setattr(asd_mod.QThreadPool.globalInstance(), "start",
                            lambda w: None)
        dialog.type_combo.setCurrentIndex(dialog.type_combo.findData("pbs"))
        dialog.host_input.setText("pbs.local")
        dialog.pwd_input.setText("secret")
        dialog._on_add()
        assert created["method"] == "datastores"
        assert created["tag"] == "validate"
        assert created["cfg"]["type"] == "pbs"

    def test_validate_done_accepts(self, dialog):
        dialog.type_combo.setCurrentIndex(dialog.type_combo.findData("pbs"))
        dialog.host_input.setText("pbs.local")
        dialog.show()
        dialog._on_validate_done("validate", [])
        assert dialog.result() == QDialog.Accepted

    def test_validate_wrong_tag_ignored(self, dialog):
        dialog.show()
        dialog._on_validate_done("other", [])
        assert dialog.result() != QDialog.Accepted
