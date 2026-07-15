"""Tests for the Node domain model."""

from __future__ import annotations

import pytest

from pve_center.domain import Node, NodeStatus

# --- Fixtures ---


CLUSTER_NODE_DICT = {
    "node": "pve01",
    "status": "online",
    "cpu": 0.42,
    "sockets": 2,
    "mem": 8589934592,        # 8 GiB
    "maxmem": 17179869184,    # 16 GiB
    "disk": 1073741824,       # 1 GiB
    "maxdisk": 53687091200,   # 50 GiB
    "uptime": 466560,         # 5d 9h 36m
    "pveversion": "pve-manager/8.2.4/abc123",
    "kernel": "Linux 6.8.12",
    "qemu": "8.2.0",
    "lxctype": "6.0",
}

STANDALONE_NODE_DICT = {
    "node": "host07",
    "status": "offline",
    "cpu": 0,
    "sockets": 1,
    "mem": 0,
    "maxmem": 0,
    "disk": 0,
    "maxdisk": 0,
    "uptime": 0,
    "pveversion": "",
    "kernel": "",
    "qemu": "",
    "lxctype": "",
}

ERROR_NODE_DICT = {
    "node": "host09",
    "status": "error",
    "error": "Connection refused",
    "cpu": 0,
    "sockets": 0,
    "mem": 0,
    "maxmem": 0,
    "disk": 0,
    "maxdisk": 0,
    "uptime": 0,
    "pveversion": "",
    "kernel": "",
    "qemu": "",
    "lxctype": "",
}


# --- from_pve: basic construction ---


class TestFromPveBasic:
    def test_cluster_node_all_fields(self):
        n = Node.from_pve(CLUSTER_NODE_DICT, "h1", "ros", is_cluster=True)
        assert n.host_name == "h1"
        assert n.node == "pve01"
        assert n.cluster == "ros"
        assert n.status is NodeStatus.ONLINE
        assert n.error == ""
        assert n.cpu_fraction == pytest.approx(0.42)
        assert n.cpu_sockets == 2
        assert n.mem_bytes == 8589934592
        assert n.maxmem_bytes == 17179869184
        assert n.disk_bytes == 1073741824
        assert n.maxdisk_bytes == 53687091200
        assert n.uptime_seconds == 466560
        assert n.pve_version_raw == "pve-manager/8.2.4/abc123"
        assert n.kernel_version == "Linux 6.8.12"
        assert n.qemu_version == "8.2.0"
        assert n.lxc_version == "6.0"
        assert n.is_cluster is True

    def test_standalone_node(self):
        n = Node.from_pve(STANDALONE_NODE_DICT, "h7", "", is_cluster=False)
        assert n.host_name == "h7"
        assert n.node == "host07"
        assert n.cluster == ""
        assert n.status is NodeStatus.OFFLINE
        assert n.is_cluster is False

    def test_error_node(self):
        n = Node.from_pve(ERROR_NODE_DICT, "h9", "", is_cluster=False)
        assert n.status is NodeStatus.ERROR
        assert n.error == "Connection refused"

    def test_is_cluster_default_false(self):
        n = Node.from_pve(CLUSTER_NODE_DICT, "h1", "ros")
        assert n.is_cluster is False


# --- from_pve: missing / weird fields ---


class TestFromPveMissing:
    def test_empty_dict(self):
        n = Node.from_pve({}, "h1", "ros")
        assert n.node == ""
        assert n.status is NodeStatus.UNKNOWN
        assert n.cpu_fraction == 0.0
        assert n.cpu_sockets == 0
        assert n.mem_bytes == 0
        assert n.maxmem_bytes == 0
        assert n.uptime_seconds == 0
        assert n.pve_version_raw == ""
        assert n.error == ""

    def test_none_values(self):
        d = {"node": "pve02", "status": "online", "cpu": None, "mem": None,
             "maxmem": None, "uptime": None, "sockets": None}
        n = Node.from_pve(d, "h1", "ros")
        assert n.cpu_fraction == 0.0
        assert n.mem_bytes == 0
        assert n.maxmem_bytes == 0
        assert n.uptime_seconds == 0
        assert n.cpu_sockets == 0

    def test_int_cpu(self):
        """PVE sometimes returns cpu as int 0 instead of float."""
        n = Node.from_pve({"node": "pve03", "status": "online", "cpu": 0}, "h1", "")
        assert n.cpu_fraction == 0.0
        assert n.cpu_pct == 0.0

    def test_missing_status(self):
        n = Node.from_pve({"node": "pve04"}, "h1", "")
        assert n.status is NodeStatus.UNKNOWN


# --- computed properties ---


class TestComputedProperties:
    def test_cpu_pct_float(self):
        n = Node.from_pve(CLUSTER_NODE_DICT, "h1", "ros")
        assert n.cpu_pct == pytest.approx(42.0)

    def test_cpu_pct_zero(self):
        n = Node.from_pve({"node": "x", "status": "online", "cpu": 0}, "h", "")
        assert n.cpu_pct == 0.0

    def test_cpu_pct_none(self):
        n = Node.from_pve({"node": "x", "status": "online", "cpu": None}, "h", "")
        assert n.cpu_pct == 0.0

    def test_cpu_pct_full(self):
        n = Node.from_pve({"node": "x", "status": "online", "cpu": 1.0}, "h", "")
        assert n.cpu_pct == pytest.approx(100.0)

    def test_mem_gib(self):
        n = Node.from_pve(CLUSTER_NODE_DICT, "h1", "ros")
        assert n.mem_gib == pytest.approx(8.0)
        assert n.maxmem_gib == pytest.approx(16.0)

    def test_mem_gib_zero(self):
        n = Node.from_pve(STANDALONE_NODE_DICT, "h7", "")
        assert n.mem_gib == 0.0
        assert n.maxmem_gib == 0.0

    def test_mem_pct(self):
        n = Node.from_pve(CLUSTER_NODE_DICT, "h1", "ros")
        # 8 GiB / 16 GiB = 50%
        assert n.mem_pct == 50

    def test_mem_pct_zero_total(self):
        n = Node.from_pve(STANDALONE_NODE_DICT, "h7", "")
        assert n.mem_pct == 0

    def test_disk_gib(self):
        n = Node.from_pve(CLUSTER_NODE_DICT, "h1", "ros")
        assert n.disk_gib == pytest.approx(1.0, abs=0.01)
        assert n.maxdisk_gib == pytest.approx(50.0, abs=0.01)

    def test_uptime_str(self):
        n = Node.from_pve(CLUSTER_NODE_DICT, "h1", "ros")
        # 466560 = 5d 9h 36m
        assert "5d" in n.uptime_str
        assert "9h" in n.uptime_str
        assert "36m" in n.uptime_str

    def test_uptime_str_zero(self):
        n = Node.from_pve(STANDALONE_NODE_DICT, "h7", "")
        assert n.uptime_str == "—"

    def test_pve_version(self):
        n = Node.from_pve(CLUSTER_NODE_DICT, "h1", "ros")
        assert n.pve_version == "abc123"

    def test_pve_version_no_slash(self):
        n = Node.from_pve({"node": "x", "status": "online",
                            "pveversion": "8.3.0"}, "h", "")
        assert n.pve_version == "8.3.0"

    def test_pve_version_empty(self):
        n = Node.from_pve(STANDALONE_NODE_DICT, "h7", "")
        assert n.pve_version == ""

    def test_display_name_cluster(self):
        n = Node.from_pve(CLUSTER_NODE_DICT, "h1", "ros")
        assert n.display_name == "pve01@ros"

    def test_display_name_standalone(self):
        n = Node.from_pve(STANDALONE_NODE_DICT, "h7", "")
        assert n.display_name == "host07"


# --- status_color ---


class TestStatusColor:
    def test_online(self):
        n = Node.from_pve({"node": "x", "status": "online"}, "h", "")
        assert n.status_color == "ok"

    def test_offline(self):
        n = Node.from_pve({"node": "x", "status": "offline"}, "h", "")
        assert n.status_color == "off"

    def test_error(self):
        n = Node.from_pve({"node": "x", "status": "error"}, "h", "")
        assert n.status_color == "err"

    def test_unknown(self):
        n = Node.from_pve({"node": "x", "status": "weird"}, "h", "")
        assert n.status_color == "warn"


# --- frozen ---


class TestFrozen:
    def test_immutable(self):
        n = Node.from_pve(CLUSTER_NODE_DICT, "h1", "ros")
        with pytest.raises(AttributeError):
            n.cpu_fraction = 0.99  # type: ignore[misc]

    def test_hashable(self):
        n1 = Node.from_pve(CLUSTER_NODE_DICT, "h1", "ros")
        n2 = Node.from_pve(CLUSTER_NODE_DICT, "h1", "ros")
        assert n1 == n2
        assert hash(n1) == hash(n2)
        assert len({n1, n2}) == 1
