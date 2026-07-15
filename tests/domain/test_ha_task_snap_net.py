"""Tests for HaGroup, HaResource, Task, Snapshot, and NetworkInterface models."""

from __future__ import annotations

from pve_center.domain import HaGroup, HaResource, NetworkInterface, Snapshot, Task

# --- HaGroup ---

HA_GROUP_DICT = {
    "group": "my-ha-group",
    "nodes": "pve01,pve02,pve03",
    "restricted": 1,
    "nofailback": 0,
    "comment": "Production HA",
    "digest": "abc123",
}


class TestHaGroupFromPve:
    def test_all_fields(self):
        g = HaGroup.from_pve(HA_GROUP_DICT)
        assert g.group == "my-ha-group"
        assert g.nodes == "pve01,pve02,pve03"
        assert g.restricted is True
        assert g.nofailback is False
        assert g.comment == "Production HA"
        assert g.digest == "abc123"

    def test_empty(self):
        g = HaGroup.from_pve({})
        assert g.group == ""
        assert g.node_list == []

    def test_node_list(self):
        g = HaGroup.from_pve(HA_GROUP_DICT)
        assert g.node_list == ["pve01", "pve02", "pve03"]


# --- HaResource ---

HA_RESOURCE_DICT = {
    "sid": "vm:100",
    "group": "my-ha-group",
    "state": "started",
    "max_restart": 3,
    "max_relocate": 1,
    "comment": "Critical VM",
}


class TestHaResourceFromPve:
    def test_all_fields(self):
        r = HaResource.from_pve(HA_RESOURCE_DICT)
        assert r.sid == "vm:100"
        assert r.group == "my-ha-group"
        assert r.state == "started"
        assert r.max_restart == 3
        assert r.max_relocate == 1
        assert r.comment == "Critical VM"

    def test_defaults(self):
        r = HaResource.from_pve({"sid": "vm:200"})
        assert r.max_restart == 1
        assert r.max_relocate == 1

    def test_vmid_extraction(self):
        r = HaResource.from_pve(HA_RESOURCE_DICT)
        assert r.vmid == 100

    def test_vmid_none(self):
        r = HaResource.from_pve({"sid": "storage:nfs"})
        assert r.vmid is None

    def test_vmid_malformed(self):
        r = HaResource.from_pve({"sid": "vm:abc"})
        assert r.vmid is None


# --- Task ---

TASK_DICT = {
    "upid": "UPID:pve01:0001:0002:1700000000:qmstart:100:root@pam:",
    "node": "pve01",
    "type": "qmstart",
    "status": "OK",
    "starttime": 1700000000,
    "endtime": 1700000010,
    "user": "root@pam",
    "vmid": 100,
}

TASK_RUNNING_DICT = {
    "upid": "UPID:pve02:0001:0002:1700000100:vzdump:200:root@pam:",
    "node": "pve02",
    "type": "vzdump",
    "status": "RUNNING",
    "starttime": 1700000100,
    "user": "root@pam",
}


class TestTaskFromPve:
    def test_all_fields(self):
        t = Task.from_pve(TASK_DICT)
        assert t.upid == TASK_DICT["upid"]
        assert t.node == "pve01"
        assert t.task_type == "qmstart"
        assert t.status == "OK"
        assert t.starttime == 1700000000.0
        assert t.endtime == 1700000010.0
        assert t.user == "root@pam"
        assert t.vmid == 100

    def test_running(self):
        t = Task.from_pve(TASK_RUNNING_DICT)
        assert t.is_running is True
        assert t.is_ok is False

    def test_ok(self):
        t = Task.from_pve(TASK_DICT)
        assert t.is_ok is True
        assert t.is_running is False

    def test_duration(self):
        t = Task.from_pve(TASK_DICT)
        assert t.duration_seconds == 10.0

    def test_duration_zero(self):
        t = Task.from_pve(TASK_RUNNING_DICT)
        assert t.duration_seconds == 0.0

    def test_empty_dict(self):
        t = Task.from_pve({})
        assert t.upid == ""
        assert t.vmid is None

    def test_vmid_from_upid(self):
        d = {"upid": "UPID:pve01:0001:0002:1700000000:qmstart:42:root@pam:"}
        t = Task.from_pve(d)
        assert t.vmid == 42

    def test_vmid_from_id_field(self):
        t = Task.from_pve({"id": 300, "upid": ""})
        assert t.vmid == 300


# --- Snapshot ---

SNAPSHOT_DICT = {
    "name": "pre-update",
    "description": "Before OS update",
    "snaptime": 1700000000,
    "parent": "base",
    "vmstate": 1,
    "size": 2147483648,  # 2 GiB
}

SNAPSHOT_ROOT_DICT = {
    "name": "base",
    "description": "",
    "snaptime": 1699000000,
    "parent": "",
    "vmstate": 0,
    "size": 0,
}

SNAPSHOT_HOST_DICT = {
    "name": "auto-backup",
    "description": "Auto",
    "snaptime": 1700000000,
    "parent": "base",
    "vmstate": 0,
    "size": 0,
    "vmid": 100,
    "vm_name": "web-server",
    "host_name": "h1",
    "node": "pve01",
}


class TestSnapshotFromPve:
    def test_all_fields(self):
        s = Snapshot.from_pve(SNAPSHOT_DICT)
        assert s.name == "pre-update"
        assert s.description == "Before OS update"
        assert s.snaptime == 1700000000
        assert s.parent == "base"
        assert s.vmstate is True
        assert s.size_bytes == 2147483648

    def test_root_snapshot(self):
        s = Snapshot.from_pve(SNAPSHOT_ROOT_DICT)
        assert s.is_root is True
        assert s.vmstate is False

    def test_is_root_false(self):
        s = Snapshot.from_pve(SNAPSHOT_DICT)
        assert s.is_root is False

    def test_is_root_current_parent(self):
        s = Snapshot.from_pve({"name": "snap1", "parent": "current"})
        assert s.is_root is True

    def test_host_snapshot_synthetic_fields(self):
        s = Snapshot.from_pve(SNAPSHOT_HOST_DICT)
        assert s.vmid == 100
        assert s.vm_name == "web-server"
        assert s.host_name == "h1"
        assert s.node == "pve01"

    def test_vm_snapshot_no_synthetic(self):
        s = Snapshot.from_pve(SNAPSHOT_DICT)
        assert s.vmid == 0
        assert s.vm_name == ""

    def test_size_str(self):
        s = Snapshot.from_pve(SNAPSHOT_DICT)
        assert "GiB" in s.size_str

    def test_size_str_zero(self):
        s = Snapshot.from_pve(SNAPSHOT_ROOT_DICT)
        assert s.size_str == "—"

    def test_empty_dict(self):
        s = Snapshot.from_pve({})
        assert s.name == ""
        assert s.snaptime == 0
        assert s.is_root is True


# --- NetworkInterface ---

NET_IFACE_DICT = {
    "iface": "eth0",
    "type": "eth",
    "active": 1,
    "method": "static",
    "address": "192.168.1.10",
    "netmask": "255.255.255.0",
    "gateway": "192.168.1.1",
    "bridge_ports": "",
    "vlan_id": 100,
    "mtu": 1500,
    "pending": 0,
    "autostart": 1,
}

BRIDGE_DICT = {
    "iface": "vmbr0",
    "type": "bridge",
    "active": 1,
    "method": "manual",
    "bridge_ports": "eth0,eth1",
    "pending": 1,
}


class TestNetworkInterfaceFromPve:
    def test_all_fields(self):
        ni = NetworkInterface.from_pve(NET_IFACE_DICT)
        assert ni.iface == "eth0"
        assert ni.iface_type == "eth"
        assert ni.active is True
        assert ni.method == "static"
        assert ni.address == "192.168.1.10"
        assert ni.netmask == "255.255.255.0"
        assert ni.gateway == "192.168.1.1"
        assert ni.vlan_id == "100"
        assert ni.mtu == "1500"
        assert ni.pending is False
        assert ni.autostart is True

    def test_bridge(self):
        ni = NetworkInterface.from_pve(BRIDGE_DICT)
        assert ni.iface_type == "bridge"
        assert ni.bridge_ports == "eth0,eth1"
        assert ni.bridge_port_list == ["eth0", "eth1"]
        assert ni.pending is True

    def test_addr_str_with_netmask(self):
        ni = NetworkInterface.from_pve(NET_IFACE_DICT)
        assert ni.addr_str == "192.168.1.10/255.255.255.0"

    def test_addr_str_no_netmask(self):
        ni = NetworkInterface.from_pve({"address": "10.0.0.1"})
        assert ni.addr_str == "10.0.0.1"

    def test_addr_str_empty(self):
        ni = NetworkInterface.from_pve({})
        assert ni.addr_str == ""

    def test_bridge_port_list_empty(self):
        ni = NetworkInterface.from_pve({})
        assert ni.bridge_port_list == []

    def test_vlan_id_as_string(self):
        ni = NetworkInterface.from_pve({"vlan_id": 200})
        assert ni.vlan_id == "200"

    def test_mtu_as_string(self):
        ni = NetworkInterface.from_pve({"mtu": 9000})
        assert ni.mtu == "9000"

    def test_empty_dict(self):
        ni = NetworkInterface.from_pve({})
        assert ni.iface == ""
        assert ni.active is False
        assert ni.vlan_id == ""
