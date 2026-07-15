"""ProxmoxSession — unified connection to PVE API.

Wraps proxmoxer.ProxmoxAPI with unified error handling, SSL management,
and connection lifecycle.  All provider API modules use this class instead
of creating raw ProxmoxAPI / requests.Session instances.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

import urllib3
from proxmoxer import ProxmoxAPI

from ._errors import ProxmoxError, from_exception

logger = logging.getLogger(__name__)

PVE_PORT = 8006

_WARN_SUPPRESSED = False


def _suppress_ssl_warnings() -> None:
    global _WARN_SUPPRESSED
    if not _WARN_SUPPRESSED:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        _WARN_SUPPRESSED = True


def _verify_ssl(cfg: dict) -> bool:
    """Return verify_ssl value for requests/proxmoxer.

    trust_ssl=False (default) → strict verification, verify_ssl=True.
    trust_ssl=True → accept any cert, verify_ssl=False.
    """
    trust = cfg.get("trust_ssl", False)
    if trust:
        _suppress_ssl_warnings()
    return not bool(trust)


def _q(value) -> str:
    """URL-encode a path segment for proxmoxer."""
    return quote(str(value), safe="")


class ProxmoxSession:
    """Wraps ProxmoxAPI with unified error handling and connection lifecycle."""

    def __init__(self, cfg: dict, timeout: int = 15) -> None:
        self.cfg = cfg
        self.timeout = timeout
        self._proxmox: ProxmoxAPI | None = None
        self._closed = False

    @property
    def proxmox(self) -> ProxmoxAPI:
        if self._proxmox is None:
            self._proxmox = ProxmoxAPI(
                self.cfg["host"],
                user=self.cfg["user"],
                token_name=self.cfg["token_name"],
                token_value=self.cfg["token_value"],
                verify_ssl=_verify_ssl(self.cfg),
                timeout=self.timeout,
            )
            sess = self._proxmox._store.get("session")
            if sess is not None:
                sess.max_redirects = 0
                sess.allow_redirects = False
        return self._proxmox

    def close(self) -> None:
        """Close underlying requests.Session to prevent connection pool leaks."""
        if self._closed:
            return
        self._closed = True
        if self._proxmox is not None:
            try:
                sess = self._proxmox._store.get("session")
                if sess is not None:
                    sess.close()
            except Exception:
                pass

    def __enter__(self) -> ProxmoxSession:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- convenience: call proxmoxer chain, convert exceptions --

    def call(self, func, *args, **kwargs):
        """Call a proxmoxer accessor with unified exception conversion."""
        try:
            return func(*args, **kwargs)
        except ProxmoxError:
            raise
        except Exception as exc:
            raise from_exception(exc) from exc

    @property
    def host(self) -> str:
        return self.cfg["host"]

    @property
    def auth_header(self) -> str:
        return (
            f"PVEAPIToken={self.cfg['user']}!{self.cfg['token_name']}"
            f"={self.cfg['token_value']}"
        )

    @property
    def verify(self) -> bool:
        return _verify_ssl(self.cfg)

    @property
    def base_url(self) -> str:
        return f"https://{self.cfg['host']}:{PVE_PORT}/api2/json"
