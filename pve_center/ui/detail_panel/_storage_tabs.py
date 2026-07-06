from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QScrollArea,
    QStackedWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..icons import get_icon
from ..theme import Color
from ._constants import _HAS_PG, TabIndex, _progress_style
from ._table_utils import (
    format_volsize,
    loading_label,
    make_filterable_table,
    make_table,
    safe_pct,
    set_cell_text,
    update_progress_bar,
)


class StorageTabs:
    def __init__(self, panel):
        self.panel = panel

    def build_storage_overview_tab(self):
        from ..widgets.card_list import CardList
        columns = {
            "key": "name",
            "title": "name",
            "fields": [
                ("type_text", 75),
                ("content_text", 225),
                ("location_text", 80),
                ("used_text", 100),
                ("total_text", 100),
                ("usage_text", 65),
            ],
        }
        self.panel.storage_list = CardList(columns)
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        tab.setWidget(self.panel.storage_list)
        return tab

    def build_storage_detail_tab(self):
        panel = self.panel
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        panel.storage_detail_name = QLabel()
        panel.storage_detail_name.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(panel.storage_detail_name)

        panel.storage_detail_params = make_table(
            [tr("Parameter"), tr("Value")],
            [(QHeaderView.Stretch, None), (QHeaderView.Stretch, None)],
        )
        layout.addWidget(panel.storage_detail_params)

        panel.storage_detail_bar = QProgressBar()
        panel.storage_detail_bar.setRange(0, 100)
        panel.storage_detail_bar.setTextVisible(True)
        panel.storage_detail_bar.setMinimumHeight(24)
        layout.addWidget(panel.storage_detail_bar)

        metrics_row = QHBoxLayout()
        metrics_row.addWidget(QLabel(tr("Fill level")))
        metrics_row.addStretch()
        panel.storage_detail_tf_combo = QComboBox()
        panel.storage_detail_tf_combo.addItem(tr("hour"), "hour")
        panel.storage_detail_tf_combo.addItem(tr("day"), "day")
        panel.storage_detail_tf_combo.addItem(tr("week"), "week")
        panel.storage_detail_tf_combo.addItem(tr("month"), "month")
        panel.storage_detail_tf_combo.addItem(tr("year"), "year")
        panel.storage_detail_tf_combo.setCurrentIndex(0)
        panel.storage_detail_tf_combo.currentIndexChanged.connect(
            panel._on_storage_timeframe_changed
        )
        metrics_row.addWidget(panel.storage_detail_tf_combo)
        layout.addLayout(metrics_row)

        panel.storage_detail_plot = QWidget()
        if _HAS_PG:
            import pyqtgraph as pg
            date_axis = pg.DateAxisItem(orientation='bottom')
            panel.storage_plot_widget = pg.PlotWidget(
                axisItems={'bottom': date_axis}, title=tr("Fill level")
            )
            panel.storage_plot_widget.setLabel('left', 'GiB')
            panel.storage_plot_widget.showGrid(x=False, y=True, alpha=0.3)
            panel.storage_plot_widget.enableAutoRange(axis='y')
            panel.storage_plot_widget.setMouseEnabled(x=False, y=False)
            panel.storage_plot_widget.setMinimumHeight(220)
            panel.storage_plot_curve = panel.storage_plot_widget.plot(
                [], [], pen=pg.mkPen(Color.STATUS_WARN, width=2),
                fillLevel=0, fillBrush=pg.mkBrush(Color.STATUS_WARN + "33")
            )
            sd_plot_layout = QVBoxLayout(panel.storage_detail_plot)
            sd_plot_layout.setContentsMargins(0, 0, 0, 0)
            sd_plot_layout.addWidget(panel.storage_plot_widget)
        else:
            sd_plot_layout = QVBoxLayout(panel.storage_detail_plot)
            sd_plot_layout.setContentsMargins(0, 0, 0, 0)
            sd_plot_layout.addWidget(QLabel(tr("PyQtGraph not installed")))
        layout.addWidget(panel.storage_detail_plot)

        panel.storage_detail_nodes_label = QLabel()
        panel.storage_detail_nodes_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(panel.storage_detail_nodes_label)

        panel.storage_detail_nodes_table = make_table(
            [tr("Node"), tr("Type"), tr("Content"), tr("Used"), tr("Total"), tr("Usage")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 65),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 100),
             (QHeaderView.Interactive, 100), (QHeaderView.Interactive, 95)],
            sortable=True,
        )
        layout.addWidget(panel.storage_detail_nodes_table)

        layout.addStretch()
        return widget

    def build_backups_tab(self):
        panel = self.panel
        table = make_table(
            [tr("VM"), tr("Type"), tr("Format"), tr("Size"), tr("Created")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 65),
             (QHeaderView.Interactive, 70), (QHeaderView.Interactive, 80),
             (QHeaderView.Stretch, None)],
            sortable=True,
        )
        panel.storage_backups_table = table
        stack = QStackedWidget()
        loading = loading_label()
        stack.addWidget(loading)
        stack.addWidget(make_filterable_table(table))
        stack.setCurrentIndex(0)
        panel.storage_backups_loading = loading
        panel.storage_backups_stack = stack
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(stack)
        tab.setWidget(container)
        return tab

    def build_disks_vm_tab(self):
        panel = self.panel
        table = make_table(
            [tr("VM"), tr("Name"), tr("Volume"), tr("Bus"), tr("Size")],
            [(QHeaderView.Stretch, None), (QHeaderView.Stretch, None),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 60),
             (QHeaderView.Interactive, 80)],
            sortable=True,
        )
        panel.storage_disks_table = table
        stack = QStackedWidget()
        loading = loading_label()
        stack.addWidget(loading)
        stack.addWidget(make_filterable_table(table))
        stack.setCurrentIndex(0)
        panel.storage_disks_loading = loading
        panel.storage_disks_stack = stack
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(stack)
        tab.setWidget(container)
        return tab

    def build_iso_tab(self):
        panel = self.panel
        table = make_table(
            [tr("Volume"), tr("Format"), tr("Size"), tr("Modified")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 70),
             (QHeaderView.Interactive, 80), (QHeaderView.Stretch, None)],
            sortable=True,
        )
        panel.storage_iso_table = table
        stack = QStackedWidget()
        loading = loading_label()
        stack.addWidget(loading)
        stack.addWidget(make_filterable_table(table))
        stack.setCurrentIndex(0)
        panel.storage_iso_loading = loading
        panel.storage_iso_stack = stack
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(stack)
        tab.setWidget(container)
        return tab

    def build_templates_tab(self):
        panel = self.panel
        table = make_table(
            [tr("Volume"), tr("Format"), tr("Size"), tr("Modified")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 70),
             (QHeaderView.Interactive, 80), (QHeaderView.Stretch, None)],
            sortable=True,
        )
        panel.storage_tpl_table = table
        stack = QStackedWidget()
        loading = loading_label()
        stack.addWidget(loading)
        stack.addWidget(make_filterable_table(table))
        stack.setCurrentIndex(0)
        panel.storage_tpl_loading = loading
        panel.storage_tpl_stack = stack
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(stack)
        tab.setWidget(container)
        return tab

    # --- Populate / fetch ---

    def populate_storage_table(self, storages):
        card_items = []
        for st in storages:
            name = st.get("storage", st.get("id", ""))
            content = st.get("content", "")
            if isinstance(content, list):
                content = ", ".join(content)
            cluster = st.get("cluster")
            location = cluster if cluster else st.get("node", st.get("host_name", ""))
            used = st.get("used", 0) or 0
            total = st.get("total", 0) or 0
            used_gb = round(used / (1024**3), 1) if used else 0
            total_gb = round(total / (1024**3), 1) if total else 0
            pct = safe_pct(used, total)
            card_items.append({
                "name": name,
                "type_text": st.get("type", ""),
                "content_text": content,
                "location_text": location,
                "used_text": f"{used_gb} GiB",
                "total_text": f"{total_gb} GiB",
                "usage_text": f"{pct}%",
            })
        self.panel.storage_list.set_items(card_items)

    def show_storage_folder(self):
        panel = self.panel
        panel.detail_label.setText(tr("Storage"))
        panel.detail_sublabel.setText("")
        panel.detail_sublabel.setVisible(False)
        panel.tabs.setTabVisible(TabIndex.MONITOR, False)
        panel.tabs.setTabVisible(TabIndex.HARDWARE, False)
        panel.tabs.setTabVisible(TabIndex.STORAGES, True)
        panel.tabs.setCurrentIndex(TabIndex.STORAGES)
        seen = set()
        deduped = []
        for st in panel.all_storages:
            cluster = st.get("cluster")
            if cluster:
                key = (st.get("storage"), cluster)
            else:
                key = (st.get("storage"), st.get("host_name"))
            if key not in seen:
                seen.add(key)
                deduped.append(st)
        self.populate_storage_table(deduped)

    def show_storage_detail(self, storage_name, data):
        panel = self.panel
        cluster = data.get("cluster")
        host_name_filter = data.get("host_name")
        if cluster:
            title = f"{storage_name} @ {cluster}"
        elif host_name_filter:
            title = f"{storage_name} ({host_name_filter})"
        else:
            title = storage_name
        panel.detail_label.setText(title)
        panel.detail_sublabel.setText("")
        panel.detail_sublabel.setVisible(False)
        panel.tabs.setTabVisible(TabIndex.MONITOR, False)
        panel.tabs.setTabVisible(TabIndex.HARDWARE, False)
        panel.tabs.setTabVisible(TabIndex.OPTIONS, False)
        panel.tabs.setTabVisible(TabIndex.HISTORY, False)
        panel.tabs.setTabVisible(TabIndex.HOST_VMS, False)
        panel.tabs.setTabVisible(TabIndex.POOL_VMS, False)
        panel.tabs.setTabVisible(TabIndex.SUMMARY, False)
        panel.tabs.setTabVisible(TabIndex.STORAGES, False)
        panel.tabs.setTabVisible(TabIndex.HOST_STORAGE, False)
        panel.tabs.setTabVisible(TabIndex.STORAGE_DETAIL, True)
        panel.tabs.setTabVisible(TabIndex.BACKUPS, False)
        panel.tabs.setTabVisible(TabIndex.DISKS_VM, False)
        panel.tabs.setTabVisible(TabIndex.ISO, False)
        panel.tabs.setTabVisible(TabIndex.TEMPLATES, False)
        panel.tabs.setCurrentIndex(TabIndex.STORAGE_DETAIL)
        panel.storage_detail_name.setText(title)
        if cluster:
            filtered = [s for s in panel.all_storages
                        if s.get("storage") == storage_name and s.get("cluster") == cluster]
        else:
            filtered = [s for s in panel.all_storages if s.get("storage") == storage_name]
        if not filtered:
            panel.storage_detail_params.setRowCount(0)
            panel.storage_detail_bar.setValue(0)
            panel.storage_detail_bar.setFormat(tr("No data"))
            panel.storage_detail_nodes_table.setRowCount(0)
            return
        rep = filtered[0]
        st_type = rep.get("type", "")
        content = rep.get("content", "")
        if isinstance(content, list):
            content = ", ".join(content)
        total_used = sum(s.get("used", 0) or 0 for s in filtered)
        total_total = sum(s.get("total", 0) or 0 for s in filtered)
        total_pct = safe_pct(total_used, total_total)
        used_gb = round(total_used / (1024**3), 1) if total_used else 0
        total_gb = round(total_total / (1024**3), 1) if total_total else 0
        params = [
            (tr("Type"), st_type),
            (tr("Content"), content),
            (tr("Used"), f"{used_gb} GiB"),
            (tr("Total"), f"{total_gb} GiB"),
            (tr("Usage"), f"{total_pct}%"),
            (tr("Nodes"), str(len(filtered))),
        ]
        panel.storage_detail_params.setRowCount(len(params))
        for i, (k, v) in enumerate(params):
            panel.storage_detail_params.setItem(i, 0, QTableWidgetItem(k))
            panel.storage_detail_params.setItem(i, 1, QTableWidgetItem(str(v)))
        panel.storage_detail_params.resizeRowsToContents()
        for r in range(panel.storage_detail_params.rowCount()):
            if panel.storage_detail_params.rowHeight(r) > 22:
                panel.storage_detail_params.setRowHeight(r, 22)
        panel.storage_detail_bar.setStyleSheet(_progress_style(total_pct))
        panel.storage_detail_bar.setValue(total_pct)
        panel.storage_detail_bar.setFormat(f"{total_pct}%  ({used_gb}/{total_gb} GiB)")
        panel.storage_detail_nodes_label.setText(tr("Per node:") if cluster else tr("Node:"))
        panel.storage_detail_nodes_table.setRowCount(len(filtered))
        for i, st in enumerate(filtered):
            node = st.get("node", "")
            panel.storage_detail_nodes_table.setItem(i, 0, QTableWidgetItem(node))
            panel.storage_detail_nodes_table.setItem(i, 1, QTableWidgetItem(st.get("type", "")))
            sc = st.get("content", "")
            if isinstance(sc, list):
                sc = ", ".join(sc)
            panel.storage_detail_nodes_table.setItem(i, 2, QTableWidgetItem(sc))
            used = st.get("used", 0) or 0
            total = st.get("total", 0) or 0
            u_gb = round(used / (1024**3), 1) if used else 0
            t_gb = round(total / (1024**3), 1) if total else 0
            pct = safe_pct(used, total)
            panel.storage_detail_nodes_table.setItem(i, 3, QTableWidgetItem(f"{u_gb} GiB"))
            panel.storage_detail_nodes_table.setItem(i, 4, QTableWidgetItem(f"{t_gb} GiB"))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(pct)
            bar.setStyleSheet(_progress_style(pct))
            bar.setFormat(f"{pct}%")
            panel.storage_detail_nodes_table.setCellWidget(i, 5, bar)
            bi = QTableWidgetItem("")
            bi.setFlags(Qt.ItemIsEnabled)
            panel.storage_detail_nodes_table.setItem(i, 5, bi)
        panel.storage_detail_nodes_table.resizeRowsToContents()
        for r in range(panel.storage_detail_nodes_table.rowCount()):
            if panel.storage_detail_nodes_table.rowHeight(r) > 24:
                panel.storage_detail_nodes_table.setRowHeight(r, 24)
        if _HAS_PG:
            panel.storage_plot_curve.setData([], [])
        self.fetch_storage_metrics(storage_name, filtered)
        self.load_storage_content(storage_name, filtered, rep)

    def load_storage_content(self, storage_name, filtered, rep):
        panel = self.panel
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
        panel.storage_backups_table.setRowCount(0)
        panel.storage_disks_table.setRowCount(0)
        panel.storage_iso_table.setRowCount(0)
        panel.storage_tpl_table.setRowCount(0)
        seen_tabs = set()
        for ct in allowed:
            info = tab_map.get(ct)
            if info:
                idx, title, headers = info
                seen_tabs.add(idx)
                panel.tabs.setTabVisible(idx, True)
                panel.tabs.setTabText(idx, title)
                table_map = {
                    10: panel.storage_backups_table,
                    11: panel.storage_disks_table,
                    12: panel.storage_iso_table,
                    13: panel.storage_tpl_table,
                }
                tbl = table_map.get(idx)
                if tbl:
                    tbl.setColumnCount(len(headers))
                    tbl.setHorizontalHeaderLabels(headers)
        loading_map = {
            10: panel.storage_backups_stack,
            11: panel.storage_disks_stack,
            12: panel.storage_iso_stack,
            13: panel.storage_tpl_stack,
        }
        for idx in seen_tabs:
            stack = loading_map.get(idx)
            if stack:
                stack.setCurrentIndex(0)
                stack.widget(0).setText(tr("Loading..."))
        node_entry = filtered[0]
        node_name = node_entry.get("node", "")
        host_name = node_entry.get("host_name", "")
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        panel._storage_content_pending = {}
        workers_launched = 0
        from ..api.metrics import StorageContentListWorker
        for ct in allowed:
            if ct == "backup":
                self.fetch_storage_backups_simple(storage_name, node_name, host_name, cfg)
                continue
            if ct in tab_map:
                worker = StorageContentListWorker(cfg, node_name, storage_name, ct)
                worker.signals.result.connect(
                    lambda sn, content_type, data, w=worker: (
                        self.on_storage_content_piece(sn, content_type, data),
                        panel._workers_mgr.discard_worker(w)
                    )
                )
                worker.signals.error.connect(
                    lambda sn, content_type, err, w=worker: (
                        self.on_storage_content_piece(sn, content_type, []),
                        panel._workers_mgr.discard_worker(w)
                    )
                )
                panel._workers_mgr.run_worker(worker)
                workers_launched += 1
        if workers_launched > 0:
            panel._storage_content_pending[storage_name] = {ct: None for ct in allowed if ct in tab_map and ct != "backup"}
        if "images" in allowed or "rootdir" in allowed:
            nodes_with_sto = set(s.get("node") for s in filtered)
            node_vms = [vm for vm in panel.all_vms if vm.get("node") in nodes_with_sto]
            self.fetch_storage_disks_simple(storage_name, node_name, host_name, cfg, node_vms)

    def on_storage_content_piece(self, storage_name, content_type, data):
        panel = self.panel
        if panel.current_obj_type != "storage" or panel.current_obj_name != storage_name:
            return
        pending = panel._storage_content_pending.get(storage_name)
        if pending:
            pending[content_type] = data
            if all(v is not None for v in pending.values()):
                del panel._storage_content_pending[storage_name]
                self.render_storage_content(storage_name, pending)

    def render_storage_content(self, storage_name, pending):
        panel = self.panel
        for ct, items in pending.items():
            if ct == "iso" and items:
                panel.storage_iso_stack.setCurrentIndex(1)
                self.populate_content_table(panel.storage_iso_table, items, "iso")
                panel._iso_volids = {v.get("volid", "") for v in items if v.get("volid")}
            elif ct == "iso":
                panel.storage_iso_stack.widget(0).setText(tr("No data"))
                panel.storage_iso_stack.setCurrentIndex(0)
                panel.storage_iso_table.setRowCount(0)
            elif ct in ("vztmpl", "snippets") and items:
                panel.storage_tpl_stack.setCurrentIndex(1)
                self.populate_content_table(panel.storage_tpl_table, items, "template")
            elif ct in ("vztmpl", "snippets"):
                panel.storage_tpl_stack.widget(0).setText(tr("No data"))
                panel.storage_tpl_stack.setCurrentIndex(0)
                panel.storage_tpl_table.setRowCount(0)

    def populate_content_table(self, table, items, icon_type=None):
        table.setRowCount(len(items))
        for i, vol in enumerate(items):
            volid_item = QTableWidgetItem(vol.get("volid", ""))
            if icon_type:
                volid_item.setIcon(get_icon(icon_type))
            table.setItem(i, 0, volid_item)
            table.setItem(i, 1, QTableWidgetItem(vol.get("format", "")))
            table.setItem(i, 2, QTableWidgetItem(format_volsize(vol.get("size", 0))))
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

    def on_storage_timeframe_changed(self, idx):
        panel = self.panel
        if panel.current_obj_type == "storage":
            storage_name = panel.current_obj_name
            data = panel.current_obj_data or {}
            cluster = data.get("cluster")
            host_name_filter = data.get("host_name")
            if cluster:
                filtered = [s for s in panel.all_storages
                            if s.get("storage") == storage_name and s.get("cluster") == cluster]
            elif host_name_filter:
                filtered = [s for s in panel.all_storages
                            if s.get("storage") == storage_name and s.get("host_name") == host_name_filter]
            else:
                filtered = [s for s in panel.all_storages if s.get("storage") == storage_name]
            if filtered:
                self.fetch_storage_metrics(storage_name, filtered)

    def fetch_storage_metrics(self, storage_name, filtered):
        panel = self.panel
        node_entry = filtered[0]
        node_name = node_entry.get("node", "")
        host_name = node_entry.get("host_name", "")
        cfg = panel._cfg_by_name.get(host_name)
        if not cfg:
            return
        timeframe = panel.storage_detail_tf_combo.currentData()
        if _HAS_PG:
            panel.storage_plot_curve.setData([], [])
        from ..api.metrics import StorageMetricsWorker
        worker = StorageMetricsWorker(cfg, node_name, storage_name, timeframe)
        worker.signals.data_fetched.connect(
            lambda tf, nn, md, w=worker: (
                self.on_storage_metrics_fetched(tf, nn, md),
                panel._workers_mgr.discard_worker(w)
            )
        )
        worker.signals.error_occurred.connect(lambda err, w=worker: panel._workers_mgr.discard_worker(w))
        panel._workers_mgr.run_worker(worker)

    def on_storage_metrics_fetched(self, timeframe, node_name, metrics_dict):
        panel = self.panel
        if panel.current_obj_type != "storage":
            return
        if not _HAS_PG or not metrics_dict.get("usage"):
            return
        times = [pt["time"] for pt in metrics_dict["usage"]]
        values = [pt["value"] / (1024**3) for pt in metrics_dict["usage"]]
        panel.storage_plot_curve.setData(times, values)

    def fetch_storage_backups_simple(self, storage_name, node_name, host_name, cfg):
        panel = self.panel
        from ..api.metrics import StorageBackupWorker
        worker = StorageBackupWorker(cfg, node_name, storage_name)
        worker.signals.backups_ready.connect(
            lambda sn, data, w=worker: (
                self.on_storage_backups(sn, data),
                panel._workers_mgr.discard_worker(w)
            )
        )
        worker.signals.backups_error.connect(
            lambda sn, err, w=worker: (
                self.on_storage_backups(sn, []),
                panel._workers_mgr.discard_worker(w)
            )
        )
        panel._workers_mgr.run_worker(worker)

    def on_storage_backups(self, storage_name, backups):
        panel = self.panel
        if panel.current_obj_type != "storage" or panel.current_obj_name != storage_name:
            return
        if backups:
            panel.storage_backups_stack.setCurrentIndex(1)
            self.populate_storage_backups_table(backups)
        else:
            panel.storage_backups_stack.widget(0).setText(tr("No data"))
            panel.storage_backups_stack.setCurrentIndex(0)
            panel.storage_backups_table.setRowCount(0)

    def populate_storage_backups_table(self, backups):
        table = self.panel.storage_backups_table
        table.setRowCount(len(backups))
        for i, b in enumerate(backups):
            vm_item = QTableWidgetItem(f"VM {b.get('vmid', '')}")
            vm_item.setIcon(get_icon("backup"))
            table.setItem(i, 0, vm_item)
            table.setItem(i, 1, QTableWidgetItem(b.get("subtype") or b.get("type", "")))
            table.setItem(i, 2, QTableWidgetItem(b.get("format", "")))
            size = b.get("size", 0) or 0
            table.setItem(i, 3, QTableWidgetItem(format_volsize(size) if size else "0"))
            ctime = b.get("ctime")
            if ctime:
                table.setItem(i, 4, QTableWidgetItem(datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M")))
            else:
                table.setItem(i, 4, QTableWidgetItem(""))
        table.resizeRowsToContents()
        for r in range(table.rowCount()):
            if table.rowHeight(r) > 24:
                table.setRowHeight(r, 24)

    def fetch_storage_disks_simple(self, storage_name, node_name, host_name, cfg, node_vms):
        panel = self.panel
        from ..api.metrics import StorageDisksWorker
        worker = StorageDisksWorker(cfg, node_name, storage_name, node_vms)
        worker.signals.disks_ready.connect(
            lambda sn, data, w=worker: (
                self.on_storage_disks(sn, data),
                panel._workers_mgr.discard_worker(w)
            )
        )
        worker.signals.disks_error.connect(
            lambda sn, err, w=worker: (
                self.on_storage_disks(sn, []),
                panel._workers_mgr.discard_worker(w)
            )
        )
        panel._workers_mgr.run_worker(worker)

    def on_storage_disks(self, storage_name, disks):
        panel = self.panel
        if panel.current_obj_type != "storage" or panel.current_obj_name != storage_name:
            return
        if disks:
            panel.storage_disks_stack.setCurrentIndex(1)
            self.populate_storage_disks_table(disks)
        else:
            panel.storage_disks_stack.widget(0).setText(tr("No data"))
            panel.storage_disks_stack.setCurrentIndex(0)
            panel.storage_disks_table.setRowCount(0)

    def populate_storage_disks_table(self, disks):
        table = self.panel.storage_disks_table
        table.setRowCount(len(disks))
        for i, d in enumerate(disks):
            vmid_item = QTableWidgetItem(str(d.get("vmid", "")))
            vmid_item.setIcon(get_icon("disk"))
            table.setItem(i, 0, vmid_item)
            table.setItem(i, 1, QTableWidgetItem(d.get("vm_name", "")))
            table.setItem(i, 2, QTableWidgetItem(d.get("volid", "")))
            table.setItem(i, 3, QTableWidgetItem(d.get("bus", "")))
            table.setItem(i, 4, QTableWidgetItem(format_volsize(d.get("size", 0))))
        table.resizeRowsToContents()
        for r in range(table.rowCount()):
            if table.rowHeight(r) > 24:
                table.setRowHeight(r, 24)

    def update_storage_cells(self):
        panel = self.panel
        storage_name = panel.current_obj_name
        data = panel.current_obj_data or {}
        cluster = data.get("cluster")
        host_name_filter = data.get("host_name")
        if cluster:
            filtered = [s for s in panel.all_storages
                        if s.get("storage") == storage_name and s.get("cluster") == cluster]
        elif host_name_filter:
            filtered = [s for s in panel.all_storages
                        if s.get("storage") == storage_name and s.get("host_name") == host_name_filter]
        else:
            filtered = [s for s in panel.all_storages if s.get("storage") == storage_name]
        if not filtered:
            return
        total_used = sum(s.get("used", 0) or 0 for s in filtered)
        total_total = sum(s.get("total", 0) or 0 for s in filtered)
        total_pct = safe_pct(total_used, total_total)
        used_gb = round(total_used / (1024**3), 1) if total_used else 0
        total_gb = round(total_total / (1024**3), 1) if total_total else 0

        panel._set_storage_param(tr("Used"), f"{used_gb} GiB")
        panel._set_storage_param(tr("Total"), f"{total_gb} GiB")
        panel._set_storage_param(tr("Usage"), f"{total_pct}%")
        panel.storage_detail_bar.setStyleSheet(_progress_style(total_pct))
        panel.storage_detail_bar.setValue(total_pct)
        panel.storage_detail_bar.setFormat(f"{total_pct}%  ({used_gb}/{total_gb} GiB)")

        node_table = panel.storage_detail_nodes_table
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
            total = st.get("total", 0) or 0
            u_gb = round(used / (1024**3), 1) if used else 0
            t_gb = round(total / (1024**3), 1) if total else 0
            pct = safe_pct(used, total)
            set_cell_text(node_table, r, 3, f"{u_gb} GiB")
            set_cell_text(node_table, r, 4, f"{t_gb} GiB")
            old_bar = node_table.cellWidget(r, 5)
            if isinstance(old_bar, QProgressBar):
                update_progress_bar(old_bar, pct, f"{pct}%")
