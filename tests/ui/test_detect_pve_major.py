"""Tests for _detect_pve_major: version routing for backup jobs API (PVE7/8/9)."""

from types import SimpleNamespace

from pve_center.ui.detail_panel._host_tabs import HostTabs


def make(major_raw):
    """Build a HostTabs instance without running Qt __init__."""
    h = HostTabs.__new__(HostTabs)
    h.panel = SimpleNamespace(
        all_nodes=[SimpleNamespace(host_name="h1", pve_version_raw=major_raw)])
    return h


class TestDetectPveMajor:
    def test_pve7_string(self):
        assert make("pve-manager/7.4-3/0615a192")._detect_pve_major(
            {"name": "h1"}) == 7

    def test_pve8_string(self):
        assert make("pve-manager/8.2.4/1d1797f6785b6c23")._detect_pve_major(
            {"name": "h1"}) == 8

    def test_pve9_string(self):
        assert make("pve-manager/9.1.2")._detect_pve_major({"name": "h1"}) == 9

    def test_bare_version(self):
        assert make("7.2-1")._detect_pve_major({"name": "h1"}) == 7

    def test_unknown_host_defaults_to_7(self):
        # Safe fallback: routes to the legacy /cluster/backup API.
        assert make("pve-manager/8.1.1")._detect_pve_major(
            {"name": "other"}) == 7

    def test_empty_version_defaults_to_7(self):
        assert make("")._detect_pve_major({"name": "h1"}) == 7
