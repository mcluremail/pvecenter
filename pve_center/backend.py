import logging
import os
import threading

import requests
import urllib3
from proxmoxer import ProxmoxAPI
from PySide6.QtCore import QObject, QRunnable, Signal

from .provider import (
    AccessAPI,
    ClusterAPI,
    NodeAPI,
    PoolAPI,
    ProxmoxSession,
    StorageAPI,
    TaskAPI,
    VmAPI,
)
from .ui.i18n import tr
from .ui.vm_actions import VM_ACTION_MESSAGE_LABELS

logger = logging.getLogger(__name__)

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


def _close_proxmox(proxmox):
    """Close underlying requests.Session to prevent connection pool leaks."""
    try:
        sess = proxmox._store.get("session")
        if sess is not None:
            sess.close()
    except Exception:
        pass


def _cleanup_vv(vv_path):
    if vv_path and os.path.exists(vv_path):
        try:
            os.unlink(vv_path)
        except OSError:
            pass


def _make_proxmox(cfg, timeout=15):
    """Create ProxmoxAPI with SSL verification and redirects disabled."""
    proxmox = ProxmoxAPI(
        cfg["host"],
        user=cfg["user"],
        token_name=cfg["token_name"],
        token_value=cfg["token_value"],
        verify_ssl=_verify_ssl(cfg),
        timeout=timeout,
    )
    sess = proxmox._store.get("session")
    if sess is not None:
        sess.max_redirects = 0
        sess.allow_redirects = False
    return proxmox


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


def _pve_ticket_auth(host, user, password, verify=False):
    import requests as rq
    url = f"https://{host}:{PVE_PORT}/api2/json/access/ticket"
    resp = rq.post(url, data={"username": user, "password": password},
                   verify=verify, timeout=15, allow_redirects=False)
    resp.raise_for_status()
    data = resp.json().get("data", {})
    return {
        "ticket": data.get("ticket"),
        "csrf": data.get("CSRFPreventionToken"),
    }


def create_admin_token(host, user, password, trust_ssl=False):
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
        ticket_data = _pve_ticket_auth(host, user, password, verify=verify)
        ticket = ticket_data["ticket"]
        csrf = ticket_data["csrf"]
        sess = rq.Session()
        sess.verify = verify
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
    def __init__(self, host, user, password, trust_ssl=False):
        super().__init__()
        self.host = host
        self.user = user
        self.password = password
        self.trust_ssl = trust_ssl
        self.signals = TokenCreationSignals()

    def run(self):
        try:
            result = create_admin_token(self.host, self.user, self.password,
                                        trust_ssl=self.trust_ssl)
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
class FetchSignals(QObject):
    result_ready = Signal(dict)
    finished = Signal()


class FetchWorker(QRunnable):
    """Загружает сводку по узлу через QThreadPool.
    Независимые API-запросы выполняются параллельно через threading.Thread."""
    def __init__(self, node_cfg):
        super().__init__()
        self.node_cfg = node_cfg
        self.signals = FetchSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.node_cfg, timeout=15)
            cluster_api = ClusterAPI(session)
            pool_api = PoolAPI(session)
            node_api = NodeAPI(session)
            vm_api = VmAPI(session)
            storage_api = StorageAPI(session)

            is_cluster_rep = self.node_cfg.get("cluster_rep", False)

        # -- Parallel phase 1: pools, HA groups, resources --
            vmid_to_pool = {}
            pool_names = []
            ha_groups = []
            nodes = []
            vms = []
            storages = []
            cluster_name = ""
            node_name = ""

            pool_lock = threading.Lock()
            ha_lock = threading.Lock()
            res_lock = threading.Lock()

            def fetch_pools():
                nonlocal vmid_to_pool, pool_names
                try:
                    pools_data = pool_api.list()
                    with pool_lock:
                        pool_names = [p.get("poolid") or p.get("pool") for p in pools_data
                                      if p.get("poolid") or p.get("pool")]

                    def fetch_pool_detail(p):
                        pname = p.get("poolid") or p.get("pool")
                        if not pname:
                            return
                        try:
                            pd = pool_api.get(pname)
                            members = pd.get("members") if isinstance(pd, dict) else None
                        except Exception:
                            members = p.get("members")
                        if not isinstance(members, list):
                            return
                        local = {}
                        for m in members:
                            mt = m.get("type")
                            mv = m.get("vmid")
                            if mt in ("qemu", "lxc") and mv is not None:
                                local[int(mv)] = pname
                        with pool_lock:
                            vmid_to_pool.update(local)
                    pool_candidates = [p for p in pools_data if p.get("poolid") or p.get("pool")]
                    pool_threads = [threading.Thread(target=fetch_pool_detail, args=(p,), daemon=True)
                                    for p in pool_candidates]
                    for t in pool_threads:
                        t.start()
                    for t in pool_threads:
                        t.join(timeout=10)
                except Exception as e:
                    logger.debug("backend error: %s", e)

            def fetch_ha():
                nonlocal ha_groups
                try:
                    result = []
                    for g in cluster_api.list_ha_groups():
                        result.append({
                            "group": g.get("group", ""),
                            "nodes": g.get("nodes", ""),
                            "restricted": g.get("restricted", 0),
                            "nofailback": g.get("nofailback", 0),
                            "comment": g.get("comment", ""),
                            "digest": g.get("digest", ""),
                        })
                    result.sort(key=lambda x: x["group"])
                    with ha_lock:
                        ha_groups = result
                except Exception:
                    pass

            def fetch_resources():
                nonlocal nodes, vms, storages, cluster_name
                try:
                    resources = cluster_api.list_resources()
                    with res_lock:
                        nodes = [r for r in resources if r.get("type") == "node"]
                        vms = [r for r in resources if r.get("type") in ("qemu", "lxc")]
                        storages = [r for r in resources if r.get("type") == "storage"]
                        cluster_name = self.node_cfg.get("cluster", "")
                        for n in nodes:
                            short = n["node"]
                            n["_display_name"] = f"{short}@{cluster_name}" if cluster_name else short
                except Exception as e:
                    logger.debug("backend error: %s", e)

            phase1 = []
            phase1.append(threading.Thread(target=fetch_pools, daemon=True))
            phase1.append(threading.Thread(target=fetch_ha, daemon=True))
            if is_cluster_rep:
                phase1.append(threading.Thread(target=fetch_resources, daemon=True))

            for t in phase1:
                t.start()
            for t in phase1:
                t.join(timeout=20)

            # -- Parallel phase 2: storage details per node / standalone data --
            iso_images = {}
            iso_lock = threading.Lock()

            if is_cluster_rep:
                for n in nodes:
                    n["host_name"] = self.node_cfg["name"]
                for s in storages:
                    s["host_name"] = self.node_cfg["name"]
                    s["cluster"] = cluster_name

                # Подтягиваем used/total с каждой ноды параллельно
                detail_lock = threading.Lock()
                detail_by_node = {}

                def fetch_node_storage(n):
                    node_name = n["node"]
                    try:
                        node_storages = node_api.list_storage(node_name)
                        with detail_lock:
                            detail_by_node[node_name] = {
                                ds["storage"]: ds for ds in node_storages
                            }
                    except Exception:
                        with detail_lock:
                            detail_by_node[node_name] = {}

                storage_threads = [threading.Thread(target=fetch_node_storage, args=(n,), daemon=True)
                                   for n in nodes]
                for t in storage_threads:
                    t.start()
                for t in storage_threads:
                    t.join(timeout=20)

                # Подтягиваем версии с каждой ноды параллельно
                version_lock = threading.Lock()

                def fetch_node_version(n):
                    node_name = n["node"]
                    try:
                        ver = node_api.get_version(node_name)
                        with version_lock:
                            qemu = ver.get("qemu")
                            if qemu:
                                n["qemu"] = qemu
                            lxc = ver.get("lxc")
                            if lxc:
                                n["lxctype"] = lxc
                    except Exception:
                        pass
                    # pveversion и kernel из статуса ноды
                    try:
                        st = node_api.get_status(node_name)
                        with version_lock:
                            pve = st.get("pveversion")
                            if pve:
                                n["pveversion"] = pve
                            n["kernel"] = st.get("kversion", "")
                    except Exception:
                        pass

                ver_threads = [threading.Thread(target=fetch_node_version, args=(n,), daemon=True)
                              for n in nodes]
                for t in ver_threads:
                    t.start()
                for t in ver_threads:
                    t.join(timeout=10)

                for s in storages:
                    detail = detail_by_node.get(s.get("node", ""), {}).get(s.get("storage", ""), {})
                    if detail.get("used") is not None and (s.get("used") or 0) == 0:
                        s["used"] = detail["used"]
                    if detail.get("total") is not None and (s.get("total") or 0) == 0:
                        s["total"] = detail["total"]
                    if detail.get("avail") is not None and (s.get("avail") or 0) == 0:
                        s["avail"] = detail["avail"]
                for vm in vms:
                    if not vm.get("pool"):
                        vm["pool"] = vmid_to_pool.get(vm["vmid"])
            else:
                # Standalone: получаем имя ноды и данные параллельно
                def fetch_standalone():
                    nonlocal node_name, nodes, vms, storages
                    try:
                        local_nodes = node_api.list()
                        nn = local_nodes[0].get("node") if local_nodes else self.node_cfg["name"]
                    except Exception:
                        nn = self.node_cfg["name"]
                    node_name = nn
                    try:
                        node_status = node_api.get_status(node_name)
                    except Exception:
                        return
                    with res_lock:
                        nodes = [{**node_status, "node": node_name,
                                  "_display_name": self.node_cfg["name"],
                                  "host_name": self.node_cfg["name"],
                                  "status": "online"}]
                    try:
                        qemu_list = vm_api.list_qemu(node_name)
                        lxc_list = vm_api.list_lxc(node_name)
                        vms_local = []
                        for v in qemu_list:
                            vms_local.append({**v, "type": "qemu",
                                              "node": node_name,
                                              "host_name": self.node_cfg["name"],
                                              "pool": vmid_to_pool.get(v.get("vmid"))})
                        for v in lxc_list:
                            vms_local.append({**v, "type": "lxc",
                                              "node": node_name,
                                              "host_name": self.node_cfg["name"],
                                              "pool": vmid_to_pool.get(v.get("vmid"))})
                        storages_local = list(node_api.list_storage(node_name))
                        for st in storages_local:
                            st["node"] = node_name
                            st["host_name"] = self.node_cfg["name"]
                            st["cluster"] = ""
                        with res_lock:
                            vms = vms_local
                            storages = storages_local
                    except Exception as e:
                        logger.debug("backend error: %s", e)

                standalone_thread = threading.Thread(target=fetch_standalone, daemon=True)
                standalone_thread.start()
                standalone_thread.join(timeout=30)

                # Повторно применяем pool после завершения pool-потоков
                # (fetch_pools может ещё работать, когда fetch_standalone уже забрал vms)
                for vm in vms:
                    if not vm.get("pool"):
                        vm["pool"] = vmid_to_pool.get(vm.get("vmid"))

                # Версии для standalone ноды (pveversion/kernel уже в node_status)
                if nodes:
                    try:
                        ver = node_api.get_version(node_name)
                        qemu = ver.get("qemu")
                        if qemu:
                            for n in nodes:
                                n["qemu"] = qemu
                        lxc = ver.get("lxc")
                        if lxc:
                            for n in nodes:
                                n["lxctype"] = lxc
                    except Exception:
                        pass

            # -- Parallel phase 3: ISO images --
            def fetch_iso_for_node(n):
                nname = n["node"]
                nhost = n.get("host_name", "")
                iso_storages = [
                    s["storage"] for s in storages
                    if s.get("node") == nname
                    and s.get("host_name") == nhost
                    and "iso" in (s.get("content", "") or "").split(",")
                ]
                if not iso_storages:
                    with iso_lock:
                        iso_images[nhost] = []
                    return
                try:
                    seen = {}
                    for sname in iso_storages:
                        for item in storage_api.list_content(nname, sname, content="iso"):
                            if item.get("content") == "iso":
                                volid = item["volid"]
                                if volid not in seen:
                                    seen[volid] = {
                                        "volid": volid,
                                        "format": item.get("format", ""),
                                        "size": item.get("size", 0),
                                    }
                    with iso_lock:
                        iso_images[nhost] = sorted(seen.values(), key=lambda x: x["volid"])
                except Exception:
                    with iso_lock:
                        iso_images[nhost] = []

            iso_threads = [threading.Thread(target=fetch_iso_for_node, args=(n,), daemon=True)
                           for n in nodes]
            for t in iso_threads:
                t.start()
            for t in iso_threads:
                t.join(timeout=15)

            # -- Emit result --
            self.signals.result_ready.emit({
                "host": self.node_cfg["name"],
                "status": "ok",
                "nodes": nodes,
                "vms": vms,
                "storages": storages,
                "pool_names": pool_names,
                "iso_images": iso_images,
                "ha_groups": ha_groups
            })
        except Exception as e:
            try:
                self.signals.result_ready.emit({
                    "host": self.node_cfg["name"],
                    "status": "error",
                    "error": str(e)
                })
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# VmDetailWorker (остаётся без изменений)
# ----------------------------------------------------------------------
class VmDetailSignals(QObject):
    detail_ready = Signal(dict)
    finished = Signal()


class VmDetailWorker(QRunnable):
    def __init__(self, host_cfg, node_name, vmid, vm_type):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.signals = VmDetailSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=10)
            vm_api = VmAPI(session)
            status = vm_api.get_status(self.node_name, self.vmid, self.vm_type)
            try:
                self.signals.detail_ready.emit({
                    "vmid": self.vmid,
                    "status": "ok",
                    "data": status
                })
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error: %s", e)
            try:
                self.signals.detail_ready.emit({
                    "vmid": self.vmid,
                    "status": "error",
                    "error": str(e)
                })
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# VmConfigWorker
# ----------------------------------------------------------------------
class VmConfigSignals(QObject):
    config_ready = Signal(int, dict)
    config_error = Signal(int, str)
    finished = Signal()


class VmConfigWorker(QRunnable):
    def __init__(self, host_cfg, node_name, vmid, vm_type='qemu'):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.signals = VmConfigSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=10)
            vm_api = VmAPI(session)
            config = vm_api.get_config(self.node_name, self.vmid, self.vm_type)
            try:
                self.signals.config_ready.emit(self.vmid, config)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error: %s", e)
            try:
                self.signals.config_error.emit(self.vmid, str(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# VmConfigUpdateWorker — PUT /nodes/{node}/qemu/{vmid}/config
# ----------------------------------------------------------------------
class VmConfigUpdateSignals(QObject):
    config_updated = Signal(int, object)
    config_update_error = Signal(int, str)
    finished = Signal()


class VmConfigUpdateWorker(QRunnable):
    """Обновляет параметры VM через PUT /nodes/{node}/qemu/{vmid}/config."""
    def __init__(self, host_cfg, node_name, vmid, params, vm_type='qemu'):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.params = params
        self.vm_type = vm_type
        self.signals = VmConfigUpdateSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=10)
            vm_api = VmAPI(session)
            result = vm_api.update_config(self.node_name, self.vmid, self.vm_type, **self.params)
            try:
                self.signals.config_updated.emit(self.vmid, result)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error: %s", e)
            try:
                self.signals.config_update_error.emit(self.vmid, str(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# VmDiskResizeWorker — PUT /nodes/{node}/qemu/{vmid}/resize
# ----------------------------------------------------------------------
class VmDiskResizeSignals(QObject):
    disk_resized = Signal(int, str)   # vmid, upid
    disk_resize_error = Signal(int, str)
    finished = Signal()


class VmDiskResizeWorker(QRunnable):
    """Resize a VM disk via PUT /nodes/{node}/qemu/{vmid}/resize."""
    def __init__(self, host_cfg, node_name, vmid, disk, size, vm_type="qemu"):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.disk = disk        # e.g. "scsi0", "virtio0"
        self.size = size        # e.g. "+10G" or "20G"
        self.vm_type = vm_type
        self.signals = VmDiskResizeSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=30)
            vm_api = VmAPI(session)
            result = vm_api.resize_disk(self.node_name, self.vmid, self.vm_type,
                                        self.disk, self.size)
            try:
                self.signals.disk_resized.emit(self.vmid, str(result))
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error: %s", e)
            try:
                self.signals.disk_resize_error.emit(self.vmid, _sanitize_error(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# VmDiskMoveWorker — POST /nodes/{node}/qemu/{vmid}/move_disk
# ----------------------------------------------------------------------
class VmDiskMoveSignals(QObject):
    disk_moved = Signal(int, str)   # vmid, upid
    disk_move_error = Signal(int, str)
    finished = Signal()


class VmDiskMoveWorker(QRunnable):
    """Move a VM disk to another storage via POST /nodes/{node}/qemu/{vmid}/move_disk."""
    def __init__(self, host_cfg, node_name, vmid, disk, storage,
                 delete=False, vm_type="qemu"):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.disk = disk            # e.g. "scsi0"
        self.storage = storage      # target storage name
        self.delete = delete        # delete source after move
        self.vm_type = vm_type
        self.signals = VmDiskMoveSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=60)
            vm_api = VmAPI(session)
            result = vm_api.move_disk(self.node_name, self.vmid, self.vm_type,
                                      self.disk, self.storage, delete=self.delete)
            try:
                self.signals.disk_moved.emit(self.vmid, str(result))
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error: %s", e)
            try:
                self.signals.disk_move_error.emit(self.vmid, _sanitize_error(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# VmTaskHistoryWorker
# ----------------------------------------------------------------------
class VmTaskHistorySignals(QObject):
    tasks_ready = Signal(int, list)   # vmid, список задач
    tasks_error = Signal(int, str)
    finished = Signal()


class VmTaskHistoryWorker(QRunnable):
    """Загружает историю задач для конкретной ВМ."""
    def __init__(self, host_cfg, node_name, vmid, limit=50):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.limit = limit
        self.signals = VmTaskHistorySignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=10)
            task_api = TaskAPI(session)
            tasks = task_api.list_for_vm(self.node_name, self.vmid, limit=self.limit)
            try:
                self.signals.tasks_ready.emit(self.vmid, tasks)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error: %s", e)
            try:
                self.signals.tasks_error.emit(self.vmid, str(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# VmSnapshotsWorker
# ----------------------------------------------------------------------
class VmSnapshotsSignals(QObject):
    snapshots_ready = Signal(int, list)   # vmid, список снапшотов
    snapshots_error = Signal(int, str)
    finished = Signal()


_DISK_KEYS = ("scsi", "ide", "sata", "virtio", "efidisk")


def _parse_disk_size(val_str):
    """Parse size from a PVE disk config string like 'local-lvm:vm-100-disk-0,size=32G'."""
    if not isinstance(val_str, str):
        return 0
    total = 0
    for part in val_str.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if key.strip() != "size":
            continue
        value = value.strip().upper()
        if not value:
            continue
        multiplier = 1
        if value.endswith("T"):
            multiplier = 1024 ** 4
            value = value[:-1]
        elif value.endswith("G"):
            multiplier = 1024 ** 3
            value = value[:-1]
        elif value.endswith("M"):
            multiplier = 1024 ** 2
            value = value[:-1]
        elif value.endswith("K"):
            multiplier = 1024
            value = value[:-1]
        try:
            total += float(value) * multiplier
        except ValueError:
            pass
    return int(total)


class VmSnapshotsWorker(QRunnable):
    """Загружает список снапшотов для конкретной ВМ (с доп. запросом размера)."""
    def __init__(self, host_cfg, node_name, vmid, vm_type="qemu"):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.signals = VmSnapshotsSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=10)
            vm_api = VmAPI(session)
            snaps = vm_api.list_snapshots(self.node_name, self.vmid, self.vm_type)
            filtered = [dict(s) for s in snaps if s.get("name") != "current"]
            for snap in filtered:
                name = snap.get("name", "")
                if not name:
                    continue
                try:
                    cfg = vm_api.get_snapshot_config(
                        self.node_name, self.vmid, self.vm_type, name
                    )
                    total_bytes = 0
                    for key, val in cfg.items():
                        if not isinstance(val, str):
                            continue
                        if key[0].isdigit() or key.startswith(
                            ("scsi", "ide", "sata", "virtio", "efidisk")
                        ):
                            total_bytes += _parse_disk_size(val)
                    snap["size"] = total_bytes
                except Exception:
                    snap["size"] = 0
            filtered.sort(key=lambda s: (s.get("snaptime", 0) or 0))
            try:
                self.signals.snapshots_ready.emit(self.vmid, filtered)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("VmSnapshotsWorker error for vmid %s: %s", self.vmid, e)
            try:
                self.signals.snapshots_error.emit(self.vmid, str(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# Удаление токена с сервера
# ----------------------------------------------------------------------
def delete_host_token(host_cfg):
    """Удаляет API-токен с PVE-сервера.
       Возвращает True при успехе, False при ошибке."""
    session = None
    try:
        session = ProxmoxSession(host_cfg, timeout=10)
        access_api = AccessAPI(session)
        access_api.delete_token(host_cfg["user"], host_cfg["token_name"])
        logger.info("Token %s for user %s deleted from %s",
                    host_cfg["token_name"], host_cfg["user"], host_cfg["host"])
        return True
    except Exception as e:
        logger.warning("Failed to delete token from %s: %s", host_cfg.get("host", "?"), e)
        return False
    finally:
        if session:
            session.close()


class VmActionSignals(QObject):
    action_result = Signal(str)
    action_error = Signal(str)
    finished = Signal()


class VmActionWorker(QRunnable):
    ACTION_NAMES = VM_ACTION_MESSAGE_LABELS

    def __init__(self, host_cfg, node_name, vmid, vm_type, action):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.action = action
        self.signals = VmActionSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=10)
            vm_api = VmAPI(session)
            vm_api.perform_action(self.node_name, self.vmid, self.vm_type, self.action)
            try:
                action_name = self.ACTION_NAMES.get(self.action, self.action)
                self.signals.action_result.emit(
                    tr("VM {vmid}: {action} completed").format(vmid=self.vmid, action=action_name)
                )
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error: %s", e)
            try:
                self.signals.action_error.emit(_sanitize_error(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


def _poll_task(session, node_name, upid, timeout=60, interval=1.0):
    """Poll PVE async task until it finishes or timeout.
    Returns (status, exitstatus) tuple: ('stopped', 'OK') on success.
    """
    task_api = TaskAPI(session)
    return task_api.poll(node_name, upid, timeout=timeout, interval=interval)


# ----------------------------------------------------------------------
# VmSnapshotCreateWorker
# ----------------------------------------------------------------------
class VmSnapshotCreateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class VmSnapshotCreateWorker(QRunnable):
    def __init__(self, host_cfg, node_name, vmid, vm_type, snap_name, description="", vmstate=False):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.snap_name = snap_name
        self.description = description
        self.vmstate = vmstate
        self.signals = VmSnapshotCreateSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=10)
            vm_api = VmAPI(session)
            upid = vm_api.create_snapshot(
                self.node_name, self.vmid, self.vm_type,
                self.snap_name, self.description, self.vmstate,
            )
            if isinstance(upid, dict):
                upid = upid.get("data", upid)
            if isinstance(upid, str) and upid.startswith("UPID:"):
                status, exitstatus = _poll_task(session, self.node_name, upid, timeout=120)
                if status == "stopped" and exitstatus == "OK":
                    try:
                        self.signals.result.emit(
                            tr("Snapshot \"{name}\" created").format(name=self.snap_name)
                        )
                    except RuntimeError:
                        pass
                else:
                    err = exitstatus or status
                    try:
                        self.signals.error.emit(
                            tr("Snapshot create failed: {err}").format(err=err)
                        )
                    except RuntimeError:
                        pass
            else:
                try:
                    self.signals.result.emit(
                        tr("Snapshot \"{name}\" created").format(name=self.snap_name)
                    )
                except RuntimeError:
                    pass
        except Exception as e:
            logger.debug("backend error: %s", e)
            try:
                self.signals.error.emit(_sanitize_error(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# VmSnapshotDeleteWorker
# ----------------------------------------------------------------------
class VmSnapshotDeleteSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class VmSnapshotDeleteWorker(QRunnable):
    def __init__(self, host_cfg, node_name, vmid, vm_type, snap_name):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.snap_name = snap_name
        self.signals = VmSnapshotDeleteSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=10)
            vm_api = VmAPI(session)
            upid = vm_api.delete_snapshot(self.node_name, self.vmid, self.vm_type, self.snap_name)
            if isinstance(upid, dict):
                upid = upid.get("data", upid)
            if isinstance(upid, str) and upid.startswith("UPID:"):
                status, exitstatus = _poll_task(session, self.node_name, upid, timeout=120)
                if status == "stopped" and exitstatus == "OK":
                    try:
                        self.signals.result.emit(
                            tr("Snapshot \"{name}\" deleted").format(name=self.snap_name)
                        )
                    except RuntimeError:
                        pass
                else:
                    err = exitstatus or status
                    try:
                        self.signals.error.emit(
                            tr("Snapshot delete failed: {err}").format(err=err)
                        )
                    except RuntimeError:
                        pass
            else:
                try:
                    self.signals.result.emit(
                        tr("Snapshot \"{name}\" deleted").format(name=self.snap_name)
                    )
                except RuntimeError:
                    pass
        except Exception as e:
            logger.debug("backend error: %s", e)
            try:
                self.signals.error.emit(_sanitize_error(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# ClusterTasksWorker
# ----------------------------------------------------------------------
class ClusterTasksSignals(QObject):
    tasks_ready = Signal(list)
    tasks_error = Signal(str)
    finished = Signal()


class ClusterTasksWorker:  # not QRunnable — runs via threading.Thread
    """Loads tasks from all nodes in parallel via threading.
    Takes a list of (host_cfg, node_name) — for each node
    calls /nodes/{node}/tasks, merges results by UPID."""
    def __init__(self, node_requests):
        super().__init__()
        self.node_requests = node_requests  # list of (host_cfg, node_name)
        self.signals = ClusterTasksSignals()

    def run(self):
        try:
            results = {}
            errors = []
            lock = threading.Lock()

            def fetch_node(host_cfg, node_name):
                session = None
                try:
                    session = ProxmoxSession(host_cfg, timeout=10)
                    task_api = TaskAPI(session)
                    tasks = task_api.list(node_name, limit=100)
                    with lock:
                        results[node_name] = tasks
                except Exception as e:
                    with lock:
                        errors.append(f"{node_name}: {e}")
                finally:
                    if session:
                        session.close()

            threads = [threading.Thread(target=fetch_node, args=(hc, nn), daemon=True)
                       for hc, nn in self.node_requests]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=15)

            try:
                all_by_upid = {}
                for node_name, tasks in results.items():
                    for idx, t in enumerate(tasks):
                        upid = t.get("upid")
                        if upid:
                            all_by_upid[upid] = t
                        else:
                            all_by_upid[f"_no_upid_{node_name}_{idx}"] = t
                merged = sorted(all_by_upid.values(),
                                key=lambda x: float(x.get("starttime", 0) or 0),
                                reverse=True)
                if errors:
                    logger.warning("Task collection errors: %s", "; ".join(errors))
                try:
                    self.signals.tasks_ready.emit(merged)
                except RuntimeError:
                    pass
            except Exception as exc:
                logger.debug("ClusterTasksWorker merge error: %s", exc)
                try:
                    self.signals.tasks_error.emit(str(exc))
                except RuntimeError:
                    pass
        finally:
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# VmConsoleWorker (SPICE/VNC)
# ----------------------------------------------------------------------
class VmConsoleSignals(QObject):
    console_ready = Signal(str)
    console_error = Signal(str)
    finished = Signal()


class VmConsoleWorker(QRunnable):
    """Запрашивает SPICE/VNC proxy у PVE, пишет .vv файл и запускает remote-viewer.

    QEMU: сначала SPICE, при ошибке — fallback на VNC.
    LXC:  всегда VNC.
    """
    def __init__(self, host_cfg, node_name, vmid, vm_type="qemu"):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.signals = VmConsoleSignals()

    @staticmethod
    def _build_vv_lines(config, host_fallback):
        """Строит строки .vv файла для VNC-подключения."""
        lines = ["[virt-viewer]", "type=vnc"]
        port = config.get("port")
        if port:
            lines.append(f"port={port}")
        host_raw = config.get("host") or host_fallback
        if host_raw:
            lines.append(f"host={host_raw}")
        ticket = config.get("ticket")
        if ticket:
            lines.append(f"password={ticket}")
        delete_file = config.get("delete-this-file")
        if delete_file is not None:
            lines.append(f"delete-this-file={delete_file}")
        return lines

    @staticmethod
    def _build_spice_vv_lines(config):
        """Строит строки .vv файла для SPICE-подключения."""
        lines = ["[virt-viewer]"]
        host_raw = config.get("host", "")
        if host_raw:
            lines.append(f"host={host_raw}")
        for key in ("password", "proxy", "secure-attention",
                    "tls-port", "type", "delete-this-file",
                    "host-subject", "toggle-fullscreen", "release-cursor"):
            val = config.get(key)
            if val is not None:
                lines.append(f"{key}={val}")
        title = config.get("title")
        if title:
            lines.append(f"title={title}")
        ca = config.get("ca", "")
        if ca:
            lines.append("ca=" + ca.replace("\n", "\\n"))
        return lines

    def run(self):
        import os
        import subprocess
        import sys
        import tempfile
        vv_path = None
        session = None
        used_vnc = False
        try:
            try:
                session = ProxmoxSession(self.host_cfg, timeout=10)
                vm_api = VmAPI(session)
                if self.vm_type == "lxc":
                    config = vm_api.get_vnc_proxy(
                        self.node_name, self.vmid, "lxc", self.host_cfg["host"]
                    )
                    used_vnc = True
                else:
                    try:
                        config = vm_api.get_spice_proxy(
                            self.node_name, self.vmid, self.host_cfg["host"]
                        )
                    except Exception as spice_err:
                        spice_msg = str(spice_err).lower()
                        if "not supported" in spice_msg or "spice" in spice_msg:
                            config = vm_api.get_vnc_proxy(
                                self.node_name, self.vmid, "qemu", self.host_cfg["host"]
                            )
                            used_vnc = True
                        else:
                            raise
            except Exception as e:
                msg = str(e).lower()
                if "permission check failed" in msg or "403" in msg:
                    err = tr("PVE permission denied for console (requires VM.Console)")
                elif "not supported" in msg or "spice" in msg or "vnc" in msg:
                    err = tr("Console not supported for this VM")
                else:
                    err = tr("Console proxy error: {}").format(e)
                try:
                    self.signals.console_error.emit(err)
                except RuntimeError:
                    pass
                return
            finally:
                if session:
                    session.close()
                    session = None

            try:
                if used_vnc:
                    lines = self._build_vv_lines(config, self.host_cfg.get("host", ""))
                else:
                    lines = self._build_spice_vv_lines(config)

                fd, vv_path = tempfile.mkstemp(suffix=".vv", prefix="pve_")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
                try:
                    os.chmod(vv_path, 0o600)
                except OSError:
                    pass
                import atexit
                atexit.register(lambda p=vv_path: _cleanup_vv(p))
            except Exception as e:
                try:
                    self.signals.console_error.emit(tr("VV file write error: {}").format(e))
                except RuntimeError:
                    pass
                return

            try:
                if sys.platform == "win32":
                    pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
                    pf_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
                    if not os.path.isabs(pf) or not os.path.isdir(pf):
                        pf = r"C:\Program Files"
                    if not os.path.isabs(pf_x86) or not os.path.isdir(pf_x86):
                        pf_x86 = r"C:\Program Files (x86)"
                    candidates = [
                        os.path.join(pf, "VirtViewer", "bin", "remote-viewer.exe"),
                        os.path.join(pf_x86, "VirtViewer", "bin", "remote-viewer.exe"),
                        "remote-viewer.exe",
                    ]
                    rv_cmd = next((c for c in candidates if os.path.isfile(c)), candidates[-1])
                else:
                    rv_cmd = "remote-viewer"
                proc = subprocess.Popen(
                    [rv_cmd, vv_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
                )
                try:
                    _, stderr = proc.communicate(timeout=5)
                    if proc.returncode != 0:
                        err_text = stderr.decode("utf-8", errors="replace").strip()
                        logger.warning("remote-viewer exit code %d: %s", proc.returncode, err_text)
                        try:
                            self.signals.console_error.emit(
                                tr("remote-viewer: ") + (err_text or tr("code ") + str(proc.returncode))
                            )
                        except RuntimeError:
                            pass
                        if vv_path and os.path.exists(vv_path):
                            try:
                                os.unlink(vv_path)
                            except OSError:
                                pass
                        return
                except subprocess.TimeoutExpired:
                    logger.debug("remote-viewer started (pid=%d)", proc.pid)
                    def _cleanup():
                        try:
                            proc.wait(timeout=86400)
                        except Exception:
                            try:
                                proc.kill()
                            except Exception:
                                pass
                        _cleanup_vv(vv_path)
                    threading.Thread(target=_cleanup, daemon=True).start()
            except FileNotFoundError:
                try:
                    if sys.platform == "win32":
                        hint = tr("remote-viewer not found. Download virt-viewer from:\n  https://virt-manager.org/download/")
                    elif sys.platform == "darwin":
                        hint = tr("remote-viewer not found. Install virt-viewer:\n  brew install virt-viewer")
                    else:
                        hint = tr("remote-viewer not found. Install virt-viewer:\n  apt install virt-viewer")
                    self.signals.console_error.emit(hint)
                except RuntimeError:
                    pass
                if vv_path and os.path.exists(vv_path):
                    try:
                        os.unlink(vv_path)
                    except OSError:
                        pass
                return
            except OSError:
                if vv_path and os.path.exists(vv_path):
                    try:
                        os.unlink(vv_path)
                    except OSError:
                        pass
                try:
                    self.signals.console_error.emit(tr("Failed to launch remote-viewer"))
                except RuntimeError:
                    pass
                return

            try:
                if used_vnc:
                    self.signals.console_ready.emit(tr("VNC console launched"))
                else:
                    self.signals.console_ready.emit(tr("SPICE console launched"))
            except RuntimeError:
                pass
        finally:
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# CreateVmWorker — создание VM
# ----------------------------------------------------------------------
class CreateVmSignals(QObject):
    vm_created = Signal(str)  # success message
    vm_error = Signal(str)    # error message
    finished = Signal()


class CreateVmWorker(QRunnable):
    """Creates QEMU VM via POST /nodes/{node}/qemu."""
    def __init__(self, host_cfg, node_name, params, ha_group=None):
        """
        params: dict with VM parameters (name, cores, memory, sockets, ostype, etc.)
        ha_group: HA group name (optional)
        """
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.params = params
        self.ha_group = ha_group
        self.signals = CreateVmSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=30)
            cluster_api = ClusterAPI(session)
            vm_api = VmAPI(session)

            params = dict(self.params)
            # Request next free VMID if not specified
            if not params.get("vmid"):
                try:
                    params["vmid"] = cluster_api.next_vmid()
                except Exception:
                    try:
                        self.signals.vm_error.emit(
                            tr("Could not get next free VMID from cluster")
                        )
                    except RuntimeError:
                        pass
                    return

            vm_api.create_qemu(self.node_name, **params)
            vmid = params.get("vmid", "?")
            msg = tr("VM {vmid} created on {node}").format(vmid=vmid, node=self.node_name)

            # Add to HA group
            if self.ha_group:
                try:
                    ha_params = {
                        "sid": f"vm:{vmid}",
                        "group": self.ha_group,
                    }
                    if not self.params.get("start"):
                        ha_params["state"] = "stopped"
                    cluster_api.add_ha_resource(**ha_params)
                    msg += tr(", added to HA ") + self.ha_group
                except Exception as ha_err:
                    msg += tr(", but HA error: {}").format(ha_err)

            try:
                self.signals.vm_created.emit(msg)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error: %s", e)
            try:
                self.signals.vm_error.emit(_sanitize_error(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


class DeleteVmSignals(QObject):
    vm_deleted = Signal(str)  # success message
    vm_error = Signal(str)    # error message
    finished = Signal()


class DeleteVmWorker(QRunnable):
    """Удаляет QEMU VM или LXC контейнер через DELETE /nodes/{node}/{qemu|lxc}/{vmid}."""
    def __init__(self, host_cfg, node_name, vmid, vm_type="qemu"):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.signals = DeleteVmSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=30)
            vm_api = VmAPI(session)
            vm_api.delete(self.node_name, self.vmid, self.vm_type, purge=True)
            msg = tr("VM {vmid} deleted from {node}").format(vmid=self.vmid, node=self.node_name)
            try:
                self.signals.vm_deleted.emit(msg)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error: %s", e)
            try:
                self.signals.vm_error.emit(_sanitize_error(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# HaResourcesWorker — GET /cluster/ha/resources
# ----------------------------------------------------------------------
class HaResourcesSignals(QObject):
    ha_resources_ready = Signal(list)
    ha_resources_error = Signal(str)
    finished = Signal()


class HaResourcesWorker(QRunnable):
    def __init__(self, host_cfg):
        super().__init__()
        self.host_cfg = host_cfg
        self.signals = HaResourcesSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            cluster_api = ClusterAPI(session)
            data = cluster_api.list_ha_resources()
            _safe_emit(self.signals.ha_resources_ready, data)
        except Exception as e:
            logger.debug("HA resources error: %s", e)
            _safe_emit(self.signals.ha_resources_error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# HaResourceAddWorker — POST /cluster/ha/resources
# ----------------------------------------------------------------------
class HaResourceAddSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class HaResourceAddWorker(QRunnable):
    def __init__(self, host_cfg, sid, group, state="default",
                 max_restart=1, max_relocate=1, comment=""):
        super().__init__()
        self.host_cfg = host_cfg
        self.sid = sid
        self.group = group
        self.state = state
        self.max_restart = max_restart
        self.max_relocate = max_relocate
        self.comment = comment
        self.signals = HaResourceAddSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            cluster_api = ClusterAPI(session)
            params = {
                "sid": self.sid,
                "group": self.group,
            }
            if self.state and self.state != "default":
                params["state"] = self.state
            if self.max_restart is not None:
                params["max_restart"] = self.max_restart
            if self.max_relocate is not None:
                params["max_relocate"] = self.max_relocate
            if self.comment:
                params["comment"] = self.comment
            cluster_api.add_ha_resource(**params)
            _safe_emit(self.signals.result,
                       tr("{sid} added to HA group {group}").format(sid=self.sid, group=self.group))
        except Exception as e:
            logger.debug("HA resource add error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# HaResourceDeleteWorker — DELETE /cluster/ha/resources/{sid}
# ----------------------------------------------------------------------
class HaResourceDeleteSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class HaResourceDeleteWorker(QRunnable):
    def __init__(self, host_cfg, sid):
        super().__init__()
        self.host_cfg = host_cfg
        self.sid = sid
        self.signals = HaResourceDeleteSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            cluster_api = ClusterAPI(session)
            cluster_api.delete_ha_resource(self.sid)
            _safe_emit(self.signals.result,
                       tr("{sid} removed from HA").format(sid=self.sid))
        except Exception as e:
            logger.debug("HA resource delete error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# Network CRUD workers — /nodes/{node}/network
# ----------------------------------------------------------------------
class NetworkCrudSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class NetworkCreateWorker(QRunnable):
    """POST /nodes/{node}/network — create network interface."""
    def __init__(self, host_cfg, node_name, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.params = params
        self.signals = NetworkCrudSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            node_api = NodeAPI(session)
            node_api.create_network(self.node_name, **self.params)
            iface = self.params.get("iface", "")
            _safe_emit(self.signals.result,
                       tr("Network interface {iface} created").format(iface=iface))
        except Exception as e:
            logger.debug("network create error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class NetworkUpdateWorker(QRunnable):
    """PUT /nodes/{node}/network/{iface} — update network interface."""
    def __init__(self, host_cfg, node_name, iface, params, digest=None):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.iface = iface
        self.params = params
        self.digest = digest
        self.signals = NetworkCrudSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            node_api = NodeAPI(session)
            p = dict(self.params)
            if self.digest:
                p["digest"] = self.digest
            node_api.update_network(self.node_name, self.iface, **p)
            _safe_emit(self.signals.result,
                       tr("Network interface {iface} updated").format(iface=self.iface))
        except Exception as e:
            logger.debug("network update error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class NetworkDeleteWorker(QRunnable):
    """DELETE /nodes/{node}/network/{iface} — delete network interface."""
    def __init__(self, host_cfg, node_name, iface, digest=None):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.iface = iface
        self.digest = digest
        self.signals = NetworkCrudSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            node_api = NodeAPI(session)
            params = {}
            if self.digest:
                params["digest"] = self.digest
            node_api.delete_network(self.node_name, self.iface, **params)
            _safe_emit(self.signals.result,
                       tr("Network interface {iface} deleted").format(iface=self.iface))
        except Exception as e:
            logger.debug("network delete error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class NetworkApplyWorker(QRunnable):
    """PUT /nodes/{node}/network — apply pending network changes."""
    def __init__(self, host_cfg, node_name):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.signals = NetworkCrudSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=30)
            node_api = NodeAPI(session)
            node_api.apply_network(self.node_name)
            _safe_emit(self.signals.result, tr("Network changes applied"))
        except Exception as e:
            logger.debug("network apply error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class NetworkRevertWorker(QRunnable):
    """DELETE /nodes/{node}/network — revert pending network changes."""
    def __init__(self, host_cfg, node_name):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.signals = NetworkCrudSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            node_api = NodeAPI(session)
            node_api.revert_network(self.node_name)
            _safe_emit(self.signals.result, tr("Network changes reverted"))
        except Exception as e:
            logger.debug("network revert error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# ClusterStatusWorker — GET /cluster/status + GET /cluster/config/nodes
# ----------------------------------------------------------------------
class ClusterStatusSignals(QObject):
    cluster_status_ready = Signal(dict)
    cluster_status_error = Signal(str)
    finished = Signal()


class ClusterStatusWorker(QRunnable):
    """Fetches cluster quorum status and corosync node config."""
    def __init__(self, host_cfg, timeout=15):
        super().__init__()
        self.host_cfg = host_cfg
        self.timeout = timeout
        self.signals = ClusterStatusSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=self.timeout)
            cluster_api = ClusterAPI(session)
            status = cluster_api.get_status()
            corosync_nodes = []
            try:
                corosync_nodes = cluster_api.get_config_nodes()
            except Exception:
                pass
            result = {
                "status": status,
                "corosync_nodes": corosync_nodes,
            }
            _safe_emit(self.signals.cluster_status_ready, result)
        except Exception as e:
            logger.debug("cluster status error: %s", e)
            _safe_emit(self.signals.cluster_status_error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# MigrateVmWorker — migrate VM within cluster
# ----------------------------------------------------------------------
class MigrateVmSignals(QObject):
    vm_migrated = Signal(str)
    vm_error = Signal(str)
    finished = Signal()


class MigrateVmWorker(QRunnable):
    """Migrate QEMU VM or LXC container to another node in cluster.
    QEMU: POST /nodes/{node}/qemu/{vmid}/migrate {target: ...}
    LXC:  not supported by PVE API — emit error."""
    def __init__(self, host_cfg, node_name, vmid, vm_type, target_node,
                 with_local_disks=True):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.target_node = target_node
        self.with_local_disks = with_local_disks
        self.signals = MigrateVmSignals()

    def run(self):
        if self.vm_type == "lxc":
            try:
                self.signals.vm_error.emit(
                    tr("Live migration of containers (LXC) is not supported by PVE")
                )
            except RuntimeError:
                pass
            return
        try:
            session = None
            session = ProxmoxSession(self.host_cfg, timeout=120)
            vm_api = VmAPI(session)
            vm_api.migrate(self.node_name, self.vmid, self.target_node,
                           self.with_local_disks)
            msg = tr("VM {vmid} migration to {target} started").format(
                vmid=self.vmid, target=self.target_node)
            try:
                self.signals.vm_migrated.emit(msg)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("migrate error: %s", e)
            try:
                self.signals.vm_error.emit(_sanitize_error(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# CloneVmWorker — clone QEMU VM or LXC container
# ----------------------------------------------------------------------
class CloneVmSignals(QObject):
    vm_cloned = Signal(str)
    vm_error = Signal(str)
    finished = Signal()


class CloneVmWorker(QRunnable):
    """Clone QEMU VM or LXC container.
    QEMU: POST /nodes/{node}/qemu/{vmid}/clone {newid, name, target, full, storage}
    LXC:  POST /nodes/{node}/lxc/{vmid}/clone {newid, hostname, target, storage}"""
    def __init__(self, host_cfg, node_name, vmid, vm_type, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.params = params
        self.signals = CloneVmSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=120)
            cluster_api = ClusterAPI(session)
            vm_api = VmAPI(session)

            params = dict(self.params)
            if not params.get("newid"):
                params["newid"] = cluster_api.next_vmid()

            if self.vm_type == "lxc":
                clone_params = {
                    "newid": params["newid"],
                    "target": params.get("target", self.node_name),
                }
                if params.get("name"):
                    clone_params["hostname"] = params["name"]
                if params.get("storage"):
                    clone_params["storage"] = params["storage"]
                if params.get("full"):
                    clone_params["full"] = 1
            else:
                clone_params = {
                    "newid": params["newid"],
                    "target": params.get("target", self.node_name),
                }
                if params.get("name"):
                    clone_params["name"] = params["name"]
                if params.get("full"):
                    clone_params["full"] = 1
                if params.get("storage"):
                    clone_params["storage"] = params["storage"]
            vm_api.clone(self.node_name, self.vmid, self.vm_type, **clone_params)

            newid = params.get("newid", "?")
            msg = tr("VM {vmid} cloned to {newid} on {target}").format(
                vmid=self.vmid, newid=newid,
                target=params.get("target", self.node_name))
            try:
                self.signals.vm_cloned.emit(msg)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("clone error: %s", e)
            try:
                self.signals.vm_error.emit(_sanitize_error(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# ConvertToTemplateWorker — convert QEMU VM to template
# POST /nodes/{node}/qemu/{vmid}/template
# ----------------------------------------------------------------------
class ConvertToTemplateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class ConvertToTemplateWorker(QRunnable):
    """Convert a QEMU VM to a template.
    Only QEMU is supported (LXC has no template conversion in PVE API).
    The VM must be stopped before conversion."""
    def __init__(self, host_cfg, node_name, vmid):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.signals = ConvertToTemplateSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=30)
            vm_api = VmAPI(session)
            vm_api.convert_to_template(self.node_name, self.vmid)
            msg = tr("VM {vmid} converted to template").format(vmid=self.vmid)
            try:
                self.signals.result.emit(msg)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("convert-to-template error: %s", e)
            try:
                self.signals.error.emit(_sanitize_error(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# ConvertToVmWorker — convert template back to VM
# DELETE template flag via config update: POST /nodes/{node}/qemu/{vmid}/config {template: 0}
# ----------------------------------------------------------------------
class ConvertToVmSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class ConvertToVmWorker(QRunnable):
    """Convert a QEMU template back to a regular VM by clearing the template flag."""
    def __init__(self, host_cfg, node_name, vmid):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.signals = ConvertToVmSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=30)
            vm_api = VmAPI(session)
            vm_api.post_config(self.node_name, self.vmid, "qemu", template=0)
            msg = tr("Template {vmid} converted to VM").format(vmid=self.vmid)
            try:
                self.signals.result.emit(msg)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("convert-to-vm error: %s", e)
            try:
                self.signals.error.emit(_sanitize_error(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# StorageContentDeleteWorker — destroy disk image via DELETE /storage/{storage}/content/{volid}
# ----------------------------------------------------------------------
class StorageContentDeleteSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class StorageContentDeleteWorker(QRunnable):
    def __init__(self, host_cfg, node_name, storage, volid, timeout=120):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.storage = storage
        self.volid = volid
        self.timeout = timeout
        self.signals = StorageContentDeleteSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=10)
            storage_api = StorageAPI(session)
            upid = storage_api.delete_content(self.node_name, self.storage, self.volid)
            if isinstance(upid, dict):
                upid = upid.get("data", upid)
            if isinstance(upid, str) and upid.startswith("UPID:"):
                status, exitstatus = _poll_task(
                    session, self.node_name, upid, timeout=self.timeout
                )
                if status == "stopped" and exitstatus == "OK":
                    try:
                        self.signals.result.emit(
                            tr("File deleted: {volid}").format(volid=self.volid)
                        )
                    except RuntimeError:
                        pass
                else:
                    err = exitstatus or status
                    try:
                        self.signals.error.emit(
                            tr("Delete failed: {err}").format(err=err)
                        )
                    except RuntimeError:
                        pass
            else:
                try:
                    self.signals.result.emit(
                        tr("File deleted: {volid}").format(volid=self.volid)
                    )
                except RuntimeError:
                    pass
        except Exception as e:
            logger.debug("storage content delete error: %s", e)
            try:
                self.signals.error.emit(_sanitize_error(e))
            except RuntimeError:
                pass
        finally:
            if session:
                session.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


def _safe_emit(signal, *args):
    try:
        signal.emit(*args)
    except RuntimeError:
        pass


# ----------------------------------------------------------------------
# StorageUploadWorker — POST /nodes/{node}/storage/{storage}/upload (multipart)
# ----------------------------------------------------------------------
class StorageUploadSignals(QObject):
    progress = Signal(int)
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class StorageUploadWorker(QRunnable):
    def __init__(self, host_cfg, node_name, storage_name, content_type, file_path, timeout=300):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.storage_name = storage_name
        self.content_type = content_type
        self.file_path = file_path
        self.timeout = timeout
        self.signals = StorageUploadSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=10)
            storage_api = StorageAPI(session)
            file_name = os.path.basename(self.file_path)

            def progress_cb(pct: int) -> None:
                _safe_emit(self.signals.progress, pct)

            result = storage_api.upload_file(
                self.node_name, self.storage_name, self.content_type,
                self.file_path, timeout=self.timeout, progress_callback=progress_cb,
            )
            if isinstance(result, str) and result.startswith("UPID:"):
                status, exitstatus = _poll_task(
                    session, self.node_name, result, timeout=self.timeout
                )
                if status == "stopped" and exitstatus == "OK":
                    _safe_emit(
                        self.signals.result,
                        tr("Upload complete: {name}").format(name=file_name),
                    )
                else:
                    err = exitstatus or status
                    _safe_emit(
                        self.signals.error,
                        tr("Upload failed: {err}").format(err=err),
                    )
            else:
                _safe_emit(
                    self.signals.result,
                    tr("Upload complete: {name}").format(name=file_name),
                )
        except Exception as e:
            logger.debug("upload error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# StorageDownloadUrlWorker — POST /nodes/{node}/storage/{storage}/download-url
# ----------------------------------------------------------------------
class StorageDownloadUrlSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class StorageDownloadUrlWorker(QRunnable):
    """Скачивает файл с URL на storage через PVE API.

    POST /nodes/{node}/storage/{storage}/download-url
    Параметры: url, content (iso/vztmpl), filename (optional), checksum (optional),
    verify-certificates (optional, default 1).
    """
    def __init__(self, host_cfg, node_name, storage_name, content_type, url,
                 filename=None, checksum=None, verify_certificates=True, timeout=600):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.storage_name = storage_name
        self.content_type = content_type
        self.url = url
        self.filename = filename
        self.checksum = checksum
        self.verify_certificates = verify_certificates
        self.timeout = timeout
        self.signals = StorageDownloadUrlSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=30)
            storage_api = StorageAPI(session)
            params = {
                "url": self.url,
                "content": self.content_type,
                "verify-certificates": 1 if self.verify_certificates else 0,
            }
            if self.filename:
                params["filename"] = self.filename
            if self.checksum:
                params["checksum"] = self.checksum
            result = storage_api.download_url(self.node_name, self.storage_name, **params)
            if isinstance(result, str) and result.startswith("UPID:"):
                status, exitstatus = _poll_task(
                    session, self.node_name, result, timeout=self.timeout
                )
                if status == "stopped" and exitstatus == "OK":
                    name = self.filename or self.url.split("/")[-1].split("?")[0] or "file"
                    _safe_emit(self.signals.result,
                               tr("Download complete: {name}").format(name=name))
                else:
                    err = exitstatus or status
                    _safe_emit(self.signals.error,
                               tr("Download failed: {err}").format(err=err))
            else:
                _safe_emit(self.signals.result, tr("Download complete"))
        except Exception as e:
            logger.debug("download-url error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class StorageMoveSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class StorageMoveWorker(QRunnable):
    def __init__(self, host_cfg, node_name, storage_name, volid,
                 target_storage, target_vmid=0, delete_source=False, timeout=300):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.storage_name = storage_name
        self.volid = volid
        self.target_storage = target_storage
        self.target_vmid = target_vmid
        self.delete_source = delete_source
        self.timeout = timeout
        self.signals = StorageMoveSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=10)
            storage_api = StorageAPI(session)
            upid = storage_api.move_content(
                self.node_name, self.storage_name, self.volid,
                self.target_storage, target_vmid=self.target_vmid,
                delete_source=self.delete_source,
            )
            if isinstance(upid, dict):
                upid = upid.get("data", upid)
            if isinstance(upid, str) and upid.startswith("UPID:"):
                status, exitstatus = _poll_task(
                    session, self.node_name, upid, timeout=self.timeout
                )
                if status == "stopped" and exitstatus == "OK":
                    _safe_emit(self.signals.result,
                               tr("Move complete: {volid} → {storage}").format(
                                   volid=self.volid, storage=self.target_storage))
                else:
                    err = exitstatus or status
                    _safe_emit(self.signals.error, tr("Move failed: {err}").format(err=err))
            else:
                _safe_emit(self.signals.result,
                           tr("Move complete: {volid} → {storage}").format(
                               volid=self.volid, storage=self.target_storage))
        except Exception as e:
            logger.debug("move error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# VzdumpWorker — POST /nodes/{node}/vzdump (on-demand backup)
# ----------------------------------------------------------------------
class VzdumpSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class VzdumpWorker(QRunnable):
    def __init__(self, host_cfg, node_name, vmid, storage,
                 mode="snapshot", compress="0", notes="", remove=False,
                 bwlimit=0, timeout=3600):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.storage = storage
        self.mode = mode
        self.compress = compress
        self.notes = notes
        self.remove = remove
        self.bwlimit = bwlimit
        self.timeout = timeout
        self.signals = VzdumpSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=10)
            node_api = NodeAPI(session)
            params = {
                "vmid": str(self.vmid),
                "storage": self.storage,
                "mode": self.mode,
                "compress": self.compress,
            }
            if self.notes:
                params["notes"] = self.notes
            if self.remove:
                params["remove"] = 1
            if self.bwlimit > 0:
                params["bwlimit"] = self.bwlimit
            upid = node_api.backup_vzdump(self.node_name, **params)
            if isinstance(upid, dict):
                upid = upid.get("data", upid)
            if isinstance(upid, str) and upid.startswith("UPID:"):
                status, exitstatus = _poll_task(
                    session, self.node_name, upid, timeout=self.timeout
                )
                if status == "stopped" and exitstatus == "OK":
                    _safe_emit(self.signals.result,
                               tr("Backup completed for VM {vmid}").format(vmid=self.vmid))
                else:
                    err = exitstatus or status
                    _safe_emit(self.signals.error, tr("Backup failed: {err}").format(err=err))
            else:
                _safe_emit(self.signals.result,
                           tr("Backup completed for VM {vmid}").format(vmid=self.vmid))
        except Exception as e:
            logger.debug("vzdump error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# VmRestoreWorker — POST /nodes/{node}/qemu or /nodes/{node}/lxc (restore)
# ----------------------------------------------------------------------
class VmRestoreSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class VmRestoreWorker(QRunnable):
    def __init__(self, host_cfg, node_name, vmid, vm_type, archive,
                 storage="", name="", force=False, unique=False, timeout=3600):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.archive = archive
        self.storage = storage
        self.name = name
        self.force = force
        self.unique = unique
        self.timeout = timeout
        self.signals = VmRestoreSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=10)
            vm_api = VmAPI(session)
            params = {
                "vmid": int(self.vmid),
                "archive": self.archive,
                "force": 1 if self.force else 0,
            }
            if self.storage:
                params["storage"] = self.storage
            if self.vm_type == "lxc":
                if self.name:
                    params["hostname"] = self.name
                upid = vm_api.create_lxc(self.node_name, **params)
            else:
                if self.name:
                    params["name"] = self.name
                if self.unique:
                    params["unique"] = 1
                upid = vm_api.create_qemu(self.node_name, **params)
            if isinstance(upid, dict):
                upid = upid.get("data", upid)
            if isinstance(upid, str) and upid.startswith("UPID:"):
                status, exitstatus = _poll_task(
                    session, self.node_name, upid, timeout=self.timeout
                )
                if status == "stopped" and exitstatus == "OK":
                    _safe_emit(self.signals.result,
                               tr("Restore completed for VM {vmid}").format(vmid=self.vmid))
                else:
                    err = exitstatus or status
                    _safe_emit(self.signals.error, tr("Restore failed: {err}").format(err=err))
            else:
                _safe_emit(self.signals.result,
                           tr("Restore completed for VM {vmid}").format(vmid=self.vmid))
        except Exception as e:
            logger.debug("restore error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# Cluster jobs — GET /cluster/backup (PVE7) or /cluster/jobs (PVE8+)
# ----------------------------------------------------------------------
class ClusterJobsSignals(QObject):
    jobs_ready = Signal(list)
    jobs_error = Signal(str)
    finished = Signal()


class ClusterJobsWorker(QRunnable):
    """Fetch scheduled jobs (backup + replication) from cluster API."""

    def __init__(self, host_cfg, pve_major=7):
        super().__init__()
        self.host_cfg = host_cfg
        self.pve_major = pve_major
        self.signals = ClusterJobsSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            cluster_api = ClusterAPI(session)
            jobs = cluster_api.list_all_jobs(pve_major=self.pve_major)
            _safe_emit(self.signals.jobs_ready, jobs)
        except Exception as e:
            logger.debug("cluster jobs error: %s", e)
            _safe_emit(self.signals.jobs_error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# Cluster job create — POST /cluster/backup or /cluster/jobs
# ----------------------------------------------------------------------
class ClusterJobCreateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class ClusterJobCreateWorker(QRunnable):
    """Create a scheduled backup job."""

    def __init__(self, host_cfg, params, pve_major=7):
        super().__init__()
        self.host_cfg = host_cfg
        self.params = params
        self.pve_major = pve_major
        self.signals = ClusterJobCreateSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            cluster_api = ClusterAPI(session)
            cluster_api.create_backup_job(self.params, pve_major=self.pve_major)
            _safe_emit(self.signals.result, tr("Backup job created"))
        except Exception as e:
            logger.debug("job create error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# Cluster job update — PUT /cluster/backup/{id} or /cluster/jobs/{id}
# ----------------------------------------------------------------------
class ClusterJobUpdateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class ClusterJobUpdateWorker(QRunnable):
    """Update a scheduled backup job."""

    def __init__(self, host_cfg, job_id, params, pve_major=7):
        super().__init__()
        self.host_cfg = host_cfg
        self.job_id = job_id
        self.params = params
        self.pve_major = pve_major
        self.signals = ClusterJobUpdateSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            cluster_api = ClusterAPI(session)
            cluster_api.update_backup_job(self.job_id, self.params, pve_major=self.pve_major)
            _safe_emit(self.signals.result, tr("Backup job updated"))
        except Exception as e:
            logger.debug("job update error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# Cluster job delete — DELETE /cluster/backup/{id} or /cluster/jobs/{id}
# ----------------------------------------------------------------------
class ClusterJobDeleteSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class ClusterJobDeleteWorker(QRunnable):
    """Delete a scheduled backup job."""

    def __init__(self, host_cfg, job_id, pve_major=7):
        super().__init__()
        self.host_cfg = host_cfg
        self.job_id = job_id
        self.pve_major = pve_major
        self.signals = ClusterJobDeleteSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            cluster_api = ClusterAPI(session)
            cluster_api.delete_backup_job(self.job_id, pve_major=self.pve_major)
            _safe_emit(self.signals.result, tr("Backup job deleted"))
        except Exception as e:
            logger.debug("job delete error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# Access Management — Users
# ----------------------------------------------------------------------

class AccessUsersSignals(QObject):
    users_ready = Signal(list)
    users_error = Signal(str)
    finished = Signal()


class AccessUsersWorker(QRunnable):
    """Fetch all users with token info (full=1)."""

    def __init__(self, host_cfg):
        super().__init__()
        self.host_cfg = host_cfg
        self.signals = AccessUsersSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            data = access_api.list_users()
            _safe_emit(self.signals.users_ready, data)
        except Exception as e:
            logger.debug("access users error: %s", e)
            _safe_emit(self.signals.users_error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class AccessUserCreateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class AccessUserCreateWorker(QRunnable):
    """Create a new PVE user."""

    def __init__(self, host_cfg, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.params = params
        self.signals = AccessUserCreateSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            access_api.create_user(**self.params)
            _safe_emit(self.signals.result, tr("User created"))
        except Exception as e:
            logger.debug("user create error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class AccessUserUpdateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class AccessUserUpdateWorker(QRunnable):
    """Update an existing PVE user."""

    def __init__(self, host_cfg, userid, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.userid = userid
        self.params = params
        self.signals = AccessUserUpdateSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            access_api.update_user(self.userid, **self.params)
            _safe_emit(self.signals.result, tr("User updated"))
        except Exception as e:
            logger.debug("user update error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class AccessUserDeleteSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class AccessUserDeleteWorker(QRunnable):
    """Delete a PVE user."""

    def __init__(self, host_cfg, userid):
        super().__init__()
        self.host_cfg = host_cfg
        self.userid = userid
        self.signals = AccessUserDeleteSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            access_api.delete_user(self.userid)
            _safe_emit(self.signals.result, tr("User deleted"))
        except Exception as e:
            logger.debug("user delete error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# Access Management — API Tokens
# ----------------------------------------------------------------------

class AccessTokensSignals(QObject):
    tokens_ready = Signal(list)
    tokens_error = Signal(str)
    finished = Signal()


class AccessTokensWorker(QRunnable):
    """Fetch API tokens for a user."""

    def __init__(self, host_cfg, userid):
        super().__init__()
        self.host_cfg = host_cfg
        self.userid = userid
        self.signals = AccessTokensSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            data = access_api.list_tokens(self.userid)
            _safe_emit(self.signals.tokens_ready, data)
        except Exception as e:
            logger.debug("access tokens error: %s", e)
            _safe_emit(self.signals.tokens_error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class AccessTokenCreateSignals(QObject):
    result = Signal(str, str, str)
    error = Signal(str)
    finished = Signal()


class AccessTokenCreateWorker(QRunnable):
    """Create an API token. Returns (msg, full_tokenid, value)."""

    def __init__(self, host_cfg, userid, tokenid, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.userid = userid
        self.tokenid = tokenid
        self.params = params
        self.signals = AccessTokenCreateSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            data = access_api.create_token(self.userid, self.tokenid, **self.params)
            full = data.get("full-tokenid", "")
            value = data.get("value", "")
            _safe_emit(self.signals.result, tr("Token created"), full, value)
        except Exception as e:
            logger.debug("token create error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class AccessTokenUpdateSignals(QObject):
    result = Signal(str, str, str)
    error = Signal(str)
    finished = Signal()


class AccessTokenUpdateWorker(QRunnable):
    """Update an API token. If regenerate=1, returns (msg, full_tokenid, value)."""

    def __init__(self, host_cfg, userid, tokenid, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.userid = userid
        self.tokenid = tokenid
        self.params = params
        self.signals = AccessTokenUpdateSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            data = access_api.update_token(self.userid, self.tokenid, **self.params)
            full = (data or {}).get("full-tokenid", "")
            value = (data or {}).get("value", "")
            _safe_emit(self.signals.result, tr("Token updated"), full, value)
        except Exception as e:
            logger.debug("token update error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class AccessTokenDeleteSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class AccessTokenDeleteWorker(QRunnable):
    """Delete an API token."""

    def __init__(self, host_cfg, userid, tokenid):
        super().__init__()
        self.host_cfg = host_cfg
        self.userid = userid
        self.tokenid = tokenid
        self.signals = AccessTokenDeleteSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            access_api.delete_token(self.userid, self.tokenid)
            _safe_emit(self.signals.result, tr("Token deleted"))
        except Exception as e:
            logger.debug("token delete error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# Access Management — Groups
# ----------------------------------------------------------------------

class AccessGroupsSignals(QObject):
    groups_ready = Signal(list)
    groups_error = Signal(str)
    finished = Signal()


class AccessGroupsWorker(QRunnable):
    """Fetch all user groups."""

    def __init__(self, host_cfg):
        super().__init__()
        self.host_cfg = host_cfg
        self.signals = AccessGroupsSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            data = access_api.list_groups()
            _safe_emit(self.signals.groups_ready, data)
        except Exception as e:
            logger.debug("access groups error: %s", e)
            _safe_emit(self.signals.groups_error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class AccessGroupCreateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class AccessGroupCreateWorker(QRunnable):
    """Create a new user group."""

    def __init__(self, host_cfg, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.params = params
        self.signals = AccessGroupCreateSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            access_api.create_group(**self.params)
            _safe_emit(self.signals.result, tr("Group created"))
        except Exception as e:
            logger.debug("group create error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class AccessGroupUpdateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class AccessGroupUpdateWorker(QRunnable):
    """Update a user group."""

    def __init__(self, host_cfg, groupid, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.groupid = groupid
        self.params = params
        self.signals = AccessGroupUpdateSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            access_api.update_group(self.groupid, **self.params)
            _safe_emit(self.signals.result, tr("Group updated"))
        except Exception as e:
            logger.debug("group update error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class AccessGroupDeleteSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class AccessGroupDeleteWorker(QRunnable):
    """Delete a user group."""

    def __init__(self, host_cfg, groupid):
        super().__init__()
        self.host_cfg = host_cfg
        self.groupid = groupid
        self.signals = AccessGroupDeleteSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            access_api.delete_group(self.groupid)
            _safe_emit(self.signals.result, tr("Group deleted"))
        except Exception as e:
            logger.debug("group delete error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# Access Management — Roles
# ----------------------------------------------------------------------

class AccessRolesSignals(QObject):
    roles_ready = Signal(list)
    roles_error = Signal(str)
    finished = Signal()


class AccessRolesWorker(QRunnable):
    """Fetch all roles."""

    def __init__(self, host_cfg):
        super().__init__()
        self.host_cfg = host_cfg
        self.signals = AccessRolesSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            data = access_api.list_roles()
            _safe_emit(self.signals.roles_ready, data)
        except Exception as e:
            logger.debug("access roles error: %s", e)
            _safe_emit(self.signals.roles_error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class AccessRoleCreateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class AccessRoleCreateWorker(QRunnable):
    """Create a new role."""

    def __init__(self, host_cfg, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.params = params
        self.signals = AccessRoleCreateSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            access_api.create_role(**self.params)
            _safe_emit(self.signals.result, tr("Role created"))
        except Exception as e:
            logger.debug("role create error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class AccessRoleUpdateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class AccessRoleUpdateWorker(QRunnable):
    """Update a role's privileges."""

    def __init__(self, host_cfg, roleid, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.roleid = roleid
        self.params = params
        self.signals = AccessRoleUpdateSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            access_api.update_role(self.roleid, **self.params)
            _safe_emit(self.signals.result, tr("Role updated"))
        except Exception as e:
            logger.debug("role update error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class AccessRoleDeleteSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class AccessRoleDeleteWorker(QRunnable):
    """Delete a role."""

    def __init__(self, host_cfg, roleid):
        super().__init__()
        self.host_cfg = host_cfg
        self.roleid = roleid
        self.signals = AccessRoleDeleteSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            access_api.delete_role(self.roleid)
            _safe_emit(self.signals.result, tr("Role deleted"))
        except Exception as e:
            logger.debug("role delete error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# Access Management — ACL / Permissions
# ----------------------------------------------------------------------

class AccessAclSignals(QObject):
    acl_ready = Signal(list)
    acl_error = Signal(str)
    finished = Signal()


class AccessAclWorker(QRunnable):
    """Fetch ACL entries."""

    def __init__(self, host_cfg):
        super().__init__()
        self.host_cfg = host_cfg
        self.signals = AccessAclSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            data = access_api.list_acl()
            _safe_emit(self.signals.acl_ready, data)
        except Exception as e:
            logger.debug("access acl error: %s", e)
            _safe_emit(self.signals.acl_error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


class AccessAclUpdateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()


class AccessAclUpdateWorker(QRunnable):
    """Add or remove ACL permissions."""

    def __init__(self, host_cfg, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.params = params
        self.signals = AccessAclUpdateSignals()

    def run(self):
        session = None
        try:
            session = ProxmoxSession(self.host_cfg, timeout=15)
            access_api = AccessAPI(session)
            access_api.update_acl(**self.params)
            is_delete = int(self.params.get("delete", 0) or 0)
            msg = tr("Permissions removed") if is_delete else tr("Permissions added")
            _safe_emit(self.signals.result, msg)
        except Exception as e:
            logger.debug("acl update error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if session:
                session.close()
            _safe_emit(self.signals.finished)


# ----------------------------------------------------------------------
# VersionCheckWorker — check GitHub releases for newer versions
# ----------------------------------------------------------------------
_GITHUB_API_LATEST = "https://api.github.com/repos/mcluremail/pvecenter/releases/latest"


class VersionCheckSignals(QObject):
    update_available = Signal(str, str)  # latest_version, release_url
    finished = Signal()


class VersionCheckWorker(QRunnable):
    """Check GitHub releases for a newer version of PVE Center."""
    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version
        self.signals = VersionCheckSignals()

    @staticmethod
    def _parse_version(v):
        parts = []
        for p in v.lstrip("v").split("."):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        return parts

    def run(self):
        try:
            resp = requests.get(_GITHUB_API_LATEST, timeout=10,
                                headers={"Accept": "application/vnd.github+json"})
            resp.raise_for_status()
            data = resp.json()
            latest = data.get("tag_name", "").strip()
            if not latest:
                return
            release_url = data.get("html_url", "")
            latest_norm = latest.lstrip("v")
            current_norm = self.current_version.lstrip("v")
            if self._parse_version(latest_norm) > self._parse_version(current_norm):
                _safe_emit(self.signals.update_available, latest_norm, release_url)
        except Exception as e:
            logger.debug("version check error: %s", e)
        finally:
            _safe_emit(self.signals.finished)
