"""Tests for animated loading pages (v2.11.2 spinners everywhere)."""
from types import SimpleNamespace

from PySide6.QtWidgets import QLabel, QStackedWidget, QWidget

from pve_center.ui.detail_panel._constants import TabIndex
from pve_center.ui.detail_panel._storage_tabs import StorageTabs
from pve_center.ui.detail_panel._table_utils import (
    loading_label,
    make_loading_stack,
)
from pve_center.ui.widgets.spinner import SpinnerWidget


class TestLoadingLabel:
    def test_contains_spinner(self, qtbot):
        page = loading_label()
        qtbot.addWidget(page)
        page.show()
        spinners = page.findChildren(SpinnerWidget)
        assert len(spinners) == 1
        assert spinners[0].isVisible()

    def test_contains_caption(self, qtbot):
        page = loading_label()
        qtbot.addWidget(page)
        labels = [lb for lb in page.findChildren(QLabel) if lb.text()]
        assert labels, "expected a caption label"


class TestMakeLoadingStack:
    def test_pages(self, qtbot):
        content = QLabel("content")
        stack = make_loading_stack(content)
        qtbot.addWidget(stack)
        assert stack.count() == 2
        assert stack.indexOf(content) == 1
        assert isinstance(stack.widget(0), QWidget)
        assert stack.widget(0).findChildren(SpinnerWidget)
        assert stack.currentIndex() == 0


class TestStorageMonitoringTab:
    def _build(self, qtbot, monkeypatch):
        import pve_center.config as config_mod

        monkeypatch.setattr(
            config_mod, "load_ui_state", lambda key: None
        )
        panel = SimpleNamespace(
            _on_storage_timeframe_changed=lambda *a: None,
        )
        tabs = StorageTabs(panel)
        stack = tabs.build_storage_monitoring_tab()
        qtbot.addWidget(stack)
        return panel, stack

    def test_returns_loading_stack(self, qtbot, monkeypatch):
        panel, stack = self._build(qtbot, monkeypatch)
        assert isinstance(stack, QStackedWidget)
        assert stack.count() == 2
        # Content page (plot) is the default; spinner shows on fetch.
        assert stack.currentIndex() == 1
        assert stack.widget(0).findChildren(SpinnerWidget)

    def test_tab_index_registered(self):
        assert int(TabIndex.STORAGE_MONITORING) == 10
        assert int(TabIndex.BACKUPS) == 11
        assert int(TabIndex.HA) == 24

    def test_timeframe_combo_moved(self, qtbot, monkeypatch):
        panel, stack = self._build(qtbot, monkeypatch)
        assert panel.storage_detail_tf_combo.count() == 5
        assert panel.storage_detail_tf_combo.currentData() == "hour"


class TestLoadingPageCompat:
    """v2.11.2 hotfix: loading pages must keep QLabel-compatible API.

    Worker callbacks call .setText() on loading pages (final states like
    "No data" or "Error: ..."); a bare QWidget container raised
    AttributeError: 'PySide6.QtWidgets.QWidget' object has no attribute
    'setText'.
    """

    def test_settext_proxy(self, qtbot):
        page = loading_label()
        qtbot.addWidget(page)
        initial = page.text()
        assert initial, "caption must be set"
        page.setText("No data")
        assert page.text() == "No data"

    def test_final_text_stops_spinner(self, qtbot):
        page = loading_label()
        qtbot.addWidget(page)
        page.show()
        sp = page.findChildren(SpinnerWidget)[0]
        assert sp.is_running
        page.setText("Error: boom")
        assert not sp.is_running

    def test_loading_text_rearms_spinner(self, qtbot):
        page = loading_label()
        qtbot.addWidget(page)
        page.show()
        sp = page.findChildren(SpinnerWidget)[0]
        initial = page.text()
        page.setText("No data")
        assert not sp.is_running
        page.setText(initial)
        assert sp.is_running
