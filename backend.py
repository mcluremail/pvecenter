import urllib3
import traceback
import logging
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

        data = r.json().get("data", r.json())
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
                timeout=15
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
                for n in nodes:
                    short = n["node"]
                    n["_display_name"] = f"{short}@{cluster_name}" if cluster_name else short
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


# ----------------------------------------------------------------------
# Удаление токена с сервера
# ----------------------------------------------------------------------
def delete_host_token(host_cfg):
    """Удаляет API-токен с PVE-сервера через Proxmoxer.
       Не выбрасывает исключения — ошибки только в лог."""
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
    except Exception as e:
        logger.warning("Failed to delete token from %s: %s", host_cfg.get("host", "?"), e)


# ----------------------------------------------------------------------
# VmTaskHistoryWorker
# ----------------------------------------------------------------------
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


class VmActionSignals(QObject):
    action_result = Signal(str)
    action_error = Signal(str)


class VmActionWorker(QRunnable):
    def __init__(self, host_cfg, node_name, vmid, vm_type, action):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.action = action
        self.signals = VmActionSignals()
        self.ACTION_NAMES = {
            "start": "Запуск",
            "shutdown": "Выключение",
            "stop": "Принудительное выключение",
            "reboot": "Перезагрузка",
            "reset": "Сброс",
        }

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


# ----------------------------------------------------------------------
# ClusterTasksWorker
# ----------------------------------------------------------------------
class ClusterTasksSignals(QObject):
    tasks_ready = Signal(list)
    tasks_error = Signal(str)


class ClusterTasksWorker(QRunnable):
    """Загружает задачи со всех нод через QThreadPool.
    Принимает список (host_cfg, node_name) — для каждой ноды
    вызывается /nodes/{node}/tasks, результаты мержатся по UPID."""
    def __init__(self, node_requests):
        super().__init__()
        self.node_requests = node_requests  # list of (host_cfg, node_name)
        self.signals = ClusterTasksSignals()

    def run(self):
        import logging
        log = logging.getLogger(__name__)
        all_by_upid = {}
        errors = []
        for host_cfg, node_name in self.node_requests:
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
                for t in tasks:
                    upid = t.get("upid")
                    if upid:
                        all_by_upid[upid] = t
                    else:
                        all_by_upid[id(t)] = t
            except Exception as e:
                errors.append(f"{node_name}: {e}")
                continue
        merged = sorted(all_by_upid.values(),
                        key=lambda x: float(x.get("starttime", 0) or 0),
                        reverse=True)
        if errors:
            log.warning("Ошибки при сборе задач: %s", "; ".join(errors))
        try:
            self.signals.tasks_ready.emit(merged)
        except RuntimeError:
            pass


# ----------------------------------------------------------------------
# VmConsoleWorker (SPICE)
# ----------------------------------------------------------------------
class VmConsoleSignals(QObject):
    console_ready = Signal(str)
    console_error = Signal(str)


class VmConsoleWorker(QRunnable):
    """Запрашивает SPICE proxy у PVE, пишет .vv файл и запускает remote-viewer."""
    def __init__(self, host_cfg, node_name, vmid):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.signals = VmConsoleSignals()

    def run(self):
        import os, tempfile, subprocess
        log = logging.getLogger(__name__)
        try:
            proxmox = ProxmoxAPI(
                self.host_cfg["host"],
                user=self.host_cfg["user"],
                token_name=self.host_cfg["token_name"],
                token_value=self.host_cfg["token_value"],
                verify_ssl=False,
                timeout=10
            )
            config = proxmox.nodes(self.node_name).qemu(self.vmid).spiceproxy.post()
        except Exception as e:
            msg = str(e).lower()
            if "not supported" in msg or "spice" in msg:
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

            fd, path = tempfile.mkstemp(suffix=".vv", prefix="pve_")
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
                ["remote-viewer", path],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
            try:
                _, stderr = proc.communicate(timeout=5)
                if proc.returncode != 0:
                    err_text = stderr.decode("utf-8", errors="replace").strip()
                    log.warning("remote-viewer exit code %d: %s", proc.returncode, err_text)
                    try:
                        self.signals.console_error.emit(
                            f"remote-viewer: {err_text or 'код ' + str(proc.returncode)}"
                        )
                    except RuntimeError:
                        pass
                    return
            except subprocess.TimeoutExpired:
                log.info("remote-viewer запущен (pid=%d)", proc.pid)
        except FileNotFoundError:
            try:
                self.signals.console_error.emit(
                    "remote-viewer не найден. Установите пакет virt-viewer:\n"
                    "  apt install virt-viewer"
                )
            except RuntimeError:
                pass
            return

        try:
            self.signals.console_ready.emit("🖥 SPICE консоль запущена")
        except RuntimeError:
            pass


# ----------------------------------------------------------------------
# VNC browser console (noVNC)
# ----------------------------------------------------------------------
def open_browser_console(host, node, vmid, vmname=""):
    """Открывает noVNC консоль ВМ в браузере через PVE web UI.

    Пользователь должен быть авторизован в PVE web UI в браузере.
    """
    import webbrowser
    params = f"console=kvm&novnc=1&vmid={vmid}&node={node}&resize=off&cmd="
    if vmname:
        params += f"&vmname={vmname}"
    url = f"https://{host}:8006/?{params}"
    log.info("noVNC: %s", url)
    webbrowser.open(url)
