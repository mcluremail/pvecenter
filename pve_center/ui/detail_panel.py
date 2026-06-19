import traceback
from collections import defaultdict
from datetime import datetime
from enum import IntEnum
from PySide6.QtWidgets import (QLabel, QStackedWidget, QVBoxLayout, QWidget, QTabWidget,
                               QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView,
                               QSizePolicy, QProgressBar, QHBoxLayout, QComboBox, QPushButton,
                               QMenu, QMessageBox)
from PySide6.QtCore import Qt, QThreadPool, Signal
from .hover import enable_row_hover
from .icons import get_icon
from .utils import status_text, format_uptime as _format_uptime, build_cfg_index, build_vm_index, parse_pve_error
from .vm_actions import VM_ACTION_BUTTON_LABELS, VM_ACTION_MESSAGE_LABELS, VM_ACTION_ICONS
from .i18n import tr
from ..config import save_ui_state, load_ui_state
import json as _json
from PySide6.QtGui import QColor, QBrush

_HEADER_STYLE = "QHeaderView::section { padding-left: 4px; }"


def _fmt_pveversion(val):
    val = str(val)
    return val.split("/")[1] if "/" in val else val


def _progress_style(value, max_val=100):
    """Returns QSS for QProgressBar with dynamic color."""
    pct = int((value / max_val) * 100) if max_val else 0
    if pct < 50:
        color = "#22c55e"
    elif pct < 80:
        color = "#f59e0b"
    else:
        color = "#ef4444"
    return (
        f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}"
        f"QProgressBar {{ border: 1px solid #d1d5db; border-radius: 3px;"
        f" text-align: center; font-size: 11px; background: #f3f4f6; }}"
    )

try:
    import pyqtgraph as pg
    pg.setConfigOption('background', 'w')
    pg.setConfigOption('foreground', 'k')
    _HAS_PG = True
except ImportError:
    pg = None
    _HAS_PG = False
from .widgets.vm_metrics_widget import VmMetricsWidget
from .widgets.vm_hardware_widget import VmHardwareWidget
from .widgets.vm_options_widget import VmOptionsWidget
from .widgets.vm_task_history_widget import VmTaskHistoryWidget
from .widgets.vm_pool_widget import VmPoolWidget


class TabIndex(IntEnum):
    """Named tab indices for the detail panel.
    When adding/reordering tabs — edit only this enum."""
    MONITOR = 0       # Monitoring (graphs)
    HARDWARE = 1      # Hardware
    OPTIONS = 2       # Options
    HISTORY = 3       # Task history
    HOST_VMS = 4      # Host VMs
    POOL_VMS = 5      # Pool VMs
    SUMMARY = 6       # Datacenter summary
    STORAGES = 7      # Storages (overview)
    HOST_STORAGE = 8  # Host storage
    STORAGE_DETAIL = 9  # Storage detail
    BACKUPS = 10      # Backups
    DISKS_VM = 11     # VM disks
    ISO = 12          # ISO images
    TEMPLATES = 13    # Templates
    NETWORK = 14      # Network
    SERVICES = 15     # Services
    HOST_DISKS = 16   # Host disks
    SNAPSHOTS = 17    # Snapshots

_MAX_WORKERS_DP = 8


class DetailPanel(QWidget):
    config_update_result = Signal(str)  # toast message
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
        self._all_iso_catalog = {}  # source: mainwindow.all_iso_images
        self._vm_iso_pending = {}
        self._workers = set()
        self.current_worker = None
        self.current_config_worker = None
        self.current_hist_worker = None
        self._last_vm_data = None
        self.current_obj_type = None
        self.current_obj_name = None
        self.current_obj_data = None
        self._generation = 0

        self.detail_label = QLabel(tr("Select object in tree"))
        self.detail_label.setAlignment(Qt.AlignTop)
        self.detail_label.setContentsMargins(8, 2, 0, 2)

        self.vm_action_bar = QWidget()
        self.vm_action_bar.setFixedHeight(32)
        self.vm_action_bar.setVisible(False)
        action_layout = QHBoxLayout(self.vm_action_bar)
        action_layout.setContentsMargins(4, 2, 4, 2)
        action_layout.setSpacing(4)

        self._vm_actions = VM_ACTION_BUTTON_LABELS
        action_layout.addStretch()
        self._action_buttons = {}
        for action_key, label in self._vm_actions.items():
            btn = QPushButton(get_icon(VM_ACTION_ICONS[action_key]), label)
            btn.setFixedHeight(24)
            btn.setObjectName("accentBtn" if action_key in ("start",) else "")
            btn.clicked.connect(lambda checked, a=action_key: self._on_vm_action(a))
            action_layout.addWidget(btn)
            self._action_buttons[action_key] = btn

        # Separator between power actions and console
        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setFixedHeight(18)
        sep.setStyleSheet("background: #dde1e7;")
        action_layout.addWidget(sep)

        self._console_btn = QPushButton(get_icon("console"), tr("Console"))
        self._console_btn.setFixedHeight(24)
        self._console_btn.setObjectName("accentBtn")
        self._console_btn.clicked.connect(self._on_vm_console)
        action_layout.addWidget(self._console_btn)

        self.tabs = QTabWidget()

        # --- Tab 0: Monitoring ---
        self.monitoring_tab = QScrollArea()
        self.monitoring_tab.setWidgetResizable(True)
        monitor_widget = QWidget()
        monitor_layout = QVBoxLayout(monitor_widget)
        monitor_layout.setContentsMargins(0, 0, 0, 0)

        self.info_stack = QStackedWidget()

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.info_stack.addWidget(self.info_label)

        self.vm_summary_table = QTableWidget()
        self.vm_summary_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.vm_summary_table.verticalHeader().hide()
        self.vm_summary_table.setColumnCount(2)
        self.vm_summary_table.setHorizontalHeaderLabels([tr("Parameter"), tr("Value")])
        self.vm_summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.vm_summary_table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.vm_summary_table.horizontalHeader().setStyleSheet(_HEADER_STYLE)
        self.vm_summary_table.setWordWrap(True)
        self.vm_summary_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.vm_summary_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.vm_summary_table.setAlternatingRowColors(True)
        enable_row_hover(self.vm_summary_table)
        self.info_stack.addWidget(self.vm_summary_table)

        self.info_stack.setFixedWidth(320)
        self.info_stack.setMinimumHeight(260)
        self.info_stack.setMaximumHeight(340)
        # Stretch table to fill QStackedWidget area
        self.vm_summary_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.metrics_widget = VmMetricsWidget()
        self.metrics_widget.setMinimumHeight(260)
        self.metrics_widget.setMaximumHeight(340)
        self.metrics_widget.timeframe_changed.connect(self._on_timeframe_changed)

        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 8, 0)
        middle.addWidget(self.info_stack)
        middle.addWidget(self.metrics_widget, 1)
        monitor_layout.addLayout(middle)
        monitor_layout.addStretch()

        self.monitoring_tab.setWidget(monitor_widget)
        self.tabs.addTab(self.monitoring_tab, get_icon("monitor"), tr("Monitoring"))

        # --- Tab 1: Hardware ---
        self.hardware_tab = QScrollArea()
        self.hardware_tab.setWidgetResizable(True)
        self.hardware_widget = VmHardwareWidget()
        self.hardware_tab.setWidget(self.hardware_widget)
        self.tabs.addTab(self.hardware_tab, get_icon("hardware"), tr("Hardware"))
        self.hardware_widget.config_changed.connect(self._on_vm_config_change_requested)

        # --- Tab 2: Options ---
        self.options_tab = QScrollArea()
        self.options_tab.setWidgetResizable(True)
        self.options_widget = VmOptionsWidget()
        self.options_tab.setWidget(self.options_widget)
        self.tabs.addTab(self.options_tab, get_icon("options"), tr("Options"))
        self.options_widget.config_changed.connect(self._on_vm_config_change_requested)

        # --- Tab 3: Task history ---
        self.history_tab = QScrollArea()
        self.history_tab.setWidgetResizable(True)
        self.task_history_widget = VmTaskHistoryWidget()
        self.history_tab.setWidget(self.task_history_widget)
        self.tabs.addTab(self.history_tab, get_icon("history"), tr("History"))

        # --- Tab 4: Host VM table ---
        self.host_vm_table = self._make_table(
            [tr("Name"), tr("Type"), tr("Node"), tr("Status"), "CPU %"],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 50),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 70),
             (QHeaderView.Interactive, 55)],
        )
        self.host_tab = QScrollArea()
        self.host_tab.setWidgetResizable(True)
        host_container = QWidget()
        host_layout = QVBoxLayout(host_container)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.addWidget(self.host_vm_table)
        self.host_tab.setWidget(host_container)
        self.tabs.addTab(self.host_tab, get_icon("vm"), tr("Virtual Machines"))
        self.tabs.setTabVisible(TabIndex.HOST_VMS, False)

        # --- Tab 5: Pool VMs table ---
        self.pool_widget = VmPoolWidget()
        self.pool_tab = QScrollArea()
        self.pool_tab.setWidgetResizable(True)
        self.pool_tab.setWidget(self.pool_widget)
        self.tabs.addTab(self.pool_tab, get_icon("pool"), tr("Pool VMs"))
        self.tabs.setTabVisible(TabIndex.POOL_VMS, False)

        # --- Tab 6: Host summary ---
        self.datacenter_summary = self._make_table(
            [tr("Host"), tr("Status"), tr("Address"), tr("CPU %"), tr("RAM (GiB)"), tr("Uptime")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 70),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 55),
             (QHeaderView.Interactive, 80), (QHeaderView.Interactive, 85)],
        )
        self.summary_tab = QScrollArea()
        self.summary_tab.setWidgetResizable(True)
        summary_container = QWidget()
        summary_layout = QVBoxLayout(summary_container)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.addWidget(self.datacenter_summary)
        self.summary_tab.setWidget(summary_container)
        self.tabs.addTab(self.summary_tab, get_icon("host"), tr("Summary"))
        self.tabs.setTabVisible(TabIndex.SUMMARY, False)

        # --- Tab 7: Storages overview ---
        self.storage_table = self._make_table(
            [tr("Name"), tr("Type"), tr("Content"), tr("Cluster / Node"), tr("Used"), tr("Total"), tr("Usage")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 65),
             (QHeaderView.Stretch, None), (QHeaderView.Stretch, None),
             (QHeaderView.Interactive, 70), (QHeaderView.Interactive, 70),
             (QHeaderView.Interactive, 95)],
        )
        self.storage_tab = QScrollArea()
        self.storage_tab.setWidgetResizable(True)
        storage_container = QWidget()
        storage_layout = QVBoxLayout(storage_container)
        storage_layout.setContentsMargins(0, 0, 0, 0)
        storage_layout.addWidget(self.storage_table)
        self.storage_tab.setWidget(storage_container)
        self.tabs.addTab(self.storage_tab, get_icon("storage"), tr("Storage"))
        self.tabs.setTabVisible(TabIndex.STORAGES, False)

        # --- Tab 8: Host storage ---
        self.host_storage_table = self._make_table(
            [tr("Name"), tr("Type"), tr("Content"), tr("Used"), tr("Total"), tr("Usage")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 65),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 70),
             (QHeaderView.Interactive, 70), (QHeaderView.Interactive, 95)],
        )
        self.host_storage_tab_widget = QWidget()
        hs_layout = QVBoxLayout(self.host_storage_tab_widget)
        hs_layout.setContentsMargins(0, 0, 0, 0)
        hs_layout.addWidget(self.host_storage_table)
        self.tabs.addTab(self.host_storage_tab_widget, get_icon("storage"), tr("Storage"))
        self.tabs.setTabVisible(TabIndex.HOST_STORAGE, False)

        # --- Tab 9: Storage detail ---
        self.storage_detail_widget = QWidget()
        self.storage_detail_layout = QVBoxLayout(self.storage_detail_widget)
        self.storage_detail_layout.setContentsMargins(8, 8, 8, 8)

        self.storage_detail_name = QLabel()
        self.storage_detail_name.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.storage_detail_layout.addWidget(self.storage_detail_name)

        self.storage_detail_params = self._make_table(
            [tr("Parameter"), tr("Value")],
            [(QHeaderView.Stretch, None), (QHeaderView.Stretch, None)],
        )
        self.storage_detail_layout.addWidget(self.storage_detail_params)

        self.storage_detail_bar = QProgressBar()
        self.storage_detail_bar.setRange(0, 100)
        self.storage_detail_bar.setTextVisible(True)
        self.storage_detail_bar.setMinimumHeight(24)
        self.storage_detail_layout.addWidget(self.storage_detail_bar)

        # Storage fill-level graph over time
        self.storage_metrics_row = QHBoxLayout()
        self.storage_metrics_row.addWidget(QLabel(tr("Fill level")))
        self.storage_metrics_row.addStretch()
        self.storage_detail_tf_combo = QComboBox()
        self.storage_detail_tf_combo.addItem(tr("hour"), "hour")
        self.storage_detail_tf_combo.addItem(tr("day"), "day")
        self.storage_detail_tf_combo.addItem(tr("week"), "week")
        self.storage_detail_tf_combo.addItem(tr("month"), "month")
        self.storage_detail_tf_combo.addItem(tr("year"), "year")
        self.storage_detail_tf_combo.setCurrentIndex(0)
        self.storage_detail_tf_combo.currentIndexChanged.connect(
            self._on_storage_timeframe_changed
        )
        self.storage_metrics_row.addWidget(self.storage_detail_tf_combo)
        self.storage_detail_layout.addLayout(self.storage_metrics_row)

        self.storage_detail_plot = QWidget()
        if _HAS_PG:
            date_axis = pg.DateAxisItem(orientation='bottom')
            self.storage_plot_widget = pg.PlotWidget(
                axisItems={'bottom': date_axis}, title=tr("Fill level")
            )
            self.storage_plot_widget.setLabel('left', 'GiB')
            self.storage_plot_widget.showGrid(x=True, y=True)
            self.storage_plot_widget.enableAutoRange(axis='y')
            self.storage_plot_widget.setMouseEnabled(x=False, y=False)
            self.storage_plot_widget.setFixedHeight(220)
            self.storage_plot_curve = self.storage_plot_widget.plot(
                [], [], pen=pg.mkPen('#374151', width=2)
            )
            sd_plot_layout = QVBoxLayout(self.storage_detail_plot)
            sd_plot_layout.setContentsMargins(0, 0, 0, 0)
            sd_plot_layout.addWidget(self.storage_plot_widget)
        else:
            sd_plot_layout = QVBoxLayout(self.storage_detail_plot)
            sd_plot_layout.setContentsMargins(0, 0, 0, 0)
            sd_plot_layout.addWidget(QLabel(tr("PyQtGraph not installed")))
        self.storage_detail_layout.addWidget(self.storage_detail_plot)

        self.storage_detail_nodes_label = QLabel()
        self.storage_detail_nodes_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        self.storage_detail_layout.addWidget(self.storage_detail_nodes_label)

        self.storage_detail_nodes_table = self._make_table(
            [tr("Node"), tr("Type"), tr("Content"), tr("Used"), tr("Total"), tr("Usage")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 65),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 70),
             (QHeaderView.Interactive, 70), (QHeaderView.Interactive, 95)],
            sortable=True,
        )
        self.storage_detail_layout.addWidget(self.storage_detail_nodes_table)

        self.storage_detail_layout.addStretch()
        self.tabs.addTab(self.storage_detail_widget, get_icon("storage"), tr("Storage Detail"))
        self.tabs.setTabVisible(TabIndex.STORAGE_DETAIL, False)

        # --- Tab 10: Backups ---
        self.storage_backups_table = self._make_table(
            [tr("VM"), tr("Type"), tr("Format"), tr("Size"), tr("Created")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 65),
             (QHeaderView.Interactive, 60), (QHeaderView.Interactive, 70),
             (QHeaderView.Stretch, None)],
            sortable=True,
        )
        self.storage_backups_stack = QStackedWidget()
        self.storage_backups_loading = QLabel(tr("Loading..."))
        self.storage_backups_loading.setAlignment(Qt.AlignCenter)
        self.storage_backups_loading.setStyleSheet("color: #9ca3af; font-size: 14px;")
        self.storage_backups_stack.addWidget(self.storage_backups_loading)
        self.storage_backups_stack.addWidget(self._make_filterable_table(self.storage_backups_table))
        self.storage_backups_stack.setCurrentIndex(0)
        self.storage_backups_tab = QScrollArea()
        self.storage_backups_tab.setWidgetResizable(True)
        sb_container = QWidget()
        sb_layout = QVBoxLayout(sb_container)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.addWidget(self.storage_backups_stack)
        self.storage_backups_tab.setWidget(sb_container)
        self.tabs.addTab(self.storage_backups_tab, get_icon("backup"), tr("Backups"))
        self.tabs.setTabVisible(TabIndex.BACKUPS, False)

        # --- Tab 11: VM Disks ---
        self.storage_disks_table = self._make_table(
            [tr("VM"), tr("Name"), tr("Volume"), tr("Bus"), tr("Size")],
            [(QHeaderView.Stretch, None), (QHeaderView.Stretch, None),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 55),
             (QHeaderView.Interactive, 70)],
            sortable=True,
        )
        self.storage_disks_stack = QStackedWidget()
        self.storage_disks_loading = QLabel(tr("Loading..."))
        self.storage_disks_loading.setAlignment(Qt.AlignCenter)
        self.storage_disks_loading.setStyleSheet("color: #9ca3af; font-size: 14px;")
        self.storage_disks_stack.addWidget(self.storage_disks_loading)
        self.storage_disks_stack.addWidget(self._make_filterable_table(self.storage_disks_table))
        self.storage_disks_stack.setCurrentIndex(0)
        self.storage_disks_tab = QScrollArea()
        self.storage_disks_tab.setWidgetResizable(True)
        sd_container = QWidget()
        sd2_layout = QVBoxLayout(sd_container)
        sd2_layout.setContentsMargins(0, 0, 0, 0)
        sd2_layout.addWidget(self.storage_disks_stack)
        self.storage_disks_tab.setWidget(sd_container)
        self.tabs.addTab(self.storage_disks_tab, get_icon("disk"), tr("VM Disks"))
        self.tabs.setTabVisible(TabIndex.DISKS_VM, False)

        # --- Tab 12: ISO images ---
        self.storage_iso_table = self._make_table(
            [tr("Volume"), tr("Format"), tr("Size"), tr("Modified")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 60),
             (QHeaderView.Interactive, 70), (QHeaderView.Stretch, None)],
            sortable=True,
        )
        self.storage_iso_stack = QStackedWidget()
        self.storage_iso_loading = QLabel(tr("Loading..."))
        self.storage_iso_loading.setAlignment(Qt.AlignCenter)
        self.storage_iso_loading.setStyleSheet("color: #9ca3af; font-size: 14px;")
        self.storage_iso_stack.addWidget(self.storage_iso_loading)
        self.storage_iso_stack.addWidget(self._make_filterable_table(self.storage_iso_table))
        self.storage_iso_stack.setCurrentIndex(0)
        self.storage_iso_tab = QScrollArea()
        self.storage_iso_tab.setWidgetResizable(True)
        iso_container = QWidget()
        iso_layout = QVBoxLayout(iso_container)
        iso_layout.setContentsMargins(0, 0, 0, 0)
        iso_layout.addWidget(self.storage_iso_stack)
        self.storage_iso_tab.setWidget(iso_container)
        self.tabs.addTab(self.storage_iso_tab, get_icon("iso"), tr("ISO"))
        self.tabs.setTabVisible(TabIndex.ISO, False)

        # --- Tab 13: Templates ---
        self.storage_tpl_table = self._make_table(
            [tr("Volume"), tr("Format"), tr("Size"), tr("Modified")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 60),
             (QHeaderView.Interactive, 70), (QHeaderView.Stretch, None)],
            sortable=True,
        )
        self.storage_tpl_stack = QStackedWidget()
        self.storage_tpl_loading = QLabel(tr("Loading..."))
        self.storage_tpl_loading.setAlignment(Qt.AlignCenter)
        self.storage_tpl_loading.setStyleSheet("color: #9ca3af; font-size: 14px;")
        self.storage_tpl_stack.addWidget(self.storage_tpl_loading)
        self.storage_tpl_stack.addWidget(self._make_filterable_table(self.storage_tpl_table))
        self.storage_tpl_stack.setCurrentIndex(0)
        self.storage_tpl_tab = QScrollArea()
        self.storage_tpl_tab.setWidgetResizable(True)
        tpl_container = QWidget()
        tpl_layout = QVBoxLayout(tpl_container)
        tpl_layout.setContentsMargins(0, 0, 0, 0)
        tpl_layout.addWidget(self.storage_tpl_stack)
        self.storage_tpl_tab.setWidget(tpl_container)
        self.tabs.addTab(self.storage_tpl_tab, get_icon("template"), tr("Templates"))
        self.tabs.setTabVisible(TabIndex.TEMPLATES, False)

        # --- Tab 14: Network ---
        self.host_network_loading = QLabel(tr("Loading..."))
        self.host_network_loading.setAlignment(Qt.AlignCenter)
        self.host_network_loading.setStyleSheet("color: #9ca3af; font-size: 14px;")
        self.host_network_table = self._make_table(
            [tr("Interface"), tr("Type"), tr("State"), "Method", "CIDR"],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 65),
             (QHeaderView.Interactive, 75), (QHeaderView.Interactive, 70),
             (QHeaderView.Stretch, None)],
        )
        self.host_network_stack = QStackedWidget()
        self.host_network_stack.addWidget(self.host_network_loading)
        self.host_network_stack.addWidget(self.host_network_table)
        self.host_network_stack.setCurrentIndex(0)
        self.host_network_tab = QScrollArea()
        self.host_network_tab.setWidgetResizable(True)
        net_container = QWidget()
        net_layout = QVBoxLayout(net_container)
        net_layout.setContentsMargins(0, 0, 0, 0)
        net_layout.addWidget(self.host_network_stack)
        self.host_network_tab.setWidget(net_container)
        self.tabs.addTab(self.host_network_tab, get_icon("network"), tr("Network"))
        self.tabs.setTabVisible(TabIndex.NETWORK, False)

        # --- Tab 15: Services ---
        self.host_services_loading = QLabel(tr("Loading..."))
        self.host_services_loading.setAlignment(Qt.AlignCenter)
        self.host_services_loading.setStyleSheet("color: #9ca3af; font-size: 14px;")
        self.host_services_table = self._make_table(
            [tr("Service"), tr("State"), tr("Description")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 75),
             (QHeaderView.Stretch, None)],
        )
        self.host_services_stack = QStackedWidget()
        self.host_services_stack.addWidget(self.host_services_loading)
        self.host_services_stack.addWidget(self.host_services_table)
        self.host_services_stack.setCurrentIndex(0)
        self.host_services_tab = QScrollArea()
        self.host_services_tab.setWidgetResizable(True)
        svc_container = QWidget()
        svc_layout = QVBoxLayout(svc_container)
        svc_layout.setContentsMargins(0, 0, 0, 0)
        svc_layout.addWidget(self.host_services_stack)
        self.host_services_tab.setWidget(svc_container)
        self.tabs.addTab(self.host_services_tab, get_icon("services"), tr("Services"))
        self.tabs.setTabVisible(TabIndex.SERVICES, False)

        # --- Tab 16: Host disks ---
        self.host_disks_loading = QLabel(tr("Loading..."))
        self.host_disks_loading.setAlignment(Qt.AlignCenter)
        self.host_disks_loading.setStyleSheet("color: #9ca3af; font-size: 14px;")
        self.host_disks_table = self._make_table(
            [tr("Device"), tr("Type"), tr("Model"), tr("Size"), tr("Serial")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 65),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 70),
             (QHeaderView.Stretch, None)],
        )
        self.host_disks_stack = QStackedWidget()
        self.host_disks_stack.addWidget(self.host_disks_loading)
        self.host_disks_stack.addWidget(self.host_disks_table)
        self.host_disks_stack.setCurrentIndex(0)
        self.host_disks_tab = QScrollArea()
        self.host_disks_tab.setWidgetResizable(True)
        disk_container = QWidget()
        disk_layout = QVBoxLayout(disk_container)
        disk_layout.setContentsMargins(0, 0, 0, 0)
        disk_layout.addWidget(self.host_disks_stack)
        self.host_disks_tab.setWidget(disk_container)
        self.tabs.addTab(self.host_disks_tab, get_icon("disk"), tr("Disks"))
        self.tabs.setTabVisible(TabIndex.HOST_DISKS, False)

        # --- Tab 17: VM Snapshots ---
        self.host_snapshots_loading = QLabel(tr("Loading..."))
        self.host_snapshots_loading.setAlignment(Qt.AlignCenter)
        self.host_snapshots_loading.setStyleSheet("color: #9ca3af; font-size: 14px;")
        self.host_snapshots_table = self._make_table(
            [tr("VM"), tr("Snapshot"), tr("Description"), tr("Created"), tr("Current")],
            [(QHeaderView.Stretch, None), (QHeaderView.Stretch, None),
             (QHeaderView.Stretch, None), (QHeaderView.Stretch, None),
             (QHeaderView.Interactive, 65)],
            sortable=True,
        )
        self.host_snapshots_stack = QStackedWidget()
        self.host_snapshots_stack.addWidget(self.host_snapshots_loading)
        self.host_snapshots_stack.addWidget(self.host_snapshots_table)
        self.host_snapshots_stack.setCurrentIndex(0)
        self.host_snapshots_tab = QScrollArea()
        self.host_snapshots_tab.setWidgetResizable(True)
        snap_container = QWidget()
        snap_layout = QVBoxLayout(snap_container)
        snap_layout.setContentsMargins(0, 0, 0, 0)
        snap_layout.addWidget(self.host_snapshots_stack)
        self.host_snapshots_tab.setWidget(snap_container)
        self.tabs.addTab(self.host_snapshots_tab, get_icon("snapshot"), tr("Snapshots"))
        self.tabs.setTabVisible(TabIndex.SNAPSHOTS, False)

        self.tabs.hide()

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.detail_label)
        main_layout.addWidget(self.vm_action_bar)
        main_layout.addWidget(self.tabs)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

    # ------------------------------------------------------------------
    # Common methods
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_pve_error(err):
        return parse_pve_error(err)

    def _run_worker(self, worker):
        if len(self._workers) >= _MAX_WORKERS_DP:
            return
        self._workers.add(worker)
        worker.signals.finished.connect(lambda w=worker: self._discard_worker(w))
        QThreadPool.globalInstance().start(worker)

    def _discard_worker(self, worker):
        """Safely removes worker from _workers.
        Called in finally after signal handling to prevent worker leaks
        on RuntimeError (destroyed widget) or any handler exception."""
        self._workers.discard(worker)

    def set_lists(self, all_nodes, all_vms, all_storages=None):
        self.all_nodes = all_nodes
        self.all_vms = all_vms
        self._vms_by_key = build_vm_index(all_vms)
        self.all_storages = all_storages or []

    def set_iso_catalog(self, iso_images):
        self._all_iso_catalog = iso_images or {}

    def _on_vm_action(self, action):
        if not self._last_vm_data:
            return
        vmid = self._last_vm_data.get("vmid")
        host_name = self._last_vm_data.get("host_name") or self._last_vm_data.get("node")
        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            return
        if action in ("stop", "reset"):
            msgs = {
                "stop": tr("Force stop VM {vmid}? Unsaved data will be lost.").format(vmid=vmid),
                "reset": tr("Force reset VM {vmid}?").format(vmid=vmid),
            }
            msg = QMessageBox(QMessageBox.Warning, tr("Confirm"), msgs[action], parent=self)
            yes = msg.addButton(tr("Yes"), QMessageBox.YesRole)
            msg.addButton(tr("No"), QMessageBox.NoRole)
            msg.setDefaultButton(yes)
            msg.exec()
            if msg.clickedButton() != yes:
                return
        node_name = self._last_vm_data.get("node") or host_name
        vm_type = self._last_vm_data.get("type", "qemu")
        from ..backend import VmActionWorker
        worker = VmActionWorker(cfg, node_name, vmid, vm_type, action)
        for btn in self._action_buttons.values():
            btn.setEnabled(False)
        self.detail_label.setText(f"VM/CT: {vmid} — {VM_ACTION_MESSAGE_LABELS.get(action, action)}...")
        worker.signals.action_result.connect(lambda msg: (
            self._on_action_finished(msg),
            self._refresh_after_action(),
            self._discard_worker(worker)
        ))
        worker.signals.action_error.connect(lambda err: (
            self._on_action_error(err),
            self._discard_worker(worker)
        ))
        self._run_worker(worker)

    def _update_action_buttons(self, vm_data=None):
        """Recalculates VM action button state based on status."""
        if vm_data is None:
            vm_data = self._last_vm_data or {}
        status = vm_data.get("status", "") if vm_data else ""
        for key, btn in self._action_buttons.items():
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
        self._console_btn.setEnabled(
            vm_type in ("qemu", "lxc") and status == "running"
        )

    def _on_action_finished(self, msg):
        vm = self._last_vm_data or {}
        self.detail_label.setText(f"VM/CT: {vm.get('name', vm.get('vmid', ''))} — {msg}")
        self._update_action_buttons(vm)

    def _on_action_error(self, err):
        self.detail_label.setText(self._parse_pve_error(err))
        self._update_action_buttons(self._last_vm_data)

    def _on_vm_console(self):
        if not self._last_vm_data:
            return
        vm_type = self._last_vm_data.get("type", "qemu")
        vmid = self._last_vm_data.get("vmid")
        host_name = self._last_vm_data.get("host_name") or self._last_vm_data.get("node")
        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            return
        node_name = self._last_vm_data.get("node") or host_name
        self._console_btn.setEnabled(False)
        self.detail_label.setText(tr("VM {vmid}: opening SPICE console...").format(vmid=vmid))
        from ..backend import VmConsoleWorker
        worker = VmConsoleWorker(cfg, node_name, vmid, vm_type)
        worker.signals.console_ready.connect(lambda msg: (
            self.detail_label.setText(msg),
            self._console_btn.setEnabled(True),
            self._discard_worker(worker)
        ))
        worker.signals.console_error.connect(lambda err: (
            self.detail_label.setText(err),
            self._console_btn.setEnabled(True),
            self._discard_worker(worker)
        ))
        self._run_worker(worker)


    def _refresh_after_action(self):
        if not self._last_vm_data:
            return
        host_name = self._last_vm_data.get("host_name") or self._last_vm_data.get("node")
        vmid = self._last_vm_data.get("vmid")
        vm_type = self._last_vm_data.get("type", "qemu")
        node_name = self._last_vm_data.get("node") or host_name
        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            return
        gen = self._generation
        self._cancel_detail_worker()
        from ..backend import VmDetailWorker
        worker = VmDetailWorker(cfg, node_name, vmid, vm_type)
        worker.signals.detail_ready.connect(lambda d, g=gen, h=host_name, w=worker: (
            self._on_detail_loaded(d, g, h),
            self._discard_worker(w)
        ))
        self.current_worker = worker
        self._run_worker(worker)

    @staticmethod
    def _compact_table(table, max_height=22):
        for r in range(table.rowCount()):
            if table.rowHeight(r) > max_height:
                table.setRowHeight(r, max_height)

    _FILTER_TEXT_ROLE = Qt.UserRole + 42

    @staticmethod
    def _make_table(headers, col_specs, sortable=False):
        """Create a styled QTableWidget with standard appearance.
        headers: list of column header strings.
        col_specs: list of (QHeaderView.ResizeMode, width_or_None) per column.
        """
        table = QTableWidget()
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().hide()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        for col, (mode, width) in enumerate(col_specs):
            table.horizontalHeader().setSectionResizeMode(col, mode)
            if width is not None:
                table.setColumnWidth(col, width)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        table.horizontalHeader().setStyleSheet(_HEADER_STYLE)
        table.setAlternatingRowColors(True)
        if sortable:
            table.setSortingEnabled(True)
        enable_row_hover(table)
        return table

    @staticmethod
    def _filter_table(table, text):
        needle = text.lower()
        sort_was = table.isSortingEnabled()
        if sort_was:
            table.setSortingEnabled(False)
        table.blockSignals(True)
        try:
            for row in range(table.rowCount()):
                visible = False
                for col in range(table.columnCount()):
                    item = table.item(row, col)
                    if not item:
                        continue
                    cached = item.data(DetailPanel._FILTER_TEXT_ROLE)
                    if cached is None:
                        cached = item.text().lower()
                        item.setData(DetailPanel._FILTER_TEXT_ROLE, cached)
                    if needle in cached:
                        visible = True
                        break
                table.setRowHidden(row, not visible)
        finally:
            table.blockSignals(False)
            if sort_was:
                table.setSortingEnabled(True)

    def _make_filterable_table(self, table):
        from PySide6.QtWidgets import QLineEdit
        from PySide6.QtCore import QTimer
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        search = QLineEdit()
        search.setPlaceholderText(tr("Filter"))
        search.setStyleSheet(
            "QLineEdit { font-size: 12px; padding: 4px 8px; border: 1px solid #d1d5db; "
            "border-radius: 3px; margin: 4px 4px 0 4px; }"
        )
        debounce = QTimer()
        debounce.setSingleShot(True)
        debounce.setInterval(200)
        debounce.timeout.connect(lambda: DetailPanel._filter_table(table, search.text()))
        search.textChanged.connect(debounce.start)
        layout.addWidget(search)
        layout.addWidget(table)
        container._filter_debounce = debounce
        return container

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

            self._cancel_detail_worker()
            self._cancel_config_worker()
            self._cancel_history_worker()
            self.metrics_widget.clear_curves()

            self.tabs.setTabVisible(TabIndex.OPTIONS, False)
            self.tabs.setTabVisible(TabIndex.HISTORY, False)
            self.tabs.setTabVisible(TabIndex.HOST_VMS, False)
            self.tabs.setTabVisible(TabIndex.POOL_VMS, False)
            self.tabs.setTabVisible(TabIndex.SUMMARY, False)
            self.tabs.setTabVisible(TabIndex.STORAGES, False)
            self.tabs.setTabVisible(TabIndex.HOST_STORAGE, False)
            self.tabs.setTabVisible(TabIndex.STORAGE_DETAIL, False)
            self.tabs.setTabVisible(TabIndex.BACKUPS, False)
            self.tabs.setTabVisible(TabIndex.DISKS_VM, False)
            self.tabs.setTabVisible(TabIndex.ISO, False)
            self.tabs.setTabVisible(TabIndex.TEMPLATES, False)
            self.tabs.setTabVisible(TabIndex.NETWORK, False)
            self.tabs.setTabVisible(TabIndex.SERVICES, False)
            self.tabs.setTabVisible(TabIndex.HOST_DISKS, False)
            self.tabs.setTabVisible(TabIndex.SNAPSHOTS, False)

            if obj_type == "cluster_folder":
                self._show_cluster_folder(obj_name)
            elif obj_type == "storage_folder":
                self._show_storage_folder()
            elif obj_type == "standalone_folder":
                self._show_standalone_folder(obj_name)
            elif obj_type == "cluster":
                self._show_cluster(obj_name)
            elif obj_type == "host":
                self._show_host_info(obj_name, data)
            elif obj_type == "pool":
                self._show_pool_info(obj_name)
            elif obj_type == "vm":
                self._show_vm_info_init(obj_name, data, gen)
            elif obj_type == "storage":
                self._show_storage_detail(obj_name, data)

        except Exception:
            traceback.print_exc()
            self.detail_label.setText(tr("Error: {name}").format(name=obj_name))
            self.info_label.setText(tr("An error occurred while loading information"))
            self.info_stack.setCurrentIndex(0)

    @staticmethod
    def _set_cell_text(table, row, col, text, fg_color=None):
        item = table.item(row, col)
        if item is None:
            item = QTableWidgetItem(text)
            table.setItem(row, col, item)
        else:
            item.setText(text)
        if fg_color:
            item.setForeground(QBrush(QColor(fg_color)))

    @staticmethod
    def _update_progress_bar(bar, value, fmt):
        bar.setValue(value)
        bar.setFormat(fmt)
        bar.setStyleSheet(_progress_style(value))

    def _update_vm_summary_cell(self, label, value, fg_color=None):
        table = self.vm_summary_table
        for r in range(table.rowCount()):
            if table.item(r, 0) and table.item(r, 0).text() == label:
                self._set_cell_text(table, r, 1, str(value), fg_color)
                break

    def _update_host_cells(self, host_data):
        if not host_data:
            return
        host_name = host_data.get("node", "")
        host_cfg_name = host_data.get("host_name", "")
        is_online = host_data.get("status") != "error"

        if is_online:
            cpu_frac = host_data.get("cpu", 0)
            cpu_pct = round(cpu_frac * 100, 1) if isinstance(cpu_frac, float) else 0
            mem_bytes = host_data.get("mem", 0)
            mem_gb = round(mem_bytes / (1024**3), 2) if mem_bytes else 0
            maxmem_bytes = host_data.get("maxmem", 0)
            maxmem_gb = round(maxmem_bytes / (1024**3), 2) if maxmem_bytes else 0
            uptime = host_data.get("uptime", 0)
            status = host_data.get("status", "")

            self._update_vm_summary_cell(tr("Status"), status_text(status),
                "#22c55e" if status == "online" else "#ef4444" if status == "offline" else "#f59e0b")
            self._update_vm_summary_cell(tr("CPU"), f"{cpu_pct}%")
            self._update_vm_summary_cell(tr("RAM (GiB)"), f"{mem_gb} / {maxmem_gb}")
            self._update_vm_summary_cell(tr("Uptime"), _format_uptime(uptime))

        WARN_ROLE = Qt.UserRole + 10
        vmid_role = Qt.UserRole + 30
        vms_of_host = [vm for vm in self.all_vms
                       if vm.get("node") == host_name
                       and vm.get("host_name") == host_cfg_name]
        fresh_by_vmid = {vm.get("vmid"): vm for vm in vms_of_host}

        table = self.host_vm_table
        for r in range(table.rowCount()):
            name_item = table.item(r, 0)
            if name_item is None:
                continue
            vmid = name_item.data(vmid_role)
            if vmid is None:
                continue
            new_vm = fresh_by_vmid.get(vmid)
            if new_vm is None:
                continue

            name_item.setText(str(new_vm.get("name", "")))
            self._set_cell_text(table, r, 1, str(new_vm.get("type", "")))
            self._set_cell_text(table, r, 2, str(new_vm.get("node", new_vm.get("host_name", ""))))

            vm_status = str(new_vm.get("status", ""))
            status_color = "#22c55e" if vm_status == "running" else "#ef4444" if vm_status == "stopped" else "#f59e0b"
            self._set_cell_text(table, r, 3, vm_status, status_color)

            cpu_val = new_vm.get("cpu", 0)
            if isinstance(cpu_val, float):
                cpu_str = str(round(cpu_val * 100, 1))
            else:
                cpu_str = str(cpu_val)
            self._set_cell_text(table, r, 4, cpu_str)

            warning = (isinstance(cpu_val, float) and cpu_val >= 0.9) or vm_status == "stopped"
            for c in range(5):
                it = table.item(r, c)
                if it:
                    if warning:
                        it.setBackground(QColor("#fef3c7"))
                        it.setData(WARN_ROLE, True)
                    else:
                        was_warn = it.data(WARN_ROLE)
                        if was_warn:
                            it.setData(WARN_ROLE, None)
                            it.setBackground(QColor("#f3f4f6") if r % 2 == 1 else QBrush())

    def _update_cluster_summary_cells(self, hosts):
        table = self.datacenter_summary
        node_by_name = {n.get("node", ""): n for n in hosts}

        for r in range(table.rowCount()):
            name_item = table.item(r, 0)
            if name_item is None:
                continue
            node_name = name_item.text()
            node = node_by_name.get(node_name)
            if node is None:
                continue

            status = node.get("status", "unknown")
            status_color = "#22c55e" if status == "online" else "#ef4444" if status == "offline" else "#f59e0b"
            self._set_cell_text(table, r, 1, f"● {status}", status_color)

            cpu_frac = node.get("cpu", 0)
            cpu_pct = round(cpu_frac * 100, 1) if isinstance(cpu_frac, float) else 0
            old_bar = table.cellWidget(r, 3)
            if isinstance(old_bar, QProgressBar):
                self._update_progress_bar(old_bar, int(cpu_pct), f"{cpu_pct}%")

            mem_bytes = node.get("mem", 0)
            maxmem_bytes = node.get("maxmem", 1) or 1
            mem_gb = round(mem_bytes / (1024**3), 2) if mem_bytes else 0
            maxmem_gb = round(maxmem_bytes / (1024**3), 2)
            mem_pct = int((mem_bytes / maxmem_bytes) * 100) if maxmem_bytes else 0
            old_ram = table.cellWidget(r, 4)
            if isinstance(old_ram, QProgressBar):
                self._update_progress_bar(old_ram, mem_pct, f"{mem_gb}/{maxmem_gb} GiB")

            uptime_sec = node.get("uptime", 0)
            uptime_str = _format_uptime(uptime_sec) if uptime_sec else ''
            self._set_cell_text(table, r, 5, uptime_str)

    def _update_vm_cells(self, vm_data):
        if not vm_data:
            return
        detail_key = (vm_data.get("vmid"), vm_data.get("host_name") or vm_data.get("node"))
        detail = self.details_cache.get(detail_key)
        if not detail:
            return

        status = vm_data.get("status") or detail.get("status", "")
        status_color = "#22c55e" if status == "running" else "#ef4444" if status == "stopped" else "#f59e0b"
        self._update_vm_summary_cell(tr("Status"), status_text(status), status_color)

        cpu_usage = vm_data.get("cpu") or detail.get("cpu", 0)
        if isinstance(cpu_usage, float):
            cpu_usage = round(cpu_usage * 100, 1)
        self._update_vm_summary_cell(tr("CPU usage (%)"), f"{cpu_usage}%")

        def safe_int(val): return int(val) if isinstance(val, (int, float)) else 0

        maxmem_bytes = safe_int(detail.get("maxmem") or vm_data.get("maxmem"))
        mem_used_bytes = safe_int(detail.get("mem"))
        maxmem_gb = round(maxmem_bytes / (1024**3), 2) if maxmem_bytes else 0
        mem_used_gb = round(mem_used_bytes / (1024**3), 2) if mem_used_bytes else 0
        self._update_vm_summary_cell(tr("RAM (GiB)"), f"{mem_used_gb} / {maxmem_gb}")

        maxdisk_bytes = safe_int(detail.get("maxdisk") or vm_data.get("maxdisk"))
        disk_used_bytes = safe_int(detail.get("disk"))
        maxdisk_gb = round(maxdisk_bytes / (1024**3), 2) if maxdisk_bytes else 0
        disk_used_gb = round(disk_used_bytes / (1024**3), 2) if disk_used_bytes else 0
        self._update_vm_summary_cell(tr("Disk (GiB)"), f"{disk_used_gb} / {maxdisk_gb}")

        netin = detail.get("netin", 0)
        netout = detail.get("netout", 0)
        netin_mb = round(netin / (1024*1024), 2) if netin else 0
        netout_mb = round(netout / (1024*1024), 2) if netout else 0
        self._update_vm_summary_cell(tr("Net in (MB)"), str(netin_mb))
        self._update_vm_summary_cell(tr("Net out (MB)"), str(netout_mb))

        uptime = detail.get("uptime") or vm_data.get("uptime", "")
        self._update_vm_summary_cell(tr("Uptime"), _format_uptime(uptime) if uptime else '')

    def _update_pool_cells(self):
        pool_name = self.current_obj_name
        vms = [vm for vm in self.all_vms if vm.get("pool") == pool_name]
        self.pool_widget.set_pool_vms(vms)

    def _set_storage_param(self, label, value):
        table = self.storage_detail_params
        for r in range(table.rowCount()):
            if table.item(r, 0) and table.item(r, 0).text() == label:
                self._set_cell_text(table, r, 1, str(value))
                break

    def _update_storage_cells(self):
        storage_name = self.current_obj_name
        data = self.current_obj_data or {}
        cluster = data.get("cluster")
        host_name_filter = data.get("host_name")
        if cluster:
            filtered = [s for s in self.all_storages
                        if s.get("storage") == storage_name and s.get("cluster") == cluster]
        elif host_name_filter:
            filtered = [s for s in self.all_storages
                        if s.get("storage") == storage_name and s.get("host_name") == host_name_filter]
        else:
            filtered = [s for s in self.all_storages if s.get("storage") == storage_name]
        if not filtered:
            return
        total_used = sum(s.get("used", 0) or 0 for s in filtered)
        total_total = sum(s.get("total", 0) or 0 for s in filtered)
        total_pct = int((total_used / total_total) * 100) if total_total else 0
        used_gb = round(total_used / (1024**3), 1)
        total_gb = round(total_total / (1024**3), 1)

        self._set_storage_param(tr("Used"), f"{used_gb} GiB")
        self._set_storage_param(tr("Total"), f"{total_gb} GiB")
        self._set_storage_param(tr("Usage"), f"{total_pct}%")
        self.storage_detail_bar.setStyleSheet(_progress_style(total_pct))
        self.storage_detail_bar.setValue(total_pct)
        self.storage_detail_bar.setFormat(f"{total_pct}%  ({used_gb}/{total_gb} GiB)")

        node_table = self.storage_detail_nodes_table
        node_by_storage = {}
        for st in filtered:
            node_by_storage[st.get("node", "")] = st
        for r in range(node_table.rowCount()):
            name_item = node_table.item(r, 0)
            if name_item is None:
                continue
            st = node_by_storage.get(name_item.text())
            if st is None:
                continue
            used = st.get("used", 0) or 0
            total = st.get("total", 0) or 1
            u_gb = round(used / (1024**3), 1)
            t_gb = round(total / (1024**3), 1)
            pct = int((used / total) * 100) if total else 0
            self._set_cell_text(node_table, r, 3, f"{u_gb} GiB")
            self._set_cell_text(node_table, r, 4, f"{t_gb} GiB")
            old_bar = node_table.cellWidget(r, 5)
            if isinstance(old_bar, QProgressBar):
                self._update_progress_bar(old_bar, pct, f"{pct}%")

    def refresh_current_view(self):
        if self.current_obj_type is None:
            return
        saved_tab = self.tabs.currentIndex()

        if self.current_obj_type in ("standalone_folder", "cluster_folder", "storage_folder"):
            if self.current_obj_type == "standalone_folder":
                self._show_standalone_folder("")
            elif self.current_obj_type == "cluster_folder":
                self._show_cluster_folder("")
            elif self.current_obj_type == "storage_folder":
                self._show_storage_folder()
        elif self.current_obj_type == "cluster":
            hosts = []
            for node in self.all_nodes:
                host_name = node.get("host_name", "")
                cfg = self._cfg_by_name.get(host_name)
                if cfg and cfg.get("cluster") == self.current_obj_name:
                    hosts.append(node)
            self._update_cluster_summary_cells(hosts)
        elif self.current_obj_type == "host":
            host_data = next((n for n in self.all_nodes if n.get("node") == self.current_obj_name), None)
            if host_data:
                if host_data.get("status") == "error":
                    self._show_host_info(self.current_obj_name, host_data)
                else:
                    self._update_host_cells(host_data)
                    self._fetch_host_metrics(host_data)
        elif self.current_obj_type == "pool":
            self._update_pool_cells()
        elif self.current_obj_type == "vm":
            vm_data = self.current_obj_data
            if vm_data:
                lookup_host = vm_data.get("host_name") or vm_data.get("node")
                fresh = self._vms_by_key.get((lookup_host, vm_data.get("vmid")))
                if fresh:
                    self.current_obj_data = fresh
                    self.hardware_widget.set_vm_status(fresh.get("status", ""))
                self._update_vm_cells(fresh or vm_data)
                self._show_vm_metrics(fresh or vm_data)
        elif self.current_obj_type == "storage":
            self._update_storage_cells()

        self.tabs.setCurrentIndex(saved_tab)

    def _cancel_detail_worker(self):
        if self.current_worker:
            self._discard_worker(self.current_worker)
            try: self.current_worker.signals.detail_ready.disconnect()
            except RuntimeError: pass
            self.current_worker = None

    def _cancel_config_worker(self):
        if self.current_config_worker:
            self._discard_worker(self.current_config_worker)
            try: self.current_config_worker.signals.config_ready.disconnect()
            except RuntimeError: pass
            try: self.current_config_worker.signals.config_error.disconnect()
            except RuntimeError: pass
            self.current_config_worker = None

    def _cancel_history_worker(self):
        if self.current_hist_worker:
            self._discard_worker(self.current_hist_worker)
            try: self.current_hist_worker.signals.tasks_ready.disconnect()
            except RuntimeError: pass
            try: self.current_hist_worker.signals.tasks_error.disconnect()
            except RuntimeError: pass
            self.current_hist_worker = None

    # ------------------------------------------------------------------
    # Populate host summary table (with progress bars)
    # ------------------------------------------------------------------
    def _populate_host_summary(self, hosts):
        table = self.datacenter_summary
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            tr("Host"), tr("Status"), tr("Address"), tr("CPU %"), tr("RAM (GiB)"), tr("Uptime")
        ])
        # Сбрасываем режимы для всех колонок сразу, иначе при переключении
        # между 5-колоночной (_show_cluster_folder) и 6-колоночной
        # конфигурацией Qt сохраняет старые режимы — ширина колонок "плывёт".
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.setColumnWidth(1, 70)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.setColumnWidth(3, 55)
        table.setColumnWidth(4, 80)
        table.setColumnWidth(5, 85)
        table.setRowCount(len(hosts))
        for i, node in enumerate(hosts):
            node_name = node.get("_display_name") or node.get("node", "?")
            table.setItem(i, 0, QTableWidgetItem(node_name))

            status = node.get("status", "unknown")
            status_item = QTableWidgetItem(f"● {status_text(status)}")
            if status == "online":
                status_item.setForeground(QBrush(QColor("#22c55e")))
            elif status == "offline":
                status_item.setForeground(QBrush(QColor("#ef4444")))
            else:
                status_item.setForeground(QBrush(QColor("#f59e0b")))
            table.setItem(i, 1, status_item)

            host_name = node.get("host_name", "")
            cfg = self._cfg_by_name.get(host_name)
            address = cfg.get("host", "") if cfg else ""
            table.setItem(i, 2, QTableWidgetItem(address))

            cpu_frac = node.get("cpu", 0)
            cpu_pct = round(cpu_frac * 100, 1) if isinstance(cpu_frac, float) else 0
            cpu_bar = QProgressBar()
            cpu_bar.setRange(0, 100)
            cpu_bar.setValue(int(cpu_pct))
            cpu_bar.setStyleSheet(_progress_style(int(cpu_pct)))
            cpu_bar.setFormat(f"{cpu_pct}%")
            table.setCellWidget(i, 3, cpu_bar)
            cpu_item = QTableWidgetItem("")
            cpu_item.setFlags(Qt.ItemIsEnabled)
            table.setItem(i, 3, cpu_item)

            mem_bytes = node.get("mem", 0)
            maxmem_bytes = node.get("maxmem", 1) or 1
            mem_gb = round(mem_bytes / (1024**3), 2) if mem_bytes else 0
            maxmem_gb = round(maxmem_bytes / (1024**3), 2)
            mem_pct = int((mem_bytes / maxmem_bytes) * 100) if maxmem_bytes else 0
            ram_bar = QProgressBar()
            ram_bar.setRange(0, 100)
            ram_bar.setValue(mem_pct)
            ram_bar.setStyleSheet(_progress_style(mem_pct))
            ram_bar.setFormat(f"{mem_gb}/{maxmem_gb} GiB")
            table.setCellWidget(i, 4, ram_bar)
            ram_item = QTableWidgetItem("")
            ram_item.setFlags(Qt.ItemIsEnabled)
            table.setItem(i, 4, ram_item)

            uptime_sec = node.get("uptime", 0)
            uptime_str = _format_uptime(uptime_sec) if uptime_sec else ''
            table.setItem(i, 5, QTableWidgetItem(uptime_str))

        table.resizeRowsToContents()
        self._compact_table(table, 24)

    def _show_cluster_folder(self, name):
        self.detail_label.setText(tr("Clusters"))
        self.tabs.setTabVisible(TabIndex.MONITOR, False)
        self.tabs.setTabVisible(TabIndex.HARDWARE, False)
        self.tabs.setTabVisible(TabIndex.HOST_VMS, False)
        self.tabs.setTabVisible(TabIndex.SUMMARY, True)
        self.tabs.setCurrentIndex(TabIndex.SUMMARY)
        clusters = {}
        for node in self.all_nodes:
            host_name = node.get("host_name", "")
            cfg = self._cfg_by_name.get(host_name)
            cl = cfg.get("cluster") if cfg else None
            if cl and cl not in (False, None, "Standalone"):
                clusters.setdefault(cl, {"hosts": [], "nodes": set()})
                clusters[cl]["hosts"].append(node)
                clusters[cl]["nodes"].add(node.get("node"))
        for cl in clusters.values():
            cl["vms"] = [vm for vm in self.all_vms if vm.get("node") in cl["nodes"]]
        table = self.datacenter_summary
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([tr("Cluster"), tr("Hosts"), tr("VMs"), tr("CPU %"), tr("RAM (GiB)")])
        # Тот же сброс, что и в _populate_host_summary — иначе при возврате
        # из 6-колоночной конфигурации 6-я колонка наследует Stretch.
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.setColumnWidth(1, 65)
        table.setColumnWidth(2, 65)
        table.setColumnWidth(3, 55)
        table.setColumnWidth(4, 85)
        table.setRowCount(max(len(clusters), 1))
        if not clusters:
            table.setSpan(0, 0, 1, 5)
            empty = QTableWidgetItem(tr("No clusters configured"))
            empty.setFlags(empty.flags() & ~Qt.ItemIsSelectable)
            empty.setTextAlignment(Qt.AlignCenter)
            table.setItem(0, 0, empty)
        for i, (cl_name, cl_data) in enumerate(sorted(clusters.items(), key=lambda x: x[0].lower())):
            table.setItem(i, 0, QTableWidgetItem(cl_name))
            hosts_ok = sum(1 for h in cl_data["hosts"] if h.get("status") == "online")
            table.setItem(i, 1, QTableWidgetItem(f"{hosts_ok}/{len(cl_data['hosts'])}"))
            vms_ok = sum(1 for v in cl_data["vms"] if v.get("status") == "running")
            table.setItem(i, 2, QTableWidgetItem(f"{vms_ok}/{len(cl_data['vms'])}"))
            cpu_vals = [h.get("cpu", 0) for h in cl_data["hosts"] if isinstance(h.get("cpu"), float)]
            avg_cpu = round(sum(cpu_vals) / len(cpu_vals) * 100, 1) if cpu_vals else 0
            cpu_bar = QProgressBar()
            cpu_bar.setRange(0, 100)
            cpu_bar.setValue(int(avg_cpu))
            cpu_bar.setStyleSheet(_progress_style(int(avg_cpu)))
            cpu_bar.setFormat(f"{avg_cpu}%")
            table.setCellWidget(i, 3, cpu_bar)
            ci = QTableWidgetItem("")
            ci.setFlags(Qt.ItemIsEnabled)
            table.setItem(i, 3, ci)
            mem_total = sum(h.get("maxmem", 0) for h in cl_data["hosts"])
            mem_used = sum(h.get("mem", 0) for h in cl_data["hosts"])
            mem_total_gb = round(mem_total / (1024**3), 1)
            mem_used_gb = round(mem_used / (1024**3), 1)
            mem_pct = int((mem_used / mem_total) * 100) if mem_total else 0
            ram_bar = QProgressBar()
            ram_bar.setRange(0, 100)
            ram_bar.setValue(mem_pct)
            ram_bar.setStyleSheet(_progress_style(mem_pct))
            ram_bar.setFormat(f"{mem_used_gb}/{mem_total_gb} GiB")
            table.setCellWidget(i, 4, ram_bar)
            ri = QTableWidgetItem("")
            ri.setFlags(Qt.ItemIsEnabled)
            table.setItem(i, 4, ri)
        table.resizeRowsToContents()
        for r in range(table.rowCount()):
            if table.rowHeight(r) > 24:
                table.setRowHeight(r, 24)

    def _populate_storage_table(self, storages):
        table = self.storage_table
        table.setRowCount(len(storages))
        for i, st in enumerate(storages):
            table.setItem(i, 0, QTableWidgetItem(st.get("storage", st.get("id", ""))))
            table.setItem(i, 1, QTableWidgetItem(st.get("type", "")))
            content = st.get("content", "")
            if isinstance(content, list):
                content = ", ".join(content)
            table.setItem(i, 2, QTableWidgetItem(content))
            cluster = st.get("cluster")
            host_val = cluster if cluster else st.get("node", st.get("host_name", ""))
            table.setItem(i, 3, QTableWidgetItem(host_val))
            used = st.get("used", 0) or 0
            total = st.get("total", 0) or 1
            used_gb = round(used / (1024**3), 1)
            total_gb = round(total / (1024**3), 1)
            pct = int((used / total) * 100) if total else 0
            table.setItem(i, 4, QTableWidgetItem(f"{used_gb} GiB"))
            table.setItem(i, 5, QTableWidgetItem(f"{total_gb} GiB"))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(pct)
            bar.setStyleSheet(_progress_style(pct))
            bar.setFormat(f"{pct}%")
            table.setCellWidget(i, 6, bar)
            bi = QTableWidgetItem("")
            bi.setFlags(Qt.ItemIsEnabled)
            table.setItem(i, 6, bi)
        table.resizeRowsToContents()
        for r in range(table.rowCount()):
            if table.rowHeight(r) > 24:
                table.setRowHeight(r, 24)

    def _show_storage_folder(self):
        self.detail_label.setText(tr("Storage"))
        self.tabs.setTabVisible(TabIndex.MONITOR, False)
        self.tabs.setTabVisible(TabIndex.HARDWARE, False)
        self.tabs.setTabVisible(TabIndex.STORAGES, True)
        self.tabs.setCurrentIndex(TabIndex.STORAGES)
        seen = set()
        deduped = []
        for st in self.all_storages:
            cluster = st.get("cluster")
            if cluster:
                key = (st.get("storage"), cluster)
            else:
                key = (st.get("storage"), st.get("host_name"))
            if key not in seen:
                seen.add(key)
                deduped.append(st)
        self._populate_storage_table(deduped)

    def _show_storage_detail(self, storage_name, data):
        cluster = data.get("cluster")
        host_name_filter = data.get("host_name")
        if cluster:
            title = f"{storage_name} @ {cluster}"
        elif host_name_filter:
            title = f"{storage_name} ({host_name_filter})"
        else:
            title = storage_name
        self.detail_label.setText(tr("Storage: {title}").format(title=title))
        self.tabs.setTabVisible(TabIndex.MONITOR, False)
        self.tabs.setTabVisible(TabIndex.HARDWARE, False)
        self.tabs.setTabVisible(TabIndex.OPTIONS, False)
        self.tabs.setTabVisible(TabIndex.HISTORY, False)
        self.tabs.setTabVisible(TabIndex.HOST_VMS, False)
        self.tabs.setTabVisible(TabIndex.POOL_VMS, False)
        self.tabs.setTabVisible(TabIndex.SUMMARY, False)
        self.tabs.setTabVisible(TabIndex.STORAGES, False)
        self.tabs.setTabVisible(TabIndex.HOST_STORAGE, False)
        self.tabs.setTabVisible(TabIndex.STORAGE_DETAIL, True)
        self.tabs.setTabVisible(TabIndex.BACKUPS, False)
        self.tabs.setTabVisible(TabIndex.DISKS_VM, False)
        self.tabs.setTabVisible(TabIndex.ISO, False)
        self.tabs.setTabVisible(TabIndex.TEMPLATES, False)
        self.tabs.setCurrentIndex(TabIndex.STORAGE_DETAIL)
        self.storage_detail_name.setText(title)
        if cluster:
            filtered = [s for s in self.all_storages
                        if s.get("storage") == storage_name and s.get("cluster") == cluster]
        else:
            filtered = [s for s in self.all_storages if s.get("storage") == storage_name]
        if not filtered:
            self.storage_detail_params.setRowCount(0)
            self.storage_detail_bar.setValue(0)
            self.storage_detail_bar.setFormat(tr("No data"))
            self.storage_detail_nodes_table.setRowCount(0)
            return
        rep = filtered[0]
        st_type = rep.get("type", "")
        content = rep.get("content", "")
        if isinstance(content, list):
            content = ", ".join(content)
        total_used = sum(s.get("used", 0) or 0 for s in filtered)
        total_total = sum(s.get("total", 0) or 0 for s in filtered)
        total_pct = int((total_used / total_total) * 100) if total_total else 0
        used_gb = round(total_used / (1024**3), 1)
        total_gb = round(total_total / (1024**3), 1)
        params = [
            (tr("Type"), st_type),
            (tr("Content"), content),
            (tr("Used"), f"{used_gb} GiB"),
            (tr("Total"), f"{total_gb} GiB"),
            (tr("Usage"), f"{total_pct}%"),
            (tr("Nodes"), str(len(filtered))),
        ]
        self.storage_detail_params.setRowCount(len(params))
        for i, (k, v) in enumerate(params):
            self.storage_detail_params.setItem(i, 0, QTableWidgetItem(k))
            self.storage_detail_params.setItem(i, 1, QTableWidgetItem(str(v)))
        self.storage_detail_params.resizeRowsToContents()
        for r in range(self.storage_detail_params.rowCount()):
            if self.storage_detail_params.rowHeight(r) > 22:
                self.storage_detail_params.setRowHeight(r, 22)
        self.storage_detail_bar.setStyleSheet(_progress_style(total_pct))
        self.storage_detail_bar.setValue(total_pct)
        self.storage_detail_bar.setFormat(f"{total_pct}%  ({used_gb}/{total_gb} GiB)")
        self.storage_detail_nodes_label.setText(tr("Per node:") if cluster else tr("Node:"))
        self.storage_detail_nodes_table.setRowCount(len(filtered))
        for i, st in enumerate(filtered):
            node = st.get("node", "")
            self.storage_detail_nodes_table.setItem(i, 0, QTableWidgetItem(node))
            self.storage_detail_nodes_table.setItem(i, 1, QTableWidgetItem(st.get("type", "")))
            sc = st.get("content", "")
            if isinstance(sc, list):
                sc = ", ".join(sc)
            self.storage_detail_nodes_table.setItem(i, 2, QTableWidgetItem(sc))
            used = st.get("used", 0) or 0
            total = st.get("total", 0) or 1
            u_gb = round(used / (1024**3), 1)
            t_gb = round(total / (1024**3), 1)
            pct = int((used / total) * 100) if total else 0
            self.storage_detail_nodes_table.setItem(i, 3, QTableWidgetItem(f"{u_gb} GiB"))
            self.storage_detail_nodes_table.setItem(i, 4, QTableWidgetItem(f"{t_gb} GiB"))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(pct)
            bar.setStyleSheet(_progress_style(pct))
            bar.setFormat(f"{pct}%")
            self.storage_detail_nodes_table.setCellWidget(i, 5, bar)
            bi = QTableWidgetItem("")
            bi.setFlags(Qt.ItemIsEnabled)
            self.storage_detail_nodes_table.setItem(i, 5, bi)
        self.storage_detail_nodes_table.resizeRowsToContents()
        for r in range(self.storage_detail_nodes_table.rowCount()):
            if self.storage_detail_nodes_table.rowHeight(r) > 24:
                self.storage_detail_nodes_table.setRowHeight(r, 24)
        if _HAS_PG:
            self.storage_plot_curve.setData([], [])
        self._fetch_storage_metrics(storage_name, filtered)
        self._load_storage_content(storage_name, filtered, rep)

    @staticmethod
    def _format_volsize(size_bytes):
        if not size_bytes:
            return "0"
        gb = size_bytes / (1024**3)
        if gb >= 1024:
            return f"{gb/1024:.1f} TiB"
        return f"{gb:.1f} GiB"

    def _load_storage_content(self, storage_name, filtered, rep):
        allowed = rep.get("content", [])
        if isinstance(allowed, str):
            allowed = [c.strip() for c in allowed.split(",") if c.strip()]
        tab_map = {
            "backup": (10, tr("Backups"), [tr("VM"), tr("Type"), tr("Format"), tr("Size"), tr("Created")]),
            "images": (11, tr("VM Disks"), [tr("VM"), tr("Name"), tr("Volume"), tr("Bus"), tr("Size")]),
            "rootdir": (11, tr("VM Disks"), [tr("VM"), tr("Name"), tr("Volume"), tr("Bus"), tr("Size")]),
            "iso": (12, tr("ISO"), [tr("Volume"), tr("Format"), tr("Size"), tr("Modified")]),
            "vztmpl": (13, tr("Templates"), [tr("Volume"), tr("Format"), tr("Size"), tr("Modified")]),
            "snippets": (13, tr("Templates"), [tr("Volume"), tr("Format"), tr("Size"), tr("Modified")]),
        }
        self.storage_backups_table.setRowCount(0)
        self.storage_disks_table.setRowCount(0)
        self.storage_iso_table.setRowCount(0)
        self.storage_tpl_table.setRowCount(0)
        seen_tabs = set()
        for ct in allowed:
            info = tab_map.get(ct)
            if info:
                idx, title, headers = info
                seen_tabs.add(idx)
                self.tabs.setTabVisible(idx, True)
                self.tabs.setTabText(idx, title)
                table_map = {
                    10: self.storage_backups_table,
                    11: self.storage_disks_table,
                    12: self.storage_iso_table,
                    13: self.storage_tpl_table,
                }
                tbl = table_map.get(idx)
                if tbl:
                    tbl.setColumnCount(len(headers))
                    tbl.setHorizontalHeaderLabels(headers)
        loading_map = {
            10: self.storage_backups_stack,
            11: self.storage_disks_stack,
            12: self.storage_iso_stack,
            13: self.storage_tpl_stack,
        }
        for idx in seen_tabs:
            stack = loading_map.get(idx)
            if stack:
                stack.setCurrentIndex(0)
                stack.widget(0).setText(tr("Loading..."))
        node_entry = filtered[0]
        node_name = node_entry.get("node", "")
        host_name = node_entry.get("host_name", "")
        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            return
        self._storage_content_pending = {}
        workers_launched = 0
        from .api.metrics import StorageContentListWorker
        for ct in allowed:
            if ct == "backup":
                self._fetch_storage_backups_simple(storage_name, node_name, host_name, cfg)
                continue
            if ct in tab_map:
                worker = StorageContentListWorker(cfg, node_name, storage_name, ct)
                worker.signals.result.connect(
                    lambda sn, content_type, data, w=worker: (
                        self._on_storage_content_piece(sn, content_type, data),
                        self._discard_worker(w)
                    )
                )
                worker.signals.error.connect(
                    lambda sn, content_type, err, w=worker: (
                        self._on_storage_content_piece(sn, content_type, []),
                        self._discard_worker(w)
                    )
                )
                self._run_worker(worker)
                workers_launched += 1
        if workers_launched > 0:
            self._storage_content_pending[storage_name] = {ct: None for ct in allowed if ct in tab_map and ct != "backup"}
        if "images" in allowed or "rootdir" in allowed:
            nodes_with_sto = set(s.get("node") for s in filtered)
            node_vms = [vm for vm in self.all_vms if vm.get("node") in nodes_with_sto]
            self._fetch_storage_disks_simple(storage_name, node_name, host_name, cfg, node_vms)

    def _on_storage_content_piece(self, storage_name, content_type, data):
        if self.current_obj_type != "storage" or self.current_obj_name != storage_name:
            return
        pending = self._storage_content_pending.get(storage_name)
        if pending:
            pending[content_type] = data
            if all(v is not None for v in pending.values()):
                del self._storage_content_pending[storage_name]
                self._render_storage_content(storage_name, pending)

    def _render_storage_content(self, storage_name, pending):
        for ct, items in pending.items():
            if ct == "iso" and items:
                self.storage_iso_stack.setCurrentIndex(1)
                self._populate_content_table(self.storage_iso_table, items)
                self._iso_volids = {v.get("volid", "") for v in items if v.get("volid")}
            elif ct == "iso":
                self.storage_iso_stack.widget(0).setText(tr("No data"))
                self.storage_iso_stack.setCurrentIndex(0)
                self.storage_iso_table.setRowCount(0)
            elif ct in ("vztmpl", "snippets") and items:
                self.storage_tpl_stack.setCurrentIndex(1)
                self._populate_content_table(self.storage_tpl_table, items)
            elif ct in ("vztmpl", "snippets"):
                self.storage_tpl_stack.widget(0).setText(tr("No data"))
                self.storage_tpl_stack.setCurrentIndex(0)
                self.storage_tpl_table.setRowCount(0)

    def _populate_content_table(self, table, items):
        table.setRowCount(len(items))
        for i, vol in enumerate(items):
            table.setItem(i, 0, QTableWidgetItem(vol.get("volid", "")))
            table.setItem(i, 1, QTableWidgetItem(vol.get("format", "")))
            table.setItem(i, 2, QTableWidgetItem(self._format_volsize(vol.get("size", 0))))
            ctime = vol.get("ctime")
            if ctime:
                table.setItem(i, 3, QTableWidgetItem(datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M")))
            else:
                mtime = vol.get("mtime")
                if mtime:
                    table.setItem(i, 3, QTableWidgetItem(datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")))
                else:
                    table.setItem(i, 3, QTableWidgetItem(""))
        table.resizeRowsToContents()
        for r in range(table.rowCount()):
            if table.rowHeight(r) > 24:
                table.setRowHeight(r, 24)

    def _populate_host_storage_table(self, storages):
        table = self.host_storage_table
        table.setRowCount(len(storages))
        for i, st in enumerate(storages):
            table.setItem(i, 0, QTableWidgetItem(st.get("storage", st.get("id", ""))))
            table.setItem(i, 1, QTableWidgetItem(st.get("type", "")))
            content = st.get("content", "")
            if isinstance(content, list):
                content = ", ".join(content)
            table.setItem(i, 2, QTableWidgetItem(content))
            used = st.get("used", 0) or 0
            total = st.get("total", 0) or 1
            used_gb = round(used / (1024**3), 1)
            total_gb = round(total / (1024**3), 1)
            pct = int((used / total) * 100) if total else 0
            table.setItem(i, 3, QTableWidgetItem(f"{used_gb} GiB"))
            table.setItem(i, 4, QTableWidgetItem(f"{total_gb} GiB"))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(pct)
            bar.setStyleSheet(_progress_style(pct))
            bar.setFormat(f"{pct}%")
            table.setCellWidget(i, 5, bar)
            bi = QTableWidgetItem("")
            bi.setFlags(Qt.ItemIsEnabled)
            table.setItem(i, 5, bi)
        table.resizeRowsToContents()
        for r in range(table.rowCount()):
            if table.rowHeight(r) > 24:
                table.setRowHeight(r, 24)

    def _fetch_host_network(self, host_name, host_data):
        node_name = host_data.get("node", "")
        host_cfg_name = host_data.get("host_name", "")
        cfg = self._cfg_by_name.get(host_cfg_name)
        if not cfg:
            self.host_network_stack.widget(0).setText(tr("No data"))
            self.host_network_stack.setCurrentIndex(0)
            return
        from .api.metrics import HostNetworkWorker
        worker = HostNetworkWorker(cfg, node_name)
        worker.signals.network_ready.connect(
            lambda nn, data, w=worker: (
                self._on_host_network(nn, data),
                self._discard_worker(w)
            )
        )
        worker.signals.network_error.connect(
            lambda nn, err, w=worker: (
                self._on_host_network(nn, []),
                self._discard_worker(w)
            )
        )
        self._run_worker(worker)

    def _on_host_network(self, node_name, interfaces):
        if self.current_obj_type != "host" or self.current_obj_name != node_name:
            return
        if interfaces:
            self.host_network_stack.setCurrentIndex(1)
            self._populate_host_network_table(interfaces)
        else:
            self.host_network_stack.widget(0).setText(tr("No data"))
            self.host_network_stack.setCurrentIndex(0)

    def _populate_host_network_table(self, interfaces):
        table = self.host_network_table
        table.setRowCount(len(interfaces))
        for i, iface in enumerate(interfaces):
            table.setItem(i, 0, QTableWidgetItem(iface.get("iface", "")))
            table.setItem(i, 1, QTableWidgetItem(iface.get("type", "")))
            state = iface.get("active", 0)
            state_str = tr("on") if state == 1 else tr("off")
            table.setItem(i, 2, QTableWidgetItem(state_str))
            table.setItem(i, 3, QTableWidgetItem(iface.get("method", "")))
            addresses = iface.get("address", "")
            cidr = iface.get("cidr", "")
            table.setItem(i, 4, QTableWidgetItem(f"{addresses}/{cidr}" if cidr else addresses))
        table.resizeRowsToContents()
        for r in range(table.rowCount()):
            if table.rowHeight(r) > 24:
                table.setRowHeight(r, 24)
        table.setSortingEnabled(True)

    def _fetch_host_services(self, host_name, host_data):
        node_name = host_data.get("node", "")
        host_cfg_name = host_data.get("host_name", "")
        cfg = self._cfg_by_name.get(host_cfg_name)
        if not cfg:
            self.host_services_stack.widget(0).setText(tr("No data"))
            self.host_services_stack.setCurrentIndex(0)
            return
        from .api.metrics import HostServicesWorker
        worker = HostServicesWorker(cfg, node_name)
        worker.signals.services_ready.connect(
            lambda nn, data, w=worker: (
                self._on_host_services(nn, data),
                self._discard_worker(w)
            )
        )
        worker.signals.services_error.connect(
            lambda nn, err, w=worker: (
                self._on_host_services(nn, []),
                self._discard_worker(w)
            )
        )
        self._run_worker(worker)

    def _on_host_services(self, node_name, services):
        if self.current_obj_type != "host" or self.current_obj_name != node_name:
            return
        if services:
            self.host_services_stack.setCurrentIndex(1)
            self._populate_host_services_table(services)
        else:
            self.host_services_stack.widget(0).setText(tr("No data"))
            self.host_services_stack.setCurrentIndex(0)

    def _populate_host_services_table(self, services):
        table = self.host_services_table
        table.setRowCount(len(services))
        for i, svc in enumerate(services):
            table.setItem(i, 0, QTableWidgetItem(svc.get("name", "")))
            state = svc.get("state", "")
            table.setItem(i, 1, QTableWidgetItem(state))
            table.setItem(i, 2, QTableWidgetItem(svc.get("desc", "")))
        table.resizeRowsToContents()
        for r in range(table.rowCount()):
            if table.rowHeight(r) > 24:
                table.setRowHeight(r, 24)
        table.setSortingEnabled(True)

    def _on_storage_timeframe_changed(self, idx):
        if self.current_obj_type == "storage":
            storage_name = self.current_obj_name
            data = self.current_obj_data or {}
            cluster = data.get("cluster")
            host_name_filter = data.get("host_name")
            if cluster:
                filtered = [s for s in self.all_storages
                            if s.get("storage") == storage_name and s.get("cluster") == cluster]
            elif host_name_filter:
                filtered = [s for s in self.all_storages
                            if s.get("storage") == storage_name and s.get("host_name") == host_name_filter]
            else:
                filtered = [s for s in self.all_storages if s.get("storage") == storage_name]
            if filtered:
                self._fetch_storage_metrics(storage_name, filtered)

    def _fetch_storage_metrics(self, storage_name, filtered):
        node_entry = filtered[0]
        node_name = node_entry.get("node", "")
        host_name = node_entry.get("host_name", "")
        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            return
        patched = self.storage_detail_tf_combo
        timeframe = patched.currentData()
        if _HAS_PG:
            self.storage_plot_curve.setData([], [])
        from .api.metrics import StorageMetricsWorker
        worker = StorageMetricsWorker(cfg, node_name, storage_name, timeframe)
        worker.signals.data_fetched.connect(
            lambda tf, nn, md, w=worker: (
                self._on_storage_metrics_fetched(tf, nn, md),
                self._discard_worker(w)
            )
        )
        worker.signals.error_occurred.connect(lambda err, w=worker: self._discard_worker(w))
        self._run_worker(worker)

    def _on_storage_metrics_fetched(self, timeframe, node_name, metrics_dict):
        if self.current_obj_type != "storage":
            return
        if not _HAS_PG or not metrics_dict.get("usage"):
            return
        times = [pt["time"] for pt in metrics_dict["usage"]]
        values = [pt["value"] / (1024**3) for pt in metrics_dict["usage"]]
        self.storage_plot_curve.setData(times, values)

    def _fetch_storage_backups_simple(self, storage_name, node_name, host_name, cfg):
        from .api.metrics import StorageBackupWorker
        worker = StorageBackupWorker(cfg, node_name, storage_name)
        worker.signals.backups_ready.connect(
            lambda sn, data, w=worker: (
                self._on_storage_backups(sn, data),
                self._discard_worker(w)
            )
        )
        worker.signals.backups_error.connect(
            lambda sn, err, w=worker: (
                self._on_storage_backups(sn, []),
                self._discard_worker(w)
            )
        )
        self._run_worker(worker)

    def _on_storage_backups(self, storage_name, backups):
        if self.current_obj_type != "storage" or self.current_obj_name != storage_name:
            return
        if backups:
            self.storage_backups_stack.setCurrentIndex(1)
            self._populate_storage_backups_table(backups)
        else:
            self.storage_backups_stack.widget(0).setText(tr("No data"))
            self.storage_backups_stack.setCurrentIndex(0)
            self.storage_backups_table.setRowCount(0)

    def _populate_storage_backups_table(self, backups):
        table = self.storage_backups_table
        table.setRowCount(len(backups))
        for i, b in enumerate(backups):
            table.setItem(i, 0, QTableWidgetItem(f"VM {b.get('vmid', '')}"))
            table.setItem(i, 1, QTableWidgetItem(b.get("subtype") or b.get("type", "")))
            table.setItem(i, 2, QTableWidgetItem(b.get("format", "")))
            size = b.get("size", 0) or 0
            table.setItem(i, 3, QTableWidgetItem(self._format_volsize(size) if size else "0"))
            ctime = b.get("ctime")
            if ctime:
                table.setItem(i, 4, QTableWidgetItem(datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M")))
            else:
                table.setItem(i, 4, QTableWidgetItem(""))
        table.resizeRowsToContents()
        for r in range(table.rowCount()):
            if table.rowHeight(r) > 24:
                table.setRowHeight(r, 24)

    def _fetch_storage_disks_simple(self, storage_name, node_name, host_name, cfg, node_vms):
        from .api.metrics import StorageDisksWorker
        worker = StorageDisksWorker(cfg, node_name, storage_name, node_vms)
        worker.signals.disks_ready.connect(
            lambda sn, data, w=worker: (
                self._on_storage_disks(sn, data),
                self._discard_worker(w)
            )
        )
        worker.signals.disks_error.connect(
            lambda sn, err, w=worker: (
                self._on_storage_disks(sn, []),
                self._discard_worker(w)
            )
        )
        self._run_worker(worker)

    def _on_storage_disks(self, storage_name, disks):
        if self.current_obj_type != "storage" or self.current_obj_name != storage_name:
            return
        if disks:
            self.storage_disks_stack.setCurrentIndex(1)
            self._populate_storage_disks_table(disks)
        else:
            self.storage_disks_stack.widget(0).setText(tr("No data"))
            self.storage_disks_stack.setCurrentIndex(0)
            self.storage_disks_table.setRowCount(0)

    def _populate_storage_disks_table(self, disks):
        table = self.storage_disks_table
        table.setRowCount(len(disks))
        for i, d in enumerate(disks):
            table.setItem(i, 0, QTableWidgetItem(str(d.get("vmid", ""))))
            table.setItem(i, 1, QTableWidgetItem(d.get("vm_name", "")))
            table.setItem(i, 2, QTableWidgetItem(d.get("volid", "")))
            table.setItem(i, 3, QTableWidgetItem(d.get("bus", "")))
            table.setItem(i, 4, QTableWidgetItem(self._format_volsize(d.get("size", 0))))
        table.resizeRowsToContents()
        for r in range(table.rowCount()):
            if table.rowHeight(r) > 24:
                table.setRowHeight(r, 24)

    def _fetch_host_disks(self, host_name, host_data):
        node_name = host_data.get("node", "")
        host_cfg_name = host_data.get("host_name", "")
        cfg = self._cfg_by_name.get(host_cfg_name)
        if not cfg:
            self.host_disks_stack.widget(0).setText(tr("No data"))
            self.host_disks_stack.setCurrentIndex(0)
            return
        from .api.metrics import HostDisksWorker
        worker = HostDisksWorker(cfg, node_name)
        worker.signals.disks_ready.connect(
            lambda nn, data, w=worker: (
                self._on_host_disks(nn, data),
                self._discard_worker(w)
            )
        )
        worker.signals.disks_error.connect(
            lambda nn, err, w=worker: (
                self._on_host_disks(nn, []),
                self._discard_worker(w)
            )
        )
        self._run_worker(worker)

    def _on_host_disks(self, node_name, disks):
        if self.current_obj_type != "host" or self.current_obj_name != node_name:
            return
        if disks:
            self.host_disks_stack.setCurrentIndex(1)
            self._populate_host_disks_table(disks)
        else:
            self.host_disks_stack.widget(0).setText(tr("No data"))
            self.host_disks_stack.setCurrentIndex(0)

    def _populate_host_disks_table(self, disks):
        table = self.host_disks_table
        # Deduplicate by wwn — FC multipath creates many sd* paths to one LUN
        seen_wwn = set()
        unique = []
        for d in disks:
            wwn = d.get("wwn", "") or d.get("serial", "")
            if wwn and wwn in seen_wwn:
                continue
            if wwn:
                seen_wwn.add(wwn)
            unique.append(d)
        table.setRowCount(len(unique))
        for i, d in enumerate(unique):
            model = d.get("model", "")
            devpath = d.get("devpath", "")
            table.setItem(i, 0, QTableWidgetItem(devpath))
            table.setItem(i, 1, QTableWidgetItem(d.get("type", "")))
            table.setItem(i, 2, QTableWidgetItem(str(model)[:50]))
            table.setItem(i, 3, QTableWidgetItem(self._format_volsize(d.get("size", 0))))
            table.setItem(i, 4, QTableWidgetItem(d.get("wwn", "") or d.get("serial", "")))
        table.resizeRowsToContents()
        for r in range(table.rowCount()):
            if table.rowHeight(r) > 24:
                table.setRowHeight(r, 24)
        table.setSortingEnabled(True)

    def _fetch_host_snapshots(self, host_name, host_data):
        node_name = host_data.get("node", "")
        host_cfg_name = host_data.get("host_name", "")
        cfg = self._cfg_by_name.get(host_cfg_name)
        if not cfg:
            self.host_snapshots_stack.widget(0).setText(tr("No data"))
            self.host_snapshots_stack.setCurrentIndex(0)
            return
        vms = [vm for vm in self.all_vms if vm.get("node") == host_name and vm.get("host_name") == host_cfg_name]
        from .api.metrics import HostSnapshotsWorker
        worker = HostSnapshotsWorker(cfg, node_name, vms)
        worker.signals.snapshots_ready.connect(
            lambda nn, data, w=worker: (
                self._on_host_snapshots(nn, data),
                self._discard_worker(w)
            )
        )
        worker.signals.snapshots_error.connect(
            lambda nn, err, w=worker: (
                self._on_host_snapshots(nn, []),
                self._discard_worker(w)
            )
        )
        self._run_worker(worker)

    def _on_host_snapshots(self, node_name, snapshots):
        if self.current_obj_type != "host" or self.current_obj_name != node_name:
            return
        if snapshots:
            self.host_snapshots_stack.setCurrentIndex(1)
            self._populate_host_snapshots_table(snapshots)
        else:
            self.host_snapshots_stack.widget(0).setText(tr("No snapshots"))
            self.host_snapshots_stack.setCurrentIndex(0)

    def _populate_host_snapshots_table(self, snapshots):
        table = self.host_snapshots_table
        table.setRowCount(len(snapshots))
        for i, snap in enumerate(snapshots):
            table.setItem(i, 0, QTableWidgetItem(f"{snap.get('vmid', '')} {snap.get('vm_name', '')}"))
            table.setItem(i, 1, QTableWidgetItem(snap.get("name", "")))
            table.setItem(i, 2, QTableWidgetItem(snap.get("description", "")))
            snaptime = snap.get("snaptime", 0)
            if snaptime:
                ts = datetime.fromtimestamp(snaptime).strftime("%Y-%m-%d %H:%M:%S")
                table.setItem(i, 3, QTableWidgetItem(ts))
            else:
                table.setItem(i, 3, QTableWidgetItem(""))
            running = tr("yes") if snap.get("running", 0) else tr("no")
            table.setItem(i, 4, QTableWidgetItem(running))
        table.resizeRowsToContents()
        for r in range(table.rowCount()):
            if table.rowHeight(r) > 24:
                table.setRowHeight(r, 24)

    def _show_standalone_folder(self, name):
        self.detail_label.setText(tr("Standalone hosts"))
        self.tabs.setTabVisible(TabIndex.MONITOR, False)
        self.tabs.setTabVisible(TabIndex.HARDWARE, False)
        self.tabs.setTabVisible(TabIndex.SUMMARY, True)
        self.tabs.setCurrentIndex(TabIndex.SUMMARY)
        standalone = []
        for node in self.all_nodes:
            host_name = node.get("host_name", "")
            cfg = self._cfg_by_name.get(host_name)
            cl = cfg.get("cluster") if cfg else None
            if not cl or cl in (False, None, "Standalone"):
                standalone.append(node)
        self._populate_host_summary(standalone)

    def _show_cluster(self, cluster_name):
        self.detail_label.setText(tr("Cluster: {name}").format(name=cluster_name))
        self.tabs.setTabVisible(TabIndex.MONITOR, False)
        self.tabs.setTabVisible(TabIndex.HARDWARE, False)
        self.tabs.setTabVisible(TabIndex.HOST_VMS, False)
        self.tabs.setTabVisible(TabIndex.SUMMARY, True)
        self.tabs.setTabVisible(TabIndex.POOL_VMS, False)
        self.tabs.setCurrentIndex(TabIndex.SUMMARY)

        hosts = []
        for node in self.all_nodes:
            host_name = node.get("host_name", "")
            cfg = self._cfg_by_name.get(host_name)
            if cfg and cfg.get("cluster") == cluster_name:
                hosts.append(node)
        self._populate_host_summary(hosts)

    def _show_host_info(self, host_name, host_data):
        node = next((n for n in self.all_nodes if n.get("node") == host_name), None)
        display_name = node.get("_display_name") if node else host_name
        self.detail_label.setText(tr("Host: {name}").format(name=display_name))

        if host_data and host_data.get("status") == "error":
            err = host_data.get("error", "")
            reason = self._parse_pve_error(err)
            self.info_label.setStyleSheet("font-size: 13px; color: #ef4444; padding: 40px 16px;")
            self.info_label.setText(
                f"<div style='text-align: center;'>"
                f"<span style='font-size: 22px; font-weight: 700;'>" + tr("❌ {} is unavailable").format(display_name) + "</span>"
                f"<br><br>"
                f"<span style='font-size: 14px; color: #dc2626;'>{reason}</span>"
                f"</div>"
            )
            self.info_stack.setCurrentIndex(0)
            self.metrics_widget.setVisible(False)
            self.metrics_widget.clear_curves()
            self.tabs.setCurrentIndex(TabIndex.MONITOR)
            # Hide all tabs except Monitoring (shows error text)
            for t in range(self.tabs.count()):
                self.tabs.setTabVisible(t, t == TabIndex.MONITOR)
            return

        self.metrics_widget.setVisible(True)
        self.tabs.setTabVisible(TabIndex.MONITOR, True)
        self.tabs.setTabVisible(TabIndex.HARDWARE, False)
        self.tabs.setTabVisible(TabIndex.HOST_VMS, True)
        self.tabs.setTabVisible(TabIndex.HOST_STORAGE, True)
        self.tabs.setTabVisible(TabIndex.NETWORK, True)
        self.tabs.setTabVisible(TabIndex.SERVICES, True)
        self.tabs.setTabVisible(TabIndex.HOST_DISKS, True)
        self.tabs.setTabVisible(TabIndex.SNAPSHOTS, True)
        self.tabs.setCurrentIndex(TabIndex.MONITOR)

        self.host_network_stack.setCurrentIndex(0)
        self.host_network_stack.widget(0).setText(tr("Loading..."))
        self.host_network_table.setRowCount(0)
        self.host_services_stack.setCurrentIndex(0)
        self.host_services_stack.widget(0).setText(tr("Loading..."))
        self.host_services_table.setRowCount(0)
        self.host_disks_stack.setCurrentIndex(0)
        self.host_disks_stack.widget(0).setText(tr("Loading..."))
        self.host_disks_table.setRowCount(0)
        self.host_snapshots_stack.setCurrentIndex(0)
        self.host_snapshots_stack.widget(0).setText(tr("Loading..."))
        self.host_snapshots_table.setRowCount(0)

        if host_data and host_data.get("status") != "error":
            host_cfg = self._cfg_by_name.get(host_data.get("host_name", ""))
            address = host_cfg.get("host", "") if host_cfg else ""
            cpu_frac = host_data.get("cpu", 0)
            cpu_pct = round(cpu_frac * 100, 1) if isinstance(cpu_frac, float) else 0
            mem_bytes = host_data.get("mem", 0)
            mem_gb = round(mem_bytes / (1024**3), 2) if mem_bytes else 0
            maxmem_bytes = host_data.get("maxmem", 0)
            maxmem_gb = round(maxmem_bytes / (1024**3), 2) if maxmem_bytes else 0
            uptime = host_data.get("uptime", 0)

            table = self.vm_summary_table
            params = [
                (tr("Host name"), host_data.get("node", "")),
                (tr("Status"), status_text(host_data.get("status", ""))),
                (tr("Address"), address),
                (tr("PVE version"), _fmt_pveversion(host_data.get("pveversion", "?"))),
                ("QEMU", host_data.get("qemu", "?")),
                (tr("Kernel"), host_data.get("kernel", "?")),
                ("LXC", host_data.get("lxctype", "?")),
                (tr("CPU %"), f"{cpu_pct}%"),
                (tr("RAM (GiB)"), f"{mem_gb} / {maxmem_gb}"),
                (tr("Uptime"), _format_uptime(uptime)),
            ]
            table.setRowCount(len(params))
            for i, (k, v) in enumerate(params):
                table.setItem(i, 0, QTableWidgetItem(k))
                table.setItem(i, 1, QTableWidgetItem(str(v)))
            table.resizeRowsToContents()
            self._compact_table(table, 22)
            self.info_stack.setCurrentIndex(1)
        else:
            self.info_label.setText(tr("No data"))
            self.info_stack.setCurrentIndex(0)
            return

        vms_of_host = [vm for vm in self.all_vms
                       if vm.get("node") == host_name
                       and vm.get("host_name") == (host_data.get("host_name") if host_data else host_name)]
        self.host_vm_table.setSortingEnabled(False)
        self.host_vm_table.setRowCount(len(vms_of_host))
        WARN_ROLE = Qt.UserRole + 10
        for i, vm in enumerate(vms_of_host):
            name_item = QTableWidgetItem(str(vm.get("name", "")))
            name_item.setData(Qt.UserRole + 30, vm.get("vmid"))  # store vmid for matching
            self.host_vm_table.setItem(i, 0, name_item)
            self.host_vm_table.setItem(i, 1, QTableWidgetItem(str(vm.get("type", ""))))
            self.host_vm_table.setItem(i, 2, QTableWidgetItem(str(vm.get("node", vm.get("host_name", "")))))
            vm_status = str(vm.get("status", ""))
            vm_status_item = QTableWidgetItem(status_text(vm_status))
            if vm_status == "running":
                vm_status_item.setForeground(QBrush(QColor("#22c55e")))
            elif vm_status == "stopped":
                vm_status_item.setForeground(QBrush(QColor("#ef4444")))
            else:
                vm_status_item.setForeground(QBrush(QColor("#f59e0b")))
            self.host_vm_table.setItem(i, 3, vm_status_item)
            cpu_val = vm.get("cpu", 0)
            if isinstance(cpu_val, float):
                cpu = round(cpu_val * 100, 1)
            else:
                cpu = cpu_val
            self.host_vm_table.setItem(i, 4, QTableWidgetItem(str(cpu)))
            warning = (isinstance(cpu_val, float) and cpu_val >= 0.9) or vm_status == "stopped"
            if warning:
                for c in range(5):
                    it = self.host_vm_table.item(i, c)
                    if it:
                        it.setBackground(QColor("#fef3c7"))
                        it.setData(WARN_ROLE, True)
        self._compact_table(self.host_vm_table)
        self.host_vm_table.setSortingEnabled(True)

        # Storage for host
        host_storages = [s for s in self.all_storages
                         if s.get("node") == host_name
                         and s.get("host_name") == (host_data.get("host_name") if host_data else host_name)]
        self._populate_host_storage_table(host_storages)

        self._fetch_host_network(host_name, host_data)
        self._fetch_host_services(host_name, host_data)
        self._fetch_host_disks(host_name, host_data)
        self._fetch_host_snapshots(host_name, host_data)

        self._fetch_host_metrics(host_data)

    def _fetch_host_metrics(self, host_data):
        node_name = host_data.get("node", "")
        host_cfg_name = host_data.get("host_name", "")
        cfg = self._cfg_by_name.get(host_cfg_name)
        self.metrics_widget.show_disk_io(False)
        if not cfg:
            self.metrics_widget.clear_curves()
            return
        timeframe = self.metrics_widget.timeframe_combo.currentData()
        cache_key = ("host", node_name, timeframe)
        if cache_key in self.metrics_cache:
            self.metrics_widget.update_curves(self.metrics_cache[cache_key])
            return
        from .api.metrics import HostMetricsWorker
        worker = HostMetricsWorker(cfg, node_name, timeframe)
        worker.signals.data_fetched.connect(lambda tf, nn, md, g=self._generation, w=worker: (self._on_host_metrics_fetched(tf, nn, md, g), self._discard_worker(w)))
        worker.signals.error_occurred.connect(lambda err, w=worker: self._discard_worker(w))
        self._run_worker(worker)

    def _on_host_metrics_fetched(self, timeframe, node_name, metrics_dict, gen):
        if gen != self._generation:
            return
        cache_key = ("host", node_name, timeframe)
        self.metrics_cache[cache_key] = metrics_dict
        self.metrics_widget.update_curves(metrics_dict)

    def _show_pool_info(self, pool_name):
        self.detail_label.setText(tr("Pool: {name}").format(name=pool_name))
        self.tabs.setTabVisible(TabIndex.MONITOR, False)
        self.tabs.setTabVisible(TabIndex.HARDWARE, False)
        self.tabs.setTabVisible(TabIndex.OPTIONS, False)
        self.tabs.setTabVisible(TabIndex.HISTORY, False)
        self.tabs.setTabVisible(TabIndex.HOST_VMS, False)
        self.tabs.setTabVisible(TabIndex.POOL_VMS, True)
        self.tabs.setCurrentIndex(TabIndex.POOL_VMS)

        vms_in_pool = [vm for vm in self.all_vms if vm.get("pool") == pool_name]
        self.pool_widget.set_pool_vms(vms_in_pool)

    # ------------------------------------------------------------------
    # Virtual machines
    # ------------------------------------------------------------------
    def _on_timeframe_changed(self, new_timeframe):
        if self.current_obj_type == "host":
            host_data = next((n for n in self.all_nodes if n.get("node") == self.current_obj_name), None)
            if host_data:
                self._fetch_host_metrics(host_data)
        elif self._last_vm_data is not None:
            self._show_vm_metrics(self._last_vm_data)

    def _load_iso_for_node(self, host_name, node_name):
        """Load ISO images available on a node and store in _iso_by_node."""
        self._iso_by_node[node_name] = set()
        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            return
        storages = [s for s in self.all_storages
                    if s.get("node") == node_name
                    and "iso" in (s.get("content", "").split(","))]
        for storage_info in storages:
            storage = storage_info.get("storage")
            if not storage:
                continue
            from .api.metrics import StorageContentListWorker
            worker = StorageContentListWorker(cfg, node_name, storage, "iso")
            worker.signals.result.connect(
                lambda sn, ct, data, n=node_name: self._on_vm_iso_loaded(n, data)
            )
            worker.signals.error.connect(
                lambda sn, ct, err, n=node_name: None
            )
            self._run_worker(worker)

    def _on_vm_iso_loaded(self, node_name, data):
        vols = {v.get("volid") for v in (data or []) if v.get("volid")}
        if node_name in self._iso_by_node:
            self._iso_by_node[node_name].update(vols)

    def _show_vm_info_init(self, vm_name, vm_data, gen):
        self.detail_label.setText(tr("VM/CT: {name}").format(name=vm_name))
        self._last_vm_data = vm_data
        self.tabs.setTabVisible(TabIndex.MONITOR, True)
        self.tabs.setTabVisible(TabIndex.HARDWARE, True)
        self.tabs.setTabVisible(TabIndex.OPTIONS, True)
        self.tabs.setTabVisible(TabIndex.HISTORY, True)
        self.tabs.setTabVisible(TabIndex.HOST_VMS, False)
        self.tabs.setCurrentIndex(TabIndex.MONITOR)

        if not vm_data:
            self.info_label.setText(tr("No data"))
            self.info_stack.setCurrentIndex(0)
            return

        vmid = vm_data.get("vmid")
        host_name = vm_data.get("host_name") or vm_data.get("node")
        detail_key = (vmid, host_name)

        self._show_vm_metrics(vm_data)

        if detail_key not in self.details_cache:
            self.info_label.setText(tr("Loading detailed info..."))
            self.info_stack.setCurrentIndex(0)
            cfg = self._cfg_by_name.get(host_name)
            if cfg:
                node_name = vm_data.get("node") or host_name
                vm_type = vm_data.get("type", "qemu")
                from ..backend import VmDetailWorker
                worker = VmDetailWorker(cfg, node_name, vmid, vm_type)
                worker.signals.detail_ready.connect(lambda d, g=gen, h=host_name, w=worker: (self._on_detail_loaded(d, g, h), self._discard_worker(w)))
                self.current_worker = worker
                self._run_worker(worker)
        else:
            self._display_full_vm_info(vm_data, self.details_cache[detail_key])

        node_name = vm_data.get("node") or host_name
        self._load_iso_for_node(host_name, node_name)

        if detail_key not in self.config_cache:
            self.hardware_widget.set_hardware_data(None)
            self.options_widget.set_options_data(None)
            cfg = self._cfg_by_name.get(host_name)
            if cfg:
                vm_type = vm_data.get("type", "qemu")
                from ..backend import VmConfigWorker
                worker = VmConfigWorker(cfg, node_name, vmid, vm_type)
                worker.signals.config_ready.connect(lambda vid, c, g=gen, h=host_name, w=worker: (self._on_config_loaded(vid, c, g, h), self._discard_worker(w)))
                worker.signals.config_error.connect(lambda vid, err, w=worker: self._discard_worker(w))
                self.current_config_worker = worker
                self._run_worker(worker)
        else:
            detail = self.details_cache.get(detail_key)
            self.hardware_widget.set_hardware_data(self.config_cache[detail_key], detail)
            self.options_widget.set_options_data(self.config_cache[detail_key])

        # Editor context (host_name, vmid, node)
        self.hardware_widget.set_context(host_name, vmid, node_name)
        self.hardware_widget.set_vm_status(vm_data.get("status", ""))
        # ISO — first from all_iso_catalog (mainwindow), then from async loading
        if node_name not in self._iso_by_node and self._all_iso_catalog:
            self._iso_by_node[node_name] = {
                iso["volid"] for iso in self._all_iso_catalog.get(node_name, [])
            }
        iso_set = self._iso_by_node.setdefault(node_name, set())
        self.hardware_widget.set_iso_list(iso_set)
        self.options_widget.set_context(host_name, vmid, node_name)

        if detail_key not in self.task_history_cache:
            self.task_history_widget.set_tasks([])
            cfg = self._cfg_by_name.get(host_name)
            if cfg:
                node_name = vm_data.get("node") or host_name
                from ..backend import VmTaskHistoryWorker
                self.current_hist_worker = VmTaskHistoryWorker(cfg, node_name, vmid, limit=50)
                self.current_hist_worker.signals.tasks_ready.connect(lambda vid, t, g=gen, h=host_name, w=self.current_hist_worker: (self._on_tasks_loaded(vid, t, g, h), self._discard_worker(w)))
                self.current_hist_worker.signals.tasks_error.connect(lambda vid, err, w=self.current_hist_worker: self._discard_worker(w))
                self._run_worker(self.current_hist_worker)
        else:
            self.task_history_widget.set_tasks(self.task_history_cache[detail_key])

    def _show_vm_metrics(self, vm_data):
        if not self.metrics_widget._has_plot:
            return
        self.metrics_widget.show_disk_io(True)
        vmid = vm_data.get("vmid")
        host_name = vm_data.get("host_name") or vm_data.get("node")
        timeframe = self.metrics_widget.timeframe_combo.currentData()
        cache_key = (vmid, host_name, timeframe)
        if cache_key in self.metrics_cache:
            self.metrics_widget.update_curves(self.metrics_cache[cache_key])
            return

        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            return
        node_name = vm_data.get("node") or host_name
        vm_type = vm_data.get("type", "qemu")

        from .api.metrics import MetricsWorker
        worker = MetricsWorker(cfg, node_name, vmid, vm_type, timeframe)
        worker.signals.data_fetched.connect(lambda tf, v, md, g=self._generation, h=host_name, w=worker: (self._on_metrics_fetched(tf, v, md, g, h), self._discard_worker(w)))
        worker.signals.error_occurred.connect(lambda err, w=worker: self._discard_worker(w))
        self._run_worker(worker)

    def _on_metrics_fetched(self, timeframe, vmid, metrics_dict, gen, host_name):
        if gen != self._generation:
            return
        if not self._last_vm_data:
            return
        current_host = self._last_vm_data.get("host_name") or self._last_vm_data.get("node")
        current_vmid = self._last_vm_data.get("vmid")
        if current_vmid != vmid or current_host != host_name:
            return
        cache_key = (vmid, host_name, timeframe)
        self.metrics_cache[cache_key] = metrics_dict
        self.metrics_widget.update_curves(metrics_dict)

    def _on_detail_loaded(self, detail, gen, host_name):
        if gen != self._generation:
            return
        vmid = detail.get("vmid")
        detail_key = (vmid, host_name)
        vm_data = self._vms_by_key.get((host_name, vmid), {})
        if detail["status"] == "ok":
            self.details_cache[detail_key] = detail["data"]
            self._display_full_vm_info(vm_data, detail["data"])
            self.tabs.setCurrentIndex(TabIndex.MONITOR)
            if detail_key in self.config_cache:
                self.hardware_widget.set_hardware_data(self.config_cache[detail_key], detail["data"])
            # Update _last_vm_data and buttons (status may have changed after start/stop/reboot)
            if self._last_vm_data:
                merged = {**vm_data, **detail["data"]}
                self._last_vm_data = merged
                self._update_action_buttons(merged)
        else:
            self.info_label.setText(self._parse_pve_error(detail.get("error", "")))
            self.info_stack.setCurrentIndex(0)

    def _on_vm_config_change_requested(self, host_name, vmid_str, params):
        """Launches VmConfigUpdateWorker to save a parameter change."""
        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            return
        vmid = int(vmid_str)
        vm = self._vms_by_key.get((host_name, vmid))
        node = vm.get("node") if vm else host_name
        vm_type = "qemu"

        from ..backend import VmConfigUpdateWorker
        worker = VmConfigUpdateWorker(cfg, node, vmid, params, vm_type)
        worker.signals.config_updated.connect(
            lambda vid, res, w=worker: (
                self.config_update_result.emit(tr("VM {vid}: parameter changed").format(vid=vid)),
                self._reload_config(vmid, host_name),
                self._discard_worker(w),
            )
        )
        worker.signals.config_update_error.connect(
            lambda vid, err, w=worker: (
                self.config_update_result.emit(tr("Error changing VM {vid}: {err}").format(vid=vid, err=err)),
                self._discard_worker(w),
            )
        )
        self._run_worker(worker)

    def _on_config_loaded(self, vmid, config, gen, host_name):
        if gen != self._generation:
            return
        detail_key = (vmid, host_name)
        self.config_cache[detail_key] = config
        if self._last_vm_data and self._last_vm_data.get("vmid") == vmid and self._last_vm_data.get("host_name") == host_name:
            detail = self.details_cache.get(detail_key)
            self.hardware_widget.set_hardware_data(config, detail)
            self.options_widget.set_options_data(config)

    def _on_tasks_loaded(self, vmid, tasks, gen, host_name):
        if gen != self._generation:
            return
        detail_key = (vmid, host_name)
        self.task_history_cache[detail_key] = tasks
        if self._last_vm_data and self._last_vm_data.get("vmid") == vmid and self._last_vm_data.get("host_name") == host_name:
            self.task_history_widget.set_tasks(tasks)

    def _reload_config(self, vmid, host_name):
        """Reloads VM config after a change."""
        detail_key = (vmid, host_name)
        self.config_cache.pop(detail_key, None)
        cfg = self._cfg_by_name.get(host_name)
        if cfg and self._last_vm_data:
            node_name = self._last_vm_data.get("node") or host_name
            gen = self._generation
            from ..backend import VmConfigWorker
            worker = VmConfigWorker(cfg, node_name, vmid, "qemu")
            worker.signals.config_ready.connect(
                lambda vid, c, g=gen, h=host_name, w=worker: (
                    self._on_config_loaded(vid, c, g, h),
                    self._discard_worker(w),
                )
            )
            worker.signals.config_error.connect(lambda vid, err, w=worker: self._discard_worker(w))
            self._run_worker(worker)

    def _display_full_vm_info(self, basic, detail):
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

            table = self.vm_summary_table
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
            self._compact_table(table, 22)

            self.info_stack.setCurrentIndex(1)
        except Exception:
            traceback.print_exc()
            self.info_label.setText(tr("Error building info"))
            self.info_stack.setCurrentIndex(0)
