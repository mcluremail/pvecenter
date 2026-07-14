# Changelog

## v2.9.0 — VM templates, cloning, audit fixes, update check

**New features**
- VM templates: convert QEMU VM ↔ template (context menu + detail panel buttons)
- Clone from template: host context menu shows templates, clone dialog picks template then target
- Template-aware UI: template VMs get distinct icon in tree, lifecycle/migrate/console actions disabled for templates
- LXC console: VNC proxy support (was SPICE-only, always failed for containers)
- Automatic update check: fetches GitHub releases on startup, notifies if newer version available

**Bug fixes (audit)**
- Tree soft refresh: template VMs now show template icon (was reverting to VM status icon)
- Worker pool exhaustion: user now gets notification when max concurrent workers reached (was silent)
- DeleteVmWorker: LXC containers now deleted via lxc endpoint (was always QEMU endpoint)
- VmConsoleWorker: LXC uses VNC proxy, QEMU uses SPICE (was SPICE for both)
- _on_vm_convert: pre-checks VM is stopped before converting to template
- _on_vm_action_from_tree: rejects lifecycle actions for templates
- _on_vm_migrate: rejects migration for templates
- Dead code: removed unused `suspend` from _CONFIRM_ACTIONS/_CONFIRM_MESSAGES
- Signal consistency: `vm_clone_from_template_requested` now `(host_name, node)` order

## v2.8.1 — audit bug fixes

**Bug fixes (18 issues)**
- LXC restore: used `hostname` param instead of `name`; `unique` only sent for QEMU VMs
- PVE8 `/cluster/jobs`: filtered to `vzdump` type only (was returning all job types)
- Removed dead `/cluster/replication` API call (endpoint doesn't exist)
- PVE8 job create/update: now includes `type=vzdump` param (was falling back to PVE7)
- ClusterJobUpdateWorker: `id` stripped from PUT body (was causing HTTP 400)
- BackupJobDialog: weekday names now translatable (`tr()` at call time, not module load)
- BackupJobDialog: `prune-backups` parsing handles `keep-last=N` format
- BackupJobDialog: Save button disabled + warning shown when no backup storages
- BackupJobDialog: `bool("0")` == True bug for `enabled` field (now `int()`)
- BackupJobDialog: removed dead `is_pve8` parameter
- VzdumpDialog: canonical i18n key `Backup VM {vmid}`
- VM backup tab: storage name now shown in Storage column (was always empty)
- VM backup tab: generation guard prevents cross-VM data corruption on rapid switch
- Cluster snapshots: crash fix — `data` is a list, not dict (was calling `.items()`)
- Cluster storage aggregation: filtered by cluster name (was summing all clusters)
- Cluster health tab: completion check for hosts without config
- Backup jobs: fetched for cluster-member hosts via cluster config
- TabIndex.HARDWARE: now hidden on type switch (was always visible)
- Notification: `online→online` no longer shows spurious warning toast
- Notification: `vm_status_changed` unused `old_status` parameter removed

## v2.8.0 — vzdump backup & restore, backup jobs, cluster tabs

**New features**
- VM on-demand backup (vzdump): storage, mode (snapshot/suspend/stop), compression (none/gzip/lzo/zstd), notes, remove-old, bandwidth limit
- VM restore from backup: new VMID auto-suggest, target storage, force overwrite, unique MAC
- Backup jobs scheduling: add/edit/remove jobs with Daily/Weekly/Custom schedule, retention, compression — supports both PVE 8+ (`/cluster/jobs`) and PVE 7 (`/cluster/backup`)
- Cluster-level tabs: Virtual Machines (aggregated), Storage (aggregated), Snapshots, Health, Backup Jobs
- Cluster summary cards: hosts (online/total), VMs (running/total), CPU, RAM, Storage with progress bars
- VM stats header: VMs total (running/stopped), CPU used, RAM used
- Summary tab moved to first position for cluster view
- Double-click on backup job row to edit
- Restore icon added to icon set

**Bug fixes**
- FadeToast crash: weakref pattern prevents "Internal C++ object already deleted" (strong ref kept toast alive after parent deleted)
- Cluster health tab stuck on Loading: replaced arbitrary `total * 2` threshold with done/total counter

## v2.7.0 — hardware management, storage operations, audit

**New features**
- VM Hardware Add/Remove/Edit: toolbar with 8 device types (Hard Disk, CD/DVD, Network, USB, PCI, Serial, EFI Disk, TPM)
- Disk destroy on removal: optional delete storage content after removing disk from VM config
- Hotplug-aware guards: Add/Remove blocked for running VMs unless hotplug allows the device type
- Storage file operations: Upload (ISO, templates, backups), Move (between storages), Remove — toolbar above each content table
- Upload progress bar: real-time progress shown in cluster tasks table
- 137 new i18n keys for ar/zh/fr/es (health-check, status-bar, SSL notifications, hardware editors)

**Bug fixes**
- Backup volid: stored in Qt.UserRole (was returning "VM 123" instead of actual volid for Move/Remove)
- Progress row stale index: reindexed on insert (concurrent uploads shifted rows)
- itemSelectionChanged reconnect leak: disconnect before reconnect (accumulated callbacks)
- set_vm_status order: called before set_hardware_data (buttons reflected previous VM's status)
- _parse_net/_parse_disk: handle None without str(None)="None" bug
- VmDiskEditorDialog: preserve non-cache params (discard, ssd, iothread) on cache change
- EFI disk: size=2 for efitype=2m, size=4 for 4m (was always 4)
- is_cdrom_key: check value for ide2, not always True (hard disks on ide2 no longer treated as CD-ROM)
- create_admin_token: handle r is None, init sess=None before try
- _ProgressReader: add seek/tell/fileno for requests compatibility
- StorageUploadWorker: fix resp.json double-parse when data is string
- _poll_task: guard against non-dict data response
- fetch_standalone: use v.get("vmid") instead of v["vmid"]
- on_snapshots_error: pop stale cache entry on error
- ISO worker: routed through _workers_mgr, errors logged instead of swallowed

**Dead code removed**
- Download feature (PVE API doesn't support file download via token)
- Dead signals: destroy_disk, opacity Property
- Dead fields: _MAX_SLOTS, _has_selection, seen set
- Duplicate PVE_PORT, unused imports, stale comments
- Debug logging (token_create, remote-viewer) INFO → DEBUG

## v2.6.0 — features & fixes

**New features**
- Status bar: hosts, VMs, CPU, RAM summary in bottom bar
- Tray icon: minimize to tray on close, quick actions menu
- RRD timeframe persistence: chart range saved between sessions
- Node comparison: side-by-side cluster node comparison view
- Multi-cluster dashboard: Clusters | Nodes toggle in cluster folder summary
- Health check tab: CPU/mem/disk thresholds, PVE service status, apt updates
- Audit log filters: text search + status dropdown (All/OK/Errors/Running)
- Pool resource summary: aggregated VM count, CPU, memory, disk with progress bars
- Offline mode: cached resources loaded on startup, shown until first live data arrives

**Bug fixes**
- SSL error detection: actionable message for self-signed/expired/invalid certificates
- Session leak: requests.Session closed in finally block of all 13 ProxmoxAPI workers
- Node deduplication: nodes matched by (node, host_name) — standalone hosts with same PVE node name no longer count each other's VMs
- CardList key collisions: key changed from "node" to "node@host_name" for uniqueness
- Summary view column alignment: header labels + VMs column added to standalone host list
- Cluster folder: standalone hosts no longer appear in cluster node compare view
- Pool metric cards: fixed height instead of expanding to fill available space
- Audit log filter bar: compact, right-aligned, minimal vertical space
- Tasks table sort freeze: sort in Python before table insert — eliminated 3-5s freeze on 400+ rows
- Worker memory leak: signal connections disconnected in _discard_worker — was leaking 108K lambda objects (30+ MiB)
- Cluster summary VM count: matched by host_name set instead of node name set

## v2.5.1 — bugfix release

Comprehensive code audit: ~21 bugs fixed across backend, UI, metrics, i18n, and resource management.

**Backend**
- Fixed API token creation: removed broken fallback that set token value to token name instead of secret
- Fixed SSL trust inversion: `trust_ssl` semantics now consistent across all code paths
- Fixed `UnboundLocalError` on connection error during token creation
- Fixed session leak: `requests.Session` now closed in `finally` block
- Standalone hosts: added missing `host_name` and `cluster` fields (caused UI KeyError)
- Fixed pool assignment race in standalone mode (re-applied after pool fetch)
- Removed duplicate API call in standalone fetch
- `fetch_resources`: guard against missing `type` field
- `ClusterTasksWorker`: now emits `tasks_error` on merge/sort failure (was hanging UI)

**UI crashes**
- All `data["key"]` accesses replaced with `.get()` guards in worker callbacks
- Fixed spinner leak: `_soft_refresh_active` and `_spin_timer` now reset on hard refresh
- Fixed hotplug validation typo: `networkdisk,usb` → `network,disk,usb` (invalid PVE API value)

**Metrics & notification**
- Fixed `KeyError` on RRD sparse data (`entry.get('time')`)
- Fixed notification crash on deleted widget (`RuntimeError` guard in `_restore_color`)
- Fixed toast replacement race: disconnect `destroyed` signal before `deleteLater`
- Fixed double `metric_changed` emit in metrics widget
- Fixed sort indicator arrow mismatch in cluster tasks table
- Host workers now tracked and cancelled on tab switch (no more orphaned QThreads)

**i18n**
- Added 8 missing lowercase status translations (running, stopped, paused, error, offline, online, unknown, mounted)
- Wrapped untranslated UI strings: Method, CIDR, Filter, No data, VM/CT prefix

**Dead code removed**
- Unused attributes: `_vm_iso_pending`, `_iso_volids`, `_disk_visible`, `_scroll`
- Dead `seen_names` initialization in tree panel

**Resource leaks**
- Detail panel caches (details, config, metrics, task history) now cleared on data refresh
- `QTimer` in table filter now has parent (was parentless)
- Freeze detector thread stopped on application close
- `ClusterTasksWorker`: signals disconnected when max workers cap hit (was orphaning workers)

## v2.5.0 — UI redesign

- MetricCard-based dashboard with progress bars
- CardList widget for list views (Host VMs, Cluster Summary, Storage Overview)
- Hardware/Options tabs with section grouping and device icons
- Hide empty section headers
- Fixed freeze on close (timers + thread pool shutdown)
- Tree expanded-state persistence
- CD-ROM detection by value (`media=cdrom`)

## v2.4.0

- Theme refresh (minimalist style)
- Header bar, segmented tabs, borderless tables
- Charts with area fill
- AddServer dialog with SSL trust toggle