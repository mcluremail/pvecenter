"""Domain model: Pool (PVE resource pool).

A pool is a named grouping of VMs.  Members are derived from VMs'
``pool`` field, not stored on the Pool object itself.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pool:
    """A PVE resource pool."""

    poolid: str
    """Pool identifier / name."""

    @staticmethod
    def from_pve(d: dict) -> Pool:
        """Build a Pool from a raw dict (``{"poolid": "name"}``)."""
        return Pool(poolid=d.get("poolid", "") or d.get("pool", "") or "")
