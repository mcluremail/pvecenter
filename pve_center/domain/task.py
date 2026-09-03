"""Domain model: Task (PVE background task / job).

Represents an entry from ``/nodes/{node}/tasks``.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._dictcompat import DictCompat


@dataclass(frozen=True)
class Task(DictCompat):
    """A PVE background task (snapshot, backup, start/stop, etc.)."""

    _FIELD_MAP = {
        "upid": "upid",
        "node": "node",
        "type": "task_type",
        "status": "status",
        "starttime": "starttime",
        "endtime": "endtime",
        "user": "user",
        "vmid": "vmid",
        "display_name": "display_name",
        "vm_name": "vm_name",
    }

    upid: str
    """Full UPID string (unique task identifier)."""

    node: str
    """PVE node name where the task ran."""

    task_type: str
    """Task type code, e.g. 'qmstart', 'vzdump', 'snapshot'."""

    status: str
    """Task status: 'OK', 'RUNNING', or error string."""

    starttime: float
    """Unix timestamp (epoch seconds)."""

    endtime: float
    """Unix timestamp; 0/missing means still running."""

    user: str
    """User identity, e.g. 'root@pam'."""

    vmid: int | None
    """VM ID if applicable, None otherwise."""

    display_name: str | None = None
    """UI display name of the node (enriched by the app, not from PVE)."""

    vm_name: str | None = None
    """VM name resolved from vmid (enriched by the app, not from PVE)."""

    @property
    def is_running(self) -> bool:
        """Whether the task is still running."""
        return self.status == "RUNNING" or (not self.endtime and bool(self.starttime))

    @property
    def is_ok(self) -> bool:
        """Whether the task completed successfully."""
        return self.status == "OK"

    @property
    def duration_seconds(self) -> float:
        """Task duration in seconds (0 if still running)."""
        if not self.endtime or not self.starttime:
            return 0.0
        return self.endtime - self.starttime

    @staticmethod
    def from_pve(d: dict) -> Task:
        """Build a Task from a raw PVE API dict.

        The ``vmid`` field is parsed from ``vmid`` or ``id`` keys,
        falling back to parsing the UPID string (both the vmid slot and
        the ``--vmid`` entry in the args segment).
        ``display_name`` and ``vm_name`` are app-side enrichment fields
        and are read back from cache dicts.
        """
        vmid_raw = d.get("vmid") or d.get("id")
        vmid: int | None = None
        if vmid_raw is not None:
            try:
                vmid = int(vmid_raw)
            except (ValueError, TypeError):
                pass

        upid = d.get("upid", "") or ""
        if vmid is None and upid:
            parts = upid.split(":")
            if len(parts) > 6 and parts[6].isdigit():
                try:
                    vmid = int(parts[6])
                except (ValueError, IndexError):
                    pass
            elif len(parts) >= 9:
                info = ":".join(parts[8:])
                idx = info.find("--vmid ")
                if idx >= 0:
                    rest = info[idx + 7:].lstrip()
                    end = rest.find(" ")
                    num = rest[:end] if end >= 0 else rest
                    if num.isdigit():
                        try:
                            vmid = int(num)
                        except (ValueError, IndexError):
                            pass

        return Task(
            upid=upid,
            node=d.get("node", "") or "",
            task_type=d.get("type", "") or "",
            status=d.get("status", "") or "",
            starttime=float(d.get("starttime", 0) or 0),
            endtime=float(d.get("endtime", 0) or 0),
            user=d.get("user", "") or "",
            vmid=vmid,
            display_name=d.get("display_name"),
            vm_name=d.get("vm_name"),
        )
