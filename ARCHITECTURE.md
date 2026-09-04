# ARCHITECTURE.md

## Принципы

- UI не зависит от Proxmox API.
- Core не зависит от Qt.
- Источники данных взаимозаменяемы.
- Server является опциональным.

## Слои

UI
↓
Application Services
↓
Core / Domain
↓
Data Provider
↓
ProxmoxProvider | ServerProvider

## Data Provider (реализация)

Шов определён протоколом `provider.DataProvider` (см. `pve_center/provider/_provider.py`):
единая поверхность доступа — `nodes / vms / cluster / storage / tasks / pools / access / rrd` + `close()`.

- `ProxmoxProvider` — единственная реализация сегодня: фасад над `ProxmoxSession`
  (proxmoxer) и типизированными `XxxAPI`-классами; фасады создаются лениво и
  разделяют пул соединений сессии.
- Backend-воркеры (`backend.py`) зависят только от фасада `ProxmoxProvider` —
  не от API-классов напрямую; `ui/api/metrics.py` использует `provider.rrd`.
- Тесты подменяют `backend.ProxmoxProvider` целиком (фейк с атрибутами-фасадами).
- Задел v3.5: второй `ServerProvider` (pve-center server) или PBS-плагин
  реализует тот же протокол без изменения воркеров.

## Domain Model

Datacenter
Site
Cluster
Node
VM
Container
Storage
Network
Task
Snapshot
Backup
User
Tag

## Cache
- soft update
- diff объектов
- уведомления UI

## Event Bus

NodeChanged
VMChanged
TaskCreated
TaskFinished
AlertRaised

## Plugins

- Proxmox
- PBS
- Notifications
- Policies
- Reports
- Prometheus
- Redfish

### Plugins (реализация, v3.5 seed)

Шов: `pve_center/plugins/` (`Plugin`, `ProviderPlugin` — Protocol, `PluginRegistry`).

- Плагин — именованный юнит (`id`, `name`); registration явная, без динамического
  импорта. Реестр — процесс-wide singleton (`get_registry()`).
- Семейство data-source плагинов: `create_provider(cfg, timeout)` собирает
  `DataProvider` из host-конфига; диспетчеризация по `cfg["type"]` (по умолчанию `"pve"`).
  Встроен только `PvePlugin` (оборачивает `ProxmoxProvider`); PBS (B17 этап 2) и
  ServerProvider (v4.0) регистрируются как отдельные плагины.
- Backend-воркеры и `ui/api/metrics.py` создают провайдеров только через
  `plugins.create_provider(cfg)` — тип источника определяется конфигом хоста.
- Feature-плагины (Notifications, Policies, Reports, Prometheus, Redfish) —
  продолжение этого шва позже.

## Будущий Server

Desktop
↕ REST/WebSocket
PVECenter Server
- Inventory
- Cache
- History
- Event Bus
- Policy Engine
- Providers
↕
Proxmox API
