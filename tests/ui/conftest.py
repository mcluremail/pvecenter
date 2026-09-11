"""Общие фикстуры UI-тестов.

offline/main_window определены в M0.2 (runtime-контракт) и используются
несколькими файлами (test_runtime_contract, test_optimistic).
"""

import pytest

from tests.ui.runtime_contract import (
    install_autofire_dialogs,
    install_fake_pool,
    install_guard,
    install_pyqtgraph_shims,
)


@pytest.fixture()
def offline(monkeypatch):
    """Полный офлайн-режим: guard + fake pool + autofire диалоги."""
    violations = install_guard(monkeypatch)
    pool = install_fake_pool(monkeypatch)
    install_autofire_dialogs(monkeypatch)
    install_pyqtgraph_shims(monkeypatch)
    return violations, pool


@pytest.fixture()
def main_window(qtbot, monkeypatch, tmp_path, offline):
    """MainWindow как в tests/ui/test_refresh_tracking.py + офлайн."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from pve_center.ui.mainwindow import MainWindow

    mw = MainWindow()
    qtbot.addWidget(mw)
    yield mw
    mw.close()
