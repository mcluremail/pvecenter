import urllib3
import traceback
import secrets
import string
from PySide6.QtCore import Signal, QRunnable, QObject
from proxmoxer import ProxmoxAPI

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ----------------------------------------------------------------------
# Создание API токена через парольную аутентификацию
# ----------------------------------------------------------------------
def create_pve_token(host, user, password):
    """Создаёт API-токен на PVE-хосте.

    Возвращает dict с полями token_name, token_value или dict с полем error.
    """
    try:
        proxmox = ProxmoxAPI(host, user=user, password=password, verify_ssl=False, timeout=15)
        token_id = "dashboard-" + "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
        result = proxmox.access.users(user).token(token_id).post(
            comment="PVE Center dashboard",
            expire=0,
        )
        # proxmoxer возвращает dict с value внутри data
        data = result.get("data", result)
        if isinstance(data, dict) and "value" in data:
            return {"token_name": token_id, "token_value": data["value"]}
        # fallback — если результат пришёл иначе
        return {"token_name": token_id, "token_value": data.get("tokenid", "")}
    except Exception as e:
        msg = str(e)
        if "authorization" in msg.lower() or "permission" in msg.lower() or "401" in msg:
            return {"error": "Неверный логин или пароль"}
        if "connection" in msg.lower() or "timeout" in msg.lower() or "resolve" in msg.lower():
            return {"error": f"Не удалось подключиться к {host}"}
        return {"error": msg}


def test_ticket_auth(host, user, password):
    """Проверяет парольную аутентификацию. Возвращает True/False + сообщение."""
    try:
        proxmox = ProxmoxAPI(host, user=user, password=password, verify_ssl=False, timeout=10)
        proxmox.version.get()
        return True, ""
    except Exception as e:
        return False, str(e)


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
                node_name = self.node_cfg["name"]
                node_status = proxmox.nodes(node_name).status.get()
                nodes = [{**node_status, "node": node_name, "status": "online"}]
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
