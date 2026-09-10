"""Регресс аудита 2026-09-09: воркер, отклонённый _run_worker (пул
переполнен), не должен учитываться в ожиданиях refresh-циклов — иначе
hard-финализация блокируется навсегда, soft-цикл висит до тайм-аута."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def main_window(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from pve_center.ui.mainwindow import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    yield mw
    mw.close()


def _fill_pool(mw):
    from pve_center.ui.mainwindow import MAX_WORKERS

    dummies = []
    for _ in range(MAX_WORKERS):
        d = MagicMock()
        mw._workers.add(d)
        dummies.append(d)
    return dummies


def test_run_worker_rejects_when_pool_full(main_window):
    mw = main_window
    _fill_pool(mw)
    w = MagicMock()
    assert mw._run_worker(w) is False
    assert w not in mw._workers


def test_run_worker_accepts_with_free_slot(main_window):
    mw = main_window
    w = MagicMock()
    assert mw._run_worker(w) is True
    assert w in mw._workers


def test_rejected_fetchworker_not_tracked_hard(main_window, monkeypatch):
    """track_hard после успешного старта: отклонённый FetchWorker не
    попадает в hard_pending → финализация не блокируется навсегда."""
    mw = main_window
    created = []

    class _FakeFetch:
        def __init__(self, cfg):
            self.signals = MagicMock()
            self.node_cfg = cfg
            created.append(self)

    import pve_center.ui.mainwindow as mw_mod
    monkeypatch.setattr(mw_mod, "FetchWorker", _FakeFetch)
    mw.nodes_cfg = [{"name": "h1", "host": "10.0.0.1", "user": "u@pam",
                     "token_name": "t", "token_value": "s"}]
    _fill_pool(mw)

    mw.refresh_data()

    assert len(created) == 1          # воркер создан...
    assert created[0] not in mw._workers  # ...отклонён пулом
    assert mw._refresh.hard_pending_count == 0  # и НЕ трекнут в hard


def test_soft_cycle_skips_overflow_hosts(main_window, monkeypatch):
    """begin_soft должна считать только фактически запускаемые воркеры,
    иначе цикл ждёт результаты, которые никогда не придут (до тайм-аута)."""
    mw = main_window
    created = []

    class _FakeFetch:
        def __init__(self, cfg):
            self.signals = MagicMock()
            self.node_cfg = cfg
            created.append(self)

    import pve_center.ui.mainwindow as mw_mod
    monkeypatch.setattr(mw_mod, "FetchWorker", _FakeFetch)
    mw.nodes_cfg = [{"name": f"h{i}", "host": f"10.0.0.{i}", "user": "u@pam",
                     "token_name": "t", "token_value": "s"} for i in range(3)]
    _fill_pool(mw)
    mw.last_refresh_ts = 0.0  # разрешить soft_refresh

    mw.soft_refresh()

    assert created == []                      # пула нет — никто не стартует
    assert mw._refresh.soft_running is False  # цикл не висит до тайм-аута
