"""Лёгкая шина событий — seed для ROADMAP v3.0 (Event Bus).

Минималистичный pub/sub без зависимостей от Qt. Потокобезопасность:
мутации подписок под lock; обработчики вызываются в потоке издателя —
из worker-потока публикуйте через QueuedConnection/InvokeMethod.

Использование:
    bus = EventBus()
    off = bus.subscribe("node.status_changed", lambda e: ...)
    bus.publish(Event("node.status_changed", {"node": "n1", "status": "online"}))
    off()  # отписка
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    """Иммутабельное событие шины: топик + произвольный payload."""

    topic: str
    payload: Any = None


Handler = Callable[[Event], None]


class EventBus:
    """Реестр подписчиков по топикам с изолированной доставкой.

    Исключение в одном обработчике логируется и не мешает доставке
    остальным подписчикам того же события.
    """

    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = {}
        self._lock = threading.Lock()

    def subscribe(self, topic: str, handler: Handler) -> Callable[[], None]:
        """Подписаться; возвращает функцию отписки (идемпотентна)."""
        with self._lock:
            self._subs.setdefault(topic, []).append(handler)

        def unsubscribe() -> None:
            with self._lock:
                handlers = self._subs.get(topic)
                if handlers is not None and handler in handlers:
                    handlers.remove(handler)
                    if not handlers:
                        del self._subs[topic]

        return unsubscribe

    def publish(self, event: Event) -> int:
        """Доставить событие подписчикам топика. Возвращает число доставок."""
        with self._lock:
            handlers = list(self._subs.get(event.topic, ()))
        delivered = 0
        for handler in handlers:
            try:
                handler(event)
                delivered += 1
            except Exception:
                logger.exception("event handler failed: topic=%s", event.topic)
        return delivered

    def subscriber_count(self, topic: str) -> int:
        with self._lock:
            return len(self._subs.get(topic, ()))

    def clear(self) -> None:
        """Снять все подписки (для тестов)."""
        with self._lock:
            self._subs.clear()
