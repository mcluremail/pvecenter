"""Tests for TreePanel with domain objects."""
import json

import pytest
from PySide6.QtCore import QMimeData, QPointF
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from pve_center.domain.enums import VmStatus
from pve_center.domain.repositories import NodeRepository, VmRepository
from pve_center.ui.tree_panel import (
    GROUP_MIME,
    ITEM_KEY_ROLE,
    VM_KEY_ROLE,
    GroupTreeWidget,
    TreePanel,
)


@pytest.fixture(autouse=True)
def _isolated_tree_state(monkeypatch):
    """B20: keep treeMode ui_state out of the real config DB."""
    import pve_center.ui.tree_panel as tp_mod

    state = {}
    monkeypatch.setattr(tp_mod, "load_ui_state", lambda key: state.get(key))
    monkeypatch.setattr(
        tp_mod, "save_ui_state", lambda key, value: state.__setitem__(key, value)
    )


def _make_nodes_cfg(standalone_names=None, clusters=None):
    """Build a minimal nodes_cfg list for TreePanel."""
    cfgs = []
    standalone_names = standalone_names or []
    clusters = clusters or {}
    for name in standalone_names:
        cfgs.append({"name": name, "cluster": "", "skip": False})
    for cluster_name, rep_name in clusters.items():
        cfgs.append({"name": rep_name, "cluster": cluster_name, "cluster_rep": True, "skip": False})
    return cfgs


def _collect_items(tp):
    """Return {key_tuple: item} for all tree items."""
    result = {}

    def walk(item):
        key = item.data(0, ITEM_KEY_ROLE)
        if key is not None:
            result[key] = item
        for i in range(item.childCount()):
            walk(item.child(i))

    for i in range(tp.tree.topLevelItemCount()):
        walk(tp.tree.topLevelItem(i))
    return result


class TestTreePanelBuild:
    """TreePanel._build_tree with domain objects via update_data."""

    def test_standalone_node(self, qtbot, make_node):
        cfg = [{"name": "h1", "cluster": "", "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        node = make_node(host_name="h1", node="pve01")
        node_repo = NodeRepository()
        node_repo.add(node)
        vm_repo = VmRepository()

        tp.update_data(node_repo.all(), vm_repo.all(), final=True,
                       node_repo=node_repo, vm_repo=vm_repo)
        tp._build_tree()

        # B20: no sections — the standalone host sits flat at top level
        items = _collect_items(tp)
        assert not any(k[0] in ("section", "storage_section") for k in items)
        host_key = ("host", "pve01", "h1")
        assert host_key in items
        assert "pve01" in items[host_key].text(0)
        assert items[host_key].parent() is None

    def test_node_with_vms(self, qtbot, make_node, make_vm):
        cfg = [{"name": "h1", "cluster": "", "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        node = make_node(host_name="h1", node="pve01")
        vm1 = make_vm(vmid=100, name="alpha", host_name="h1", node="pve01", status=VmStatus.RUNNING)
        vm2 = make_vm(vmid=101, name="beta", host_name="h1", node="pve01", status=VmStatus.STOPPED)

        node_repo = NodeRepository()
        node_repo.add(node)
        vm_repo = VmRepository()
        vm_repo.add(vm1)
        vm_repo.add(vm2)

        tp.update_data(node_repo.all(), vm_repo.all(), final=True,
                       node_repo=node_repo, vm_repo=vm_repo)
        tp._build_tree()

        items = _collect_items(tp)
        host = items[("host", "pve01", "h1")]
        text = host.text(0)
        # [running/total] = [1/2]
        assert "[1/2]" in text
        # Should have 2 vm children
        assert host.childCount() == 2

    def test_cluster_nodes(self, qtbot, make_node):
        cfg = [{"name": "rep1", "cluster": "mycluster", "cluster_rep": True, "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        n1 = make_node(host_name="rep1", node="n1", cluster="mycluster", is_cluster=True)
        n2 = make_node(host_name="rep1", node="n2", cluster="mycluster", is_cluster=True)
        node_repo = NodeRepository()
        node_repo.add(n1)
        node_repo.add(n2)
        vm_repo = VmRepository()

        tp.update_data(node_repo.all(), vm_repo.all(), final=True,
                       node_repo=node_repo, vm_repo=vm_repo)
        tp._build_tree()

        # B20: cluster item lives flat at top level
        items = _collect_items(tp)
        assert not any(k[0] in ("section", "storage_section") for k in items)
        cl = items[("cluster", "mycluster")]
        assert "mycluster" in cl.text(0)
        assert cl.childCount() == 2  # two nodes
        assert cl.parent() is None

    def test_empty_tree(self, qtbot):
        cfg = []
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        node_repo = NodeRepository()
        vm_repo = VmRepository()
        tp.update_data(node_repo.all(), vm_repo.all(), final=True,
                       node_repo=node_repo, vm_repo=vm_repo)
        tp._build_tree()
        # B20: no section headers — the tree is simply empty
        assert tp.tree.topLevelItemCount() == 0

    def test_error_node(self, qtbot):
        cfg = [{"name": "h1", "cluster": "", "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        err_node_dict = {
            "node": "h1",
            "status": "error",
            "error": "Connection refused",
            "host_name": "h1",
            "_display_name": "h1",
            "_is_cluster": False,
        }
        from pve_center.domain.node import Node
        node = Node.from_pve(err_node_dict, "h1", "", False)
        node_repo = NodeRepository()
        node_repo.add(node)
        vm_repo = VmRepository()

        tp.update_data(node_repo.all(), vm_repo.all(), final=True,
                       node_repo=node_repo, vm_repo=vm_repo)
        tp._build_tree()

        items = _collect_items(tp)
        host = items[("host", "h1", "h1")]
        assert "h1" in host.text(0)


class TestTreePanelVmCountStr:
    def test_empty(self):
        from pve_center.ui.tree_panel import _vm_count_str
        assert _vm_count_str([]) == "[0/0]"

    def test_mixed(self, make_vm):
        from pve_center.ui.tree_panel import _vm_count_str
        vms = [
            make_vm(vmid=1, status=VmStatus.RUNNING),
            make_vm(vmid=2, status=VmStatus.STOPPED),
            make_vm(vmid=3, status=VmStatus.RUNNING),
        ]
        assert _vm_count_str(vms) == "[2/3]"

    def test_with_domain_objects(self, make_vm):
        from pve_center.ui.tree_panel import _vm_count_str
        vms = [
            make_vm(vmid=1, status=VmStatus.RUNNING),
            make_vm(vmid=2, status=VmStatus.RUNNING),
        ]
        # Domain Vm uses DictCompat.get("status") which returns the string value
        assert _vm_count_str(vms) == "[2/2]"


class TestSelectedVmKeys:
    """TreePanel.selected_vm_keys for bulk actions (B3)."""

    def _build_tree_with_vms(self, qtbot, make_node, make_vm):
        cfg = [{"name": "h1", "cluster": "", "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        node = make_node(host_name="h1", node="pve01")
        vm1 = make_vm(vmid=100, name="alpha", host_name="h1", node="pve01",
                      status=VmStatus.RUNNING)
        vm2 = make_vm(vmid=101, name="beta", host_name="h1", node="pve01",
                      status=VmStatus.STOPPED)

        node_repo = NodeRepository()
        node_repo.add(node)
        vm_repo = VmRepository()
        vm_repo.add(vm1)
        vm_repo.add(vm2)

        tp.update_data(node_repo.all(), vm_repo.all(), final=True,
                       node_repo=node_repo, vm_repo=vm_repo)
        tp._build_tree()

        # Collect VM items (items carrying a VM key) — B20: hosts sit
        # directly at top level, VMs are their children
        vm_items = []
        for i in range(tp.tree.topLevelItemCount()):
            host = tp.tree.topLevelItem(i)
            for k in range(host.childCount()):
                vm = host.child(k)
                if vm.data(0, VM_KEY_ROLE) is not None:
                    vm_items.append(vm)
        assert len(vm_items) == 2
        return tp, vm_items

    def test_empty_selection(self, qtbot, make_node, make_vm):
        tp, _vm_items = self._build_tree_with_vms(qtbot, make_node, make_vm)
        assert tp.selected_vm_keys() == []

    def test_single_selection(self, qtbot, make_node, make_vm):
        tp, vm_items = self._build_tree_with_vms(qtbot, make_node, make_vm)
        vm_items[0].setSelected(True)
        keys = tp.selected_vm_keys()
        assert len(keys) == 1
        assert keys[0] == ("h1", 100, "pve01")

    def test_multi_selection(self, qtbot, make_node, make_vm):
        tp, vm_items = self._build_tree_with_vms(qtbot, make_node, make_vm)
        vm_items[0].setSelected(True)
        vm_items[1].setSelected(True)
        keys = tp.selected_vm_keys()
        assert len(keys) == 2
        assert ("h1", 100, "pve01") in keys
        assert ("h1", 101, "pve01") in keys

    def test_extended_selection_mode(self, qtbot, make_node, make_vm):
        tp, _vm_items = self._build_tree_with_vms(qtbot, make_node, make_vm)
        assert tp.tree.selectionMode() == QTreeWidget.SelectionMode.ExtendedSelection


class TestHostGroups:
    """B16: user-defined host groups in the tree."""

    def test_grouped_standalone_host(self, qtbot, make_node, make_vm):
        cfg = [{"name": "h1", "cluster": "", "skip": False, "group": "Site A"}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        node = make_node(host_name="h1", node="pve01")
        node_repo = NodeRepository()
        node_repo.add(node)
        vm_repo = VmRepository()
        vm_repo.add(make_vm(vmid=100, name="alpha", host_name="h1",
                            node="pve01", status=VmStatus.RUNNING))

        tp.update_data(node_repo.all(), vm_repo.all(), final=True,
                       node_repo=node_repo, vm_repo=vm_repo)
        tp._build_tree()

        items = _collect_items(tp)
        group_key = next((k for k in items if k[0] == "group"), None)
        assert group_key is not None
        assert group_key[1] == "Site A"
        # Group shows aggregated VM count
        assert "[1/1]" in items[group_key].text(0)
        # Host is under the group, not at top level (B20: no sections)
        host_key = next((k for k in items if k[0] == "host"), None)
        assert host_key == ("host", "pve01", "h1")
        assert items[host_key].parent() is items[group_key]
        assert not any(k[0] in ("section", "storage_section") for k in items)

    def test_grouped_cluster(self, qtbot, make_node, make_vm):
        cfg = [
            {"name": "h1", "cluster": "cl1", "cluster_rep": True, "skip": False,
             "group": "DC West"},
            {"name": "h2", "cluster": "cl1", "cluster_rep": False, "skip": False,
             "group": "DC West"},
        ]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        node_repo = NodeRepository()
        node_repo.add(make_node(host_name="h1", node="pve01"))
        vm_repo = VmRepository()
        vm_repo.add(make_vm(vmid=100, name="alpha", host_name="h1",
                            node="pve01", status=VmStatus.RUNNING))

        tp.update_data(node_repo.all(), vm_repo.all(), final=True,
                       node_repo=node_repo, vm_repo=vm_repo)
        tp._build_tree()

        items = _collect_items(tp)
        group_key = next((k for k in items if k[0] == "group"), None)
        assert group_key is not None
        assert group_key[1] == "DC West"
        # Cluster item lives inside the group (B20: no sections)
        cluster_key = next((k for k in items if k[0] == "cluster"), None)
        assert cluster_key == ("cluster", "cl1")
        assert items[cluster_key].parent() is items[group_key]
        assert not any(k[0] in ("section", "storage_section") for k in items)

    def test_ungrouped_hosts_flat(self, qtbot, make_node):
        cfg = [
            {"name": "h1", "cluster": "", "skip": False, "group": "Site A"},
            {"name": "h2", "cluster": "", "skip": False},
        ]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        node_repo = NodeRepository()
        node_repo.add(make_node(host_name="h1", node="n1"))
        node_repo.add(make_node(host_name="h2", node="n2"))

        tp.update_data(node_repo.all(), [], final=True,
                       node_repo=node_repo, vm_repo=None)
        tp._build_tree()

        items = _collect_items(tp)
        group_key = next((k for k in items if k[0] == "group"), None)
        assert group_key == ("group", "Site A")
        hosts = [k for k in items if k[0] == "host"]
        host_parents = {k: items[k].parent() for k in hosts}
        h1_key = next(k for k in hosts if k[2] == "h1")
        h2_key = next(k for k in hosts if k[2] == "h2")
        assert host_parents[h1_key] is items[group_key]
        # B20: no sections — ungrouped host sits flat at top level
        assert host_parents[h2_key] is None

    def test_group_of_cluster_applies_to_all_members(self, qtbot, make_node):
        """Partial cfg grouping: group on rep cfg only still pulls the cluster."""
        cfg = [
            {"name": "h1", "cluster": "cl1", "cluster_rep": True, "skip": False,
             "group": "DC"},
            {"name": "h2", "cluster": "cl1", "cluster_rep": False, "skip": False},
        ]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        node_repo = NodeRepository()
        node_repo.add(make_node(host_name="h1", node="pve01"))
        node_repo.add(make_node(host_name="h2", node="pve02"))

        tp.update_data(node_repo.all(), [], final=True,
                       node_repo=node_repo, vm_repo=None)
        tp._build_tree()

        items = _collect_items(tp)
        cluster_key = next((k for k in items if k[0] == "cluster"), None)
        assert cluster_key == ("cluster", "cl1")
        group_key = next(k for k in items if k[0] == "group")
        assert items[cluster_key].parent() is items[group_key]


class _FakeDropEvent:
    """Mimics QDropEvent for GroupTreeWidget._decode/_drop_group tests."""

    def __init__(self, mime):
        self._mime = mime
        self.accepted = False
        self.ignored = False

    def mimeData(self):
        return self._mime

    def position(self):
        return QPointF(0, 0)

    def acceptProposedAction(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True


class TestGroupDragDrop:
    """B16: drag&drop hosts/clusters into groups."""

    def _make_widget(self, qtbot):
        cfg = [
            {"name": "h1", "cluster": "", "skip": False, "group": "G"},
            {"name": "h2", "cluster": "", "skip": False},
        ]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)
        gt = tp.tree
        assert isinstance(gt, GroupTreeWidget)

        group = QTreeWidgetItem(["G"])
        group.setData(0, ITEM_KEY_ROLE, ("group", "G"))
        gt.addTopLevelItem(group)
        host_in_group = QTreeWidgetItem(["h1"])
        host_in_group.setData(0, ITEM_KEY_ROLE, ("host", "n1", "h1"))
        group.addChild(host_in_group)
        cluster_in_group = QTreeWidgetItem(["cl1"])
        cluster_in_group.setData(0, ITEM_KEY_ROLE, ("cluster", "cl1"))
        group.addChild(cluster_in_group)

        host_flat = QTreeWidgetItem(["h2"])
        host_flat.setData(0, ITEM_KEY_ROLE, ("host", "n2", "h2"))
        gt.addTopLevelItem(host_flat)

        items = {
            "group": group,
            "host_in_group": host_in_group,
            "cluster_in_group": cluster_in_group,
            "host_flat": host_flat,
        }
        return tp, gt, items

    def test_drag_payload(self, qtbot):
        _tp, gt, items = self._make_widget(qtbot)
        assert gt._drag_payload(items["host_in_group"]) == {"kind": "host", "name": "h1"}
        assert gt._drag_payload(items["cluster_in_group"]) == {"kind": "cluster", "name": "cl1"}
        assert gt._drag_payload(items["host_flat"]) == {"kind": "host", "name": "h2"}
        # Non-draggable: group and plain items
        assert gt._drag_payload(items["group"]) is None
        assert gt._drag_payload(QTreeWidgetItem(["vm"])) is None
        assert gt._drag_payload(None) is None

    def test_decode_valid_and_invalid(self, qtbot):
        _tp, gt, _items = self._make_widget(qtbot)
        mime = QMimeData()
        mime.setData(GROUP_MIME, json.dumps({"kind": "host", "name": "h1"}).encode())
        assert gt._decode(_FakeDropEvent(mime)) == {"kind": "host", "name": "h1"}

        wrong_mime = QMimeData()
        wrong_mime.setData("text/plain", b"x")
        assert gt._decode(_FakeDropEvent(wrong_mime)) is None

        bad_json = QMimeData()
        bad_json.setData(GROUP_MIME, b"{not json")
        assert gt._decode(_FakeDropEvent(bad_json)) is None

        bad_kind = QMimeData()
        bad_kind.setData(GROUP_MIME, json.dumps({"kind": "vm", "name": "x"}).encode())
        assert gt._decode(_FakeDropEvent(bad_kind)) is None

    def test_drop_group_resolution(self, qtbot):
        _tp, gt, items = self._make_widget(qtbot)
        assert gt._drop_group(items["group"]) == "G"
        assert gt._drop_group(items["host_in_group"]) == "G"
        assert gt._drop_group(items["cluster_in_group"]) == "G"
        # B20: no sections — a host outside any group is not a target
        assert gt._drop_group(items["host_flat"]) is None
        assert gt._drop_group(None) is None

    def test_drop_event_emits_group_move(self, qtbot):
        tp, gt, items = self._make_widget(qtbot)
        gt.itemAt = lambda _p: items["host_in_group"]
        emitted = []
        tp.group_move_requested.connect(lambda k, n, g: emitted.append((k, n, g)))

        mime = QMimeData()
        mime.setData(GROUP_MIME, json.dumps({"kind": "host", "name": "h9"}).encode())
        event = _FakeDropEvent(mime)
        gt.dropEvent(event)

        assert event.accepted and not event.ignored
        assert emitted == [("host", "h9", "G")]

    def test_drop_event_ignored_on_invalid_target(self, qtbot):
        tp, gt, items = self._make_widget(qtbot)
        gt.itemAt = lambda _p: items["host_flat"]
        emitted = []
        tp.group_move_requested.connect(lambda k, n, g: emitted.append((k, n, g)))

        mime = QMimeData()
        mime.setData(GROUP_MIME, json.dumps({"kind": "host", "name": "h9"}).encode())
        event = _FakeDropEvent(mime)
        gt.dropEvent(event)

        assert event.ignored and not event.accepted
        assert emitted == []


def _find_item(tp, text_part):
    """Depth-first search for an item whose column-0 text contains text_part."""
    def walk(item):
        if text_part in item.text(0):
            return item
        for i in range(item.childCount()):
            found = walk(item.child(i))
            if found:
                return found
        return None
    for i in range(tp.tree.topLevelItemCount()):
        found = walk(tp.tree.topLevelItem(i))
        if found:
            return found
    return None


class TestTreePanelNotes:
    """B19: per-item notes in tree column 1."""

    def test_host_default_note_is_fqdn(self, qtbot, make_node):
        cfg = [{"name": "h1", "host": "pve01.example.com", "cluster": "", "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)
        node = make_node(host_name="h1", node="pve01")
        tp.update_data([node], [], final=True)

        host_item = _find_item(tp, "pve01")
        assert host_item is not None
        assert host_item.text(1) == "pve01.example.com"

    def test_host_user_note_overrides_fqdn(self, qtbot, make_node):
        cfg = [{"name": "h1", "host": "pve01.example.com", "cluster": "", "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)
        tp._tree_notes["host:h1"] = "Main node"
        node = make_node(host_name="h1", node="pve01")
        tp.update_data([node], [], final=True)

        host_item = _find_item(tp, "pve01")
        assert host_item.text(1) == "Main node"

    def test_cluster_and_vm_notes(self, qtbot, make_node, make_vm):
        cfg = [{"name": "h1", "cluster": "c1", "cluster_rep": True, "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)
        tp._tree_notes["cluster:c1"] = "Prod cluster"
        tp._tree_notes["vm:h1:100"] = "web server"
        node = make_node(host_name="h1", node="pve01", cluster="c1")
        vm = make_vm(host_name="h1", node="pve01", vmid=100)
        tp.update_data([node], [vm], final=True)

        cl_item = _find_item(tp, "c1")
        assert cl_item is not None
        assert cl_item.text(1) == "Prod cluster"
        vm_item = _find_item(tp, "test-vm")
        assert vm_item is not None
        assert vm_item.text(1) == "web server"

    def test_no_note_without_cfg_host(self, qtbot, make_node):
        cfg = [{"name": "h1", "cluster": "", "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)
        node = make_node(host_name="h1", node="pve01")
        tp.update_data([node], [], final=True)

        host_item = _find_item(tp, "pve01")
        assert host_item is not None
        assert host_item.text(1) == ""

    def test_long_note_truncated_with_tooltip(self, qtbot, make_node):
        cfg = [{"name": "h1", "host": "pve01.example.com", "cluster": "", "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)
        tp._tree_notes["host:h1"] = "x" * 80
        node = make_node(host_name="h1", node="pve01")
        tp.update_data([node], [], final=True)

        host_item = _find_item(tp, "pve01")
        assert host_item.text(1) == "x" * 59 + "…"
        assert host_item.toolTip(1) == "x" * 80


class TestTreeModes:
    """B20: Hosts / Storages view modes."""

    def test_default_mode_is_hosts(self, qtbot):
        cfg = [{"name": "h1", "cluster": "", "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)
        assert tp._tree_mode == "hosts"
        assert tp._mode_combo.currentData() == "hosts"
        assert tp._mode_combo.count() == 2

    def test_flat_top_level_mix(self, qtbot, make_node):
        """B20: clusters and standalone hosts share one flat top level."""
        cfg = [
            {"name": "bhost", "cluster": "", "skip": False},
            {"name": "rep", "cluster": "acl", "cluster_rep": True, "skip": False},
        ]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        node_repo = NodeRepository()
        node_repo.add(make_node(host_name="rep", node="n1", cluster="acl", is_cluster=True))
        node_repo.add(make_node(host_name="bhost", node="n2"))
        tp.update_data(node_repo.all(), [], final=True,
                       node_repo=node_repo, vm_repo=None)

        top_keys = [
            tp.tree.topLevelItem(i).data(0, ITEM_KEY_ROLE)
            for i in range(tp.tree.topLevelItemCount())
        ]
        # Sorted together: cluster "acl" before host "bhost"
        assert top_keys == [("cluster", "acl"), ("host", "n2", "bhost")]

    def test_storages_mode_layout(self, qtbot, make_node, make_storage):
        cfg = [
            {"name": "h1", "cluster": "cl1", "cluster_rep": True, "skip": False},
            {"name": "h2", "cluster": "", "skip": False},
        ]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        node_repo = NodeRepository()
        n1 = make_node(host_name="h1", node="n1", cluster="cl1", is_cluster=True)
        n2 = make_node(host_name="h2", node="n2")
        node_repo.add(n1)
        node_repo.add(n2)
        storages = [
            make_storage(host_name="h1", node="n1", cluster="cl1",
                         storage="ceph", shared=True),
            make_storage(host_name="h1", node="n1", cluster="cl1",
                         storage="local", shared=False),
            make_storage(host_name="h2", node="n2", storage="local2"),
        ]
        tp.update_data(node_repo.all(), [], storages, final=True,
                       node_repo=node_repo, vm_repo=None)
        tp.set_mode("storages")

        items = _collect_items(tp)
        # Shared storage hangs off the cluster item, labelled "@cluster"
        shared = items[("storage", "ceph", "cluster", "cl1")]
        assert "@cl1" in shared.text(0)
        assert shared.parent() is items[("cluster", "cl1")]
        # Local cluster-node storage hangs off the host inside the cluster
        local = items[("storage", "local", "host", "h1")]
        assert local.parent() is items[("host", "n1", "h1")]
        assert items[("host", "n1", "h1")].parent() is items[("cluster", "cl1")]
        # Standalone host keeps its own storages
        s2 = items[("storage", "local2", "host", "h2")]
        assert s2.parent() is items[("host", "n2", "h2")]
        assert not any(k[0] in ("section", "storage_section") for k in items)

    def test_storages_mode_false_cluster_cfg(self, qtbot, make_node):
        """Real-world regression: standalone host configs store
        "cluster": false (JSON bool). The worker used to pass it through
        raw, so Storage.cluster was False and the storages view dropped
        all local storages (False == "" is False)."""
        from pve_center.domain.storage import Storage as DomainStorage

        cfg = [{"name": "h1", "cluster": False, "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        node_repo = NodeRepository()
        node_repo.add(make_node(host_name="h1", node="n1"))
        # Same path as mainwindow.on_worker_finished: cluster arg comes
        # from node_cfg["cluster"] == False and must normalize to "".
        st = DomainStorage.from_pve(
            {"storage": "local", "node": "n1", "type": "dir",
             "content": "images", "plugintype": "dir",
             "disk": 1, "maxdisk": 10},
            "h1", False,  # type: ignore[arg-type]
        )
        assert st.cluster == ""
        tp.update_data(node_repo.all(), [], [st], final=True,
                       node_repo=node_repo, vm_repo=None)
        tp.set_mode("storages")

        items = _collect_items(tp)
        assert ("storage", "local", "host", "h1") in items

    def test_shared_storage_dedup(self, qtbot, make_node, make_storage):
        """The same shared storage reported by several nodes appears once."""
        cfg = [{"name": "h1", "cluster": "cl1", "cluster_rep": True, "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        node_repo = NodeRepository()
        node_repo.add(make_node(host_name="h1", node="n1", cluster="cl1", is_cluster=True))
        node_repo.add(make_node(host_name="h1", node="n2", cluster="cl1", is_cluster=True))
        storages = [
            make_storage(host_name="h1", node="n1", cluster="cl1",
                         storage="ceph", shared=True),
            make_storage(host_name="h1", node="n2", cluster="cl1",
                         storage="ceph", shared=True),
        ]
        tp.update_data(node_repo.all(), [], storages, final=True,
                       node_repo=node_repo, vm_repo=None)
        tp.set_mode("storages")

        items = _collect_items(tp)
        ceph_items = [k for k in items if k[:2] == ("storage", "ceph")]
        assert len(ceph_items) == 1
        # 1 shared storage + 2 member hosts (n1, n2), nothing else
        assert items[("cluster", "cl1")].childCount() == 3

    def test_mode_persisted_and_restored(self, qtbot, make_node, monkeypatch):
        import pve_center.ui.tree_panel as tp_mod

        saved = {}
        monkeypatch.setattr(tp_mod, "save_ui_state", lambda k, v: saved.__setitem__(k, v))
        monkeypatch.setattr(tp_mod, "load_ui_state", lambda k: saved.get(k))

        cfg = [{"name": "h1", "cluster": "", "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)
        assert tp._tree_mode == "hosts"

        tp.set_mode("storages")
        assert tp._tree_mode == "storages"
        assert saved == {"treeMode": "storages"}
        assert tp._mode_combo.currentData() == "storages"

        tp2 = TreePanel(cfg)
        qtbot.addWidget(tp2)
        assert tp2._tree_mode == "storages"

    def test_set_mode_same_value_noop(self, qtbot, monkeypatch):
        import pve_center.ui.tree_panel as tp_mod

        calls = []
        monkeypatch.setattr(tp_mod, "save_ui_state", lambda k, v: calls.append((k, v)))
        cfg = [{"name": "h1", "cluster": "", "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)
        tp.set_mode("hosts")
        assert calls == []

    def test_reveal_key_switches_mode(self, qtbot, make_node, make_storage):
        cfg = [{"name": "h1", "cluster": "cl1", "cluster_rep": True, "skip": False}]
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        node_repo = NodeRepository()
        node_repo.add(make_node(host_name="h1", node="n1", cluster="cl1", is_cluster=True))
        storages = [make_storage(host_name="h1", node="n1", cluster="cl1",
                                 storage="ceph", shared=True)]
        tp.update_data(node_repo.all(), [], storages, final=True,
                       node_repo=node_repo, vm_repo=None)
        assert tp._tree_mode == "hosts"

        tp.reveal_key(("storage", "ceph", "cluster", "cl1"))
        assert tp._tree_mode == "storages"
        current = tp.tree.currentItem()
        assert current is not None
        assert current.data(0, ITEM_KEY_ROLE) == ("storage", "ceph", "cluster", "cl1")

        # Host keys do not switch the mode
        tp.set_mode("hosts")
        tp.reveal_key(("host", "n1", "h1"))
        assert tp._tree_mode == "hosts"
        assert tp.tree.currentItem().data(0, ITEM_KEY_ROLE) == ("host", "n1", "h1")
