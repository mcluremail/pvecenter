"""Unified Proxmox API access layer.

Provides typed API methods returning domain objects or raw dicts,
with unified error handling via ProxmoxError hierarchy.

Usage::

    from pve_center.provider import ProxmoxSession, ClusterAPI, VmAPI

    with ProxmoxSession(cfg, timeout=15) as session:
        cluster = ClusterAPI(session)
        resources = cluster.list_resources()
        vms = VmAPI(session)
        config = vms.get_config("node1", 100, "qemu")
"""

from __future__ import annotations

from ._access import AccessAPI
from ._cluster import ClusterAPI
from ._errors import (
    ProxmoxApiError,
    ProxmoxAuthError,
    ProxmoxError,
    ProxmoxNetworkError,
    ProxmoxNotFoundError,
    ProxmoxPermissionError,
    ProxmoxTimeoutError,
    from_exception,
    sanitize,
)
from ._nodes import NodeAPI
from ._pools import PoolAPI
from ._rrd import RrdAPI
from ._session import PVE_PORT, ProxmoxSession
from ._storage import StorageAPI
from ._tasks import TaskAPI
from ._vms import VmAPI

__all__ = [
    "AccessAPI",
    "ClusterAPI",
    "NodeAPI",
    "PVE_PORT",
    "PoolAPI",
    "ProxmoxApiError",
    "ProxmoxAuthError",
    "ProxmoxError",
    "ProxmoxNetworkError",
    "ProxmoxNotFoundError",
    "ProxmoxPermissionError",
    "ProxmoxSession",
    "ProxmoxTimeoutError",
    "RrdAPI",
    "StorageAPI",
    "TaskAPI",
    "VmAPI",
    "from_exception",
    "sanitize",
]
