import urllib3
import traceback
from PySide6.QtCore import Signal, QRunnable, QObject
from proxmoxer import ProxmoxAPI

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _domain_from_host(host):
    """Возвращает домен из FQDN (pve01.ros.linru.grp → ros.linru.grp)."""
    parts = host.split(".", 1)
    return parts[1] if len(parts) > 1 else None


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
    """Создаёт локального PVE-юзера `pvecenter@pve` с ролью Administrator
    на `/` и генерирует API-токен для него.

    Использует прямые HTTP-запросы (без Proxmoxer), чтобы избежать
    проблем с маппингом HTTP-методов.

    Аргументы:
        host: адрес PVE-хоста
        user: существующий пользователь с правами на создание пользователей/ACL
        password: его пароль

    Возвращает dict с полями token_name, token_value, user
    или dict с полем error.
    """
    import requests as rq
    import secrets as sec
    import string as str_mod

    service_user = "pvecenter@pve"

    try:
        ticket_data = _pve_ticket_auth(host, user, password)
        ticket = ticket_data["ticket"]
        csrf = ticket_data["csrf"]
        cookie_token = f"PVEAuthCookie={ticket}"
        sess = rq.Session()
        sess.verify = False
        sess.headers.update({"Cookie": cookie_token, "CSRFPreventionToken": csrf})

        users = sess.get(
            f"https://{host}:{PVE_PORT}/api2/json/access/users",
            timeout=15
        ).json().get("data", [])
        existing = {u.get("userid") for u in users}

        if service_user not in existing:
            pwd = "".join(sec.choice(str_mod.ascii_letters + str_mod.digits) for _ in range(24))
            r = sess.post(
                f"https://{host}:{PVE_PORT}/api2/json/access/users",
                data={"userid": service_user, "password": pwd,
                       "comment": "PVE Center service user (auto-created)", "enable": 1},
                timeout=15,
            )
            if r.status_code >= 400:
                print(f"[create_user] {r.status_code}: {r.text[:200]}")

        acls = sess.get(
            f"https://{host}:{PVE_PORT}/api2/json/access/acl",
            timeout=15
        ).json().get("data", [])
        has_admin_acl = any(
            a.get("path") == "/"
            and service_user in (a.get("users") or a.get("ugid") or "")
            for a in acls
        )

        if not has_admin_acl:
            r = sess.post(
                f"https://{host}:{PVE_PORT}/api2/json/access/acl",
                data={"path": "/", "roles": "Administrator", "users": service_user},
                timeout=15,
            )
            if r.status_code >= 400:
                print(f"[acl_put] {r.status_code}: {r.text[:200]}")
            else:
                print(f"[acl_put] OK — Administrator granted to {service_user} on /")

        token_id = "pvecenter-" + "".join(
            sec.choice(str_mod.ascii_lowercase + str_mod.digits) for _ in range(6)
        )
        r = sess.put(
            f"https://{host}:{PVE_PORT}/api2/json/access/users/{service_user}/token/{token_id}",
            data={"comment": "PVE Center dashboard", "expire": 0, "privsep": 0},
            timeout=15,
        )
        print(f"[token_create] HTTP {r.status_code}")
        if r.status_code >= 400:
            print(f"[token_create] error: {r.text[:300]}")
            return {"error": f"Ошибка создания токена: {r.status_code}"}
        data = r.json().get("data", r.json())
        print(f"[token_create] response data: {data}")
        token_value = ""
        if isinstance(data, dict) and "value" in data:
            token_value = data["value"]
        elif isinstance(data, dict) and data.get("tokenid"):
            token_value = data.get("tokenid", "")

        if not token_value:
            return {"error": "Пустое значение токена в ответе сервера"}

        auth_header = f"PVEAPIToken={service_user}!{token_id}={token_value}"

        # Верификация: пробуем получить список нод этим токеном
        try:
            vr = rq.get(
                f"https://{host}:{PVE_PORT}/api2/json/cluster/resources",
                headers={"Authorization": auth_header},
                verify=False, timeout=10,
            )
            print(f"[verify] /cluster/resources HTTP {vr.status_code}")
            if vr.status_code == 200:
                print("[verify] OK — token works")
            else:
                print(f"[verify] FAILED: {vr.text[:200]}")
                return {"error": f"Токен создан, но не работает: {vr.status_code}"}
        except Exception as ve:
            print(f"[verify] exception: {ve}")

        return {"token_name": token_id, "token_value": token_value,
                "user": service_user}

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
class FetchSignals(QObject):
    result_ready = Signal(dict)


class FetchWorker(QRunnable):
    """Загружает сводку по узлу через QThreadPool."""
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
                timeout=10
            )

            vmid_to_pool = {}
            try:
                pools_data = proxmox.pools.get()
                for p in pools_data:
                    pool_name = p.get("poolid") or p.get("pool")
                    if not pool_name:
                        continue
                    members = p.get("members")
                    if not isinstance(members, list):
                        continue
                    for member in members:
                        m_type = member.get("type")
                        m_vmid = member.get("vmid")
                        if m_type in ("qemu", "lxc") and m_vmid is not None:
                            vmid_to_pool[int(m_vmid)] = pool_name
            except Exception:
                traceback.print_exc()

            is_cluster_rep = self.node_cfg.get("cluster_rep", False)

            storages = []
            if is_cluster_rep:
                resources = proxmox.cluster.resources.get()
                nodes = [r for r in resources if r["type"] == "node"]
                vms = [r for r in resources if r["type"] in ("qemu", "lxc")]
                storages = [r for r in resources if r.get("type") == "storage"]
                cluster_name = self.node_cfg.get("cluster", "")
                domain = _domain_from_host(self.node_cfg["host"])
                for n in nodes:
                    short = n["node"]
                    if domain:
                        n["_display_name"] = f"{short}.{domain}"
                    else:
                        n["_display_name"] = short
                for s in storages:
                    s["host_name"] = self.node_cfg["name"]
                    s["cluster"] = cluster_name

                # Подтягиваем used/total с каждой ноды
                detail_by_node = {}
                for n in nodes:
                    node_name = n["node"]
                    try:
                        node_storages = proxmox.nodes(node_name).storage.get()
                        detail_by_node[node_name] = {
                            ds["storage"]: ds for ds in node_storages
                        }
                    except Exception:
                        detail_by_node[node_name] = {}
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
                # Получаем реальное короткое имя ноды с сервера (для API-запросов,
                # чтобы избежать proxy loop в pveproxy)
                try:
                    local_nodes = proxmox.nodes.get()
                    real_node_name = local_nodes[0]["node"] if local_nodes else self.node_cfg["name"]
                except Exception:
                    real_node_name = self.node_cfg["name"]
                node_name = real_node_name
                node_status = proxmox.nodes(node_name).status.get()
                nodes = [{**node_status, "node": node_name,
                          "_display_name": self.node_cfg["name"],
                          "status": "online"}]
                qemu_list = proxmox.nodes(node_name).qemu.get()
                lxc_list = proxmox.nodes(node_name).lxc.get()
                vms = []
                for v in qemu_list:
                    vms.append({**v, "type": "qemu",
                                "node": node_name,
                                "pool": vmid_to_pool.get(v["vmid"])})
                for v in lxc_list:
                    vms.append({**v, "type": "lxc",
                                "node": node_name,
                                "pool": vmid_to_pool.get(v["vmid"])})
                storages = list(proxmox.nodes(node_name).storage.get())
                for st in storages:
                    st["node"] = node_name
                    st["host_name"] = self.node_cfg["name"]

            self.signals.result_ready.emit({
                "host": self.node_cfg["name"],
                "status": "ok",
                "nodes": nodes,
                "vms": vms,
                "storages": storages
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


# ----------------------------------------------------------------------
# VmDetailWorker (остаётся без изменений)
# ----------------------------------------------------------------------
class VmDetailSignals(QObject):
    detail_ready = Signal(dict)


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


# ----------------------------------------------------------------------
# VmConfigWorker
# ----------------------------------------------------------------------
class VmConfigSignals(QObject):
    config_ready = Signal(int, dict)
    config_error = Signal(int, str)


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


# ----------------------------------------------------------------------
# VmTaskHistoryWorker (добавлен заново)
# ----------------------------------------------------------------------
class VmTaskHistorySignals(QObject):
    tasks_ready = Signal(int, list)   # vmid, список задач
    tasks_error = Signal(int, str)


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


# ----------------------------------------------------------------------
# ClusterTasksWorker
# ----------------------------------------------------------------------
class ClusterTasksSignals(QObject):
    tasks_ready = Signal(list)
    tasks_error = Signal(str)


class ClusterTasksWorker(QRunnable):
    """Загружает последние задачи кластера через QThreadPool."""
    def __init__(self, host_cfg):
        super().__init__()
        self.host_cfg = host_cfg
        self.signals = ClusterTasksSignals()

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
            tasks = proxmox.cluster.tasks.get()
            try:
                self.signals.tasks_ready.emit(tasks)
            except RuntimeError:
                pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.signals.tasks_error.emit(str(e))
            except RuntimeError:
                pass
