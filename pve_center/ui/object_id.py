"""Typed object identifiers and centralized lookup helpers.

Every PVE entity in pve-center is uniquely identified by a typed ID.
This module provides frozen dataclass IDs with stable field ordering,
__hash__/__eq__ for use as dict keys, and centralized lookup functions
that replace ad-hoc O(n) scans with O(1) dict access.

Canonical identity rules:
  Host  — (host_name, node)        host_name = config name, node = PVE node name
  VM    — (host_name, vmid)        vmid is unique within a host/cluster config
  Storage — (host_name, node, storage)  storage = PVE storage ID

The field order is ALWAYS: host_name first, then PVE-specific fields.
This is the single source of truth — all code should use these IDs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HostId:
    """Uniquely identifies a PVE host/node.

    host_name: pve-center config name (unique, e.g. 'hv01.bala.ltn.linru.grp')
    node:      PVE API node name (not unique across configs, e.g. 'hv01')
    """
    host_name: str
    node: str

    def __str__(self) -> str:
        return f"{self.host_name}/{self.node}"


@dataclass(frozen=True)
class VmId:
    """Uniquely identifies a VM or container.

    host_name: pve-center config name
    vmid:      PVE VM/CT ID (integer)
    """
    host_name: str
    vmid: int

    def __str__(self) -> str:
        return f"{self.host_name}/{self.vmid}"


@dataclass(frozen=True)
class StorageId:
    """Uniquely identifies a storage on a specific host/node.

    host_name: pve-center config name
    node:      PVE node name
    storage:   PVE storage ID
    """
    host_name: str
    node: str
    storage: str

    def __str__(self) -> str:
        return f"{self.host_name}/{self.node}/{self.storage}"


# ── Lookup helpers ──────────────────────────────────────────────


def find_node(all_nodes: list, all_nodes_by_pair: dict, host_name: str, node: str) -> dict | None:
    """O(1) node lookup by (host_name, node). Falls back to O(n) scan."""
    result = all_nodes_by_pair.get((host_name, node))
    if result is not None:
        return result
    for n in all_nodes:
        if n.get("host_name") == host_name and n.get("node") == node:
            return n
    return None


def find_vm(vms_by_key: dict, host_name: str, vmid: int) -> dict | None:
    """O(1) VM lookup by (host_name, vmid)."""
    return vms_by_key.get((host_name, vmid))


def find_storages_for_host(all_storages: list, host_name: str, node: str) -> list:
    """Return all storages belonging to a specific (host_name, node)."""
    return [s for s in all_storages
            if s.get("host_name") == host_name
            and s.get("node") == node]


def find_vms_for_host(all_vms: list, host_name: str, node: str) -> list:
    """Return all VMs belonging to a specific (host_name, node)."""
    return [v for v in all_vms
            if v.get("host_name") == host_name
            and v.get("node") == node]
