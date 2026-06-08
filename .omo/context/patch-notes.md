# PVE Center — Patch Notes (сессия 2026-06-08, Antigravity/Claude Sonnet)

---

## Исправление: клик по нодам кластера не обновлял инфу

**Файл:** `ui/tree_panel.py`

**Метод 1: `_on_item_clicked` (~строка 643)**

**Проблема:**  
Все ноды кластера имеют одинаковый `host_name` (имя кластерного конфига, e.g. `"my-cluster"`).  
Поиск `host_data` шёл только по `host_name` → `next()` всегда возвращал **первую ноду** в `all_nodes`, независимо от того, какую кликнул пользователь. Все ноды кластера отображали данные первой ноды.

**Исправление:**  
Добавлен фильтр по `node == item_name` (PVE-имя ноды, e.g. `"pve1"`, `"pve2"`).  
Т.е. теперь поиск: `host_name == host_name_key AND node == item_name`.  
Fallback на только `host_name` если строгий поиск ничего не нашёл (standalone-кейс).

```python
# БЫЛО:
host_data = next((n for n in self.all_nodes
                  if n.get("host_name") == host_name_key), None)

# СТАЛО:
host_data = next((n for n in self.all_nodes
                  if n.get("host_name") == host_name_key
                  and n.get("node") == item_name), None)
if host_data is None:
    host_data = next((n for n in self.all_nodes
                      if n.get("host_name") == host_name_key), None)
```

---

**Метод 2: `update_node_statuses` (~строка 522)**

**Проблема:**  
Та же логика — при soft refresh иконки статусов нод в дереве брали статус первой ноды кластера для всех остальных.

**Исправление:**  
Аналогично — фильтр по `host_name AND node`, fallback на только `host_name`.

```python
# БЫЛО:
host = next((n for n in all_nodes if n.get("host_name") == hn), None)

# СТАЛО:
host = next((n for n in all_nodes
             if n.get("host_name") == hn
             and n.get("node") == node_name), None)
if host is None:
    host = next((n for n in all_nodes if n.get("host_name") == hn), None)
```

---

## Контекст

- `ITEM_KEY_ROLE` для host-элементов: `("host", node_name, host_name)`, где:
  - `node_name` = короткое PVE-имя (`pve1`, `pve2`)
  - `host_name` = имя конфига (`"my-cluster"` для кластера, само имя для standalone)
- Кластерные ноды: в `all_nodes` все имеют одинаковый `host_name` (кластерный конфиг), но разный `node`.
