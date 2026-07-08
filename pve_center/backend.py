import logging
import threading
import time

import urllib3
from proxmoxer import ProxmoxAPI
from PySide6.QtCore import QObject, QRunnable, Signal

from .ui.i18n import tr
from .ui.vm_actions import VM_ACTION_MESSAGE_LABELS

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _verify_ssl(cfg):
    """Return verify_ssl value for requests/proxmoxer.
    trust_ssl=True (default) → accept cert, verify_ssl=False.
    trust_ssl=False → strict verification, verify_ssl=True."""
    return not bool(cfg.get("trust_ssl", True))


def _close_proxmox(proxmox):
    """Close underlying requests.Session to prevent connection pool leaks."""
    try:
        sess = proxmox._store.get("session")
        if sess is not None:
            sess.close()
    except Exception:
        pass


# ----------------------------------------------------------------------
# Create API token for PVE Center
# ----------------------------------------------------------------------
PVE_PORT = 8006


def _pve_ticket_auth(host, user, password, verify=False):
    import requests as rq
    url = f"https://{host}:{PVE_PORT}/api2/json/access/ticket"
    resp = rq.post(url, data={"username": user, "password": password},
                   verify=verify, timeout=15)
    resp.raise_for_status()
    data = resp.json().get("data", {})
    return {
        "ticket": data.get("ticket"),
        "csrf": data.get("CSRFPreventionToken"),
    }


def create_admin_token(host, user, password, trust_ssl=True):
    """Create an API token for the specified PVE user.
    The token is created on behalf of the user — PVE audit shows
    the real operator, and permissions match their roles.

    Args:
        host: PVE host address
        user: existing PVE user (root@pam, user@ipa, ...)
        password: user's password
        trust_ssl: if True (default), accept self-signed certs (verify=False).
                   If False, require valid SSL certificate.

    Returns:
        dict with token_name, token_value, user fields
        or dict with error field.
    """
    import secrets as sec
    import string as str_mod

    import requests as rq
    verify = not bool(trust_ssl)

    try:
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
                f"https://{host}:{PVE_PORT}/api2/json/access/users/{user}/token/{token_id}",
                data={"comment": "PVE Center", "expire": 0, "privsep": 0},
                timeout=15,
            )
            logger.info("token_create %s %s HTTP %s", method, token_id, r.status_code)
            if r.status_code < 400:
                break
        if r is None or r.status_code >= 400:
            logger.error("token_create error: %s", r.text[:300])
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
                verify=verify, timeout=10,
            )
            if vr.status_code != 200:
                logger.warning("verify FAILED: %s", vr.text[:200])
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
        return {"error": msg}
    finally:
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
    def __init__(self, host, user, password, trust_ssl=True):
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
            try:
                self.signals.token_error.emit(str(e))
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
        proxmox = None
        try:
            proxmox = ProxmoxAPI(
                self.node_cfg["host"],
                user=self.node_cfg["user"],
                token_name=self.node_cfg["token_name"],
                token_value=self.node_cfg["token_value"],
                verify_ssl=_verify_ssl(self.node_cfg),
                timeout=15
            )

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
                    pools_data = proxmox.pools.get()
                    with pool_lock:
                        pool_names = [p.get("poolid") or p.get("pool") for p in pools_data
                                      if p.get("poolid") or p.get("pool")]

                    def fetch_pool_detail(p):
                        pname = p.get("poolid") or p.get("pool")
                        if not pname:
                            return
                        try:
                            pd = proxmox.pools(pname).get()
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
                except Exception:
                    logger.debug("backend error", exc_info=True)

            def fetch_ha():
                nonlocal ha_groups
                try:
                    result = []
                    for g in proxmox.cluster.ha.groups.get():
                        gn = g.get("group")
                        if gn:
                            result.append(gn)
                    result.sort()
                    with ha_lock:
                        ha_groups = result
                except Exception:
                    pass

            def fetch_resources():
                nonlocal nodes, vms, storages, cluster_name
                try:
                    resources = proxmox.cluster.resources.get()
                    with res_lock:
                        nodes = [r for r in resources if r.get("type") == "node"]
                        vms = [r for r in resources if r.get("type") in ("qemu", "lxc")]
                        storages = [r for r in resources if r.get("type") == "storage"]
                        cluster_name = self.node_cfg.get("cluster", "")
                        for n in nodes:
                            short = n["node"]
                            n["_display_name"] = f"{short}@{cluster_name}" if cluster_name else short
                except Exception:
                    logger.debug("backend error", exc_info=True)

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
                        node_storages = proxmox.nodes(node_name).storage.get()
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
                        ver = proxmox.nodes(node_name).version.get()
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
                        st = proxmox.nodes(node_name).status.get()
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
                        local_nodes = proxmox.nodes.get()
                        nn = local_nodes[0]["node"] if local_nodes else self.node_cfg["name"]
                    except Exception:
                        nn = self.node_cfg["name"]
                    node_name = nn
                    try:
                        node_status = proxmox.nodes(node_name).status.get()
                    except Exception:
                        return
                    with res_lock:
                        nodes = [{**node_status, "node": node_name,
                                  "_display_name": self.node_cfg["name"],
                                  "host_name": self.node_cfg["name"],
                                  "status": "online"}]
                    try:
                        qemu_list = proxmox.nodes(node_name).qemu.get()
                        lxc_list = proxmox.nodes(node_name).lxc.get()
                        vms_local = []
                        for v in qemu_list:
                            vms_local.append({**v, "type": "qemu",
                                              "node": node_name,
                                              "host_name": self.node_cfg["name"],
                                              "pool": vmid_to_pool.get(v["vmid"])})
                        for v in lxc_list:
                            vms_local.append({**v, "type": "lxc",
                                              "node": node_name,
                                              "host_name": self.node_cfg["name"],
                                              "pool": vmid_to_pool.get(v["vmid"])})
                        storages_local = list(proxmox.nodes(node_name).storage.get())
                        for st in storages_local:
                            st["node"] = node_name
                            st["host_name"] = self.node_cfg["name"]
                            st["cluster"] = ""
                        with res_lock:
                            vms = vms_local
                            storages = storages_local
                    except Exception:
                        logger.debug("backend error", exc_info=True)

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
                        ver = proxmox.nodes(node_name).version.get()
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
                iso_storages = [
                    s["storage"] for s in storages
                    if s.get("node") == nname and "iso" in (s.get("content", "") or "").split(",")
                ]
                if not iso_storages:
                    with iso_lock:
                        iso_images[nname] = []
                    return
                try:
                    seen = {}
                    for sname in iso_storages:
                        for item in proxmox.nodes(nname).storage(sname).content.get(content="iso"):
                            if item.get("content") == "iso":
                                volid = item["volid"]
                                if volid not in seen:
                                    seen[volid] = {
                                        "volid": volid,
                                        "format": item.get("format", ""),
                                        "size": item.get("size", 0),
                                    }
                    with iso_lock:
                        iso_images[nname] = sorted(seen.values(), key=lambda x: x["volid"])
                except Exception:
                    with iso_lock:
                        iso_images[nname] = []

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
            _close_proxmox(proxmox)
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
        proxmox = None
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=_verify_ssl(self.host_cfg),
                timeout=10
            )
            if self.vm_type == "qemu":
                status = proxmox.nodes(self.node_name).qemu(self.vmid).status.current.get()
            else:
                status = proxmox.nodes(self.node_name).lxc(self.vmid).status.current.get()
            try:
                self.signals.detail_ready.emit({
                    "vmid": self.vmid,
                    "status": "ok",
                    "data": status
                })
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error", exc_info=True)
            try:
                self.signals.detail_ready.emit({
                    "vmid": self.vmid,
                    "status": "error",
                    "error": str(e)
                })
            except RuntimeError:
                pass
        finally:
            _close_proxmox(proxmox)
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
        proxmox = None
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=_verify_ssl(self.host_cfg),
                timeout=10
            )
            if self.vm_type == "qemu":
                config = proxmox.nodes(self.node_name).qemu(self.vmid).config.get()
            else:
                config = proxmox.nodes(self.node_name).lxc(self.vmid).config.get()
            try:
                self.signals.config_ready.emit(self.vmid, config)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error", exc_info=True)
            try:
                self.signals.config_error.emit(self.vmid, str(e))
            except RuntimeError:
                pass
        finally:
            _close_proxmox(proxmox)
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
        proxmox = None
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=_verify_ssl(self.host_cfg),
                timeout=10,
            )
            if self.vm_type == "qemu":
                result = proxmox.nodes(self.node_name).qemu(self.vmid).config.put(**self.params)
            else:
                result = proxmox.nodes(self.node_name).lxc(self.vmid).config.put(**self.params)
            try:
                self.signals.config_updated.emit(self.vmid, result)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error", exc_info=True)
            try:
                self.signals.config_update_error.emit(self.vmid, str(e))
            except RuntimeError:
                pass
        finally:
            _close_proxmox(proxmox)
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
        proxmox = None
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=_verify_ssl(self.host_cfg),
                timeout=10
            )
            tasks = proxmox.nodes(self.node_name).tasks.get(vmid=self.vmid, limit=self.limit)
            try:
                self.signals.tasks_ready.emit(self.vmid, tasks)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error", exc_info=True)
            try:
                self.signals.tasks_error.emit(self.vmid, str(e))
            except RuntimeError:
                pass
        finally:
            _close_proxmox(proxmox)
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
        proxmox = None
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=_verify_ssl(self.host_cfg),
                timeout=10,
            )
            node = proxmox.nodes(self.node_name)
            resource = node.qemu(self.vmid) if self.vm_type == "qemu" else node.lxc(self.vmid)
            snaps = resource.snapshot.get()
            filtered = [dict(s) for s in snaps if s.get("name") != "current"]
            for snap in filtered:
                name = snap.get("name", "")
                if not name:
                    continue
                try:
                    cfg = resource.snapshot(name).config.get()
                    total_bytes = 0
                    for key, val in cfg.items():
                        if not isinstance(val, str):
                            continue
                        if key[0].isdigit() or key.startswith(("scsi", "ide", "sata", "virtio", "efidisk")):
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
            _close_proxmox(proxmox)
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


# ----------------------------------------------------------------------
# Удаление токена с сервера
# ----------------------------------------------------------------------
def delete_host_token(host_cfg):
    """Удаляет API-токен с PVE-сервера через Proxmoxer.
       Возвращает True при успехе, False при ошибке."""
    proxmox = None
    try:
        proxmox = ProxmoxAPI(
            host_cfg["host"],
            user=host_cfg["user"],
            token_name=host_cfg["token_name"],
            token_value=host_cfg["token_value"],
            verify_ssl=_verify_ssl(host_cfg),
            timeout=10,
        )
        userid = host_cfg["user"]
        token_id = host_cfg["token_name"]
        proxmox.access.users(userid).token(token_id).delete()
        logger.info("Token %s for user %s deleted from %s", token_id, userid, host_cfg["host"])
        return True
    except Exception as e:
        logger.warning("Failed to delete token from %s: %s", host_cfg.get("host", "?"), e)
        return False
    finally:
        _close_proxmox(proxmox)


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
        proxmox = None
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=_verify_ssl(self.host_cfg),
                timeout=10,
            )
            if self.vm_type == "qemu":
                call = getattr(
                    proxmox.nodes(self.node_name).qemu(self.vmid).status,
                    self.action,
                )
            else:
                call = getattr(
                    proxmox.nodes(self.node_name).lxc(self.vmid).status,
                    self.action,
                )
            call.post()
            try:
                action_name = self.ACTION_NAMES.get(
                    self.action, self.action
                )
                self.signals.action_result.emit(
                    tr("VM {vmid}: {action} completed").format(vmid=self.vmid, action=action_name)
                )
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error", exc_info=True)
            try:
                self.signals.action_error.emit(str(e))
            except RuntimeError:
                pass
        finally:
            _close_proxmox(proxmox)
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


def _poll_task(proxmox, node_name, upid, timeout=60, interval=1.0):
    """Poll PVE async task until it finishes or timeout.
    Returns (status, exitstatus) tuple: ('stopped', 'OK') on success.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            info = proxmox.nodes(node_name).tasks(upid).status.get()
            data = info.get("data", info) if isinstance(info, dict) else info
            status = data.get("status", "")
            if status == "stopped":
                return status, data.get("exitstatus", "")
            time.sleep(interval)
        except Exception as exc:
            return "error", str(exc)
    return "timeout", ""


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
        proxmox = None
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=_verify_ssl(self.host_cfg),
                timeout=10,
            )
            node = proxmox.nodes(self.node_name)
            resource = node.qemu(self.vmid) if self.vm_type == "qemu" else node.lxc(self.vmid)
            upid = resource.snapshot.post(
                snapname=self.snap_name,
                description=self.description,
                vmstate=1 if self.vmstate else 0,
            )
            if isinstance(upid, dict):
                upid = upid.get("data", upid)
            if isinstance(upid, str) and upid.startswith("UPID:"):
                status, exitstatus = _poll_task(proxmox, self.node_name, upid, timeout=120)
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
            logger.debug("backend error", exc_info=True)
            try:
                self.signals.error.emit(str(e))
            except RuntimeError:
                pass
        finally:
            _close_proxmox(proxmox)
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
        proxmox = None
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=_verify_ssl(self.host_cfg),
                timeout=10,
            )
            node = proxmox.nodes(self.node_name)
            resource = node.qemu(self.vmid) if self.vm_type == "qemu" else node.lxc(self.vmid)
            upid = resource.snapshot(self.snap_name).delete()
            if isinstance(upid, dict):
                upid = upid.get("data", upid)
            if isinstance(upid, str) and upid.startswith("UPID:"):
                status, exitstatus = _poll_task(proxmox, self.node_name, upid, timeout=120)
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
            logger.debug("backend error", exc_info=True)
            try:
                self.signals.error.emit(str(e))
            except RuntimeError:
                pass
        finally:
            _close_proxmox(proxmox)
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
                proxmox = None
                try:
                    proxmox = ProxmoxAPI(
                        host_cfg["host"],
                        user=host_cfg["user"],
                        token_name=host_cfg["token_name"],
                        token_value=host_cfg["token_value"],
                        verify_ssl=_verify_ssl(host_cfg),
                        timeout=10
                    )
                    tasks = proxmox.nodes(node_name).tasks.get(limit=100)
                    with lock:
                        results[node_name] = tasks
                except Exception as e:
                    with lock:
                        errors.append(f"{node_name}: {e}")
                finally:
                    _close_proxmox(proxmox)

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
                logger.debug("ClusterTasksWorker merge error", exc_info=True)
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
# VmConsoleWorker (SPICE)
# ----------------------------------------------------------------------
class VmConsoleSignals(QObject):
    console_ready = Signal(str)
    console_error = Signal(str)
    finished = Signal()


class VmConsoleWorker(QRunnable):
    """Запрашивает SPICE proxy у PVE, пишет .vv файл и запускает remote-viewer."""
    def __init__(self, host_cfg, node_name, vmid, vm_type="qemu"):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.signals = VmConsoleSignals()

    def run(self):
        import os
        import subprocess
        import sys
        import tempfile
        vv_path = None
        proxmox = None
        try:
            try:
                proxmox = ProxmoxAPI(
                    self.host_cfg["host"],
                    user=self.host_cfg["user"],
                    token_name=self.host_cfg["token_name"],
                    token_value=self.host_cfg["token_value"],
                    verify_ssl=_verify_ssl(self.host_cfg),
                    timeout=10
                )
                endpoint = (proxmox.nodes(self.node_name).lxc if self.vm_type == "lxc"
                            else proxmox.nodes(self.node_name).qemu)
                config = endpoint(self.vmid).spiceproxy.post(
                    proxy=self.host_cfg["host"]
                )
            except Exception as e:
                msg = str(e).lower()
                if "permission check failed" in msg or "403" in msg:
                    err = tr("PVE permission denied for SPICE (requires VM.Console)")
                elif "not supported" in msg or "spice" in msg:
                    err = tr("SPICE not supported for this VM")
                else:
                    err = tr("SPICE proxy error: {}").format(e)
                try:
                    self.signals.console_error.emit(err)
                except RuntimeError:
                    pass
                return
            finally:
                _close_proxmox(proxmox)
                proxmox = None

            try:
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

                fd, vv_path = tempfile.mkstemp(suffix=".vv", prefix="pve_")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
            except Exception as e:
                try:
                    self.signals.console_error.emit(tr("VV file write error: {}").format(e))
                except RuntimeError:
                    pass
                return

            try:
                if sys.platform == "win32":
                    candidates = [
                        os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                                     "VirtViewer", "bin", "remote-viewer.exe"),
                        os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                                     "VirtViewer", "bin", "remote-viewer.exe"),
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
                    logger.info("remote-viewer started (pid=%d)", proc.pid)
                    def _cleanup():
                        try:
                            proc.wait()
                        except Exception:
                            pass
                        if vv_path and os.path.exists(vv_path):
                            try:
                                os.unlink(vv_path)
                            except OSError:
                                pass
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
        proxmox = None
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=_verify_ssl(self.host_cfg),
                timeout=30,
            )

            params = dict(self.params)
            # Request next free VMID if not specified
            if not params.get("vmid"):
                try:
                    params["vmid"] = proxmox.cluster.nextid.get()
                except Exception:
                    try:
                        self.signals.vm_error.emit(
                            tr("Could not get next free VMID from cluster")
                        )
                    except RuntimeError:
                        pass
                    return

            proxmox.nodes(self.node_name).qemu.post(**params)
            # POST /nodes/{node}/qemu returns UPID string, not {"data": {"vmid":...}}
            # vmid is now guaranteed in params (user-provided or nextid)
            vmid = params.get("vmid", "?")
            msg = tr("VM {vmid} created on {node}").format(vmid=vmid, node=self.node_name)

            # Add to HA group
            if self.ha_group:
                try:
                    ha_params = {
                        "sid": f"vm:{vmid}",
                        "group": self.ha_group,
                    }
                    # If user unchecked "Start", prevent HA from starting the VM
                    if not self.params.get("start"):
                        ha_params["state"] = "stopped"
                    proxmox.cluster.ha.resources.post(**ha_params)
                    msg += tr(", added to HA ") + self.ha_group
                except Exception as ha_err:
                    msg += tr(", but HA error: {}").format(ha_err)

            try:
                self.signals.vm_created.emit(msg)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error", exc_info=True)
            try:
                self.signals.vm_error.emit(str(e))
            except RuntimeError:
                pass
        finally:
            _close_proxmox(proxmox)
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


class DeleteVmSignals(QObject):
    vm_deleted = Signal(str)  # success message
    vm_error = Signal(str)    # error message
    finished = Signal()


class DeleteVmWorker(QRunnable):
    """Удаляет QEMU VM через DELETE /nodes/{node}/qemu/{vmid}."""
    def __init__(self, host_cfg, node_name, vmid):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.signals = DeleteVmSignals()

    def run(self):
        proxmox = None
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=_verify_ssl(self.host_cfg),
                timeout=30,
            )

            proxmox.nodes(self.node_name).qemu(self.vmid).delete(purge=1)
            msg = tr("VM {vmid} deleted from {node}").format(vmid=self.vmid, node=self.node_name)
            try:
                self.signals.vm_deleted.emit(msg)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("backend error", exc_info=True)
            try:
                self.signals.vm_error.emit(str(e))
            except RuntimeError:
                pass
        finally:
            _close_proxmox(proxmox)
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


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
            proxmox = None
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=_verify_ssl(self.host_cfg),
                timeout=120,
            )
            params = {"target": self.target_node}
            if self.with_local_disks:
                params["with-local-disks"] = 1
            proxmox.nodes(self.node_name).qemu(self.vmid).migrate.post(**params)
            msg = tr("VM {vmid} migration to {target} started").format(
                vmid=self.vmid, target=self.target_node)
            try:
                self.signals.vm_migrated.emit(msg)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("migrate error", exc_info=True)
            try:
                self.signals.vm_error.emit(str(e))
            except RuntimeError:
                pass
        finally:
            _close_proxmox(proxmox)
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
        proxmox = None
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=_verify_ssl(self.host_cfg),
                timeout=120,
            )

            params = dict(self.params)
            if not params.get("newid"):
                params["newid"] = proxmox.cluster.nextid.get()

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
                proxmox.nodes(self.node_name).lxc(self.vmid).clone.post(**clone_params)
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
                proxmox.nodes(self.node_name).qemu(self.vmid).clone.post(**clone_params)

            newid = params.get("newid", "?")
            msg = tr("VM {vmid} cloned to {newid} on {target}").format(
                vmid=self.vmid, newid=newid,
                target=params.get("target", self.node_name))
            try:
                self.signals.vm_cloned.emit(msg)
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug("clone error", exc_info=True)
            try:
                self.signals.vm_error.emit(str(e))
            except RuntimeError:
                pass
        finally:
            _close_proxmox(proxmox)
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
        proxmox = None
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=_verify_ssl(self.host_cfg),
                timeout=10,
            )
            upid = (
                proxmox.nodes(self.node_name)
                .storage(self.storage)
                .content(self.volid)
                .delete()
            )
            if isinstance(upid, dict):
                upid = upid.get("data", upid)
            if isinstance(upid, str) and upid.startswith("UPID:"):
                status, exitstatus = _poll_task(
                    proxmox, self.node_name, upid, timeout=self.timeout
                )
                if status == "stopped" and exitstatus == "OK":
                    try:
                        self.signals.result.emit(
                            tr("Disk image {volid} destroyed").format(volid=self.volid)
                        )
                    except RuntimeError:
                        pass
                else:
                    err = exitstatus or status
                    try:
                        self.signals.error.emit(
                            tr("Destroy failed: {err}").format(err=err)
                        )
                    except RuntimeError:
                        pass
            else:
                try:
                    self.signals.result.emit(
                        tr("Disk image {volid} destroyed").format(volid=self.volid)
                    )
                except RuntimeError:
                    pass
        except Exception as e:
            logger.debug("storage content delete error", exc_info=True)
            try:
                self.signals.error.emit(str(e))
            except RuntimeError:
                pass
        finally:
            _close_proxmox(proxmox)
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass
