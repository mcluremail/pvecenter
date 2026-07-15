"""Tests for the Vm domain model."""

from __future__ import annotations

import pytest

from pve_center.domain import Vm, VmStatus, VmType

VM_DICT = {
    "vmid": 100,
    "name": "web-server",
    "type": "qemu",
    "node": "pve01",
    "status": "running",
    "cpu": 0.35,
    "mem": 2147483648,       # 2 GiB
    "maxmem": 4294967296,    # 4 GiB
    "disk": 0,
    "maxdisk": 53687091200,  # 50 GiB
    "uptime": 93600,         # 1d 2h
    "netin": 104857600,      # 100 MiB
    "netout": 52428800,      # 50 MiB
    "diskread": 0,
    "diskwrite": 0,
    "template": 0,
    "tags": "prod;web",
    "hastate": "started",
    "pool": "web-pool",
}

LXC_DICT = {
    "vmid": 200,
    "name": "db-container",
    "type": "lxc",
    "node": "pve02",
    "status": "stopped",
    "cpu": 0,
    "mem": 0,
    "maxmem": 8589934592,
    "disk": 1073741824,  # 1 GiB
    "maxdisk": 17179869184,  # 16 GiB
    "uptime": 0,
    "netin": 0,
    "netout": 0,
    "diskread": 0,
    "diskwrite": 0,
}

MINIMAL_DICT = {"vmid": 300, "type": "qemu"}


class TestFromPveBasic:
    def test_qemu_all_fields(self):
        vm = Vm.from_pve(VM_DICT, "h1")
        assert vm.vmid == 100
        assert vm.name == "web-server"
        assert vm.vm_type is VmType.QEMU
        assert vm.node == "pve01"
        assert vm.host_name == "h1"
        assert vm.pool == "web-pool"
        assert vm.status is VmStatus.RUNNING
        assert vm.hastate == "started"
        assert vm.tags == "prod;web"
        assert vm.template is False
        assert vm.cpu_fraction == pytest.approx(0.35)

    def test_lxc_stopped(self):
        vm = Vm.from_pve(LXC_DICT, "h2")
        assert vm.vm_type is VmType.LXC
        assert vm.status is VmStatus.STOPPED
        assert vm.is_lxc is True
        assert vm.is_qemu is False

    def test_minimal_dict(self):
        vm = Vm.from_pve(MINIMAL_DICT, "h1")
        assert vm.vmid == 300
        assert vm.name == ""
        assert vm.status is VmStatus.UNKNOWN
        assert vm.cpu_fraction == 0.0

    def test_empty_dict(self):
        vm = Vm.from_pve({}, "h1")
        assert vm.vmid == 0
        assert vm.name == ""
        assert vm.vm_type is VmType.UNKNOWN
        assert vm.status is VmStatus.UNKNOWN

    def test_none_values(self):
        d = {"vmid": 1, "cpu": None, "mem": None, "maxmem": None, "uptime": None}
        vm = Vm.from_pve(d, "h")
        assert vm.cpu_fraction == 0.0
        assert vm.mem_bytes == 0
        assert vm.maxmem_bytes == 0
        assert vm.uptime_seconds == 0

    def test_template_true(self):
        vm = Vm.from_pve({"vmid": 1, "template": 1}, "h")
        assert vm.template is True


class TestComputedProperties:
    def test_cpu_pct(self):
        vm = Vm.from_pve(VM_DICT, "h1")
        assert vm.cpu_pct == pytest.approx(35.0)

    def test_cpu_pct_zero(self):
        vm = Vm.from_pve({"vmid": 1, "cpu": 0}, "h")
        assert vm.cpu_pct == 0.0

    def test_mem_gib(self):
        vm = Vm.from_pve(VM_DICT, "h1")
        assert vm.mem_gib == pytest.approx(2.0)
        assert vm.maxmem_gib == pytest.approx(4.0)

    def test_mem_pct(self):
        vm = Vm.from_pve(VM_DICT, "h1")
        assert vm.mem_pct == 50

    def test_disk_gib_lxc(self):
        vm = Vm.from_pve(LXC_DICT, "h2")
        assert vm.disk_gib == pytest.approx(1.0)
        assert vm.maxdisk_gib == pytest.approx(16.0)

    def test_disk_pct_lxc(self):
        vm = Vm.from_pve(LXC_DICT, "h2")
        assert vm.disk_pct == 6  # 1/16 ~ 6%

    def test_disk_zero_qemu(self):
        vm = Vm.from_pve(VM_DICT, "h1")
        assert vm.disk_gib == 0.0
        assert vm.disk_pct == 0

    def test_netin_mib(self):
        vm = Vm.from_pve(VM_DICT, "h1")
        assert vm.netin_mib == pytest.approx(100.0)
        assert vm.netout_mib == pytest.approx(50.0)

    def test_uptime_str(self):
        vm = Vm.from_pve(VM_DICT, "h1")
        assert "1d" in vm.uptime_str

    def test_uptime_str_zero(self):
        vm = Vm.from_pve(LXC_DICT, "h2")
        assert vm.uptime_str == "—"

    def test_display_name_with_name(self):
        vm = Vm.from_pve(VM_DICT, "h1")
        assert vm.display_name == "web-server"

    def test_display_name_without_name(self):
        vm = Vm.from_pve({"vmid": 42}, "h")
        assert vm.display_name == "VM 42"

    def test_status_color_running(self):
        vm = Vm.from_pve(VM_DICT, "h1")
        assert vm.status_color == "ok"

    def test_status_color_stopped(self):
        vm = Vm.from_pve(LXC_DICT, "h2")
        assert vm.status_color == "err"

    def test_status_color_paused(self):
        vm = Vm.from_pve({"vmid": 1, "status": "paused"}, "h")
        assert vm.status_color == "warn"

    def test_key(self):
        vm = Vm.from_pve(VM_DICT, "h1")
        assert vm.key == ("h1", 100)


class TestFrozen:
    def test_immutable(self):
        vm = Vm.from_pve(VM_DICT, "h1")
        with pytest.raises(AttributeError):
            vm.name = "other"

    def test_hashable(self):
        vm1 = Vm.from_pve(VM_DICT, "h1")
        vm2 = Vm.from_pve(VM_DICT, "h1")
        assert vm1 == vm2
        assert hash(vm1) == hash(vm2)
