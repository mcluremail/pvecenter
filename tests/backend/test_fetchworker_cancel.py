"""FetchWorker.cancel() must abort run() quietly (no signal emissions)
so app shutdown is not delayed by in-flight refresh workers."""

from __future__ import annotations

from pve_center import backend
from pve_center.backend import FetchWorker
from tests.backend.test_backend import FakeProvider


def _make_worker(monkeypatch, provider):
    monkeypatch.setattr(backend.fetch, "create_provider", lambda cfg, timeout=15: provider)
    return FetchWorker({"name": "h1"})


def test_cancel_skips_all_work_and_emits_nothing(qtbot, monkeypatch):
    provider = FakeProvider()
    worker = _make_worker(monkeypatch, provider)
    worker.cancel()

    emitted = []
    worker.signals.result_ready.connect(lambda d: emitted.append(d))
    worker.run()

    assert emitted == []
    assert provider.closed


def test_uncancelled_worker_emits_result(qtbot, monkeypatch):
    provider = FakeProvider()
    worker = _make_worker(monkeypatch, provider)

    emitted = []
    worker.signals.result_ready.connect(lambda d: emitted.append(d))
    worker.run()

    assert len(emitted) == 1
    assert emitted[0]["status"] == "ok"
    assert provider.closed
