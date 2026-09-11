# Конкуренты pve_center — обзор (2026-09-10)

Зачем: для планирования v3.0 нужно понять, с кем соревнуемся и за счёт чего
быть лучше. Методика: поиск по GitHub (stars, стек, активность) + чтение
README/TODO проектов. Внешние обзоры App Store / форумов — отдельно, здесь
только опенсорс и официальный клиент.

## Главный вывод

Прямых desktop-аналогов pve_center (multi-cluster + управление ВМ/хранилищами
+ бэкапы + консоли в одном окне) **нет**. Рынок разбит на ниши:

1. **Официальный web GUI** — эталон по покрытию API; главный соперник по
   «полезной работе».
2. **Агрегаторы multi-cluster** — ниша больше не пуста: официальный
   **Proxmox Datacenter Manager** и коммерческий **ProxCenter** закрывают
   «агрегацию» (см. ниже). Их общий формат: web + отдельный сервер.
3. **VDI-лаунчеры** — только консоли, без управления.
4. **Мониторинг-панели** — только наблюдение и алерты.
5. **Скрипты/моды/темы** — заполняют UX-дыры web GUI (тёмная тема с ★2540 —
   прямой спрос на современный визуал).

**Итог для стратегии:** запрос подтверждён деньгами и штатом (PDM — целое
направление Proxmox GmbH; ProxCenter — enterprise-клиенты), но desktop-ниша
(запустил приложение → работаешь, без установки сервера) **свободна**.
Агрегация — не уникальность, уникальность = **агрегация без сервера,
на рабочем столе, со скоростью**. Позиционирование: «PDM для человека».

## Коммерческие и официальные агрегаторы

| Продукт | Формат | Цена | Функционал | Слабости |
|---|---|---|---|---|
| [Proxmox Datacenter Manager](https://www.proxmox.com/en/products/proxmox-datacenter-manager/overview) | Web, отдельный сервер (AGPL) | Бесплатен; поддержка/обновления — за Enterprise-подписку PVE | Агрегация PVE+PBS, live-миграция между кластерами, мощный поиск, custom views, LDAP/AD/OIDC, RBAC, EVPN-SDN, update management | Server+web (не desktop); сыроват для реальной работы (альфа-период 2024–25, UX в процессе); enterprise-заточен |
| [ProxCenter](https://www.proxcenter.io) | Web, Docker self-hosted | Community free; Enterprise — лицензия | Дашборд drag-drop, инвентарь, PBS-мульти, Ceph-мониторинг; Enterprise: DRS, cross-cluster replication, LDAP/SSO, AI-аналитика, миграция с ESXi/XCP-ng/Nutanix/Hyper-V | Не desktop; киллер-фичи за деньгами; web-зависимости |
| PegaProx | Web | Free (заявлено) | Мульти-кластер PVE+XCP-ng, cross-cluster миграции, load balancing, аудит | Молодой проект, зрелость неясна |
| [ProxUI](https://github.com/greenlogles/ProxUI) | Web | Free (опенсорс) | Современный UI, mobile-подход, мульти-кластер, cloud-шаблоны | Молодой, масштаб неизвестен |

Сигналы: ProxCenter имеет enterprise-клиентов (Bouygues, Millennium, EPI-USE,
Atomic Data и др.) и прессу («vCenter-опыт для Proxmox», StarWind, Virtualization
Howto). Вывод: **платят за готовое управление мульти-кластером** — наш сегмент
подтверждён; при этом ни один из них не desktop.

## Реестр

### Desktop-клиенты (прямая ниша)

| Проект | ★ | Стек | Функционал | Слабости UX |
|---|---|---|---|---|
| [PVE-VDIClient](https://github.com/joshpatten/PVE-VDIClient) | 1092 | Python, tkinter | VDI-брокер: логин → список ВМ по правам → SPICE; multi-cluster «server groups»; MSI для массового деплоя | tkinter-UI; только консоли: нет CRUD, бэкапов, мониторинга; конфиг через ini-файл |
| [Proxmox-Desktop-Client](https://github.com/sakakun/Proxmox-Desktop-Client) | 168 | C#/WPF, Windows | Список ВМ + power actions; noVNC/SPICE/xtermJS; WebView-панель с автологином в web GUI | Windows-only; авто-refresh 60 с; нет управления (создание/миграция/storage/бэкапы) |
| [proxmanager](https://github.com/pauloswear/proxmanager) | 157 | Python, PyQt5 | Дашборд одной ноды (CPU/RAM/load), quick actions start/stop/reboot, SPICE/VNC/RDP, папки серверов | В TODO самого автора: спиннеры на кнопках (сейчас блокирующие), noVNC без webui; Linux не проверен; один нод |
| [cv4pve-vdi](https://github.com/Corsinvest/cv4pve-vdi) | 126 | C# | Лаунчер консолей SPICE/VNC/RDP/SSH из трея | Утилита-лаунчер, не клиент управления |

### Мониторинг / дашборды

| Проект | ★ | Что делает | Чему учит |
|---|---|---|---|
| [Pulse](https://github.com/rcourtman/Pulse) | 6689 | Web-мониторинг PVE/PBS/Docker/k8s/TrueNAS: метрики, умные алерты, «AI-патрули», верифицированные фиксы | Зона «наблюдение» уже занята сильным web-продуктом; desktop-клиенту нужен Pulse-лайт (пороги + уведомления), не дублирование |
| [ProxMenux](https://github.com/MacRimi/ProxMenux) | 2962 | Меню-тулкит post-install + live web-дашборд | Спрос на «быстрый обзор без входа в GUI» |

### Экосистема web GUI (косвенные сигналы)

- [PVEDiscordDark](https://github.com/Weilbyte/PVEDiscordDark) ★2540 — тёмная
  тема для web UI: **спрос на современный визуал огромен**.
- PVE-mods ★1908, pvetools ★5272, community-scripts ★29.5k — пользователи
  массово дорабатывают web GUI скриптами = его UX их не устраивает.

### Не конкуренты (справочно)

- API-библиотеки: go-proxmox (285★), terraform-провайдеры (bpg ★2220),
  proxmoxer — инфраструктура, не UI.
- TUI: proxxx (Rust/ratatui, 26★), bash-TUI менеджеры — терминальная ниша.
- Мобильные: bVNC/remote-desktop-clients (★2505) — консоли на Android;
  зрелых мобильных клиентов управления нет.

### Другие системы виртуализации (что передираем, 2026-09-10)

Проверены Xen Orchestra (XCP-ng), Nutanix Prism, SCVMM/RHV/Harvester.

| Источник | Фича | Вердикт |
|---|---|---|
| Xen Orchestra | Incremental/Continuous Replication + DR (standby-копии на другом пуле) | Полный аналог требует живого планировщика; берём идею **«DR-режим»**: bulk-restore парка из PBS в другой кластер одной кнопкой (идеи без вехи) |
| Xen Orchestra | Load Balancing | Мимо — server-часть, не desktop-архитектура |
| Xen Orchestra | Rolling Pool Upgrades | Мимо — update management отвергнут (опасная зона) |
| Nutanix Prism | Capacity Runway / What-if (прогноз «кончатся через N дней», сценарии добавления нагрузки) | Берём в идеи: **capacity forecasting** — чисто клиентские расчёты поверх уже собираемых rrddata |
| Nutanix Prism | One-click ops, predictive ML | Мимо (ML-инфраструктура) |
| SCVMM/RHV | Quotas, self-service, hosted engine, dynamic optimization | Мимо — всё server-side, desktop-клиенту нечего взять |
| vSphere/vCenter | Maintenance Mode | **Берём** — веха M4 (у PVE нативного нет, оркестрируем сами) |
| vSphere/vCenter | Affinity/Anti-affinity rules | Берём в идеи (`/cluster/ha/rules`, PVE 9 — API есть, UI нет ни у кого) |
| vSphere/vCenter | Alarms, inventory reports | Уже в плане (M8-алерты, отчёты в идеях) |

Общий принцип, зафиксированный 2026-09-10: **ориентир по фичам — лидер рынка
(vSphere)**; передираем то, что реализуемо без постоянно живущего сервера.

## Боли конкурентов, валидирующие нашу стратегию

1. **Блокирующий UI**: proxmanager честно пишет в TODO «добавить спиннеры на
   кнопки»; web GUI подвисает на больших кластерах. → Скорость и нулевая
   блокировка UI — рабочий дифференциатор, а не абстракция.
2. **Медленная свежесть данных**: Proxmox-Desktop-Client — refresh раз в
   60 секунд. → У нас фон-обновление 20 с + optimistic UI.
3. **Один нод / один кластер**: proxmanager (нода), VDI-клиенты (список ВМ).
   → Multi-cluster-first остаётся нашим преимуществом.
4. **Нет PBS в desktop-нише**: у всех консоль-клиентов ноль про бэкапы.
   → Наша PBS-интеграция уникальна для desktop.
5. **Визуал**: главный «конкурент» по красоте — тема PVEDiscordDark.
   → Современная тема (тёмная/светлая) в 3.x обязательна.

## Сравнение с pve_center (v2.13)

Уже впереди desktop-ниши: multi-cluster дерево, CRUD ВМ/CT/storage,
backup jobs, PBS-панель, noVNC, массовые операции, 5 локалей, 806 тестов.
Отстаём/дыры: нет тем, нет командной палитры, нет SSH/RDP-лаунчера, нет
алертов; UI-паритет с офиц. PVE неполный (~80% сценариев) — карта дыр в
FEATURES_BACKLOG B23; API-поверхность: ~12–15% эндпоинтов PVE (449 путей /
680 endpoint'ов в apidoc), осознанные 80% сценариев админа.

Ответ конкурентам по киллер-фичам (план 3.0): **Fleet Health** (M4 —
health несвязанных кластеров одним взглядом, ни у кого нет), maintenance
mode (M5 — аналог vSphere), desktop-алерты (M9), движок тем-плагинов
(M1 — ответ PVEDiscordDark). Cross-cluster move — потенциал подтверждён
(ни у кого нет GUI), реализация on hold до тестовой инфраструктуры
(B21). Полная карта агрегации (PDM/ProxCenter) при этом не копируется:
наш формат — без сервера.

## Источники

GitHub Search API (2026-09-10), README перечисленных репозиториев,
proxmox.com (PDM), proxcenter.io, duckduckgo-поиск по XO/Nutanix (2026-09-10),
apidoc.js (PVE API, 449 путей). Обновлять перед каждым циклом планирования
мажора.
