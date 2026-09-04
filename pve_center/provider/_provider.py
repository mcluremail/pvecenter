"""Data provider seam (ARCHITECTURE.md: ProxmoxProvider / ServerProvider).

DataProvider is the protocol the application core depends on instead of
concrete Proxmox API classes. Today the only implementation talks
directly to Proxmox VE (PveProvider groundwork: ProxmoxProvider); later
the same surface can be served by the pve-center server backend
(ServerProvider) or a PBS plugin without touching backend workers.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ._access import AccessAPI
from ._cluster import ClusterAPI
from ._nodes import NodeAPI
from ._pools import PoolAPI
from ._rrd import RrdAPI
from ._session import ProxmoxSession
from ._storage import StorageAPI
from ._tasks import TaskAPI
from ._vms import VmAPI


@runtime_checkable
class DataProvider(Protocol):
    """Unified read/write surface over a managed environment."""

    @property
    def nodes(self) -> NodeAPI: ...

    @property
    def vms(self) -> VmAPI: ...

    @property
    def cluster(self) -> ClusterAPI: ...

    @property
    def storage(self) -> StorageAPI: ...

    @property
    def tasks(self) -> TaskAPI: ...

    @property
    def pools(self) -> PoolAPI: ...

    @property
    def access(self) -> AccessAPI: ...

    @property
    def rrd(self) -> RrdAPI: ...

    def close(self) -> None: ...


class ProxmoxProvider:
    """DataProvider implementation on top of the Proxmox VE API.

    Wraps one ProxmoxSession; API facades are created lazily and share
    its connection pool. ``close()`` releases the underlying session.
    """

    def __init__(self, cfg: dict, timeout: float = 15) -> None:
        self._session = ProxmoxSession(cfg, timeout=timeout)
        self._nodes: NodeAPI | None = None
        self._vms: VmAPI | None = None
        self._cluster: ClusterAPI | None = None
        self._storage: StorageAPI | None = None
        self._tasks: TaskAPI | None = None
        self._pools: PoolAPI | None = None
        self._access: AccessAPI | None = None
        self._rrd: RrdAPI | None = None

    @property
    def nodes(self) -> NodeAPI:
        if self._nodes is None:
            self._nodes = NodeAPI(self._session)
        return self._nodes

    @property
    def vms(self) -> VmAPI:
        if self._vms is None:
            self._vms = VmAPI(self._session)
        return self._vms

    @property
    def cluster(self) -> ClusterAPI:
        if self._cluster is None:
            self._cluster = ClusterAPI(self._session)
        return self._cluster

    @property
    def storage(self) -> StorageAPI:
        if self._storage is None:
            self._storage = StorageAPI(self._session)
        return self._storage

    @property
    def tasks(self) -> TaskAPI:
        if self._tasks is None:
            self._tasks = TaskAPI(self._session)
        return self._tasks

    @property
    def pools(self) -> PoolAPI:
        if self._pools is None:
            self._pools = PoolAPI(self._session)
        return self._pools

    @property
    def access(self) -> AccessAPI:
        if self._access is None:
            self._access = AccessAPI(self._session)
        return self._access

    @property
    def rrd(self) -> RrdAPI:
        if self._rrd is None:
            self._rrd = RrdAPI(self._session)
        return self._rrd

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> ProxmoxProvider:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
