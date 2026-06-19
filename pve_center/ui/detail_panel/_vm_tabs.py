import traceback

from PySide6.QtWidgets import (QLabel, QStackedWidget, QVBoxLayout, QWidget,
                               QSizePolicy, QTableWidgetItem, QMessageBox,
                               QPushButton, QHBoxLayout, QScrollArea,
                               QTableWidget, QHeaderView)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush

from ..i18n import tr
from ..utils import status_text, format_uptime as _format_uptime, parse_pve_error
from ..vm_actions import VM_ACTION_BUTTON_LABELS, VM_ACTION_MESSAGE_LABELS, VM_ACTION_ICONS
from ..icons import get_icon
from ._constants import TabIndex
from ._table_utils import compact_table, set_cell_text

from ..widgets.vm_metrics_widget import VmMetricsWidget
from ..widgets.vm_hardware_widget import VmHardwareWidget
from ..widgets.vm_options_widget import VmOptionsWidget
from ..widgets.vm_task_history_widget import VmTaskHistoryWidget
from ..widgets.vm_pool_widget import VmPoolWidget


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

        panel.info_stack = QStackedWidget()

        panel.info_label = QLabel()
        panel.info_label.setWordWrap(True)
        panel.info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        panel.info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        panel.info_stack.addWidget(panel.info_label)

        panel.vm_summary_table = self._build_vm_summary_table()
        panel.info_stack.addWidget(panel.vm_summary_table)

        panel.info_stack.setFixedWidth(320)
        panel.info_stack.setMinimumHeight(260)
        panel.info_stack.setMaximumHeight(340)
        panel.vm_summary_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        panel.metrics_widget = VmMetricsWidget()
        panel.metrics_widget.setMinimumHeight(260)
        panel.metrics_widget.setMaximumHeight(340)
        panel.metrics_widget.timeframe_changed.connect(panel._on_timeframe_changed)

        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 8, 0)
        middle.addWidget(panel.info_stack)
        middle.addWidget(panel.metrics_widget, 1)
        monitor_layout.addLayout(middle)
        monitor_layout.addStretch()

        tab.setWidget(monitor_widget)
        return tab

    def _build_vm_summary_table(self):
        from PySide6.QtWidgets import QTableWidget, QHeaderView
        from ._constants import _HEADER_STYLE
        from ..hover import enable_row_hover
        table = QTableWidget()
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().hide()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels([tr("Parameter"), tr("Value")])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        table.horizontalHeader().setStyleSheet(_HEADER_STYLE)
        table.setWordWrap(True)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setAlternatingRowColors(True)
        enable_row_hover(table)
        return table

    def build_hardware_tab(self):
        panel = self.panel
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        panel.hardware_widget = VmHardwareWidget()
        tab.setWidget(panel.hardware_widget)
        panel.hardware_widget.config_changed.connect(panel._on_vm_config_change_requested)
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

    def build_pool_tab(self):
        panel = self.panel
        panel.pool_widget = VmPoolWidget()
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
        if action in ("stop", "reset"):
            msgs = {
                "stop": tr("Force stop VM {vmid}? Unsaved data will be lost.").format(vmid=vmid),
                "reset": tr("Force reset VM {vmid}?").format(vmid=vmid),
            }
            msg = QMessageBox(QMessageBox.Warning, tr("Confirm"), msgs[action], parent=panel)
            yes = msg.addButton(tr("Yes"), QMessageBox.YesRole)
            msg.addButton(tr("No"), QMessageBox.NoRole)
            msg.setDefaultButton(yes)
            msg.exec()
            if msg.clickedButton() != yes:
                return
        node_name = panel._last_vm_data.get("node") or host_name
        vm_type = panel._last_vm_data.get("type", "qemu")
        from ...backend import VmActionWorker
        worker = VmActionWorker(cfg, node_name, vmid, vm_type, action)
        for btn in panel._action_buttons.values():
            btn.setEnabled(False)
        panel.detail_label.setText(f"VM/CT: {vmid} — {VM_ACTION_MESSAGE_LABELS.get(action, action)}...")
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
        panel.detail_label.setText(f"VM/CT: {vm.get('name', vm.get('vmid', ''))} — {msg}")
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
        vm_type = panel._last_vm_data.get("type", "qemu")
        node_name = panel._last_vm_data.get("node") or host_name
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        gen = panel._generation
        panel._workers_mgr.cancel_detail_worker()
        from ...backend import VmDetailWorker
        worker = VmDetailWorker(cfg, node_name, vmid, vm_type)
        worker.signals.detail_ready.connect(lambda d, g=gen, h=host_name, w=worker: (
            self.on_detail_loaded(d, g, h),
            panel._workers_mgr.discard_worker(w)
        ))
        panel._workers_mgr.current_worker = worker
        panel._workers_mgr.run_worker(worker)

    # --- VM info / metrics ---

    def show_vm_info_init(self, vm_name, vm_data, gen):
        panel = self.panel
        panel.detail_label.setText(tr("VM/CT: {name}").format(name=vm_name))
        panel._last_vm_data = vm_data
        panel.tabs.setTabVisible(TabIndex.MONITOR, True)
        panel.tabs.setTabVisible(TabIndex.HARDWARE, True)
        panel.tabs.setTabVisible(TabIndex.OPTIONS, True)
        panel.tabs.setTabVisible(TabIndex.HISTORY, True)
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
            panel.info_label.setText(tr("Loading detailed info..."))
            panel.info_stack.setCurrentIndex(0)
            cfg = panel._cfg_by_name.get(host_name)
            if cfg:
                node_name = vm_data.get("node") or host_name
                vm_type = vm_data.get("type", "qemu")
                from ...backend import VmDetailWorker
                worker = VmDetailWorker(cfg, node_name, vmid, vm_type)
                worker.signals.detail_ready.connect(lambda d, g=gen, h=host_name, w=worker: (self.on_detail_loaded(d, g, h), panel._workers_mgr.discard_worker(w)))
                panel._workers_mgr.current_worker = worker
                panel._workers_mgr.run_worker(worker)
        else:
            self.display_full_vm_info(vm_data, panel.details_cache[detail_key])

        node_name = vm_data.get("node") or host_name
        self.load_iso_for_node(host_name, node_name)

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

        panel.hardware_widget.set_context(host_name, vmid, node_name)
        panel.hardware_widget.set_vm_status(vm_data.get("status", ""))
        if node_name not in panel._iso_by_node and panel._all_iso_catalog:
            panel._iso_by_node[node_name] = {
                iso["volid"] for iso in panel._all_iso_catalog.get(node_name, [])
            }
        iso_set = panel._iso_by_node.setdefault(node_name, set())
        panel.hardware_widget.set_iso_list(iso_set)
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

    def on_detail_loaded(self, detail, gen, host_name):
        panel = self.panel
        if gen != panel._generation:
            return
        vmid = detail.get("vmid")
        detail_key = (vmid, host_name)
        vm_data = panel._vms_by_key.get((host_name, vmid), {})
        if detail["status"] == "ok":
            panel.details_cache[detail_key] = detail["data"]
            self.display_full_vm_info(vm_data, detail["data"])
            panel.tabs.setCurrentIndex(TabIndex.MONITOR)
            if detail_key in panel.config_cache:
                panel.hardware_widget.set_hardware_data(panel.config_cache[detail_key], detail["data"])
            if panel._last_vm_data:
                merged = {**vm_data, **detail["data"]}
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
        vm_type = "qemu"

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

    def reload_config(self, vmid, host_name):
        panel = self.panel
        detail_key = (vmid, host_name)
        panel.config_cache.pop(detail_key, None)
        cfg = panel._cfg_by_name.get(host_name)
        if cfg and panel._last_vm_data:
            node_name = panel._last_vm_data.get("node") or host_name
            gen = panel._generation
            from ...backend import VmConfigWorker
            worker = VmConfigWorker(cfg, node_name, vmid, "qemu")
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
            vm_type = basic.get("type") or detail.get("type", "")
            status = basic.get("status") or detail.get("status", "")
            pool = basic.get("pool") or tr("None")

            def safe_int(val): return int(val) if isinstance(val, (int, float)) else 0

            maxmem_bytes = safe_int(detail.get("maxmem") or basic.get("maxmem"))
            mem_used_bytes = safe_int(detail.get("mem"))
            maxmem_gb = round(maxmem_bytes / (1024**3), 2) if maxmem_bytes else 0
            mem_used_gb = round(mem_used_bytes / (1024**3), 2) if mem_used_bytes else 0

            cpus = detail.get("cpus") or basic.get("cpus") or 0
            cpu_usage = basic.get("cpu") or detail.get("cpu", 0)
            if isinstance(cpu_usage, float): cpu_usage = round(cpu_usage * 100, 1)

            maxdisk_bytes = safe_int(detail.get("maxdisk") or basic.get("maxdisk"))
            disk_used_bytes = safe_int(detail.get("disk"))
            maxdisk_gb = round(maxdisk_bytes / (1024**3), 2) if maxdisk_bytes else 0
            disk_used_gb = round(disk_used_bytes / (1024**3), 2) if disk_used_bytes else 0

            netin = detail.get("netin", 0)
            netout = detail.get("netout", 0)
            netin_mb = round(netin / (1024*1024), 2) if netin else 0
            netout_mb = round(netout / (1024*1024), 2) if netout else 0

            uptime = detail.get("uptime") or basic.get("uptime", "")
            tags = basic.get("tags") or detail.get("tags") or ""

            ha = detail.get("hastate", tr("Unknown"))
            running_qemu = detail.get("running-qemu", "")

            table = panel.vm_summary_table
            params = [
                (tr("Name"), name),
                (tr("Type"), vm_type.upper()),
                (tr("Status"), status_text(status)),
                (tr("Pool"), str(pool)),
                (tr("Tags"), tags or '-'),
                (tr("CPU Cores"), cpus),
                (tr("CPU usage (%)"), f"{cpu_usage}%"),
                (tr("RAM (GiB)"), f"{mem_used_gb} / {maxmem_gb}"),
                (tr("Disk (GiB)"), f"{disk_used_gb} / {maxdisk_gb}"),
                (tr("Net in (MB)"), netin_mb),
                (tr("Net out (MB)"), netout_mb),
                (tr("Uptime"), _format_uptime(uptime) if uptime else ''),
                (tr("HA state"), str(ha)),
            ]
            if running_qemu:
                params.append((tr("QEMU version"), running_qemu))
            table.setRowCount(len(params))
            for i, (k, v) in enumerate(params):
                table.setItem(i, 0, QTableWidgetItem(k))
                item = QTableWidgetItem(str(v))
                if k == tr("Status"):
                    if status == "running":
                        item.setForeground(QBrush(QColor("#22c55e")))
                    elif status == "stopped":
                        item.setForeground(QBrush(QColor("#ef4444")))
                    else:
                        item.setForeground(QBrush(QColor("#f59e0b")))
                table.setItem(i, 1, item)
            table.resizeRowsToContents()
            compact_table(table, 22)

            panel.info_stack.setCurrentIndex(1)
        except Exception:
            traceback.print_exc()
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
        status_color = "#22c55e" if status == "running" else "#ef4444" if status == "stopped" else "#f59e0b"
        panel._update_vm_summary_cell(tr("Status"), status_text(status), status_color)

        cpu_usage = vm_data.get("cpu") or detail.get("cpu", 0)
        if isinstance(cpu_usage, float):
            cpu_usage = round(cpu_usage * 100, 1)
        panel._update_vm_summary_cell(tr("CPU usage (%)"), f"{cpu_usage}%")

        def safe_int(val): return int(val) if isinstance(val, (int, float)) else 0

        maxmem_bytes = safe_int(detail.get("maxmem") or vm_data.get("maxmem"))
        mem_used_bytes = safe_int(detail.get("mem"))
        maxmem_gb = round(maxmem_bytes / (1024**3), 2) if maxmem_bytes else 0
        mem_used_gb = round(mem_used_bytes / (1024**3), 2) if mem_used_bytes else 0
        panel._update_vm_summary_cell(tr("RAM (GiB)"), f"{mem_used_gb} / {maxmem_gb}")

        maxdisk_bytes = safe_int(detail.get("maxdisk") or vm_data.get("maxdisk"))
        disk_used_bytes = safe_int(detail.get("disk"))
        maxdisk_gb = round(maxdisk_bytes / (1024**3), 2) if maxdisk_bytes else 0
        disk_used_gb = round(disk_used_bytes / (1024**3), 2) if disk_used_bytes else 0
        panel._update_vm_summary_cell(tr("Disk (GiB)"), f"{disk_used_gb} / {maxdisk_gb}")

        netin = detail.get("netin", 0)
        netout = detail.get("netout", 0)
        netin_mb = round(netin / (1024*1024), 2) if netin else 0
        netout_mb = round(netout / (1024*1024), 2) if netout else 0
        panel._update_vm_summary_cell(tr("Net in (MB)"), str(netin_mb))
        panel._update_vm_summary_cell(tr("Net out (MB)"), str(netout_mb))

        uptime = detail.get("uptime") or vm_data.get("uptime", "")
        panel._update_vm_summary_cell(tr("Uptime"), _format_uptime(uptime) if uptime else '')

    def update_pool_cells(self):
        panel = self.panel
        pool_name = panel.current_obj_name
        vms = [vm for vm in panel.all_vms if vm.get("pool") == pool_name]
        panel.pool_widget.set_pool_vms(vms)

    def show_pool_info(self, pool_name):
        panel = self.panel
        panel.detail_label.setText(tr("Pool: {name}").format(name=pool_name))
        panel.tabs.setTabVisible(TabIndex.MONITOR, False)
        panel.tabs.setTabVisible(TabIndex.HARDWARE, False)
        panel.tabs.setTabVisible(TabIndex.OPTIONS, False)
        panel.tabs.setTabVisible(TabIndex.HISTORY, False)
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
                    and "iso" in (s.get("content", "").split(","))]
        for storage_info in storages:
            storage = storage_info.get("storage")
            if not storage:
                continue
            from ..api.metrics import StorageContentListWorker
            worker = StorageContentListWorker(cfg, node_name, storage, "iso")
            worker.signals.result.connect(
                lambda sn, ct, data, n=node_name: self.on_vm_iso_loaded(n, data)
            )
            worker.signals.error.connect(
                lambda sn, ct, err, n=node_name: None
            )
            panel._workers_mgr.run_worker(worker)

    def on_vm_iso_loaded(self, node_name, data):
        panel = self.panel
        vols = {v.get("volid") for v in (data or []) if v.get("volid")}
        if node_name in panel._iso_by_node:
            panel._iso_by_node[node_name].update(vols)