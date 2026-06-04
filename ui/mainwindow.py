import time
import threading
import traceback
from PySide6.QtWidgets import (QMainWindow, QSplitter, QPushButton,
                               QHBoxLayout, QVBoxLayout, QWidget,
                               QMessageBox, QLabel)
from PySide6.QtCore import Qt, Slot, QTimer

from ..backend import FetchWorker, ClusterTasksWorker
from ..config import save_config, cache_password
from .notification import NotificationManager
from .tree_panel import TreePanel
from .detail_panel import DetailPanel
from .widgets.cluster_tasks_widget import ClusterTasksWidget
from .icons import get_icon

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

        self.setStyleSheet("""
            QTreeWidget {
                font-size: 13px;
                alternate-background-color: #f3f4f6;
                border: none;
                outline: none;
            }
            QTreeWidget::item {
                padding: 1px 4px;
                min-height: 20px;
            }
            QTreeView::branch {
                background: transparent;
            }
            QTableWidget {
                font-size: 12px;
                alternate-background-color: #f3f4f6;
                gridline-color: transparent;
            }
            QTableWidget::item {
                padding: 1px 4px;
            }
            QHeaderView::section {
                font-weight: 600;
                padding: 3px 4px;
                background-color: transparent;
                border: none;
                border-right: none;
                border-bottom: 1px solid #d1d5db;
                font-size: 13px;
            }
            QTableCornerButton::section {
                background: transparent;
                border: none;
                border-bottom: 1px solid #d1d5db;
            }
            QTabWidget::pane {
                border-top: 1px solid #d1d5db;
            }
            QTabBar {
                margin-left: 4px;
            }
            QTabBar::tab {
                padding: 4px 10px;
                font-size: 12px;
            }
            QProgressBar {
                border: 1px solid #d1d5db;
                border-radius: 3px;
                text-align: center;
                height: 16px;
                background: #f3f4f6;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background-color: #6b7280;
                border-radius: 2px;
            }
            QPushButton {
                padding: 4px 14px;
                font-size: 12px;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                background: #f9fafb;
            }
            QPushButton:hover {
                background: #e5e7eb;
            }
            QPushButton:pressed {
                background: #d1d5db;
            }
            QPushButton:disabled {
                color: #9ca3af;
                background: #f3f4f6;
            }
            QPushButton#refreshBtn {
                background: transparent;
                border: none;
                padding: 2px;
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
            }
            QPushButton#refreshBtn:hover {
                background: #e5e7eb;
                border-radius: 3px;
            }
            QPushButton#refreshBtn:pressed {
                background: #d1d5db;
                border-radius: 3px;
            }
            QSplitter::handle {
                width: 6px;
                background: #d1d5db;
                margin: 0 1px;
            }
            QSplitter::handle:hover {
                background: #9ca3af;
            }
        """)

        self.nodes_cfg = nodes_cfg or []
        self.all_nodes = []
        self.all_vms = []
        self.all_storages = []

        self._seen_storage_keys = set()
        self._first_data_ready = False
        self._last_host_statuses = {}
        self._last_vm_statuses = {}

        self.tree_panel = TreePanel(self.nodes_cfg)
        self.detail_panel = DetailPanel(self.nodes_cfg)

        self.tree_panel.item_selected.connect(self.detail_panel.show_details)

        self.tree_panel.add_server_requested.connect(self._on_add_server)

        self._notifications = NotificationManager(self)

        # Горизонтальный сплиттер (дерево + детали)
        h_splitter = QSplitter(Qt.Horizontal)
        h_splitter.addWidget(self.tree_panel)
        h_splitter.addWidget(self.detail_panel)
        h_splitter.setSizes([280, 1220])

        # Нижняя панель с задачами кластера
        self.tasks_widget = ClusterTasksWidget()
        self.tasks_widget.setMaximumHeight(150)

        # Вертикальный сплиттер
        v_splitter = QSplitter(Qt.Vertical)
        v_splitter.addWidget(h_splitter)
        v_splitter.addWidget(self.tasks_widget)
        v_splitter.setSizes([550, 150])

        self.refresh_btn = QPushButton()
        self.refresh_btn.setObjectName("refreshBtn")
        self.refresh_btn.setIcon(get_icon("refresh"))
        self.refresh_btn.setToolTip("Обновить")
        self.refresh_btn.clicked.connect(self.refresh_data)

        controls = QHBoxLayout()
        controls.addStretch()
        controls.addWidget(self.refresh_btn)

        main_layout = QVBoxLayout()
        main_layout.addLayout(controls)
        main_layout.addWidget(v_splitter)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.status_bar = self.statusBar()
        self.status_label = QLabel("")
        self.status_bar.addPermanentWidget(self.status_label)

        self._workers = set()

        # Переменные для мягкого обновления
        self.last_refresh_ts = 0
        self.refresh_interval = 5
        self._soft_refresh_running = False
        self._soft_refresh_start = 0
        self._soft_refresh_timeout = 30
        self._soft_gen = 0
        self._soft_nodes = []
        self._soft_vms = []
        self._soft_storages = []
        self._soft_had_errors = False

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
        self.tasks_timer.setInterval(30000)            # 30 секунд
        self.tasks_timer.timeout.connect(self.refresh_cluster_tasks)
        self.tasks_timer.start()

        # Первая загрузка задач
        QTimer.singleShot(1000, self.refresh_cluster_tasks)

    def _run_worker(self, worker):
        if len(self._workers) >= MAX_WORKERS:
            return
        self._workers.add(worker)
        cls_name = type(worker).__name__
        t = threading.Thread(target=worker.run, daemon=True, name=f"wkr-{cls_name}-{id(worker)}")
        t.start()

    # ------------------------------------------------------------
    # Добавление сервера
    # ------------------------------------------------------------
    def _on_add_server(self):
        from .add_server_dialog import AddServerDialog
        dialog = AddServerDialog(self)
        if dialog.exec() != AddServerDialog.Accepted:
            return
        cfg = dialog.get_config()
        self.nodes_cfg.append(cfg)
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

        # Сохраняем выделение и вкладку
        self._saved_key = self.tree_panel.get_current_item_key()
        self._saved_tab = self.detail_panel.tabs.currentIndex()
        self._saved_obj_type = self.detail_panel.current_obj_type

        self.refresh_btn.setEnabled(False)
        self.all_nodes.clear()
        self.all_vms.clear()
        self.all_storages.clear()
        self._seen_storage_keys.clear()
        self._first_selection_done = False

        self.tree_panel.start_loading()

        # Пул сам управляет потоками, просто запускаем задачи
        active_cfgs = [cfg for cfg in self.nodes_cfg if not cfg.get("skip", False)]
        self.progress.setMaximum(len(active_cfgs))
        self.progress.setValue(0)

        for cfg in active_cfgs:
            worker = FetchWorker(cfg)
            worker.signals.result_ready.connect(
                lambda data, w=worker: (self.on_worker_finished(data, w), self._workers.discard(w))
            )
            self._run_worker(worker)

    @Slot(dict)
    def on_worker_finished(self, data, worker=None):
        self._workers.discard(worker)
        if data["status"] == "ok":
            for node in data["nodes"]:
                node["host_name"] = data["host"]
                self.all_nodes.append(node)
            for vm in data["vms"]:
                vm["host_name"] = data["host"]
                self.all_vms.append(vm)
            for st in data.get("storages", []):
                st["host_name"] = data["host"]
                key = (st.get("storage"), st.get("node"))
                if key not in self._seen_storage_keys:
                    self._seen_storage_keys.add(key)
                    self.all_storages.append(st)
        else:
            self.all_nodes.append({
                "node": data["host"],
                "status": "error",
                "error": data["error"],
                "host_name": data["host"]
            })

        self.tree_panel.update_data(self.all_nodes, self.all_vms, self.all_storages)
        self.detail_panel.set_lists(self.all_nodes, self.all_vms, self.all_storages)
        self._detect_status_changes()

        fetch_workers = [w for w in self._workers if isinstance(w, FetchWorker)]
        if not fetch_workers:
            if not getattr(self, '_first_selection_done', False):
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
            self.refresh_btn.setEnabled(True)
            self.last_refresh_ts = time.time()
            self._soft_refresh_start = time.time()
            self._update_status_bar()

    def _detect_status_changes(self):
        for node in self.all_nodes:
            name = node.get("node", "")
            status = node.get("status", "unknown")
            old = self._last_host_statuses.get(name)
            if old is not None and old != status:
                display = node.get("_display_name") or name
                self._notifications.host_status_changed(display, old, status)
            self._last_host_statuses[name] = status

        for vm in self.all_vms:
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
                self._soft_counter = 0
                self._soft_nodes.clear()
                self._soft_vms.clear()
                self._soft_storages.clear()
            else:
                return
        self._soft_refresh_running = True
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
        for cfg in active_cfgs:
            worker = FetchWorker(cfg)
            worker.signals.result_ready.connect(
                lambda data, w=worker, g=soft_gen: (self.on_soft_refresh_result(data, w, g), self._workers.discard(w))
            )
            self._run_worker(worker)

    @Slot(dict)
    def on_soft_refresh_result(self, data, worker=None, gen=0):
        if gen != self._soft_gen:
            self._workers.discard(worker)
            return
        if data["status"] == "ok":
            for node in data["nodes"]:
                node["host_name"] = data["host"]
                self._soft_nodes.append(node)
            for vm in data["vms"]:
                vm["host_name"] = data["host"]
                self._soft_vms.append(vm)
        else:
            self._soft_had_errors = True

        self._soft_counter += 1
        active_count = len([cfg for cfg in self.nodes_cfg if not cfg.get("skip", False)])

        if self._soft_counter >= active_count:
            if self._soft_nodes or self._soft_vms:
                try:
                    self.tree_panel.update_node_statuses(self._soft_nodes, self._soft_vms)
                    self.detail_panel.all_nodes = list(self._soft_nodes)
                    self.detail_panel.all_vms = list(self._soft_vms)
                    self.detail_panel.refresh_current_view()
                    self._detect_status_changes()
                except Exception:
                    traceback.print_exc()
            self._soft_nodes.clear()
            self._soft_vms.clear()
            self._soft_counter = 0
            self._soft_refresh_running = False

    # ------------------------------------------------------------
    # Обновление задач кластера
    # ------------------------------------------------------------
    def refresh_cluster_tasks(self):
        cfg = next((c for c in self.nodes_cfg if c.get("cluster_rep")), None)
        if not cfg:
            cfg = self.nodes_cfg[0] if self.nodes_cfg else None
        if not cfg:
            print("[Tasks] Нет узлов")
            return
        worker = ClusterTasksWorker(cfg)
        worker.signals.tasks_ready.connect(lambda t, w=worker: (self._on_cluster_tasks_loaded(t), self._workers.discard(w)))
        worker.signals.tasks_error.connect(lambda err, w=worker: self._workers.discard(w))
        self._run_worker(worker)

    def _on_cluster_tasks_loaded(self, tasks):
        try:
            self.tasks_widget.set_tasks(tasks)
        except Exception as e:
            print(f"[Tasks] Ошибка при установке задач: {e}")

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

    # ------------------------------------------------------------
    # Детектор зависания
    # ------------------------------------------------------------
    def _heartbeat(self):
        self._last_heartbeat = time.time()

    def _detect_freeze(self):
        import sys
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
        super().closeEvent(event)
