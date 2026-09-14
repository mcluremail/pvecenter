"""Plugin API (v3.5) — protocols and registry in plugins/base.py.

Built-in registry carries the Proxmox VE data-source plugin;
``create_provider(cfg)`` dispatches by ``cfg["type"]`` (default "pve").
"""

from __future__ import annotations

from ..provider import DataProvider
from ._pbs import PbsPlugin
from ._pve import PvePlugin
from ._themes import (
    BreezeDarkTheme,
    BreezeTheme,
    GraphiteTheme,
    LightTheme,
    OxygenTheme,
    SystemTheme,
)
from .base import Plugin, PluginError, PluginRegistry, ProviderPlugin, ThemePlugin

_BUILTINS = (PvePlugin(), PbsPlugin())
_BUILTIN_THEMES = (
    LightTheme(),
    BreezeTheme(),
    BreezeDarkTheme(),
    OxygenTheme(),
    GraphiteTheme(),
    SystemTheme(),
)


def default_registry() -> PluginRegistry:
    """Fresh registry with built-in plugins; callers may extend it."""
    reg = PluginRegistry()
    for plugin in _BUILTINS:
        reg.register(plugin)
    for theme in _BUILTIN_THEMES:
        reg.register_theme(theme)
    return reg


_registry: PluginRegistry | None = None


def get_registry() -> PluginRegistry:
    """Process-wide registry (lazy singleton)."""
    global _registry
    if _registry is None:
        _registry = default_registry()
    return _registry


def create_provider(cfg: dict, timeout: float = 15) -> DataProvider:
    """Build the DataProvider for a host config (plugin dispatch by type)."""
    return get_registry().create_provider(cfg, timeout=timeout)


__all__ = [
    "Plugin",
    "PluginError",
    "PluginRegistry",
    "ProviderPlugin",
    "ThemePlugin",
    "PbsPlugin",
    "PvePlugin",
    "LightTheme",
    "BreezeTheme",
    "BreezeDarkTheme",
    "OxygenTheme",
    "GraphiteTheme",
    "SystemTheme",
    "create_provider",
    "default_registry",
    "get_registry",
]
