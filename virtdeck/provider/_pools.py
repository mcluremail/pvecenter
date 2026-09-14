"""PoolAPI — pool PVE endpoints.

Covers: /pools, /pools/{poolid}.
"""

from __future__ import annotations

from ._session import ProxmoxSession, _q


class PoolAPI:
    """Pool PVE API methods."""

    def __init__(self, session: ProxmoxSession) -> None:
        self._s = session

    def list(self) -> list[dict]:
        """GET /pools — list all pools."""
        return self._s.call(self._s.proxmox.pools.get)

    def get(self, pool_id: str) -> dict:
        """GET /pools/{poolid} — pool detail with members."""
        return self._s.call(self._s.proxmox.pools(_q(pool_id)).get)
