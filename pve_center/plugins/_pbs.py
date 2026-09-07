"""Built-in Proxmox Backup Server data-source plugin (B17 stage 2)."""

from __future__ import annotations

from ..pbs import PbsProvider


class PbsPlugin:
    """Dispatch target for host configs of type "pbs"."""

    id = "pbs"
    name = "Proxmox Backup Server"

    def create_provider(self, cfg: dict, timeout: float = 15) -> PbsProvider:
        return PbsProvider(cfg, timeout=timeout)
