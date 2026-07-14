# Идеи фичей — backlog

## Done

### F1. About dialog ✅ (v1.5.0)
Диалог "О программе": версия, автор, лицензия, ссылка на GitHub, описание.
Кнопка About в тулбаре (иконка "i" в круге).

### F2. Keyring storage ✅ (v2.0.0)
Мастер-пароль удалён. Токены хранятся в системном keyring (по одному секрету на узел).
Конфигурация узлов — в config.sqlite (без token_value).
Export/import — encrypted bundle с паролем.

## Version numbering

| Изменение | Паттерн | Пример |
|---|---|---|
| Багфикс | `1.5.X` | 1.5.1, 1.5.2, ... |
| Новая фича | `1.X.0` | 1.6.0, 1.7.0, ... |
| Глобальные изменения | `X.0.0` | 2.0.0 |

## Backlog

### B1. Snapshots management
Создание/удаление/откат снапшотов ВМ из UI. Сейчас только просмотр.
- Контекстное меню ВМ → "Snapshots" → диалог со списком + кнопками
- Create: `POST /nodes/{node}/{type}/{vmid}/snapshot` с именем
- Rollback: `POST /nodes/{node}/{type}/{vmid}/snapshot/{name}/rollback`
- Delete: `DELETE /nodes/{node}/{type}/{vmid}/snapshot/{name}`
- Подтверждение для rollback и delete

### B2. VM config editor — hardware hotplug ✅ (v2.8.x)
Редактирование CPU/RAM/disk/net без пересоздания ВМ.
- `PUT /nodes/{node}/qemu/{vmid}/config` — все системные параметры
- Hotplug для CPU/RAM/net (на работающей ВМ)
- Disk resize: `PUT /nodes/{node}/qemu/{vmid}/resize`
- Disk move: `POST /nodes/{node}/qemu/{vmid}/move_disk`
- Add/remove devices: disk, cdrom, net, usb, pci, serial, efi, tpm
- Валидация перед применением

### B3. Bulk VM actions
Массовые операции над выбранными ВМ: start/stop/migrate/clone.
- Ctrl+click в дереве для multi-select
- Тулбар с bulk actions когда выбрано >1 ВМ
- Прогресс-бар на операцию

### B4. Storage operations ✅ (v2.8.x)
- Перемещение диска между storage (`POST /nodes/{node}/qemu/{vmid}/move_disk`)
- Resize диска (`PUT /nodes/{node}/qemu/{vmid}/resize`)
- Upload ISO через UI — не реализовано (future)

### B5. HA group management
Просмотр/создание/удаление HA groups. Сейчас только чтение.
- `GET/POST/DELETE /cluster/ha/groups`
- Назначение ВМ в HA group
- Редактирование приоритетов

### B6. User management
Просмотр PVE users и их токенов.
- `GET /access/users` + `GET /access/users/{user}/token/{tokenid}`
- Создание/удаление токенов из UI (сейчас только auto-create)
- Просмотр permissions

### B7. Node network config
Редактирование сетевых интерфейсов хоста. Сейчас только просмотр.
- `PUT /nodes/{node}/network/{iface}` с изменённой конфигурацией
- Apply network changes (`POST /nodes/{node}/network` с `apply=1`)
- Создание/удаление bridges, VLAN

### B8. Backup jobs
Создание/редактирование backup jobs. Сейчас только просмотр бэкапов.
- `POST /nodes/{node}/vzdump` — разовый бэкап
- `GET/POST/PUT/DELETE /cluster/jobs/schedule` — scheduled jobs
- Restore из бэкапа: `POST /nodes/{node}/qemu/{vmid}/clone` с `restore=1`

### B9. VNC console
VNC консоль как альтернатива SPICE (для ВМ без SPICE).
- `POST /nodes/{node}/qemu/{vmid}/vncproxy`
- Запуск external VNC viewer (vncviewer) с прокси-портом

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

### B12. Cluster operations
- Добавление ноды в кластер через UI (`pvecm add`)
- Просмотр quorum status (`GET /cluster/status`)
- Corosync config viewer