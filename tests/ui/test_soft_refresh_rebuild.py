"""Regression: soft refresh must rebuild the tree when the cluster
structure changes (e.g. a storage removed on the PVE side), otherwise
stale items linger until the next hard refresh."""

from pve_center.domain.node import Node as DomainNode
from pve_center.domain.repositories import (
    NodeRepository,
    StorageRepository,
    VmRepository,
)
from pve_center.domain.storage import Storage as DomainStorage
from pve_center.domain.vm import Vm as DomainVm
from pve_center.ui.mainwindow import _repo_signature


def _populate(node_repo, vm_repo, storage_repo):
    node_repo.add(DomainNode.from_pve({"node": "n1", "status": "online"}, "h1", "", False))
    vm_repo.add(DomainVm.from_pve({"vmid": 100, "node": "n1", "status": "stopped"}, "h1"))
    storage_repo.add(DomainStorage.from_pve({"storage": "local", "node": "n1"}, "h1", ""))


def test_signature_changes_when_storage_removed():
    nr, vr, sr = NodeRepository(), VmRepository(), StorageRepository()
    _populate(nr, vr, sr)
    sig_before = _repo_signature(nr, vr, sr)
    assert ("h1", "n1", "local") in sig_before[2]

    sr.clear()
    sig_after = _repo_signature(nr, vr, sr)
    assert sig_before != sig_after
    assert sig_after[2] == frozenset()


def test_signature_stable_when_only_metrics_change():
    nr, vr, sr = NodeRepository(), VmRepository(), StorageRepository()
    _populate(nr, vr, sr)
    sig_before = _repo_signature(nr, vr, sr)

    sr.add(DomainStorage.from_pve(
        {"storage": "local", "node": "n1", "used": 5, "total": 10}, "h1", ""))
    vr.add(DomainVm.from_pve(
        {"vmid": 100, "node": "n1", "status": "running", "cpu": 0.5}, "h1"))
    sig_after = _repo_signature(nr, vr, sr)

    assert sig_before == sig_after


def test_signature_changes_when_vm_or_node_added():
    nr, vr, sr = NodeRepository(), VmRepository(), StorageRepository()
    _populate(nr, vr, sr)
    sig_before = _repo_signature(nr, vr, sr)

    vr.add(DomainVm.from_pve({"vmid": 101, "node": "n1", "status": "stopped"}, "h1"))
    sig_vms = _repo_signature(nr, vr, sr)
    assert sig_vms != sig_before

    nr.add(DomainNode.from_pve({"node": "n2", "status": "online"}, "h1", "", False))
    sig_nodes = _repo_signature(nr, vr, sr)
    assert sig_nodes != sig_vms
