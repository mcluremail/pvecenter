# История изменений — PVE Center

## 2026-06-08 — Производительность загрузки

**Главное: экран перестал висеть при старте приложения.**

### Сделано

1. **FetchWorker — параллельные API-вызовы (backend.py)**
   - Раньше ~15 последовательных HTTP-запросов на кластерную репу
   - Теперь три параллельные фазы: pools + HA + resources одновременно, storage details по нодам параллельно, ISO по нодам параллельно
   - Для standalone: pools и данные ноды параллельно

2. **Status bar — сразу при первом воркере (mainwindow.py)**
   - `_update_status_bar()` вызывается после каждого воркера
   - Пользователь видит частичные данные: `Хостов: 1/3 ВМ: 12`

3. **Загрузка задач — с первым воркером (mainwindow.py)**
   - `refresh_cluster_tasks` стартует при первом же `on_worker_finished`, а не в финале
   - Guard `_tasks_started` от дублирования

4. **Сводка кластера — без задержки (mainwindow.py)**
   - `_do_first_selection()` вызывается **до** `_build_tree` (который с сотнями VM)
   - Сводка рендерится мгновенно, дерево достраивается после

5. **`_do_first_selection()` вынесен в метод (mainwindow.py)**
   - Убрана копипаста промежуточного и финального селекта

### Статусы всех багов

| Баг | Статус |
|-----|--------|
| Спиннер кластера гаснет — кластер исчезает в середине загрузки | Исправлен (incremental tree: `final=False` не трогает спиннеры, `_build_tree` подмешивает заглушки из `nodes_cfg`) |
| Панель задач не грузит standalone — поиск конфига по `pve_node` вместо `host_name` | Исправлен |
| Производительность: панель задач медленно появлялась — `singleShot(1000)`, новый TLS handshake, блокировка QThreadPool | Исправлен (убрал `singleShot(1000)`, кэш, `threading.Thread` вместо QThreadPool, стартует с первым воркером) |
| Кэш задач в памяти не переживал перезапуск | Исправлен (SQLite в `~/.config/pve-center/tasks_cache.sqlite`) |
| Долгая загрузка дерева, статусбара и сводки кластера | Исправлен (параллельный FetchWorker, ранний статусбар, селект до _build_tree) |

---

## 🔴 БАГ: Спиннер кластера гаснет и кластер исчезает из дерева при прилёте данных отдельного хоста

**Статус:** Исправлен  
**Файлы:** `ui/tree_panel.py`, `ui/mainwindow.py`

### Решение

`update_data` разделён на два режима через `final=False/True`:
- **Промежуточный** (`final=False`) — не трогает `_loading_hosts` и спиннеры
- **Финальный** (`final=True`) — `_loading_hosts.clear()` + `_spin_timer.stop()`

`_build_tree` подмешивает кластеры из `nodes_cfg`, для которых нет нод в `all_nodes` — они остаются в дереве с иконкой спиннера.

Ключевые изменения:
- `update_data(self, ..., final=False)` — промежуточное обновление без очистки спиннеров
- `_build_tree` — шаг 2: добавляет пустые кластеры из `nodes_cfg` в `cluster_nodes`
- Вызов 1 из `on_worker_finished`: `final=False`
- Вызов 2 (когда все воркеры завершились): `final=True`

---

## 🔴 БАГ: Нижняя панель задач не грузит задачи для standalone-хостов

**Статус:** Исправлен  
**Файл:** `ui/mainwindow.py`

### Решение

Поиск конфига по `host_name` (cfg["name"]), а не по `pve_node` (PVE short name).

```python
cfg = next((c for c in self.nodes_cfg if c.get("name") == host_name), None)
if cfg is None:
    cfg = next((c for c in self.nodes_cfg if c["name"].split("@")[0] == pve_node), None)
```

Кластерные ноды ищутся через `cluster_rep`, standalone — через `host_name`.

---

## 🟡 ПРОИЗВОДИТЕЛЬНОСТЬ: Панель задач появлялась медленно

**Статус:** Исправлен  
**Файлы:** `ui/mainwindow.py`, `backend.py`

### Сделано

1. **Убран `singleShot(1000)`** — первая загрузка из `on_worker_finished` при первом же воркере
2. **Кэш задач** (`self._cached_tasks`) — показывает кэш мгновенно при повторных запросах
3. **ClusterTasksWorker** — запускается в `threading.Thread`, не блокирует QThreadPool
4. **Загрузка стартует при первом воркере** — не ждёт все FetchWorker-ы

---

## ✅ ИСПРАВЛЕНО: Кэш задач не переживал перезапуск приложения

**Статус:** Исправлен (SQLite)  
**Файл:** `config.py`, `ui/mainwindow.py`, `ui/widgets/cluster_tasks_widget.py`

### Решение

SQLite в `~/.config/pve-center/tasks_cache.sqlite`:
- `config.py`: `save_tasks_cache()` / `load_tasks_cache()` с `threading.Lock`
- `mainwindow.py`: загружает при старте, сохраняет при каждом обновлении
- `ClusterTasksWidget.set_placeholder()`: строка-заглушка пока кэша нет

| Запуск | Что видит пользователь |
|--------|------------------------|
| Первый (кэша нет) | "Загрузка задач..." → через ~3-8с реальные задачи |
| Повторный | Задачи с прошлого раза мгновенно → через ~3-8с свежие |