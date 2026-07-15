"""Tests for VmStatus and VmType enums."""

from __future__ import annotations

from pve_center.domain import QuorumState, VmStatus, VmType


class TestVmStatusFromPve:
    def test_running(self):
        assert VmStatus.from_pve("running") is VmStatus.RUNNING

    def test_stopped(self):
        assert VmStatus.from_pve("stopped") is VmStatus.STOPPED

    def test_paused(self):
        assert VmStatus.from_pve("paused") is VmStatus.PAUSED

    def test_unknown(self):
        assert VmStatus.from_pve("unknown") is VmStatus.UNKNOWN

    def test_invalid(self):
        assert VmStatus.from_pve("nope") is VmStatus.UNKNOWN

    def test_none(self):
        assert VmStatus.from_pve(None) is VmStatus.UNKNOWN

    def test_empty(self):
        assert VmStatus.from_pve("") is VmStatus.UNKNOWN


class TestVmTypeFromPve:
    def test_qemu(self):
        assert VmType.from_pve("qemu") is VmType.QEMU

    def test_lxc(self):
        assert VmType.from_pve("lxc") is VmType.LXC

    def test_invalid(self):
        assert VmType.from_pve("nope") is VmType.UNKNOWN

    def test_none(self):
        assert VmType.from_pve(None) is VmType.UNKNOWN


class TestQuorumState:
    def test_truthy(self):
        assert QuorumState.from_pve(1) is QuorumState.OK
        assert QuorumState.from_pve(True) is QuorumState.OK

    def test_falsy(self):
        assert QuorumState.from_pve(0) is QuorumState.LOST
        assert QuorumState.from_pve(False) is QuorumState.LOST

    def test_none(self):
        assert QuorumState.from_pve(None) is QuorumState.UNKNOWN
