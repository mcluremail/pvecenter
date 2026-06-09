import urllib3
import traceback
import logging
import threading
import concurrent.futures
from PySide6.QtCore import Signal, QRunnable, QObject
from proxmoxer import ProxmoxAPI

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ----------------------------------------------------------------------
# Создание API токена для PVE Center
# ----------------------------------------------------------------------
PVE_PORT = 8006


def _pve_ticket_auth(host, user, password):
    import requests as rq
    url = f"https://{host}:{PVE_PORT}/api2/json/access/ticket"
    resp = rq.post(url, data={"username": user, "password": password},
                   verify=False, timeout=15)
    resp.raise_for_status()
    data = resp.json().get("data", {})
    return {
        "ticket": data.get("ticket"),
        "csrf": data.get("CSRFPreventionToken"),
    }


def create_admin_token(host, user, password):
    """Создаёт API-токен для указанного пользователя PVE.
    Токен создаётся от имени самого пользователя — аудит в PVE показывает
    реального оператора, а права соответствуют его ролям.

    Аргументы:
        host: адрес PVE-хоста
        user: существующий пользователь PVE (root@pam, user@ipa, ...)
        password: его пароль

    Возвращает dict с полями token_name, token_value, user
    или dict с полем error.
    """
    import requests as rq
    import secrets as sec
    import string as str_mod

    try:
        ticket_data = _pve_ticket_auth(host, user, password)
        ticket = ticket_data["ticket"]
        csrf = ticket_data["csrf"]
        sess = rq.Session()
        sess.verify = False
        sess.headers.update({
            "Cookie": f"PVEAuthCookie={ticket}",
            "CSRFPreventionToken": csrf,
        })

        token_id = "pvecenter-" + "".join(
            sec.choice(str_mod.ascii_lowercase + str_mod.digits) for _ in range(6)
        )
        for method in ("post", "put"):
            r = getattr(sess, method)(
                f"https://{host}:{PVE_PORT}/api2/json/access/users/{user}/token/{token_id}",
                data={"comment": "PVE Center dashboard", "expire": 0, "privsep": 0},
                timeout=15,
            )
            logger.info("token_create %s %s HTTP %s", method, token_id, r.status_code)
            if r.status_code < 400:
                break
        if r.status_code >= 400:
            logger.error("token_create error: %s", r.text[:300])
            return {"error": f"Ошибка создания токена: {r.status_code}"}

        data = r.json()
        data = data.get("data", data)
        token_value = ""
        if isinstance(data, dict) and "value" in data:
            token_value = data["value"]
        elif isinstance(data, dict) and data.get("tokenid"):
            token_value = data.get("tokenid", "")

        if not token_value:
            return {"error": "Пустое значение токена в ответе сервера"}

        auth_header = f"PVEAPIToken={user}!{token_id}={token_value}"
        try:
            vr = rq.get(
                f"https://{host}:{PVE_PORT}/api2/json/cluster/resources",
                headers={"Authorization": auth_header},
                verify=False, timeout=10,
            )
            if vr.status_code != 200:
                logger.warning("verify FAILED: %s", vr.text[:200])
                return {"error": f"Токен создан, но не работает: {vr.status_code}"}
        except Exception as ve:
            logger.warning("verify exception: %s", ve)

        return {"token_name": token_id, "token_value": token_value, "user": user}

    except Exception as e:
        msg = str(e)
        if "authorization" in msg.lower() or "permission" in msg.lower() or "401" in msg:
            return {"error": "Неверный логин или пароль"}
        if "connection" in msg.lower() or "timeout" in msg.lower() or "resolve" in msg.lower():
            return {"error": f"Не удалось подключиться к {host}"}
        return {"error": msg}


# ----------------------------------------------------------------------
# FetchWorker (QRunnable)
# ----------------------------------------------------------------------
class TokenCreationSignals(QObject):
    token_ready = Signal(dict)
    token_error = Signal(str)
    finished = Signal()


class TokenCreationWorker(QRunnable):
    """Создаёт API-токен в фоновом потоке, не блокируя UI."""
    def __init__(self, host, user, password):
        super().__init__()
        self.host = host
        self.user = user
        self.password = password
        self.signals = TokenCreationSignals()

    def run(self):
        try:
            result = create_admin_token(self.host, self.user, self.password)
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
        try:
            proxmox = ProxmoxAPI(
                self.node_cfg["host"],
                user=self.node_cfg["user"],
                token_name=self.node_cfg["token_name"],
                token_value=self.node_cfg["token_value"],
                verify_ssl=False,
                timeout=15
            )

            is_cluster_rep = self.node_cfg.get("cluster_rep", False)

            # ── Параллельная фаза 1: pools, HA groups, resources ──────
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
                    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
                        ex.map(fetch_pool_detail, pool_candidates, timeout=10)
                except Exception:
                    traceback.print_exc()

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
                        nodes = [r for r in resources if r["type"] == "node"]
                        vms = [r for r in resources if r["type"] in ("qemu", "lxc")]
                        storages = [r for r in resources if r.get("type") == "storage"]
                        cluster_name = self.node_cfg.get("cluster", "")
                        for n in nodes:
                            short = n["node"]
                            n["_display_name"] = f"{short}@{cluster_name}" if cluster_name else short
                except Exception:
                    traceback.print_exc()

            phase1 = []
            phase1.append(threading.Thread(target=fetch_pools, daemon=True))
            phase1.append(threading.Thread(target=fetch_ha, daemon=True))
            if is_cluster_rep:
                phase1.append(threading.Thread(target=fetch_resources, daemon=True))

            for t in phase1:
                t.start()
            for t in phase1:
                t.join(timeout=20)

            # ── Параллельная фаза 2: storage details per node / standalone data ──
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
                            pve = ver.get("pveversion")
                            if pve:
                                n["pveversion"] = pve
                            qemu = ver.get("qemu")
                            if qemu:
                                n["qemu"] = qemu
                            lxc = ver.get("lxc")
                            if lxc:
                                n["lxctype"] = lxc
                    except Exception:
                        pass
                    # kernel из статуса ноды
                    try:
                        st = proxmox.nodes(node_name).status.get()
                        with version_lock:
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
                                  "status": "online"}]
                    try:
                        qemu_list = proxmox.nodes(node_name).qemu.get()
                        lxc_list = proxmox.nodes(node_name).lxc.get()
                        vms_local = []
                        for v in qemu_list:
                            vms_local.append({**v, "type": "qemu",
                                              "node": node_name,
                                              "pool": vmid_to_pool.get(v["vmid"])})
                        for v in lxc_list:
                            vms_local.append({**v, "type": "lxc",
                                              "node": node_name,
                                              "pool": vmid_to_pool.get(v["vmid"])})
                        storages_local = list(proxmox.nodes(node_name).storage.get())
                        for st in storages_local:
                            st["node"] = node_name
                            st["host_name"] = self.node_cfg["name"]
                        with res_lock:
                            vms = vms_local
                            storages = storages_local
                    except Exception:
                        traceback.print_exc()

                standalone_thread = threading.Thread(target=fetch_standalone, daemon=True)
                standalone_thread.start()
                standalone_thread.join(timeout=30)

                # Версии для standalone ноды
                if nodes:
                    try:
                        ver = proxmox.nodes(node_name).version.get()
                        pve = ver.get("pveversion")
                        if pve:
                            for n in nodes:
                                n["pveversion"] = pve
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
                    try:
                        st = proxmox.nodes(node_name).status.get()
                        kver = st.get("kversion")
                        if kver:
                            for n in nodes:
                                n["kernel"] = kver
                    except Exception:
                        pass

            # ── Параллельная фаза 3: ISO образы ────────────────────
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

            # ── Отправляем результат ──────────────────────────────
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
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=False,
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
            traceback.print_exc()
            try:
                self.signals.detail_ready.emit({
                    "vmid": self.vmid,
                    "status": "error",
                    "error": str(e)
                })
            except RuntimeError:
                pass
        finally:
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
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=False,
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
            traceback.print_exc()
            try:
                self.signals.config_error.emit(self.vmid, str(e))
            except RuntimeError:
                pass
        finally:
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
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=False,
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
            traceback.print_exc()
            try:
                self.signals.config_update_error.emit(self.vmid, str(e))
            except RuntimeError:
                pass
        finally:
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
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=False,
                timeout=10
            )
            tasks = proxmox.nodes(self.node_name).tasks.get(vmid=self.vmid, limit=self.limit)
            try:
                self.signals.tasks_ready.emit(self.vmid, tasks)
            except RuntimeError:
                pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.signals.tasks_error.emit(self.vmid, str(e))
            except RuntimeError:
                pass
        finally:
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
    try:
        proxmox = ProxmoxAPI(
            host_cfg["host"],
            user=host_cfg["user"],
            token_name=host_cfg["token_name"],
            token_value=host_cfg["token_value"],
            verify_ssl=False,
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


class VmActionSignals(QObject):
    action_result = Signal(str)
    action_error = Signal(str)
    finished = Signal()


class VmActionWorker(QRunnable):
    ACTION_NAMES = {
        "start": "Запуск",
        "shutdown": "Выключение",
        "stop": "Принудительное выключение",
        "reboot": "Перезагрузка",
        "reset": "Сброс",
        "resume": "Возобновление",
    }

    def __init__(self, host_cfg, node_name, vmid, vm_type, action):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.action = action
        self.signals = VmActionSignals()

    def run(self):
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=False,
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
                    f"VM {self.vmid}: {action_name} выполнена"
                )
            except RuntimeError:
                pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.signals.action_error.emit(str(e))
            except RuntimeError:
                pass
        finally:
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
    """Загружает задачи со всех нод параллельно через threading.
    Принимает список (host_cfg, node_name) — для каждой ноды
    вызывается /nodes/{node}/tasks, результаты мержатся по UPID."""
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
                try:
                    proxmox = ProxmoxAPI(
                        host_cfg["host"],
                        user=host_cfg["user"],
                        token_name=host_cfg["token_name"],
                        token_value=host_cfg["token_value"],
                        verify_ssl=False,
                        timeout=10
                    )
                    tasks = proxmox.nodes(node_name).tasks.get(limit=100)
                    with lock:
                        results[node_name] = tasks
                except Exception as e:
                    with lock:
                        errors.append(f"{node_name}: {e}")

            threads = [threading.Thread(target=fetch_node, args=(hc, nn), daemon=True)
                       for hc, nn in self.node_requests]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=15)

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
                logger.warning("Ошибки при сборе задач: %s", "; ".join(errors))
            try:
                self.signals.tasks_ready.emit(merged)
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
        import os, tempfile, subprocess
        vv_path = None
        try:
            try:
                proxmox = ProxmoxAPI(
                    self.host_cfg["host"],
                    user=self.host_cfg["user"],
                    token_name=self.host_cfg["token_name"],
                    token_value=self.host_cfg["token_value"],
                    verify_ssl=False,
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
                    err = "Недостаточно прав PVE для SPICE (требуется VM.Console)"
                elif "not supported" in msg or "spice" in msg:
                    err = "SPICE не поддерживается для этой ВМ"
                else:
                    err = f"Ошибка SPICE proxy: {e}"
                try:
                    self.signals.console_error.emit(err)
                except RuntimeError:
                    pass
                return

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
                    self.signals.console_error.emit(f"Ошибка записи .vv: {e}")
                except RuntimeError:
                    pass
                return

            try:
                proc = subprocess.Popen(
                    ["remote-viewer", vv_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
                )
                try:
                    _, stderr = proc.communicate(timeout=5)
                    if proc.returncode != 0:
                        err_text = stderr.decode("utf-8", errors="replace").strip()
                        logger.warning("remote-viewer exit code %d: %s", proc.returncode, err_text)
                        try:
                            self.signals.console_error.emit(
                                f"remote-viewer: {err_text or 'код ' + str(proc.returncode)}"
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
                    logger.info("remote-viewer запущен (pid=%d)", proc.pid)
                    # remote-viewer detached — следим за процессом в фоне,
                    # удалим .vv после его завершения
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
                    self.signals.console_error.emit(
                        "remote-viewer не найден. Установите пакет virt-viewer:\n"
                        "  apt install virt-viewer"
                    )
                except RuntimeError:
                    pass
                if vv_path and os.path.exists(vv_path):
                    try:
                        os.unlink(vv_path)
                    except OSError:
                        pass
                return

            try:
                self.signals.console_ready.emit("🖥 SPICE консоль запущена")
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
    """Создаёт QEMU VM через POST /nodes/{node}/qemu."""
    def __init__(self, host_cfg, node_name, params, ha_group=None):
        """
        params: dict с параметрами VM (name, cores, memory, sockets, ostype, etc.)
        ha_group: имя HA группы (опционально)
        """
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.params = params
        self.ha_group = ha_group
        self.signals = CreateVmSignals()

    def run(self):
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=False,
                timeout=30,
            )

            params = dict(self.params)
            # Если vmid не указан (0, None) — запрашиваем следующий свободный
            if not params.get("vmid"):
                try:
                    params["vmid"] = proxmox.cluster.nextid.get()
                except Exception:
                    try:
                        self.signals.vm_error.emit(
                            "Не удалось получить следующий свободный VMID от кластера"
                        )
                    except RuntimeError:
                        pass
                    return

            result = proxmox.nodes(self.node_name).qemu.post(**params)
            # POST /nodes/{node}/qemu возвращает UPID-строку, не {"data": {"vmid":...}}
            # vmid уже гарантированно есть в params (user-provided или nextid)
            vmid = params.get("vmid", "?")
            msg = f"VM {vmid} создана на {self.node_name}"

            # Добавление в HA группу
            if self.ha_group:
                try:
                    ha_params = {
                        "sid": f"vm:{vmid}",
                        "group": self.ha_group,
                    }
                    # Если пользователь снял галку «Запустить» — не даем HA стартовать VM
                    if not self.params.get("start"):
                        ha_params["state"] = "stopped"
                    proxmox.cluster.ha.resources.post(**ha_params)
                    msg += f", добавлена в HA «{self.ha_group}»"
                except Exception as ha_err:
                    msg += f", но ошибка HA: {ha_err}"

            try:
                self.signals.vm_created.emit(msg)
            except RuntimeError:
                pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.signals.vm_error.emit(str(e))
            except RuntimeError:
                pass
        finally:
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
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=False,
                timeout=30,
            )

            proxmox.nodes(self.node_name).qemu(self.vmid).delete(purge=1)
            msg = f"VM {self.vmid} удалена с {self.node_name}"
            try:
                self.signals.vm_deleted.emit(msg)
            except RuntimeError:
                pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.signals.vm_error.emit(str(e))
            except RuntimeError:
                pass
        finally:
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass
