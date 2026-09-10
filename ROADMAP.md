# ROADMAP.md

## v2.13 — Стабилизация (последний 2.x) ✅ (выпущено в v2.13.0)
- ✅ B12a/B12b: cluster join и create через UI (`POST /cluster/config[/join]`)
- ✅ B4 завершение: CRUD storage-определений (`/storage`), Copy volume
- ✅ B11: произвольный диапазон метрик + экспорт CSV
- ✅ PBS-серверы в отдельном режиме дерева «Backup servers view»,
  per-node строки под shared-хранилищами кластера
- ✅ Стилизация: акцент только у первичных действий (Start, Create VM)
- ✅ i18n: полный паритет ключей в 5 локалях (версия 31)
- ✅ Аудит 2026-09-10 (`docs/AUDIT_2026-09-10.md`): join-воркер получал
  конфиг без credentials — исправлено
- ~~Управление кластером после создания (перемещение нод, link-топология)~~ —
  кандидат в 3.x

## v2.10 — Стабилизация Desktop ✅
- ✅ Тесты backend-воркеров и config (tests/backend, tests/config)
- ✅ Глобальный поиск (B14)
- ✅ Массовые операции (B3)
- ✅ Snapshot rollback (B1a)
- ~~Dry Run (B15)~~ — исключено по решению (см. FEATURES_BACKLOG.md)

## v2.12 — Резервное копирование и PBS (B17) ✅ (выпущено в v2.12.0)
Этап 1 — через PVE API (storage типа pbs):
- ✅ Статус и заполненность PBS-хранилищ (покрывается общим storage-UI)
- ✅ Просмотр PBS-снапшотов: владелец, время, состояние верификации
- ✅ Удаление отдельных бэкапов из UI (prune по одному)
- ✅ Restore PBS-бэкапа в новую ВМ/контейнер

Этап 2 — прямое подключение к PBS API (порт 8007), отдельный плагин:
- ✅ Plugin API: `PbsPlugin` (dispatch по `cfg["type"]="pbs"`), клиент с ticket-авторизацией
- ✅ Добавление PBS-сервера в диалоге Add Server (проверка подключения при добавлении)
- ✅ PBS-серверы в дереве (flat, режим Hosts) со списком datastores и заполненностью
- ✅ Панель PBS: статус/usage datastore, снапшоты (ns, verify, владелец, размер,
  удаление), sync/verify/prune задачи (просмотр, запуск вручную)
- ~~Server-side trash~~ — в PBS API нет публичных эндпоинтов trash (серверная фича)

## Поддержка версий PVE
- ✅ PVE 7.x — поддерживается (основная среда эксплуатации): jobs через
  `/cluster/backup`, детект версии с fallback на 7, HA через `/cluster/ha/groups`
- ✅ PVE 8.x — базовая линейка, полное покрытие
- ✅ PVE 9.x — совместимость подтверждена аудитом по API-документации (2026-09):
  breaking changes учтены — VNC password+TLS (PSA-2026-00014-1), `schedule` вместо
  `starttime`/`dow` в backup jobs, HA groups deprecated (fallback в UI)
- Нюансы PVE 7.0 (без 7.1+): в ответе jobs нет `schedule`, нет `download-url` —
  UI показывает пустое расписание, загрузка ISO по URL недоступна; 7.1+ — полностью

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
