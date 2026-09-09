"""Console workers: VNC (websocket ticket) and SPICE."""

import logging
import os
import threading

from PySide6.QtCore import QObject, QRunnable, Signal

from ..plugins import create_provider
from ..ui.i18n import tr
from .core import PVE_PORT, _cleanup_vv

logger = logging.getLogger(__name__)

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
        ticket = config.get("password") or config.get("ticket")
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
        import subprocess
        import sys
        import tempfile
        vv_path = None
        provider = None
        used_vnc = False
        try:
            try:
                provider = create_provider(self.host_cfg, timeout=10)
                vm_api = provider.vms
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
                if provider:
                    provider.close()
                    provider = None

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
# NoVncWorker — встроенная noVNC-консоль (websocket)
# ----------------------------------------------------------------------
class NoVncSignals(QObject):
    ready = Signal(str, str)  # ws_url, vnc ticket (RFB password)
    error = Signal(str)
    finished = Signal()
class NoVncWorker(QRunnable):
    """Готовит параметры для встроенной noVNC-консоли.

    POST vncproxy → GET vncwebsocket (валидация vncticket) → ws_url.
    Подключение выполняет WsBridge в UI-потоке окна консоли.
    """
    def __init__(self, host_cfg, node_name, vmid, vm_type="qemu"):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.vmid = vmid
        self.vm_type = vm_type
        self.signals = NoVncSignals()

    @staticmethod
    def build_ws_url(host, node, vmid, vm_type, port, ticket):
        """Строит wss:// URL websocket-эндпоинта PVE (порт API 8006)."""
        from urllib.parse import quote
        return (
            f"wss://{quote(host, safe='')}:{PVE_PORT}"
            f"/api2/json/nodes/{quote(str(node), safe='')}"
            f"/{vm_type}/{quote(str(vmid), safe='')}"
            f"/vncwebsocket?port={int(port)}"
            f"&vncticket={quote(ticket, safe='')}"
        )

    @staticmethod
    def extract_ticket(config):
        """VNCTicket из ответа vncproxy: password (патченные 8.4.19+/9.1.9+)
        или ticket (PVE 7/старые)."""
        return config.get("password") or config.get("ticket") or ""

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=10)
            vm_api = provider.vms
            try:
                config = vm_api.get_vnc_proxy(
                    self.node_name, self.vmid, self.vm_type
                )
            except Exception as e:
                raise RuntimeError(f"vncproxy: {e}") from e
            port = int(config.get("port", 0))
            ticket = self.extract_ticket(config)
            if not port or not ticket:
                raise ValueError(tr("VNC proxy returned no port/ticket"))
            # Валидирует vncticket и «взводит» websocket-эндпоинт на сервере.
            try:
                vm_api.get_vnc_websocket(
                    self.node_name, self.vmid, self.vm_type, port, ticket
                )
            except Exception as e:
                raise RuntimeError(f"vncwebsocket: {e}") from e
            ws_url = self.build_ws_url(
                self.host_cfg["host"], self.node_name, self.vmid,
                self.vm_type, port, ticket
            )
            try:
                self.signals.ready.emit(ws_url, ticket)
            except RuntimeError:
                pass
        except Exception as e:
            msg = str(e).lower()
            if "permission check failed" in msg or "403" in msg:
                err = tr("PVE permission denied for console (requires VM.Console)")
            elif "not supported" in msg or "vnc" in msg:
                err = tr("Console not supported for this VM")
            else:
                err = tr("Console proxy error: {}").format(e)
            try:
                self.signals.error.emit(err)
            except RuntimeError:
                pass
        finally:
            if provider:
                provider.close()
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass

# ----------------------------------------------------------------------
# CreateVmWorker — создание VM
# ----------------------------------------------------------------------
