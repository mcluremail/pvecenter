import logging
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..icons import get_icon
from ..theme import Color
from ..utils import format_uptime as _format_uptime
from ..utils import parse_pve_error, status_text
from ..vm_actions import VM_ACTION_MESSAGE_LABELS, confirm_vm_action
from ..widgets.metric_card import MetricCard
from ..widgets.vm_hardware_widget import VmHardwareWidget
from ..widgets.vm_metrics_widget import VmMetricsWidget
from ..widgets.vm_options_widget import VmOptionsWidget
from ..widgets.vm_pool_widget import VmPoolWidget
from ..widgets.vm_task_history_widget import VmTaskHistoryWidget
from ._constants import TabIndex
from ._table_utils import loading_label, safe_pct

logger = logging.getLogger(__name__)


def _safe_int(val):
    return int(val) if isinstance(val, (int, float)) else 0


class VMTabs:
    def __init__(self, panel):
        self.panel = panel

    def build_monitoring_tab(self):
        panel = self.panel
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        monitor_widget = QWidget()
        monitor_layout = QVBoxLayout(monitor_widget)
        monitor_layout.setContentsMargins(0, 0, 0, 0)
        monitor_layout.setSpacing(8)

        panel.info_stack = QStackedWidget()

        panel.info_label = QLabel()
        panel.info_label.setWordWrap(True)
        panel.info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        panel.info_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        panel.info_stack.addWidget(panel.info_label)

        cards_widget = QWidget()
        cards_layout = QGridLayout(cards_widget)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(8)

        panel.card_cpu = MetricCard(tr("CPU"), "—", show_progress=True)
        panel.card_ram = MetricCard(tr("RAM"), "—", show_progress=True)
        panel.card_disk = MetricCard(tr("Disk"), "—", show_progress=True)
        panel.card_net = MetricCard(tr("Network"), "—")
        panel.card_uptime = MetricCard(tr("Uptime"), "—")
        panel.card_status = MetricCard(tr("Status"), "—")

        cards_layout.addWidget(panel.card_status, 0, 0)
        cards_layout.addWidget(panel.card_cpu, 0, 1)
        cards_layout.addWidget(panel.card_ram, 0, 2)
        cards_layout.addWidget(panel.card_disk, 1, 0)
        cards_layout.addWidget(panel.card_net, 1, 1)
        cards_layout.addWidget(panel.card_uptime, 1, 2)

        panel.info_stack.addWidget(cards_widget)
        panel.info_stack.setCurrentIndex(0)

        monitor_layout.addWidget(panel.info_stack)

        panel.metrics_widget = VmMetricsWidget()
        panel.metrics_widget.setMinimumHeight(200)
        panel.metrics_widget.timeframe_changed.connect(panel._on_timeframe_changed)
        monitor_layout.addWidget(panel.metrics_widget, 1)

        tab.setWidget(monitor_widget)
        return tab

    def build_hardware_tab(self):
        panel = self.panel
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        panel.hardware_widget = VmHardwareWidget()
        tab.setWidget(panel.hardware_widget)
        panel.hardware_widget.config_changed.connect(panel._on_vm_config_change_requested)
        panel.hardware_widget.remove_device.connect(self._on_remove_with_destroy)
        panel.hardware_widget.disk_resize.connect(self.on_disk_resize)
        panel.hardware_widget.disk_move.connect(self.on_disk_move)
        return tab

    def build_options_tab(self):
        panel = self.panel
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        panel.options_widget = VmOptionsWidget()
        tab.setWidget(panel.options_widget)
        panel.options_widget.config_changed.connect(panel._on_vm_config_change_requested)
        return tab

    def build_history_tab(self):
        panel = self.panel
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        panel.task_history_widget = VmTaskHistoryWidget()
        tab.setWidget(panel.task_history_widget)
        return tab

    def build_snapshots_tab(self):
        panel = self.panel
        loading = loading_label()
        tree = QTreeWidget()
        tree.setHeaderLabels([
            tr("Snapshot"), tr("Description"), tr("Created"),
            tr("VM State"), tr("Size"), tr("Parent"),
        ])
        tree.setEditTriggers(QTreeWidget.NoEditTriggers)
        tree.setRootIsDecorated(True)
        tree.setAlternatingRowColors(True)
        tree.setColumnWidth(0, 200)
        tree.setColumnWidth(1, 200)
        tree.setColumnWidth(2, 160)
        tree.setColumnWidth(3, 80)
        tree.setColumnWidth(4, 100)
        tree.header().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        tree.header().setStretchLastSection(False)
        tree.header().setSectionResizeMode(5, QHeaderView.Stretch)
        tree.setContextMenuPolicy(Qt.CustomContextMenu)
        tree.customContextMenuRequested.connect(self._on_snapshot_context_menu)
        stack = QStackedWidget()
        stack.addWidget(loading)
        stack.addWidget(tree)
        stack.setCurrentIndex(0)
        panel.vm_snapshots_loading = loading
        panel.vm_snapshots_tree = tree
        panel.vm_snapshots_stack = stack
        btn_bar = QWidget()
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)
        create_btn = QPushButton(get_icon("snapshot"), tr("Create Snapshot"))
        create_btn.setMinimumHeight(28)
        create_btn.clicked.connect(self.on_snapshot_create)
        btn_layout.addWidget(create_btn)
        btn_layout.addStretch()
        panel.vm_snapshots_create_btn = create_btn
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(btn_bar)
        layout.addWidget(stack)
        tab.setWidget(container)
        return tab

    def build_vm_backup_tab(self):
        panel = self.panel
        loading = loading_label()
        from ._table_utils import make_filterable_table, make_table
        table = make_table(
            [tr("Archive"), tr("Type"), tr("Format"), tr("Size"), tr("Created"), tr("Storage")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 65),
             (QHeaderView.Interactive, 70), (QHeaderView.Interactive, 80),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 100)],
            sortable=True,
        )
        panel.vm_backup_table = table
        toolbar = QWidget()
        btn_layout = QVBoxLayout(toolbar)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)
        btn_row = QWidget()
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.setSpacing(4)
        backup_btn = QPushButton(get_icon("backup"), tr("Backup now"))
        backup_btn.setMinimumHeight(28)
        backup_btn.clicked.connect(self.on_vm_backup)
        btn_row_layout.addWidget(backup_btn)
        restore_btn = QPushButton(get_icon("restore"), tr("Restore"))
        restore_btn.setMinimumHeight(28)
        restore_btn.clicked.connect(self.on_vm_restore)
        btn_row_layout.addWidget(restore_btn)
        btn_row_layout.addStretch()
        btn_layout.addWidget(btn_row)
        panel.vm_backup_btn = backup_btn
        panel.vm_restore_btn = restore_btn
        stack = QStackedWidget()
        stack.addWidget(loading)
        filter_table = make_filterable_table(table)
        stack.addWidget(filter_table)
        stack.setCurrentIndex(0)
        panel.vm_backup_loading = loading
        panel.vm_backup_stack = stack
        btn_layout.addWidget(stack)
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(toolbar)
        tab.setWidget(container)
        return tab

    def build_pool_tab(self):
        panel = self.panel
        panel.pool_widget = VmPoolWidget()
        panel.pool_widget.navigate_requested.connect(panel.navigate_requested.emit)
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        tab.setWidget(panel.pool_widget)
        return tab

    # --- VM actions ---

    def on_vm_action(self, action):
        panel = self.panel
        if not panel._last_vm_data:
            return
        vmid = panel._last_vm_data.get("vmid")
        host_name = panel._last_vm_data.get("host_name") or panel._last_vm_data.get("node")
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        if not confirm_vm_action(action, vmid, parent=panel):
            return
        node_name = panel._last_vm_data.get("node") or host_name
        vm_type = panel._last_vm_data.get("type", "qemu")
        from ...backend import VmActionWorker
        worker = VmActionWorker(cfg, node_name, vmid, vm_type, action)
        for btn in panel._action_buttons.values():
            btn.setEnabled(False)
        panel.detail_label.setText(tr("VM/CT: {name}").format(name=vmid) + " — " + VM_ACTION_MESSAGE_LABELS.get(action, action) + "...")
        worker.signals.action_result.connect(lambda msg: (
            self.on_action_finished(msg),
            self.refresh_after_action(),
            panel._workers_mgr.discard_worker(worker)
        ))
        worker.signals.action_error.connect(lambda err: (
            self.on_action_error(err),
            panel._workers_mgr.discard_worker(worker)
        ))
        panel._workers_mgr.run_worker(worker)

    def update_action_buttons(self, vm_data=None):
        panel = self.panel
        if vm_data is None:
            vm_data = panel._last_vm_data or {}
        status = vm_data.get("status", "") if vm_data else ""
        for key, btn in panel._action_buttons.items():
            btn.setEnabled(True)
            if key == "start":
                btn.setEnabled(status not in ("running",))
            elif key in ("shutdown", "stop"):
                btn.setEnabled(status == "running")
            elif key in ("reboot", "reset"):
                btn.setEnabled(status == "running")
            elif key == "resume":
                btn.setEnabled(status == "paused")
        vm_type = vm_data.get("type", "qemu") if vm_data else "qemu"
        panel._console_btn.setEnabled(
            vm_type in ("qemu", "lxc") and status == "running"
        )

    def on_action_finished(self, msg):
        panel = self.panel
        vm = panel._last_vm_data or {}
        panel.detail_label.setText(tr("VM/CT: {name}").format(name=vm.get('name', vm.get('vmid', ''))) + " — " + msg)
        self.update_action_buttons(vm)

    def on_action_error(self, err):
        panel = self.panel
        panel.detail_label.setText(parse_pve_error(err))
        self.update_action_buttons(panel._last_vm_data)

    def on_vm_console(self):
        panel = self.panel
        if not panel._last_vm_data:
            return
        vm_type = panel._last_vm_data.get("type", "qemu")
        vmid = panel._last_vm_data.get("vmid")
        host_name = panel._last_vm_data.get("host_name") or panel._last_vm_data.get("node")
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        node_name = panel._last_vm_data.get("node") or host_name
        panel._console_btn.setEnabled(False)
        panel.detail_label.setText(tr("VM {vmid}: opening SPICE console...").format(vmid=vmid))
        from ...backend import VmConsoleWorker
        worker = VmConsoleWorker(cfg, node_name, vmid, vm_type)
        worker.signals.console_ready.connect(lambda msg: (
            panel.detail_label.setText(msg),
            panel._console_btn.setEnabled(True),
            panel._workers_mgr.discard_worker(worker)
        ))
        worker.signals.console_error.connect(lambda err: (
            panel.detail_label.setText(err),
            panel._console_btn.setEnabled(True),
            panel._workers_mgr.discard_worker(worker)
        ))
        panel._workers_mgr.run_worker(worker)

    def refresh_after_action(self):
        panel = self.panel
        if not panel._last_vm_data:
            return
        host_name = panel._last_vm_data.get("host_name") or panel._last_vm_data.get("node")
        vmid = panel._last_vm_data.get("vmid")
        vm_type = panel._last_vm_data.get("type", "qemu") or "qemu"
        node_name = panel._last_vm_data.get("node") or host_name
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        panel._workers_mgr.cancel_detail_worker()
        from ...backend import VmDetailWorker
        worker = VmDetailWorker(cfg, node_name, vmid, vm_type)
        worker.signals.detail_ready.connect(lambda d, w=worker: (
            self.on_action_detail_loaded(d, host_name),
            panel._workers_mgr.discard_worker(w)
        ))
        panel._workers_mgr.current_worker = worker
        panel._workers_mgr.run_worker(worker)

    # --- VM info / metrics ---

    def show_vm_info_init(self, vm_name, vm_data, gen):
        panel = self.panel
        panel.detail_label.setText(vm_name)
        panel.detail_sublabel.setText("")
        panel.detail_sublabel.setVisible(False)
        panel._last_vm_data = vm_data
        panel.tabs.setTabVisible(TabIndex.MONITOR, True)
        panel.tabs.setTabVisible(TabIndex.HARDWARE, True)
        panel.tabs.setTabVisible(TabIndex.OPTIONS, True)
        panel.tabs.setTabVisible(TabIndex.HISTORY, True)
        panel.tabs.setTabVisible(TabIndex.VM_SNAPSHOTS, True)
        panel.tabs.setTabVisible(TabIndex.VM_BACKUP, True)
        panel.tabs.setTabVisible(TabIndex.HOST_VMS, False)
        panel.tabs.setCurrentIndex(TabIndex.MONITOR)

        if not vm_data:
            panel.info_label.setText(tr("No data"))
            panel.info_stack.setCurrentIndex(0)
            return

        vmid = vm_data.get("vmid")
        host_name = vm_data.get("host_name") or vm_data.get("node")
        detail_key = (vmid, host_name)

        self.show_vm_metrics(vm_data)

        if detail_key not in panel.details_cache:
            cfg = panel._cfg_by_name.get(host_name)
            if cfg:
                panel.info_label.setText(tr("Loading detailed info..."))
                panel.info_stack.setCurrentIndex(0)
                node_name = vm_data.get("node") or host_name
                vm_type = vm_data.get("type", "qemu")
                from ...backend import VmDetailWorker
                worker = VmDetailWorker(cfg, node_name, vmid, vm_type)
                worker.signals.detail_ready.connect(lambda d, g=gen, h=host_name, w=worker: (self.on_detail_loaded(d, g, h), panel._workers_mgr.discard_worker(w)))
                panel._workers_mgr.current_worker = worker
                panel._workers_mgr.run_worker(worker)
            else:
                panel.info_label.setText(tr("Server configuration not found for {host}").format(host=host_name))
                panel.info_stack.setCurrentIndex(0)
        else:
            self.display_full_vm_info(vm_data, panel.details_cache[detail_key])

        node_name = vm_data.get("node") or host_name

        vm_type = vm_data.get("type", "qemu") or "qemu"
        if detail_key not in panel.vm_snapshots_cache:
            panel.vm_snapshots_tree.clear()
            panel.vm_snapshots_loading.setText(tr("Loading..."))
            panel.vm_snapshots_stack.setCurrentIndex(0)
            cfg = panel._cfg_by_name.get(host_name)
            if cfg:
                from ...backend import VmSnapshotsWorker
                panel._workers_mgr.current_snap_worker = VmSnapshotsWorker(cfg, node_name, vmid, vm_type)
                panel._workers_mgr.current_snap_worker.signals.snapshots_ready.connect(
                    lambda vid, snaps, g=gen, h=host_name, w=panel._workers_mgr.current_snap_worker:
                        (self.on_snapshots_loaded(vid, snaps, g, h), panel._workers_mgr.discard_worker(w)))
                panel._workers_mgr.current_snap_worker.signals.snapshots_error.connect(
                    lambda vid, err, g=gen, h=host_name, w=panel._workers_mgr.current_snap_worker:
                        (self.on_snapshots_error(vid, err, g, h), panel._workers_mgr.discard_worker(w)))
                panel._workers_mgr.run_worker(panel._workers_mgr.current_snap_worker)
        else:
            self.populate_vm_snapshots_tree(panel.vm_snapshots_cache[detail_key])

        self.load_iso_for_node(host_name, node_name)
        self.load_vm_backups(vmid, node_name, host_name)

        panel.hardware_widget.set_vm_status(vm_data.get("status", ""))
        panel.hardware_widget.set_context(host_name, vmid, node_name)
        if detail_key not in panel.config_cache:
            panel.hardware_widget.set_hardware_data(None)
            panel.options_widget.set_options_data(None)
            cfg = panel._cfg_by_name.get(host_name)
            if cfg:
                vm_type = vm_data.get("type", "qemu")
                from ...backend import VmConfigWorker
                worker = VmConfigWorker(cfg, node_name, vmid, vm_type)
                worker.signals.config_ready.connect(lambda vid, c, g=gen, h=host_name, w=worker: (self.on_config_loaded(vid, c, g, h), panel._workers_mgr.discard_worker(w)))
                worker.signals.config_error.connect(lambda vid, err, w=worker: panel._workers_mgr.discard_worker(w))
                panel._workers_mgr.current_config_worker = worker
                panel._workers_mgr.run_worker(worker)
        else:
            detail = panel.details_cache.get(detail_key)
            panel.hardware_widget.set_hardware_data(panel.config_cache[detail_key], detail)
            panel.options_widget.set_options_data(panel.config_cache[detail_key])
        if node_name not in panel._iso_by_node and panel._all_iso_catalog:
            panel._iso_by_node[node_name] = {
                iso["volid"] for iso in panel._all_iso_catalog.get(node_name, [])
            }
        iso_set = panel._iso_by_node.setdefault(node_name, set())
        panel.hardware_widget.set_iso_list(iso_set)
        node_storages = [s for s in panel.all_storages
                         if s.get("node") == node_name
                         and s.get("host_name") == host_name
                         and "images" in (s.get("content", "") or "").split(",")]
        panel.hardware_widget.set_storage_list(node_storages)
        panel.options_widget.set_context(host_name, vmid, node_name)

        if detail_key not in panel.task_history_cache:
            panel.task_history_widget.set_tasks([])
            cfg = panel._cfg_by_name.get(host_name)
            if cfg:
                node_name = vm_data.get("node") or host_name
                from ...backend import VmTaskHistoryWorker
                panel._workers_mgr.current_hist_worker = VmTaskHistoryWorker(cfg, node_name, vmid, limit=50)
                panel._workers_mgr.current_hist_worker.signals.tasks_ready.connect(lambda vid, t, g=gen, h=host_name, w=panel._workers_mgr.current_hist_worker: (self.on_tasks_loaded(vid, t, g, h), panel._workers_mgr.discard_worker(w)))
                panel._workers_mgr.current_hist_worker.signals.tasks_error.connect(lambda vid, err, w=panel._workers_mgr.current_hist_worker: panel._workers_mgr.discard_worker(w))
                panel._workers_mgr.run_worker(panel._workers_mgr.current_hist_worker)
        else:
            panel.task_history_widget.set_tasks(panel.task_history_cache[detail_key])

    def show_vm_metrics(self, vm_data):
        panel = self.panel
        if not panel.metrics_widget._has_plot:
            return
        panel.metrics_widget.show_disk_io(True)
        vmid = vm_data.get("vmid")
        host_name = vm_data.get("host_name") or vm_data.get("node")
        timeframe = panel.metrics_widget.timeframe_combo.currentData()
        cache_key = (vmid, host_name, timeframe)
        if cache_key in panel.metrics_cache:
            panel.metrics_widget.update_curves(panel.metrics_cache[cache_key])
            return

        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        node_name = vm_data.get("node") or host_name
        vm_type = vm_data.get("type", "qemu")

        from ..api.metrics import MetricsWorker
        worker = MetricsWorker(cfg, node_name, vmid, vm_type, timeframe)
        worker.signals.data_fetched.connect(lambda tf, v, md, g=panel._generation, h=host_name, w=worker: (self.on_metrics_fetched(tf, v, md, g, h), panel._workers_mgr.discard_worker(w)))
        worker.signals.error_occurred.connect(lambda err, w=worker: panel._workers_mgr.discard_worker(w))
        panel._workers_mgr.run_worker(worker)

    def on_metrics_fetched(self, timeframe, vmid, metrics_dict, gen, host_name):
        panel = self.panel
        if gen != panel._generation:
            return
        if not panel._last_vm_data:
            return
        current_host = panel._last_vm_data.get("host_name") or panel._last_vm_data.get("node")
        current_vmid = panel._last_vm_data.get("vmid")
        if current_vmid != vmid or current_host != host_name:
            return
        cache_key = (vmid, host_name, timeframe)
        panel.metrics_cache[cache_key] = metrics_dict
        panel.metrics_widget.update_curves(metrics_dict)

    def on_action_detail_loaded(self, detail, host_name):
        panel = self.panel
        if not panel._last_vm_data:
            return
        if detail.get("status") != "ok":
            return
        vmid = detail.get("vmid")
        data = detail.get("data", {})
        vm_data = panel._vms_by_key.get((host_name, vmid), {})
        merged = {**vm_data, **data}
        panel._last_vm_data = merged
        self.update_action_buttons(merged)
        self.update_vm_cells(merged)
        detail_key = (vmid, host_name)
        panel.details_cache[detail_key] = data
        self.display_full_vm_info(merged, data)

    def on_detail_loaded(self, detail, gen, host_name):
        panel = self.panel
        if gen != panel._generation:
            return
        vmid = detail.get("vmid")
        detail_key = (vmid, host_name)
        vm_data = panel._vms_by_key.get((host_name, vmid), {})
        if detail.get("status") == "ok":
            data = detail.get("data", {})
            panel.details_cache[detail_key] = data
            self.display_full_vm_info(vm_data, data)
            panel.tabs.setCurrentIndex(TabIndex.MONITOR)
            if detail_key in panel.config_cache:
                panel.hardware_widget.set_hardware_data(panel.config_cache[detail_key], data)
            if panel._last_vm_data:
                merged = {**vm_data, **data}
                panel._last_vm_data = merged
                self.update_action_buttons(merged)
        else:
            panel.info_label.setText(parse_pve_error(detail.get("error", "")))
            panel.info_stack.setCurrentIndex(0)

    def on_vm_config_change_requested(self, host_name, vmid_str, params):
        panel = self.panel
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        vmid = int(vmid_str)
        vm = panel._vms_by_key.get((host_name, vmid))
        node = vm.get("node") if vm else host_name
        vm_type = (vm.get("type") if vm else "qemu") or "qemu"

        from ...backend import VmConfigUpdateWorker
        worker = VmConfigUpdateWorker(cfg, node, vmid, params, vm_type)
        worker.signals.config_updated.connect(
            lambda vid, res, w=worker: (
                panel.config_update_result.emit(tr("VM {vid}: parameter changed").format(vid=vid)),
                self.reload_config(vmid, host_name),
                panel._workers_mgr.discard_worker(w),
            )
        )
        worker.signals.config_update_error.connect(
            lambda vid, err, w=worker: (
                panel.config_update_result.emit(tr("Error changing VM {vid}: {err}").format(vid=vid, err=err)),
                panel._workers_mgr.discard_worker(w),
            )
        )
        panel._workers_mgr.run_worker(worker)

    def _on_remove_with_destroy(self, host_name, vmid_str, key, raw_value):
        panel = self.panel
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        vmid = int(vmid_str)
        vm = panel._vms_by_key.get((host_name, vmid))
        node = vm.get("node") if vm else host_name
        vm_type = (vm.get("type") if vm else "qemu") or "qemu"

        from ...backend import VmConfigUpdateWorker
        worker = VmConfigUpdateWorker(cfg, node, vmid, {"delete": key}, vm_type)
        worker.signals.config_updated.connect(
            lambda vid, res, w=worker: (
                panel.config_update_result.emit(
                    tr("VM {vid}: {key} removed").format(vid=vid, key=key)
                ),
                self._destroy_disk_after_remove(host_name, node, key, raw_value),
                self.reload_config(vmid, host_name),
                panel._workers_mgr.discard_worker(w),
            )
        )
        worker.signals.config_update_error.connect(
            lambda vid, err, w=worker: (
                panel.config_update_result.emit(
                    tr("Error removing {key}: {err}").format(key=key, err=err)
                ),
                panel._workers_mgr.discard_worker(w),
            )
        )
        panel._workers_mgr.run_worker(worker)

    def _destroy_disk_after_remove(self, host_name, node, key, raw_value):
        panel = self.panel
        val_str = str(raw_value or "")
        storage = ""
        volid = ""
        if ":" in val_str:
            storage = val_str.split(":")[0]
            rest = val_str.split(":", 1)[1]
            volid = f"{storage}:{rest.split(',')[0]}"
        if not storage or not volid:
            return
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        from ...backend import StorageContentDeleteWorker
        worker = StorageContentDeleteWorker(cfg, node, storage, volid)
        worker.signals.result.connect(
            lambda msg, w=worker: (
                panel.config_update_result.emit(msg),
                panel._workers_mgr.discard_worker(w),
            )
        )
        worker.signals.error.connect(
            lambda err, w=worker: (
                panel.config_update_result.emit(
                    tr("Destroy failed: {err}").format(err=err)
                ),
                panel._workers_mgr.discard_worker(w),
            )
        )
        panel._workers_mgr.run_worker(worker)

    def on_disk_resize(self, host_name, vmid_str, disk, size):
        panel = self.panel
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        vmid = int(vmid_str)
        vm = panel._vms_by_key.get((host_name, vmid))
        node = vm.get("node") if vm else host_name
        vm_type = (vm.get("type") if vm else "qemu") or "qemu"

        from ...backend import VmDiskResizeWorker
        worker = VmDiskResizeWorker(cfg, node, vmid, disk, size, vm_type)
        worker.signals.disk_resized.connect(
            lambda vid, upid, w=worker: (
                panel.config_update_result.emit(
                    tr("VM {vid}: disk {disk} resized by {size}").format(
                        vid=vid, disk=disk, size=size)
                ),
                self.reload_config(vmid, host_name),
                panel._workers_mgr.discard_worker(w),
            )
        )
        worker.signals.disk_resize_error.connect(
            lambda vid, err, w=worker: (
                panel.config_update_result.emit(
                    tr("Resize failed: {err}").format(err=err)
                ),
                panel._workers_mgr.discard_worker(w),
            )
        )
        panel._workers_mgr.run_worker(worker)

    def on_disk_move(self, host_name, vmid_str, disk, storage, delete):
        panel = self.panel
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        vmid = int(vmid_str)
        vm = panel._vms_by_key.get((host_name, vmid))
        node = vm.get("node") if vm else host_name
        vm_type = (vm.get("type") if vm else "qemu") or "qemu"

        from ...backend import VmDiskMoveWorker
        worker = VmDiskMoveWorker(cfg, node, vmid, disk, storage, delete, vm_type)
        worker.signals.disk_moved.connect(
            lambda vid, upid, w=worker: (
                panel.config_update_result.emit(
                    tr("VM {vid}: disk {disk} moved to {storage}").format(
                        vid=vid, disk=disk, storage=storage)
                ),
                self.reload_config(vmid, host_name),
                panel._workers_mgr.discard_worker(w),
            )
        )
        worker.signals.disk_move_error.connect(
            lambda vid, err, w=worker: (
                panel.config_update_result.emit(
                    tr("Move failed: {err}").format(err=err)
                ),
                panel._workers_mgr.discard_worker(w),
            )
        )
        panel._workers_mgr.run_worker(worker)

    def on_config_loaded(self, vmid, config, gen, host_name):
        panel = self.panel
        if gen != panel._generation:
            return
        detail_key = (vmid, host_name)
        panel.config_cache[detail_key] = config
        if panel._last_vm_data and panel._last_vm_data.get("vmid") == vmid and panel._last_vm_data.get("host_name") == host_name:
            detail = panel.details_cache.get(detail_key)
            panel.hardware_widget.set_hardware_data(config, detail)
            panel.options_widget.set_options_data(config)

    def on_tasks_loaded(self, vmid, tasks, gen, host_name):
        panel = self.panel
        if gen != panel._generation:
            return
        detail_key = (vmid, host_name)
        panel.task_history_cache[detail_key] = tasks
        if panel._last_vm_data and panel._last_vm_data.get("vmid") == vmid and panel._last_vm_data.get("host_name") == host_name:
            panel.task_history_widget.set_tasks(tasks)

    def on_snapshots_loaded(self, vmid, snapshots, gen, host_name):
        panel = self.panel
        if gen != panel._generation:
            return
        detail_key = (vmid, host_name)
        panel.vm_snapshots_cache[detail_key] = snapshots
        if panel._last_vm_data and panel._last_vm_data.get("vmid") == vmid and panel._last_vm_data.get("host_name") == host_name:
            self.populate_vm_snapshots_tree(snapshots)

    def on_snapshots_error(self, vmid, err, gen, host_name):
        panel = self.panel
        if gen != panel._generation:
            return
        if not panel._last_vm_data or panel._last_vm_data.get("vmid") != vmid or panel._last_vm_data.get("host_name") != host_name:
            return
        detail_key = (vmid, host_name)
        panel.vm_snapshots_cache.pop(detail_key, None)
        panel.vm_snapshots_loading.setText(parse_pve_error(err))
        panel.vm_snapshots_stack.setCurrentIndex(0)

    def reload_snapshots(self, vmid, host_name):
        panel = self.panel
        detail_key = (vmid, host_name)
        panel.vm_snapshots_cache.pop(detail_key, None)
        panel.vm_snapshots_tree.clear()
        panel.vm_snapshots_loading.setText(tr("Loading..."))
        panel.vm_snapshots_stack.setCurrentIndex(0)
        cfg = panel._cfg_by_name.get(host_name)
        if cfg and panel._last_vm_data:
            node_name = panel._last_vm_data.get("node") or host_name
            vm_type = panel._last_vm_data.get("type", "qemu") or "qemu"
            gen = panel._generation
            from ...backend import VmSnapshotsWorker
            worker = VmSnapshotsWorker(cfg, node_name, vmid, vm_type)
            worker.signals.snapshots_ready.connect(
                lambda vid, snaps, g=gen, h=host_name, w=worker: (
                    self.on_snapshots_loaded(vid, snaps, g, h),
                    panel._workers_mgr.discard_worker(w),
                )
            )
            worker.signals.snapshots_error.connect(
                lambda vid, err, g=gen, h=host_name, w=worker: (
                    self.on_snapshots_error(vid, err, g, h),
                    panel._workers_mgr.discard_worker(w),
                )
            )
            panel._workers_mgr.run_worker(worker)

    def on_snapshot_create(self):
        panel = self.panel
        if not panel._last_vm_data:
            return
        vmid = panel._last_vm_data.get("vmid")
        host_name = panel._last_vm_data.get("host_name") or panel._last_vm_data.get("node")
        node_name = panel._last_vm_data.get("node") or host_name
        vm_type = panel._last_vm_data.get("type", "qemu") or "qemu"
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        from PySide6.QtWidgets import (
            QCheckBox,
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QLineEdit,
        )
        dlg = QDialog(panel)
        dlg.setWindowTitle(tr("Create Snapshot"))
        dlg.setMinimumWidth(360)
        form = QFormLayout(dlg)
        name_edit = QLineEdit()
        name_edit.setPlaceholderText(tr("Snapshot name"))
        desc_edit = QLineEdit()
        desc_edit.setPlaceholderText(tr("Description"))
        vmstate_check = QCheckBox()
        vmstate_check.setToolTip(tr("Include RAM state in snapshot"))
        form.addRow(tr("Snapshot name"), name_edit)
        form.addRow(tr("Description"), desc_edit)
        form.addRow(tr("Include RAM state"), vmstate_check)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=dlg,
        )
        ok_btn = buttons.button(QDialogButtonBox.Ok)
        ok_btn.setEnabled(False)
        name_edit.textChanged.connect(lambda t: ok_btn.setEnabled(bool(t.strip())))
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec() != QDialog.Accepted:
            return
        snap_name = name_edit.text().strip()
        if not snap_name:
            return
        description = desc_edit.text().strip()
        vmstate = vmstate_check.isChecked()
        from ...backend import VmSnapshotCreateWorker
        worker = VmSnapshotCreateWorker(cfg, node_name, vmid, vm_type, snap_name, description, vmstate)
        panel.vm_snapshots_create_btn.setEnabled(False)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self.reload_snapshots(vmid, host_name),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(parse_pve_error(err)),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.finished.connect(
            lambda: panel.vm_snapshots_create_btn.setEnabled(True)
        )
        panel._workers_mgr.run_worker(worker)

    def _on_snapshot_context_menu(self, pos):
        panel = self.panel
        tree = panel.vm_snapshots_tree
        item = tree.itemAt(pos)
        if not item:
            return
        snap_name = item.text(0)
        if not snap_name:
            return
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QMenu
        menu = QMenu(tree)
        menu.setStyleSheet(
            "QMenu { font-size: 12px; padding: 2px; }"
            "QMenu::item { padding: 4px 12px; }"
            f"QMenu::item:selected {{ background: {Color.GRAY_200}; }}"
        )
        delete_act = QAction(tr("Delete snapshot"), tree)
        delete_act.triggered.connect(lambda: self.on_snapshot_delete(snap_name))
        menu.addAction(delete_act)
        menu.exec(tree.viewport().mapToGlobal(pos))

    def on_snapshot_delete(self, snap_name):
        panel = self.panel
        if not panel._last_vm_data:
            return
        vmid = panel._last_vm_data.get("vmid")
        host_name = panel._last_vm_data.get("host_name") or panel._last_vm_data.get("node")
        node_name = panel._last_vm_data.get("node") or host_name
        vm_type = panel._last_vm_data.get("type", "qemu") or "qemu"
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        from ..vm_actions import confirm_snapshot_delete
        if not confirm_snapshot_delete(snap_name, parent=panel):
            return
        from ...backend import VmSnapshotDeleteWorker
        worker = VmSnapshotDeleteWorker(cfg, node_name, vmid, vm_type, snap_name)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self.reload_snapshots(vmid, host_name),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(parse_pve_error(err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_worker(worker)

    def populate_vm_snapshots_tree(self, snapshots):
        panel = self.panel
        tree = panel.vm_snapshots_tree
        tree.clear()
        if not snapshots:
            panel.vm_snapshots_loading.setText(tr("No snapshots"))
            panel.vm_snapshots_stack.setCurrentIndex(0)
            return
        snap_by_name = {}
        for snap in snapshots:
            snap_by_name[snap.get("name", "")] = snap
        created_items = set()
        remaining = list(snapshots)

        def create_item(snap):
            name = snap.get("name", "")
            desc = snap.get("description", "") or ""
            snaptime = snap.get("snaptime", 0)
            if snaptime:
                ts = datetime.fromtimestamp(snaptime).strftime("%Y-%m-%d %H:%M:%S")
            else:
                ts = ""
            vm_state = tr("yes") if snap.get("vmstate", 0) else tr("no")
            size_val = snap.get("size", "")
            if isinstance(size_val, (int, float)) and size_val > 0:
                gb = size_val / (1024 ** 3)
                if gb >= 1024:
                    size_str = f"{gb / 1024:.1f} TiB"
                else:
                    size_str = f"{gb:.1f} GiB"
            else:
                size_str = str(size_val) if size_val else "—"
            parent_name = snap.get("parent", "") or ""
            item = QTreeWidgetItem([name, desc, ts, vm_state, size_str, parent_name])
            return item

        for _ in range(len(snapshots) + 1):
            progress = False
            still = []
            for snap in remaining:
                parent_name = snap.get("parent", "") or ""
                if not parent_name or parent_name == "current" or parent_name not in snap_by_name:
                    item = create_item(snap)
                    tree.addTopLevelItem(item)
                    snap["_tree_item"] = item
                    created_items.add(snap.get("name", ""))
                    progress = True
                elif parent_name in created_items:
                    parent_snap = snap_by_name[parent_name]
                    parent_item = parent_snap.get("_tree_item")
                    if parent_item:
                        item = create_item(snap)
                        parent_item.addChild(item)
                        snap["_tree_item"] = item
                        created_items.add(snap.get("name", ""))
                        progress = True
                    else:
                        still.append(snap)
                else:
                    still.append(snap)
            remaining = still
            if not progress:
                break

        tree.expandAll()
        tree.resizeColumnToContents(0)
        panel.vm_snapshots_stack.setCurrentIndex(1)

    def reload_config(self, vmid, host_name):
        panel = self.panel
        detail_key = (vmid, host_name)
        panel.config_cache.pop(detail_key, None)
        cfg = panel._cfg_by_name.get(host_name)
        if cfg and panel._last_vm_data:
            node_name = panel._last_vm_data.get("node") or host_name
            vm_type = panel._last_vm_data.get("type", "qemu") or "qemu"
            gen = panel._generation
            from ...backend import VmConfigWorker
            worker = VmConfigWorker(cfg, node_name, vmid, vm_type)
            worker.signals.config_ready.connect(
                lambda vid, c, g=gen, h=host_name, w=worker: (
                    self.on_config_loaded(vid, c, g, h),
                    panel._workers_mgr.discard_worker(w),
                )
            )
            worker.signals.config_error.connect(lambda vid, err, w=worker: panel._workers_mgr.discard_worker(w))
            panel._workers_mgr.run_worker(worker)

    def display_full_vm_info(self, basic, detail):
        panel = self.panel
        try:
            vmid = basic.get("vmid") or detail.get("vmid", "?")
            name = basic.get("name") or detail.get("name", "")
            status = basic.get("status") or detail.get("status", "")

            maxmem_bytes = _safe_int(detail.get("maxmem") or basic.get("maxmem"))
            mem_used_bytes = _safe_int(detail.get("mem"))
            maxmem_gb = round(maxmem_bytes / (1024**3), 2) if maxmem_bytes else 0
            mem_used_gb = round(mem_used_bytes / (1024**3), 2) if mem_used_bytes else 0
            mem_pct = safe_pct(mem_used_bytes, maxmem_bytes)

            cpus = detail.get("cpus") or basic.get("cpus") or 0
            cpu_usage = basic.get("cpu") or detail.get("cpu", 0)
            if isinstance(cpu_usage, float): cpu_usage = round(cpu_usage * 100, 1)

            maxdisk_bytes = _safe_int(detail.get("maxdisk") or basic.get("maxdisk"))
            disk_used_bytes = _safe_int(detail.get("disk"))
            maxdisk_gb = round(maxdisk_bytes / (1024**3), 2) if maxdisk_bytes else 0
            vm_type = (detail.get("type") or basic.get("type", "qemu"))
            if vm_type == "lxc" and disk_used_bytes:
                disk_used_gb = round(disk_used_bytes / (1024**3), 2)
                disk_pct = safe_pct(disk_used_bytes, maxdisk_bytes)
                panel.card_disk.set_value(f"{disk_used_gb} / {maxdisk_gb} {tr('GiB')}")
                panel.card_disk.set_progress(disk_pct)
            else:
                panel.card_disk.set_value(f"{maxdisk_gb} {tr('GiB')}")
                panel.card_disk.set_progress(0)
                panel.card_disk.set_subtitle(tr("Size (usage unavailable)"))

            netin = detail.get("netin", 0)
            netout = detail.get("netout", 0)
            netin_mb = round(netin / (1024*1024), 2) if netin else 0
            netout_mb = round(netout / (1024*1024), 2) if netout else 0

            uptime = detail.get("uptime") or basic.get("uptime", "")
            tags = basic.get("tags") or detail.get("tags") or ""
            ha = basic.get("hastate") or detail.get("hastate", "")

            panel.detail_label.setText(f"{name or vmid}")

            subtitle_parts = [status_text(status)]
            if cpus:
                subtitle_parts.append(f"{cpus} {tr('cores')}")
            if maxmem_gb:
                subtitle_parts.append(f"{maxmem_gb} {tr('GiB')} RAM")
            uptime_str = _format_uptime(uptime) if uptime else ""
            if uptime_str:
                subtitle_parts.append(f"{uptime_str} {tr('uptime')}")
            panel.detail_sublabel.setText(" · ".join(subtitle_parts))
            panel.detail_sublabel.setVisible(True)

            panel.card_status.set_value(status_text(status))
            panel.card_status.set_title(tr("Status"))
            status_color = Color.STATUS_OK if status == "running" else Color.STATUS_ERR if status == "stopped" else Color.STATUS_WARN
            panel.card_status.set_value_color(status_color)
            if ha and ha not in ("", "ignored"):
                panel.card_status.set_subtitle(f"HA: {ha}")
            else:
                panel.card_status.set_subtitle("")

            panel.card_cpu.set_title(tr("CPU"))
            panel.card_cpu.set_value(f"{cpu_usage}%")
            panel.card_cpu.set_subtitle(f"{cpus} {tr('cores')}")
            panel.card_cpu.set_progress(cpu_usage)

            panel.card_ram.set_title(tr("RAM"))
            panel.card_ram.set_value(f"{mem_used_gb} / {maxmem_gb} {tr('GiB')}")
            panel.card_ram.set_progress(mem_pct)

            panel.card_disk.set_title(tr("Disk"))
            panel.card_net.set_title(tr("Network"))
            panel.card_net.set_value(f"↓ {netin_mb} MB")
            panel.card_net.set_subtitle(f"↑ {netout_mb} MB")

            panel.card_uptime.set_title(tr("Uptime"))
            panel.card_uptime.set_value(_format_uptime(uptime) if uptime else "—")
            panel.card_uptime.set_subtitle(f"{tr('Tags')}: {tags}" if tags else "")

            panel.info_stack.setCurrentIndex(1)
        except Exception as exc:
            logger.debug("display_full_vm_info error", exc_info=True)
            self.panel.config_update_result.emit(
                tr("Error: {err}").format(err=str(exc)[:100])
            )
            panel.info_label.setText(tr("Error building info"))
            panel.info_stack.setCurrentIndex(0)

    def update_vm_cells(self, vm_data):
        panel = self.panel
        if not vm_data:
            return
        detail_key = (vm_data.get("vmid"), vm_data.get("host_name") or vm_data.get("node"))
        detail = panel.details_cache.get(detail_key)
        if not detail:
            return

        status = vm_data.get("status") or detail.get("status", "")
        status_color = Color.STATUS_OK if status == "running" else Color.STATUS_ERR if status == "stopped" else Color.STATUS_WARN
        panel.card_status.set_value(status_text(status))
        panel.card_status.set_value_color(status_color)

        cpu_usage = vm_data.get("cpu") or detail.get("cpu", 0)
        if isinstance(cpu_usage, float):
            cpu_usage = round(cpu_usage * 100, 1)
        panel.card_cpu.set_value(f"{cpu_usage}%")
        panel.card_cpu.set_progress(cpu_usage)

        maxmem_bytes = _safe_int(detail.get("maxmem") or vm_data.get("maxmem"))
        mem_used_bytes = _safe_int(detail.get("mem"))
        maxmem_gb = round(maxmem_bytes / (1024**3), 2) if maxmem_bytes else 0
        mem_used_gb = round(mem_used_bytes / (1024**3), 2) if mem_used_bytes else 0
        panel.card_ram.set_value(f"{mem_used_gb} / {maxmem_gb} {tr('GiB')}")
        panel.card_ram.set_progress(safe_pct(mem_used_bytes, maxmem_bytes))

        maxdisk_bytes = _safe_int(detail.get("maxdisk") or vm_data.get("maxdisk"))
        disk_used_bytes = _safe_int(detail.get("disk"))
        maxdisk_gb = round(maxdisk_bytes / (1024**3), 2) if maxdisk_bytes else 0
        vm_type = detail.get("type") or vm_data.get("type", "qemu")
        if vm_type == "lxc" and disk_used_bytes:
            disk_used_gb = round(disk_used_bytes / (1024**3), 2)
            panel.card_disk.set_value(f"{disk_used_gb} / {maxdisk_gb} {tr('GiB')}")
            panel.card_disk.set_progress(safe_pct(disk_used_bytes, maxdisk_bytes))
        else:
            panel.card_disk.set_value(f"{maxdisk_gb} {tr('GiB')}")
            panel.card_disk.set_progress(0)
            panel.card_disk.set_subtitle(tr("Size (usage unavailable)"))

        netin = detail.get("netin", 0)
        netout = detail.get("netout", 0)
        netin_mb = round(netin / (1024*1024), 2) if netin else 0
        netout_mb = round(netout / (1024*1024), 2) if netout else 0
        panel.card_net.set_value(f"↓ {netin_mb} MB")
        panel.card_net.set_subtitle(f"↑ {netout_mb} MB")

        uptime = detail.get("uptime") or vm_data.get("uptime", "")
        panel.card_uptime.set_value(_format_uptime(uptime) if uptime else "—")

    def update_pool_cells(self):
        panel = self.panel
        pool_name = panel.current_obj_name
        vms = [vm for vm in panel.all_vms if vm.get("pool") == pool_name]
        panel.pool_widget.set_pool_vms(vms)

    def show_pool_info(self, pool_name):
        panel = self.panel
        panel.detail_label.setText(tr("Pool: {name}").format(name=pool_name))
        panel.detail_sublabel.setText("")
        panel.detail_sublabel.setVisible(False)
        panel.tabs.setTabVisible(TabIndex.MONITOR, False)
        panel.tabs.setTabVisible(TabIndex.HARDWARE, False)
        panel.tabs.setTabVisible(TabIndex.OPTIONS, False)
        panel.tabs.setTabVisible(TabIndex.HISTORY, False)
        panel.tabs.setTabVisible(TabIndex.VM_SNAPSHOTS, False)
        panel.tabs.setTabVisible(TabIndex.VM_BACKUP, False)
        panel.tabs.setTabVisible(TabIndex.HOST_VMS, False)
        panel.tabs.setTabVisible(TabIndex.POOL_VMS, True)
        panel.tabs.setCurrentIndex(TabIndex.POOL_VMS)

        vms_in_pool = [vm for vm in panel.all_vms if vm.get("pool") == pool_name]
        panel.pool_widget.set_pool_vms(vms_in_pool)

    def load_iso_for_node(self, host_name, node_name):
        panel = self.panel
        panel._iso_by_node[node_name] = set()
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        storages = [s for s in panel.all_storages
                    if s.get("node") == node_name
                    and s.get("host_name") == host_name
                    and "iso" in (s.get("content") or "").split(",")]
        from ..api.metrics import StorageContentListWorker
        for storage_info in storages:
            storage = storage_info.get("storage")
            if not storage:
                continue
            worker = StorageContentListWorker(cfg, node_name, storage, "iso")
            worker.signals.result.connect(
                lambda sn, ct, data, n=node_name: self.on_vm_iso_loaded(n, data)
            )
            worker.signals.error.connect(
                lambda sn, ct, err, n=node_name: logger.warning("ISO load failed for %s/%s: %s", n, sn, err)
            )
            panel._workers_mgr.run_worker(worker)

    def on_vm_iso_loaded(self, node_name, data):
        panel = self.panel
        vols = {v.get("volid") for v in (data or []) if v.get("volid")}
        if node_name in panel._iso_by_node:
            panel._iso_by_node[node_name].update(vols)

    # --- VM backup (vzdump + restore) ---

    def load_vm_backups(self, vmid, node_name, host_name):
        panel = self.panel
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        panel.vm_backup_loading.setText(tr("Loading..."))
        panel.vm_backup_stack.setCurrentIndex(0)
        panel.vm_backup_table.setRowCount(0)
        backup_storages = [
            s for s in panel.all_storages
            if s.get("node") == node_name
            and s.get("host_name") == host_name
            and "backup" in (s.get("content", "") or "").split(",")
        ]
        if not backup_storages:
            panel.vm_backup_loading.setText(tr("No backup storage available"))
            return
        panel._vm_backup_pending = len(backup_storages)
        panel._vm_backup_all = []
        panel._vm_backup_gen = getattr(panel, "_generation", 0)
        from ..api.metrics import StorageContentListWorker
        for storage_info in backup_storages:
            storage = storage_info.get("storage")
            if not storage:
                continue
            worker = StorageContentListWorker(cfg, node_name, storage, "backup")
            worker.signals.result.connect(
                lambda sn, ct, data, v=vmid, s=storage: self.on_vm_backups_loaded(v, s, data)
            )
            worker.signals.error.connect(
                lambda sn, ct, err, v=vmid, s=storage: self.on_vm_backups_loaded(v, s, [])
            )
            panel._workers_mgr.run_worker(worker)

    def on_vm_backups_loaded(self, vmid, storage_name, data):
        panel = self.panel
        gen = getattr(panel, "_vm_backup_gen", None)
        if gen is not None and gen != getattr(panel, "_generation", 0):
            return
        if not hasattr(panel, "_vm_backup_pending"):
            return
        for b in (data or []):
            if str(b.get("vmid", "")) == str(vmid):
                b["storage"] = storage_name
                panel._vm_backup_all.append(b)
        panel._vm_backup_pending -= 1
        if panel._vm_backup_pending > 0:
            return
        backups = panel._vm_backup_all
        panel.__dict__.pop("_vm_backup_pending", None)
        panel._vm_backup_all = []
        panel._vm_backup_gen = None
        if backups:
            panel.vm_backup_stack.setCurrentIndex(1)
            self.populate_vm_backups_table(backups)
        else:
            panel.vm_backup_loading.setText(tr("No backups found for this VM"))
            panel.vm_backup_stack.setCurrentIndex(0)

    def populate_vm_backups_table(self, backups):
        panel = self.panel
        table = panel.vm_backup_table
        table.setSortingEnabled(False)
        table.setRowCount(len(backups))
        from ._table_utils import format_volsize
        for i, b in enumerate(backups):
            volid = b.get("volid", "")
            archive_item = QTableWidgetItem(volid)
            archive_item.setIcon(get_icon("backup"))
            archive_item.setData(Qt.UserRole, volid)
            table.setItem(i, 0, archive_item)
            table.setItem(i, 1, QTableWidgetItem(b.get("subtype") or b.get("type", "")))
            table.setItem(i, 2, QTableWidgetItem(b.get("format", "")))
            size = b.get("size", 0) or 0
            table.setItem(i, 3, QTableWidgetItem(format_volsize(size) if size else "0"))
            ctime = b.get("ctime")
            if ctime:
                table.setItem(i, 4, QTableWidgetItem(datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M")))
            else:
                table.setItem(i, 4, QTableWidgetItem(""))
            table.setItem(i, 5, QTableWidgetItem(b.get("storage", "")))
        table.setSortingEnabled(True)

    def on_vm_backup(self):
        panel = self.panel
        if not panel._last_vm_data:
            return
        vmid = panel._last_vm_data.get("vmid")
        host_name = panel._last_vm_data.get("host_name") or panel._last_vm_data.get("node")
        node_name = panel._last_vm_data.get("node") or host_name
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        from ..vzdump_dialog import VzdumpDialog
        storages = [s for s in panel.all_storages
                    if s.get("node") == node_name
                    and s.get("host_name") == host_name]
        dlg = VzdumpDialog(panel, vmid=vmid, storages=storages)
        if dlg.exec() != VzdumpDialog.Accepted:
            return
        params = dlg.get_params()
        if not params:
            return
        from ...backend import VzdumpWorker
        worker = VzdumpWorker(
            cfg, node_name, vmid,
            storage=params["storage"],
            mode=params["mode"],
            compress=params["compress"],
            notes=params["notes"],
            remove=params["remove"],
            bwlimit=params["bwlimit"],
        )
        key = f"vzdump:{vmid}"
        panel.transfer_started.emit(key, tr("Backup VM {vmid}").format(vmid=vmid))
        panel.vm_backup_btn.setEnabled(False)
        worker.signals.result.connect(lambda msg, k=key, w=worker: (
            panel.transfer_finished.emit(k, True, msg),
            panel.config_update_result.emit(msg),
            self.load_vm_backups(vmid, node_name, host_name),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, k=key, w=worker: (
            panel.transfer_finished.emit(k, False, err),
            panel.config_update_result.emit(parse_pve_error(err)),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.finished.connect(
            lambda: panel.vm_backup_btn.setEnabled(True)
        )
        panel._workers_mgr.run_worker(worker)

    def on_vm_restore(self):
        panel = self.panel
        if not panel._last_vm_data:
            return
        host_name = panel._last_vm_data.get("host_name") or panel._last_vm_data.get("node")
        node_name = panel._last_vm_data.get("node") or host_name
        vm_type = panel._last_vm_data.get("type", "qemu") or "qemu"
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        table = panel.vm_backup_table
        row = table.currentRow()
        if row < 0:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(panel, tr("Restore"), tr("Select a backup to restore"))
            return
        archive_item = table.item(row, 0)
        if not archive_item:
            return
        volid = archive_item.data(Qt.UserRole) or archive_item.text()
        if not volid:
            return
        used_vmids = {v.get("vmid") for v in panel.all_vms if v.get("vmid")}
        next_vmid = self._next_free_vmid(used_vmids)
        from ..vm_restore_dialog import VmRestoreDialog
        storages = [s for s in panel.all_storages
                    if s.get("node") == node_name
                    and s.get("host_name") == host_name]
        dlg = VmRestoreDialog(panel, volid=volid, vm_type=vm_type,
                              storages=storages, next_vmid=next_vmid)
        if dlg.exec() != VmRestoreDialog.Accepted:
            return
        params = dlg.get_params()
        from ...backend import VmRestoreWorker
        worker = VmRestoreWorker(
            cfg, node_name, params["vmid"], vm_type, volid,
            storage=params["storage"],
            name=params["name"],
            force=params["force"],
            unique=params["unique"],
        )
        key = f"restore:{params['vmid']}"
        panel.transfer_started.emit(key, tr("Restore VM {vmid}").format(vmid=params["vmid"]))
        panel.vm_restore_btn.setEnabled(False)
        worker.signals.result.connect(lambda msg, k=key, w=worker: (
            panel.transfer_finished.emit(k, True, msg),
            panel.config_update_result.emit(msg),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, k=key, w=worker: (
            panel.transfer_finished.emit(k, False, err),
            panel.config_update_result.emit(parse_pve_error(err)),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.finished.connect(
            lambda: panel.vm_restore_btn.setEnabled(True)
        )
        panel._workers_mgr.run_worker(worker)

    @staticmethod
    def _next_free_vmid(used_vmids, start=100, end=999999999):
        for vid in range(start, end + 1):
            if vid not in used_vmids:
                return vid
        return start
