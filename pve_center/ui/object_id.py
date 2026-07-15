"""Typed object identifiers for PVE entities.

Every PVE entity in pve-center is uniquely identified by a typed ID.
This module provides frozen dataclass IDs with stable field ordering
and __hash__/__eq__ for use as dict keys.

Canonical identity rules:
  Host    — (host_name, node)            host_name = config name, node = PVE node name
  VM      — (host_name, vmid)            vmid is unique within a host/cluster config
  Storage — (host_name, node, storage)  storage = PVE storage ID

The field order is ALWAYS: host_name first, then PVE-specific fields.
This is the single source of truth — all code should use these IDs.

Lookup is handled by domain repositories (NodeRepository, VmRepository,
StorageRepository) — see pve_center/domain/repositories.py.
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
