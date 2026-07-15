"""Domain model layer for PVE Center.

Pure-Python dataclasses and enums representing PVE entities.
No Qt/i18n dependencies — safe to use in any context.
"""

from __future__ import annotations

from .cluster import ClusterInfo, ClusterNode
from .enums import NodeStatus, QuorumState, VmStatus, VmType
from .ha_group import HaGroup
from .ha_resource import HaResource
from .iso_image import IsoImage
from .network import NetworkInterface
from .node import Node
from .pool import Pool
from .repositories import (
    NodeRepository,
    PoolRepository,
    StorageRepository,
    VmRepository,
)
from .snapshot import Snapshot
from .storage import Storage
from .task import Task
from .vm import Vm

__all__ = [
    "ClusterInfo",
    "ClusterNode",
    "HaGroup",
    "HaResource",
    "IsoImage",
    "NetworkInterface",
    "Node",
    "NodeRepository",
    "NodeStatus",
    "Pool",
    "PoolRepository",
    "QuorumState",
    "Snapshot",
    "Storage",
    "StorageRepository",
    "Task",
    "Vm",
    "VmRepository",
    "VmStatus",
    "VmType",
]
