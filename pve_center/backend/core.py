"""Shared helpers for backend workers: SSL handling, error sanitizing, task await."""

import os

import urllib3

PVE_PORT = 8006
_WARN_SUPPRESSED = False
def _suppress_ssl_warnings():
    global _WARN_SUPPRESSED
    if not _WARN_SUPPRESSED:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        _WARN_SUPPRESSED = True
def _verify_ssl(cfg):
    """Return verify_ssl value for requests/proxmoxer.
    trust_ssl=False (default) → strict verification, verify_ssl=True.
    trust_ssl=True → accept any cert, verify_ssl=False."""
    trust = cfg.get("trust_ssl", False)
    if trust:
        _suppress_ssl_warnings()
    return not bool(trust)
def _cleanup_vv(vv_path):
    if vv_path and os.path.exists(vv_path):
        try:
            os.unlink(vv_path)
        except OSError:
            pass
def _q(value):
    """URL-encode a path segment for proxmoxer."""
    from urllib.parse import quote
    return quote(str(value), safe="")
def _sanitize_error(exc):
    """Sanitize exception message for UI display — strip URLs, hostnames, credential fragments."""
    msg = str(exc)
    import re as _re
    # Strip URLs
    msg = _re.sub(r'https?://[^\s\'"]+', '[url]', msg)
    # Strip host:port patterns
    msg = _re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+\b', '[host]', msg)
    # Limit length
    if len(msg) > 150:
        msg = msg[:150] + "..."
    return msg

# ----------------------------------------------------------------------
# Create API token for PVE Center
# ----------------------------------------------------------------------
def _await_task(provider, node_name, result, timeout=120):
    """Wait for a PVE async task started by an API call.

    PVE returns a UPID for async operations and a data payload for
    synchronous ones. Returns (True, "") on success — task finished with
    exitstatus OK, or the call completed synchronously without a UPID —
    and (False, errmsg) on task failure or timeout.
    """
    upid = result.get("data", result) if isinstance(result, dict) else result
    if not (isinstance(upid, str) and upid.startswith("UPID:")):
        return True, ""
    status, exitstatus = provider.tasks.poll(
        node_name, upid, timeout=timeout, interval=1.0
    )
    if status == "stopped" and exitstatus == "OK":
        return True, ""
    return False, exitstatus or status

# ----------------------------------------------------------------------
# VmSnapshotCreateWorker
# ----------------------------------------------------------------------
def _safe_emit(signal, *args):
    try:
        signal.emit(*args)
    except RuntimeError:
        pass

# ----------------------------------------------------------------------
# StorageUploadWorker — POST /nodes/{node}/storage/{storage}/upload (multipart)
# ----------------------------------------------------------------------
