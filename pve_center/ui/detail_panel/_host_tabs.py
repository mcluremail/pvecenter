from datetime import datetime

from PySide6.QtWidgets import (QTableWidgetItem, QProgressBar, QScrollArea, QWidget,
                               QVBoxLayout, QStackedWidget, QLabel, QHeaderView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush

from ..i18n import tr
from ..utils import status_text, format_uptime as _format_uptime
from ._constants import _progress_style, TabIndex
from ._table_utils import make_table, compact_table, set_cell_text, update_progress_bar

_LOADING_STYLE = "color: #9ca3af; font-size: 14px;"


def _loading_label():
    lbl = QLabel(tr("Loading..."))
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(_LOADING_STYLE)
    return lbl


class HostTabs:
    def __init__(self, panel):
        self.panel = panel

    def build_host_vm_tab(self):
        table = make_table(
            [tr("Name"), tr("Type"), tr("Node"), tr("Status"), "CPU %"],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 50),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 70),
             (QHeaderView.Interactive, 55)],
        )
        self.panel.host_vm_table = table
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(table)
        tab.setWidget(container)
        return tab

    def build_host_storage_tab(self):
        table = make_table(
            [tr("Name"), tr("Type"), tr("Content"), tr("Used"), tr("Total"), tr("Usage")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 65),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 70),
             (QHeaderView.Interactive, 70), (QHeaderView.Interactive, 95)],
        )
        self.panel.host_storage_table = table
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(table)
        return widget

    def build_network_tab(self):
        loading = _loading_label()
        table = make_table(
            [tr("Interface"), tr("Type"), tr("State"), "Method", "CIDR"],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 65),
             (QHeaderView.Interactive, 75), (QHeaderView.Interactive, 70),
             (QHeaderView.Stretch, None)],
        )
        stack = QStackedWidget()
        stack.addWidget(loading)
        stack.addWidget(table)
        stack.setCurrentIndex(0)
        self.panel.host_network_loading = loading
        self.panel.host_network_table = table
        self.panel.host_network_stack = stack
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(stack)
        tab.setWidget(container)
        return tab

    def build_services_tab(self):
        loading = _loading_label()
        table = make_table(
            [tr("Service"), tr("State"), tr("Description")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 75),
             (QHeaderView.Stretch, None)],
        )
        stack = QStackedWidget()
        stack.addWidget(loading)
        stack.addWidget(table)
        stack.setCurrentIndex(0)
        self.panel.host_services_loading = loading
        self.panel.host_services_table = table
        self.panel.host_services_stack = stack
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(stack)
        tab.setWidget(container)
        return tab

    def build_host_disks_tab(self):
        loading = _loading_label()
        table = make_table(
            [tr("Device"), tr("Type"), tr("Model"), tr("Size"), tr("Serial")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 65),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 70),
             (QHeaderView.Stretch, None)],
        )
        stack = QStackedWidget()
        stack.addWidget(loading)
        stack.addWidget(table)
        stack.setCurrentIndex(0)
        self.panel.host_disks_loading = loading
        self.panel.host_disks_table = table
        self.panel.host_disks_stack = stack
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(stack)
        tab.setWidget(container)
        return tab

    def build_snapshots_tab(self):
        loading = _loading_label()
        table = make_table(
            [tr("VM"), tr("Snapshot"), tr("Description"), tr("Created"), tr("Current")],
            [(QHeaderView.Stretch, None), (QHeaderView.Stretch, None),
             (QHeaderView.Stretch, None), (QHeaderView.Stretch, None),
             (QHeaderView.Interactive, 65)],
            sortable=True,
        )
        stack = QStackedWidget()
        stack.addWidget(loading)
        stack.addWidget(table)
        stack.setCurrentIndex(0)
        self.panel.host_snapshots_loading = loading
        self.panel.host_snapshots_table = table
        self.panel.host_snapshots_stack = stack
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(stack)
        tab.setWidget(container)
        return tab

    def build_summary_tab(self):
        from ._table_utils import make_table as _mt
        table = _mt(
            [tr("Host"), tr("Status"), tr("Address"), tr("CPU %"), tr("RAM (GiB)"), tr("Uptime")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 70),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 55),
             (QHeaderView.Interactive, 80), (QHeaderView.Interactive, 85)],
        )
        self.panel.datacenter_summary = table
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(table)
        tab.setWidget(container)
        return tab

    # --- Populate / fetch logic ---

    def populate_host_summary(self, hosts):
        panel = self.panel
        table = panel.datacenter_summary
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            tr("Host"), tr("Status"), tr("Address"), tr("CPU %"), tr("RAM (GiB)"), tr("Uptime")
        ])
        from PySide6.QtWidgets import QHeaderView
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
            cfg = panel._cfg_by_name.get(host_name)
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
        compact_table(table, 24)

    def show_cluster_folder(self, name):
        panel = self.panel
        panel.detail_label.setText(tr("Clusters"))
        panel.tabs.setTabVisible(TabIndex.MONITOR, False)
        panel.tabs.setTabVisible(TabIndex.HARDWARE, False)
        panel.tabs.setTabVisible(TabIndex.HOST_VMS, False)
        panel.tabs.setTabVisible(TabIndex.SUMMARY, True)
        panel.tabs.setCurrentIndex(TabIndex.SUMMARY)
        clusters = {}
        for node in panel.all_nodes:
            host_name = node.get("host_name", "")
            cfg = panel._cfg_by_name.get(host_name)
            cl = cfg.get("cluster") if cfg else None
            if cl and cl not in (False, None, "Standalone"):
                clusters.setdefault(cl, {"hosts": [], "nodes": set()})
                clusters[cl]["hosts"].append(node)
                clusters[cl]["nodes"].add(node.get("node"))
        for cl in clusters.values():
            cl["vms"] = [vm for vm in panel.all_vms if vm.get("node") in cl["nodes"]]
        table = panel.datacenter_summary
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([tr("Cluster"), tr("Hosts"), tr("VMs"), tr("CPU %"), tr("RAM (GiB)")])
        from PySide6.QtWidgets import QHeaderView
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

    def show_standalone_folder(self, name):
        panel = self.panel
        panel.detail_label.setText(tr("Standalone hosts"))
        panel.tabs.setTabVisible(TabIndex.MONITOR, False)
        panel.tabs.setTabVisible(TabIndex.HARDWARE, False)
        panel.tabs.setTabVisible(TabIndex.SUMMARY, True)
        panel.tabs.setCurrentIndex(TabIndex.SUMMARY)
        standalone = []
        for node in panel.all_nodes:
            host_name = node.get("host_name", "")
            cfg = panel._cfg_by_name.get(host_name)
            cl = cfg.get("cluster") if cfg else None
            if not cl or cl in (False, None, "Standalone"):
                standalone.append(node)
        self.populate_host_summary(standalone)

    def show_cluster(self, cluster_name):
        panel = self.panel
        panel.detail_label.setText(tr("Cluster: {name}").format(name=cluster_name))
        panel.tabs.setTabVisible(TabIndex.MONITOR, False)
        panel.tabs.setTabVisible(TabIndex.HARDWARE, False)
        panel.tabs.setTabVisible(TabIndex.HOST_VMS, False)
        panel.tabs.setTabVisible(TabIndex.SUMMARY, True)
        panel.tabs.setTabVisible(TabIndex.POOL_VMS, False)
        panel.tabs.setCurrentIndex(TabIndex.SUMMARY)
        hosts = []
        for node in panel.all_nodes:
            host_name = node.get("host_name", "")
            cfg = panel._cfg_by_name.get(host_name)
            if cfg and cfg.get("cluster") == cluster_name:
                hosts.append(node)
        self.populate_host_summary(hosts)

    def show_host_info(self, host_name, host_data):
        panel = self.panel
        node = next((n for n in panel.all_nodes if n.get("node") == host_name), None)
        display_name = node.get("_display_name") if node else host_name
        panel.detail_label.setText(tr("Host: {name}").format(name=display_name))

        if host_data and host_data.get("status") == "error":
            from ..utils import parse_pve_error
            err = host_data.get("error", "")
            reason = parse_pve_error(err)
            panel.info_label.setStyleSheet("font-size: 13px; color: #ef4444; padding: 40px 16px;")
            panel.info_label.setText(
                f"<div style='text-align: center;'>"
                f"<span style='font-size: 22px; font-weight: 700;'>" + tr("❌ {} is unavailable").format(display_name) + "</span>"
                f"<br><br>"
                f"<span style='font-size: 14px; color: #dc2626;'>{reason}</span>"
                f"</div>"
            )
            panel.info_stack.setCurrentIndex(0)
            panel.metrics_widget.setVisible(False)
            panel.metrics_widget.clear_curves()
            panel.tabs.setCurrentIndex(TabIndex.MONITOR)
            for t in range(panel.tabs.count()):
                panel.tabs.setTabVisible(t, t == TabIndex.MONITOR)
            return

        panel.metrics_widget.setVisible(True)
        panel.tabs.setTabVisible(TabIndex.MONITOR, True)
        panel.tabs.setTabVisible(TabIndex.HARDWARE, False)
        panel.tabs.setTabVisible(TabIndex.HOST_VMS, True)
        panel.tabs.setTabVisible(TabIndex.HOST_STORAGE, True)
        panel.tabs.setTabVisible(TabIndex.NETWORK, True)
        panel.tabs.setTabVisible(TabIndex.SERVICES, True)
        panel.tabs.setTabVisible(TabIndex.HOST_DISKS, True)
        panel.tabs.setTabVisible(TabIndex.SNAPSHOTS, True)
        panel.tabs.setCurrentIndex(TabIndex.MONITOR)

        panel.host_network_stack.setCurrentIndex(0)
        panel.host_network_stack.widget(0).setText(tr("Loading..."))
        panel.host_network_table.setRowCount(0)
        panel.host_services_stack.setCurrentIndex(0)
        panel.host_services_stack.widget(0).setText(tr("Loading..."))
        panel.host_services_table.setRowCount(0)
        panel.host_disks_stack.setCurrentIndex(0)
        panel.host_disks_stack.widget(0).setText(tr("Loading..."))
        panel.host_disks_table.setRowCount(0)
        panel.host_snapshots_stack.setCurrentIndex(0)
        panel.host_snapshots_stack.widget(0).setText(tr("Loading..."))
        panel.host_snapshots_table.setRowCount(0)

        if host_data and host_data.get("status") != "error":
            from ._constants import _fmt_pveversion
            host_cfg = panel._cfg_by_name.get(host_data.get("host_name", ""))
            address = host_cfg.get("host", "") if host_cfg else ""
            cpu_frac = host_data.get("cpu", 0)
            cpu_pct = round(cpu_frac * 100, 1) if isinstance(cpu_frac, float) else 0
            mem_bytes = host_data.get("mem", 0)
            mem_gb = round(mem_bytes / (1024**3), 2) if mem_bytes else 0
            maxmem_bytes = host_data.get("maxmem", 0)
            maxmem_gb = round(maxmem_bytes / (1024**3), 2) if maxmem_bytes else 0
            uptime = host_data.get("uptime", 0)

            table = panel.vm_summary_table
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
            compact_table(table, 22)
            panel.info_stack.setCurrentIndex(1)
        else:
            panel.info_label.setText(tr("No data"))
            panel.info_stack.setCurrentIndex(0)
            return

        vms_of_host = [vm for vm in panel.all_vms
                       if vm.get("node") == host_name
                       and vm.get("host_name") == (host_data.get("host_name") if host_data else host_name)]
        panel.host_vm_table.setSortingEnabled(False)
        panel.host_vm_table.setRowCount(len(vms_of_host))
        WARN_ROLE = Qt.UserRole + 10
        for i, vm in enumerate(vms_of_host):
            name_item = QTableWidgetItem(str(vm.get("name", "")))
            name_item.setData(Qt.UserRole + 30, vm.get("vmid"))
            panel.host_vm_table.setItem(i, 0, name_item)
            panel.host_vm_table.setItem(i, 1, QTableWidgetItem(str(vm.get("type", ""))))
            panel.host_vm_table.setItem(i, 2, QTableWidgetItem(str(vm.get("node", vm.get("host_name", "")))))
            vm_status = str(vm.get("status", ""))
            vm_status_item = QTableWidgetItem(status_text(vm_status))
            if vm_status == "running":
                vm_status_item.setForeground(QBrush(QColor("#22c55e")))
            elif vm_status == "stopped":
                vm_status_item.setForeground(QBrush(QColor("#ef4444")))
            else:
                vm_status_item.setForeground(QBrush(QColor("#f59e0b")))
            panel.host_vm_table.setItem(i, 3, vm_status_item)
            cpu_val = vm.get("cpu", 0)
            if isinstance(cpu_val, float):
                cpu = round(cpu_val * 100, 1)
            else:
                cpu = cpu_val
            panel.host_vm_table.setItem(i, 4, QTableWidgetItem(str(cpu)))
            warning = (isinstance(cpu_val, float) and cpu_val >= 0.9) or vm_status == "stopped"
            if warning:
                for c in range(5):
                    it = panel.host_vm_table.item(i, c)
                    if it:
                        it.setBackground(QColor("#fef3c7"))
                        it.setData(WARN_ROLE, True)
        compact_table(panel.host_vm_table)
        panel.host_vm_table.setSortingEnabled(True)

        host_storages = [s for s in panel.all_storages
                         if s.get("node") == host_name
                         and s.get("host_name") == (host_data.get("host_name") if host_data else host_name)]
        self.populate_host_storage_table(host_storages)

        self.fetch_host_network(host_name, host_data)
        self.fetch_host_services(host_name, host_data)
        self.fetch_host_disks(host_name, host_data)
        self.fetch_host_snapshots(host_name, host_data)
        self.fetch_host_metrics(host_data)

    def populate_host_storage_table(self, storages):
        panel = self.panel
        table = panel.host_storage_table
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

    def update_host_cells(self, host_data):
        panel = self.panel
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

            panel._update_vm_summary_cell(tr("Status"), status_text(status),
                "#22c55e" if status == "online" else "#ef4444" if status == "offline" else "#f59e0b")
            panel._update_vm_summary_cell(tr("CPU"), f"{cpu_pct}%")
            panel._update_vm_summary_cell(tr("RAM (GiB)"), f"{mem_gb} / {maxmem_gb}")
            panel._update_vm_summary_cell(tr("Uptime"), _format_uptime(uptime))

        WARN_ROLE = Qt.UserRole + 10
        vmid_role = Qt.UserRole + 30
        vms_of_host = [vm for vm in panel.all_vms
                       if vm.get("node") == host_name
                       and vm.get("host_name") == host_cfg_name]
        fresh_by_vmid = {vm.get("vmid"): vm for vm in vms_of_host}

        table = panel.host_vm_table
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
            set_cell_text(table, r, 1, str(new_vm.get("type", "")))
            set_cell_text(table, r, 2, str(new_vm.get("node", new_vm.get("host_name", ""))))

            vm_status = str(new_vm.get("status", ""))
            status_color = "#22c55e" if vm_status == "running" else "#ef4444" if vm_status == "stopped" else "#f59e0b"
            set_cell_text(table, r, 3, vm_status, status_color)

            cpu_val = new_vm.get("cpu", 0)
            if isinstance(cpu_val, float):
                cpu_str = str(round(cpu_val * 100, 1))
            else:
                cpu_str = str(cpu_val)
            set_cell_text(table, r, 4, cpu_str)

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

    def update_cluster_summary_cells(self, hosts):
        panel = self.panel
        table = panel.datacenter_summary
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
            set_cell_text(table, r, 1, f"● {status}", status_color)

            cpu_frac = node.get("cpu", 0)
            cpu_pct = round(cpu_frac * 100, 1) if isinstance(cpu_frac, float) else 0
            old_bar = table.cellWidget(r, 3)
            if isinstance(old_bar, QProgressBar):
                update_progress_bar(old_bar, int(cpu_pct), f"{cpu_pct}%")

            mem_bytes = node.get("mem", 0)
            maxmem_bytes = node.get("maxmem", 1) or 1
            mem_gb = round(mem_bytes / (1024**3), 2) if mem_bytes else 0
            maxmem_gb = round(maxmem_bytes / (1024**3), 2)
            mem_pct = int((mem_bytes / maxmem_bytes) * 100) if maxmem_bytes else 0
            old_ram = table.cellWidget(r, 4)
            if isinstance(old_ram, QProgressBar):
                update_progress_bar(old_ram, mem_pct, f"{mem_gb}/{maxmem_gb} GiB")

            uptime_sec = node.get("uptime", 0)
            uptime_str = _format_uptime(uptime_sec) if uptime_sec else ''
            set_cell_text(table, r, 5, uptime_str)

    def fetch_host_network(self, host_name, host_data):
        panel = self.panel
        node_name = host_data.get("node", "")
        host_cfg_name = host_data.get("host_name", "")
        cfg = panel._cfg_by_name.get(host_cfg_name)
        if not cfg:
            panel.host_network_stack.widget(0).setText(tr("No data"))
            panel.host_network_stack.setCurrentIndex(0)
            return
        from ..api.metrics import HostNetworkWorker
        worker = HostNetworkWorker(cfg, node_name)
        worker.signals.network_ready.connect(
            lambda nn, data, w=worker: (
                self.on_host_network(nn, data),
                panel._workers_mgr.discard_worker(w)
            )
        )
        worker.signals.network_error.connect(
            lambda nn, err, w=worker: (
                self.on_host_network(nn, []),
                panel._workers_mgr.discard_worker(w)
            )
        )
        panel._workers_mgr.run_worker(worker)

    def on_host_network(self, node_name, interfaces):
        panel = self.panel
        if panel.current_obj_type != "host" or panel.current_obj_name != node_name:
            return
        if interfaces:
            panel.host_network_stack.setCurrentIndex(1)
            self.populate_host_network_table(interfaces)
        else:
            panel.host_network_stack.widget(0).setText(tr("No data"))
            panel.host_network_stack.setCurrentIndex(0)

    def populate_host_network_table(self, interfaces):
        table = self.panel.host_network_table
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

    def fetch_host_services(self, host_name, host_data):
        panel = self.panel
        node_name = host_data.get("node", "")
        host_cfg_name = host_data.get("host_name", "")
        cfg = panel._cfg_by_name.get(host_cfg_name)
        if not cfg:
            panel.host_services_stack.widget(0).setText(tr("No data"))
            panel.host_services_stack.setCurrentIndex(0)
            return
        from ..api.metrics import HostServicesWorker
        worker = HostServicesWorker(cfg, node_name)
        worker.signals.services_ready.connect(
            lambda nn, data, w=worker: (
                self.on_host_services(nn, data),
                panel._workers_mgr.discard_worker(w)
            )
        )
        worker.signals.services_error.connect(
            lambda nn, err, w=worker: (
                self.on_host_services(nn, []),
                panel._workers_mgr.discard_worker(w)
            )
        )
        panel._workers_mgr.run_worker(worker)

    def on_host_services(self, node_name, services):
        panel = self.panel
        if panel.current_obj_type != "host" or panel.current_obj_name != node_name:
            return
        if services:
            panel.host_services_stack.setCurrentIndex(1)
            self.populate_host_services_table(services)
        else:
            panel.host_services_stack.widget(0).setText(tr("No data"))
            panel.host_services_stack.setCurrentIndex(0)

    def populate_host_services_table(self, services):
        table = self.panel.host_services_table
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

    def fetch_host_disks(self, host_name, host_data):
        panel = self.panel
        node_name = host_data.get("node", "")
        host_cfg_name = host_data.get("host_name", "")
        cfg = panel._cfg_by_name.get(host_cfg_name)
        if not cfg:
            panel.host_disks_stack.widget(0).setText(tr("No data"))
            panel.host_disks_stack.setCurrentIndex(0)
            return
        from ..api.metrics import HostDisksWorker
        worker = HostDisksWorker(cfg, node_name)
        worker.signals.disks_ready.connect(
            lambda nn, data, w=worker: (
                self.on_host_disks(nn, data),
                panel._workers_mgr.discard_worker(w)
            )
        )
        worker.signals.disks_error.connect(
            lambda nn, err, w=worker: (
                self.on_host_disks(nn, []),
                panel._workers_mgr.discard_worker(w)
            )
        )
        panel._workers_mgr.run_worker(worker)

    def on_host_disks(self, node_name, disks):
        panel = self.panel
        if panel.current_obj_type != "host" or panel.current_obj_name != node_name:
            return
        if disks:
            panel.host_disks_stack.setCurrentIndex(1)
            self.populate_host_disks_table(disks)
        else:
            panel.host_disks_stack.widget(0).setText(tr("No data"))
            panel.host_disks_stack.setCurrentIndex(0)

    def populate_host_disks_table(self, disks):
        from ._table_utils import format_volsize
        table = self.panel.host_disks_table
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
            table.setItem(i, 3, QTableWidgetItem(format_volsize(d.get("size", 0))))
            table.setItem(i, 4, QTableWidgetItem(d.get("wwn", "") or d.get("serial", "")))
        table.resizeRowsToContents()
        for r in range(table.rowCount()):
            if table.rowHeight(r) > 24:
                table.setRowHeight(r, 24)
        table.setSortingEnabled(True)

    def fetch_host_snapshots(self, host_name, host_data):
        panel = self.panel
        node_name = host_data.get("node", "")
        host_cfg_name = host_data.get("host_name", "")
        cfg = panel._cfg_by_name.get(host_cfg_name)
        if not cfg:
            panel.host_snapshots_stack.widget(0).setText(tr("No data"))
            panel.host_snapshots_stack.setCurrentIndex(0)
            return
        vms = [vm for vm in panel.all_vms if vm.get("node") == host_name and vm.get("host_name") == host_cfg_name]
        from ..api.metrics import HostSnapshotsWorker
        worker = HostSnapshotsWorker(cfg, node_name, vms)
        worker.signals.snapshots_ready.connect(
            lambda nn, data, w=worker: (
                self.on_host_snapshots(nn, data),
                panel._workers_mgr.discard_worker(w)
            )
        )
        worker.signals.snapshots_error.connect(
            lambda nn, err, w=worker: (
                self.on_host_snapshots(nn, []),
                panel._workers_mgr.discard_worker(w)
            )
        )
        panel._workers_mgr.run_worker(worker)

    def on_host_snapshots(self, node_name, snapshots):
        panel = self.panel
        if panel.current_obj_type != "host" or panel.current_obj_name != node_name:
            return
        if snapshots:
            panel.host_snapshots_stack.setCurrentIndex(1)
            self.populate_host_snapshots_table(snapshots)
        else:
            panel.host_snapshots_stack.widget(0).setText(tr("No snapshots"))
            panel.host_snapshots_stack.setCurrentIndex(0)

    def populate_host_snapshots_table(self, snapshots):
        table = self.panel.host_snapshots_table
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

    def fetch_host_metrics(self, host_data):
        panel = self.panel
        node_name = host_data.get("node", "")
        host_cfg_name = host_data.get("host_name", "")
        cfg = panel._cfg_by_name.get(host_cfg_name)
        panel.metrics_widget.show_disk_io(False)
        if not cfg:
            panel.metrics_widget.clear_curves()
            return
        timeframe = panel.metrics_widget.timeframe_combo.currentData()
        cache_key = ("host", node_name, timeframe)
        if cache_key in panel.metrics_cache:
            panel.metrics_widget.update_curves(panel.metrics_cache[cache_key])
            return
        from ..api.metrics import HostMetricsWorker
        worker = HostMetricsWorker(cfg, node_name, timeframe)
        worker.signals.data_fetched.connect(lambda tf, nn, md, g=panel._generation, w=worker: (self.on_host_metrics_fetched(tf, nn, md, g), panel._workers_mgr.discard_worker(w)))
        worker.signals.error_occurred.connect(lambda err, w=worker: panel._workers_mgr.discard_worker(w))
        panel._workers_mgr.run_worker(worker)

    def on_host_metrics_fetched(self, timeframe, node_name, metrics_dict, gen):
        panel = self.panel
        if gen != panel._generation:
            return
        cache_key = ("host", node_name, timeframe)
        panel.metrics_cache[cache_key] = metrics_dict
        panel.metrics_widget.update_curves(metrics_dict)