"""M0.3: optimistic UI каркас «применить сразу → подтвердить/откатить».

UI показывает целевое состояние немедленно, не дожидаясь ни ответа
воркера, ни следующего refresh-цикла:

1. apply(): VmRepository патчится (frozen Vm заменяется копией с
   целевым статусом), запись попадает в pending;
2. успех воркера → confirm(): pending снимается, целевой статус
   остаётся до прихода реальных данных (refresh_data);
3. ошибка воркера → rollback(): прежний статус возвращается в
   репозиторий, дерево перерисовывается.

Дерево показывает pending-элементы спиннером (TreePanel.
set_pending_vm_keys), поэтому UI-состояние видно в каждый момент.
Каркас доменно-зависим в одном месте: POWER_TARGET_STATUS задаёт
целевой статус для power-действия; действия вне словаря (migrate,
clone, snapshot) оптимистично не применяются.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from ..domain.enums import VmStatus
from ..domain.repositories import VmRepository

POWER_TARGET_STATUS: dict[str, VmStatus] = {
    "start": VmStatus.RUNNING,
    "resume": VmStatus.RUNNING,
    "reboot": VmStatus.RUNNING,
    "reset": VmStatus.RUNNING,
    "shutdown": VmStatus.STOPPED,
    "stop": VmStatus.STOPPED,
}


@dataclass(frozen=True)
class _Pending:
    """Одно изменение в полёте (оригинал статуса для отката)."""

    host_name: str
    vmid: int
    action: str
    prev_status: VmStatus


class OptimisticVMs:
    """Менеджер optimistic-изменений статусов ВМ поверх VmRepository.

    Поток: apply() возвращает токен (или None — действие не power /
    ВМ не найдена / шаблон); токен.confirm() или токен.rollback()
    завершают изменение. Каждый шаг дёргает on_change (перерисовка).
    """

    def __init__(
        self,
        vm_repo: VmRepository,
        on_change: Callable[[], None] | None = None,
    ):
        self._repo = vm_repo
        self._on_change = on_change or (lambda: None)
        self._pending: dict[tuple[str, int], _Pending] = {}

    def apply(self, host_name: str, vmid: int, action: str) -> "OptimisticToken | None":
        target = POWER_TARGET_STATUS.get(action)
        if target is None:
            return None
        vm = self._repo.get(host_name, vmid)
        if vm is None or vm.template:
            return None
        key = (host_name, vmid)
        # Повторное действие поверх pending: оригинал статуса сохраняем,
        # откат вернёт его, а не промежуточный optimistic.
        prev = self._pending[key].prev_status if key in self._pending else vm.status
        self._repo.add(replace(vm, status=target))
        self._pending[key] = _Pending(host_name, vmid, action, prev)
        self._on_change()
        return OptimisticToken(self, key)

    def confirm(self, host_name: str, vmid: int) -> None:
        if self._pending.pop((host_name, vmid), None) is not None:
            self._on_change()

    def rollback(self, host_name: str, vmid: int) -> None:
        pending = self._pending.pop((host_name, vmid), None)
        if pending is None:
            return
        vm = self._repo.get(host_name, vmid)
        if vm is not None:
            self._repo.add(replace(vm, status=pending.prev_status))
        self._on_change()

    def pending_keys(self) -> set[tuple[str, int]]:
        return set(self._pending)

    def pending_action(self, host_name: str, vmid: int) -> str | None:
        pending = self._pending.get((host_name, vmid))
        return pending.action if pending else None


class OptimisticToken:
    """Ручка одного optimistic-изменения: confirm/rollback по ответу."""

    __slots__ = ("_manager", "_host_name", "_vmid")

    def __init__(self, manager: OptimisticVMs, key: tuple[str, int]):
        self._manager = manager
        self._host_name, self._vmid = key

    def confirm(self) -> None:
        self._manager.confirm(self._host_name, self._vmid)

    def rollback(self) -> None:
        self._manager.rollback(self._host_name, self._vmid)
