# PVE Center — Полный аудит
> Дата: 2026-06-08 · Модель: Antigravity / Claude Sonnet (Thinking)
> Два прохода: 1) общий код/логика/UX, 2) сверка с официальной документацией PVE API

---

## I. Баги кода

### 🔴 Критические

**B1. `_run_worker` (mainwindow.py:137) — воркеры не удаляются при ошибке**
Воркер добавляется в `_workers`, удаляется только в лямбдах сигналов.
Если сигнал не дошёл (RuntimeError, виджет уничтожен) — воркер навсегда остаётся,
забивая лимит `MAX_WORKERS=16` и останавливая все обновления.

**B2. `add_server_dialog.py:131` — `create_admin_token` блокирует главный поток**
Синхронный HTTP с таймаутом 15с выполняется прямо в GUI-потоке.
`processEvents()` — паллиатив. UI полностью замирает на время запроса.

**B3. `tree_panel.py:406–426` — двойной подсчёт ВМ на хосте**
`vms_on_host` вычислялся дважды: второй раз без фильтра по `host_name`.
При одинаковых именах нод в разных кластерах ВМ смешивались.

**B4. `tree_panel.py:643–650` — клик по нодам кластера давал данные первой ноды [ИСПРАВЛЕНО]**
Все ноды кластера имеют одинаковый `host_name`. Поиск без фильтра по `node`
всегда возвращал первую ноду. Исправлено: фильтр по `host_name AND node`.
Аналогично исправлено в `update_node_statuses` для иконок при soft refresh.

**B5. `notification.py:123` — дедупликация тостов не работает**
Ключ `str(id(text))` — адрес объекта в памяти, всегда уникален.
`_active` не защищает от дублей. При частых обновлениях тосты множатся.
Исправление: использовать `text` или `hash(text)` как ключ.

**B6. `mainwindow.py:611` — защита от устаревших задач сломана**
```python
if gen != 0 and gen != self._tasks_gen: return
```
При `gen=0` (дефолт) условие `gen != 0` — False, данные применяются без проверки.

**B7. `detail_panel.py` — кнопки ВМ не пересчитываются после действия**
После start/stop/reboot кнопки разблокируются (`setEnabled(True)` для всех),
но актуальное состояние (какие активны) не пересчитывается до следующего рефреша (20с).

**B8. `backend.py:694` — fallback `vmid=0` при ошибке nextid**
PVE отклонит создание ВМ с `vmid=0`. Нужно пробрасывать ошибку через `vm_error.emit`.

**B9. `mainwindow.py` — `_detect_status_changes` при soft_refresh использует устаревшие данные**
В `on_soft_refresh_result` вызов `_detect_status_changes()` использует `self.all_nodes`
(старые данные mainwindow), а не `self._soft_nodes` (свежие). Изменения статусов могут не замечаться.

**B10. `create_vm_dialog.py:534` — walrus-оператор поверх уже существующей переменной `name`**
```python
"name": name if (name := self.name_input.text().strip()) else None,
```
`name` уже объявлен строкой выше. Walrus создаёт новую переменную в scope выражения — мина при рефакторинге.

---

### 🟡 Архитектурные / логические

**B11. `all_pools` не инициализирован в `__init__` (mainwindow.py)**
Используется через `getattr(self, 'all_pools', [])`. Нужно добавить `self.all_pools = []` в `__init__`.

**B12. `QRunnable` запускается через `threading.Thread` вместо `QThreadPool`**
Теряются преимущества QThreadPool (авто-управление, приоритеты, отмена).
Замена: `QThreadPool.globalInstance().start(worker)`.

**B13. `soft_refresh` не обновляет `self.all_nodes`/`self.all_vms` mainwindow**
При soft_refresh данные идут в `_soft_nodes` → `detail_panel`, но `self.all_nodes` в mainwindow
не обновляется → `refresh_cluster_tasks` и `_detect_status_changes` работают со старыми данными.

**B14. Захардкоженные индексы вкладок (detail_panel.py:777–792)**
18 строк `setTabVisible(N, False)` по числовым индексам.
Добавление/перестановка вкладки ломает всё. Нужны константы или enum.

---

## II. API-аудит (сверка с документацией PVE)

### 🔴 Значимые

**A1. `StorageMetricsWorker` — RRD-данные в байтах, ось Y подписана «GiB» (metrics.py:64)**
`used` из rrddata — сырые байты. График отображает значения без деления на `1024³`.
Визуально: ~терабайты вместо гигабайт.

**A2. `StorageBackupWorker` — таймаут 10с (metrics.py:144)**
`StorageContentListWorker` для того же эндпоинта использует `timeout=60`.
Листинг бэкапов на больших хранилищах легко превышает 10с.

**A3. `HostSnapshotsWorker` + `StorageDisksWorker` — `max_workers=20` (metrics.py:327, 417)**
20 параллельных HTTP-запросов к одному PVE. PVE имеет rate limiting.
При большом кол-ве ВМ часть запросов упадёт с 429/503. Рекомендуется 4–8.

**A4. SPICE — 403 (нет `VM.Console`) маскируется как «не поддерживается» (backend.py:582)**
```python
if "not supported" in msg or "spice" in msg:
    err = "SPICE не поддерживается для этой ВМ"
```
PVE при 403 возвращает `"Permission check failed"` — без слов "not supported"/"spice".
Пользователь видит неверную диагностику. Нужна явная проверка кода 403.

---

### 🟡 Логические несоответствия с API

**A5. `HostMetricsWorker` — мёртвый fallback `net/2` (metrics.py:489–490)**
```python
elif key in ('netin', 'netout') and 'net' in entry:
    metrics[key].append({'time': t, 'value': entry['net'] / 2})
```
PVE node rrddata возвращает `netin` и `netout` как отдельные поля — `net` не существует.
Если `netin`/`netout` вдруг отсутствуют, оба получат одинаковое значение `net/2`.

**A6. SPICE — не передаётся `proxy` в POST-запрос (backend.py:579)**
```python
config = proxmox.nodes(self.node_name).qemu(self.vmid).spiceproxy.post()
```
API принимает `proxy` (адрес прокси). Без него PVE возвращает адрес ноды, где фактически
запущена ВМ — в кластере это может быть недоступная сеть.
Нужно: `spiceproxy.post(proxy=self.host_cfg["host"])`.

**A7. `FetchWorker` — `GET /pools` не возвращает `members` (backend.py:138)**
`proxmox.pools.get()` без параметров возвращает список пулов без поля `members` —
оно есть только в `GET /pools/{poolid}`.
`members` всегда `None` → `vmid_to_pool` всегда пуст → код мёртвый.
(ВМ получают пул из `cluster/resources`, так что видимой поломки нет.)

---

### 🟢 Мелкие несоответствия API

**A8. VMID минимум по API — 100, в коде — 0 (create_vm_dialog.py:176)**
`setRange(0, 999999999)`. PVE требует VMID ≥ 100. Значения 1–99 API отклонит с ошибкой.

**A9. LXC SPICE заблокирован, хотя API его поддерживает (detail_panel.py:660)**
`/nodes/{node}/lxc/{vmid}/spiceproxy` существует в API.
Либо добавить поддержку, либо уточнить сообщение об ошибке.

---

## III. Мусор / косметика

| # | Файл | Что |
|---|------|-----|
| M1 | `notification.py:67` | TODO «убрать дебаг-фичу» — но клик-копирование заявлено как фича в handoff |
| M2 | `detail_panel.py:27` | Комментарий без константы: `# Максимум воркеров в detail_panel` |
| M3 | `create_vm_dialog.py:137` | `_grid(rows, cols)` — параметры принимаются, нигде не используются |
| M4 | `tree_panel.py:538` | `import re as _re` внутри `@staticmethod` — на каждый вызов |
| M5 | `theme.py:505` | `QFont.PreferAntialias` — deprecated в Qt6, нужно `QFont.StyleStrategy.PreferAntialias` |
| M6 | `backend.py:771` | Trailing blank line |
| M7 | `mainwindow.py:17–18` | `logger` объявлен, следом сразу импорт — не в блоке импортов |
| M8 | `config.py:9` | `nodes.enc` рядом с кодом, а не в `~/.config/pve-center/` |

---

## IV. UX/UI

1. **Stop/Reset без подтверждения** — принудительные операции без диалога
2. **Добавление сервера зависает** — `create_admin_token` в GUI-потоке, 15с таймаут
3. **Нет индикатора фонового обновления** — пользователь не знает, идёт ли рефреш
4. **Эмодзи в кнопках** — на Linux без emoji-шрифта рендерятся как квадраты
5. **Вкладка «ВМ хоста» — иконка диска** вместо иконки ВМ (`detail_panel.py:181`)
6. **Прогресс-бары CPU/RAM** — один синий цвет при любой нагрузке (нет зелёный/жёлтый/красный)
7. **Сплиттер 280px** — узковато, положение не сохраняется через QSettings
8. **QSpinBox для VMID** — крутилка бесполезна, лучше QLineEdit с валидатором
9. **Статус в дереве и тостах** — английские значения (`running`, `stopped`) вместо русских
10. **Пустое дерево** — нет подсказки «нажмите + чтобы добавить сервер»
11. **`add_server_dialog.py:126`** — «Создание пользователя и токена...» — пользователь не создаётся
12. **Шрифт Terminus** — на HiDPI выглядит плохо, рассмотреть JetBrains Mono

---

## V. Что исправлено в ходе аудита

| Файл | Что |
|------|-----|
| `ui/tree_panel.py` | Клик по нодам кластера: поиск `host_data` по `host_name AND node` вместо только `host_name` |
| `ui/tree_panel.py` | `update_node_statuses`: иконки статусов нод при soft refresh — та же правка |

---

## VI. Аудит правок DeepSeek (сессия 2026-06-08, второй проход)

### Что DeepSeek исправил корректно

Большинство пунктов из аудита B1–B14, A1–A9 закрыты:
QThreadPool, спиннер, TabIndex enum, _update_action_buttons, диалог stop/reset,
SVG-иконки, max_workers=8, timeout=60, RRD /1024³, TokenCreationWorker,
proxy в spiceproxy, LXC SPICE, 403-диагностика, /pools/{id} для members,
_config_dir() + миграция, QLineEdit для VMID, STATUS_RU, пустой экран в дереве.

---

### 🔴 Новые баги, внесённые DeepSeek

**N1. `_on_action_finished` пересчитывает кнопки по устаревшему статусу (detail_panel.py)**
```python
def _on_action_finished(self, msg):
    self._update_action_buttons(self._last_vm_data)  # статус ещё СТАРЫЙ
```
`self._last_vm_data` содержит статус ДО действия. После `start` статус всё ещё `"stopped"` →
кнопка Start остаётся активной. Правильно: пересчитывать после `_refresh_after_action`,
когда пришли свежие данные.

**N2. `TokenCreationWorker` создан, но не использован (backend.py / add_server_dialog.py)**
Новый воркер есть в `backend.py`, но `add_server_dialog._on_auth` по-прежнему вызывает
синхронный `create_admin_token` в GUI-потоке. Баг B2 (блокировка UI) не исправлен.

**N3. `config.py` — `SALT_FILE` не мигрируется**
```python
for fn in (ENC_FILE, CONFIG_JSON):   # SALT_FILE пропущен
    _migrate_if_needed(fn)
```
`nodes.salt` остаётся рядом с кодом. `load_config` после миграции ищет salt
по `_config_dir()`, где его нет → расшифровка упадёт при первом запуске после переезда.

**N4. SVG-иконки `_RESET` и `_REBOOT` идентичны (icons.py)**
Copy-paste: `_RESET` — точная копия `_REBOOT`. Кнопки визуально неразличимы.

### 🟡 Спорные моменты

**S1. `import logging` продублирован в mainwindow.py**
Строка 6 (оригинал) + строка 19 (добавлена DeepSeek). Второй перезаписывает первый
с тем же результатом. Мусор.

**S2. `_on_action_error` — неявное поведение кнопок**
После ошибки `_update_action_buttons(self._last_vm_data)` пересчитывает по старому статусу.
Формально корректно (действие не выполнилось, ВМ в исходном состоянии), но неочевидно.

---

### 📊 SQLite — вывод

Оправдан как отдельный `~/.config/pve-center/cache.db` для:
- истории задач (сейчас не персистируется между запусками)
- кеша метрик (сейчас dict в памяти, живёт сессию)
- лога изменений статусов

Не нужен для конфига нод и токенов — шифрованный файл проще и безопаснее.
Полный перевод конфига на SQLite избыточен и создаст зависимость от миграций схемы.
