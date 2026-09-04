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

### B1a. Snapshot rollback ✅ (v2.10.0 — main)
Откат ВМ/контейнера к снапшоту из таба Snapshots: кнопка в тулбаре + контекстное меню.
- `POST /nodes/{node}/{type}/{vmid}/snapshot/{name}/rollback`, ожидание UPID задачи
- Подтверждение с предупреждением, guard для псевдо-снапшота "current"

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

### B3. Bulk VM actions ✅ (v2.10.0, main)
Массовые операции над выбранными ВМ (контекстное меню при multi-select >1 ВМ):
- ExtendedSelection в дереве (Ctrl+click / Shift+click)
- Массовые start/shutdown/reboot/stop из контекстного меню
- Прогресс-бар с кнопкой Cancel, сводка ok/failed
- Доменный слой: `plan_bulk_action` (фильтр шаблонов/недоступных ВМ, dedup)
- Не вошло: bulk migrate (требует выбора target node — кандидат на отдельную задачу)

## Backlog

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

### B14. Global search ✅ Done
Глобальный поиск по всем кластерам из VISION.md.
- Поиск по: VMID, имени, тегам, владельцу, IP, node, cluster, storage
- Реализация поверх доменных репозиториев (O(1)-индексы готовы)
- Быстрый переход к найденному объекту в дереве

Реализовано: `domain/search.py` (чистая функция поверх репозиториев —
поиск по имени, VMID, тегам, пулу, node, config-хосту, кластеру, storage,
poolid) + `ui/search_dialog.py` (дебаунс 200 мс, колонки Type/Name/Location)
+ кнопка в тулбаре и Ctrl+F; выбор результата прыгает в дерево через
`TreePanel.find_and_select`. 14 тестов в `tests/domain/test_search.py`.
Не вошло (следующий шаг): поиск по IP (нет в list-level данных), владелец.

### B15. Dry Run
Предварительный просмотр опасных действий (из ROADMAP v0.x).
- Перед подтверждением показывать: какие API-запросы будут отправлены
- Ожидаемые последствия (например, "диск X будет удалён со storage")

### B16. Пользовательские группы серверов и кластеров ✅ (v2.10.0, main)
Группировка отдельных серверов и кластеров в именованные группы (по площадкам, датацентрам, назначению).
- Дополнительный уровень в дереве поверх секций «Clusters» и «Standalone hosts» (с агрегированной сводкой [running/total])
- Хранение группировки в config.sqlite (поле `group` у хоста; группа кластера задаётся на всех участниках)
- Контекстное меню «Move to group...» (для хоста и кластера) + Rename/Delete группы
- Drag&drop: перетаскивание хоста/кластера на группу или в секции Clusters/Standalone hosts (убрать из группы); дерево не мутируется — сигнал и перестройка
- Сводка по группе: SUMMARY + Host VMs с агрегированными карточками (аналог сводки кластера)
- Фундамент для сущностей Site/Datacenter из VISION.md

### B17. Резервное копирование и PBS (Proxmox Backup Server)
Расширенная работа с бэкапами, включая PBS (плагин PBS заявлен в VISION.md / ARCHITECTURE.md).
Этап 1 — через PVE API (стorage типа pbs):
- Статус и заполненность PBS-хранилищ
- Просмотр backup-групп и снапшотов PBS: владелец, время, verify state
- Удаление отдельных бэкапов из UI (prune по одному)
- Restore PBS-бэкапа в новую ВМ/контейнер (`/qemu` create с archive=pbs volid)
Этап 2 — прямое подключение к PBS API (порт 8007), как отдельный плагин:
- регистрируется через Plugin API (`pve_center/plugins/`, dispatch по `cfg["type"]="pbs"`)
- Datastores: список, использование, история
- Sync / prune / verify jobs: просмотр, запуск, расписание
- Server-side trash и namespace поддержка

### B18. Разобраться с логикой дерева (левая панель)
Аудит и продумывание структуры левой панели: как организованы группы (B16),
кластеры, одиночные хосты, хранилища — что куда должно быть вложено.

**Аудит выполнен (2.10), фактическая структура (`tree_panel.py`):**
- Верхний уровень: пользовательские группы (B16) → секции «Clusters» →
  «Standalone hosts» → «Storage». Группы строятся из `cfg["group"]` (хост — своё,
  кластер — от любого участника).
- Кластер: агрегат `[r/t]` по всем ВМ кластера; внутри — элементы нод (листья:
  статус, тултип, заметка B19, без своих ВМ), затем группы пулов, затем ВМ без
  пула прямо на уровне кластера. Т.е. ВМ подняты на уровень кластера (view «по пулам»).
- Одиночный хост: пулы → ВМ; ВМ без пула — прямо под хостом. Модель вложенности
  отличается от кластера (там ВМ не под нодой).
- Пул может отображаться и под кластером, и под одиночными хостами (пул,
  размазанный по кластеру и standalone, виден в обоих местах) — осознанно.
- Storage: отдельная секция; в кластере — дедуп по имени («name (@cluster)»),
  отдельные — «name (host)». Хранилища не входят в группы и не вложены в хосты.
- Раскрытие дерева хранится по текстовым путям колонки 0 (суффикс `[r/t]`
  срезается); заметки B19 живут в колонке 1 и на пути не влияют.

**Найденные несостыковки (зафиксировано как follow-up, в 2.10 не трогаем):**
- Две модели вложенности: в кластере ВМ ищут на уровне кластера, у standalone —
  под нодой. Кандидат: переключатель вида кластера «по нодам / по пулам».
- Дедуп хранилищ кластера по имени маскирует per-node различия (same name,
  разное содержимое). Кандидат: раскрытие «name (@cluster)» → список нод.
- Группы B16 не включают хранилища; секция Storage игнорирует группы.
- Секции «Clusters»/«Standalone hosts» видны даже пустыми.
- Согласование с VISION.md (Site/Datacenter) — отложить до v3.x-проектирования.

### B19. Примечания к элементам дерева — РЕАЛИЗОВАНО (2.10)
Короткая пользовательская заметка для каждого элемента дерева (хост, кластер,
группа, ВМ, storage), отображаемая прямо в дереве — чтобы различать элементы
(например «тестовый», «billing», «secondary DC»).
- Хранение: таблица `tree_notes (key, note)` в config.sqlite; ключи
  `host:<name>`, `cluster:<name>`, `group:<name>`, `vm:<host>:<vmid>`,
  `storage:<name>:<scope>`; API `load_tree_notes()` / `save_tree_note()`
- Редактирование: контекстное меню «Edit note…» (многострочный диалог);
  пустая заметка удаляет запись
- Отображение: вторая колонка дерева приглушённым серым, длинные заметки
  обрезаются (полный текст в tooltip)
- Дефолт для хоста: FQDN/адрес из `cfg["host"]` (показывается, пока пользователь
  не задал свою заметку)
- PVE-теги не трогаются (локальная метка)
- Follow-up: индексация заметок в глобальном поиске (B14)
