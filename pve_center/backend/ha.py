"""HA resources: list, add, delete."""

import logging

from PySide6.QtCore import QObject, QRunnable, Signal

from ..domain.ha_resource import HaResource
from ..plugins import create_provider
from ..ui.i18n import tr
from .core import _safe_emit, _sanitize_error

logger = logging.getLogger(__name__)

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
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            cluster_api = provider.cluster
            data = cluster_api.list_ha_resources()
            resources = [HaResource.from_pve(r) for r in data]
            _safe_emit(self.signals.ha_resources_ready, resources)
        except Exception as e:
            logger.debug("HA resources error: %s", e)
            _safe_emit(self.signals.ha_resources_error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
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
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            cluster_api = provider.cluster
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
            if provider:
                provider.close()
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
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            cluster_api = provider.cluster
            cluster_api.delete_ha_resource(self.sid)
            _safe_emit(self.signals.result,
                       tr("{sid} removed from HA").format(sid=self.sid))
        except Exception as e:
            logger.debug("HA resource delete error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)

# ----------------------------------------------------------------------
# Network CRUD workers — /nodes/{node}/network
# ----------------------------------------------------------------------
