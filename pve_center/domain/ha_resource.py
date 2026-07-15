"""Domain model: HaResource (PVE HA managed resource)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HaResource:
    """A PVE HA-managed resource (typically a VM).

    Resources are VMs that are managed by the HA manager.
    """

    sid: str
    """Resource identifier, e.g. 'vm:100'."""

    group: str
    """HA group name this resource belongs to."""

    state: str
    """HA state: 'default', 'started', 'stopped', 'enabled', 'ignored'."""

    max_restart: int
    """Max restart attempts on failure."""

    max_relocate: int
    """Max relocate attempts on failure."""

    comment: str

    @property
    def vmid(self) -> int | None:
        """Extract VM ID from sid, e.g. 'vm:100' → 100. None if unparseable."""
        if self.sid.startswith("vm:"):
            try:
                return int(self.sid[3:])
            except ValueError:
                pass
        return None

    @staticmethod
    def from_pve(d: dict) -> HaResource:
        """Build an HaResource from a raw PVE API dict."""
        return HaResource(
            sid=d.get("sid", "") or "",
            group=d.get("group", "") or "",
            state=d.get("state", "") or "",
            max_restart=d.get("max_restart", 1) or 1,
            max_relocate=d.get("max_relocate", 1) or 1,
            comment=d.get("comment", "") or "",
        )
