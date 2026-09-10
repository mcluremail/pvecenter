"""Tests for pve_center.pbs.workers — PbsApiWorker lifecycle.

Регресс аудита 2026-09-09: провайдер (requests.Session) закрывается в
finally — и при успехе, и при ошибке (раньше не закрывался вовсе).
"""
from __future__ import annotations

import pytest

from pve_center.pbs.client import PbsError
from pve_center.pbs.provider import PbsProvider
from pve_center.pbs.workers import PbsApiWorker


class FakeClient:
    def __init__(self, boom: bool = False):
        self.boom = boom
        self.closed = False

    def close(self):
        self.closed = True

    def datastores(self):
        if self.boom:
            raise PbsError("boom", 500)
        return [{"store": "main"}]

    def datastore_status(self, store):
        return {"usage": 0.5, "used": 5, "total": 10}


@pytest.fixture()
def fake_provider(monkeypatch):
    made = []

    def _make(cfg, timeout=15):
        p = PbsProvider(cfg, timeout=timeout)
        p._client = FakeClient(boom=cfg.get("_boom", False))
        made.append(p)
        return p

    monkeypatch.setattr("pve_center.pbs.workers.PbsProvider", _make)
    return made


def _run_worker(cfg):
    results, failures = [], []
    signals = PbsApiWorker.signals
    signals.done.connect(lambda tag, res: results.append(res))
    signals.failed.connect(lambda tag, err: failures.append(err))
    w = PbsApiWorker(cfg, "datastores")
    w.run()  # QThreadPool не нужен: run() вызываем напрямую
    return results, failures


def test_provider_closed_on_success(fake_provider):
    results, failures = _run_worker({"host": "h", "_boom": False})
    assert failures == []
    assert results and results[0] and results[0][0].name == "main"
    assert len(fake_provider) == 1
    assert fake_provider[0]._client.closed


def test_provider_closed_on_error(fake_provider):
    results, failures = _run_worker({"host": "h", "_boom": True})
    assert results == []
    assert failures == ["boom"]
    assert fake_provider[0]._client.closed
