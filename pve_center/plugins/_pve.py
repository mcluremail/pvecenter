"""Built-in Proxmox VE data-source plugin."""

from __future__ import annotations

from ..provider import DataProvider, ProxmoxProvider


class PvePlugin:
    """Dispatch target for host configs of type "pve" (the default)."""

    id = "pve"
    name = "Proxmox VE"

    def create_provider(self, cfg: dict, timeout: float = 15) -> DataProvider:
        return ProxmoxProvider(cfg, timeout=timeout)
