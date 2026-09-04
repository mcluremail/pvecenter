"""Tests for pve_center/plugins — registry, dispatch, built-in PVE plugin."""

from __future__ import annotations

import pytest

from pve_center.plugins import (
    PluginError,
    PluginRegistry,
    ProviderPlugin,
    PvePlugin,
    create_provider,
    default_registry,
    get_registry,
)
from pve_center.provider import DataProvider, ProxmoxProvider

_CFG = {"host": "h", "user": "u", "token_name": "t", "token_value": "v"}


class TestRegistry:
    def test_default_registry_has_pve(self):
        assert default_registry().ids() == ["pve"]

    def test_register_and_get(self):
        reg = PluginRegistry()
        plugin = PvePlugin()
        reg.register(plugin)
        assert reg.get("pve") is plugin

    def test_duplicate_registration_raises(self):
        reg = default_registry()
        with pytest.raises(PluginError, match="already registered"):
            reg.register(PvePlugin())

    def test_unknown_plugin_raises(self):
        with pytest.raises(PluginError, match="unknown plugin"):
            default_registry().get("nope")

    def test_process_wide_registry_is_singleton(self):
        assert get_registry() is get_registry()


class TestCreateProvider:
    def test_default_type_is_pve(self):
        assert isinstance(create_provider(_CFG), ProxmoxProvider)

    def test_explicit_pve_type(self):
        assert isinstance(create_provider({**_CFG, "type": "pve"}),
                          ProxmoxProvider)

    def test_unknown_type_raises(self):
        with pytest.raises(PluginError, match="unknown plugin"):
            create_provider({**_CFG, "type": "nope"})

    def test_timeout_passthrough(self):
        provider = create_provider(_CFG, timeout=42)
        assert provider._session.timeout == 42

    def test_provider_satisfies_protocol(self):
        assert isinstance(create_provider(_CFG), DataProvider)


class TestCustomPlugin:
    def test_third_party_plugin_dispatch(self):
        class StubProvider:
            def close(self):
                pass

        class FakePlugin:
            id = "fake"
            name = "Fake Source"

            def create_provider(self, cfg, timeout=15):
                return StubProvider()

        reg = default_registry()
        reg.register(FakePlugin())
        assert isinstance(reg.ids(), list) and "fake" in reg.ids()
        assert isinstance(
            reg.create_provider({**_CFG, "type": "fake"}), StubProvider)

    def test_non_provider_plugin_rejected_for_dispatch(self):
        class NotAProviderPlugin:
            id = "misc"
            name = "Misc feature plugin"

        reg = PluginRegistry()
        reg.register(NotAProviderPlugin())
        with pytest.raises(PluginError, match="does not provide data sources"):
            reg.create_provider({**_CFG, "type": "misc"})

    def test_pve_plugin_satisfies_provider_plugin_protocol(self):
        assert isinstance(PvePlugin(), ProviderPlugin)
