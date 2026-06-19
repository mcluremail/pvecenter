"""Common UI helpers: status text, formatting."""

import re

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


def build_cfg_index(nodes_cfg):
    """Build {name: cfg} dict from nodes_cfg list for O(1) lookup.
    On duplicate names (should not happen) last one wins."""
    return {c.get("name", ""): c for c in nodes_cfg}


def build_vm_index(all_vms):
    """Build {(host_name, vmid): vm} dict for O(1) lookup.
    On duplicate keys (should not happen) last one wins."""
    return {(v.get("host_name"), v.get("vmid")): v for v in all_vms}


def build_node_index(all_nodes):
    """Build {(host_name, node): node} and {host_name: node} dicts.
    Returns (by_pair, by_host) — by_host maps host_name to first matching node.
    """
    by_pair = {}
    by_host = {}
    for n in all_nodes:
        hn = n.get("host_name", "")
        nn = n.get("node", "")
        by_pair[(hn, nn)] = n
        if hn not in by_host:
            by_host[hn] = n
    return by_pair, by_host


def find_vm(all_vms, host_name, vmid, _cache=None):
    """Find VM by (host_name, vmid). Uses cache dict if provided.
    Callers should pass a pre-built cache via build_vm_index for O(1) lookup.
    """
    if _cache is not None:
        return _cache.get((host_name, vmid))
    return next((v for v in all_vms
                 if v.get("host_name") == host_name and v.get("vmid") == vmid), None)


def find_node_cfg(nodes_cfg, host_name, _cache=()):
    """Find node config by host name. Uses cache dict if provided.
    _cache is a {name: cfg} dict; if empty (default), falls back to linear scan.
    Callers should pass a pre-built cache via build_cfg_index for O(1) lookup.
    """
    if _cache:
        return _cache.get(host_name)
    return next((c for c in nodes_cfg if c.get("name") == host_name), None)


def parse_pve_error(err):
    """Translate a raw PVE API error string into a user-facing message.
    Returns the original string if no known pattern matches.
    """
    if not err:
        return ""
    err_lower = err.lower()
    if "permission check failed" in err_lower:
        m = re.search(r"Permission check failed\s*\(([^)]+)\)", err)
        if m:
            return tr("PVE permission denied: {path}").format(path=m.group(1))
        return tr("PVE permission denied")
    if "403" in err_lower:
        return tr("PVE permission denied (403)")
    if "unauthorized" in err_lower or "401" in err_lower:
        return tr("API token authorization error (401)")
    if "resolve" in err_lower or "dns" in err_lower or "name or service not known" in err_lower:
        return tr("Cannot resolve DNS name")
    if "connection refused" in err_lower or "connection reset" in err_lower:
        return tr("PVE API unavailable (connection refused)")
    if "timeout" in err_lower:
        return tr("Host not responding (timeout)")
    return err
