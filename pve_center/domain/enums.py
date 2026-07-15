"""Domain enums for PVE entities.

Enums are pure Python — no Qt/i18n dependencies.
"""

from __future__ import annotations

from enum import Enum


class NodeStatus(Enum):
    """Operational status of a PVE node."""

    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    UNKNOWN = "unknown"

    @staticmethod
    def from_pve(value: str | None) -> NodeStatus:
        """Convert a raw PVE status string to enum.

        Unknown/missing values map to UNKNOWN.
        """
        try:
            return NodeStatus(value)
        except (ValueError, TypeError):
            return NodeStatus.UNKNOWN


class VmStatus(Enum):
    """Operational status of a PVE VM or container."""

    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    UNKNOWN = "unknown"

    @staticmethod
    def from_pve(value: str | None) -> VmStatus:
        """Convert a raw PVE status string to enum.

        Unknown/missing values map to UNKNOWN.
        """
        try:
            return VmStatus(value)
        except (ValueError, TypeError):
            return VmStatus.UNKNOWN


class VmType(Enum):
    """Type of a PVE virtual machine."""

    QEMU = "qemu"
    LXC = "lxc"
    UNKNOWN = "unknown"

    @staticmethod
    def from_pve(value: str | None) -> VmType:
        """Convert a raw PVE type string to enum."""
        try:
            return VmType(value)
        except (ValueError, TypeError):
            return VmType.UNKNOWN


class QuorumState(Enum):
    """Cluster quorum state."""

    OK = "ok"
    LOST = "lost"
    UNKNOWN = "unknown"

    @staticmethod
    def from_pve(quorate: int | bool | None) -> QuorumState:
        """Derive quorum state from the ``quorate`` field."""
        if quorate:
            return QuorumState.OK
        if quorate is not None and not quorate:
            return QuorumState.LOST
        return QuorumState.UNKNOWN
