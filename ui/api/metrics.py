import requests
import traceback
import urllib.parse
import concurrent.futures
import threading
from PySide6.QtCore import QRunnable, QObject, Signal
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _check_response(resp):
    """Проверяет HTTP-ответ и достаёт тело ошибки из PVE JSON."""
    if not resp.ok:
        try:
            body = resp.json()
            msg = body.get('data', {}).get('message', '') or body.get('message', '')
        except Exception:
            msg = ''
        raise Exception(f"HTTP {resp.status_code}: {msg or resp.reason}"[:500])

class MetricsSignals(QObject):
    # timeframe, vmid, metrics_dict
    data_fetched = Signal(str, int, dict)
    error_occurred = Signal(str)

class HostMetricsSignals(QObject):
    data_fetched = Signal(str, str, dict)  # timeframe, node_name, metrics_dict
    error_occurred = Signal(str)

class StorageMetricsWorker(QRunnable):
    """Загружает RRD-данные для хранилища (заполнение по времени)."""
    def __init__(self, host_cfg, node_name, storage_name, timeframe='hour'):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.storage_name = storage_name
        self.timeframe = timeframe
        self.signals = HostMetricsSignals()

    def run(self):
        session = requests.Session()
        try:
            session.verify = False
            auth_token = (
                f"PVEAPIToken={self.host_cfg['user']}!"
                f"{self.host_cfg['token_name']}={self.host_cfg['token_value']}"
            )
            headers = {"Authorization": auth_token}
            encoded_name = urllib.parse.quote(self.storage_name, safe='')
            url = (
                f"https://{self.host_cfg['host']}:8006/api2/json/"
                f"nodes/{self.node_name}/storage/{encoded_name}/rrddata"
            )
            params = {'timeframe': self.timeframe, 'cf': 'AVERAGE'}
            resp = session.get(url, headers=headers, params=params, timeout=10)
            _check_response(resp)
            rrd_response = resp.json()['data']

            metrics = {'usage': []}
            for entry in rrd_response:
                t = entry.get('time')
                val = entry.get('used')
                if t is not None and val is not None:
                    metrics['usage'].append({'time': t, 'value': val})
            try:
                self.signals.data_fetched.emit(self.timeframe, self.node_name, metrics)
            except RuntimeError:
                pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.signals.error_occurred.emit(str(e))
            except RuntimeError:
                pass
        finally:
            session.close()


class ContentListSignals(QObject):
    result = Signal(str, str, list)  # storage_name, content_type, list of vol dicts
    error = Signal(str, str, str)

class StorageContentListWorker(QRunnable):
    def __init__(self, host_cfg, node_name, storage_name, content_type):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.storage_name = storage_name
        self.content_type = content_type
        self.signals = ContentListSignals()

    def run(self):
        session = requests.Session()
        try:
            session.verify = False
            auth_token = (f"PVEAPIToken={self.host_cfg['user']}!{self.host_cfg['token_name']}={self.host_cfg['token_value']}")
            headers = {"Authorization": auth_token}
            encoded_name = urllib.parse.quote(self.storage_name, safe='')
            url = (f"https://{self.host_cfg['host']}:8006/api2/json/"
                   f"nodes/{self.node_name}/storage/{encoded_name}/content")
            resp = session.get(url, headers=headers, params={"content": self.content_type}, verify=False, timeout=60)
            _check_response(resp)
            data = resp.json().get('data', [])
            try:
                self.signals.result.emit(self.storage_name, self.content_type, data)
            except RuntimeError:
                pass
        except requests.exceptions.ReadTimeout:
            try:
                self.signals.error.emit(self.storage_name, self.content_type, "Таймаут PVE при загрузке содержимого хранилища")
            except RuntimeError:
                pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.signals.error.emit(self.storage_name, self.content_type, str(e))
            except RuntimeError:
                pass
        finally:
            session.close()


class BackupSignals(QObject):
    backups_ready = Signal(str, list)
    backups_error = Signal(str, str)

class StorageBackupWorker(QRunnable):
    def __init__(self, host_cfg, node_name, storage_name):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.storage_name = storage_name
        self.signals = BackupSignals()

    def run(self):
        session = requests.Session()
        try:
            session.verify = False
            auth_token = (f"PVEAPIToken={self.host_cfg['user']}!{self.host_cfg['token_name']}={self.host_cfg['token_value']}")
            headers = {"Authorization": auth_token}
            encoded_name = urllib.parse.quote(self.storage_name, safe='')
            url = (f"https://{self.host_cfg['host']}:8006/api2/json/"
                   f"nodes/{self.node_name}/storage/{encoded_name}/content")
            resp = session.get(url, headers=headers, params={"content": "backup"}, verify=False, timeout=10)
            _check_response(resp)
            data = resp.json().get('data', [])
            try:
                self.signals.backups_ready.emit(self.storage_name, data)
            except RuntimeError:
                pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.signals.backups_error.emit(self.storage_name, str(e))
            except RuntimeError:
                pass
        finally:
            session.close()


class NetworkSignals(QObject):
    network_ready = Signal(str, list)
    network_error = Signal(str, str)

class HostNetworkWorker(QRunnable):
    def __init__(self, host_cfg, node_name):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.signals = NetworkSignals()

    def run(self):
        session = requests.Session()
        try:
            session.verify = False
            auth_token = (
                f"PVEAPIToken={self.host_cfg['user']}!"
                f"{self.host_cfg['token_name']}={self.host_cfg['token_value']}"
            )
            headers = {"Authorization": auth_token}
            url = (f"https://{self.host_cfg['host']}:8006/api2/json/"
                   f"nodes/{self.node_name}/network")
            resp = session.get(url, headers=headers, verify=False, timeout=10)
            _check_response(resp)
            data = resp.json().get('data', [])
            try:
                self.signals.network_ready.emit(self.node_name, data)
            except RuntimeError:
                pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.signals.network_error.emit(self.node_name, str(e))
            except RuntimeError:
                pass
        finally:
            session.close()


class ServicesSignals(QObject):
    services_ready = Signal(str, list)
    services_error = Signal(str, str)

class HostServicesWorker(QRunnable):
    def __init__(self, host_cfg, node_name):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.signals = ServicesSignals()

    def run(self):
        session = requests.Session()
        try:
            session.verify = False
            auth_token = (
                f"PVEAPIToken={self.host_cfg['user']}!"
                f"{self.host_cfg['token_name']}={self.host_cfg['token_value']}"
            )
            headers = {"Authorization": auth_token}
            url = (f"https://{self.host_cfg['host']}:8006/api2/json/"
                   f"nodes/{self.node_name}/services")
            resp = session.get(url, headers=headers, verify=False, timeout=10)
            _check_response(resp)
            data = resp.json().get('data', [])
            try:
                self.signals.services_ready.emit(self.node_name, data)
            except RuntimeError:
                pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.signals.services_error.emit(self.node_name, str(e))
            except RuntimeError:
                pass
        finally:
            session.close()


class DisksSignals(QObject):
    disks_ready = Signal(str, list)
    disks_error = Signal(str, str)

class HostDisksWorker(QRunnable):
    def __init__(self, host_cfg, node_name):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.signals = DisksSignals()

    def run(self):
        session = requests.Session()
        try:
            session.verify = False
            auth_token = (
                f"PVEAPIToken={self.host_cfg['user']}!"
                f"{self.host_cfg['token_name']}={self.host_cfg['token_value']}"
            )
            headers = {"Authorization": auth_token}
            url = (f"https://{self.host_cfg['host']}:8006/api2/json/"
                   f"nodes/{self.node_name}/disks/list")
            resp = session.get(url, headers=headers, verify=False, timeout=10)
            _check_response(resp)
            data = resp.json().get('data', [])
            try:
                self.signals.disks_ready.emit(self.node_name, data)
            except RuntimeError:
                pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.signals.disks_error.emit(self.node_name, str(e))
            except RuntimeError:
                pass
        finally:
            session.close()


class SnapshotSignals(QObject):
    snapshots_ready = Signal(str, list)
    snapshots_error = Signal(str, str)

class HostSnapshotsWorker(QRunnable):
    def __init__(self, host_cfg, node_name, vms):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vms = vms
        self.signals = SnapshotSignals()

    def run(self):
        try:
            auth_token = (
                f"PVEAPIToken={self.host_cfg['user']}!"
                f"{self.host_cfg['token_name']}={self.host_cfg['token_value']}"
            )
            headers = {"Authorization": auth_token}
            base = f"https://{self.host_cfg['host']}:8006/api2/json"
            all_snapshots = []
            lock = threading.Lock()

            def fetch_vm_snapshots(vm):
                vmid = vm.get("vmid")
                vm_type = vm.get("type", "qemu")
                vm_name = vm.get("name", "")
                if not vmid:
                    return
                s = requests.Session()
                try:
                    s.verify = False
                    enc_node = urllib.parse.quote(self.node_name, safe="")
                    url = f"{base}/nodes/{enc_node}/{vm_type}/{vmid}/snapshot"
                    r = s.get(url, headers=headers, verify=False, timeout=10)
                    _check_response(r)
                    data = r.json().get("data", [])
                    for snap in data:
                        if snap.get("name") == "current":
                            continue
                        snap["vmid"] = vmid
                        snap["vm_name"] = vm_name
                        with lock:
                            all_snapshots.append(dict(snap))
                except Exception:
                    pass
                finally:
                    s.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                executor.map(fetch_vm_snapshots, self.vms)

            all_snapshots.sort(key=lambda s: (s.get("vmid", 0), s.get("snaptime", 0) or 0))
            try:
                self.signals.snapshots_ready.emit(self.node_name, all_snapshots)
            except RuntimeError:
                pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.signals.snapshots_error.emit(self.node_name, str(e))
            except RuntimeError:
                pass


class DiskSignals(QObject):
    disks_ready = Signal(str, list)
    disks_error = Signal(str, str)

class StorageDisksWorker(QRunnable):
    """Собирает диски ВМ на указанном storage из VM configs (параллельно)."""
    def __init__(self, host_cfg, node_name, storage_name, all_vms):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.storage_name = storage_name
        self.all_vms = all_vms
        self.signals = DiskSignals()

    def run(self):
        try:
            auth_token = (
                f"PVEAPIToken={self.host_cfg['user']}!"
                f"{self.host_cfg['token_name']}={self.host_cfg['token_value']}"
            )
            headers = {"Authorization": auth_token}
            base = f"https://{self.host_cfg['host']}:8006/api2/json"
            prefix = self.storage_name + ":"
            disks = []
            lock = threading.Lock()

            def fetch_vm_config(vm):
                vmid = vm.get("vmid")
                vm_node = vm.get("node")
                if not vmid or not vm_node:
                    return
                s = requests.Session()
                try:
                    s.verify = False
                    enc_node = urllib.parse.quote(vm_node, safe="")
                    vm_type = vm.get("type", "qemu")
                    r = s.get(
                        f"{base}/nodes/{enc_node}/{vm_type}/{vmid}/config",
                        headers=headers, verify=False, timeout=10
                    )
                    _check_response(r)
                    config = r.json().get("data", {})
                    vm_name = vm.get("name", "")

                    for key, val in config.items():
                        val_str = str(val)
                        if ":" in val_str and val_str.startswith(prefix):
                            # Пропускаем CDROM (ISO образы)
                            if "media=cdrom" in val_str:
                                continue
                            volpath = val_str.split(",")[0]
                            volparts = volpath.split(":", 1)
                            if len(volparts) == 2:
                                volid = volparts[1]
                                size_bytes = 0
                                for part in str(val).split(","):
                                    part = part.strip()
                                    if part.startswith("size="):
                                        size_str = part.split("=", 1)[1]
                                        size_bytes = self._parse_size(size_str)
                                        break
                                with lock:
                                    disks.append({
                                        "vmid": vmid,
                                        "vm_name": vm_name,
                                        "volid": f"{self.storage_name}:{volid}",
                                        "bus": key,
                                        "size": size_bytes
                                    })
                except Exception:
                    pass
                finally:
                    s.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                executor.map(fetch_vm_config, self.all_vms)

            try:
                self.signals.disks_ready.emit(self.storage_name, disks)
            except RuntimeError:
                pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.signals.disks_error.emit(self.storage_name, str(e))
            except RuntimeError:
                pass

    @staticmethod
    def _parse_size(size_str):
        """Parse PVE size string like '32G', '512M', '1T' to bytes."""
        size_str = str(size_str).strip().upper()
        if size_str.endswith("T"):
            return int(float(size_str[:-1]) * 1024**4)
        elif size_str.endswith("G"):
            return int(float(size_str[:-1]) * 1024**3)
        elif size_str.endswith("M"):
            return int(float(size_str[:-1]) * 1024**2)
        elif size_str.endswith("K"):
            return int(float(size_str[:-1]) * 1024)
        else:
            try:
                return int(float(size_str))
            except ValueError:
                return 0


class HostMetricsWorker(QRunnable):
    """Загружает RRD-данные для узла Proxmox (ЦП, RAM, сеть)."""
    def __init__(self, host_cfg, node_name, timeframe='hour'):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.timeframe = timeframe
        self.signals = HostMetricsSignals()

    def run(self):
        session = requests.Session()
        try:
            session.verify = False
            auth_token = (
                f"PVEAPIToken={self.host_cfg['user']}!"
                f"{self.host_cfg['token_name']}={self.host_cfg['token_value']}"
            )
            headers = {"Authorization": auth_token}
            url = (
                f"https://{self.host_cfg['host']}:8006/api2/json/"
                f"nodes/{self.node_name}/rrddata"
            )
            params = {'timeframe': self.timeframe, 'cf': 'AVERAGE'}
            resp = session.get(url, headers=headers, params=params, timeout=10)
            _check_response(resp)
            rrd_response = resp.json()['data']

            metrics = {
                'cpu': [],
                'mem': [],
                'netin': [],
                'netout': [],
            }
            for entry in rrd_response:
                t = entry['time']
                for key in metrics.keys():
                    field = 'memused' if key == 'mem' else key
                    if field in entry and entry[field] is not None:
                        metrics[key].append({'time': t, 'value': entry[field]})
                    elif key in ('netin', 'netout') and 'net' in entry and entry['net'] is not None:
                        metrics[key].append({'time': t, 'value': entry['net'] / 2})
            try:
                self.signals.data_fetched.emit(self.timeframe, self.node_name, metrics)
            except RuntimeError:
                pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.signals.error_occurred.emit(str(e))
            except RuntimeError:
                pass
        finally:
            session.close()


class MetricsWorker(QRunnable):
    """Загружает RRD-данные для ВМ/CT (ЦП, RAM, сеть, диск)."""
    def __init__(self, host_cfg, node_name, vmid, vm_type='qemu', timeframe='hour'):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.timeframe = timeframe
        self.signals = MetricsSignals()

    def run(self):
        session = requests.Session()
        try:
            session.verify = False
            auth_token = (
                f"PVEAPIToken={self.host_cfg['user']}!"
                f"{self.host_cfg['token_name']}={self.host_cfg['token_value']}"
            )
            headers = {"Authorization": auth_token}
            url = (
                f"https://{self.host_cfg['host']}:8006/api2/json/"
                f"nodes/{self.node_name}/{self.vm_type}/{self.vmid}/rrddata"
            )
            params = {'timeframe': self.timeframe, 'cf': 'AVERAGE'}
            resp = session.get(url, headers=headers, params=params, timeout=10)
            _check_response(resp)
            rrd_response = resp.json()['data']

            metrics = {
                'cpu': [],
                'mem': [],
                'netin': [],
                'netout': [],
                'diskread': [],
                'diskwrite': []
            }
            for entry in rrd_response:
                t = entry['time']
                for key in metrics.keys():
                    if key in entry and entry[key] is not None:
                        metrics[key].append({'time': t, 'value': entry[key]})
            try:
                self.signals.data_fetched.emit(self.timeframe, self.vmid, metrics)
            except RuntimeError:
                pass
        except Exception as e:
            traceback.print_exc()
            try:
                self.signals.error_occurred.emit(str(e))
            except RuntimeError:
                pass
        finally:
            session.close()
