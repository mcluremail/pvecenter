"""Common UI helpers: status text, formatting."""

from .i18n import tr

STATUS_RU = {
    "running": "running",
    "stopped": "stopped",
    "paused": "paused",
    "error": "error",
    "offline": "offline",
    "online": "online",
    "unknown": "unknown",
    "mounted": "mounted",
}


def status_text(s):
    """Return human-readable status for display.
    tr() translates the status label to the current language.
    """
    return tr(STATUS_RU.get(s, s))


def format_uptime(seconds):
    """Format uptime in seconds to compact form: '5d 3h 20m 10s'."""
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
