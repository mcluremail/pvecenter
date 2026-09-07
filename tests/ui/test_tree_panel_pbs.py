"""Tests for TreePanel PBS items (B17 stage 2)."""
import pytest

from pve_center.ui.tree_panel import TreePanel
from tests.ui.test_tree_panel import _collect_items


@pytest.fixture(autouse=True)
def _isolated_tree_state(monkeypatch):
    import pve_center.ui.tree_panel as tp_mod

    state = {}
    monkeypatch.setattr(tp_mod, "load_ui_state", lambda key: state.get(key))
    monkeypatch.setattr(
        tp_mod, "save_ui_state", lambda key, value: state.__setitem__(key, value)
    )


def _panel(qtbot, cfgs):
    tp = TreePanel(cfgs)
    qtbot.addWidget(tp)
    return tp


_PBS = {"name": "pbs1", "type": "pbs", "host": "pbs.local",
        "port": 8007, "user": "root@pam", "token_value": "s"}


class TestPbsItems:
    def test_start_loading_adds_pbs_item(self, qtbot):
        tp = _panel(qtbot, [{"name": "h1", "skip": False}, _PBS])
        tp.start_loading()
        items = _collect_items(tp)
        assert ("pbs", "pbs1") in items
        assert ("host", "h1") in items
        # PBS servers never join the loading-spinner bookkeeping
        assert "pbs1" not in tp._loading_hosts

    def test_skipped_pbs_excluded(self, qtbot):
        tp = _panel(qtbot, [{**_PBS, "skip": True}])
        tp.start_loading()
        assert ("pbs", "pbs1") not in _collect_items(tp)

    def test_hosts_view_includes_pbs(self, qtbot, make_node):
        tp = _panel(qtbot, [{"name": "h1", "skip": False}, _PBS])
        tp.update_data([make_node()], [], [], final=True,
                       node_repo=tp._node_repo, vm_repo=tp._vm_repo)
        items = _collect_items(tp)
        assert ("pbs", "pbs1") in items
        assert items[("pbs", "pbs1")].text(1) == "pbs.local"

    def test_hosts_view_no_loading_stub_for_pbs(self, qtbot):
        """_compute_grouping must not create a host loading-stub for a PBS
        cfg (regression: eternal spinner duplicate of the PBS item)."""
        tp = _panel(qtbot, [_PBS])
        tp.update_data([], [], [], final=True,
                       node_repo=tp._node_repo, vm_repo=tp._vm_repo)
        items = _collect_items(tp)
        assert ("pbs", "pbs1") in items
        assert not [k for k in items if k[0] == "host" and "pbs1" in k]
        assert "pbs1" not in tp._loading_hosts

    def test_set_pbs_datastores(self, qtbot):
        tp = _panel(qtbot, [_PBS])
        tp.start_loading()
        stores = [type("DS", (), {"name": "main", "usage": 0.5})(),
                  type("DS", (), {"name": "alt", "usage": 0.9})()]
        tp.set_pbs_datastores("pbs1", stores)
        items = _collect_items(tp)
        assert ("pbs_datastore", "pbs1", "alt") in items
        assert ("pbs_datastore", "pbs1", "main") in items
        ds_item = items[("pbs_datastore", "pbs1", "main")]
        assert ds_item.text(1) == "50%"
        assert ds_item.parent() is items[("pbs", "pbs1")]

    def test_set_pbs_datastores_unknown_server_noop(self, qtbot):
        tp = _panel(qtbot, [_PBS])
        tp.start_loading()
        tp.set_pbs_datastores("nope", [])
        items = _collect_items(tp)
        assert not items[("pbs", "pbs1")].childCount()

    def test_click_pbs_emits(self, qtbot):
        tp = _panel(qtbot, [_PBS])
        tp.start_loading()
        emitted = []
        tp.item_selected.connect(lambda t, n, d: emitted.append((t, n, d)))
        items = _collect_items(tp)
        tp._on_item_clicked(items[("pbs", "pbs1")], 0)
        assert emitted == [("pbs", "pbs1", {})]

    def test_click_pbs_datastore_emits(self, qtbot):
        tp = _panel(qtbot, [_PBS])
        tp.start_loading()
        stores = [type("DS", (), {"name": "main", "usage": 0.5})()]
        tp.set_pbs_datastores("pbs1", stores)
        emitted = []
        tp.item_selected.connect(lambda t, n, d: emitted.append((t, n, d)))
        items = _collect_items(tp)
        tp._on_item_clicked(items[("pbs_datastore", "pbs1", "main")], 0)
        assert emitted == [("pbs_datastore", "pbs1",
                            {"server": "pbs1", "store": "main"})]


class TestDatastoreSelectionPreserved:
    """Regression: taking/rebuilding datastore children must not throw the
    selection to a random tree item (user: 'selection jumps from PBS')."""

    def test_refill_preserves_datastore_selection(self, qtbot):
        tp = _panel(qtbot, [_PBS])
        tp.start_loading()
        stores = [type("DS", (), {"name": "main", "usage": 0.5})()]
        tp.set_pbs_datastores("pbs1", stores)
        ds = _collect_items(tp)[("pbs_datastore", "pbs1", "main")]
        tp.tree.setCurrentItem(ds)
        # second fill (e.g. show_datastore reload) recreates children
        tp.set_pbs_datastores("pbs1", stores)
        assert tp.get_current_item_key() == ("pbs_datastore", "pbs1", "main")

    def test_rebuild_falls_back_to_pbs_parent(self, qtbot, make_node):
        tp = _panel(qtbot, [_PBS])
        tp.start_loading()
        stores = [type("DS", (), {"name": "main", "usage": 0.5})()]
        tp.set_pbs_datastores("pbs1", stores)
        tp.tree.setCurrentItem(
            _collect_items(tp)[("pbs_datastore", "pbs1", "main")])
        # rebuild loses datastore children -> land on the PBS server item,
        # never on an unrelated group/cluster/host
        tp.update_data([make_node()], [], [], final=True,
                       node_repo=tp._node_repo, vm_repo=tp._vm_repo)
        assert tp.get_current_item_key() == ("pbs", "pbs1")

    def test_rebuild_then_refill_restores_child(self, qtbot, make_node):
        tp = _panel(qtbot, [_PBS])
        tp.start_loading()
        stores = [type("DS", (), {"name": "main", "usage": 0.5})()]
        tp.set_pbs_datastores("pbs1", stores)
        tp.tree.setCurrentItem(
            _collect_items(tp)[("pbs_datastore", "pbs1", "main")])
        tp.update_data([make_node()], [], [], final=True,
                       node_repo=tp._node_repo, vm_repo=tp._vm_repo)
        tp.set_pbs_datastores("pbs1", stores)
        assert tp.get_current_item_key() == ("pbs_datastore", "pbs1", "main")

    def test_refill_does_not_reemit_selection(self, qtbot):
        """Refill must restore the selection silently: no item_selected
        re-emission (it re-ran show_datastore and reset the active tab)."""
        tp = _panel(qtbot, [_PBS])
        tp.start_loading()
        stores = [type("DS", (), {"name": "main", "usage": 0.5})()]
        tp.set_pbs_datastores("pbs1", stores)
        tp.tree.setCurrentItem(
            _collect_items(tp)[("pbs_datastore", "pbs1", "main")])
        qtbot.wait(400)  # flush nav timer fired by the manual setCurrentItem
        emitted = []
        tp.item_selected.connect(lambda t, n, d: emitted.append((t, n, d)))
        tp.set_pbs_datastores("pbs1", stores)
        qtbot.wait(400)
        assert emitted == []
        assert tp.get_current_item_key() == ("pbs_datastore", "pbs1", "main")
