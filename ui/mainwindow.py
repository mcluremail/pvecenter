import sys
import time
import threading
import traceback
import logging
from PySide6.QtWidgets import (QMainWindow, QSplitter,
                               QHBoxLayout, QVBoxLayout, QWidget,
                               QMessageBox, QLabel, QDialog, QPushButton, QCheckBox)
from PySide6.QtCore import Qt, Slot, QTimer, QThreadPool

from ..backend import FetchWorker, ClusterTasksWorker, DeleteVmWorker, delete_host_token
from ..config import save_config, save_tasks_cache, load_tasks_cache, save_ui_state, load_ui_state
import json as _json
from . import theme
from .notification import NotificationManager
from .tree_panel import TreePanel
from .detail_panel import DetailPanel
from .widgets.cluster_tasks_widget import ClusterTasksWidget
from .icons import get_icon
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
            lambda msg: self._notifications.show(msg, error="Ошибка" in msg)
        )

        self.tree_panel.item_selected.connect(self.detail_panel.show_details)

        self.tree_panel.add_server_requested_context.connect(self._on_add_server)

        self.tree_panel.host_remove_requested.connect(self._on_host_remove)
        self.tree_panel.host_token_refresh_requested.connect(self._on_host_token_refresh)
        self.tree_panel.vm_create_requested.connect(self._on_vm_create_requested)
        self.tree_panel.vm_delete_requested.connect(self._on_vm_delete_requested)

        self._notifications = NotificationManager(self)

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
            save_ui_state("splitter_h", _json.dumps(self.h_splitter.sizes()))
            save_ui_state("splitter_v", _json.dumps(self.v_splitter.sizes()))
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
        self._refresh_spinner.setStyleSheet("color: #6b7280; padding-right: 8px;")
        self.status_bar.insertPermanentWidget(0, self._refresh_spinner)
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

        # Таймер автообновления основных данных
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(20000)          # 20 секунд
        self.refresh_timer.timeout.connect(self.soft_refresh)
        self.refresh_timer.start()

        # Таймер watchdog — проверяет, жив ли event loop
        self._watchdog_timer = QTimer(self)
        self._watchdog_timer.setInterval(1000)
        self._watchdog_timer.timeout.connect(lambda: None)
        self._watchdog_timer.start()

        # Детектор зависания главного потока
        self._last_heartbeat = time.time()
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(500)
        self._heartbeat_timer.timeout.connect(self._heartbeat)
        self._heartbeat_timer.start()
        self._freeze_detector = threading.Thread(target=self._detect_freeze, daemon=True, name="freeze-detector")
        self._freeze_detector.start()

        # Таймер обновления задач кластера
        self.tasks_timer = QTimer(self)
        self.tasks_timer.setInterval(60000)            # 60 секунд
        self.tasks_timer.timeout.connect(self.refresh_cluster_tasks)
        self.tasks_timer.start()

        # Первая загрузка задач — стартует из on_worker_finished, когда all_nodes заполнен
        self._cached_tasks = load_tasks_cache()

    def _run_worker(self, worker):
        if len(self._workers) >= MAX_WORKERS:
            return
        self._workers.add(worker)
        if hasattr(worker.signals, "finished"):
            worker.signals.finished.connect(lambda w=worker: self._discard_worker(w))
        QThreadPool.globalInstance().start(worker)

    def _discard_worker(self, worker):
        """Безопасно удаляет воркер из _workers.
        Вызывается в finally после обработки сигнала, чтобы воркер не утекал
        при RuntimeError (уничтоженный виджет) или любом исключении в хендлере."""
        self._workers.discard(worker)

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

        cfg = next((c for c in self.nodes_cfg if c["name"] == host_name), None)
        if not cfg:
            self.status_label.setText(f"Конфиг не найден для {host_name}")
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
            self._notifications.show(f"Ошибка создания ВМ: {err}", error=True),
            self.status_label.setText(f"Ошибка: {err}"),
            self._discard_worker(w)
        ))
        self._run_worker(worker)
        self.status_label.setText("Создание ВМ...")

    # ------------------------------------------------------------
    # Удаление ВМ
    # ------------------------------------------------------------
    def _on_vm_delete_requested(self, host_name, node, vmid):
        # Найти ВМ по vmid + host_name
        vm = next((v for v in self.all_vms
                   if v.get("vmid") == vmid and v.get("host_name") == host_name), None)
        vm_name = vm.get("name") if vm else f"VM {vmid}"
        vm_status = vm.get("status", "") if vm else ""
        is_running = vm_status == "running"

        # Найти конфиг хоста
        cfg = next((c for c in self.nodes_cfg if c.get("name") == host_name), None)
        if not cfg:
            self._notifications.show(f"Конфиг не найден для {host_name}", error=True)
            return

        # Диалог подтверждения
        dlg = QDialog(self)
        dlg.setWindowTitle("Удаление ВМ")
        dlg.setFixedSize(480, is_running and 280 or 240)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        warning = QLabel(
            f"<b>ВМ «{vm_name}» (VMID: {vmid})</b> на узле <b>{node}</b>"
            "<br><br>"
            "<span style='color:#c0392b;'>Это действие необратимо. "
            "Все диски ВМ будут удалены.</span>"
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)

        if is_running:
            run_warning = QLabel(
                "<span style='color:#c0392b; font-weight:bold;'>ВМ запущена!</span>"
                "<br>Она будет принудительно остановлена и удалена."
            )
            run_warning.setWordWrap(True)
            layout.addWidget(run_warning)

        confirm_check = QCheckBox("Я подтверждаю удаление")
        layout.addWidget(confirm_check)

        if is_running:
            force_check = QCheckBox("Принудительно остановить и удалить")
            force_check.setStyleSheet("color: #c0392b;")
            layout.addWidget(force_check)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        delete_btn = QPushButton("Удалить")
        delete_btn.setFixedWidth(120)
        delete_btn.setObjectName("dangerBtn")
        delete_btn.setEnabled(False)
        cancel_btn = QPushButton("Отмена")
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
            self._notifications.show(f"Ошибка удаления ВМ: {err}", error=True),
            self.status_label.setText(f"Ошибка: {err}"),
            self._discard_worker(w)
        ))
        self._run_worker(worker)
        self.status_label.setText(f"Удаление ВМ {vmid}...")

    def _confirm_delete(self, text):
        dlg = QDialog(self)
        dlg.setWindowTitle("Удаление")
        dlg.setFixedSize(420, 130)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(text))
        layout.addStretch()
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        yes_btn = QPushButton("Да")
        yes_btn.setFixedWidth(80)
        no_btn = QPushButton("Нет")
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

    def _on_host_remove(self, item_type, item_name):
        if item_type == "host":
            text = f"Удалить хост «{item_name}» из конфигурации?"
            matched = [c for c in self.nodes_cfg if c.get("name") == item_name]
        elif item_type == "cluster":
            if not item_name:
                return
            count = sum(1 for c in self.nodes_cfg if c.get("cluster") == item_name)
            text = f"Удалить кластер «{item_name}» ({count} записей) из конфигурации?"
            matched = [c for c in self.nodes_cfg if c.get("cluster") == item_name]
        elif item_type == "section":
            if item_name == "Кластеры":
                matched = [c for c in self.nodes_cfg if c.get("cluster") and c.get("cluster") not in (False, None, "Standalone")]
                text = f"Удалить все {len(matched)} кластерных записей из конфигурации?"
            elif item_name == "Отдельные хосты":
                matched = [c for c in self.nodes_cfg if not c.get("cluster") or c.get("cluster") in (False, None, "Standalone")]
                text = f"Удалить все {len(matched)} записей отдельных хостов из конфигурации?"
            else:
                return
        else:
            return
        if not self._confirm_delete(text):
            return
        for cfg in matched:
            delete_host_token(cfg)
        self.nodes_cfg = [c for c in self.nodes_cfg if c not in matched]
        save_config(self.nodes_cfg)
        self.refresh_data()

    def _on_host_token_refresh(self, host_name):
        cfg = next((c for c in self.nodes_cfg if c.get("name") == host_name), None)
        if not cfg:
            return
        from .add_server_dialog import AddServerDialog
        dialog = AddServerDialog(self, "reconnect")
        dialog.setWindowTitle(f"Обновить токен — {host_name}")
        dialog.host_input.setText(cfg.get("host", ""))
        dialog.host_input.setEnabled(False)
        dialog.user_input.setText(cfg.get("user", "root@pam"))
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
        save_config(self.nodes_cfg)
        self.refresh_data()

    # ------------------------------------------------------------
    # Ручное обновление (кнопка "Обновить")
    # ------------------------------------------------------------
    def refresh_data(self):
        # Отменяем все pending soft_refresh — их результаты устарели
        self._soft_gen += 1
        self._soft_refresh_running = False
        self._soft_counter = 0
        self._soft_had_errors = False
        self._soft_nodes.clear()
        self._soft_vms.clear()
        self._soft_storages.clear()

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
        self.all_iso_images.clear()
        self.all_ha_groups.clear()
        self._seen_storage_keys.clear()
        self._first_selection_done = False

        self.tree_panel.start_loading()

        active_cfgs = [cfg for cfg in self.nodes_cfg if not cfg.get("skip", False)]

        self._refresh_gen += 1
        refresh_gen = self._refresh_gen

        for cfg in active_cfgs:
            worker = FetchWorker(cfg)
            worker.signals.result_ready.connect(
                lambda data, w=worker, g=refresh_gen: (self.on_worker_finished(data, w, g), self._discard_worker(w))
            )
            self._run_worker(worker)

        if not active_cfgs:
            self.all_nodes.clear()
            self.all_vms.clear()
            self.all_storages.clear()
            self.tree_panel.update_data(self.all_nodes, self.all_vms, self.all_storages)
            self.detail_panel.set_lists(self.all_nodes, self.all_vms, self.all_storages)
            self._update_status_bar()

    @Slot(dict)
    def on_worker_finished(self, data, worker=None, gen=0):
        if gen != 0 and gen != self._refresh_gen:
            return
        if data["status"] == "ok":
            is_cluster = worker.node_cfg.get("cluster_rep", False) if worker else False
            for node in data["nodes"]:
                node["host_name"] = data["host"]
                node["_is_cluster"] = is_cluster
                self.all_nodes.append(node)
            for vm in data["vms"]:
                vm["host_name"] = data["host"]
                # Дедупликация: если VM с таким (host_name, vmid) уже есть — заменяем
                vm_key = (data["host"], vm.get("vmid", 0))
                idx = next((i for i, v in enumerate(self.all_vms)
                            if (v.get("host_name"), v.get("vmid")) == vm_key), None)
                if idx is not None:
                    self.all_vms[idx] = vm
                else:
                    self.all_vms.append(vm)
            for st in data.get("storages", []):
                st["host_name"] = data["host"]
                key = (st.get("storage"), st.get("node"), data["host"])
                if key not in self._seen_storage_keys:
                    self._seen_storage_keys.add(key)
                    self.all_storages.append(st)
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
            host = data["host"]
            ha_list = data.get("ha_groups", [])
            if ha_list:
                self.all_ha_groups[host] = ha_list
        else:
            is_cluster_err = worker.node_cfg.get("cluster_rep", False) if worker else False
            self.all_nodes.append({
                "node": data["host"],
                "status": "error",
                "error": data["error"],
                "host_name": data["host"],
                "_display_name": data["host"],
                "_is_cluster": is_cluster_err
            })

        self._detect_status_changes()

        # Обновляем статус-бар сразу — частичные данные лучше, чем пустота
        self._update_status_bar()

        # Промежуточное обновление дерева — без очистки спиннеров.
        # Не загрузившиеся кластеры остаются в дереве как заглушки со спиннерами.
        self.tree_panel.update_data(self.all_nodes, self.all_vms, self.all_storages, final=False)
        self.detail_panel.set_lists(self.all_nodes, self.all_vms, self.all_storages)

        # Выбираем первый элемент в дереве при первой же возможности.
        if not getattr(self, '_first_selection_done', False) and self.tree_panel.tree.topLevelItemCount() > 0:
            self._do_first_selection()

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
            # Все данные загружены — финальная перестройка: спиннеры гаснут, VM/пулы в дереве
            self.tree_panel.update_data(self.all_nodes, self.all_vms, self.all_storages, final=True)
            self.last_refresh_ts = time.time()
            self._soft_refresh_start = time.time()
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
                vm_name = vm.get("name") or f"VM {vm['vmid']}"
                self._notifications.vm_status_changed(vm_name, vm.get("host_name", ""), old, status)
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
            else:
                return
        self._soft_refresh_running = True
        self._soft_refresh_active = True
        if not self._spin_timer.isActive():
            self._spin_timer.start()
        self._soft_refresh_start = now
        self.last_refresh_ts = now
        self._soft_gen += 1
        soft_gen = self._soft_gen

        self._soft_nodes.clear()
        self._soft_vms.clear()
        self._soft_storages.clear()
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
        if data["status"] == "ok":
            is_cluster = worker.node_cfg.get("cluster_rep", False) if worker else False
            for node in data["nodes"]:
                node["host_name"] = data["host"]
                node["_is_cluster"] = is_cluster
                self._soft_nodes.append(node)
            for vm in data["vms"]:
                vm["host_name"] = data["host"]
                self._soft_vms.append(vm)
            for st in data.get("storages", []):
                st["host_name"] = data["host"]
                self._soft_storages.append(st)
        else:
            self._soft_had_errors = True
            self._soft_nodes.append({
                "node": data["host"],
                "status": "error",
                "error": data["error"],
                "host_name": data["host"],
                "_display_name": data["host"]
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
                    self.detail_panel.all_nodes[:] = self._soft_nodes
                    self.detail_panel.all_vms[:] = self._soft_vms
                    self.detail_panel.all_storages[:] = self._soft_storages
                    self.detail_panel.refresh_current_view()
                    # Пробрасываем уже собранные на hard refresh пулы/HA/ISO —
                    # soft refresh не имеет ProxmoxAPI, пересобрать не может
                    self.detail_panel.all_pools = self.all_pools
                    self.detail_panel.all_ha_groups = self.all_ha_groups
                    self.detail_panel.all_iso_images = self.all_iso_images
                    self._detect_status_changes(self._soft_nodes, self._soft_vms)
                    self._update_status_bar()
                except Exception:
                    traceback.print_exc()
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
            self.tasks_widget.set_placeholder("Загрузка задач...")
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
                cfg = next((c for c in self.nodes_cfg if c.get("name") == host_name), None)
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
        # Запускаем в отдельном потоке, а не через QThreadPool — чтобы не блокировать
        # слот пула на время join() внутри ClusterTasksWorker.run()
        t = threading.Thread(target=worker.run, daemon=True)
        t.start()

    def _on_cluster_tasks_loaded(self, tasks, gen=None):
        if gen is None:
            logger.warning("_on_cluster_tasks_loaded вызван без gen — обрабатываем без защиты по поколению")
            self._update_cluster_tasks_widget(tasks)
            return
        if gen != self._tasks_gen:
            return
        self._update_cluster_tasks_widget(tasks)

    def _update_cluster_tasks_widget(self, tasks):
        self._cached_tasks = tasks
        save_tasks_cache(tasks)
        try:
            node_map = {}
            for n in self.all_nodes:
                node_map[n.get("node")] = n.get("_display_name") or n.get("node")
            vm_map = {}
            for vm in self.all_vms:
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
                geo = _json.loads(raw)
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
                val = _json.loads(raw)
                if isinstance(val, list):
                    self._saved_key = tuple(val)
                else:
                    self._saved_key = val
            except (TypeError, ValueError, _json.JSONDecodeError):
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
                vals = _json.loads(raw)
                if isinstance(vals, list):
                    self.h_splitter.setSizes([int(x) for x in vals])
            except (TypeError, ValueError):
                pass
        else:
            self.h_splitter.setSizes([360, 1140])
        raw = load_ui_state("splitter_v")
        if raw:
            try:
                vals = _json.loads(raw)
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
        vms_count = len(self.all_vms)
        self.status_label.setText(
            f"Хостов: {hosts_ok}/{hosts_total}  ВМ: {vms_count}  Обновлено: {now_str}"
        )

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
        while True:
            time.sleep(2)
            now = time.time()
            elapsed = now - self._last_heartbeat
            if elapsed > 3:
                print(f"\n=== FREEZE DETECTED: main thread unresponsive for {elapsed:.1f}s ===")
                for thread_id, frame in sys._current_frames().items():
                    name = ""
                    for t in threading.enumerate():
                        if t.ident == thread_id:
                            name = t.name
                            break
                    if "MainThread" in name or name == "":
                        import traceback
                        print(f"Thread [{thread_id}] ({name}):")
                        traceback.print_stack(frame)
                print("=== END FREEZE REPORT ===\n")

    # ------------------------------------------------------------
    # Закрытие приложения
    # ------------------------------------------------------------
    def closeEvent(self, event):
        self.refresh_timer.stop()
        self.tasks_timer.stop()
        self.tree_panel.save_state()
        # Сохраняем состояние окна
        geo = self.geometry()
        save_ui_state("window_geometry", _json.dumps([geo.x(), geo.y(), geo.width(), geo.height()]))
        save_ui_state("window_maximized", "1" if self.isMaximized() else "0")
        key = self.tree_panel.get_current_item_key()
        if key:
            save_ui_state("saved_key", _json.dumps(key))
        save_ui_state("saved_tab", str(self.detail_panel.tabs.currentIndex()))
        save_ui_state("saved_obj_type", str(self.detail_panel.current_obj_type or ""))
        save_ui_state("splitter_h", _json.dumps(self.h_splitter.sizes()))
        save_ui_state("splitter_v", _json.dumps(self.v_splitter.sizes()))
        super().closeEvent(event)
