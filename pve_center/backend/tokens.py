"""API token lifecycle: creation on PVE hosts and deletion."""

import logging

from PySide6.QtCore import QObject, QRunnable, Signal

from ..plugins import create_provider
from ..provider._session import _proxies
from ..ui.i18n import tr
from .core import PVE_PORT, _q, _sanitize_error, _suppress_ssl_warnings

logger = logging.getLogger(__name__)

def _pve_ticket_auth(host, user, password, verify=False, proxy=None):
    import requests as rq
    url = f"https://{host}:{PVE_PORT}/api2/json/access/ticket"
    resp = rq.post(url, data={"username": user, "password": password},
                   verify=verify, timeout=15, allow_redirects=False,
                   proxies=_proxies(proxy))
    resp.raise_for_status()
    data = resp.json().get("data", {})
    return {
        "ticket": data.get("ticket"),
        "csrf": data.get("CSRFPreventionToken"),
    }
def create_admin_token(host, user, password, trust_ssl=False, proxy=None):
    """Create an API token for the specified PVE user.
    The token is created on behalf of the user — PVE audit shows
    the real operator, and permissions match their roles.

    Args:
        host: PVE host address
        user: existing PVE user (root@pam, user@ipa, ...)
        password: user's password
        trust_ssl: if True, accept self-signed certs (verify=False).
                   If False (default), require valid SSL certificate.

    Returns:
        dict with token_name, token_value, user fields
        or dict with error field.
    """
    import secrets as sec
    import string as str_mod

    import requests as rq
    verify = not bool(trust_ssl)
    if trust_ssl:
        _suppress_ssl_warnings()

    try:
        sess = None
        ticket_data = _pve_ticket_auth(host, user, password, verify=verify,
                                       proxy=proxy)
        ticket = ticket_data["ticket"]
        csrf = ticket_data["csrf"]
        sess = rq.Session()
        sess.verify = verify
        if proxy:
            # Явный прокси: env-прокси не должен перебивать session-level.
            sess.trust_env = False
            sess.proxies.update(_proxies(proxy))
        sess.headers.update({
            "Cookie": f"PVEAuthCookie={ticket}",
            "CSRFPreventionToken": csrf,
        })

        token_id = "pvecenter-" + "".join(
            sec.choice(str_mod.ascii_lowercase + str_mod.digits) for _ in range(6)
        )
        r = None
        for method in ("post", "put"):
            r = getattr(sess, method)(
                f"https://{host}:{PVE_PORT}/api2/json/access/users/{_q(user)}/token/{_q(token_id)}",
                data={"comment": "PVE Center", "expire": 0, "privsep": 0},
                timeout=15,
            )
            logger.debug("token_create %s %s HTTP %s", method, token_id, r.status_code)
            if r.status_code < 400:
                break
        if r is None:
            return {"error": tr("Token creation error: no response")}
        if r.status_code >= 400:
            logger.error("token_create failed: HTTP %s", r.status_code)
            return {"error": tr("Token creation error: {}").format(r.status_code)}

        data = r.json()
        data = data.get("data", data)
        token_value = ""
        if isinstance(data, dict) and data.get("value"):
            token_value = data["value"]
        if not token_value:
            return {"error": tr("Empty token value in server response")}

        auth_header = f"PVEAPIToken={user}!{token_id}={token_value}"
        try:
            vr = rq.get(
                f"https://{host}:{PVE_PORT}/api2/json/cluster/resources",
                headers={"Authorization": auth_header},
                verify=verify, timeout=10, allow_redirects=False,
                proxies=_proxies(proxy),
            )
            if vr.status_code != 200:
                logger.warning("verify FAILED: HTTP %s", vr.status_code)
                return {"error": tr("Token created but not working: {}").format(vr.status_code)}
        except Exception as ve:
            logger.warning("verify exception: %s", ve)

        return {"token_name": token_id, "token_value": token_value, "user": user}

    except Exception as e:
        msg = str(e)
        if "authorization" in msg.lower() or "permission" in msg.lower() or "401" in msg:
            return {"error": tr("Invalid login or password")}
        if "connection" in msg.lower() or "timeout" in msg.lower() or "resolve" in msg.lower():
            return {"error": tr("Cannot connect to {}").format(host)}
        return {"error": tr("Token creation failed. Check host, user, and password.")}
    finally:
        if sess is not None:
            try:
                sess.close()
            except Exception:
                pass

# ----------------------------------------------------------------------
# FetchWorker (QRunnable)
# ----------------------------------------------------------------------
class TokenCreationSignals(QObject):
    token_ready = Signal(dict)
    token_error = Signal(str)
    finished = Signal()
class TokenCreationWorker(QRunnable):
    """Создаёт API-токен в фоновом потоке, не блокируя UI."""
    def __init__(self, host, user, password, trust_ssl=False, proxy=None):
        super().__init__()
        self.host = host
        self.user = user
        self.password = password
        self.trust_ssl = trust_ssl
        self.proxy = proxy
        self.signals = TokenCreationSignals()

    def run(self):
        try:
            result = create_admin_token(self.host, self.user, self.password,
                                        trust_ssl=self.trust_ssl,
                                        proxy=self.proxy)
            self.password = None
            if "error" in result:
                try:
                    self.signals.token_error.emit(result["error"])
                except RuntimeError:
                    pass
            else:
                try:
                    self.signals.token_ready.emit(result)
                except RuntimeError:
                    pass
        except Exception as e:
            self.password = None
            try:
                self.signals.token_error.emit(_sanitize_error(e))
            except RuntimeError:
                pass
        finally:
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass
def delete_host_token(host_cfg):
    """Удаляет API-токен с PVE-сервера.
       Возвращает True при успехе, False при ошибке."""
    provider = None
    try:
        provider = create_provider(host_cfg, timeout=10)
        access_api = provider.access
        access_api.delete_token(host_cfg["user"], host_cfg["token_name"])
        logger.info("Token %s for user %s deleted from %s",
                    host_cfg["token_name"], host_cfg["user"], host_cfg["host"])
        return True
    except Exception as e:
        logger.warning("Failed to delete token from %s: %s", host_cfg.get("host", "?"), e)
        return False
    finally:
        if provider:
            provider.close()
