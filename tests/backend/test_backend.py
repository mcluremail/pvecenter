"""Tests for pve_center/backend.py — pure helpers and token-creation flow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from pve_center import backend

# --- _verify_ssl ---


class TestVerifySsl:
    def test_default_strict(self):
        assert backend._verify_ssl({}) is True

    def test_explicit_false(self):
        assert backend._verify_ssl({"trust_ssl": False}) is True

    def test_trusted(self):
        assert backend._verify_ssl({"trust_ssl": True}) is False

    def test_truthy_string(self):
        assert backend._verify_ssl({"trust_ssl": "1"}) is False


# --- _q ---


class TestQ:
    def test_space(self):
        assert backend._q("a b") == "a%20b"

    def test_slash_and_at(self):
        assert backend._q("user@pam") == "user%40pam"
        assert backend._q("a/b") == "a%2Fb"

    def test_non_string(self):
        assert backend._q(100) == "100"

    def test_safe_chars_kept(self):
        assert backend._q("a.b-c_d") == "a.b-c_d"


# --- _sanitize_error ---


class TestSanitizeError:
    def test_strips_url(self):
        msg = backend._sanitize_error(Exception("GET https://10.0.0.1:8006/api2/json failed"))
        assert "10.0.0.1" not in msg.replace("[host]", "")
        assert "https://" not in msg

    def test_strips_host_port(self):
        msg = backend._sanitize_error(Exception("connect to 192.168.1.10:8006"))
        assert "192.168.1.10" not in msg
        assert "[host]" in msg

    def test_truncates_long(self):
        msg = backend._sanitize_error(Exception("x" * 500))
        assert len(msg) == 153  # 150 + "..."
        assert msg.endswith("...")

    def test_short_preserved(self):
        assert backend._sanitize_error(Exception("boom")) == "boom"


# --- _close_proxmox / _cleanup_vv ---


class TestCloseAndCleanup:
    def test_close_proxmox_closes_session(self):
        sess = MagicMock()
        proxmox = SimpleNamespace(_store={"session": sess})
        backend._close_proxmox(proxmox)
        sess.close.assert_called_once()

    def test_close_proxmox_without_session(self):
        backend._close_proxmox(SimpleNamespace(_store={}))

    def test_close_proxmox_swallows_errors(self):
        sess = MagicMock()
        sess.close.side_effect = RuntimeError("closed twice")
        backend._close_proxmox(SimpleNamespace(_store={"session": sess}))

    def test_cleanup_vv_removes_file(self, tmp_path):
        f = tmp_path / "spice.vv"
        f.write_text("[virt-viewer]")
        backend._cleanup_vv(str(f))
        assert not f.exists()

    def test_cleanup_vv_missing_file(self, tmp_path):
        backend._cleanup_vv(str(tmp_path / "gone.vv"))

    def test_cleanup_vv_falsy(self):
        backend._cleanup_vv("")
        backend._cleanup_vv(None)


# --- _parse_disk_size ---


class TestParseDiskSize:
    def test_simple_gigabytes(self):
        assert backend._parse_disk_size("local-lvm:vm-100-disk-0,size=32G") == 32 * 1024**3

    def test_terabytes(self):
        assert backend._parse_disk_size("size=1T") == 1024**4

    def test_megabytes_and_kilobytes(self):
        assert backend._parse_disk_size("size=512M") == 512 * 1024**2
        assert backend._parse_disk_size("size=1024K") == 1024 * 1024  # 1 MiB

    def test_fractional(self):
        assert backend._parse_disk_size("size=1.5G") == int(1.5 * 1024**3)

    def test_multiple_sizes_summed(self):
        val = "scsi0,size=10G,scsi1,size=5G"
        assert backend._parse_disk_size(val) == 15 * 1024**3

    def test_no_size_key(self):
        assert backend._parse_disk_size("local-lvm:vm-100-disk-0") == 0

    def test_invalid_value(self):
        assert backend._parse_disk_size("size=abc") == 0

    def test_empty_value(self):
        assert backend._parse_disk_size("size=") == 0

    def test_non_string(self):
        assert backend._parse_disk_size(None) == 0
        assert backend._parse_disk_size(42) == 0


# --- create_admin_token ---


def _resp(status=200, payload=None):
    return SimpleNamespace(
        status_code=status,
        json=lambda: payload if payload is not None else {"data": {}},
        raise_for_status=lambda: (_ for _ in ()).throw(
            requests.HTTPError(f"{status} Error"))
        if status >= 400 else None,
    )


class FakeSession:
    def __init__(self, responses):
        self.verify = None
        self.headers = {}
        self.responses = list(responses)
        self.closed = False

    def post(self, url, **kwargs):
        return self.responses.pop(0)

    def put(self, url, **kwargs):
        return self.responses.pop(0)

    def close(self):
        self.closed = True


@pytest.fixture
def ticket_ok(monkeypatch):
    """Ticket endpoint returns valid ticket/csrf."""
    monkeypatch.setattr(
        requests, "post",
        lambda url, **kw: _resp(200, {"data": {"ticket": "TICKET",
                                               "CSRFPreventionToken": "CSRF"}}),
    )


class TestCreateAdminToken:
    def test_success(self, ticket_ok, monkeypatch):
        fake = FakeSession([_resp(200, {"data": {"value": "UUID-123"}})])
        monkeypatch.setattr(requests, "Session", lambda: fake)
        monkeypatch.setattr(requests, "get", lambda url, **kw: _resp(200, {}))
        result = backend.create_admin_token("pve.local", "root@pam", "pass")
        assert "error" not in result
        assert result["token_value"] == "UUID-123"
        assert result["user"] == "root@pam"
        assert result["token_name"].startswith("pvecenter-")
        assert fake.closed

    def test_post_and_put_both_fail(self, ticket_ok, monkeypatch):
        fake = FakeSession([_resp(400), _resp(400)])
        monkeypatch.setattr(requests, "Session", lambda: fake)
        result = backend.create_admin_token("pve.local", "root@pam", "pass")
        assert "error" in result
        assert "token_name" not in result

    def test_empty_token_value(self, ticket_ok, monkeypatch):
        fake = FakeSession([_resp(200, {"data": {}})])
        monkeypatch.setattr(requests, "Session", lambda: fake)
        result = backend.create_admin_token("pve.local", "root@pam", "pass")
        assert "error" in result

    def test_verify_fails(self, ticket_ok, monkeypatch):
        fake = FakeSession([_resp(200, {"data": {"value": "UUID"}})])
        monkeypatch.setattr(requests, "Session", lambda: fake)
        monkeypatch.setattr(requests, "get", lambda url, **kw: _resp(403))
        result = backend.create_admin_token("pve.local", "root@pam", "pass")
        assert "error" in result
        assert "not working" in result["error"]

    def test_bad_credentials(self, monkeypatch):
        monkeypatch.setattr(
            requests, "post",
            lambda url, **kw: _resp(401),
        )
        result = backend.create_admin_token("pve.local", "root@pam", "wrong")
        assert result == {"error": backend.tr("Invalid login or password")}

    def test_connection_error(self, monkeypatch):
        def boom(url, **kw):
            raise requests.ConnectionError("connection refused")

        monkeypatch.setattr(requests, "post", boom)
        result = backend.create_admin_token("pve.local", "root@pam", "pass")
        assert result == {"error": backend.tr("Cannot connect to {}").format("pve.local")}

    def test_generic_error(self, monkeypatch):
        def boom(url, **kw):
            raise ValueError("weird")

        monkeypatch.setattr(requests, "post", boom)
        result = backend.create_admin_token("pve.local", "root@pam", "pass")
        assert "error" in result


# --- delete_host_token ---


class TestDeleteHostToken:
    def test_success(self, monkeypatch):
        sess = MagicMock()
        monkeypatch.setattr(backend, "ProxmoxSession", lambda cfg, timeout=10: sess)
        api = MagicMock()
        monkeypatch.setattr(backend, "AccessAPI", lambda session: api)
        cfg = {"host": "10.0.0.1", "user": "root@pam", "token_name": "pvecenter-x"}
        assert backend.delete_host_token(cfg) is True
        api.delete_token.assert_called_once_with("root@pam", "pvecenter-x")
        sess.close.assert_called_once()

    def test_failure_returns_false(self, monkeypatch):
        sess = MagicMock()
        monkeypatch.setattr(backend, "ProxmoxSession", lambda cfg, timeout=10: sess)
        api = MagicMock()
        api.delete_token.side_effect = RuntimeError("nope")
        monkeypatch.setattr(backend, "AccessAPI", lambda session: api)
        assert backend.delete_host_token({"user": "u", "token_name": "t"}) is False
        sess.close.assert_called_once()


# --- BulkVmActionWorker ---


class TestBulkVmActionWorker:
    @staticmethod
    def _make_worker(monkeypatch, failures=None):
        """Build a bulk worker with mocked ProxmoxSession/VmAPI.

        failures: dict {vmid: exception} — those VMs raise in perform_action.
        Returns (worker, recorded) where recorded collects signal emissions.
        """
        sessions = []

        class FakeSession:
            def __init__(self, cfg, timeout=10):
                self.closed = False
                sessions.append(self)

            def close(self):
                self.closed = True

        calls = []

        def fake_perform_action(api_self, node, vmid, vm_type, action):
            calls.append((node, vmid, vm_type, action))
            if failures and vmid in failures:
                raise failures[vmid]

        class FakeVmAPI:
            def __init__(self, session):
                self.session = session

            perform_action = fake_perform_action

        monkeypatch.setattr(backend, "ProxmoxSession", FakeSession)
        monkeypatch.setattr(backend, "VmAPI", FakeVmAPI)

        targets = [
            {"host_cfg": {"name": "h1"}, "node": "n1", "vmid": v, "vm_type": "qemu"}
            for v in (100, 101, 102)
        ]
        worker = backend.BulkVmActionWorker(targets, "start")
        recorded = {"progress": [], "vm_done": [], "finished": []}
        worker.signals.progress.connect(
            lambda d, t, v: recorded["progress"].append((d, t, v)))
        worker.signals.vm_done.connect(
            lambda v, ok, m: recorded["vm_done"].append((v, ok, m)))
        worker.signals.finished.connect(lambda: recorded["finished"].append(True))
        return worker, recorded, calls, sessions

    def test_all_success(self, monkeypatch):
        worker, recorded, calls, sessions = self._make_worker(monkeypatch)
        worker.run()
        assert [c[1] for c in calls] == [100, 101, 102]
        assert all(c[3] == "start" for c in calls)
        assert all(ok for _v, ok, _m in recorded["vm_done"])
        assert recorded["finished"] == [True]
        assert recorded["progress"] == [(0, 3, 100), (1, 3, 101), (2, 3, 102)]
        assert all(s.closed for s in sessions)
        assert not worker.was_cancelled

    def test_partial_failure_continues(self, monkeypatch):
        failures = {101: RuntimeError("vm locked")}
        worker, recorded, calls, _sessions = self._make_worker(
            monkeypatch, failures=failures)
        worker.run()
        assert [c[1] for c in calls] == [100, 101, 102]  # loop continues
        results = {v: ok for v, ok, _m in recorded["vm_done"]}
        assert results == {100: True, 101: False, 102: True}
        _v, ok, msg = next(r for r in recorded["vm_done"] if not r[1])
        assert "locked" in msg

    def test_cancel_stops_loop(self, monkeypatch):
        worker, recorded, calls, _sessions = self._make_worker(monkeypatch)
        worker.cancel()
        worker.run()
        assert calls == []
        assert recorded["vm_done"] == []
        assert worker.was_cancelled
        assert recorded["finished"] == [True]

    def test_cancel_midway(self, monkeypatch):
        worker, recorded, calls, _sessions = self._make_worker(monkeypatch)
        state = {"count": 0}

        def fake_perform(api_self, node, vmid, vm_type, action):
            state["count"] += 1
            if state["count"] >= 2:
                worker.cancel()
            calls.append((node, vmid, vm_type, action))

        monkeypatch.setattr(backend.VmAPI, "perform_action", fake_perform)
        worker.run()
        # VM 100 done, VM 101 triggers cancel mid-run but still completes it;
        # VM 102 skipped
        assert [c[1] for c in calls] == [100, 101]
        assert worker.was_cancelled
        assert recorded["finished"] == [True]

    def test_empty_targets(self, monkeypatch):
        monkeypatch.setattr(backend, "ProxmoxSession", MagicMock())
        worker = backend.BulkVmActionWorker([], "start")
        recorded = {"finished": []}
        worker.signals.finished.connect(lambda: recorded["finished"].append(True))
        worker.run()
        assert recorded["finished"] == [True]
        assert not worker.was_cancelled
