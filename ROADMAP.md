# ROADMAP.md

## v2.10 — Стабилизация Desktop ✅
- ✅ Тесты backend-воркеров и config (tests/backend, tests/config)
- ✅ Глобальный поиск (B14)
- ✅ Массовые операции (B3)
- ✅ Snapshot rollback (B1a)
- ~~Dry Run (B15)~~ — исключено по решению (см. FEATURES_BACKLOG.md)

## v2.12 — Резервное копирование и PBS (B17, этап 1)
Через PVE API (storage типа pbs):
- Статус и заполненность PBS-хранилищ (покрывается общим storage-UI)
- Просмотр PBS-снапшотов: владелец, время, состояние верификации
- Удаление отдельных бэкапов из UI (prune по одному)
- Restore PBS-бэкапа в новую ВМ/контейнер

## v3.0 — Production Desktop
Цель: лучший desktop-клиент для управления несколькими независимыми PVE.

## v3.5 — Платформа
- ✅ Стабильная модель объектов (миграция UI с dict на доменные модели завершена в v2.10)
- ✅ Data Provider API: шов `DataProvider` (Protocol) + фасад `ProxmoxProvider`
  (`provider/_provider.py`); backend и metrics работают через фасад
- ✅ Plugin API (seed): `plugins/` — `ProviderPlugin` + `PluginRegistry`, диспетчеризация
  `create_provider(cfg)` по `cfg["type"]`; feature-плагины (Notifications, Policies, ...)
  — продолжение шва

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
