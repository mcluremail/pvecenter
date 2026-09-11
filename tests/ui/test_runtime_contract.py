"""M0.2: runtime-контракт «ни одного сетевого вызова в UI-потоке».

Офлайн-прогон action-слотов: guard-провайдер фиксирует любой вызов
sync-клиента из main-потока, fake-пул не выполняет воркеры, диалоги
автопринимаются. Требование ROADMAP: toolbar, контекст-меню дерева,
диалоги — ни один слот не должен дотянуться до провайдера синхронно.
"""

import threading

import pytest
from PySide6.QtGui import QAction

import tests.ui.runtime_contract as rc
from tests.ui.runtime_contract import (
    RuntimeContractViolation,
    _SyncTrap,
    install_guard,
)


class TestGuard:
    """Guard-провайдер: ловит sync-клиент в main-потоке, пропускает
    фоновые потоки."""

    def test_main_thread_call_is_recorded(self, monkeypatch):
        violations = install_guard(monkeypatch)
        import pve_center.plugins as plugins_mod

        provider = plugins_mod.create_provider({"name": "h1", "type": "pve"})
        provider.cluster.get("nodes")
        assert len(violations) == 3
        assert "provider[h1]: доступ к .cluster" in violations[0]
        assert "provider[h1].cluster: доступ к .get" in violations[1]
        assert "provider[h1].cluster.get: вызов" in violations[2]

    def test_raise_mode_raises_base_exception(self, monkeypatch):
        install_guard(monkeypatch, raise_in_main=True)
        import pve_center.plugins as plugins_mod

        provider = plugins_mod.create_provider({"name": "h1", "type": "pve"})
        with pytest.raises(RuntimeContractViolation):
            provider.vms.list()

    def test_background_thread_is_not_a_violation(self, monkeypatch):
        violations = install_guard(monkeypatch)
        import pve_center.plugins as plugins_mod

        provider = plugins_mod.create_provider({"name": "h1", "type": "pve"})

        result = {}

        def worker():
            result["value"] = provider.nodes.get("n1")

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert result["value"] is None
        assert violations == []


def _run_and_report(actions, violations, label):
    """Триггерит каждый action в изоляции и возвращает отчёт нарушений:
    {«action»: [сообщения guard]} — только по нарушившим действиям.
    Модальные диалоги, открытые слотом, закрывает modal-closer."""
    report = {}
    closer = rc.install_modal_closer()
    closer.start()
    try:
        for act in actions:
            before = len(violations)
            act.trigger()
            new = violations[before:]
            if new:
                name = act.objectName() or act.text() or f"<unnamed @ {id(act):#x}>"
                report[f"{label}: {name}"] = new
    finally:
        closer.stop()
    return report


def test_toolbar_actions_make_no_sync_calls(main_window, offline):
    """Все QAction MainWindow (toolbar и пр.) не выполняют сетевых
    вызовов в UI-потоке."""
    violations, _ = offline
    mw = main_window
    actions = mw.findChildren(QAction)
    assert actions, "MainWindow обязан иметь actions"
    report = _run_and_report(actions, violations, "mainwindow")
    assert not report, "Синхронные сетевые вызовы в UI-потоке:\n" + "\n".join(
        f"{k}\n  " + "\n  ".join(v) for k, v in report.items()
    )


def test_tree_context_menus_make_no_sync_calls(qtbot, offline, make_node, make_vm):
    """Контекст-меню дерева (VM и host) — действия не тянут сеть."""
    violations, _ = offline
    from pve_center.domain.enums import VmStatus
    from pve_center.domain.repositories import NodeRepository, VmRepository
    from pve_center.ui.tree_panel import ITEM_KEY_ROLE, VM_KEY_ROLE, TreePanel

    cfg = [{"name": "h1", "cluster": "", "skip": False}]
    tp = TreePanel(cfg)
    qtbot.addWidget(tp)

    node = make_node(host_name="h1", node="pve01")
    vm = make_vm(vmid=100, name="alpha", host_name="h1", node="pve01", status=VmStatus.RUNNING)
    node_repo = NodeRepository()
    node_repo.add(node)
    vm_repo = VmRepository()
    vm_repo.add(vm)
    tp.update_data(node_repo.all(), vm_repo.all(), final=True, node_repo=node_repo, vm_repo=vm_repo)
    tp._build_tree()

    # Контекст-меню открывается по itemAt(pos): подать позицию элемента ВМ
    # (элемент ищем по VM_KEY_ROLE — текст может содержать декорации).
    vm_items = []

    def walk(item):
        if item.data(0, VM_KEY_ROLE) is not None:
            vm_items.append(item)
        for i in range(item.childCount()):
            walk(item.child(i))

    for i in range(tp.tree.topLevelItemCount()):
        walk(tp.tree.topLevelItem(i))
    assert vm_items, "ВМ-элемент должен быть в дереве"
    # M0.2 рефакторинг tree_panel: меню строится билдером, exec не нужен.
    menus = [tp._build_context_menu(vm_items[0])]
    # Host-элемент: те же правила для host-меню.
    host_items = []

    def walk_keys(item):
        key = item.data(0, ITEM_KEY_ROLE)
        if key and isinstance(key, tuple) and key[0] == "host":
            host_items.append(item)
        for i in range(item.childCount()):
            walk_keys(item.child(i))

    for i in range(tp.tree.topLevelItemCount()):
        walk_keys(tp.tree.topLevelItem(i))
    if host_items:
        menus.append(tp._build_context_menu(host_items[0]))
    menus = [m for m in menus if m is not None]
    assert menus, "Контекст-меню должно собраться"
    report = {}
    while menus:
        menu = menus.pop()
        report.update(
            _run_and_report(
                [a for a in menu.actions() if a.isEnabled() and not a.isSeparator()],
                violations,
                f"menu@{menu.title() or 'tree'}",
            )
        )
    assert not report, "Синхронные сетевые вызовы в UI-потоке:\n" + "\n".join(
        f"{k}\n  " + "\n  ".join(v) for k, v in report.items()
    )


def test_trap_in_worker_thread_returns_stub():
    """_SyncTrap из фонового потока — заглушка (без нарушений)."""
    collected = []
    trap = _SyncTrap("provider", collect=collected.append)
    result = {}

    def worker():
        sub = trap.cluster
        result["call"] = sub.get("n1")

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert result["call"] is None
    assert collected == []


def test_main_window_fixture_boots_offline(main_window, offline):
    """Санити: MainWindow создаётся офлайн, guard активен, нарушений
    при загрузке нет."""
    violations, _ = offline
    assert main_window is not None
    assert violations == []
