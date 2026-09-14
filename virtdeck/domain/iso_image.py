"""Domain model: IsoImage (ISO file on PVE storage)."""

from __future__ import annotations

from dataclasses import dataclass

from ._format import format_volsize


@dataclass(frozen=True)
class IsoImage:
    """An ISO image stored on a PVE storage."""

    volid: str
    """Volume ID, e.g. 'local:iso/ubuntu-22.04.iso'."""

    fmt: str
    """Format string, e.g. 'iso'."""

    size_bytes: int
    """File size in bytes."""

    # -- Computed properties --
    @property
    def size_str(self) -> str:
        """Human-readable size (GiB / TiB), or '0' for zero."""
        return format_volsize(self.size_bytes)

    # -- Factory --
    @staticmethod
    def from_pve(d: dict) -> IsoImage:
        """Build an IsoImage from a raw PVE content API dict."""
        return IsoImage(
            volid=d.get("volid", "") or "",
            fmt=d.get("format", "") or "",
            size_bytes=d.get("size", 0) or 0,
        )
