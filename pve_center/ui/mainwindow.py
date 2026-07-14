import json
import logging
import sys
import threading
import time
import traceback

from PySide6.QtCore import QSize, Qt, QThreadPool, QTimer, Slot
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QSystemTrayIcon,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..backend import ClusterTasksWorker, DeleteVmWorker, FetchWorker, delete_host_token
from ..config import (
    export_config,
    import_config,
    load_tasks_cache,
    load_ui_state,
    save_config,
    save_tasks_cache,
    save_ui_state,
)
from . import theme
from .detail_panel import DetailPanel
from .i18n import get_language, supported_languages, tr
from .icons import get_icon
from .notification import NotificationManager
from .theme import Color
from .tree_panel import TreePanel
from .utils import build_cfg_index, build_vm_index
from .vm_actions import confirm_vm_action
from .widgets.cluster_tasks_widget import ClusterTasksWidget

logger = logging.getLogger(__name__)

# Максимум одновременно работающих воркеров
MAX_WORKERS = 16

class MainWindow(QMainWindow):
    def __init__(self, nodes_cfg=None):
        super().__init__()
        self.setWindowTitle("PVE Center")
        from .icons import init_icons
        init_icons()
        self.setWindowIcon(get_icon("app"))
        self.resize(1600, 900)

        theme.load()

        self.nodes_cfg = nodes_cfg or []
        self._cfg_by_name = build_cfg_index(self.nodes_cfg)
        self._vms_by_key = {}
        self.all_nodes = []
        self.all_vms = []
        self.all_storages = []
        self.all_iso_images = {}
        self.all_ha_groups = {}
        self.all_pools = []

        self._first_selection_done = False
        self._seen_storage_keys = set()
        self._last_host_statuses = {}
        self._last_vm_statuses = {}

        self.tree_panel = TreePanel(self.nodes_cfg)
        self.detail_panel = DetailPanel(self.nodes_cfg)
        self.detail_panel.config_update_result.connect(
            lambda msg: self._notifications.show(msg, error=tr("Error") in msg)
        )
        self.detail_panel.transfer_started.connect(
            lambda key, desc: self.tasks_widget.add_progress_row(key, desc)
        )
        self.detail_panel.transfer_progress.connect(
            lambda key, pct: self.tasks_widget.update_progress_row(key, pct)
        )
        self.detail_panel.transfer_finished.connect(
            lambda key, ok, msg: self.tasks_widget.finish_progress_row(key, ok, msg)
        )

        self.tree_panel.item_selected.connect(self.detail_panel.show_details)
        self.detail_panel.navigate_requested.connect(self.tree_panel.find_and_select)

        self.tree_panel.add_server_requested_context.connect(self._on_add_server)

        self.tree_panel.host_remove_requested.connect(self._on_host_remove)
        self.tree_panel.host_token_refresh_requested.connect(self._on_host_token_refresh)
        self.tree_panel.host_trust_ssl_changed.connect(self._on_host_trust_ssl)
        self.tree_panel.vm_create_requested.connect(self._on_vm_create_requested)
        self.tree_panel.vm_delete_requested.connect(self._on_vm_delete_requested)
        self.tree_panel.vm_action_requested.connect(self._on_vm_action_from_tree)
        self.tree_panel.vm_migrate_requested.connect(self._on_vm_migrate)
        self.tree_panel.vm_clone_requested.connect(self._on_vm_clone)
        self.tree_panel.console_requested.connect(self._on_console_from_tree)

        self._notifications = NotificationManager(self)

        self._tray = None
        self._tray_minimize_to_tray = True
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._init_tray()

        self.h_splitter = QSplitter(Qt.Horizontal)
        self.h_splitter.addWidget(self.tree_panel)
        self.h_splitter.addWidget(self.detail_panel)

        self.tasks_widget = ClusterTasksWidget()

        self.v_splitter = QSplitter(Qt.Vertical)
        self.v_splitter.addWidget(self.h_splitter)
        self.v_splitter.addWidget(self.tasks_widget)

        # Восстанавливаем положение сплиттеров из SQLite
        self._restore_splitter_state()

        # Сохраняем позиции сплиттера при изменении
        def _save_splitter():
            save_ui_state("splitter_h", json.dumps(self.h_splitter.sizes()))
            save_ui_state("splitter_v", json.dumps(self.v_splitter.sizes()))
        self.h_splitter.splitterMoved.connect(_save_splitter)
        self.v_splitter.splitterMoved.connect(_save_splitter)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.v_splitter)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.status_bar = self.statusBar()
        self.status_label = QLabel("")
        self.status_bar.addPermanentWidget(self.status_label)

        self._refresh_spinner = QLabel("")
        self._refresh_spinner.setStyleSheet(f"color: {Color.GRAY_500}; padding-right: 8px;")
        self._refresh_spinner.setAccessibleName(tr("Refreshing data"))
        self._refresh_spinner.setToolTip(tr("Data refresh in progress"))
        self.status_bar.insertPermanentWidget(0, self._refresh_spinner)

        self._lang_combo = QComboBox()
        self._lang_combo.setFixedWidth(110)
        self._lang_combo.setStyleSheet(
            f"QComboBox {{ font-size: 12px; border: 1px solid {Color.SLATE_300}; border-radius: 3px; "
            f"padding: 1px 4px; background: {Color.SLATE_100}; color: {Color.SLATE_700}; }}"
            f"QComboBox:hover {{ border-color: {Color.SLATE_400}; background: {Color.SLATE_200}; }}"
            f"QComboBox::drop-down {{ border: none; width: 16px; }}"
            f"QComboBox QAbstractItemView {{ font-size: 12px; }}"
        )
        self._lang_combo.blockSignals(True)
        current_lang = get_language()
        for code, native_name in sorted(supported_languages().items(), key=lambda x: x[0]):
            self._lang_combo.addItem(native_name, code)
            if code == current_lang:
                self._lang_combo.setCurrentIndex(self._lang_combo.count() - 1)
        self._lang_combo.blockSignals(False)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        self.status_bar.insertPermanentWidget(1, self._lang_combo)
        self._spin_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._spin_idx = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(100)
        self._spin_timer.timeout.connect(self._tick_spinner)
        self._soft_refresh_active = False

        self._workers = set()
        self._tasks_gen = 0
        self._tasks_started = False

        # Поколение hard refresh — предотвращает race condition при повторных refresh_data()
        self._refresh_gen = 0

        # Переменные для мягкого обновления
        self.last_refresh_ts = 0
        self.refresh_interval = 5
        self._soft_refresh_running = False
        self._soft_refresh_start = 0
        self._soft_refresh_timeout = 30
        self._soft_gen = 0
        self._soft_counter = 0
        self._soft_nodes = []
        self._soft_vms = []
        self._soft_storages = []
        self._soft_had_errors = False

        # Восстанавливаем состояние окна: геометрия, maximized, последний выбранный элемент
        self._restore_window_state()

        self.show()
        self.refresh_data()

        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)
        self._toolbar.setIconSize(QSize(18, 18))
        self._toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)

        add_action = QAction(get_icon("add"), tr("Add server"), self)
        add_action.setToolTip(tr("Add server") + " (Ctrl+N)")
        add_action.triggered.connect(lambda: self._on_add_server())
        self._toolbar.addAction(add_action)

        refresh_action = QAction(get_icon("refresh"), tr("Refresh"), self)
        refresh_action.setToolTip(tr("Refresh data") + " (Ctrl+R)")
        refresh_action.triggered.connect(self.refresh_data)
        self._toolbar.addAction(refresh_action)

        self._toolbar.addSeparator()

        export_action = QAction(get_icon("export"), tr("Export configuration"), self)
        export_action.setToolTip(tr("Export configuration"))
        export_action.triggered.connect(self._on_export_config)
        self._toolbar.addAction(export_action)

        import_action = QAction(get_icon("import"), tr("Import configuration"), self)
        import_action.setToolTip(tr("Import configuration"))
        import_action.triggered.connect(self._on_import_config)
        self._toolbar.addAction(import_action)

        self._toolbar.addSeparator()

        about_action = QAction(get_icon("about"), tr("About"), self)
        about_action.setToolTip(tr("About"))
        about_action.triggered.connect(self._on_about)
        self._toolbar.addAction(about_action)

        quit_action = QAction(tr("Quit"), self)
        quit_action.setToolTip(tr("Quit") + " (Ctrl+Q)")
        quit_action.triggered.connect(self._tray_quit)
        self._toolbar.addAction(quit_action)

        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().Policy.Expanding, spacer.sizePolicy().Policy.Fixed)
        self._toolbar.addWidget(spacer)

        brand = QLabel("PVE Center")
        brand.setStyleSheet("font-weight: 600; font-size: 14px; letter-spacing: -0.01em; padding-right: 8px;")
        self._toolbar.addWidget(brand)

        self.addToolBar(self._toolbar)

        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.refresh_data)
        QShortcut(QKeySequence("F5"), self, activated=self.refresh_data)
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self._tray_quit)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=lambda: self._on_add_server())
        QShortcut(QKeySequence("Del"), self, activated=self.tree_panel.request_delete_current)

        # Таймер автообновления основных данных
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(20000)          # 20 секунд
        self.refresh_timer.timeout.connect(self.soft_refresh)
        self.refresh_timer.start()

        # Детектор зависания главного потока
        self._last_heartbeat = time.time()
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(500)
        self._heartbeat_timer.timeout.connect(self._heartbeat)
        self._heartbeat_timer.start()
        self._freeze_detector = threading.Thread(target=self._detect_freeze, daemon=True, name="freeze-detector")
        self._closing = False
        self._freeze_detector.start()

        # Таймер обновления задач кластера
        self.tasks_timer = QTimer(self)
        self.tasks_timer.setInterval(60000)            # 60 секунд
        self.tasks_timer.timeout.connect(self.refresh_cluster_tasks)
        self.tasks_timer.start()

        # Первая загрузка задач — стартует из on_worker_finished, когда all_nodes заполнен
        self._cached_tasks = load_tasks_cache()

        # Offline mode: load cached resources immediately so tree is populated
        # before the first network response arrives
        from ..config import load_resources_cache
        cached_res, cached_ts = load_resources_cache()
        if cached_res:
            try:
                self.all_nodes[:] = cached_res.get("nodes", [])
                self.all_vms[:] = cached_res.get("vms", [])
                self.all_storages[:] = cached_res.get("storages", [])
                self._vms_by_key = build_vm_index(self.all_vms)
                self.detail_panel.all_nodes[:] = self.all_nodes
                self.detail_panel.all_vms[:] = self.all_vms
                self.detail_panel.all_storages[:] = self.all_storages
                self.detail_panel._vms_by_key = self._vms_by_key
                self.tree_panel.update_node_statuses(self.all_nodes, self.all_vms)
                self._offline_mode = True
                self._offline_ts = cached_ts
            except Exception:
                self._offline_mode = False
                self._offline_ts = None
        else:
            self._offline_mode = False
            self._offline_ts = None

    def _run_worker(self, worker):
        if len(self._workers) >= MAX_WORKERS:
            return
        self._workers.add(worker)
        if hasattr(worker.signals, "finished"):
            worker.signals.finished.connect(lambda w=worker: self._discard_worker(w))
        QThreadPool.globalInstance().start(worker)

    def _discard_worker(self, worker):
        """Удаляет воркер из _workers и отключает signal connections."""
        self._workers.discard(worker)
        if not worker or not hasattr(worker, "signals"):
            return
        import warnings
        sigs = worker.signals
        for attr in ("finished", "result_ready", "tasks_ready", "tasks_error",
                     "detail_ready", "config_ready", "config_error",
                     "config_updated", "config_update_error",
                     "action_result", "action_error",
                     "console_ready", "console_error",
                     "vm_created", "vm_error", "vm_deleted",
                     "vm_migrated", "vm_cloned",
                     "token_ready", "token_error"):
            sig = getattr(sigs, attr, None)
            if sig is None:
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    sig.disconnect()
            except (RuntimeError, TypeError):
                pass

    def _dedup_storages(self, new_storages, host_name, target_list):
        for st in new_storages:
            st["host_name"] = host_name
            key = (st.get("storage"), st.get("node"), host_name)
            if key not in self._seen_storage_keys:
                self._seen_storage_keys.add(key)
                target_list.append(st)

    def _on_about(self):
        from .about_dialog import AboutDialog
        AboutDialog(self).exec()

    def _on_export_config(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Export configuration"), "pve-center-nodes.enc",
            tr("Encrypted config (*.enc);;All files (*.*)"))
        if not path:
            return
        if export_config(path):
            QMessageBox.information(self, tr("Export"),
                                    tr("Configuration exported to:\n{path}").format(path=path))
        else:
            QMessageBox.warning(self, tr("Export"),
                                 tr("No servers to export. "
                                    "Add at least one server first."))

    def _on_import_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Import configuration"), "",
            tr("Encrypted config (*.enc);;All files (*.*)"))
        if not path:
            return
        merged = import_config(path, merge=True)
        if merged is None:
            return
        self.nodes_cfg = merged
        self._cfg_by_name = build_cfg_index(self.nodes_cfg)
        self.tree_panel.set_servers(merged)
        self.detail_panel.update_nodes_cfg(merged)
        QMessageBox.information(self, tr("Import"),
                                tr("Configuration imported ({count} hosts).").format(
                                    count=len(merged)))

    # ------------------------------------------------------------
    # Добавление сервера
    # ------------------------------------------------------------
    def _on_add_server(self, context=""):
        from .add_server_dialog import AddServerDialog
        dialog = AddServerDialog(self, context)
        if dialog.exec() != AddServerDialog.Accepted:
            return
        cfg = dialog.get_config()
        self.nodes_cfg.append(cfg)
        self._cfg_by_name[cfg.get("name", "")] = cfg
        self.tree_panel.set_servers(self.nodes_cfg)
        self.detail_panel.update_nodes_cfg(self.nodes_cfg)
        save_config(self.nodes_cfg)
        self.refresh_data()

    # ------------------------------------------------------------
    # Создание ВМ
    # ------------------------------------------------------------
    def _on_vm_create_requested(self, node_name, host_name):
        from .create_vm_dialog import CreateVmDialog
        dialog = CreateVmDialog(self, nodes=self.all_nodes, storages=self.all_storages,
                                pools=getattr(self, 'all_pools', []),
                                iso_images=getattr(self, 'all_iso_images', {}),
                                ha_groups=getattr(self, 'all_ha_groups', {}))
        if dialog.exec() != CreateVmDialog.Accepted:
            return
        params = dialog.get_params()
        sel_node = dialog.get_node()
        ha_group = dialog.get_ha_group()

        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            self.status_label.setText(tr("Config not found for {}").format(host_name))
            return

        from ..backend import CreateVmWorker
        worker = CreateVmWorker(cfg, sel_node, params, ha_group=ha_group)
        worker.signals.vm_created.connect(lambda msg, w=worker: (
            self._notifications.show(msg),
            self.status_label.setText(msg),
            QTimer.singleShot(1500, self.refresh_data),
            self._discard_worker(w)
        ))
        worker.signals.vm_error.connect(lambda err, w=worker: (
            self._notifications.show(tr("VM creation error: {}").format(err), error=True),
            self.status_label.setText(tr("Error: {}").format(err)),
            self._discard_worker(w)
        ))
        self._run_worker(worker)
        self.status_label.setText(tr("Creating VM..."))

    # ------------------------------------------------------------
    # Удаление ВМ
    # ------------------------------------------------------------
    def _on_vm_delete_requested(self, host_name, node, vmid):
        # Найти ВМ по vmid + host_name
        vm = self._vms_by_key.get((host_name, vmid))
        vm_name = vm.get("name") if vm else f"VM {vmid}"
        vm_status = vm.get("status", "") if vm else ""
        is_running = vm_status == "running"

        # Найти конфиг хоста
        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            self._notifications.show(tr("Config not found for {}").format(host_name), error=True)
            return

        # Диалог подтверждения
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Delete VM"))
        dlg.setFixedSize(480, is_running and 280 or 240)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        warning = QLabel(
            f"<b>{tr('VM')} «{vm_name}» (VMID: {vmid})</b> {tr('on node')} <b>{node}</b>"
            "<br><br>"
            f"<span style='color:{Color.ERROR_RED};'>{tr('This action is irreversible.')} "
            f"{tr('All VM disks will be deleted.')}</span>"
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)

        if is_running:
            run_warning = QLabel(
                f"<span style='color:{Color.ERROR_RED}; font-weight:bold;'>{tr('VM is running!')}</span>"
                f"<br>{tr('It will be forcibly stopped and deleted.')}"
            )
            run_warning.setWordWrap(True)
            layout.addWidget(run_warning)

        confirm_check = QCheckBox(tr("I confirm deletion"))
        layout.addWidget(confirm_check)

        if is_running:
            force_check = QCheckBox(tr("Force stop and delete"))
            force_check.setStyleSheet(f"color: {Color.ERROR_RED};")
            layout.addWidget(force_check)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        delete_btn = QPushButton(tr("Delete"))
        delete_btn.setFixedWidth(120)
        delete_btn.setObjectName("dangerBtn")
        delete_btn.setEnabled(False)
        cancel_btn = QPushButton(tr("Cancel"))
        cancel_btn.setFixedWidth(120)
        cancel_btn.setDefault(True)

        if is_running:
            confirm_check.toggled.connect(
                lambda checked: delete_btn.setEnabled(checked and force_check.isChecked()))
            force_check.toggled.connect(
                lambda checked: delete_btn.setEnabled(checked and confirm_check.isChecked()))
        else:
            confirm_check.toggled.connect(delete_btn.setEnabled)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        cancel_btn.clicked.connect(dlg.reject)

        confirmed = [False]
        def do_delete():
            confirmed[0] = True
            dlg.accept()
        delete_btn.clicked.connect(do_delete)

        dlg.exec()
        if not confirmed[0]:
            return

        worker = DeleteVmWorker(cfg, node, vmid)
        worker.signals.vm_deleted.connect(lambda msg, w=worker: (
            self._notifications.show(msg),
            self.status_label.setText(msg),
            QTimer.singleShot(1500, self.refresh_data),
            self._discard_worker(w)
        ))
        worker.signals.vm_error.connect(lambda err, w=worker: (
            self._notifications.show(tr("VM deletion error: {}").format(err), error=True),
            self.status_label.setText(tr("Error: {}").format(err)),
            self._discard_worker(w)
        ))
        self._run_worker(worker)
        self.status_label.setText(tr("Deleting VM {}...").format(vmid))

    def _confirm_delete(self, text):
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Delete"))
        dlg.setFixedSize(420, 130)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(text))
        layout.addStretch()
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        yes_btn = QPushButton(tr("Yes"))
        yes_btn.setFixedWidth(80)
        no_btn = QPushButton(tr("No"))
        no_btn.setFixedWidth(80)
        no_btn.setDefault(True)
        btn_layout.addWidget(yes_btn)
        btn_layout.addWidget(no_btn)
        layout.addLayout(btn_layout)
        result = [False]
        yes_btn.clicked.connect(lambda: (result.__setitem__(0, True), dlg.accept()))
        no_btn.clicked.connect(dlg.reject)
        dlg.exec()
        return result[0]

    def _on_vm_action_from_tree(self, host_name, node, vmid, action):
        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            self._notifications.show(tr("Config not found for {}").format(host_name), error=True)
            return
        vm = self._vms_by_key.get((host_name, vmid))
        vm_type = (vm.get("type", "qemu") if vm else "qemu")
        if not confirm_vm_action(action, vmid, parent=self):
            return
        from ..backend import VmActionWorker
        worker = VmActionWorker(cfg, node, vmid, vm_type, action)
        worker.signals.action_result.connect(lambda msg: (
            self._notifications.show(msg),
            self.refresh_data()
        ))
        worker.signals.action_error.connect(lambda err: (
            self._notifications.show(tr("Action error: {}").format(err), error=True)
        ))
        self._run_worker(worker)

    def _on_console_from_tree(self, host_name, node, vmid):
        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            self._notifications.show(tr("Config not found for {}").format(host_name), error=True)
            return
        vm = self._vms_by_key.get((host_name, vmid))
        vm_type = (vm.get("type", "qemu") if vm else "qemu")
        from ..backend import VmConsoleWorker
        worker = VmConsoleWorker(cfg, node, vmid, vm_type)
        worker.signals.console_ready.connect(lambda msg: self._notifications.show(msg))
        worker.signals.console_error.connect(lambda err: self._notifications.show(err, error=True))
        self._run_worker(worker)

    def _get_cluster_nodes(self, host_name, current_node):
        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            return [n for n in self.all_nodes if n.get("node") != current_node]
        cluster = cfg.get("cluster", "")
        if not cluster or cluster in (False, None, "Standalone"):
            return []
        return [n for n in self.all_nodes
                if n.get("node") != current_node
                and n.get("host_name") == host_name]

    def _on_vm_migrate(self, host_name, node, vmid):
        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            self._notifications.show(tr("Config not found for {}").format(host_name), error=True)
            return
        vm = self._vms_by_key.get((host_name, vmid))
        vm_info = {
            "name": vm.get("name", "") if vm else "",
            "vmid": vmid,
            "type": vm.get("type", "qemu") if vm else "qemu",
            "node": node,
        }
        cluster_nodes = self._get_cluster_nodes(host_name, node)
        from .migrate_vm_dialog import MigrateVMDialog
        dialog = MigrateVMDialog(self, vm_info=vm_info,
                                 cluster_nodes=cluster_nodes,
                                 current_node=node)
        if dialog.exec() != MigrateVMDialog.Accepted:
            return
        target = dialog.get_target()
        if not target:
            return
        vm_type = vm_info["type"]
        with_local_disks = dialog.get_with_local_disks()
        from ..backend import MigrateVmWorker
        worker = MigrateVmWorker(cfg, node, vmid, vm_type, target,
                                 with_local_disks=with_local_disks)
        worker.signals.vm_migrated.connect(lambda msg: (
            self._notifications.show(msg),
            self.status_label.setText(msg),
            QTimer.singleShot(2000, self.refresh_data)
        ))
        worker.signals.vm_error.connect(lambda err: (
            self._notifications.show(tr("Migration error: {}").format(err), error=True),
            self.status_label.setText(tr("Error: {}").format(err))
        ))
        self._run_worker(worker)
        self.status_label.setText(tr("Migrating VM {vmid}...").format(vmid=vmid))

    def _on_vm_clone(self, host_name, node, vmid):
        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            self._notifications.show(tr("Config not found for {}").format(host_name), error=True)
            return
        vm = self._vms_by_key.get((host_name, vmid))
        vm_info = {
            "name": vm.get("name", "") if vm else "",
            "vmid": vmid,
            "type": vm.get("type", "qemu") if vm else "qemu",
            "node": node,
        }
        cluster_nodes = self._get_cluster_nodes(host_name, node)
        node_storages = [s for s in self.all_storages if s.get("node") == node]
        from .clone_vm_dialog import CloneVMDialog
        dialog = CloneVMDialog(self, vm_info=vm_info,
                               cluster_nodes=cluster_nodes,
                               current_node=node,
                               storages=node_storages)
        if dialog.exec() != CloneVMDialog.Accepted:
            return
        params = dialog.get_params()
        vm_type = vm_info["type"]
        from ..backend import CloneVmWorker
        worker = CloneVmWorker(cfg, node, vmid, vm_type, params)
        worker.signals.vm_cloned.connect(lambda msg: (
            self._notifications.show(msg),
            self.status_label.setText(msg),
            QTimer.singleShot(2000, self.refresh_data)
        ))
        worker.signals.vm_error.connect(lambda err: (
            self._notifications.show(tr("Clone error: {}").format(err), error=True),
            self.status_label.setText(tr("Error: {}").format(err))
        ))
        self._run_worker(worker)
        self.status_label.setText(tr("Cloning VM {vmid}...").format(vmid=vmid))

    def _on_host_remove(self, item_type, item_name):
        if item_type == "host":
            text = tr("Remove host «{}» from configuration?").format(item_name)
            matched = [c for c in self.nodes_cfg if c.get("name") == item_name]
        elif item_type == "cluster":
            if not item_name:
                return
            count = sum(1 for c in self.nodes_cfg if c.get("cluster") == item_name)
            text = tr("Remove cluster «{name}» ({count} records) from configuration?").format(name=item_name, count=count)
            matched = [c for c in self.nodes_cfg if c.get("cluster") == item_name]
        elif item_type == "section":
            if item_name == tr("Clusters"):
                matched = [c for c in self.nodes_cfg if c.get("cluster") and c.get("cluster") not in (False, None, "Standalone")]
                text = tr("Remove all {} cluster records from configuration?").format(len(matched))
            elif item_name == tr("Standalone hosts"):
                matched = [c for c in self.nodes_cfg if not c.get("cluster") or c.get("cluster") in (False, None, "Standalone")]
                text = tr("Remove all {} standalone host records from configuration?").format(len(matched))
            else:
                return
        else:
            return
        if not self._confirm_delete(text):
            return
        errors = []
        for cfg in matched:
            ok = delete_host_token(cfg)
            if not ok:
                errors.append(cfg.get("name", cfg.get("host", "?")))
        if errors:
            self._notifications.show(
                tr("Failed to delete tokens: {}. Configuration cleared.").format(", ".join(errors)),
                error=True
            )
        self.nodes_cfg = [c for c in self.nodes_cfg if c not in matched]
        self._cfg_by_name = build_cfg_index(self.nodes_cfg)
        self.tree_panel.set_servers(self.nodes_cfg)
        self.detail_panel.update_nodes_cfg(self.nodes_cfg)
        save_config(self.nodes_cfg)
        from ..config import delete_node_tokens
        delete_node_tokens([c.get("name", "") for c in matched])
        self.refresh_data()

    def _on_host_token_refresh(self, host_name):
        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            return
        from .add_server_dialog import AddServerDialog
        dialog = AddServerDialog(self, "reconnect")
        dialog.setWindowTitle(tr("Refresh token — {}").format(host_name))
        dialog.host_input.setText(cfg.get("host", ""))
        dialog.host_input.setEnabled(False)
        dialog.user_input.setText(cfg.get("user", "root@pam"))
        dialog.trust_ssl_cb.setChecked(bool(cfg.get("trust_ssl", True)))
        if dialog.exec() != AddServerDialog.Accepted:
            return
        new_cfg = dialog.get_config()
        idx = next((i for i, c in enumerate(self.nodes_cfg) if c.get("name") == host_name), None)
        if idx is not None:
            new_cfg["name"] = host_name
            new_cfg["host"] = cfg["host"]
            new_cfg["cluster"] = cfg.get("cluster", False)
            if cfg.get("cluster_rep"):
                new_cfg["cluster_rep"] = True
            self.nodes_cfg[idx] = new_cfg
            self._cfg_by_name[host_name] = new_cfg
        self.tree_panel.set_servers(self.nodes_cfg)
        self.detail_panel.update_nodes_cfg(self.nodes_cfg)
        save_config(self.nodes_cfg)
        self.refresh_data()

    def _on_host_trust_ssl(self, host_name, trust_ssl):
        cfg = self._cfg_by_name.get(host_name)
        if not cfg:
            return
        cfg["trust_ssl"] = bool(trust_ssl)
        save_config(self.nodes_cfg)
        self.tree_panel.set_servers(self.nodes_cfg)
        self.refresh_data()
    def refresh_data(self):
        # Отменяем все pending soft_refresh — их результаты устарели
        self._soft_gen += 1
        self._soft_refresh_running = False
        self._soft_refresh_active = False
        self._soft_counter = 0
        self._soft_had_errors = False
        self._soft_nodes.clear()
        self._soft_vms.clear()
        self._soft_storages.clear()
        self._spin_timer.stop()
        self._refresh_spinner.setText("")

        # Сохраняем выделение и вкладку (для послед. восстановления после refresh)
        current_key = self.tree_panel.get_current_item_key()
        if current_key is not None:
            self._saved_key = current_key
        current_tab = self.detail_panel.tabs.currentIndex()
        if current_tab is not None:
            self._saved_tab = current_tab
        current_type = self.detail_panel.current_obj_type
        if current_type is not None:
            self._saved_obj_type = current_type

        self.all_nodes.clear()
        self.all_vms.clear()
        self.all_storages.clear()
        self.detail_panel.all_nodes.clear()
        self.detail_panel.all_vms.clear()
        self.detail_panel.all_storages.clear()
        self._vms_by_key.clear()
        self.all_iso_images.clear()
        self.all_ha_groups.clear()
        self.all_pools.clear()
        self._seen_storage_keys.clear()
        self._first_selection_done = False
        self._tasks_started = False

        self.tree_panel.start_loading()

        active_cfgs = [cfg for cfg in self.nodes_cfg if not cfg.get("skip", False)]

        self._refresh_gen += 1
        refresh_gen = self._refresh_gen

        for cfg in active_cfgs:
            worker = FetchWorker(cfg)
            worker.signals.result_ready.connect(
                lambda data, w=worker, g=refresh_gen: self.on_worker_finished(data, w, g)
            )
            self._run_worker(worker)

        if not active_cfgs:
            self.all_nodes.clear()
            self.all_vms.clear()
            self.all_storages.clear()
            self.tree_panel.update_data(self.all_nodes, self.all_vms, self.all_storages, final=True)
            self.detail_panel.set_lists(self.all_nodes, self.all_vms, self.all_storages)
            self.detail_panel.set_iso_catalog(self.all_iso_images)
            self._update_status_bar()

    @Slot(dict)
    def on_worker_finished(self, data, worker=None, gen=0):
        if gen != 0 and gen != self._refresh_gen:
            return
        status = data.get("status", "error")
        host = data.get("host", "")
        if status == "ok":
            is_cluster = worker.node_cfg.get("cluster_rep", False) if worker else False
            existing_node_keys = {(n.get("node"), n.get("host_name")) for n in self.all_nodes}
            for node in data.get("nodes", []):
                node["host_name"] = host
                node["_is_cluster"] = is_cluster
                key = (node.get("node"), host)
                if key in existing_node_keys:
                    idx = next(i for i, n in enumerate(self.all_nodes)
                               if (n.get("node"), n.get("host_name")) == key)
                    self.all_nodes[idx] = node
                else:
                    existing_node_keys.add(key)
                    self.all_nodes.append(node)
            for vm in data.get("vms", []):
                vm["host_name"] = host
                # Дедупликация: если VM с таким (host_name, vmid) уже есть — заменяем
                vm_key = (host, vm.get("vmid", 0))
                idx = next((i for i, v in enumerate(self.all_vms)
                            if (v.get("host_name"), v.get("vmid")) == vm_key), None)
                if idx is not None:
                    self.all_vms[idx] = vm
                else:
                    self.all_vms.append(vm)
                self._vms_by_key[vm_key] = vm
            self._dedup_storages(data.get("storages", []), host, self.all_storages)
            # Собираем уникальные имена пулов
            known = {p["poolid"] for p in self.all_pools if "poolid" in p}
            for pn in data.get("pool_names", []):
                if pn and pn not in known:
                    known.add(pn)
                    self.all_pools.append({"poolid": pn})
            # Собираем ISO-образы (node -> list volid)
            for nname, isos in data.get("iso_images", {}).items():
                if isos:
                    self.all_iso_images[nname] = isos
            # Собираем HA группы (host_name -> [group, ...])
            ha_list = data.get("ha_groups", [])
            if ha_list:
                self.all_ha_groups[host] = ha_list
        else:
            is_cluster_err = worker.node_cfg.get("cluster_rep", False) if worker else False
            err_msg = data.get("error", "Unknown error")
            err_key = (host, host)
            if not any((n.get("node"), n.get("host_name")) == err_key for n in self.all_nodes):
                self.all_nodes.append({
                    "node": host,
                    "status": "error",
                    "error": err_msg,
                    "host_name": host,
                    "_display_name": host,
                    "_is_cluster": is_cluster_err
                })
            from ..utils import parse_pve_error
            reason = parse_pve_error(err_msg)
            self._notifications.show(
                tr("Connection error: {host} — {reason}").format(host=host, reason=reason),
                error=True,
            )

        self._detect_status_changes()

        # Обновляем статус-бар сразу — частичные данные лучше, чем пустота
        self._update_status_bar()

        # Промежуточное обновление дерева — без очистки спиннеров.
        # Не загрузившиеся кластеры остаются в дереве как заглушки со спиннерами.
        self.tree_panel.update_data(self.all_nodes, self.all_vms, self.all_storages, final=False)
        self.detail_panel.set_lists(self.all_nodes, self.all_vms, self.all_storages)
        self.detail_panel.set_iso_catalog(self.all_iso_images)

        # Выбираем первый элемент в дереве при первой же возможности.
        if not getattr(self, '_first_selection_done', False) and self.tree_panel.tree.topLevelItemCount() > 0:
            self._do_first_selection()
            self.detail_panel.refresh_current_view()

        # Загрузка задач стартует при первом же воркере — не ждём все данные
        if not self._tasks_started:
            self._tasks_started = True
            QTimer.singleShot(0, self.refresh_cluster_tasks)

        fetch_workers = [w for w in self._workers if isinstance(w, FetchWorker)]
        if not fetch_workers:
            # Выбираем первый элемент до финальной перестройки дерева —
            # сводка кластера появляется сразу, не дожидаясь _build_tree с сотнями VM
            if not getattr(self, '_first_selection_done', False):
                self._do_first_selection()
                self.detail_panel.refresh_current_view()
            # Все данные загружены — финальная перестройка: спиннеры гаснут, VM/пулы в дереве
            self.tree_panel.update_data(self.all_nodes, self.all_vms, self.all_storages, final=True)
            self.last_refresh_ts = time.time()
            self._soft_refresh_start = time.time()
            self._update_status_bar()
            from ..config import save_resources_cache
            save_resources_cache(self.all_nodes, self.all_vms, self.all_storages)
            if self._offline_mode:
                self._offline_mode = False
                self._offline_ts = None
                self._update_status_bar()

    def _detect_status_changes(self, nodes=None, vms=None):
        nodes = nodes if nodes is not None else self.all_nodes
        vms = vms if vms is not None else self.all_vms
        for node in nodes:
            name = node.get("node", "")
            status = node.get("status", "unknown")
            old = self._last_host_statuses.get(name)
            if old is not None and old != status:
                display = node.get("_display_name") or name
                self._notifications.host_status_changed(display, old, status)
            self._last_host_statuses[name] = status

        for vm in vms:
            key = (vm.get("host_name", ""), vm.get("vmid", 0))
            status = vm.get("status", "unknown")
            old = self._last_vm_statuses.get(key)
            if old is not None and old != status:
                vm_name = vm.get("name") or f"VM {vm.get('vmid', '?')}"
                self._notifications.vm_status_changed(vm_name, vm.get("host_name", ""), status)
            self._last_vm_statuses[key] = status

    # ------------------------------------------------------------
    # Фоновое (мягкое) обновление
    # ------------------------------------------------------------
    def soft_refresh(self):
        now = time.time()
        if now - self.last_refresh_ts < self.refresh_interval:
            return
        if self._soft_refresh_running:
            if now - self._soft_refresh_start > self._soft_refresh_timeout:
                self._soft_gen += 1
                self._soft_refresh_running = False
                self._soft_refresh_active = False
                self._soft_counter = 0
                self._soft_nodes.clear()
                self._soft_vms.clear()
                self._soft_storages.clear()
                self._seen_storage_keys.clear()
            else:
                return
        # Atomic guard: claim ownership before any nested event loop can fire.
        self._soft_refresh_running = True
        self._soft_refresh_active = True
        my_gen = self._soft_gen + 1
        self._soft_gen = my_gen
        soft_gen = my_gen
        if not self._spin_timer.isActive():
            self._spin_timer.start()
        self._soft_refresh_start = now
        self.last_refresh_ts = now

        self._soft_nodes.clear()
        self._soft_vms.clear()
        self._soft_storages.clear()
        self._seen_storage_keys.clear()
        self._soft_counter = 0
        self._soft_had_errors = False

        active_cfgs = [cfg for cfg in self.nodes_cfg if not cfg.get("skip", False)]
        if not active_cfgs:
            self._soft_refresh_running = False
            return
        for cfg in active_cfgs:
            worker = FetchWorker(cfg)
            worker.signals.result_ready.connect(
                lambda data, w=worker, g=soft_gen: (self.on_soft_refresh_result(data, w, g), self._discard_worker(w))
            )
            self._run_worker(worker)

    @Slot(dict)
    def on_soft_refresh_result(self, data, worker=None, gen=0):
        if gen != self._soft_gen:
            return
        status = data.get("status", "error")
        host = data.get("host", "")
        if status == "ok":
            is_cluster = worker.node_cfg.get("cluster_rep", False) if worker else False
            existing_keys = {(n.get("node"), n.get("host_name")) for n in self._soft_nodes}
            for node in data.get("nodes", []):
                node["host_name"] = host
                node["_is_cluster"] = is_cluster
                key = (node.get("node"), host)
                if key in existing_keys:
                    idx = next(i for i, n in enumerate(self._soft_nodes)
                               if (n.get("node"), n.get("host_name")) == key)
                    self._soft_nodes[idx] = node
                else:
                    existing_keys.add(key)
                    self._soft_nodes.append(node)
            for vm in data.get("vms", []):
                vm["host_name"] = host
                vm_key = (host, vm.get("vmid", 0))
                idx = next((i for i, v in enumerate(self._soft_vms)
                            if (v.get("host_name"), v.get("vmid")) == vm_key), None)
                if idx is not None:
                    self._soft_vms[idx] = vm
                else:
                    self._soft_vms.append(vm)
            self._dedup_storages(data.get("storages", []), host, self._soft_storages)
        else:
            self._soft_had_errors = True
            err_msg = data.get("error", "Unknown error")
            err_key = (host, host)
            if not any((n.get("node"), n.get("host_name")) == err_key for n in self._soft_nodes):
                self._soft_nodes.append({
                    "node": host,
                    "status": "error",
                    "error": err_msg,
                    "host_name": host,
                    "_display_name": host
                })

        self._soft_counter += 1
        active_count = len([cfg for cfg in self.nodes_cfg if not cfg.get("skip", False)])

        if self._soft_counter >= active_count:
            if self._soft_nodes or self._soft_vms:
                try:
                    self.tree_panel.update_node_statuses(self._soft_nodes, self._soft_vms)
                    self.all_nodes[:] = self._soft_nodes
                    self.all_vms[:] = self._soft_vms
                    self.all_storages[:] = self._soft_storages
                    self._vms_by_key = build_vm_index(self.all_vms)
                    self.detail_panel.all_nodes[:] = self._soft_nodes
                    self.detail_panel.all_vms[:] = self._soft_vms
                    self.detail_panel.all_storages[:] = self._soft_storages
                    self.detail_panel._vms_by_key = self._vms_by_key
                    self.detail_panel.refresh_current_view()
                    # Пробрасываем уже собранные на hard refresh пулы/HA —
                    # soft refresh не имеет ProxmoxAPI, пересобрать не может
                    self.detail_panel.all_pools = self.all_pools
                    self.detail_panel.all_ha_groups = self.all_ha_groups
                    self.detail_panel.set_iso_catalog(self.all_iso_images)
                    self._detect_status_changes(self._soft_nodes, self._soft_vms)
                    self._update_status_bar()
                    from ..config import save_resources_cache
                    save_resources_cache(self._soft_nodes, self._soft_vms, self._soft_storages)
                    if self._offline_mode:
                        self._offline_mode = False
                        self._offline_ts = None
                except Exception as exc:
                    logger.debug("soft_refresh error", exc_info=True)
                    self._notifications.show(
                        tr("Error: {err}").format(err=str(exc)[:100]),
                        error=True,
                    )
            self._soft_nodes.clear()
            self._soft_vms.clear()
            self._soft_storages.clear()
            self._soft_counter = 0
            self._soft_refresh_running = False
            self._soft_refresh_active = False

    # ------------------------------------------------------------
    # Обновление задач кластера
    # ------------------------------------------------------------
    def refresh_cluster_tasks(self):
        # Показываем кэшированные задачи мгновенно, пока воркер грузит свежие
        if self._cached_tasks:
            self.tasks_widget.set_tasks(self._cached_tasks)
        elif not self._workers:
            self.tasks_widget.set_placeholder(tr("Loading tasks..."))
        if not self.nodes_cfg or not self.all_nodes:
            return

        node_requests = []
        seen_nodes = set()

        rep_cfg = next((c for c in self.nodes_cfg if c.get("cluster_rep")), None)
        for n in self.all_nodes:
            pve_node = n.get("node", "")
            host_name = n.get("host_name", "")
            if not pve_node or pve_node in seen_nodes:
                continue
            display = n.get("_display_name", "")

            if rep_cfg and display.endswith(f"@{rep_cfg.get('cluster', '')}"):
                cfg = rep_cfg
            else:
                cfg = self._cfg_by_name.get(host_name)
                if cfg is None:
                    cfg = next((c for c in self.nodes_cfg
                                if c["name"].split("@")[0] == pve_node), None)
            if cfg:
                node_requests.append((cfg, pve_node))
                seen_nodes.add(pve_node)

        if not node_requests:
            return

        self._tasks_gen += 1
        tasks_gen = self._tasks_gen
        worker = ClusterTasksWorker(node_requests)
        worker.signals.tasks_ready.connect(
            lambda t, w=worker, g=tasks_gen: (
                self._on_cluster_tasks_loaded(t, g),
                self._discard_worker(w)
            )
        )
        worker.signals.tasks_error.connect(lambda err, w=worker: self._discard_worker(w))
        # finished подключается в _run_worker; но ClusterTasksWorker запускается
        # через threading.Thread (а не QThreadPool), чтобы не блокировать слот
        # пула на время join() внутри run(). Поэтому регистрируем в _workers
        # вручную — иначе воркер не учтётся в MAX_WORKERS и утечёт при падении
        # до emit.
        if len(self._workers) >= MAX_WORKERS:
            try:
                worker.signals.tasks_ready.disconnect()
                worker.signals.tasks_error.disconnect()
            except (RuntimeError, TypeError):
                pass
            return
        self._workers.add(worker)
        worker.signals.finished.connect(lambda w=worker: self._discard_worker(w))
        t = threading.Thread(target=worker.run, daemon=True)
        t.start()

    def _on_cluster_tasks_loaded(self, tasks, gen):
        if gen != self._tasks_gen:
            return
        self._update_cluster_tasks_widget(tasks)

    def _update_cluster_tasks_widget(self, tasks):
        self._cached_tasks = tasks
        save_tasks_cache(tasks)
        try:
            node_map = {}
            for n in list(self.all_nodes):
                node_map[n.get("node")] = n.get("_display_name") or n.get("node")
            vm_map = {}
            for vm in list(self.all_vms):
                vm_vmid = vm.get("vmid")
                if vm_vmid is not None:
                    vm_map[int(vm_vmid)] = vm.get("name")
            for task in tasks:
                node = task.get("node", "")
                if node in node_map:
                    task["_display_name"] = node_map[node]
                # API может вернуть vmid как 'vmid', 'id' или только в UPID
                vmid = task.get("vmid") or task.get("id")
                if vmid is None or vmid == "":
                    upid = task.get("upid", "")
                    if upid.startswith("UPID:"):
                        parts = upid.split(":")
                        if len(parts) >= 7 and parts[6].isdigit():
                            vmid = parts[6]
                        if not vmid and len(parts) >= 9:
                            info = ":".join(parts[8:])
                            idx = info.find("--vmid ")
                            if idx >= 0:
                                rest = info[idx + 7:].lstrip()
                                end = rest.find(" ")
                                num = rest[:end] if end >= 0 else rest
                                if num.isdigit():
                                    vmid = num
                if vmid is not None:
                    try:
                        task["_vmid"] = str(vmid)
                        task["_vm_name"] = vm_map.get(int(vmid), "")
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            logger.error("Ошибка при обогащении задач: %s", e)
        try:
            self.tasks_widget.set_tasks(tasks)
        except Exception as e:
            logger.error("Ошибка при установке задач: %s", e)

    # ------------------------------------------------------------
    # Сохранение/восстановление состояния окна (SQLite)
    # ------------------------------------------------------------
    def _restore_window_state(self):
        """Восстанавливает геометрию, maximized, splitter-ы и последний выбранный элемент.
        Вызывается до show(), чтобы окно появилось в правильном положении.
        Используем SQLite (ui_state), а не QSettings, потому что:
          - Единое хранилище: задачи и UI-состояние в одном файле
          - Прозрачность: файл в ~/.config/pve-center/, можно глянуть руками
          - QSettings размазывает данные по platform-specific местам (реестр/dconf/INI)"""
        raw = load_ui_state("window_geometry")
        if raw:
            try:
                geo = json.loads(raw)
                if isinstance(geo, list) and len(geo) == 4:
                    self.setGeometry(*geo)
            except (TypeError, ValueError):
                pass
        raw = load_ui_state("window_maximized")
        if raw == "1":
            self.showMaximized()
        raw = load_ui_state("saved_key")
        if raw:
            try:
                val = json.loads(raw)
                if isinstance(val, list):
                    self._saved_key = tuple(val)
                else:
                    self._saved_key = val
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        raw = load_ui_state("saved_tab")
        if raw:
            try:
                self._saved_tab = int(raw)
            except (TypeError, ValueError):
                pass
        raw = load_ui_state("saved_obj_type")
        if raw:
            self._saved_obj_type = raw

    def _restore_splitter_state(self):
        """Восстанавливает позиции сплиттеров из SQLite."""
        raw = load_ui_state("splitter_h")
        if raw:
            try:
                vals = json.loads(raw)
                if isinstance(vals, list):
                    self.h_splitter.setSizes([int(x) for x in vals])
            except (TypeError, ValueError):
                pass
        else:
            self.h_splitter.setSizes([360, 1140])
        raw = load_ui_state("splitter_v")
        if raw:
            try:
                vals = json.loads(raw)
                if isinstance(vals, list):
                    self.v_splitter.setSizes([int(x) for x in vals])
            except (TypeError, ValueError):
                pass
        else:
            self.v_splitter.setSizes([550, 150])

    # ------------------------------------------------------------
    # Строка состояния
    # ------------------------------------------------------------
    def _update_status_bar(self):
        from datetime import datetime
        now_str = datetime.now().strftime("%H:%M:%S")
        hosts_ok = sum(1 for n in self.all_nodes if n.get("status") == "online")
        hosts_total = len(self.all_nodes)
        hosts_err = sum(1 for n in self.all_nodes if n.get("status") == "error")
        vms_count = len(self.all_vms)
        vms_running = sum(1 for v in self.all_vms if v.get("status") == "running")
        clusters = set()
        for n in self.all_nodes:
            c = n.get("cluster") or ""
            if c and c != "Standalone":
                clusters.add(c)
        total_cpu = sum(n.get("cpu", 0) * n.get("sockets", 1) for n in self.all_nodes if n.get("status") == "online")
        total_mem = sum(n.get("mem", 0) for n in self.all_nodes if n.get("status") == "online")
        total_maxmem = sum(n.get("maxmem", 0) for n in self.all_nodes if n.get("status") == "online")
        mem_pct = (total_mem / total_maxmem * 100) if total_maxmem else 0
        cpu_pct = (total_cpu * 100) if total_cpu else 0
        parts = [
            tr("Hosts: {ok}/{total}").format(ok=hosts_ok, total=hosts_total),
            tr("Clusters: {n}").format(n=len(clusters)) if clusters else "",
            tr("VMs: {running}/{total}").format(running=vms_running, total=vms_count),
            tr("CPU: {pct}%").format(pct=f"{cpu_pct:.0f}"),
            tr("RAM: {pct}%").format(pct=f"{mem_pct:.0f}"),
        ]
        if hosts_err:
            parts.append(tr("Errors: {n}").format(n=hosts_err))
        if self._offline_mode:
            parts.append(tr("Offline (cached)"))
        parts.append(now_str)
        self.status_label.setText("  ".join(p for p in parts if p))

    def _do_first_selection(self):
        self._first_selection_done = True
        saved_key = getattr(self, '_saved_key', None)
        if saved_key:
            item = self.tree_panel.find_item_by_key(saved_key)
            if item:
                self.tree_panel.tree.setCurrentItem(item)
                self.tree_panel._on_item_clicked(item, 0)
                saved_tab = getattr(self, '_saved_tab', 0)
                saved_type = getattr(self, '_saved_obj_type', None)
                if saved_type and saved_type == self.detail_panel.current_obj_type:
                    QTimer.singleShot(100, lambda: self.detail_panel.tabs.setCurrentIndex(saved_tab))
            else:
                self.tree_panel.select_first_item()
        else:
            self.tree_panel.select_first_item()

    # ------------------------------------------------------------
    # Детектор зависания
    # ------------------------------------------------------------
    def _tick_spinner(self):
        """Анимирует спиннер в статус-баре при фоновом обновлении."""
        if not self._soft_refresh_active:
            self._refresh_spinner.setText("")
            self._spin_timer.stop()
            return
        self._refresh_spinner.setText(self._spin_frames[self._spin_idx])
        self._spin_idx = (self._spin_idx + 1) % len(self._spin_frames)

    def _heartbeat(self):
        self._last_heartbeat = time.time()

    def _detect_freeze(self):
        while not self._closing:
            time.sleep(2)
            if self._closing:
                break
            now = time.time()
            elapsed = now - self._last_heartbeat
            if elapsed > 3:
                logger.error("=== FREEZE DETECTED: main thread unresponsive for %.1fs ===", elapsed)
                try:
                    main_thread = threading.main_thread()
                    frame = sys._current_frames().get(main_thread.ident)
                    if frame is not None:
                        import io
                        buf = io.StringIO()
                        traceback.print_stack(frame, file=buf)
                        stack = buf.getvalue()
                        if stack:
                            logger.error("MainThread stack:\n%s", stack)
                        else:
                            logger.error("MainThread stack: <empty>")
                    else:
                        logger.error("MainThread frame not found")
                except Exception as exc:
                    logger.error("Failed to dump stack: %s", exc, exc_info=True)
                logger.error("=== END FREEZE REPORT ===")

    def _on_language_changed(self, idx):
        code = self._lang_combo.itemData(idx)
        if not code or code == get_language():
            return
        save_ui_state("language", code)
        msg = QMessageBox(QMessageBox.Question, tr("Language changed"),
                          tr("The language will change after restart. Restart now?"),
                          parent=self)
        yes = msg.addButton(tr("Yes"), QMessageBox.YesRole)
        msg.addButton(tr("No"), QMessageBox.NoRole)
        msg.setDefaultButton(yes)
        msg.exec()
        if msg.clickedButton() == yes:
            # Save everything and restart via Python module (path-independent)
            self.refresh_timer.stop()
            self.tasks_timer.stop()
            self.tree_panel.save_state()
            from PySide6.QtCore import QCoreApplication
            QCoreApplication.quit()
            import os
            import sys
            self_dir = os.path.dirname(os.path.abspath(__file__))          # ui/
            pkg_dir = os.path.dirname(self_dir)                            # pve_center/
            parent_dir = os.path.dirname(pkg_dir)                          # /home/taurus
            env = os.environ.copy()
            env["PYTHONPATH"] = f"{parent_dir}:{env.get('PYTHONPATH', '')}"
            os.execve(sys.executable, [sys.executable, "-m", "pve_center.main"], env)

    # ------------------------------------------------------------
    # Tray icon
    # ------------------------------------------------------------
    def _init_tray(self):
        icon = get_icon("app")
        if icon is None:
            return
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("PVE Center")
        menu = QMenu(self)
        show_act = menu.addAction(tr("Show window"))
        show_act.triggered.connect(self._tray_show)
        refresh_act = menu.addAction(tr("Refresh"))
        refresh_act.triggered.connect(self.refresh_data)
        menu.addSeparator()
        quit_act = menu.addAction(tr("Quit"))
        quit_act.triggered.connect(self._tray_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _tray_show(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_quit(self):
        self._tray_minimize_to_tray = False
        self._save_state_and_quit()

    def _save_state_and_quit(self):
        self._closing = True
        self.refresh_timer.stop()
        self.tasks_timer.stop()
        self._heartbeat_timer.stop()
        self._spin_timer.stop()
        self.tree_panel.save_state()
        geo = self.geometry()
        save_ui_state("window_geometry", json.dumps([geo.x(), geo.y(), geo.width(), geo.height()]))
        save_ui_state("window_maximized", "1" if self.isMaximized() else "0")
        key = self.tree_panel.get_current_item_key()
        if key:
            save_ui_state("saved_key", json.dumps(key))
        save_ui_state("saved_tab", str(self.detail_panel.tabs.currentIndex()))
        save_ui_state("saved_obj_type", str(self.detail_panel.current_obj_type or ""))
        save_ui_state("splitter_h", json.dumps(self.h_splitter.sizes()))
        save_ui_state("splitter_v", json.dumps(self.v_splitter.sizes()))
        QThreadPool.globalInstance().clear()
        QThreadPool.globalInstance().waitForDone(3000)
        if self._tray:
            self._tray.hide()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self._tray_show()

    # ------------------------------------------------------------
    # Закрытие приложения
    # ------------------------------------------------------------
    def closeEvent(self, event):
        if self._tray and self._tray.isVisible() and self._tray_minimize_to_tray:
            event.ignore()
            self.hide()
            self._tray.showMessage(
                "PVE Center",
                tr("Minimize to tray"),
                QSystemTrayIcon.Information,
                2000,
            )
            return
        self._save_state_and_quit()
        super().closeEvent(event)
