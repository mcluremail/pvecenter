"""Tests for domain/bulk.py — bulk VM action planning."""

from pve_center.domain.bulk import BulkTarget, plan_bulk_action
from pve_center.domain.repositories import VmRepository


class FakeVm:
    """Minimal VM stub with dict-compat .get()."""

    def __init__(self, vmid, template=False, vm_type="qemu"):
        self._data = {"vmid": vmid, "template": template, "type": vm_type}

    def get(self, key, default=None):
        return self._data.get(key, default)


class FakeRepo:
    def __init__(self, vms):
        self._vms = {(v._data["vmid"]): v for v in vms}

    def get(self, host_name, vmid):
        return self._vms.get(vmid)


def test_all_valid_targets():
    repo = FakeRepo([FakeVm(100), FakeVm(101, vm_type="lxc")])
    keys = [("h1", 100, "n1"), ("h1", 101, "n1")]
    plan = plan_bulk_action(keys, repo, {"h1"})
    assert plan.targets == (
        BulkTarget("h1", "n1", 100, "qemu"),
        BulkTarget("h1", "n1", 101, "lxc"),
    )
    assert plan.skipped_count == 0


def test_templates_skipped():
    repo = FakeRepo([FakeVm(100), FakeVm(101, template=True)])
    keys = [("h1", 100, "n1"), ("h1", 101, "n1")]
    plan = plan_bulk_action(keys, repo, {"h1"})
    assert [t.vmid for t in plan.targets] == [100]
    assert plan.skipped_templates == (101,)


def test_missing_vm_skipped():
    repo = FakeRepo([FakeVm(100)])
    keys = [("h1", 100, "n1"), ("h1", 999, "n1")]
    plan = plan_bulk_action(keys, repo, {"h1"})
    assert [t.vmid for t in plan.targets] == [100]
    assert plan.skipped_no_vm == (999,)


def test_no_config_skipped():
    repo = FakeRepo([FakeVm(100), FakeVm(101)])
    keys = [("h1", 100, "n1"), ("offline-host", 101, "n1")]
    plan = plan_bulk_action(keys, repo, {"h1"})
    assert [t.vmid for t in plan.targets] == [100]
    assert plan.skipped_no_config == (101,)


def test_mixed_skips_counted():
    repo = FakeRepo([FakeVm(100), FakeVm(101, template=True), FakeVm(102)])
    keys = [("h1", 100, "n1"), ("h1", 101, "n1"),
            ("bad", 102, "n1"), ("h1", 999, "n1")]
    plan = plan_bulk_action(keys, repo, {"h1"})
    assert len(plan.targets) == 1
    assert plan.skipped_count == 3


def test_duplicates_deduplicated():
    repo = FakeRepo([FakeVm(100)])
    keys = [("h1", 100, "n1"), ("h1", 100, "n1"), ("h1", 100, "other-node")]
    plan = plan_bulk_action(keys, repo, {"h1"})
    assert len(plan.targets) == 1


def test_malformed_keys_ignored():
    repo = FakeRepo([FakeVm(100)])
    plan = plan_bulk_action([("h1", 100), "garbage", None, ("h1", 100, "n1", "extra")],
                            repo, {"h1"})
    assert plan.targets == ()


def test_empty_selection():
    plan = plan_bulk_action([], FakeRepo([]), {"h1"})
    assert plan.targets == ()
    assert plan.skipped_count == 0


def test_none_repo():
    plan = plan_bulk_action([("h1", 100, "n1")], None, {"h1"})
    assert plan.targets == ()
    assert plan.skipped_no_vm == (100,)


def test_order_preserved():
    repo = FakeRepo([FakeVm(300), FakeVm(100), FakeVm(200)])
    keys = [("h1", 300, "n1"), ("h1", 100, "n1"), ("h1", 200, "n1")]
    plan = plan_bulk_action(keys, repo, {"h1"})
    assert [t.vmid for t in plan.targets] == [300, 100, 200]


def test_real_vm_repository(tmp_path):
    """Integration: plan works with the real VmRepository + domain Vm."""
    from pve_center.domain.vm import Vm

    repo = VmRepository()
    repo.add(Vm.from_pve({"vmid": 100, "name": "web", "status": "stopped",
                          "template": 0}, "h1"))
    repo.add(Vm.from_pve({"vmid": 900, "name": "tpl", "status": "stopped",
                          "template": 1}, "h1"))
    plan = plan_bulk_action([("h1", 100, "n1"), ("h1", 900, "n1")], repo, {"h1"})
    assert [t.vmid for t in plan.targets] == [100]
    assert plan.skipped_templates == (900,)
