"""Tests for TreePanel with domain objects."""
from pve_center.domain.enums import VmStatus
from pve_center.domain.repositories import NodeRepository, VmRepository
from pve_center.ui.tree_panel import TreePanel


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
