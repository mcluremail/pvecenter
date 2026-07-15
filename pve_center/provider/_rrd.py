"""RrdAPI — RRD data PVE endpoints.

Replaces raw requests.Session usage in ui/api/metrics.py.
Uses proxmoxer via ProxmoxSession for unified auth and error handling.
"""

from __future__ import annotations

from ._session import ProxmoxSession, _q


class RrdAPI:
    """RRD data PVE API methods."""

    def __init__(self, session: ProxmoxSession) -> None:
        self._s = session

    def get_vm_rrddata(self, node: str, vmid: int | str, vm_type: str,
                       timeframe: str = "hour", cf: str = "AVERAGE") -> list[dict]:
        """GET /nodes/{node}/{qemu|lxc}/{vmid}/rrddata."""
        if vm_type == "qemu":
            return self._s.call(
                self._s.proxmox.nodes(_q(node)).qemu(_q(vmid)).rrddata.get,
                timeframe=timeframe, cf=cf,
            )
        return self._s.call(
            self._s.proxmox.nodes(_q(node)).lxc(_q(vmid)).rrddata.get,
            timeframe=timeframe, cf=cf,
        )

    def get_node_rrddata(self, node: str, timeframe: str = "hour",
                         cf: str = "AVERAGE") -> list[dict]:
        """GET /nodes/{node}/rrddata."""
        return self._s.call(
            self._s.proxmox.nodes(_q(node)).rrddata.get,
            timeframe=timeframe, cf=cf,
        )

    def get_storage_rrddata(self, node: str, storage: str,
                            timeframe: str = "hour",
                            cf: str = "AVERAGE") -> list[dict]:
        """GET /nodes/{node}/storage/{storage}/rrddata."""
        return self._s.call(
            self._s.proxmox.nodes(_q(node)).storage(_q(storage)).rrddata.get,
            timeframe=timeframe, cf=cf,
        )
