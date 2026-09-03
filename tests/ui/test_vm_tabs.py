"""Tests for VMTabs snapshot tree population with domain Snapshot objects."""
from datetime import datetime
from types import SimpleNamespace

from PySide6.QtWidgets import QLabel, QStackedWidget, QTreeWidget

from pve_center.domain.snapshot import Snapshot
from pve_center.ui.detail_panel._vm_tabs import VMTabs


def _panel():
    tree = QTreeWidget()
    tree.setColumnCount(6)
    loading = QLabel()
    stack = QStackedWidget()
    stack.addWidget(loading)  # index 0: loading/empty
    stack.addWidget(tree)     # index 1: snapshot list
    return SimpleNamespace(
        vm_snapshots_tree=tree,
        vm_snapshots_loading=loading,
        vm_snapshots_stack=stack,
    )


def _snap(name, parent="", snaptime=0, size=0, desc=""):
    return Snapshot(name=name, description=desc, snaptime=snaptime,
                    parent=parent, vmstate=False, size_bytes=size,
                    vmid=0, vm_name="", host_name="", node="")


class TestPopulateVmSnapshotsTree:
    def test_empty(self, qtbot):
        fake = SimpleNamespace(panel=_panel())
        qtbot.addWidget(fake.panel.vm_snapshots_tree)
        VMTabs.populate_vm_snapshots_tree(fake, [])
        assert fake.panel.vm_snapshots_tree.topLevelItemCount() == 0
        assert fake.panel.vm_snapshots_stack.currentIndex() == 0

    def test_root_snapshots_top_level(self, qtbot):
        fake = SimpleNamespace(panel=_panel())
        qtbot.addWidget(fake.panel.vm_snapshots_tree)
        snaps = [_snap("base", snaptime=1700000000, size=32 * 1024**3, desc="clean")]
        VMTabs.populate_vm_snapshots_tree(fake, snaps)
        tree = fake.panel.vm_snapshots_tree
        assert tree.topLevelItemCount() == 1
        item = tree.topLevelItem(0)
        assert item.text(0) == "base"
        assert item.text(1) == "clean"
        expected_ts = datetime.fromtimestamp(1700000000).strftime("%Y-%m-%d %H:%M:%S")
        assert item.text(2) == expected_ts
        assert item.text(4) == "32.0 GiB"
        assert fake.panel.vm_snapshots_stack.currentIndex() == 1

    def test_nested_children(self, qtbot):
        fake = SimpleNamespace(panel=_panel())
        qtbot.addWidget(fake.panel.vm_snapshots_tree)
        snaps = [
            _snap("work", parent="base"),
            _snap("base"),
            _snap("deep", parent="work"),
        ]
        VMTabs.populate_vm_snapshots_tree(fake, snaps)
        tree = fake.panel.vm_snapshots_tree
        assert tree.topLevelItemCount() == 1
        base_item = tree.topLevelItem(0)
        assert base_item.text(0) == "base"
        assert base_item.childCount() == 1
        work_item = base_item.child(0)
        assert work_item.text(0) == "work"
        assert work_item.childCount() == 1
        assert work_item.child(0).text(0) == "deep"

    def test_orphan_parent_becomes_top_level(self, qtbot):
        """parent references a missing snapshot -> treated as root."""
        fake = SimpleNamespace(panel=_panel())
        qtbot.addWidget(fake.panel.vm_snapshots_tree)
        snaps = [_snap("s1", parent="ghost")]
        VMTabs.populate_vm_snapshots_tree(fake, snaps)
        assert fake.panel.vm_snapshots_tree.topLevelItemCount() == 1
