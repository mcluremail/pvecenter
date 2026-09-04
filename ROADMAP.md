# ROADMAP.md

## v2.10 — Стабилизация Desktop
- Тесты backend-воркеров и config (сейчас покрыты только domain/provider/ui)
- Глобальный поиск (B14)
- Массовые операции (B3)
- Snapshot rollback (B1a)
- Dry Run и предварительная проверка опасных действий (B15)

## v3.0 — Production Desktop
Цель: лучший desktop-клиент для управления несколькими независимыми PVE.

## v3.5 — Платформа
- ✅ Стабильная модель объектов (миграция UI с dict на доменные модели завершена в v2.10)
- ✅ Data Provider API: шов `DataProvider` (Protocol) + фасад `ProxmoxProvider`
  (`provider/_provider.py`); backend и metrics работают через фасад
- Plugin API

### Техдолг миграции (осознанно не переводится на доменные модели)
- Backups-таблица и vzdump/backup jobs — dict'ами до B17 (модели бэкапов появятся там)
- rrddata / metrics (`ui/api/metrics.py`) — числовые сэмплы, dict оправдан
- VmDetailWorker / вкладка Config — глубоко вложенный PVE-конфиг, моделирование дорого при малой пользе
- Config-словари (`cfg["group"]`, тела POST-запросов) — dict по дизайну, не PVE-ответы

## v4.0 — Опциональная серверная часть
- Inventory
- Централизованный Cache
- History
- Event Bus
- REST API / WebSocket

## v4.5
- Audit
- Notifications
- CLI

## v5.0 — Policy Engine и автоматизация
- Рекомендации
- Affinity / Anti-affinity
- Балансировка нагрузки
- Maintenance policies
- DRS-подобные возможности
- Предиктивная аналитика
