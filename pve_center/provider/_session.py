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

# Явный прокси задаётся per-host: cfg["proxy"] (поле «Proxy» в диалоге
# добавления сервера). Пусто/отсутствует — стандартное поведение requests:
# env-прокси (HTTP(S)_PROXY, ALL_PROXY, no_proxy) учитываются, как в curl.
# Явный URL полностью замещает env: trust_env=False + session.proxies,
# иначе session-level proxies проигрывают env-прокси в requests.


def _suppress_ssl_warnings() -> None:
    global _WARN_SUPPRESSED
    if not _WARN_SUPPRESSED:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        _WARN_SUPPRESSED = True


def _proxy_url(cfg: dict) -> str | None:
    """Explicit per-host proxy URL from cfg["proxy"] (empty → None)."""
    url = str(cfg.get("proxy") or "").strip()
    return url or None


def _proxies(url: str | None) -> dict[str, str] | None:
    """requests proxies dict for an explicit proxy URL (None → env default)."""
    return {"http": url, "https": url} if url else None


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

    def __init__(self, cfg: dict, timeout: float = 15) -> None:
        self.cfg = cfg
        self.timeout = timeout
        self._proxmox: ProxmoxAPI | None = None
        self._closed = False

    @property
    def proxmox(self) -> ProxmoxAPI:
        if self._proxmox is None:
            proxy = _proxy_url(self.cfg)
            self._proxmox = ProxmoxAPI(
                self.cfg["host"],
                user=self.cfg["user"],
                token_name=self.cfg["token_name"],
                token_value=self.cfg["token_value"],
                verify_ssl=_verify_ssl(self.cfg),
                timeout=self.timeout,
                proxies=_proxies(proxy),
            )
            if proxy:
                # proxmoxer 2.3.0 для token-auth не применяет proxies-kwarg
                # к запросам — фиксируем явный прокси на сессии напрямую.
                sess = self._proxmox._store.get("session")
                if sess is not None:
                    sess.trust_env = False
                    sess.proxies.update(_proxies(proxy))
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
    def request_proxies(self) -> dict[str, str] | None:
        """Explicit proxies for raw requests calls (None → env default)."""
        return _proxies(_proxy_url(self.cfg))

    @property
    def base_url(self) -> str:
        return f"https://{self.cfg['host']}:{PVE_PORT}/api2/json"
