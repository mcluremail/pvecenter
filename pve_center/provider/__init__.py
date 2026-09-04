"""Unified Proxmox API access layer.

Provides typed API methods returning domain objects or raw dicts,
with unified error handling via ProxmoxError hierarchy.

Application code depends on the DataProvider protocol, not on concrete
API classes — see _provider.py (v3.5 groundwork for ServerProvider /
PBS plugins, ARCHITECTURE.md).

Usage::

    from pve_center.provider import ProxmoxProvider

    with ProxmoxProvider(cfg, timeout=15) as provider:
        resources = provider.cluster.list_resources()
        config = provider.vms.get_config("node1", 100, "qemu")
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
)
from ._nodes import NodeAPI
from ._pools import PoolAPI
from ._provider import DataProvider, ProxmoxProvider
from ._rrd import RrdAPI
from ._session import PVE_PORT, ProxmoxSession
from ._storage import StorageAPI
from ._tasks import TaskAPI
from ._vms import VmAPI

__all__ = [
    "AccessAPI",
    "ClusterAPI",
    "DataProvider",
    "NodeAPI",
    "PVE_PORT",
    "PoolAPI",
    "ProxmoxApiError",
    "ProxmoxAuthError",
    "ProxmoxError",
    "ProxmoxNetworkError",
    "ProxmoxNotFoundError",
    "ProxmoxPermissionError",
    "ProxmoxProvider",
    "ProxmoxSession",
    "ProxmoxTimeoutError",
    "RrdAPI",
    "StorageAPI",
    "TaskAPI",
    "VmAPI",
    "from_exception",
]
