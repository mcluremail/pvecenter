"""Tests for WorkerManager queueing instead of silently dropping workers."""
import pytest

import pve_center.ui.detail_panel._worker_manager as wmod
from pve_center.ui.detail_panel._constants import _MAX_WORKERS_DP
from pve_center.ui.detail_panel._worker_manager import WorkerManager


class _FakePool:
    def __init__(self):
        self.started = []

    def start(self, worker):
        self.started.append(worker)


@pytest.fixture
def pool(monkeypatch):
    fake = _FakePool()
    monkeypatch.setattr(wmod.QThreadPool, "globalInstance", staticmethod(lambda: fake))
    return fake


def _worker():
    from unittest.mock import MagicMock

    w = MagicMock()
    w.signals.finished.connect = MagicMock()
    return w


def test_worker_starts(pool):
    wm = WorkerManager()
    w = _worker()
    wm.run_worker(w)
    assert pool.started == [w]
    assert w in wm._workers


def test_pool_full_queues_then_starts_on_free(pool):
    wm = WorkerManager()
    workers = [_worker() for _ in range(_MAX_WORKERS_DP)]
    for w in workers:
        wm.run_worker(w)
    assert len(pool.started) == _MAX_WORKERS_DP

    queued = _worker()
    wm.run_worker(queued)
    assert pool.started == workers  # not started while pool is full

    wm.discard_worker(workers[0])
    assert pool.started == workers + [queued]  # pumped as a slot frees
    assert queued in wm._workers


def test_queue_is_bounded(pool):
    wm = WorkerManager()
    for _ in range(_MAX_WORKERS_DP):
        wm.run_worker(_worker())
    limit = _MAX_WORKERS_DP * 2
    for _ in range(limit):
        wm.run_worker(_worker())
    overflow = _worker()
    wm.run_worker(overflow)
    assert overflow not in wm._pending
    assert len(wm._pending) == limit


def test_host_worker_tracked_for_cancel(pool):
    wm = WorkerManager()
    w = _worker()
    wm.run_host_worker(w)
    assert w in wm.current_host_workers
    # Simulate the finished signal firing its registered callback.
    on_finished = w.signals.finished.connect.call_args[0][0]
    on_finished()
    assert w not in wm._workers
    assert w not in wm.current_host_workers


def test_cancel_general_clears_pending(pool):
    wm = WorkerManager()
    for _ in range(_MAX_WORKERS_DP):
        wm.run_worker(_worker())
    for _ in range(3):
        wm.run_worker(_worker())
    assert wm._pending
    wm.cancel_general_workers()
    assert not wm._pending
