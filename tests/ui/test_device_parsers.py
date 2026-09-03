"""Tests for device string parsers in vm_device_editors / vm_config_display."""
from pve_center.ui.vm_device_editors import _build_net, _parse_disk, _parse_net


class TestParseNet:
    def test_basic(self):
        r = _parse_net("virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0,tag=10")
        assert r["model"] == "virtio"
        assert r["mac"] == "AA:BB:CC:DD:EE:FF"
        assert r["bridge"] == "vmbr0"
        assert r["tag"] == "10"
        assert r["extra"] == []

    def test_extra_options_preserved(self):
        """firewall/rate/mtu/... must survive an edit round-trip."""
        raw = "virtio=AA:BB,bridge=vmbr0,firewall=1,rate=50,link_down=1"
        r = _parse_net(raw)
        assert "firewall=1" in r["extra"]
        assert "rate=50" in r["extra"]
        assert "link_down=1" in r["extra"]
        rebuilt = _build_net(r["model"], r["mac"], r["bridge"], r["tag"], r["queues"],
                             extra=r["extra"])
        assert rebuilt == raw

    def test_empty(self):
        r = _parse_net("")
        assert r["model"] == "virtio"
        assert r["extra"] == []


class TestParseDisk:
    def test_volume_and_size_split(self):
        """First segment is storage:volume-name; the real size comes from
        the size= option, not from the volume name."""
        r = _parse_disk("local-lvm:vm-100-disk-0,size=32G,cache=writeback,format=qcow2")
        assert r["storage"] == "local-lvm"
        assert r["volume"] == "vm-100-disk-0"
        assert r["size"] == "32G"
        assert r["cache"] == "writeback"
        assert r["format"] == "qcow2"
        assert r["extra"] == []

    def test_no_size_option(self):
        r = _parse_disk("local:vm-100-disk-1")
        assert r["volume"] == "vm-100-disk-1"
        assert r["size"] == ""

    def test_empty(self):
        r = _parse_disk("")
        assert r["storage"] == ""
        assert r["volume"] == ""
        assert r["size"] == ""


class TestFmtDisk:
    def test_shows_real_size(self):
        from pve_center.ui.vm_config_display import _fmt_disk
        out = _fmt_disk("local-lvm:vm-100-disk-0,size=32G,format=qcow2")
        assert "local-lvm" in out
        assert "vm-100-disk-0" in out
        assert "32G" in out
