"""NodeAPI — node-level PVE endpoints.

Covers: /nodes, /nodes/{node}/status, /nodes/{node}/version,
/nodes/{node}/storage, /nodes/{node}/network, /nodes/{node}/tasks,
/nodes/{node}/vzdump.
"""

from __future__ import annotations

from ._session import ProxmoxSession, _q


class NodeAPI:
    """Node-level PVE API methods."""

    def __init__(self, session: ProxmoxSession) -> None:
        self._s = session

    def list(self) -> list[dict]:
        """GET /nodes — list all nodes on this host."""
        return self._s.call(self._s.proxmox.nodes.get)

    def get_status(self, node: str) -> dict:
        """GET /nodes/{node}/status."""
        return self._s.call(self._s.proxmox.nodes(_q(node)).status.get)

    def get_version(self, node: str) -> dict:
        """GET /nodes/{node}/version."""
        return self._s.call(self._s.proxmox.nodes(_q(node)).version.get)

    def list_storage(self, node: str) -> list[dict]:
        """GET /nodes/{node}/storage."""
        return self._s.call(self._s.proxmox.nodes(_q(node)).storage.get)

    def list_networks(self, node: str) -> list[dict]:
        """GET /nodes/{node}/network."""
        return self._s.call(self._s.proxmox.nodes(_q(node)).network.get)

    def create_network(self, node: str, **params) -> object:
        """POST /nodes/{node}/network."""
        return self._s.call(self._s.proxmox.nodes(_q(node)).network.post, **params)

    def update_network(self, node: str, iface: str, **params) -> object:
        """PUT /nodes/{node}/network/{iface}."""
        return self._s.call(
            self._s.proxmox.nodes(_q(node)).network(_q(iface)).put, **params
        )

    def delete_network(self, node: str, iface: str, **params) -> object:
        """DELETE /nodes/{node}/network/{iface}."""
        return self._s.call(
            self._s.proxmox.nodes(_q(node)).network(_q(iface)).delete, **params
        )

    def apply_network(self, node: str) -> object:
        """PUT /nodes/{node}/network — apply pending changes."""
        return self._s.call(self._s.proxmox.nodes(_q(node)).network.put)

    def revert_network(self, node: str) -> object:
        """DELETE /nodes/{node}/network — revert pending changes."""
        return self._s.call(self._s.proxmox.nodes(_q(node)).network.delete)

    def list_tasks(self, node: str, limit: int = 100, **params) -> list[dict]:
        """GET /nodes/{node}/tasks."""
        return self._s.call(
            self._s.proxmox.nodes(_q(node)).tasks.get, limit=limit, **params
        )

    def get_task_status(self, node: str, upid: str) -> dict:
        """GET /nodes/{node}/tasks/{upid}/status."""
        return self._s.call(self._s.proxmox.nodes(_q(node)).tasks(_q(upid)).status.get)

    def backup_vzdump(self, node: str, **params) -> object:
        """POST /nodes/{node}/vzdump — on-demand backup."""
        return self._s.call(self._s.proxmox.nodes(_q(node)).vzdump.post, **params)
