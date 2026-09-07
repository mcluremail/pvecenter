"""Lazy tab building: DetailPanel must not build tab pages at startup.

MainWindow constructs DetailPanel immediately, but the panel stays hidden
until the user selects an object. Building 25 tab pages (~1.3s of widget
construction) must be deferred to the first show_details()/explicit
_ensure_tabs() call so the app window appears faster.
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
