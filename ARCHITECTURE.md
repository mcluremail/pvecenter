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
