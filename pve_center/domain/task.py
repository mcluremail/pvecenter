"""Domain model: Task (PVE background task / job).

Represents an entry from ``/nodes/{node}/tasks``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    """A PVE background task (snapshot, backup, start/stop, etc.)."""

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
        falling back to parsing the UPID string.
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
            if len(parts) > 6:
                try:
                    vmid = int(parts[6])
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
        )
