"""Lazy tab building: DetailPanel must not build tab pages at startup.

MainWindow constructs DetailPanel immediately, but the panel stays hidden
until the user selects an object. Building 25 tab pages (~1s of widget
construction) is deferred: a chunked timer builds a couple of pages per
event-loop tick right after the window appears, and _ensure_tabs()
synchronously drains whatever is left on the first selection.
"""

from pve_center.ui.detail_panel import DetailPanel
from pve_center.ui.detail_panel._constants import TabIndex


def test_tabs_not_built_at_construction(qtbot):
    panel = DetailPanel([])
    qtbot.addWidget(panel)
    assert panel._tabs_built is False
    assert panel.tabs.count() == 0


def test_refresh_current_view_noop_without_selection(qtbot):
    panel = DetailPanel([])
    qtbot.addWidget(panel)
    panel.refresh_current_view()
    assert panel.tabs.count() == 0


def test_ensure_tabs_builds_all_pages(qtbot):
    panel = DetailPanel([])
    qtbot.addWidget(panel)
    panel._ensure_tabs()
    assert panel._tabs_built is True
    assert panel.tabs.count() == 25
    assert panel.tabs.tabText(int(TabIndex.MONITOR)) == "Monitoring"


def test_ensure_tabs_is_idempotent(qtbot):
    panel = DetailPanel([])
    qtbot.addWidget(panel)
    panel._ensure_tabs()
    first = panel.tabs.widget(int(TabIndex.MONITOR))
    panel._ensure_tabs()
    assert panel.tabs.widget(int(TabIndex.MONITOR)) is first


def test_chunked_build_drains_queue_in_order(qtbot):
    panel = DetailPanel([])
    qtbot.addWidget(panel)
    for _ in range(50):
        if panel._tabs_built:
            break
        panel._build_tab_chunk()
    assert panel._tabs_built is True
    assert panel.tabs.count() == 25
    assert panel.tabs.tabText(int(TabIndex.HA)) == "HA"


def test_ensure_tabs_finishes_partial_chunked_build(qtbot):
    panel = DetailPanel([])
    qtbot.addWidget(panel)
    panel._build_tab_chunk()  # one chunk: a couple of tabs only
    built_so_far = panel.tabs.count()
    assert 0 < built_so_far < 25
    panel._ensure_tabs()
    assert panel.tabs.count() == 25
    assert panel._tabs_built is True
    # a late chunk tick must not rebuild anything
    panel._build_tab_chunk()
    assert panel.tabs.count() == 25
