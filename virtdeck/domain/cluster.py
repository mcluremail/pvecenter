"""Domain models: ClusterInfo and ClusterNode (corosync node).

Represent data from ``GET /cluster/status`` and ``GET /cluster/config/nodes``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import QuorumState


@dataclass(frozen=True)
class ClusterInfo:
    """Cluster-level quorum information from ``/cluster/status``."""

    quorum_state: QuorumState
    votes: int
    """Active quorum votes."""

    expected_votes: int
    """Expected quorum votes for quorum."""

    @staticmethod
    def from_pve(cluster_entry: dict) -> ClusterInfo:
        """Build ClusterInfo from the ``type == 'cluster'`` entry of /cluster/status."""
        quorate = cluster_entry.get("quorate")
        return ClusterInfo(
            quorum_state=QuorumState.from_pve(quorate),
            votes=cluster_entry.get("votes", 0) or 0,
            expected_votes=cluster_entry.get("expected_votes", 0) or 0,
        )


@dataclass(frozen=True)
class ClusterNode:
    """A corosync node from ``/cluster/status`` + ``/cluster/config/nodes``.

    Merges runtime status (online, quorum_votes, ip) with corosync config
    (ring0_addr, ring1_addr, nodeid).
    """

    name: str
    """PVE node name."""

    online: bool
    """Whether the node is online."""

    quorum_votes: int
    """Quorum votes for this node."""

    ip: str
    """IP address from /cluster/status (fallback for ring0_addr)."""

    ring0_addr: str
    """Corosync ring 0 address."""

    ring1_addr: str
    """Corosync ring 1 address."""

    nodeid: int | str
    """Corosync node ID."""

    @property
    def ring0_display(self) -> str:
        """Ring 0 address, falling back to IP from /cluster/status."""
        return self.ring0_addr or self.ip

    @property
    def votes_display(self) -> str:
        """Quorum votes as string (for table display)."""
        return str(self.quorum_votes) if self.quorum_votes else ""

    @staticmethod
    def from_pve(
        status_entry: dict,
        corosync_entry: dict | None = None,
    ) -> ClusterNode:
        """Build a ClusterNode from merged API data.

        ``status_entry`` is a ``type == 'node'`` entry from /cluster/status.
        ``corosync_entry`` is the matching entry from /cluster/config/nodes
        (or None if not found).
        """
        cs = corosync_entry or {}
        return ClusterNode(
            name=status_entry.get("name", "") or "",
            online=bool(status_entry.get("online")),
            quorum_votes=status_entry.get("quorum_votes", 0) or 0,
            ip=status_entry.get("ip", "") or "",
            ring0_addr=cs.get("ring0_addr", "") or "",
            ring1_addr=cs.get("ring1_addr", "") or "",
            nodeid=cs.get("nodeid", "") or "",
        )


@dataclass(frozen=True)
class ClusterStatus:
    """Full cluster status payload: quorum info + merged corosync nodes.

    Built from ``GET /cluster/status`` (list of cluster/node entries) and
    ``GET /cluster/config/nodes`` (corosync config).
    """

    info: ClusterInfo
    """Cluster-level quorum information."""

    nodes: tuple[ClusterNode, ...]
    """Cluster nodes with merged runtime + corosync config data."""

    @staticmethod
    def from_pve(
        status_list: list[dict],
        corosync_nodes: list[dict] | None = None,
    ) -> ClusterStatus:
        """Build a ClusterStatus from raw API lists."""
        cluster_entry = next(
            (e for e in status_list
             if isinstance(e, dict) and e.get("type") == "cluster"),
            {},
        )
        corosync_map = {
            cn.get("name", ""): cn
            for cn in (corosync_nodes or [])
            if isinstance(cn, dict)
        }
        nodes = tuple(
            ClusterNode.from_pve(e, corosync_map.get(e.get("name", "")))
            for e in status_list
            if isinstance(e, dict) and e.get("type") == "node"
        )
        return ClusterStatus(
            info=ClusterInfo.from_pve(cluster_entry),
            nodes=nodes,
        )
