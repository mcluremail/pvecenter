# UX/UI предложения — PVE Center (полный аудит)
**Дата:** 2026-06-09  
**Статус:** финальная версия после полного прочтения всего кода

---

## 🔴 Критические UX-баги (мешают работе прямо сейчас)

### UX-БАГ-1: `VmHardwareWidget` и `VmOptionsWidget` — поиск raw_key по label O(n) нестабилен

**Файл:** `ui/widgets/vm_hardware_widget.py:63`, `ui/widgets/vm_options_widget.py:63`

```python
raw_key = next((k for k, v in HW_LABELS.items() if v == label), None)
```

`HW_LABELS` — dict. Если два разных ключа имеют одинаковый label (например, кастомные диски) — редактор откроется для первого попавшегося ключа. Пользователь отредактирует не тот параметр.  
**Решение:** хранить `raw_key` в `UserRole` каждой строки при `set_hardware_data` / `set_options_data`, не искать по label.

---

### UX-БАГ-2: `_format_and_set` в `VmMetricsWidget` вызывает `plot.clear()` и `plot.addLegend()` на каждый рендер

**Файл:** `ui/widgets/vm_metrics_widget.py:141, 162`

```python
self.plot.clear()
# ...
self.plot.addLegend()  # создаёт новый LegendItem каждый раз!
```

Каждая смена метрики «Сеть» или «Диск» добавляет ещё один `LegendItem` поверх предыдущего. Легенда визуально дублируется и растёт бесконечно.  
**Решение:** сохранить `legend = self.plot.addLegend()` в `__init__`, при смене метрики делать `legend.clear()` вместо пересоздания.

---

### UX-БАГ-3: `show_disk_io` — сбрасывает текущую метрику на «ЦП» даже когда не нужно

**Файл:** `ui/widgets/vm_metrics_widget.py:71-83`

При каждом вызове `show_disk_io()` метод очищает и перезаполняет `metric_combo` — что вызывает `currentTextChanged` → `_on_metric_changed` → `_render_current_metric`. Если данные ещё не пришли (`_cached_data=None`) — нет видимого эффекта, но сигнал всё равно летит вхолостую.  
**Решение:** сравнивать текущий список элементов с новым перед очисткой — не делать ничего если набор не изменился.

---

### UX-БАГ-4: `AddServerDialog` — поле «Токен: Значение» показывается в открытом виде навсегда

**Файл:** `ui/add_server_dialog.py:71-72`

```python
self.token_value_label = QLabel("—")
self.token_value_label.setStyleSheet("font-family: monospace; color: #22c55e;")
```

После нажатия «Получить токен» токен отображается открыто в диалоге. Если пользователь сделает скриншот / запись экрана — токен утечёт. Рядом нет кнопки «Скопировать».  
**Решение:** показывать `••••••••` с кнопкой «👁» (показать/скрыть) и кнопкой «📋 Скопировать».

---

### UX-БАГ-5: `CreateVmDialog` — VMID «авто» означает 0, который PVE отвергает

**Файл:** `ui/create_vm_dialog.py:569`

```python
vmid = int(vmid_text) if vmid_text else 0
```

И в `get_params()`:
```python
if vmid > 0:
    params["vmid"] = vmid
```

Если поле пустое → `vmid=0` → не включается в params → PVE назначает сам (это правильно). Но поле имеет `placeholder="авто"` и валидатор `QIntValidator(100, 999999999)`. Если пользователь наберёт «99» (< 100) — validator не пустит, но ошибки нет — поле просто не даёт ввод. Непонятно почему не работает.  
**Решение:** добавить `QLabel` под полем: «Минимальный VMID: 100» или убрать валидатор и валидировать в `_on_create`.

---

## 🟡 Средние UX-проблемы

### UX-6: Двойной клик на `VmHardwareWidget` — `"readonly"` поля открывают диалог, но сразу отклоняются

**Файл:** `ui/widgets/vm_hardware_widget.py:64`

```python
if not raw_key or raw_key not in _FT:
    return
```

Поля `"vmgenid"`, `"running-machine"`, `"running-qemu"` присутствуют в `FIELD_TYPES` с типом `"readonly"`. `VmConfigEditorDialog` получает тип `"readonly"` и... что делает? Нужно проверить, но скорее всего либо показывает пустой диалог, либо падает.  
**Решение:** проверять `if ft_type == "readonly": return` до открытия диалога. Добавить курсор `Qt.ForbiddenCursor` для readonly-строк.

---

### UX-7: `VmTaskHistoryWidget` — время показывается в UTC, не в локальном времени

**Файл:** `ui/widgets/vm_task_history_widget.py:42-43`

```python
start_dt = datetime.fromtimestamp(float(start_ts), tz=timezone.utc)
start_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
```

`fromtimestamp(..., tz=timezone.utc)` + `strftime` без `astimezone()` → всегда UTC. Пользователь в Москве (UTC+3) видит «09:03» вместо «12:03».  
**Решение:** убрать `tz=timezone.utc` → `datetime.fromtimestamp(float(start_ts))` — это даёт локальное время.

---

### UX-8: `cluster_tasks_widget` — колонка «Статус» не переводится

**Файл:** `ui/widgets/cluster_tasks_widget.py` (строки с заполнением)

PVE возвращает статус задачи как `"OK"`, `"RUNNING"`, `"ERR:..."`, `"WARNING:..."`. В таблице показывается raw-строка из API. «OK» и «RUNNING» пользователь поймёт, но `"ERR: command 'pvesh...' failed with exit code 2"` занимает всю ширину колонки.  
**Решение:** обрезать длинные статусы до 30 символов + tooltip с полным текстом.

---

### UX-9: `_show_host_info` — при ошибке хоста вкладка «Мониторинг» остаётся активной, но пустая

**Файл:** `ui/detail_panel.py:2235`

```python
self.tabs.setCurrentIndex(TabIndex.MONITOR)
return
```

При хосте с ошибкой показывается только `info_label` с текстом ошибки, но вкладки «Мониторинг» и «Оборудование» видны (хотя `HARDWARE` не скрывается явно в этой ветке). Клик на «Мониторинг» показывает пустой график.  
**Решение:** при `status == "error"` скрывать ВСЕ вкладки кроме одной «сводной».

---

### UX-10: `_show_cluster_folder` — при 0 кластерах таблица пустая без пояснения

**Файл:** `ui/detail_panel.py:1439`

Если все хосты standalone (нет ни одного кластера) — пользователь кликает «Кластеры» → видит пустую таблицу. Нет сообщения «Кластеры не настроены».

---

### UX-11: `CreateVmDialog` — нет валидации имени ВМ (допустимые символы)

**Файл:** `ui/create_vm_dialog.py:553-557`

```python
if not name:
    self.name_input.setFocus()
    self.name_input.setStyleSheet("border: 1px solid #ef4444;")
    return
```

Проверяется только непустота имени. PVE принимает только `[a-zA-Z0-9\-._]` для имени ВМ. Имя «мой сервер» пройдёт валидацию в диалоге, но будет отклонено API.  
**Решение:** `QRegularExpressionValidator(QRegularExpression(r"[a-zA-Z0-9\-._]+"))` на поле `name_input`.

---

### UX-12: `NotificationManager` — несколько тостов перекрываются (не стекуются)

**Файл:** `ui/notification.py:122-123`

```python
toast = FadeToast(self.parent, text, color)
# позиция: parent.y() + 12 для всех тостов
```

Все тосты рождаются в одной и той же точке `(parent_width - toast_width - 20, 12)`. При одновременном изменении статуса 3 ВМ — 3 тоста на одном месте, читается только верхний.  
**Решение:** в `_show` передавать `offset_y` как сумму высот активных тостов + отступ.

---

## 🟢 Улучшения UX (низкий приоритет)

### UX-13: `vm_summary_table` — нет `setTextInteractionFlags`

**Файл:** `ui/detail_panel.py:162-177`

`vm_summary_table` — основная таблица с IP, VMID, именем хоста. `setTextInteractionFlags` не установлен → нельзя выделить мышью. `info_label` (строки 158) — `TextSelectableByMouse` установлен, таблица — нет.  
**Решение:** `self.vm_summary_table.setTextInteractionFlags(Qt.TextSelectableByMouse)` или `setSelectionMode(SingleSelection)` с копированием по Ctrl+C.

---

### UX-14: `VmMetricsWidget.set_ram_range` — заглушка, не реализована

**Файл:** `ui/widgets/vm_metrics_widget.py:90-91`

```python
def set_ram_range(self, max_bytes):
    pass
```

Метод объявлен, но не реализован. Означает, что ось Y для RAM всегда авто-ренжится — при маленьком потреблении RAM график занимает весь экран. Правильно — `setYRange(0, max_bytes / 1024**3 * 1.1)`.  
Нигде в коде `set_ram_range` не вызывается → мёртвый метод.

---

### UX-15: `add_server_dialog` — нет кнопки «Тест соединения» без создания токена

**Файл:** `ui/add_server_dialog.py`

Если у пользователя уже есть токен (не хочет создавать новый) — нет поля ввода существующего токена. Нужно идти через «Получить токен» → вводить пароль.  
**Решение:** добавить переключатель «Создать токен» / «Ввести вручную» — при «вручную» показывать 3 поля: имя, ID и значение токена.

---

### UX-16: `_show_vm_info_init` — вкладки Снапшоты, Сеть скрыты для ВМ навсегда

**Файл:** `ui/detail_panel.py:2398-2406`

`_show_vm_info_init` показывает вкладки `MONITOR, HARDWARE, OPTIONS, HISTORY`. Снапшоты ВМ — показываются только когда кликаешь на хосте. При клике на ВМ — снапшотов нет.  
**Решение:** добавить вкладку Снапшоты и в `_show_vm_info_init` — и загружать снапшоты конкретной ВМ.

---

### UX-17: `_header_duplicate` — `setDefaultAlignment` и `setStyleSheet` дублируются 2 раза подряд в каждой таблице

**Файл:** `ui/detail_panel.py` (строки 280-284, 319-321, 355-357, 460-465, ...)

Паттерн повторяется для каждой из 14 таблиц:
```python
self.table.horizontalHeader().setDefaultAlignment(...)
self.table.horizontalHeader().setStyleSheet(...)

self.table.horizontalHeader().setDefaultAlignment(...)  # ← дубль!
self.table.horizontalHeader().setStyleSheet(...)        # ← дубль!
```

Это визуальный мусор — не влияет на работу, но засоряет `__init__` (280+ строк лишних вызовов).  
**Решение:** вынести в helper `_configure_header(table)`.

---

## Итог по новым находкам

| # | Проблема | Приоритет |
|---|----------|-----------|
| UX-БАГ-1 | raw_key поиск нестабилен → редактор открывается не для того поля | 🔴 Критический |
| UX-БАГ-2 | `addLegend()` дублируется → легенда растёт | 🔴 Критический |
| UX-БАГ-7 | Время задач в UTC вместо локального | 🔴 Критический (заметно сразу) |
| UX-БАГ-3 | `show_disk_io` лишний сигнал | 🟡 Средний |
| UX-БАГ-4 | Токен отображается открыто | 🟡 Средний |
| UX-БАГ-5 | VMID валидатор без ошибки | 🟡 Средний |
| UX-6 | readonly поля открывают диалог | 🟡 Средний |
| UX-8 | Длинный статус задачи рвёт колонку | 🟡 Средний |
| UX-11 | Нет валидации имени ВМ | 🟡 Средний |
| UX-12 | Тосты перекрываются | 🟡 Средний |
| UX-9,10,13,14,15,16,17 | Прочие улучшения | 🟢 Низкий |
