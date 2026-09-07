"""Domain model: BackupSnapshot (backup on PVE storage or PBS).

Represents one backup entry as returned by
``GET /nodes/{node}/storage/{storage}/content?content=backup``.
Covers both vzdump archives (dir/nfs/zfs/...) and Proxmox Backup Server
snapshots (storage type ``pbs``), whose volids look like
``<store>:backup/vm/100/2024-05-06T07:08:09Z``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

_PBS_VOLID_RE = re.compile(
    r"^(?P<store>[^:]+):backup/"
    r"(?P<group>vm|ct)/(?P<vmid>\d+)/"
    r"(?P<time>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)$"
)

_VZDUMP_VOLID_RE = re.compile(r"vzdump-(?P<subtype>qemu|lxc)-(?P<vmid>\d+)-")


def parse_pbs_volid(volid: str) -> dict | None:
    """Parse a PBS backup volid.

    Returns ``{"store", "group", "vmid", "vm_type", "time"}`` where
    ``vm_type`` is ``"qemu"`` for ``vm`` groups and ``"lxc"`` for ``ct``,
    ``time`` a UTC datetime — or None if the volid is not a PBS snapshot.
    """
    m = _PBS_VOLID_RE.match(volid or "")
    if not m:
        return None
    try:
        dt = datetime.fromisoformat(m.group("time").replace("Z", "+00:00"))
    except ValueError:
        return None
    return {
        "store": m.group("store"),
        "group": m.group("group"),
        "vmid": int(m.group("vmid")),
        "vm_type": "qemu" if m.group("group") == "vm" else "lxc",
        "time": dt,
    }


def verify_state(verification: dict | None) -> str:
    """Normalize a PVE ``verification`` field to 'ok'/'failed'/''."""
    if not isinstance(verification, dict):
        return ""
    state = str(verification.get("state", "") or "").lower()
    if state in ("ok", "failed", "none"):
        return state
    return ""


@dataclass(frozen=True)
class BackupSnapshot:
    """A single backup entry (vzdump archive or PBS snapshot)."""

    volid: str
    """Full volume ID, e.g. 'pbs1:backup/vm/100/2024-05-06T07:08:09Z'."""

    storage: str
    """Storage name the entry was fetched from."""

    vmid: int | None
    """Guest VMID, if known."""

    vm_type: str
    """'qemu' / 'lxc' when determinable, '' otherwise."""

    time: datetime | None
    """Backup creation time (UTC for PBS snapshots)."""

    owner: str
    """PBS backup owner, e.g. 'root@pam' ('' for vzdump)."""

    verify: str
    """PBS verification state: 'ok' / 'failed' / 'none' / ''."""

    notes: str
    """PBS snapshot notes ('' for vzdump)."""

    size_bytes: int
    encrypted: bool
    is_pbs: bool

    # -- Computed properties --
    @property
    def snapshot_name(self) -> str:
        """Short snapshot label, e.g. 'vm/100 · 2024-05-06 07:08'."""
        pbs = parse_pbs_volid(self.volid)
        if pbs:
            t = pbs["time"]
            return f"{pbs['group']}/{pbs['vmid']} · {t:%Y-%m-%d %H:%M}"
        return self.volid

    # -- Factory --
    @staticmethod
    def from_content_item(d: dict, storage: str = "") -> BackupSnapshot:
        """Build a BackupSnapshot from a raw PVE content API dict."""
        volid = d.get("volid", "") or ""
        pbs = parse_pbs_volid(volid)
        vzdump = _VZDUMP_VOLID_RE.search(volid)
        vmid = d.get("vmid")
        if vmid is None and pbs:
            vmid = pbs["vmid"]
        elif vmid is None and vzdump:
            vmid = int(vzdump.group("vmid"))
        time = None
        ctime = d.get("ctime")
        if pbs:
            time = pbs["time"]
        elif ctime:
            try:
                time = datetime.fromtimestamp(int(ctime), tz=timezone.utc)
            except (ValueError, TypeError, OSError):
                time = None
        vm_type = d.get("subtype") or ""
        if vm_type not in ("qemu", "lxc") and pbs:
            vm_type = pbs["vm_type"]
        elif vm_type not in ("qemu", "lxc") and vzdump:
            vm_type = vzdump.group("subtype")
        if vm_type not in ("qemu", "lxc"):
            vm_type = ""
        return BackupSnapshot(
            volid=volid,
            storage=storage,
            vmid=int(vmid) if vmid is not None else None,
            vm_type=vm_type,
            time=time,
            owner=d.get("owner", "") or "",
            verify=verify_state(d.get("verification")),
            notes=d.get("notes", "") or "",
            size_bytes=d.get("size", 0) or 0,
            encrypted=bool(d.get("encrypted")),
            is_pbs=pbs is not None,
        )
