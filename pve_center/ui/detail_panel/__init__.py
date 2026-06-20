import logging

from PySide6.QtWidgets import (QLabel, QWidget, QTabWidget, QPushButton,
                               QHBoxLayout, QVBoxLayout)
from PySide6.QtCore import Qt, Signal

from ..utils import build_cfg_index, build_vm_index
from ..vm_actions import VM_ACTION_BUTTON_LABELS, VM_ACTION_ICONS, VM_ACTION_TOOLTIPS
from ..icons import get_icon
from ..i18n import tr
from ..theme import Color

from ._constants import TabIndex
from ._worker_manager import WorkerManager
from ._host_tabs import HostTabs
from ._storage_tabs import StorageTabs
from ._vm_tabs import VMTabs
from ._table_utils import set_cell_text

logger = logging.getLogger(__name__)


class DetailPanel(QWidget):
    config_update_result = Signal(str)

    def __init__(self, nodes_cfg):
        super().__init__()
        self.nodes_cfg = nodes_cfg
        self._cfg_by_name = build_cfg_index(self.nodes_cfg)
        self._vms_by_key = {}
        self.all_nodes = []
        self.all_vms = []
        self.all_storages = []
        self.details_cache = {}
        self.config_cache = {}
        self.metrics_cache = {}
        self.task_history_cache = {}
        self._storage_content_pending = {}
        self._iso_by_node = {}
        self._all_iso_catalog = {}
        self._vm_iso_pending = {}
        self._last_vm_data = None
        self.current_obj_type = None
        self.current_obj_name = None
        self.current_obj_data = None
        self._generation = 0
        self.all_pools = []
        self.all_ha_groups = []

        self._workers_mgr = WorkerManager()
        self._host_tabs = HostTabs(self)
        self._storage_tabs = StorageTabs(self)
        self._vm_tabs = VMTabs(self)

        self.detail_label = QLabel(tr("Select object in tree"))
        self.detail_label.setAlignment(Qt.AlignTop)
        self.detail_label.setContentsMargins(8, 2, 0, 2)

        self.vm_action_bar = QWidget()
        self.vm_action_bar.setMinimumHeight(32)
        self.vm_action_bar.setVisible(False)
        action_layout = QHBoxLayout(self.vm_action_bar)
        action_layout.setContentsMargins(4, 2, 4, 2)
        action_layout.setSpacing(4)

        self._vm_actions = VM_ACTION_BUTTON_LABELS
        action_layout.addStretch()
        self._action_buttons = {}
        for action_key, label in self._vm_actions.items():
            btn = QPushButton(get_icon(VM_ACTION_ICONS[action_key]), label)
            btn.setMinimumHeight(24)
            btn.setObjectName("accentBtn" if action_key in ("start",) else "")
            btn.setToolTip(VM_ACTION_TOOLTIPS[action_key])
            btn.clicked.connect(lambda checked, a=action_key: self._on_vm_action(a))
            action_layout.addWidget(btn)
            self._action_buttons[action_key] = btn

        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setFixedHeight(18)
        sep.setStyleSheet(f"background: {Color.BORDER};")
        action_layout.addWidget(sep)

        self._console_btn = QPushButton(get_icon("console"), tr("Console"))
        self._console_btn.setMinimumHeight(24)
        self._console_btn.setObjectName("accentBtn")
        self._console_btn.setToolTip(tr("Open SPICE/VNC console"))
        self._console_btn.clicked.connect(self._on_vm_console)
        action_layout.addWidget(self._console_btn)

        self.tabs = QTabWidget()
        self._build_tabs()

        self.tabs.hide()

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.detail_label)
        main_layout.addWidget(self.vm_action_bar)
        main_layout.addWidget(self.tabs)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

    def _build_tabs(self):
        tabs = self.tabs
        # 0: Monitoring
        tabs.addTab(self._vm_tabs.build_monitoring_tab(), get_icon("monitor"), tr("Monitoring"))
        # 1: Hardware
        tabs.addTab(self._vm_tabs.build_hardware_tab(), get_icon("hardware"), tr("Hardware"))
        # 2: Options
        tabs.addTab(self._vm_tabs.build_options_tab(), get_icon("options"), tr("Options"))
        # 3: History
        tabs.addTab(self._vm_tabs.build_history_tab(), get_icon("history"), tr("History"))
        # 4: Host VMs
        tabs.addTab(self._host_tabs.build_host_vm_tab(), get_icon("vm"), tr("Virtual Machines"))
        tabs.setTabVisible(TabIndex.HOST_VMS, False)
        # 5: Pool VMs
        tabs.addTab(self._vm_tabs.build_pool_tab(), get_icon("pool"), tr("Pool VMs"))
        tabs.setTabVisible(TabIndex.POOL_VMS, False)
        # 6: Summary
        tabs.addTab(self._host_tabs.build_summary_tab(), get_icon("host"), tr("Summary"))
        tabs.setTabVisible(TabIndex.SUMMARY, False)
        # 7: Storages overview
        tabs.addTab(self._storage_tabs.build_storage_overview_tab(), get_icon("storage"), tr("Storage"))
        tabs.setTabVisible(TabIndex.STORAGES, False)
        # 8: Host storage
        tabs.addTab(self._host_tabs.build_host_storage_tab(), get_icon("storage"), tr("Storage"))
        tabs.setTabVisible(TabIndex.HOST_STORAGE, False)
        # 9: Storage detail
        tabs.addTab(self._storage_tabs.build_storage_detail_tab(), get_icon("storage"), tr("Storage Detail"))
        tabs.setTabVisible(TabIndex.STORAGE_DETAIL, False)
        # 10: Backups
        tabs.addTab(self._storage_tabs.build_backups_tab(), get_icon("backup"), tr("Backups"))
        tabs.setTabVisible(TabIndex.BACKUPS, False)
        # 11: VM Disks
        tabs.addTab(self._storage_tabs.build_disks_vm_tab(), get_icon("disk"), tr("VM Disks"))
        tabs.setTabVisible(TabIndex.DISKS_VM, False)
        # 12: ISO
        tabs.addTab(self._storage_tabs.build_iso_tab(), get_icon("iso"), tr("ISO"))
        tabs.setTabVisible(TabIndex.ISO, False)
        # 13: Templates
        tabs.addTab(self._storage_tabs.build_templates_tab(), get_icon("template"), tr("Templates"))
        tabs.setTabVisible(TabIndex.TEMPLATES, False)
        # 14: Network
        tabs.addTab(self._host_tabs.build_network_tab(), get_icon("network"), tr("Network"))
        tabs.setTabVisible(TabIndex.NETWORK, False)
        # 15: Services
        tabs.addTab(self._host_tabs.build_services_tab(), get_icon("services"), tr("Services"))
        tabs.setTabVisible(TabIndex.SERVICES, False)
        # 16: Host disks
        tabs.addTab(self._host_tabs.build_host_disks_tab(), get_icon("disk"), tr("Disks"))
        tabs.setTabVisible(TabIndex.HOST_DISKS, False)
        # 17: Snapshots
        tabs.addTab(self._host_tabs.build_snapshots_tab(), get_icon("snapshot"), tr("Snapshots"))
        tabs.setTabVisible(TabIndex.SNAPSHOTS, False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_lists(self, all_nodes, all_vms, all_storages=None):
        self.all_nodes = all_nodes
        self.all_vms = all_vms
        self._vms_by_key = build_vm_index(all_vms)
        self.all_storages = all_storages or []

    def set_iso_catalog(self, iso_images):
        self._all_iso_catalog = iso_images or {}

    def show_details(self, obj_type, obj_name, data):
        self.tabs.show()
        if obj_type == "vm":
            self.vm_action_bar.setVisible(True)
            self._update_action_buttons(data)
        else:
            self.vm_action_bar.setVisible(False)
        try:
            self.current_obj_type = obj_type
            self.current_obj_name = obj_name
            self.current_obj_data = data
            self._generation += 1
            gen = self._generation
            self.metrics_widget.setVisible(True)
            self.info_label.setStyleSheet("")

            self._workers_mgr.cancel_detail_worker()
            self._workers_mgr.cancel_config_worker()
            self._workers_mgr.cancel_history_worker()
            self.metrics_widget.clear_curves()

            for idx in (TabIndex.OPTIONS, TabIndex.HISTORY, TabIndex.HOST_VMS,
                        TabIndex.POOL_VMS, TabIndex.SUMMARY, TabIndex.STORAGES,
                        TabIndex.HOST_STORAGE, TabIndex.STORAGE_DETAIL,
                        TabIndex.BACKUPS, TabIndex.DISKS_VM, TabIndex.ISO,
                        TabIndex.TEMPLATES, TabIndex.NETWORK, TabIndex.SERVICES,
                        TabIndex.HOST_DISKS, TabIndex.SNAPSHOTS):
                self.tabs.setTabVisible(idx, False)

            if obj_type == "cluster_folder":
                self._host_tabs.show_cluster_folder(obj_name)
            elif obj_type == "storage_folder":
                self._storage_tabs.show_storage_folder()
            elif obj_type == "standalone_folder":
                self._host_tabs.show_standalone_folder(obj_name)
            elif obj_type == "cluster":
                self._host_tabs.show_cluster(obj_name)
            elif obj_type == "host":
                self._host_tabs.show_host_info(obj_name, data)
            elif obj_type == "pool":
                self._vm_tabs.show_pool_info(obj_name)
            elif obj_type == "vm":
                self._vm_tabs.show_vm_info_init(obj_name, data, gen)
            elif obj_type == "storage":
                self._storage_tabs.show_storage_detail(obj_name, data)

        except Exception as exc:
            logger.debug("show_details error", exc_info=True)
            self.config_update_result.emit(
                tr("Error: {err}").format(err=str(exc)[:100])
            )
            self.detail_label.setText(tr("Error: {name}").format(name=obj_name))
            self.info_label.setText(tr("An error occurred while loading information"))
            self.info_stack.setCurrentIndex(0)

    def refresh_current_view(self):
        if self.current_obj_type is None:
            return
        saved_tab = self.tabs.currentIndex()

        if self.current_obj_type in ("standalone_folder", "cluster_folder", "storage_folder"):
            if self.current_obj_type == "standalone_folder":
                self._host_tabs.show_standalone_folder("")
            elif self.current_obj_type == "cluster_folder":
                self._host_tabs.show_cluster_folder("")
            elif self.current_obj_type == "storage_folder":
                self._storage_tabs.show_storage_folder()
        elif self.current_obj_type == "cluster":
            hosts = []
            for node in self.all_nodes:
                host_name = node.get("host_name", "")
                cfg = self._cfg_by_name.get(host_name)
                if cfg and cfg.get("cluster") == self.current_obj_name:
                    hosts.append(node)
            self._host_tabs.update_cluster_summary_cells(hosts)
        elif self.current_obj_type == "host":
            host_data = next((n for n in self.all_nodes if n.get("node") == self.current_obj_name), None)
            if host_data:
                if host_data.get("status") == "error":
                    self._host_tabs.show_host_info(self.current_obj_name, host_data)
                else:
                    self._host_tabs.update_host_cells(host_data)
                    self._host_tabs.fetch_host_metrics(host_data)
        elif self.current_obj_type == "pool":
            self._vm_tabs.update_pool_cells()
        elif self.current_obj_type == "vm":
            vm_data = self.current_obj_data
            if vm_data:
                lookup_host = vm_data.get("host_name") or vm_data.get("node")
                fresh = self._vms_by_key.get((lookup_host, vm_data.get("vmid")))
                if fresh:
                    self.current_obj_data = fresh
                    self.hardware_widget.set_vm_status(fresh.get("status", ""))
                self._vm_tabs.update_vm_cells(fresh or vm_data)
                self._vm_tabs.show_vm_metrics(fresh or vm_data)
        elif self.current_obj_type == "storage":
            self._storage_tabs.update_storage_cells()

        self.tabs.setCurrentIndex(saved_tab)

    # ------------------------------------------------------------------
    # Delegates to tab controllers
    # ------------------------------------------------------------------
    def _on_vm_action(self, action):
        self._vm_tabs.on_vm_action(action)

    def _update_action_buttons(self, vm_data=None):
        self._vm_tabs.update_action_buttons(vm_data)

    def _on_vm_console(self):
        self._vm_tabs.on_vm_console()

    def _on_timeframe_changed(self, new_timeframe):
        if self.current_obj_type == "host":
            host_data = next((n for n in self.all_nodes if n.get("node") == self.current_obj_name), None)
            if host_data:
                self._host_tabs.fetch_host_metrics(host_data)
        elif self._last_vm_data is not None:
            self._vm_tabs.show_vm_metrics(self._last_vm_data)

    def _on_storage_timeframe_changed(self, idx):
        self._storage_tabs.on_storage_timeframe_changed(idx)

    def _on_vm_config_change_requested(self, host_name, vmid_str, params):
        self._vm_tabs.on_vm_config_change_requested(host_name, vmid_str, params)

    # ------------------------------------------------------------------
    # Small helpers that tab controllers call back
    # ------------------------------------------------------------------
    def _set_storage_param(self, label, value):
        table = self.storage_detail_params
        for r in range(table.rowCount()):
            if table.item(r, 0) and table.item(r, 0).text() == label:
                set_cell_text(table, r, 1, str(value))
                break