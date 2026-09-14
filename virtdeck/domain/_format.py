"""Pure formatting helpers shared by domain models and UI.

No Qt/i18n dependencies — safe to use in any context.
"""

from __future__ import annotations


def format_uptime(seconds: int | float | None) -> str:
    """Format uptime in seconds to compact form: '5d 3h 20m 10s'.

    Returns empty string for zero/missing values.
    """
    if not seconds or seconds <= 0:
        return ""
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def safe_pct(used: int | float | None, total: int | float | None) -> int:
    """Calculate safe percentage (0-100) from used/total.

    Returns 0 for missing or zero total.
    """
    if not total or total <= 0:
        return 0
    pct = int((used / total) * 100)
    return max(0, min(100, pct))


def format_volsize(size_bytes: int | float | None) -> str:
    """Format a volume size in bytes to a human-readable string.

    Returns "0" for zero/missing values.
    Uses GiB for values < 1024 GiB, TiB otherwise.
    """
    if not size_bytes:
        return "0"
    gib = size_bytes / (1024**3)
    if gib >= 1024:
        return f"{gib / 1024:.1f} TiB"
    return f"{gib:.1f} GiB"
