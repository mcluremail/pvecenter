# Замена CPU → ЦП в UI

## TL;DR
> **Summary**: Заменить все упоминания "CPU" на "ЦП" в русскоязычном интерфейсе (кроме API-слоя, где английские ключи обязательны)
> **Deliverables**: 4 файла с заменой строк
> **Effort**: Quick
> **Parallel**: YES — все изменения независимы

## Scope
- INCLUDE: UI-строки в файлах `detail_panel.py`, `vm_metrics_widget.py`, `vm_pool_widget.py`, `icons.py`
- EXCLUDE: `backend.py`, `metrics.py` (API-ключи), английские комментарии

## TODOs

- [ ] 1. `ui/detail_panel.py` — заменить `"CPU %"` на `"ЦП %"` (2 вхождения) и `"CPU (среднее)"` на `"ЦП (среднее)"` (1 вхождение)

  **Acceptance Criteria**:
  - `grep -c '"CPU %"' detail_panel.py` → 0
  - `grep -c '"ЦП %"' detail_panel.py` → 2

- [ ] 2. `ui/widgets/vm_metrics_widget.py` — заменить `"CPU, %"` на `"ЦП, %"` в `_render_current_metric`

  **Acceptance Criteria**:
  - `grep -c 'CPU' vm_metrics_widget.py` → 0 (кроме `"cpu"` ключей данных)

- [ ] 3. `ui/widgets/vm_pool_widget.py` — заменить `"CPU %"` на `"ЦП %"` в header labels

  **Acceptance Criteria**:
  - `grep -c '"CPU %"' vm_pool_widget.py` → 0
  - `grep -c '"ЦП %"' vm_pool_widget.py` → 1

- [ ] 4. `icons.py` — проверить, нет ли "CPU" в SVG/комментариях (поиск: `grep -i cpu icons.py`)