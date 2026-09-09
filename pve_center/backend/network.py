"""Node network interface CRUD and apply/revert."""

import logging

from PySide6.QtCore import QObject, QRunnable, Signal

from ..plugins import create_provider
from ..ui.i18n import tr
from .core import _safe_emit, _sanitize_error

logger = logging.getLogger(__name__)

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
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            node_api = provider.nodes
            node_api.create_network(self.node_name, **self.params)
            iface = self.params.get("iface", "")
            _safe_emit(self.signals.result,
                       tr("Network interface {iface} created").format(iface=iface))
        except Exception as e:
            logger.debug("network create error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
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
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            node_api = provider.nodes
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
            if provider:
                provider.close()
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
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            node_api = provider.nodes
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
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)
class NetworkApplyWorker(QRunnable):
    """PUT /nodes/{node}/network — apply pending network changes."""
    def __init__(self, host_cfg, node_name):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.signals = NetworkCrudSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=30)
            node_api = provider.nodes
            node_api.apply_network(self.node_name)
            _safe_emit(self.signals.result, tr("Network changes applied"))
        except Exception as e:
            logger.debug("network apply error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)
class NetworkRevertWorker(QRunnable):
    """DELETE /nodes/{node}/network — revert pending network changes."""
    def __init__(self, host_cfg, node_name):
        super().__init__()
        self.host_cfg = host_cfg
        self.node_name = node_name
        self.signals = NetworkCrudSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            node_api = provider.nodes
            node_api.revert_network(self.node_name)
            _safe_emit(self.signals.result, tr("Network changes reverted"))
        except Exception as e:
            logger.debug("network revert error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)

# ----------------------------------------------------------------------
# ClusterStatusWorker — GET /cluster/status + GET /cluster/config/nodes
# ----------------------------------------------------------------------
