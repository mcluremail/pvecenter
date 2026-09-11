"""M0.2: runtime-контракт «ни одного сетевого вызова в UI-потоке»
(ROADMAP v3.0). Инфраструктура для офлайн-прогонов action-слотов:
- guard-провайдер подменяет PluginRegistry.create_provider: любой вызов
  или доступ к атрибутам провайдера из main-потока фиксируется как
  нарушение (в фоновых потоках — тихая заглушка);
- fake QThreadPool не выполняет воркеры вовсе — слоты спокойно создают
  воркеры, никто не лезет в сеть;
- autofire-патчи статических фабрик диалогов (QMessageBox/QInputDialog/
  QFileDialog) дают дефолтные ответы;
- modal-closer закрывает любой popup/modal, открытый instance-exec
  (QDialog.exec, QMenu.exec — PySide6 не даёт перехватить их патчем
  класса): таймер в event loop самого exec закрывает окно.

Нарушения накапливаются в списке, который выдаёт install_guard():
тест после обхода слотов проверяет его пустоту и печатает отчёт.
"""

import threading

from PySide6.QtCore import QThreadPool, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMessageBox,
)


class RuntimeContractViolation(BaseException):
    """Вызов sync-клиента в main-потоке.

    Наследует BaseException намеренно: слоты с ``except Exception``
    не должны проглатывать нарушение (для режима raise)."""


def _in_main_thread():
    return threading.current_thread() is threading.main_thread()


class _SyncTrap:
    """Ловушка на пути DataProvider.

    Любой вызов или доступ к атрибуту из main-потока — нарушение
    (запись в collect и/или RuntimeContractViolation); из фонового
    потока — тихая заглушка (воркер получит пустоту и деградирует
    штатным error_occurred)."""

    __slots__ = ("_path", "_collect", "_raise_in_main")

    def __init__(self, path="provider", collect=None, raise_in_main=False):
        self._path = path
        self._collect = collect
        self._raise_in_main = raise_in_main

    def _violation(self, what):
        message = f"{self._path}: {what} в UI-потоке"
        if self._collect is not None:
            if isinstance(self._collect, list):
                self._collect.append(message)
            else:
                self._collect(message)
        if self._raise_in_main:
            raise RuntimeContractViolation(message)

    def __call__(self, *args, **kwargs):
        if _in_main_thread():
            self._violation("вызов")
            return None
        return None

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if _in_main_thread():
            self._violation(f"доступ к .{name}")
        return _SyncTrap(f"{self._path}.{name}", self._collect, self._raise_in_main)

    def __repr__(self):  # pragma: no cover — отладочное
        return f"<SyncTrap {self._path}>"


def install_guard(monkeypatch, collect=None, raise_in_main=False):
    """Патчит PluginRegistry.create_provider на guard-провайдер.

    Единая точка: все импорты create_provider (backend/*, ui/api/*)
    доходят до реестра. Возвращает список нарушений (если collect
    не передан явно)."""
    import pve_center.plugins as plugins_mod

    if collect is None:
        collect = []
    plugin_cls = plugins_mod.PluginRegistry

    def _fake_create_provider(self, cfg, timeout=15):
        return _SyncTrap(f"provider[{cfg.get('name', '?')}]", collect, raise_in_main)

    monkeypatch.setattr(plugin_cls, "create_provider", _fake_create_provider)
    return collect


class _RecordingPool:
    """QThreadPool-заглушка: воркеры собираются, но не выполняются."""

    def __init__(self):
        self.started = []

    def start(self, runnable, priority=0):
        self.started.append(runnable)

    def clear(self):
        self.started.clear()

    def waitForDone(self, msecs=-1):
        return True

    def activeThreadCount(self):
        return 0

    def tryStart(self, runnable):
        self.start(runnable)
        return True

    def reserveThread(self):
        pass

    def releaseThread(self):
        pass


def install_fake_pool(monkeypatch):
    """Подменяет QThreadPool.globalInstance на собирающую заглушку —
    паттерн tests/ui/test_worker_manager.py, один патч закрывает все
    точки старта воркеров (mainwindow, WorkerManager, ui/api)."""
    pool = _RecordingPool()
    monkeypatch.setattr(QThreadPool, "globalInstance", staticmethod(lambda: pool))
    return pool


def install_modal_closer(interval_ms=20):
    """QTimer, закрывающий popup/modal-окна, открытые триггером действия.

    PySide6 не даёт перехватить instance-exec (QDialog.exec, QMenu.exec)
    патчем класса — реальный exec блокирует UI-поток. Таймер крутится в
    event loop самого exec и закрывает активное окно, exec немедленно
    возвращается (Rejected/None). Остановить после прогона: stop()."""
    timer = QTimer()
    timer.setInterval(interval_ms)

    def _close_active():
        popup = QApplication.activePopupWidget()
        if popup is not None:
            popup.close()
        modal = QApplication.activeModalWidget()
        if modal is not None:
            modal.close()

    timer.timeout.connect(_close_active)
    return timer


def install_pyqtgraph_shims(monkeypatch):
    """pyqtgraph-экспорт нестабилен в offscreen: showExportDialog падает
    с AttributeError (contextMenuItem назначается только по реальному
    mouse-событию). Экспорт графиков — вне предмета сетевого контракта,
    шим глушит только этот внешний путь."""
    try:
        from pyqtgraph.GraphicsScene.GraphicsScene import GraphicsScene
    except ImportError:  # pragma: no cover — pyqtgraph в deps проекта
        return
    monkeypatch.setattr(
        GraphicsScene,
        "showExportDialog",
        lambda self, item=None: None,
        raising=False,
    )


def install_autofire_dialogs(monkeypatch):
    """Статические фабрики диалогов отвечают «отменено»: QMessageBox →
    Yes/Ok, QInputDialog → ("", False), QFileDialog → ("", ""). Модальные
    exec кастомных диалогов закрывает install_modal_closer. Всё, что
    пошло в сеть, ловит guard-провайдер."""
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(lambda *a, **k: ("", False)),
    )
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("", False)))
    monkeypatch.setattr(
        QInputDialog,
        "getMultiLineText",
        staticmethod(lambda *a, **k: ("", False)),
    )
    monkeypatch.setattr(QInputDialog, "getDouble", staticmethod(lambda *a, **k: (0.0, False)))
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        staticmethod(lambda *a, **k: ("", False)),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )
