"""Tests for Storage, Pool, and IsoImage domain models."""

from __future__ import annotations

import pytest

from pve_center.domain import IsoImage, Pool, Storage

STORAGE_DICT = {
    "storage": "local-lvm",
    "node": "pve01",
    "type": "lvm",
    "content": "images,snippets,rootdir",
    "used": 10737418240,   # 10 GiB
    "total": 107374182400, # 100 GiB
    "avail": 96636764160,  # 90 GiB
    "shared": 0,
}

STORAGE_SHARED_DICT = {
    "storage": "nfs-backup",
    "node": "pve01",
    "type": "nfs",
    "content": "backup,iso",
    "used": 0,
    "total": 0,
    "avail": 0,
    "shared": 1,
}

ISO_DICT = {
    "volid": "local:iso/ubuntu-22.04.iso",
    "format": "iso",
    "size": 1288490188,  # ~1.2 GiB
}

ISO_TIB_DICT = {
    "volid": "big:iso/huge.iso",
    "format": "iso",
    "size": 1288490188 * 1024 * 2,  # ~2.4 TiB
}


class TestStorageFromPve:
    def test_all_fields(self):
        s = Storage.from_pve(STORAGE_DICT, "h1", "ros")
        assert s.storage == "local-lvm"
        assert s.node == "pve01"
        assert s.host_name == "h1"
        assert s.cluster == "ros"
        assert s.storage_type == "lvm"
        assert s.content == "images,snippets,rootdir"
        assert s.used_bytes == 10737418240
        assert s.total_bytes == 107374182400
        assert s.shared is False

    def test_shared_storage(self):
        s = Storage.from_pve(STORAGE_SHARED_DICT, "h1", "")
        assert s.shared is True
        assert s.cluster == ""

    def test_cluster_false_normalized(self):
        # "cluster": false from standalone host configs must become "" so
        # scope filters (s.cluster == cluster_scope) match and the
        # storage shows up in the tree's Storages view.
        s = Storage.from_pve(STORAGE_DICT, "h1", False)  # type: ignore[arg-type]
        assert s.cluster == ""

    def test_cluster_resources_plugintype(self):
        # /cluster/resources entries: "type" is "storage", backend is in
        # "plugintype" (v2.11.2: detail table showed "Type: storage")
        s = Storage.from_pve(
            {"storage": "ocfs-store", "node": "pve02", "type": "storage",
             "plugintype": "ocfs2", "content": "images", "shared": 1},
            "h1", "ros")
        assert s.storage_type == "ocfs2"

    def test_per_node_type_fallback(self):
        # /nodes/{node}/storage entries have no "plugintype"; "type" is the
        # backend and must keep working
        s = Storage.from_pve(
            {"storage": "local", "node": "pve01", "type": "dir"},
            "h1", "")
        assert s.storage_type == "dir"

    def test_empty_dict(self):
        s = Storage.from_pve({}, "h", "")
        assert s.storage == ""
        assert s.storage_type == ""
        assert s.used_bytes == 0

    def test_none_values(self):
        s = Storage.from_pve({"used": None, "total": None}, "h", "")
        assert s.used_bytes == 0
        assert s.total_bytes == 0

    def test_disk_maxdisk_fallback(self):
        """When used/total are absent (per-node /storage output), fall back
        to the disk/maxdisk keys from /cluster/resources."""
        s = Storage.from_pve({"storage": "local", "type": "dir",
                              "disk": 5, "maxdisk": 100}, "h", "")
        assert s.used_bytes == 5
        assert s.total_bytes == 100

    def test_used_wins_over_disk(self):
        s = Storage.from_pve({"used": 7, "total": 200, "disk": 5, "maxdisk": 100}, "h", "")
        assert s.used_bytes == 7
        assert s.total_bytes == 200


class TestStorageComputed:
    def test_used_gib(self):
        s = Storage.from_pve(STORAGE_DICT, "h1", "ros")
        assert s.used_gib == pytest.approx(10.0)
        assert s.total_gib == pytest.approx(100.0)

    def test_usage_pct(self):
        s = Storage.from_pve(STORAGE_DICT, "h1", "ros")
        assert s.usage_pct == 10

    def test_usage_pct_zero_total(self):
        s = Storage.from_pve(STORAGE_SHARED_DICT, "h1", "")
        assert s.usage_pct == 0

    def test_content_list(self):
        s = Storage.from_pve(STORAGE_DICT, "h1", "ros")
        assert s.content_list == ["images", "snippets", "rootdir"]

    def test_content_list_empty(self):
        s = Storage.from_pve({}, "h", "")
        assert s.content_list == []

    def test_display_name(self):
        s = Storage.from_pve(STORAGE_DICT, "h1", "ros")
        assert s.display_name == "local-lvm"


class TestPoolFromPve:
    def test_basic(self):
        p = Pool.from_pve({"poolid": "my-pool"})
        assert p.poolid == "my-pool"

    def test_fallback_pool_key(self):
        p = Pool.from_pve({"pool": "alt-name"})
        assert p.poolid == "alt-name"

    def test_empty(self):
        p = Pool.from_pve({})
        assert p.poolid == ""

    def test_comment(self):
        p = Pool.from_pve({"poolid": "my-pool", "comment": "web servers"})
        assert p.comment == "web servers"
        assert Pool.from_pve({"poolid": "x"}).comment == ""


class TestIsoImageFromPve:
    def test_basic(self):
        iso = IsoImage.from_pve(ISO_DICT)
        assert iso.volid == "local:iso/ubuntu-22.04.iso"
        assert iso.fmt == "iso"
        assert iso.size_bytes == 1288490188

    def test_empty(self):
        iso = IsoImage.from_pve({})
        assert iso.volid == ""
        assert iso.fmt == ""
        assert iso.size_bytes == 0

    def test_size_str_gib(self):
        iso = IsoImage.from_pve(ISO_DICT)
        assert "GiB" in iso.size_str

    def test_size_str_tib(self):
        iso = IsoImage.from_pve(ISO_TIB_DICT)
        assert "TiB" in iso.size_str

    def test_size_str_zero(self):
        iso = IsoImage.from_pve({})
        assert iso.size_str == "0"
