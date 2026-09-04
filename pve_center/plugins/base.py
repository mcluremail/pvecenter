"""Plugin API seed (v3.5, ARCHITECTURE.md).

A plugin is a named extension unit contributing functionality to the
application. The first family is data-source plugins: they build a
DataProvider from a host config dict. The Proxmox VE plugin is built-in;
PBS (B17 stage 2) and pve-center Server (v4.0) land as further plugins
without touching backend workers.

Feature plugins (Notifications, Policies, Reports, Prometheus, Redfish)
will extend this seam later; registration stays explicit — no dynamic
import magic.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..provider import DataProvider


class PluginError(Exception):
    """Raised for unknown plugin ids or misuse of a registered plugin."""


@runtime_checkable
class Plugin(Protocol):
    """Named extension unit."""

    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...


@runtime_checkable
class ProviderPlugin(Plugin, Protocol):
    """Data-source plugin: builds a DataProvider from a host config.

    Host configs carry ``"type"`` (missing type defaults to ``"pve"``);
    the plugin receives the raw config dict and must return an object
    satisfying provider.DataProvider.
    """

    def create_provider(self, cfg: dict, timeout: float = 15) -> DataProvider: ...


class PluginRegistry:
    """Id → plugin map with data-source dispatch."""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        pid = plugin.id
        if pid in self._plugins:
            raise PluginError(f"plugin already registered: {pid!r}")
        self._plugins[pid] = plugin

    def get(self, plugin_id: str) -> Plugin:
        try:
            return self._plugins[plugin_id]
        except KeyError:
            raise PluginError(f"unknown plugin: {plugin_id!r}") from None

    def ids(self) -> list[str]:
        return sorted(self._plugins)

    def create_provider(self, cfg: dict, timeout: float = 15) -> DataProvider:
        plugin_id = cfg.get("type", "pve")
        plugin = self.get(plugin_id)
        create = getattr(plugin, "create_provider", None)
        if create is None:
            raise PluginError(
                f"plugin {plugin_id!r} does not provide data sources")
        return create(cfg, timeout=timeout)
