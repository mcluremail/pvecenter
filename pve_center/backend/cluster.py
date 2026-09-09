"""Cluster-level workers: task collection, status, backup jobs."""

import logging
import threading

from PySide6.QtCore import QObject, QRunnable, Signal

from ..domain.cluster import ClusterStatus
from ..domain.task import Task
from ..plugins import create_provider
from ..ui.i18n import tr
from .core import _safe_emit, _sanitize_error

logger = logging.getLogger(__name__)

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
                provider = None
                try:
                    provider = create_provider(host_cfg, timeout=10)
                    task_api = provider.tasks
                    tasks = task_api.list(node_name, limit=100)
                    with lock:
                        results[node_name] = tasks
                except Exception as e:
                    with lock:
                        errors.append(f"{node_name}: {e}")
                finally:
                    if provider:
                        provider.close()

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
                merged = [Task.from_pve(x)
                          for x in sorted(all_by_upid.values(),
                                          key=lambda x: float(x.get("starttime", 0) or 0),
                                          reverse=True)]
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
class ClusterStatusSignals(QObject):
    cluster_status_ready = Signal(object)
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
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=self.timeout)
            cluster_api = provider.cluster
            status = cluster_api.get_status()
            corosync_nodes = []
            try:
                corosync_nodes = cluster_api.get_config_nodes()
            except Exception:
                pass
            result = ClusterStatus.from_pve(status, corosync_nodes)
            _safe_emit(self.signals.cluster_status_ready, result)
        except Exception as e:
            logger.debug("cluster status error: %s", e)
            _safe_emit(self.signals.cluster_status_error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)

# ----------------------------------------------------------------------
# MigrateVmWorker — migrate VM within cluster
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
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            cluster_api = provider.cluster
            jobs = cluster_api.list_all_jobs(pve_major=self.pve_major)
            _safe_emit(self.signals.jobs_ready, jobs)
        except Exception as e:
            logger.debug("cluster jobs error: %s", e)
            _safe_emit(self.signals.jobs_error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
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
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            cluster_api = provider.cluster
            cluster_api.create_backup_job(self.params, pve_major=self.pve_major)
            _safe_emit(self.signals.result, tr("Backup job created"))
        except Exception as e:
            logger.debug("job create error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
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
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            cluster_api = provider.cluster
            cluster_api.update_backup_job(self.job_id, self.params, pve_major=self.pve_major)
            _safe_emit(self.signals.result, tr("Backup job updated"))
        except Exception as e:
            logger.debug("job update error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
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
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            cluster_api = provider.cluster
            cluster_api.delete_backup_job(self.job_id, pve_major=self.pve_major)
            _safe_emit(self.signals.result, tr("Backup job deleted"))
        except Exception as e:
            logger.debug("job delete error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)

# ----------------------------------------------------------------------
# Access Management — Users
# ----------------------------------------------------------------------
