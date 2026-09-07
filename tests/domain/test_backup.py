"""Tests for pve_center.domain.backup — PBS volid parsing and snapshots."""

from datetime import datetime, timezone

from pve_center.domain.backup import BackupSnapshot, parse_pbs_volid, verify_state


class TestParsePbsVolid:
    def test_vm_snapshot(self):
        pbs = parse_pbs_volid("pbs1:backup/vm/100/2024-05-06T07:08:09Z")
        assert pbs is not None
        assert pbs["store"] == "pbs1"
        assert pbs["group"] == "vm"
        assert pbs["vmid"] == 100
        assert pbs["vm_type"] == "qemu"
        assert pbs["time"] == datetime(2024, 5, 6, 7, 8, 9, tzinfo=timezone.utc)

    def test_ct_snapshot(self):
        pbs = parse_pbs_volid("nas-pbs:backup/ct/212/2025-12-31T23:59:59Z")
        assert pbs is not None
        assert pbs["group"] == "ct"
        assert pbs["vmid"] == 212
        assert pbs["vm_type"] == "lxc"

    def test_vzdump_volid_is_not_pbs(self):
        assert parse_pbs_volid("local:backup/vzdump-qemu-100-2024_05_06-07_08_09.vma.zst") is None

    def test_garbage(self):
        assert parse_pbs_volid("") is None
        assert parse_pbs_volid("pbs1:backup/vm/100/not-a-time") is None


class TestVerifyState:
    def test_ok(self):
        assert verify_state({"state": "ok"}) == "ok"

    def test_failed(self):
        assert verify_state({"state": "failed"}) == "failed"

    def test_none_state(self):
        assert verify_state({"state": "none"}) == "none"

    def test_missing_or_invalid(self):
        assert verify_state(None) == ""
        assert verify_state({}) == ""
        assert verify_state({"state": "weird"}) == ""


class TestFromContentItem:
    def test_pbs_item(self):
        item = {
            "volid": "pbs1:backup/vm/100/2024-05-06T07:08:09Z",
            "size": 1073741824,
            "owner": "root@pam",
            "verification": {"state": "ok"},
            "notes": "daily backup",
            "encrypted": 1,
        }
        snap = BackupSnapshot.from_content_item(item, storage="pbs1")
        assert snap.is_pbs
        assert snap.vmid == 100
        assert snap.vm_type == "qemu"
        assert snap.owner == "root@pam"
        assert snap.verify == "ok"
        assert snap.notes == "daily backup"
        assert snap.encrypted is True
        assert snap.size_bytes == 1073741824
        assert snap.snapshot_name == "vm/100 · 2024-05-06 07:08"

    def test_vzdump_item(self):
        item = {
            "volid": "local:backup/vzdump-qemu-101-2024_05_06-07_08_09.vma.zst",
            "size": 2048,
            "format": "vma.zst",
            "subtype": "qemu",
            "ctime": 1714979289,
        }
        snap = BackupSnapshot.from_content_item(item, storage="local")
        assert not snap.is_pbs
        assert snap.vmid == 101
        assert snap.vm_type == "qemu"
        assert snap.owner == ""
        assert snap.verify == ""
        assert snap.time is not None
        assert snap.snapshot_name == item["volid"]

    def test_ct_time_fallback_to_vmid_parse(self):
        item = {"volid": "pbs:backup/ct/7/2024-01-02T03:04:05Z"}
        snap = BackupSnapshot.from_content_item(item)
        assert snap.vmid == 7
        assert snap.vm_type == "lxc"
        assert snap.time == datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
