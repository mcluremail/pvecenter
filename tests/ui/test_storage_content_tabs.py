"""Regression: load_storage_content must address content tabs via TabIndex.

The Monitoring tab insertion shifted raw indexes 10-13; tab_map kept stale
raw numbers and relabeled the wrong tabs (chart under "Backups" etc.).
"""

from types import SimpleNamespace

from pve_center.ui.detail_panel import DetailPanel
from pve_center.ui.detail_panel._constants import TabIndex
from pve_center.ui.detail_panel._storage_tabs import StorageTabs
from pve_center.ui.i18n import tr


def _build(qtbot):
    panel = DetailPanel([])
    qtbot.addWidget(panel)
    panel._cfg_by_name = {}
    panel._ensure_tabs()
    return panel, StorageTabs(panel)


def test_content_tabs_use_tab_index(qtbot):
    panel, storage_tabs = _build(qtbot)
    rep = SimpleNamespace(
        content_list=["backup", "images", "iso", "vztmpl"],
        node="n1",
        host_name="h1",
    )
    storage_tabs.load_storage_content("local", [rep], rep)

    expected = {
        TabIndex.BACKUPS: tr("Backups"),
        TabIndex.DISKS_VM: tr("VM Disks"),
        TabIndex.ISO: tr("ISO"),
        TabIndex.TEMPLATES: tr("Templates"),
    }
    for idx, title in expected.items():
        assert panel.tabs.isTabVisible(idx), f"tab {idx} should be visible"
        assert panel.tabs.tabText(idx) == title, f"tab {idx} label mismatch"


def test_monitoring_tab_not_reused(qtbot):
    panel, storage_tabs = _build(qtbot)
    rep = SimpleNamespace(
        content_list=["backup", "images", "iso", "vztmpl"],
        node="n1",
        host_name="h1",
    )
    storage_tabs.load_storage_content("local", [rep], rep)

    mon = TabIndex.STORAGE_MONITORING
    assert panel.tabs.tabText(mon) == tr("Monitoring")
