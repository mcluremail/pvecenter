"""Domain model: HaGroup (PVE HA group)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HaGroup:
    """A PVE High Availability group.

    Groups define which nodes a VM can run on for HA purposes.
    """

    group: str
    """Group name (primary identifier)."""

    nodes: str
    """Comma-separated node names."""

    restricted: bool
    """Whether VM can only run on listed nodes."""

    nofailback: bool
    """Whether to skip failback to preferred node."""

    comment: str
    digest: str
    """PVE config digest (for optimistic concurrency)."""

    @property
    def node_list(self) -> list[str]:
        """Node names as a list of stripped strings."""
        return [n.strip() for n in self.nodes.split(",") if n.strip()] if self.nodes else []

    @staticmethod
    def from_pve(d: dict) -> HaGroup:
        """Build an HaGroup from a raw PVE API dict."""
        return HaGroup(
            group=d.get("group", "") or "",
            nodes=d.get("nodes", "") or "",
            restricted=bool(d.get("restricted")),
            nofailback=bool(d.get("nofailback")),
            comment=d.get("comment", "") or "",
            digest=d.get("digest", "") or "",
        )
