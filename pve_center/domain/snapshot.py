"""Domain model: Snapshot (VM or container snapshot)."""

from __future__ import annotations

from dataclasses import dataclass

from ._format import format_volsize


@dataclass(frozen=True)
class Snapshot:
    """A PVE VM/container snapshot.

    The ``current`` pseudo-snapshot is excluded — it is filtered out
    by ``VmSnapshotsWorker`` and ``HostSnapshotsWorker`` before data
    reaches this model.
    """

    # -- Identity --
    name: str
    """Snapshot name (primary identifier)."""

    # -- Attributes --
    description: str
    snaptime: int
    """Unix timestamp (epoch seconds) of creation."""

    parent: str
    """Parent snapshot name; empty if root."""

    vmstate: bool
    """Whether RAM state is included."""

    size_bytes: int
    """Total disk size in bytes (computed from snapshot config)."""

    # -- Synthetic fields (added by HostSnapshotsWorker for host-level view) --
    vmid: int
    """VM ID (0 for VM-level snapshots where vmid is implied)."""

    vm_name: str
    """VM name (empty for VM-level snapshots)."""

    host_name: str
    """pve-center config name (empty for VM-level snapshots)."""

    node: str
    """PVE node name (empty for VM-level snapshots)."""

    # -- Computed properties --
    @property
    def size_str(self) -> str:
        """Human-readable size (GiB / TiB), or '—' for zero."""
        return format_volsize(self.size_bytes) if self.size_bytes else "—"

    @property
    def is_root(self) -> bool:
        """Whether this is a root snapshot (no parent)."""
        return not self.parent or self.parent == "current"

    @staticmethod
    def from_pve(d: dict) -> Snapshot:
        """Build a Snapshot from a raw PVE API dict.

        Synthetic fields (vmid, vm_name, host_name, node) default to
        empty/zero when not present (VM-level snapshots).
        """
        return Snapshot(
            name=d.get("name", "") or "",
            description=d.get("description", "") or "",
            snaptime=d.get("snaptime", 0) or 0,
            parent=d.get("parent", "") or "",
            vmstate=bool(d.get("vmstate")),
            size_bytes=d.get("size", 0) or 0,
            vmid=d.get("vmid", 0) or 0,
            vm_name=d.get("vm_name", "") or "",
            host_name=d.get("host_name", "") or "",
            node=d.get("node", "") or "",
        )
