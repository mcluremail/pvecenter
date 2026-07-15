"""Tests for the provider layer — errors, session, API modules.

Uses mock objects to simulate proxmoxer responses without real PVE connections.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pve_center.provider import (
    AccessAPI,
    ClusterAPI,
    NodeAPI,
    PoolAPI,
    ProxmoxApiError,
    ProxmoxAuthError,
    ProxmoxError,
    ProxmoxNetworkError,
    ProxmoxNotFoundError,
    ProxmoxPermissionError,
    ProxmoxSession,
    ProxmoxTimeoutError,
    RrdAPI,
    StorageAPI,
    TaskAPI,
    VmAPI,
    from_exception,
    sanitize,
)

# -- _errors tests --


class TestErrors:
    def test_hierarchy(self):
        assert issubclass(ProxmoxAuthError, ProxmoxError)
        assert issubclass(ProxmoxNetworkError, ProxmoxError)
        assert issubclass(ProxmoxTimeoutError, ProxmoxError)
        assert issubclass(ProxmoxNotFoundError, ProxmoxError)
        assert issubclass(ProxmoxPermissionError, ProxmoxError)
        assert issubclass(ProxmoxApiError, ProxmoxError)

    def test_codes(self):
        assert ProxmoxError().code == "unknown"
        assert ProxmoxAuthError().code == "auth"
        assert ProxmoxNetworkError().code == "network"
        assert ProxmoxTimeoutError().code == "timeout"
        assert ProxmoxNotFoundError().code == "not_found"
        assert ProxmoxPermissionError().code == "permission"
        assert ProxmoxApiError("msg").code == "api"

    def test_api_error_status_code(self):
        err = ProxmoxApiError("bad request", status_code=400)
        assert err.status_code == 400

    def test_from_exception_passthrough(self):
        err = ProxmoxAuthError("denied")
        assert from_exception(err) is err

    def test_from_exception_timeout(self):
        assert isinstance(from_exception(TimeoutError("timed out")), ProxmoxTimeoutError)

    def test_from_exception_401(self):
        assert isinstance(from_exception(Exception("HTTP 401 Unauthorized")), ProxmoxAuthError)

    def test_from_exception_403(self):
        assert isinstance(from_exception(Exception("HTTP 403 Forbidden")), ProxmoxAuthError)

    def test_from_exception_404(self):
        assert isinstance(from_exception(Exception("HTTP 404 Not Found")), ProxmoxNotFoundError)

    def test_from_exception_permission(self):
        exc = Exception("permission check failed for VM.Console")
        assert isinstance(from_exception(exc), ProxmoxPermissionError)

    def test_from_exception_connection(self):
        exc = Exception("Connection refused")
        assert isinstance(from_exception(exc), ProxmoxNetworkError)

    def test_from_exception_ssl(self):
        exc = Exception("SSL certificate verification failed")
        assert isinstance(from_exception(exc), ProxmoxNetworkError)

    def test_from_exception_dns(self):
        exc = Exception("name resolution failed")
        assert isinstance(from_exception(exc), ProxmoxNetworkError)

    def test_from_exception_generic(self):
        exc = Exception("something went wrong")
        result = from_exception(exc)
        assert isinstance(result, ProxmoxApiError)
        assert result.code == "api"

    def test_sanitize_strips_url(self):
        msg = sanitize(Exception("GET https://10.0.0.1:8006/api2/json/nodes failed"))
        assert "https://" not in msg
        assert "[url]" in msg

    def test_sanitize_strips_host_port(self):
        msg = sanitize(Exception("connect to 10.0.0.1:8006 failed"))
        assert "10.0.0.1:8006" not in msg
        assert "[host]" in msg

    def test_sanitize_truncates(self):
        long_msg = "x" * 300
        msg = sanitize(Exception(long_msg))
        assert len(msg) <= 153
        assert msg.endswith("...")

    def test_sanitize_preserves_short(self):
        msg = sanitize(Exception("short error"))
        assert "short error" in msg


# -- _session tests --


class TestSession:
    def _cfg(self, **overrides):
        cfg = {
            "host": "pve.example.com",
            "user": "root@pam",
            "token_name": "test",
            "token_value": "secret",
            "trust_ssl": False,
        }
        cfg.update(overrides)
        return cfg

    def test_session_init(self):
        s = ProxmoxSession(self._cfg(), timeout=10)
        assert s.timeout == 10
        assert s.host == "pve.example.com"
        assert s._proxmox is None

    def test_session_lazy_proxmox(self):
        with patch("pve_center.provider._session.ProxmoxAPI") as mock_px:
            mock_inst = MagicMock()
            mock_store = {}
            mock_inst._store = mock_store
            mock_px.return_value = mock_inst

            s = ProxmoxSession(self._cfg(), timeout=10)
            _ = s.proxmox
            assert s._proxmox is mock_inst
            mock_px.assert_called_once()

    def test_session_close_idempotent(self):
        s = ProxmoxSession(self._cfg())
        s._proxmox = MagicMock()
        s._proxmox._store = {"session": MagicMock()}
        s.close()
        s.close()
        assert s._closed

    def test_session_context_manager(self):
        s = ProxmoxSession(self._cfg())
        s._proxmox = MagicMock()
        s._proxmox._store = {"session": MagicMock()}
        with s:
            pass
        assert s._closed

    def test_session_auth_header(self):
        s = ProxmoxSession(self._cfg())
        assert s.auth_header == "PVEAPIToken=root@pam!test=secret"

    def test_session_verify_ssl_strict(self):
        s = ProxmoxSession(self._cfg(trust_ssl=False))
        assert s.verify is True

    def test_session_verify_ssl_trust(self):
        s = ProxmoxSession(self._cfg(trust_ssl=True))
        assert s.verify is False

    def test_session_base_url(self):
        s = ProxmoxSession(self._cfg())
        assert s.base_url == "https://pve.example.com:8006/api2/json"

    def test_session_call_passes_through(self):
        s = ProxmoxSession(self._cfg())
        mock_fn = MagicMock(return_value="ok")
        result = s.call(mock_fn, "arg", kw="val")
        assert result == "ok"
        mock_fn.assert_called_once_with("arg", kw="val")

    def test_session_call_converts_exception(self):
        s = ProxmoxSession(self._cfg())
        mock_fn = MagicMock(side_effect=Exception("HTTP 401 denied"))
        with pytest.raises(ProxmoxAuthError):
            s.call(mock_fn)

    def test_session_call_preserves_proxmox_error(self):
        s = ProxmoxSession(self._cfg())
        mock_fn = MagicMock(side_effect=ProxmoxNotFoundError("gone"))
        with pytest.raises(ProxmoxNotFoundError):
            s.call(mock_fn)


# -- API module tests (mocked session) --


@pytest.fixture
def mock_session():
    session = MagicMock(spec=ProxmoxSession)
    session.proxmox = MagicMock()
    session.call = MagicMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw))
    session._s = session
    return session


class TestClusterAPI:
    def test_list_resources(self, mock_session):
        mock_session.proxmox.cluster.resources.get = MagicMock(return_value=[{"type": "node"}])
        api = ClusterAPI(mock_session)
        result = api.list_resources()
        assert result == [{"type": "node"}]

    def test_get_status(self, mock_session):
        mock_session.proxmox.cluster.status.get = MagicMock(return_value=[{"name": "n1"}])
        api = ClusterAPI(mock_session)
        assert api.get_status() == [{"name": "n1"}]

    def test_next_vmid_str(self, mock_session):
        mock_session.proxmox.cluster.nextid.get = MagicMock(return_value="101")
        api = ClusterAPI(mock_session)
        assert api.next_vmid() == 101

    def test_next_vmid_dict(self, mock_session):
        mock_session.proxmox.cluster.nextid.get = MagicMock(return_value={"data": 102})
        api = ClusterAPI(mock_session)
        assert api.next_vmid() == 102

    def test_list_ha_groups(self, mock_session):
        mock_session.proxmox.cluster.ha.groups.get = MagicMock(return_value=[{"group": "g1"}])
        api = ClusterAPI(mock_session)
        assert api.list_ha_groups() == [{"group": "g1"}]

    def test_add_ha_resource(self, mock_session):
        mock_session.proxmox.cluster.ha.resources.post = MagicMock(return_value="OK")
        api = ClusterAPI(mock_session)
        api.add_ha_resource(sid="vm:100", group="g1")
        mock_session.proxmox.cluster.ha.resources.post.assert_called_once_with(
            sid="vm:100", group="g1"
        )

    def test_delete_ha_resource(self, mock_session):
        chain = mock_session.proxmox.cluster.ha.resources
        chain.return_value.delete = MagicMock(return_value=None)
        api = ClusterAPI(mock_session)
        api.delete_ha_resource("vm:100")
        chain.assert_called_with("vm%3A100")

    def test_list_all_jobs_pve8(self, mock_session):
        mock_session.proxmox.cluster.jobs.get = MagicMock(
            return_value=[{"type": "vzdump", "id": "job1"}]
        )
        api = ClusterAPI(mock_session)
        result = api.list_all_jobs(pve_major=8)
        assert len(result) == 1
        assert result[0]["type"] == "vzdump"

    def test_list_all_jobs_pve8_fallback(self, mock_session):
        mock_session.proxmox.cluster.jobs.get = MagicMock(side_effect=Exception("no jobs"))
        mock_session.proxmox.cluster.backup.get = MagicMock(return_value=[{"id": "bk1"}])
        api = ClusterAPI(mock_session)
        result = api.list_all_jobs(pve_major=8)
        assert len(result) == 1

    def test_list_all_jobs_pve7(self, mock_session):
        mock_session.proxmox.cluster.backup.get = MagicMock(return_value=[{"id": "bk1"}])
        api = ClusterAPI(mock_session)
        result = api.list_all_jobs(pve_major=7)
        assert len(result) == 1

    def test_create_backup_job_pve8(self, mock_session):
        mock_session.proxmox.cluster.jobs.post = MagicMock(return_value="OK")
        api = ClusterAPI(mock_session)
        api.create_backup_job({"storage": "local"}, pve_major=8)
        mock_session.proxmox.cluster.jobs.post.assert_called_once()

    def test_delete_backup_job_pve8_fallback(self, mock_session):
        chain_j = mock_session.proxmox.cluster.jobs
        chain_j.return_value.delete = MagicMock(side_effect=Exception("fail"))
        chain_b = mock_session.proxmox.cluster.backup
        chain_b.return_value.delete = MagicMock(return_value=None)
        api = ClusterAPI(mock_session)
        api.delete_backup_job("job1", pve_major=8)
        chain_b.assert_called_with("job1")


class TestNodeAPI:
    def test_list(self, mock_session):
        mock_session.proxmox.nodes.get = MagicMock(return_value=[{"node": "n1"}])
        api = NodeAPI(mock_session)
        assert api.list() == [{"node": "n1"}]

    def test_get_status(self, mock_session):
        chain = mock_session.proxmox.nodes
        chain.return_value.status.get = MagicMock(return_value={"pveversion": "8.1"})
        api = NodeAPI(mock_session)
        result = api.get_status("n1")
        assert result["pveversion"] == "8.1"
        chain.assert_called_with("n1")

    def test_get_version(self, mock_session):
        chain = mock_session.proxmox.nodes
        chain.return_value.version.get = MagicMock(return_value={"qemu": "8.0"})
        api = NodeAPI(mock_session)
        assert api.get_version("n1") == {"qemu": "8.0"}

    def test_list_storage(self, mock_session):
        chain = mock_session.proxmox.nodes
        chain.return_value.storage.get = MagicMock(return_value=[{"storage": "local"}])
        api = NodeAPI(mock_session)
        assert api.list_storage("n1") == [{"storage": "local"}]

    def test_list_tasks(self, mock_session):
        chain = mock_session.proxmox.nodes
        chain.return_value.tasks.get = MagicMock(return_value=[{"upid": "UPID:1"}])
        api = NodeAPI(mock_session)
        result = api.list_tasks("n1", limit=50)
        assert len(result) == 1
        chain.return_value.tasks.get.assert_called_once_with(limit=50)

    def test_apply_network(self, mock_session):
        chain = mock_session.proxmox.nodes
        chain.return_value.network.put = MagicMock(return_value=None)
        api = NodeAPI(mock_session)
        api.apply_network("n1")
        chain.return_value.network.put.assert_called_once()


class TestVmAPI:
    def test_get_config_qemu(self, mock_session):
        chain = mock_session.proxmox.nodes
        qemu_chain = chain.return_value.qemu
        qemu_chain.return_value.config.get = MagicMock(return_value={"name": "vm1"})
        api = VmAPI(mock_session)
        result = api.get_config("n1", 100, "qemu")
        assert result["name"] == "vm1"
        qemu_chain.assert_called_with("100")

    def test_get_config_lxc(self, mock_session):
        chain = mock_session.proxmox.nodes
        lxc_chain = chain.return_value.lxc
        lxc_chain.return_value.config.get = MagicMock(return_value={"hostname": "ct1"})
        api = VmAPI(mock_session)
        result = api.get_config("n1", 200, "lxc")
        assert result["hostname"] == "ct1"

    def test_perform_action(self, mock_session):
        chain = mock_session.proxmox.nodes
        qemu_chain = chain.return_value.qemu
        status_mock = qemu_chain.return_value.status
        status_mock.start.post = MagicMock(return_value="OK")
        api = VmAPI(mock_session)
        api.perform_action("n1", 100, "qemu", "start")
        status_mock.start.post.assert_called_once()

    def test_resize_disk_qemu(self, mock_session):
        chain = mock_session.proxmox.nodes
        qemu_chain = chain.return_value.qemu
        qemu_chain.return_value.resize.put = MagicMock(return_value="OK")
        api = VmAPI(mock_session)
        api.resize_disk("n1", 100, "qemu", "scsi0", "+10G")
        qemu_chain.return_value.resize.put.assert_called_once_with(
            disk="scsi0", size="%2B10G"
        )

    def test_resize_disk_lxc(self, mock_session):
        chain = mock_session.proxmox.nodes
        lxc_chain = chain.return_value.lxc
        lxc_chain.return_value.resize.put = MagicMock(return_value="OK")
        api = VmAPI(mock_session)
        api.resize_disk("n1", 200, "lxc", "rootfs", "20G")
        lxc_chain.return_value.resize.put.assert_called_once_with(
            volume="rootfs", size="20G"
        )

    def test_move_disk_qemu(self, mock_session):
        chain = mock_session.proxmox.nodes
        qemu_chain = chain.return_value.qemu
        qemu_chain.return_value.move_disk.post = MagicMock(return_value="UPID:123")
        api = VmAPI(mock_session)
        api.move_disk("n1", 100, "qemu", "scsi0", "local-lvm", delete=True)
        qemu_chain.return_value.move_disk.post.assert_called_once_with(
            disk="scsi0", storage="local-lvm", delete=1
        )

    def test_create_qemu(self, mock_session):
        chain = mock_session.proxmox.nodes
        chain.return_value.qemu.post = MagicMock(return_value="UPID:123")
        api = VmAPI(mock_session)
        api.create_qemu("n1", vmid=100, name="test")
        chain.return_value.qemu.post.assert_called_once_with(vmid=100, name="test")

    def test_delete(self, mock_session):
        chain = mock_session.proxmox.nodes
        qemu_chain = chain.return_value.qemu
        qemu_chain.return_value.delete = MagicMock(return_value=None)
        api = VmAPI(mock_session)
        api.delete("n1", 100, "qemu", purge=True)
        qemu_chain.return_value.delete.assert_called_once_with(purge=1)

    def test_migrate(self, mock_session):
        chain = mock_session.proxmox.nodes
        qemu_chain = chain.return_value.qemu
        qemu_chain.return_value.migrate.post = MagicMock(return_value="UPID:123")
        api = VmAPI(mock_session)
        api.migrate("n1", 100, "n2", with_local_disks=True)
        qemu_chain.return_value.migrate.post.assert_called_once_with(
            target="n2", **{"with-local-disks": 1}
        )

    def test_list_snapshots(self, mock_session):
        chain = mock_session.proxmox.nodes
        qemu_chain = chain.return_value.qemu
        qemu_chain.return_value.snapshot.get = MagicMock(
            return_value=[{"name": "snap1"}, {"name": "current"}]
        )
        api = VmAPI(mock_session)
        result = api.list_snapshots("n1", 100, "qemu")
        assert len(result) == 2

    def test_create_snapshot(self, mock_session):
        chain = mock_session.proxmox.nodes
        qemu_chain = chain.return_value.qemu
        qemu_chain.return_value.snapshot.post = MagicMock(return_value="UPID:123")
        api = VmAPI(mock_session)
        api.create_snapshot("n1", 100, "qemu", "snap1", description="test", vmstate=True)
        qemu_chain.return_value.snapshot.post.assert_called_once_with(
            snapname="snap1", description="test", vmstate=1
        )

    def test_get_vnc_proxy_lxc(self, mock_session):
        chain = mock_session.proxmox.nodes
        lxc_chain = chain.return_value.lxc
        lxc_chain.return_value.vncproxy.post = MagicMock(return_value={"port": 5900})
        api = VmAPI(mock_session)
        result = api.get_vnc_proxy("n1", 200, "lxc", "pve.host")
        assert result["port"] == 5900
        lxc_chain.return_value.vncproxy.post.assert_called_once_with(proxy="pve.host")

    def test_get_spice_proxy(self, mock_session):
        chain = mock_session.proxmox.nodes
        qemu_chain = chain.return_value.qemu
        qemu_chain.return_value.spiceproxy.post = MagicMock(return_value={"port": 6123})
        api = VmAPI(mock_session)
        result = api.get_spice_proxy("n1", 100, "pve.host")
        assert result["port"] == 6123


class TestStorageAPI:
    def test_list_content(self, mock_session):
        chain = mock_session.proxmox.nodes
        storage_chain = chain.return_value.storage
        storage_chain.return_value.content.get = MagicMock(
            return_value=[{"volid": "local:iso/test.iso"}]
        )
        api = StorageAPI(mock_session)
        result = api.list_content("n1", "local", content="iso")
        assert len(result) == 1
        storage_chain.return_value.content.get.assert_called_once_with(content="iso")

    def test_delete_content(self, mock_session):
        chain = mock_session.proxmox.nodes
        storage_chain = chain.return_value.storage
        content_chain = storage_chain.return_value.content
        content_chain.return_value.delete = MagicMock(return_value="UPID:123")
        api = StorageAPI(mock_session)
        api.delete_content("n1", "local", "local:iso/test.iso")
        content_chain.return_value.delete.assert_called_once()

    def test_move_content(self, mock_session):
        chain = mock_session.proxmox.nodes
        storage_chain = chain.return_value.storage
        content_chain = storage_chain.return_value.content
        content_chain.return_value.post = MagicMock(return_value="UPID:123")
        api = StorageAPI(mock_session)
        api.move_content(
            "n1", "local", "local:iso/test.iso", "fast", target_vmid=100, delete_source=True
        )
        content_chain.return_value.post.assert_called_once_with(
            target_storage="fast", target_vmid=100, delete=1
        )

    def test_download_url(self, mock_session):
        chain = mock_session.proxmox.nodes
        storage_chain = chain.return_value.storage
        storage_chain.return_value.post = MagicMock(return_value="UPID:123")
        api = StorageAPI(mock_session)
        api.download_url("n1", "local", url="http://test/iso", content="iso")
        storage_chain.return_value.post.assert_called_once()


class TestPoolAPI:
    def test_list(self, mock_session):
        mock_session.proxmox.pools.get = MagicMock(return_value=[{"poolid": "p1"}])
        api = PoolAPI(mock_session)
        assert api.list() == [{"poolid": "p1"}]

    def test_get(self, mock_session):
        chain = mock_session.proxmox.pools
        chain.return_value.get = MagicMock(return_value={"poolid": "p1", "members": []})
        api = PoolAPI(mock_session)
        result = api.get("p1")
        assert result["poolid"] == "p1"
        chain.assert_called_with("p1")


class TestTaskAPI:
    def test_list(self, mock_session):
        chain = mock_session.proxmox.nodes
        chain.return_value.tasks.get = MagicMock(return_value=[{"upid": "UPID:1"}])
        api = TaskAPI(mock_session)
        result = api.list("n1", limit=50)
        assert len(result) == 1
        chain.return_value.tasks.get.assert_called_once_with(limit=50)

    def test_get_status(self, mock_session):
        chain = mock_session.proxmox.nodes
        tasks_chain = chain.return_value.tasks
        tasks_chain.return_value.status.get = MagicMock(
            return_value={"data": {"status": "stopped", "exitstatus": "OK"}}
        )
        api = TaskAPI(mock_session)
        result = api.get_status("n1", "UPID:123")
        assert result["status"] == "stopped"

    def test_poll_finished(self, mock_session):
        chain = mock_session.proxmox.nodes
        tasks_chain = chain.return_value.tasks
        tasks_chain.return_value.status.get = MagicMock(
            return_value={"data": {"status": "stopped", "exitstatus": "OK"}}
        )
        api = TaskAPI(mock_session)
        status, exitstatus = api.poll("n1", "UPID:123", timeout=5, interval=0.01)
        assert status == "stopped"
        assert exitstatus == "OK"

    def test_poll_timeout(self, mock_session):
        chain = mock_session.proxmox.nodes
        tasks_chain = chain.return_value.tasks
        tasks_chain.return_value.status.get = MagicMock(
            return_value={"data": {"status": "running"}}
        )
        api = TaskAPI(mock_session)
        status, exitstatus = api.poll("n1", "UPID:123", timeout=0.1, interval=0.05)
        assert status == "timeout"


class TestRrdAPI:
    def test_get_vm_rrddata_qemu(self, mock_session):
        chain = mock_session.proxmox.nodes
        qemu_chain = chain.return_value.qemu
        qemu_chain.return_value.rrddata.get = MagicMock(return_value=[{"time": 1, "cpu": 0.5}])
        api = RrdAPI(mock_session)
        result = api.get_vm_rrddata("n1", 100, "qemu", "hour")
        assert len(result) == 1
        qemu_chain.return_value.rrddata.get.assert_called_once_with(
            timeframe="hour", cf="AVERAGE"
        )

    def test_get_node_rrddata(self, mock_session):
        chain = mock_session.proxmox.nodes
        chain.return_value.rrddata.get = MagicMock(return_value=[{"time": 1}])
        api = RrdAPI(mock_session)
        api.get_node_rrddata("n1", "hour")
        chain.return_value.rrddata.get.assert_called_once_with(
            timeframe="hour", cf="AVERAGE"
        )

    def test_get_storage_rrddata(self, mock_session):
        chain = mock_session.proxmox.nodes
        storage_chain = chain.return_value.storage
        storage_chain.return_value.rrddata.get = MagicMock(return_value=[{"time": 1}])
        api = RrdAPI(mock_session)
        api.get_storage_rrddata("n1", "local", "hour")
        storage_chain.return_value.rrddata.get.assert_called_once_with(
            timeframe="hour", cf="AVERAGE"
        )


class TestAccessAPI:
    def test_list_users(self, mock_session):
        mock_session.proxmox.access.users.get = MagicMock(return_value=[{"userid": "u1"}])
        api = AccessAPI(mock_session)
        api.list_users()
        mock_session.proxmox.access.users.get.assert_called_once_with(full=1)

    def test_create_user(self, mock_session):
        mock_session.proxmox.access.users.post = MagicMock(return_value=None)
        api = AccessAPI(mock_session)
        api.create_user(userid="u1@pam")
        mock_session.proxmox.access.users.post.assert_called_once_with(userid="u1@pam")

    def test_delete_user(self, mock_session):
        chain = mock_session.proxmox.access.users
        chain.return_value.delete = MagicMock(return_value=None)
        api = AccessAPI(mock_session)
        api.delete_user("u1@pam")
        chain.assert_called_with("u1%40pam")

    def test_list_tokens(self, mock_session):
        chain = mock_session.proxmox.access.users
        chain.return_value.token.get = MagicMock(return_value=[{"id": "t1"}])
        api = AccessAPI(mock_session)
        result = api.list_tokens("u1@pam")
        assert len(result) == 1

    def test_create_token(self, mock_session):
        chain = mock_session.proxmox.access.users
        token_chain = chain.return_value.token
        token_chain.return_value.post = MagicMock(
            return_value={"full-tokenid": "u1@pam!t1", "value": "secret"}
        )
        api = AccessAPI(mock_session)
        result = api.create_token("u1@pam", "t1", comment="test")
        assert result["value"] == "secret"

    def test_list_groups(self, mock_session):
        mock_session.proxmox.access.groups.get = MagicMock(return_value=[{"groupid": "g1"}])
        api = AccessAPI(mock_session)
        assert api.list_groups() == [{"groupid": "g1"}]

    def test_list_roles(self, mock_session):
        mock_session.proxmox.access.roles.get = MagicMock(return_value=[{"roleid": "r1"}])
        api = AccessAPI(mock_session)
        assert api.list_roles() == [{"roleid": "r1"}]

    def test_list_acl(self, mock_session):
        mock_session.proxmox.access.acl.get = MagicMock(return_value=[{"path": "/"}])
        api = AccessAPI(mock_session)
        assert api.list_acl() == [{"path": "/"}]

    def test_update_acl(self, mock_session):
        mock_session.proxmox.access.acl.put = MagicMock(return_value=None)
        api = AccessAPI(mock_session)
        api.update_acl(path="/", roles="Administrator", delete=0)
        mock_session.proxmox.access.acl.put.assert_called_once_with(
            path="/", roles="Administrator", delete=0
        )
