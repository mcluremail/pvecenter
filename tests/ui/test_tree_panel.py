"""Tests for TreePanel with domain objects."""
import json

from PySide6.QtCore import QMimeData, QPointF
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from pve_center.domain.enums import VmStatus
from pve_center.domain.repositories import NodeRepository, VmRepository
from pve_center.ui.i18n import tr
from pve_center.ui.tree_panel import (
    GROUP_MIME,
    ITEM_KEY_ROLE,
    VM_KEY_ROLE,
    GroupTreeWidget,
    TreePanel,
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

        # Should have Clusters + Standalone hosts sections
        top = tp.tree.topLevelItemCount()
        assert top >= 2
        # Find standalone folder
        for i in range(top):
            item = tp.tree.topLevelItem(i)
            if "Standalone" in item.text(0):
                assert item.childCount() == 1
                child = item.child(0)
                assert "pve01" in child.text(0)
                return
        raise AssertionError("Standalone folder not found")

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

        # Find the host item
        for i in range(tp.tree.topLevelItemCount()):
            item = tp.tree.topLevelItem(i)
            if "Standalone" in item.text(0):
                host = item.child(0)
                text = host.text(0)
                # [running/total] = [1/2]
                assert "[1/2]" in text
                # Should have 2 vm children
                assert host.childCount() == 2
                return
        raise AssertionError("Host not found")

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

        # Find Clusters folder
        for i in range(tp.tree.topLevelItemCount()):
            item = tp.tree.topLevelItem(i)
            if "Clusters" in item.text(0):
                assert item.childCount() == 1  # one cluster
                cl = item.child(0)
                assert "mycluster" in cl.text(0)
                assert cl.childCount() == 2  # two nodes
                return
        raise AssertionError("Clusters folder not found")

    def test_empty_tree(self, qtbot):
        cfg = []
        tp = TreePanel(cfg)
        qtbot.addWidget(tp)

        node_repo = NodeRepository()
        vm_repo = VmRepository()
        tp.update_data(node_repo.all(), vm_repo.all(), final=True,
                       node_repo=node_repo, vm_repo=vm_repo)
        tp._build_tree()
        # Should still have section headers
        assert tp.tree.topLevelItemCount() >= 2

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

        for i in range(tp.tree.topLevelItemCount()):
            item = tp.tree.topLevelItem(i)
            if "Standalone" in item.text(0):
                host = item.child(0)
                assert "h1" in host.text(0)
                return
        raise AssertionError("Error host not found")


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

        # Collect VM items (items carrying a VM key)
        vm_items = []
        for i in range(tp.tree.topLevelItemCount()):
            top = tp.tree.topLevelItem(i)
            for j in range(top.childCount()):
                host = top.child(j)
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

    def _collect_items(self, tp):
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

        items = self._collect_items(tp)
        group_key = next((k for k in items if k[0] == "group"), None)
        assert group_key is not None
        assert group_key[1] == "Site A"
        # Group shows aggregated VM count
        assert "[1/1]" in items[group_key].text(0)
        # Host is under the group, not under Standalone hosts
        host_key = next((k for k in items if k[0] == "host"), None)
        assert host_key == ("host", "pve01", "h1")
        assert items[host_key].parent() is items[group_key]
        standalone_key = next((k for k in items if k[0] == "section"
                               and "Standalone" in k[1]), None)
        assert standalone_key in items
        assert items[host_key].parent() is not items[standalone_key]

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

        items = self._collect_items(tp)
        group_key = next((k for k in items if k[0] == "group"), None)
        assert group_key is not None
        assert group_key[1] == "DC West"
        # Cluster item lives inside the group
        cluster_key = next((k for k in items if k[0] == "cluster"), None)
        assert cluster_key == ("cluster", "cl1")
        assert items[cluster_key].parent() is items[group_key]
        # Clusters section must not contain it
        clusters_section = next((k for k in items if k[0] == "section"
                                 and k[1] == tr("Clusters")), None)
        assert clusters_section is not None
        assert items[cluster_key].parent() is not items[clusters_section]

    def test_ungrouped_hosts_in_sections(self, qtbot, make_node):
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

        items = self._collect_items(tp)
        group_key = next((k for k in items if k[0] == "group"), None)
        assert group_key == ("group", "Site A")
        hosts = [k for k in items if k[0] == "host"]
        host_parents = {k: items[k].parent() for k in hosts}
        h1_key = next(k for k in hosts if k[2] == "h1")
        h2_key = next(k for k in hosts if k[2] == "h2")
        assert host_parents[h1_key] is items[group_key]
        standalone_key = next((k for k in items if k[0] == "section"
                               and "Standalone" in k[1]), None)
        assert host_parents[h2_key] is items[standalone_key]

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

        items = self._collect_items(tp)
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

        section = QTreeWidgetItem([tr("Standalone hosts")])
        section.setData(0, ITEM_KEY_ROLE, ("section", tr("Standalone hosts")))
        gt.addTopLevelItem(section)
        host_in_section = QTreeWidgetItem(["h2"])
        host_in_section.setData(0, ITEM_KEY_ROLE, ("host", "n2", "h2"))
        section.addChild(host_in_section)

        storage = QTreeWidgetItem([tr("Storage")])
        storage.setData(0, ITEM_KEY_ROLE, ("section", tr("Storage")))
        gt.addTopLevelItem(storage)

        items = {
            "group": group,
            "host_in_group": host_in_group,
            "cluster_in_group": cluster_in_group,
            "section": section,
            "host_in_section": host_in_section,
            "storage": storage,
        }
        return tp, gt, items

    def test_drag_payload(self, qtbot):
        _tp, gt, items = self._make_widget(qtbot)
        assert gt._drag_payload(items["host_in_group"]) == {"kind": "host", "name": "h1"}
        assert gt._drag_payload(items["cluster_in_group"]) == {"kind": "cluster", "name": "cl1"}
        # Non-draggable: group, section, plain items
        assert gt._drag_payload(items["group"]) is None
        assert gt._drag_payload(items["section"]) is None
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
        # Sections: ungroup targets vs. Storage
        assert gt._drop_group(items["section"]) == ""
        assert gt._drop_group(items["storage"]) is None
        # Host still under Standalone hosts -> no target
        assert gt._drop_group(items["host_in_section"]) is None
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
        gt.itemAt = lambda _p: items["storage"]
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
