"""Typed exception hierarchy for Proxmox API errors.

All exceptions raised by the provider layer are subclasses of ProxmoxError,
allowing callers to catch by category without inspecting message text.
"""

from __future__ import annotations

import re


class ProxmoxError(Exception):
    """Base for all Proxmox API errors."""

    code: str = "unknown"


class ProxmoxAuthError(ProxmoxError):
    """Authentication or authorization failure (401/403)."""

    code = "auth"


class ProxmoxNetworkError(ProxmoxError):
    """Network-level failure (connection refused, DNS, SSL handshake)."""

    code = "network"


class ProxmoxTimeoutError(ProxmoxError):
    """Request timed out."""

    code = "timeout"


class ProxmoxNotFoundError(ProxmoxError):
    """Resource not found (404)."""

    code = "not_found"


class ProxmoxPermissionError(ProxmoxError):
    """Insufficient permissions (403 with permission message)."""

    code = "permission"


class ProxmoxApiError(ProxmoxError):
    """Generic API error with HTTP status code."""

    code = "api"

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


_RE_401 = re.compile(r"\b401\b")
_RE_403 = re.compile(r"\b403\b")
_RE_404 = re.compile(r"\b404\b")
_RE_PERMISSION = re.compile(r"permission\s+check\s+failed", re.IGNORECASE)
_RE_TIMEOUT = re.compile(r"tim\s?e?o?u?t", re.IGNORECASE)
_RE_CONN = re.compile(
    r"connection|refused|unreachable|name resolution|dns|"
    r"ssl|certificate|handshake|eof.*protocol",
    re.IGNORECASE,
)


def from_exception(exc: Exception) -> ProxmoxError:
    """Classify a raw exception from requests/proxmoxer into a ProxmoxError subclass."""
    if isinstance(exc, ProxmoxError):
        return exc
    msg = str(exc)
    exc_name = type(exc).__name__

    if exc_name == "TimeoutError" or "Timeout" in exc_name or _RE_TIMEOUT.search(msg):
        return ProxmoxTimeoutError(msg)
    if _RE_PERMISSION.search(msg):
        return ProxmoxPermissionError(msg)
    if _RE_401.search(msg):
        return ProxmoxAuthError(msg)
    if _RE_404.search(msg):
        return ProxmoxNotFoundError(msg)
    if _RE_403.search(msg):
        return ProxmoxAuthError(msg)
    if _RE_CONN.search(msg):
        return ProxmoxNetworkError(msg)
    return ProxmoxApiError(msg)


def sanitize(exc: Exception) -> str:
    """Sanitize exception message for UI display — strip URLs, hostnames."""
    msg = str(exc)
    msg = re.sub(r"https?://[^\s'\"]+", "[url]", msg)
    msg = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+\b", "[host]", msg)
    if len(msg) > 150:
        msg = msg[:150] + "..."
    return msg
