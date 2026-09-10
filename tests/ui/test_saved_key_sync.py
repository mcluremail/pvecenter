"""Regression: selecting a PBS item must keep MainWindow._saved_key in
sync, otherwise a later hard refresh restores the stale startup selection
(e.g. the cluster from the previous session) and the highlight jumps."""

import pytest

from pve_center.domain.node import Node as DomainNode
from pve_center.domain.repositories import (
    NodeRepository,
    StorageRepository,
    VmRepository,
)
from pve_center.domain.vm import Vm as DomainVm

CFGS = [
    {"name": "pve1", "host": "h1", "port": 8006, "user": "u",
     "token_value": "t", "cluster": "ROS", "cluster_rep": True},
    {"name": "pbs1", "type": "pbs", "host": "h2", "port": 8007,
     "user": "u", "token_value": "t"},
]


@pytest.fixture
def main_window(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from pve_center.ui.mainwindow import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.tree_panel.set_servers(CFGS)
    mw._node_repo = NodeRepository()
    mw._vm_repo = VmRepository()
    mw._storage_repo = StorageRepository()
    mw._node_repo.add(DomainNode.from_pve(
        {"node": "n1", "status": "online"}, "pve1", "ROS", True))
    mw._vm_repo.add(DomainVm.from_pve(
        {"vmid": 100, "node": "n1", "status": "stopped"}, "pve1"))
    yield mw
    mw.close()


def _rebuild(mw):
    mw.tree_panel.update_data(
        mw._node_repo.all(), mw._vm_repo.all(), mw._storage_repo.all(),
        final=True, node_repo=mw._node_repo, vm_repo=mw._vm_repo,
    )


def test_pbs_selection_survives_hard_refresh(main_window):
    mw = main_window
    tp = mw.tree_panel
    tp.set_mode("pbs")
    _rebuild(mw)

    # _saved_key holds the stale value restored from the DB at startup.
    mw._saved_key = ("cluster", "ROS")
    mw._first_selection_done = True

    # User selects the PBS item.
    pbs_item = tp.find_item_by_key(("pbs", "pbs1"))
    assert pbs_item is not None
    tp.tree.setCurrentItem(pbs_item)
    tp._on_item_clicked(pbs_item, 0)
    assert mw._saved_key == ("pbs", "pbs1")

    # Hard refresh: tree cleared (no current), rebuilt, first-selection
    # restore runs — it must bring back PBS, not the stale cluster.
    tp.tree.clear()
    _rebuild(mw)
    mw._do_first_selection()
    # Restore is deferred until the chunked tab build drains (see
    # test_lazy_tabs: no synchronous _ensure_tabs in the worker path).
    while not mw.detail_panel._tabs_built:
        mw.detail_panel._build_tab_chunk()
    assert tp.get_current_item_key() == ("pbs", "pbs1")
