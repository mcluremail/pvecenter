"""Bulk VM action planning (B3).

Pure function: filters a multi-selection of VM tree keys into executable
targets, skipping templates, missing VMs, and hosts without config.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BulkTarget:
    """One VM ready for a bulk action."""

    host_name: str
    node: str
    vmid: int
    vm_type: str


@dataclass(frozen=True)
class BulkPlan:
    """Result of planning a bulk action over a selection."""

    targets: tuple[BulkTarget, ...] = ()
    skipped_templates: tuple[int, ...] = ()
    skipped_no_vm: tuple[int, ...] = ()
    skipped_no_config: tuple[int, ...] = ()

    @property
    def skipped_count(self) -> int:
        return (len(self.skipped_templates)
                + len(self.skipped_no_vm)
                + len(self.skipped_no_config))


def plan_bulk_action(vm_keys, vm_repo, cfg_names) -> BulkPlan:
    """Build a BulkPlan from selected VM keys.

    Args:
        vm_keys: iterable of ``(host_name, vmid, node)`` tuples (VM_KEY_ROLE).
        vm_repo: repository with ``get(host_name, vmid) -> Vm | None``.
        cfg_names: iterable of known config names (connected hosts).

    Returns:
        BulkPlan with executable targets and skip reasons, preserving order.
    """
    known_cfg = set(cfg_names)
    targets: list[BulkTarget] = []
    skipped_templates: list[int] = []
    skipped_no_vm: list[int] = []
    skipped_no_config: list[int] = []

    seen: set[tuple] = set()
    for key in vm_keys:
        if not isinstance(key, tuple) or len(key) != 3:
            continue
        host_name, vmid, node = key
        if (host_name, vmid) in seen:
            continue
        seen.add((host_name, vmid))

        if host_name not in known_cfg:
            skipped_no_config.append(vmid)
            continue
        vm = vm_repo.get(host_name, vmid) if vm_repo is not None else None
        if vm is None:
            skipped_no_vm.append(vmid)
            continue
        if vm.get("template"):
            skipped_templates.append(vmid)
            continue
        targets.append(BulkTarget(
            host_name=host_name,
            node=node,
            vmid=vmid,
            vm_type=vm.get("type", "qemu") or "qemu",
        ))

    return BulkPlan(
        targets=tuple(targets),
        skipped_templates=tuple(skipped_templates),
        skipped_no_vm=tuple(skipped_no_vm),
        skipped_no_config=tuple(skipped_no_config),
    )
