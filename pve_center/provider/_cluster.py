"""ClusterAPI — cluster-level PVE endpoints.

Covers: /cluster/resources, /cluster/status, /cluster/nextid,
/cluster/ha/groups, /cluster/ha/resources, /cluster/backup, /cluster/jobs,
/cluster/config/nodes.
"""

from __future__ import annotations

from ._session import ProxmoxSession, _q


class ClusterAPI:
    """Cluster-level PVE API methods."""

    def __init__(self, session: ProxmoxSession) -> None:
        self._s = session

    def list_resources(self) -> list[dict]:
        """GET /cluster/resources — all nodes/vms/storages."""
        return self._s.call(self._s.proxmox.cluster.resources.get)

    def get_status(self) -> list[dict]:
        """GET /cluster/status — cluster quorum and node list."""
        return self._s.call(self._s.proxmox.cluster.status.get)

    def get_config_nodes(self) -> list[dict]:
        """GET /cluster/config/nodes — corosync node config."""
        return self._s.call(self._s.proxmox.cluster.config.nodes.get)

    def next_vmid(self) -> int:
        """GET /cluster/nextid — next free VMID."""
        result = self._s.call(self._s.proxmox.cluster.nextid.get)
        if isinstance(result, str):
            return int(result)
        if isinstance(result, dict):
            return int(result.get("data", result))
        return int(result)

    # -- HA groups --

    def list_ha_groups(self) -> list[dict]:
        """GET /cluster/ha/groups."""
        return self._s.call(self._s.proxmox.cluster.ha.groups.get)

    def create_ha_group(self, **params) -> object:
        """POST /cluster/ha/groups."""
        return self._s.call(self._s.proxmox.cluster.ha.groups.post, **params)

    def update_ha_group(self, group_id: str, **params) -> object:
        """PUT /cluster/ha/groups/{group_id}."""
        return self._s.call(
            self._s.proxmox.cluster.ha.groups(_q(group_id)).put, **params
        )

    def delete_ha_group(self, group_id: str) -> object:
        """DELETE /cluster/ha/groups/{group_id}."""
        return self._s.call(self._s.proxmox.cluster.ha.groups(_q(group_id)).delete)

    # -- HA resources --

    def list_ha_resources(self) -> list[dict]:
        """GET /cluster/ha/resources."""
        return self._s.call(self._s.proxmox.cluster.ha.resources.get)

    def add_ha_resource(self, **params) -> object:
        """POST /cluster/ha/resources."""
        return self._s.call(self._s.proxmox.cluster.ha.resources.post, **params)

    def delete_ha_resource(self, sid: str) -> object:
        """DELETE /cluster/ha/resources/{sid}."""
        return self._s.call(self._s.proxmox.cluster.ha.resources(_q(sid)).delete)

    # -- Backup / jobs --

    def list_backup_jobs(self) -> list[dict]:
        """GET /cluster/backup — backup jobs (PVE7 and PVE8 fallback)."""
        return self._s.call(self._s.proxmox.cluster.backup.get)

    def list_jobs(self) -> list[dict]:
        """GET /cluster/jobs — all scheduled jobs (PVE8+)."""
        return self._s.call(self._s.proxmox.cluster.jobs.get)

    def list_all_jobs(self, pve_major: int = 7) -> list[dict]:
        """List vzdump jobs, trying /cluster/jobs first on PVE8+."""
        if pve_major >= 8:
            try:
                data = self.list_jobs()
                if isinstance(data, dict):
                    data = data.get("data", data)
                if isinstance(data, list):
                    return [j for j in data if j.get("type", "vzdump") == "vzdump"]
            except Exception:
                pass
        data = self.list_backup_jobs()
        if isinstance(data, dict):
            data = data.get("data", data)
        return data if isinstance(data, list) else []

    def create_backup_job(self, params: dict, pve_major: int = 7) -> object:
        """POST /cluster/backup or /cluster/jobs (PVE8+)."""
        if pve_major >= 8:
            try:
                p = dict(params)
                p["type"] = "vzdump"
                return self._s.call(self._s.proxmox.cluster.jobs.post, **p)
            except Exception:
                pass
        return self._s.call(self._s.proxmox.cluster.backup.post, **params)

    def update_backup_job(self, job_id: str, params: dict, pve_major: int = 7) -> object:
        """PUT /cluster/backup/{id} or /cluster/jobs/{id} (PVE8+)."""
        p = {k: v for k, v in params.items() if k != "id"}
        if pve_major >= 8:
            try:
                pj = dict(p)
                pj["type"] = "vzdump"
                return self._s.call(
                    self._s.proxmox.cluster.jobs(_q(job_id)).put, **pj
                )
            except Exception:
                pass
        return self._s.call(self._s.proxmox.cluster.backup(_q(job_id)).put, **p)

    def delete_backup_job(self, job_id: str, pve_major: int = 7) -> object:
        """DELETE /cluster/backup/{id} or /cluster/jobs/{id} (PVE8+)."""
        if pve_major >= 8:
            try:
                return self._s.call(self._s.proxmox.cluster.jobs(_q(job_id)).delete)
            except Exception:
                pass
        return self._s.call(self._s.proxmox.cluster.backup(_q(job_id)).delete)
