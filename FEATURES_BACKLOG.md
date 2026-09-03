# Идеи фичей — backlog

## Version numbering

| Изменение | Паттерн | Пример |
|---|---|---|
| Багфикс | `2.9.X` | 2.9.1, 2.9.2, ... |
| Новая фича | `2.X.0` | 2.10.0, 2.11.0, ... |
| Глобальные изменения | `X.0.0` | 3.0.0 |

## Done

### F1. About dialog ✅ (v1.5.0)
Диалог "О программе": версия, автор, лицензия, ссылка на GitHub, описание.
Кнопка About в тулбаре (иконка "i" в круге).

### F2. Keyring storage ✅ (v2.0.0)
Мастер-пароль удалён. Токены хранятся в системном keyring (по одному секрету на узел).
Конфигурация узлов — в config.sqlite (без token_value).
Export/import — encrypted bundle с паролем.

### B1. Snapshots management ✅ (v2.6.x)
Просмотр (VM + хост), создание и удаление снапшотов из UI, ожидание UPID задачи.
Откат вынесен в отдельный пункт B1a.

### B2. VM config editor — hardware hotplug ✅ (v2.8.x)
Редактирование CPU/RAM/disk/net без пересоздания ВМ.
- `PUT /nodes/{node}/qemu/{vmid}/config` — все системные параметры
- Hotplug для CPU/RAM/net (на работающей ВМ)
- Disk resize: `PUT /nodes/{node}/qemu/{vmid}/resize`
- Disk move: `POST /nodes/{node}/qemu/{vmid}/move_disk`
- Add/remove devices: disk, cdrom, net, usb, pci, serial, efi, tpm
- Валидация перед применением

### B4. Storage operations ✅ (v2.8.x)
- Перемещение диска между storage (`POST /nodes/{node}/qemu/{vmid}/move_disk`)
- Resize диска (`PUT /nodes/{node}/qemu/{vmid}/resize`)

### B5. HA management ✅ (v2.9.x, main)
HA-таб: группы и ресурсы, добавление/удаление ВМ в HA, контекстное меню.
- `GET/POST/DELETE /cluster/ha/groups`, `/cluster/ha/resources`

### B6. User management ✅ (v2.8.x)
Access-таб: пользователи, API-токены, группы, роли, ACL/permissions.
- `GET /access/users` + `GET /access/users/{user}/token/{tokenid}`
- Создание/удаление токенов из UI, просмотр permissions

### B7. Node network config ✅ (v2.9.x, main)
CRUD сетевых интерфейсов хоста, apply/revert, расширенные колонки таблицы.
- `PUT /nodes/{node}/network/{iface}`, apply: `POST /nodes/{node}/network`

### B8. Backup jobs ✅ (v2.8.0)
- Разовый бэкап vzdump: storage, mode, compression, retention, bandwidth
- Restore из бэкапа: новый VMID, target storage, force, unique MAC
- Scheduled jobs: add/edit/remove, PVE 8+ (`/cluster/jobs`) и PVE 7 (`/cluster/backup`)

### B9. VNC console ✅ (v2.9.x, main)
- QEMU: SPICE → VNC fallback (для ВМ без SPICE)
- LXC: VNC proxy (`POST /nodes/{node}/lxc/{vmid}/vncproxy`)

### B12. Cluster operations ✅ (v2.9.x, main)
- Просмотр quorum status (`GET /cluster/status`)
- Corosync config viewer
- Добавление ноды в кластер — вынесено в B12a

### B13. Download from URL ✅ (v2.9.x, main)
Загрузка ISO/шаблонов по URL напрямую на storage (`POST /nodes/{node}/storage/.../download-url`).

## Backlog

### B1a. Snapshot rollback
Откат ВМ/контейнера к снапшоту.
- `POST /nodes/{node}/{type}/{vmid}/snapshot/{name}/rollback`
- Подтверждение + guard для running ВМ
- Переводы и роль `VM.Snapshot.Rollback` уже заготовлены в i18n

### B3. Bulk VM actions
Массовые операции над выбранными ВМ: start/stop/shutdown/migrate.
- Ctrl+click в дереве для multi-select
- Тулбар с bulk actions когда выбрано >1 ВМ
- Прогресс-бар на операцию

### B10. Replication
Настройка zfs replication между нодами.
- `GET/POST/DELETE /nodes/{node}/replication`
- Просмотр статуса репликации
- Создание/удаление replication jobs

### B11. Metrics history
Графики за произвольный период (не только hour/day/week/...).
- `GET /nodes/{node}/rrddata?timeframe=...` с custom timeframe
- DatePicker для выбора периода
- Export данных в CSV

### B12a. Add node to cluster (low priority)
Добавление ноды в кластер через UI (`pvecm add`).

### B14. Global search
Глобальный поиск по всем кластерам из VISION.md.
- Поиск по: VMID, имени, тегам, владельцу, IP, node, cluster, storage
- Реализация поверх доменных репозиториев (O(1)-индексы готовы)
- Быстрый переход к найденному объекту в дереве

### B15. Dry Run
Предварительный просмотр опасных действий (из ROADMAP v0.x).
- Перед подтверждением показывать: какие API-запросы будут отправлены
- Ожидаемые последствия (например, "диск X будет удалён со storage")
