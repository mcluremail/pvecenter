"""Состояние циклов hard/soft refresh — чистая логика без Qt.

RefreshCoordinator хранит поколения, pending-множества и guard-и, на основе
которых MainWindow решает, какие результаты воркеров считать актуальными,
когда цикл завершён и когда зависший soft refresh пора сбросить по тайм-ауту.
"""

from __future__ import annotations

from typing import Any


class RefreshCoordinator:
    """Состояние hard- и soft-refresh циклов.

    Инварианты:
    - результаты воркера актуальны, только если его поколение совпадает
      с текущим (gen == 0 трактуется как legacy-вызов без поколения);
    - hard-цикл завершён, когда все воркеры поколения отчитались;
    - soft-цикл сбрасывается по тайм-ауту или новым hard refresh.
    """

    def __init__(self, soft_timeout: float = 90.0) -> None:
        self.soft_timeout = soft_timeout
        self._hard_gen = 0
        self._hard_pending: set[Any] = set()
        self._soft_gen = 0
        self._soft_running = False
        self._soft_start = 0.0
        self._soft_done = 0
        self._soft_expected = 0

    # -- hard refresh ---------------------------------------------------

    @property
    def hard_gen(self) -> int:
        return self._hard_gen

    def begin_hard(self) -> int:
        """Старт hard refresh: сброс pending. Возвращает новое поколение."""
        self._hard_gen += 1
        self._hard_pending = set()
        return self._hard_gen

    def track_hard(self, worker: Any) -> None:
        self._hard_pending.add(worker)

    def hard_done(self, worker: Any, gen: int) -> None:
        if gen == self._hard_gen:
            self._hard_pending.discard(worker)

    def hard_result_current(self, gen: int) -> bool:
        """Актуален ли результат hard-воркера (gen == 0 — legacy-вызов)."""
        return gen == 0 or gen == self._hard_gen

    @property
    def hard_pending_count(self) -> int:
        return len(self._hard_pending)

    # -- soft refresh ---------------------------------------------------

    @property
    def soft_gen(self) -> int:
        return self._soft_gen

    @property
    def soft_running(self) -> bool:
        return self._soft_running

    @property
    def soft_expected(self) -> int:
        return self._soft_expected

    def reset_soft(self) -> None:
        """Инвалидировать идущий soft-цикл (новый hard refresh / тайм-аут)."""
        self._soft_gen += 1
        self._soft_running = False
        self._soft_done = 0
        self._soft_expected = 0

    def finish_soft(self) -> None:
        """Снять флаг running без инвалидации поколения."""
        self._soft_running = False

    def soft_timed_out(self, now: float) -> bool:
        return self._soft_running and (now - self._soft_start > self.soft_timeout)

    def begin_soft(self, expected: int, now: float) -> int:
        """Заявить ownership нового soft-цикла. Возвращает поколение."""
        self._soft_running = True
        self._soft_start = now
        self._soft_done = 0
        self._soft_expected = expected
        self._soft_gen += 1
        return self._soft_gen

    def soft_result_current(self, gen: int) -> bool:
        return gen == self._soft_gen

    def soft_result(self, gen: int) -> bool:
        """Учесть результат soft-воркера; True — если это был последний."""
        if gen != self._soft_gen:
            return False
        self._soft_done += 1
        return self._soft_done >= self._soft_expected
