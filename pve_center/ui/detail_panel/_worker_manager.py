from PySide6.QtCore import QThreadPool

from ._constants import _MAX_WORKERS_DP


class WorkerManager:
    def __init__(self):
        self._workers = set()
        self.current_worker = None
        self.current_config_worker = None
        self.current_hist_worker = None
        self.current_snap_worker = None
        self.current_host_workers = set()

    def run_worker(self, worker):
        if len(self._workers) >= _MAX_WORKERS_DP:
            return
        self._workers.add(worker)
        worker.signals.finished.connect(lambda w=worker: self.discard_worker(w))
        QThreadPool.globalInstance().start(worker)

    def run_host_worker(self, worker):
        """Run a host-detail worker that is tracked for cancellation on tab switch."""
        if len(self._workers) >= _MAX_WORKERS_DP:
            return
        self._workers.add(worker)
        self.current_host_workers.add(worker)
        worker.signals.finished.connect(
            lambda w=worker: (self.discard_worker(w), self.current_host_workers.discard(w))
        )
        QThreadPool.globalInstance().start(worker)

    def discard_worker(self, worker):
        self._workers.discard(worker)

    def cancel_detail_worker(self):
        if self.current_worker:
            self.discard_worker(self.current_worker)
            try: self.current_worker.signals.detail_ready.disconnect()
            except RuntimeError: pass
            self.current_worker = None

    def cancel_config_worker(self):
        if self.current_config_worker:
            self.discard_worker(self.current_config_worker)
            try: self.current_config_worker.signals.config_ready.disconnect()
            except RuntimeError: pass
            try: self.current_config_worker.signals.config_error.disconnect()
            except RuntimeError: pass
            self.current_config_worker = None

    def cancel_history_worker(self):
        if self.current_hist_worker:
            self.discard_worker(self.current_hist_worker)
            try: self.current_hist_worker.signals.tasks_ready.disconnect()
            except RuntimeError: pass
            try: self.current_hist_worker.signals.tasks_error.disconnect()
            except RuntimeError: pass
            self.current_hist_worker = None

    def cancel_snapshots_worker(self):
        if self.current_snap_worker:
            self.discard_worker(self.current_snap_worker)
            try: self.current_snap_worker.signals.snapshots_ready.disconnect()
            except RuntimeError: pass
            try: self.current_snap_worker.signals.snapshots_error.disconnect()
            except RuntimeError: pass
            self.current_snap_worker = None

    def cancel_host_workers(self):
        """Discard all host-detail workers from the pool tracking so new
        workers can be scheduled.  Running workers keep going but their
        results are dropped by the tab-type guard in the result slots."""
        for w in list(self.current_host_workers):
            self.discard_worker(w)
        self.current_host_workers.clear()
