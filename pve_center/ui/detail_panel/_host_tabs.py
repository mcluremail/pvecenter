from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..icons import get_icon
from ..theme import Color
from ..utils import format_uptime as _format_uptime
from ..utils import status_text
from ._constants import TabIndex, _progress_style
from ._table_utils import (
    loading_label,
    make_table,
    safe_pct,
)


class HostTabs:
    def __init__(self, panel):
        self.panel = panel

    @staticmethod
    def _host_subtitle(host_data, host_name):
        parts = []
        if not host_data:
            return parts
        status = host_data.get("status", "")
        parts.append(status_text(status))
        pve_ver = host_data.get("pveversion", "")
        if pve_ver:
            ver = pve_ver.split("/")[1] if "/" in pve_ver else pve_ver
            parts.append("pve " + ver.split("-")[0] if "-" in ver else "pve " + ver)
        uptime = host_data.get("uptime", 0)
        if uptime:
            parts.append(_format_uptime(uptime) + " " + tr("uptime"))
        return parts

    def build_host_vm_tab(self):
        from ..widgets.card_list import CardList
        columns = {
            "key": "vmid",
            "dot": "status",
            "title": "name",
            "fields": [
                ("status_text", 90),
                ("cpu_text", 55),
                ("ram_text", 125),
                ("disk_text", 115),
                ("uptime_text", 125),
            ],
        }
        self.panel.host_vm_list = CardList(columns)
        self.panel.host_vm_list.cardDoubleClicked.connect(self._on_vm_card_nav)
        from ..widgets.metric_card import MetricCard
        self.panel.vm_stats_widget = QWidget()
        stats_grid = QGridLayout(self.panel.vm_stats_widget)
        stats_grid.setContentsMargins(0, 0, 0, 0)
        stats_grid.setSpacing(8)
        self.panel.card_vm_total = MetricCard(tr("VMs"), "—")
        self.panel.card_vm_cpu = MetricCard(tr("CPU used"), "—", show_progress=True)
        self.panel.card_vm_ram = MetricCard(tr("RAM used"), "—", show_progress=True)
        stats_grid.addWidget(self.panel.card_vm_total, 0, 0)
        stats_grid.addWidget(self.panel.card_vm_cpu, 0, 1)
        stats_grid.addWidget(self.panel.card_vm_ram, 0, 2)
        self.panel.vm_stats_widget.setVisible(False)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.panel.vm_stats_widget)
        layout.addWidget(self.panel.host_vm_list, 1)
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        tab.setWidget(container)
        return tab

    def build_host_storage_tab(self):
        table = make_table(
            [tr("Name"), tr("Type"), tr("Content"), tr("Used"), tr("Total"), tr("Usage")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 65),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 100),
             (QHeaderView.Interactive, 100), (QHeaderView.Interactive, 95)],
        )
        self.panel.host_storage_table = table
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(table)
        return widget

    def build_network_tab(self):
        loading = loading_label()
        table = make_table(
            [tr("Interface"), tr("Type"), tr("State"), tr("Method"), tr("CIDR")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 65),
             (QHeaderView.Interactive, 50), (QHeaderView.Interactive, 75),
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
        loading = loading_label()
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
        loading = loading_label()
        table = make_table(
            [tr("Device"), tr("Type"), tr("Model"), tr("Size"), tr("Serial")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 65),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 90),
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
        from PySide6.QtWidgets import QTreeWidget
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
        stack = QStackedWidget()
        stack.addWidget(loading)
        stack.addWidget(tree)
        stack.setCurrentIndex(0)
        self.panel.host_snapshots_loading = loading
        self.panel.host_snapshots_tree = tree
        self.panel.host_snapshots_stack = stack
        tree.itemDoubleClicked.connect(self._on_snap_tree_nav)
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(stack)
        tab.setWidget(container)
        return tab

    def build_health_tab(self):
        from ..widgets.card_list import CardList
        health_columns = {
            "key": "id",
            "dot": "severity",
            "title": "title",
            "fields": [
                ("message", 400),
            ],
        }
        self.panel.host_health_list = CardList(health_columns)
        loading = loading_label()
        stack = QStackedWidget()
        stack.addWidget(loading)
        stack.addWidget(self.panel.host_health_list)
        stack.setCurrentIndex(0)
        self.panel.host_health_loading = loading
        self.panel.host_health_stack = stack
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(stack)
        tab.setWidget(container)
        return tab

    def build_summary_tab(self):
        from ..widgets.card_list import CardList
        host_columns = {
            "key": "_key",
            "dot": "status",
            "title": "name",
            "title_width": 200,
            "header_labels": [
                (tr("Host"), 200),
                (tr("Status"), 80),
                (tr("Address"), 140),
                (tr("CPU"), 50),
                (tr("RAM"), 110),
                (tr("VMs"), 35),
                (tr("Uptime"), 90),
            ],
            "fields": [
                ("status_text", 80),
                ("address", 140),
                ("cpu_text", 50),
                ("ram_text", 110),
                ("vms_text", 35),
                ("uptime_text", 90),
            ],
        }
        self.panel.host_summary_list = CardList(host_columns, filterable=True)
        self.panel.host_summary_list.cardDoubleClicked.connect(self._on_host_card_nav)

        compare_columns = {
            "key": "_key",
            "dot": "status",
            "title": "name",
            "title_width": 140,
            "header_labels": [
                (tr("Node"), 140),
                (tr("Cluster"), 80),
                (tr("Status"), 70),
                (tr("CPU"), 50),
                (tr("RAM"), 95),
                (tr("Disk"), 90),
                (tr("VMs"), 35),
                (tr("Uptime"), 80),
            ],
            "fields": [
                ("cluster_text", 80),
                ("status_text", 70),
                ("cpu_text", 50),
                ("ram_text", 95),
                ("disk_text", 90),
                ("vms_text", 35),
                ("uptime_text", 80),
            ],
        }
        self.panel.node_compare_list = CardList(compare_columns, filterable=True)
        self.panel.node_compare_list.cardDoubleClicked.connect(self._on_host_card_nav)

        cluster_columns = {
            "key": "name",
            "title": "name",
            "title_width": 120,
            "header_labels": [
                (tr("Cluster"), 120),
                (tr("Hosts"), 70),
                (tr("VMs"), 70),
                (tr("CPU"), 55),
                (tr("RAM"), 125),
            ],
            "fields": [
                ("hosts_text", 70),
                ("vms_text", 70),
                ("cpu_text", 55),
                ("ram_text", 125),
            ],
        }
        self.panel.cluster_summary_list = CardList(cluster_columns)
        self.panel.cluster_summary_list.cardDoubleClicked.connect(self._on_cluster_card_nav)

        from PySide6.QtWidgets import QGridLayout, QScrollArea, QStackedWidget
        self.panel.summary_stack = QStackedWidget()
        self.panel.summary_stack.addWidget(self.panel.host_summary_list)
        self.panel.summary_stack.addWidget(self.panel.cluster_summary_list)
        self.panel.summary_stack.addWidget(self.panel.node_compare_list)

        self.panel.cluster_summary_cards = QWidget()
        cards_grid = QGridLayout(self.panel.cluster_summary_cards)
        cards_grid.setContentsMargins(0, 0, 0, 0)
        cards_grid.setSpacing(8)
        from ..widgets.metric_card import MetricCard
        self.panel.card_cluster_hosts = MetricCard(tr("Hosts"), "—")
        self.panel.card_cluster_vms = MetricCard(tr("VMs"), "—")
        self.panel.card_cluster_cpu = MetricCard(tr("CPU"), "—", show_progress=True)
        self.panel.card_cluster_ram = MetricCard(tr("RAM"), "—", show_progress=True)
        self.panel.card_cluster_disk = MetricCard(tr("Storage"), "—", show_progress=True)
        cards_grid.addWidget(self.panel.card_cluster_hosts, 0, 0)
        cards_grid.addWidget(self.panel.card_cluster_vms, 0, 1)
        cards_grid.addWidget(self.panel.card_cluster_cpu, 0, 2)
        cards_grid.addWidget(self.panel.card_cluster_ram, 1, 0)
        cards_grid.addWidget(self.panel.card_cluster_disk, 1, 1)
        self.panel.cluster_summary_cards.setVisible(False)

        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(8)
        cl.addWidget(self.panel.cluster_summary_cards)
        cl.addWidget(self.panel.summary_stack, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        return scroll

    def populate_host_summary(self, hosts):
        panel = self.panel
        panel.summary_stack.setCurrentIndex(0)
        card_items = []
        for node in hosts:
            node_name = node.get("_display_name") or node.get("node", "?")
            host_name = node.get("host_name", "")
            cfg = panel._cfg_by_name.get(host_name)
            if cfg and cfg.get("cluster_rep"):
                node_name = "★ " + node_name
            status = node.get("status", "unknown")
            cpu_frac = node.get("cpu", 0)
            cpu_pct = round(cpu_frac * 100, 1) if isinstance(cpu_frac, float) else 0
            mem_bytes = node.get("mem", 0)
            maxmem_bytes = node.get("maxmem", 0) or 0
            mem_gb = round(mem_bytes / (1024**3), 2) if mem_bytes else 0
            maxmem_gb = round(maxmem_bytes / (1024**3), 2) if maxmem_bytes else 0
            uptime_sec = node.get("uptime", 0)
            uptime_str = _format_uptime(uptime_sec) if uptime_sec else "—"
            vms_count = sum(
                1 for v in panel.all_vms
                if v.get("node") == node.get("node")
                and v.get("host_name") == host_name
            )
            card_items.append({
                "_key": f"{node.get('node', '')}@{host_name}",
                "node": node.get("node", ""),
                "name": node_name,
                "status": status,
                "status_text": status_text(status),
                "address": cfg.get("host", "") if cfg else "",
                "cpu_text": f"{cpu_pct}%",
                "ram_text": f"{mem_gb}/{maxmem_gb} GiB",
                "vms_text": str(vms_count),
                "uptime_text": uptime_str,
            })
        panel.host_summary_list.set_items(card_items)

    def _populate_vm_stats(self, vms):
        panel = self.panel
        total = len(vms)
        running = sum(1 for v in vms if v.get("status") == "running")
        stopped = total - running
        panel.card_vm_total.set_value(str(total))
        panel.card_vm_total.set_subtitle(f"{running} {tr('running')} · {stopped} {tr('stopped')}")
        running_vms = [v for v in vms if v.get("status") == "running"]
        cpu_sum = sum(v.get("cpu", 0) or 0 for v in running_vms)
        cpu_pct = round(cpu_sum * 100, 1) if cpu_sum else 0
        panel.card_vm_cpu.set_value(f"{cpu_pct}%")
        panel.card_vm_cpu.set_progress(min(cpu_pct, 100))
        mem_sum = sum(v.get("mem", 0) or 0 for v in vms)
        maxmem_sum = sum(v.get("maxmem", 0) or 0 for v in vms)
        mem_gb = round(mem_sum / (1024**3), 1) if mem_sum else 0
        maxmem_gb = round(maxmem_sum / (1024**3), 1) if maxmem_sum else 0
        panel.card_vm_ram.set_value(f"{mem_gb} / {maxmem_gb} {tr('GiB')}")
        panel.card_vm_ram.set_progress(safe_pct(mem_sum, maxmem_sum))
        panel.vm_stats_widget.setVisible(True)

    def _populate_cluster_summary_cards(self, hosts):
        panel = self.panel
        host_names = {h.get("host_name", "") for h in hosts}
        node_names = {h.get("node", "") for h in hosts}
        cluster_name = ""
        first_cfg = next((panel._cfg_by_name.get(h.get("host_name", "")) for h in hosts), None)
        if first_cfg:
            cluster_name = first_cfg.get("cluster", "")
        vms = [vm for vm in panel.all_vms
               if vm.get("node") in node_names
               and vm.get("host_name") in host_names]
        vms_running = sum(1 for v in vms if v.get("status") == "running")
        vms_stopped = len(vms) - vms_running
        panel.card_cluster_hosts.set_value(f"{len(hosts)}")
        running_hosts = sum(1 for h in hosts if h.get("status") == "online")
        panel.card_cluster_hosts.set_subtitle(f"{running_hosts} {tr('online')}")
        panel.card_cluster_vms.set_value(f"{vms_running}/{len(vms)}")
        panel.card_cluster_vms.set_subtitle(f"{vms_stopped} {tr('stopped')}")
        total_cpu = sum(h.get("cpu", 0) or 0 for h in hosts if h.get("status") == "online")
        online_hosts = [h for h in hosts if h.get("status") == "online"]
        n_online = len(online_hosts) or 1
        avg_cpu_pct = round((total_cpu / n_online) * 100, 1)
        panel.card_cluster_cpu.set_value(f"{avg_cpu_pct}%")
        panel.card_cluster_cpu.set_progress(avg_cpu_pct)
        total_mem = sum(h.get("mem", 0) or 0 for h in online_hosts)
        total_maxmem = sum(h.get("maxmem", 0) or 0 for h in online_hosts)
        mem_gb = round(total_mem / (1024**3), 1) if total_mem else 0
        maxmem_gb = round(total_maxmem / (1024**3), 1) if total_maxmem else 0
        panel.card_cluster_ram.set_value(f"{mem_gb} / {maxmem_gb} {tr('GiB')}")
        ram_pct = safe_pct(total_mem, total_maxmem)
        panel.card_cluster_ram.set_progress(ram_pct)
        if cluster_name:
            cluster_storages = [s for s in panel.all_storages if s.get("cluster") == cluster_name]
        else:
            cluster_storages = [s for s in panel.all_storages
                                if s.get("node") in node_names]
        total_used = sum(s.get("used", 0) or 0 for s in cluster_storages)
        total_total = sum(s.get("total", 0) or 0 for s in cluster_storages)
        used_gb = round(total_used / (1024**3), 1) if total_used else 0
        total_gb = round(total_total / (1024**3), 1) if total_total else 0
        panel.card_cluster_disk.set_value(f"{used_gb} / {total_gb} {tr('GiB')}")
        disk_pct = safe_pct(total_used, total_total)
        panel.card_cluster_disk.set_progress(disk_pct)
        panel.cluster_summary_cards.setVisible(True)

    def show_cluster_folder(self, name):
        panel = self.panel
        panel.detail_label.setText(tr("All clusters"))
        panel.detail_sublabel.setText("")
        panel.detail_sublabel.setVisible(False)
        panel.cluster_summary_cards.setVisible(False)
        panel._cluster_view_toggle.setVisible(True)
        panel.tabs.setTabVisible(TabIndex.MONITOR, False)
        panel.tabs.setTabVisible(TabIndex.HARDWARE, False)
        panel.tabs.setTabVisible(TabIndex.HOST_VMS, False)
        panel.tabs.setTabVisible(TabIndex.SUMMARY, True)
        panel.tabs.setCurrentIndex(TabIndex.SUMMARY)
        self._populate_cluster_summary()
        self._populate_node_compare()
        if not hasattr(panel, '_cluster_view_mode'):
            panel._cluster_view_mode = 'compare'
        from PySide6.QtCore import QTimer
        if panel._cluster_view_mode == 'clusters':
            panel.summary_stack.setCurrentIndex(1)
            panel._btn_clusters.setChecked(True)
            panel._btn_nodes.setChecked(False)
        else:
            panel.summary_stack.setCurrentIndex(2)
            panel._btn_clusters.setChecked(False)
            panel._btn_nodes.setChecked(True)
        QTimer.singleShot(0, lambda: panel.summary_stack.updateGeometry())

    def _populate_cluster_summary(self):
        panel = self.panel
        clusters = {}
        for node in panel.all_nodes:
            host_name = node.get("host_name", "")
            cfg = panel._cfg_by_name.get(host_name)
            cl = cfg.get("cluster") if cfg else None
            if cl and cl not in (False, None, "Standalone"):
                clusters.setdefault(cl, {"hosts": [], "host_names": set(), "nodes": set()})
                clusters[cl]["hosts"].append(node)
                clusters[cl]["host_names"].add(host_name)
                clusters[cl]["nodes"].add(node.get("node"))
        for cl in clusters.values():
            cl["vms"] = [vm for vm in panel.all_vms
                         if vm.get("host_name") in cl["host_names"]]
        cluster_items = []
        for cl_name, cl_data in sorted(clusters.items(), key=lambda x: x[0].lower()):
            hosts_ok = sum(1 for h in cl_data["hosts"] if h.get("status") == "online")
            vms_ok = sum(1 for v in cl_data["vms"] if v.get("status") == "running")
            cpu_vals = [h.get("cpu", 0) for h in cl_data["hosts"] if isinstance(h.get("cpu"), float)]
            avg_cpu = round(sum(cpu_vals) / len(cpu_vals) * 100, 1) if cpu_vals else 0
            mem_total = sum(h.get("maxmem", 0) for h in cl_data["hosts"])
            mem_used = sum(h.get("mem", 0) for h in cl_data["hosts"])
            mem_total_gb = round(mem_total / (1024**3), 1)
            mem_used_gb = round(mem_used / (1024**3), 1)
            cluster_items.append({
                "name": cl_name,
                "hosts_text": f"{hosts_ok}/{len(cl_data['hosts'])}",
                "vms_text": f"{vms_ok}/{len(cl_data['vms'])}",
                "cpu_text": f"{avg_cpu}%",
                "ram_text": f"{mem_used_gb}/{mem_total_gb} GiB",
            })
        panel.cluster_summary_list.set_items(cluster_items)

    def _populate_node_compare(self):
        panel = self.panel
        card_items = []
        def _sort_key(n):
            host_name = n.get("host_name", "")
            cfg = panel._cfg_by_name.get(host_name)
            cl = cfg.get("cluster") if cfg else None
            is_standalone = not cl or cl in (False, None, "Standalone")
            return (1 if is_standalone else 0, cl or "", n.get("node", ""))
        # Only cluster nodes — standalone has its own folder
        cluster_nodes = []
        for node in panel.all_nodes:
            host_name = node.get("host_name", "")
            cfg = panel._cfg_by_name.get(host_name)
            cl = cfg.get("cluster") if cfg else None
            if cl and cl not in (False, None, "Standalone"):
                cluster_nodes.append(node)
        for node in sorted(cluster_nodes, key=_sort_key):
            node_name = node.get("_display_name") or node.get("node", "?")
            host_name = node.get("host_name", "")
            cfg = panel._cfg_by_name.get(host_name)
            cluster_name = cfg.get("cluster", "") if cfg else ""
            if cluster_name in (None, "Standalone"):
                cluster_name = tr("Standalone")
            status = node.get("status", "unknown")
            cpu_frac = node.get("cpu", 0)
            cpu_pct = round(cpu_frac * 100, 1) if isinstance(cpu_frac, float) else 0
            mem_bytes = node.get("mem", 0)
            maxmem_bytes = node.get("maxmem", 0) or 0
            mem_gb = round(mem_bytes / (1024**3), 2) if mem_bytes else 0
            maxmem_gb = round(maxmem_bytes / (1024**3), 2) if maxmem_bytes else 0
            mem_pct = round(mem_bytes / maxmem_bytes * 100, 1) if maxmem_bytes else 0
            maxdisk_bytes = node.get("maxdisk", 0) or 0
            disk_bytes = node.get("disk", 0) or 0
            disk_gb = round(disk_bytes / (1024**3), 1) if disk_bytes else 0
            maxdisk_gb = round(maxdisk_bytes / (1024**3), 1) if maxdisk_bytes else 0
            vms_count = sum(
                1 for v in panel.all_vms
                if v.get("node") == node.get("node")
                and v.get("host_name") == host_name
            )
            uptime_sec = node.get("uptime", 0)
            uptime_str = _format_uptime(uptime_sec) if uptime_sec else "—"
            pve_ver = node.get("pveversion", "")
            if pve_ver:
                pve_ver = pve_ver.split("/")[-1] if "/" in pve_ver else pve_ver
            card_items.append({
                "_key": f"{node.get('node', '')}@{host_name}",
                "node": node.get("node", ""),
                "name": node_name,
                "status": status,
                "cluster_text": cluster_name,
                "status_text": status_text(status),
                "cpu_text": f"{cpu_pct}%",
                "ram_text": f"{mem_gb}/{maxmem_gb} ({mem_pct}%)",
                "disk_text": f"{disk_gb}/{maxdisk_gb} GiB",
                "vms_text": str(vms_count),
                "uptime_text": uptime_str,
                "pve_text": pve_ver or "—",
            })
        panel.node_compare_list.set_items(card_items)

    def show_standalone_folder(self, name):
        panel = self.panel
        panel.detail_label.setText(tr("Standalone hosts"))
        panel.detail_sublabel.setText("")
        panel.detail_sublabel.setVisible(False)
        panel.cluster_summary_cards.setVisible(False)
        panel._cluster_view_toggle.setVisible(False)
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
        hosts = []
        cluster_cfg = None
        for node in panel.all_nodes:
            host_name = node.get("host_name", "")
            cfg = panel._cfg_by_name.get(host_name)
            if cfg and cfg.get("cluster") == cluster_name:
                hosts.append(node)
                if cfg.get("cluster_rep") or cluster_cfg is None:
                    cluster_cfg = cfg
        panel.detail_label.setText(cluster_name)
        hosts_count = len(hosts)
        running = sum(1 for h in hosts if h.get("status") == "online")
        panel.detail_sublabel.setText(f"{hosts_count} {tr('hosts')} · {running} {tr('online')}")
        panel.detail_sublabel.setVisible(True)
        panel._cluster_view_toggle.setVisible(False)
        panel.tabs.setTabVisible(TabIndex.MONITOR, False)
        panel.tabs.setTabVisible(TabIndex.HARDWARE, False)
        panel.tabs.setTabVisible(TabIndex.HOST_VMS, True)
        panel.tabs.setTabVisible(TabIndex.SUMMARY, True)
        panel.tabs.setTabVisible(TabIndex.STORAGES, True)
        panel.tabs.setTabVisible(TabIndex.SNAPSHOTS, True)
        panel.tabs.setTabVisible(TabIndex.HEALTH, True)
        panel.tabs.setTabVisible(TabIndex.BACKUP_JOBS, True)
        panel.tabs.setTabVisible(TabIndex.ACCESS, True)
        panel.tabs.setTabVisible(TabIndex.POOL_VMS, False)
        panel.tabs.setCurrentIndex(TabIndex.SUMMARY)
        self.populate_host_summary(hosts)
        self._populate_cluster_summary_cards(hosts)
        self._populate_cluster_vms(cluster_name, hosts)
        self._populate_cluster_storages(cluster_name)
        self._fetch_cluster_snapshots(hosts)
        self._fetch_cluster_health(hosts)
        self._fetch_backup_jobs(cluster_cfg, cluster_name)
        self._fetch_access_all(cluster_cfg)

    def show_host_info(self, host_name, host_data):
        panel = self.panel
        host_cfg_name = (host_data.get("host_name") if host_data else "") or host_name
        node = next((n for n in panel.all_nodes
                     if n.get("node") == host_name
                     and n.get("host_name") == host_cfg_name), None)
        if node is None:
            node = host_data if host_data else None
        display_name = node.get("_display_name") if node else host_name
        panel.detail_label.setText(display_name)
        panel.detail_sublabel.setText(" · ".join(self._host_subtitle(host_data, host_name)))
        panel.detail_sublabel.setVisible(True)
        panel._cluster_view_toggle.setVisible(False)
        panel.cluster_summary_cards.setVisible(False)

        if host_data and host_data.get("status") == "error":
            from ..utils import parse_pve_error
            err = host_data.get("error", "")
            reason = parse_pve_error(err)
            panel.info_label.setStyleSheet(f"font-size: 13px; color: {Color.STATUS_ERR}; padding: 40px 16px;")
            panel.info_label.setText(
                "<div style='text-align: center;'>"
                "<span style='font-size: 22px; font-weight: 700;'>" + tr("❌ {} is unavailable").format(display_name) + "</span>"
                f"<br><br>"
                f"<span style='font-size: 14px; color: {Color.DANGER};'>{reason}</span>"
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
        panel.tabs.setTabVisible(TabIndex.HEALTH, True)
        panel.tabs.setTabVisible(TabIndex.BACKUP_JOBS, True)
        panel.tabs.setTabVisible(TabIndex.ACCESS, True)
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
        panel.host_snapshots_tree.clear()
        panel.host_health_stack.setCurrentIndex(0)
        panel.host_health_loading.setText(tr("Loading..."))
        panel.host_health_list.set_items([])

        if host_data and host_data.get("status") != "error":
            from ._constants import _fmt_pveversion
            host_cfg = panel._cfg_by_name.get(host_data.get("host_name", ""))
            cpu_frac = host_data.get("cpu", 0)
            cpu_pct = round(cpu_frac * 100, 1) if isinstance(cpu_frac, float) else 0
            mem_bytes = host_data.get("mem", 0)
            maxmem_bytes = host_data.get("maxmem", 0)
            mem_gb = round(mem_bytes / (1024**3), 2) if mem_bytes else 0
            maxmem_gb = round(maxmem_bytes / (1024**3), 2) if maxmem_bytes else 0
            uptime = host_data.get("uptime", 0)
            status = host_data.get("status", "")
            status_color = Color.STATUS_OK if status == "online" else Color.STATUS_ERR if status == "offline" else Color.STATUS_WARN

            panel.card_status.set_title(tr("Status"))
            panel.card_status.set_value(status_text(status))
            panel.card_status.set_value_color(status_color)
            panel.card_status.set_subtitle(
                tr("PVE") + " " + _fmt_pveversion(host_data.get("pveversion", "?"))
            )

            panel.card_cpu.set_value(f"{cpu_pct}%")
            cpu_sockets = host_data.get("sockets", "")
            if cpu_sockets:
                panel.card_cpu.set_subtitle(f"{cpu_sockets} {tr('sockets')}")
            else:
                panel.card_cpu.set_subtitle("")
            panel.card_cpu.set_progress(cpu_pct)

            panel.card_ram.set_value(f"{mem_gb} / {maxmem_gb} {tr('GiB')}")
            ram_pct = safe_pct(mem_bytes, maxmem_bytes)
            panel.card_ram.set_progress(ram_pct)

            host_cfg_name = (host_data.get("host_name") if host_data else "") or host_name
            vms_count = sum(1 for v in panel.all_vms
                           if v.get("node") == host_name
                           and v.get("host_name") == host_cfg_name)
            vms_running = sum(1 for v in panel.all_vms
                              if v.get("node") == host_name
                              and v.get("host_name") == host_cfg_name
                              and v.get("status") == "running")
            panel.card_disk.set_title(tr("VMs"))
            panel.card_disk.set_value(f"{vms_running}/{vms_count}")
            panel.card_disk.set_subtitle(f"{vms_count - vms_running} {tr('stopped')}" if vms_count != vms_running else "")
            panel.card_disk.set_progress(0)

            panel.card_net.set_title(tr("Uptime"))
            panel.card_net.set_value(_format_uptime(uptime) if uptime else "—")
            panel.card_net.set_subtitle("")

            panel.card_uptime.set_title(tr("Address"))
            address = host_cfg.get("host", "") if host_cfg else ""
            panel.card_uptime.set_value(address)
            ssl_state = tr("trusted") if (host_cfg and host_cfg.get("trust_ssl", True)) else tr("untrusted")
            panel.card_uptime.set_subtitle(f"SSL {ssl_state}")

            panel.info_stack.setCurrentIndex(1)
        else:
            panel.info_label.setText(tr("No data"))
            panel.info_stack.setCurrentIndex(0)
            return

        host_cfg_name = (host_data.get("host_name") if host_data else "") or host_name
        vms_of_host = [vm for vm in panel.all_vms
                       if vm.get("node") == host_name
                       and vm.get("host_name") == host_cfg_name]
        card_items = []
        for vm in vms_of_host:
            vm_status = str(vm.get("status", ""))
            cpu_val = vm.get("cpu", 0)
            if isinstance(cpu_val, float):
                cpu_str = str(round(cpu_val * 100, 1))
            else:
                cpu_str = str(cpu_val)
            mem = vm.get("mem", 0) or 0
            maxmem = vm.get("maxmem", 0) or 0
            if maxmem:
                mem_pct = round(mem / maxmem * 100, 1)
                mem_gb = round(mem / (1024**3), 2)
                maxmem_gb = round(maxmem / (1024**3), 2)
                ram_str = f"{mem_gb}/{maxmem_gb} ({mem_pct}%)"
            else:
                ram_str = "—"
            disk = vm.get("disk", 0) or 0
            maxdisk = vm.get("maxdisk", 0) or 0
            vm_type = vm.get("type", "qemu")
            if maxdisk:
                maxdisk_gb = round(maxdisk / (1024**3), 2)
                if vm_type == "lxc" and disk:
                    disk_gb = round(disk / (1024**3), 2)
                    disk_str = f"{disk_gb}/{maxdisk_gb} GiB"
                else:
                    disk_str = f"{maxdisk_gb} GiB"
            else:
                disk_str = "—"
            uptime = vm.get("uptime", 0)
            uptime_str = _format_uptime(uptime) if uptime else "—"
            card_items.append({
                "vmid": vm.get("vmid"),
                "name": str(vm.get("name", "")),
                "status": vm_status,
                "status_text": status_text(vm_status),
                "cpu_text": cpu_str,
                "ram_text": ram_str,
                "disk_text": disk_str,
                "uptime_text": uptime_str,
                "host_name": host_cfg_name,
                "node": vm.get("node", host_name),
            })
        panel.host_vm_list.set_items(card_items)
        self._populate_vm_stats(vms_of_host)

        host_storages = [s for s in panel.all_storages
                         if s.get("node") == host_name
                         and s.get("host_name") == (host_data.get("host_name") if host_data else host_name)]
        self.populate_host_storage_table(host_storages)

        self.fetch_host_network(host_name, host_data)
        self.fetch_host_services(host_name, host_data)
        self.fetch_host_disks(host_name, host_data)
        self.fetch_host_snapshots(host_name, host_data)
        self.fetch_host_metrics(host_data)
        self.fetch_host_health(host_name, host_data)
        host_cfg = panel._cfg_by_name.get(host_data.get("host_name", "")) if host_data else None
        if host_cfg:
            is_cluster_host = bool(host_cfg.get("cluster"))
            if not is_cluster_host:
                panel._backup_jobs_host_cfg = host_data.get("host_name", "") if host_data else host_name
                self._fetch_backup_jobs(host_cfg, host_name)
            else:
                cluster_name = host_cfg.get("cluster", "")
                cluster_cfg = None
                for n in panel.all_nodes:
                    cn = panel._cfg_by_name.get(n.get("host_name", ""))
                    if cn and cn.get("cluster") == cluster_name:
                        cluster_cfg = cn
                        break
                if cluster_cfg:
                    self._fetch_backup_jobs(cluster_cfg, cluster_name)
            access_cfg = host_cfg
            if is_cluster_host:
                cluster_name = host_cfg.get("cluster", "")
                for n in panel.all_nodes:
                    cn = panel._cfg_by_name.get(n.get("host_name", ""))
                    if cn and cn.get("cluster") == cluster_name:
                        access_cfg = cn
                        break
            if access_cfg:
                self._fetch_access_all(access_cfg)

    def populate_host_storage_table(self, storages):
        panel = self.panel
        table = panel.host_storage_table
        table.setRowCount(len(storages))
        for i, st in enumerate(storages):
            name_item = QTableWidgetItem(st.get("storage", st.get("id", "")))
            name_item.setIcon(get_icon("storage"))
            table.setItem(i, 0, name_item)
            table.setItem(i, 1, QTableWidgetItem(st.get("type", "")))
            content = st.get("content", "")
            if isinstance(content, list):
                content = ", ".join(content)
            table.setItem(i, 2, QTableWidgetItem(content))
            used = st.get("used", 0) or 0
            total = st.get("total", 0) or 0
            used_gb = round(used / (1024**3), 1) if used else 0
            total_gb = round(total / (1024**3), 1) if total else 0
            pct = safe_pct(used, total)
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
            from ._constants import _fmt_pveversion
            host_cfg = panel._cfg_by_name.get(host_cfg_name)
            cpu_frac = host_data.get("cpu", 0)
            cpu_pct = round(cpu_frac * 100, 1) if isinstance(cpu_frac, float) else 0
            mem_bytes = host_data.get("mem", 0)
            maxmem_bytes = host_data.get("maxmem", 0)
            mem_gb = round(mem_bytes / (1024**3), 2) if mem_bytes else 0
            maxmem_gb = round(maxmem_bytes / (1024**3), 2) if maxmem_bytes else 0
            uptime = host_data.get("uptime", 0)
            status = host_data.get("status", "")
            status_color = Color.STATUS_OK if status == "online" else Color.STATUS_ERR if status == "offline" else Color.STATUS_WARN

            panel.card_status.set_value(status_text(status))
            panel.card_status.set_value_color(status_color)
            panel.card_status.set_subtitle(
                tr("PVE") + " " + _fmt_pveversion(host_data.get("pveversion", "?"))
            )

            panel.card_cpu.set_value(f"{cpu_pct}%")
            panel.card_cpu.set_progress(cpu_pct)

            panel.card_ram.set_value(f"{mem_gb} / {maxmem_gb} {tr('GiB')}")
            panel.card_ram.set_progress(safe_pct(mem_bytes, maxmem_bytes))

            vms_count = sum(1 for v in panel.all_vms
                           if v.get("node") == host_name
                           and v.get("host_name") == host_cfg_name)
            vms_running = sum(1 for v in panel.all_vms
                              if v.get("node") == host_name
                              and v.get("host_name") == host_cfg_name
                              and v.get("status") == "running")
            panel.card_disk.set_value(f"{vms_running}/{vms_count}")
            panel.card_disk.set_subtitle(f"{vms_count - vms_running} {tr('stopped')}" if vms_count != vms_running else "")

            panel.card_net.set_value(_format_uptime(uptime) if uptime else "—")

            address = host_cfg.get("host", "") if host_cfg else ""
            panel.card_uptime.set_value(address)
            ssl_state = tr("trusted") if (host_cfg and host_cfg.get("trust_ssl", True)) else tr("untrusted")
            panel.card_uptime.set_subtitle(f"SSL {ssl_state}")

            panel.info_stack.setCurrentIndex(1)

        vms_of_host = [vm for vm in panel.all_vms
                       if vm.get("node") == host_name
                       and vm.get("host_name") == host_cfg_name]
        card_updates = []
        for vm in vms_of_host:
            vm_status = str(vm.get("status", ""))
            cpu_val = vm.get("cpu", 0)
            if isinstance(cpu_val, float):
                cpu_str = str(round(cpu_val * 100, 1))
            else:
                cpu_str = str(cpu_val)
            mem = vm.get("mem", 0) or 0
            maxmem = vm.get("maxmem", 0) or 0
            if maxmem:
                mem_pct = round(mem / maxmem * 100, 1)
                mem_gb = round(mem / (1024**3), 2)
                maxmem_gb = round(maxmem / (1024**3), 2)
                ram_str = f"{mem_gb}/{maxmem_gb} ({mem_pct}%)"
            else:
                ram_str = "—"
            disk = vm.get("disk", 0) or 0
            maxdisk = vm.get("maxdisk", 0) or 0
            vm_type = vm.get("type", "qemu")
            if maxdisk:
                maxdisk_gb = round(maxdisk / (1024**3), 2)
                if vm_type == "lxc" and disk:
                    disk_gb = round(disk / (1024**3), 2)
                    disk_str = f"{disk_gb}/{maxdisk_gb} GiB"
                else:
                    disk_str = f"{maxdisk_gb} GiB"
            else:
                disk_str = "—"
            uptime = vm.get("uptime", 0)
            uptime_str = _format_uptime(uptime) if uptime else "—"
            card_updates.append({
                "vmid": vm.get("vmid"),
                "name": str(vm.get("name", "")),
                "status": vm_status,
                "status_text": status_text(vm_status),
                "cpu_text": cpu_str,
                "ram_text": ram_str,
                "disk_text": disk_str,
                "uptime_text": uptime_str,
            })
        panel.host_vm_list.update_all(card_updates)

    def update_cluster_summary_cells(self, hosts):
        panel = self.panel
        if panel.summary_stack.currentIndex() != 0:
            return
        card_updates = []
        for node in hosts:
            node_name = node.get("_display_name") or node.get("node", "?")
            host_name = node.get("host_name", "")
            cfg = panel._cfg_by_name.get(host_name)
            if cfg and cfg.get("cluster_rep"):
                node_name = "★ " + node_name
            status = node.get("status", "unknown")
            cpu_frac = node.get("cpu", 0)
            cpu_pct = round(cpu_frac * 100, 1) if isinstance(cpu_frac, float) else 0
            mem_bytes = node.get("mem", 0)
            maxmem_bytes = node.get("maxmem", 0) or 0
            mem_gb = round(mem_bytes / (1024**3), 2) if mem_bytes else 0
            maxmem_gb = round(maxmem_bytes / (1024**3), 2) if maxmem_bytes else 0
            uptime_sec = node.get("uptime", 0)
            uptime_str = _format_uptime(uptime_sec) if uptime_sec else "—"
            vms_count = sum(
                1 for v in panel.all_vms
                if v.get("node") == node.get("node")
                and v.get("host_name") == host_name
            )
            card_updates.append({
                "_key": f"{node.get('node', '')}@{host_name}",
                "node": node.get("node", ""),
                "name": node_name,
                "status": status,
                "status_text": status_text(status),
                "address": cfg.get("host", "") if cfg else "",
                "cpu_text": f"{cpu_pct}%",
                "ram_text": f"{mem_gb}/{maxmem_gb} GiB",
                "vms_text": str(vms_count),
                "uptime_text": uptime_str,
            })
        panel.host_summary_list.update_all(card_updates)

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
            lambda nn, data, h=host_cfg_name, w=worker: (
                self.on_host_network(nn, data, h),
                panel._workers_mgr.discard_worker(w)
            )
        )
        worker.signals.network_error.connect(
            lambda nn, err, h=host_cfg_name, w=worker: (
                self.on_host_network(nn, [], h),
                panel._workers_mgr.discard_worker(w)
            )
        )
        panel._workers_mgr.run_host_worker(worker)

    def on_host_network(self, node_name, interfaces, host_cfg_name=""):
        panel = self.panel
        cur_cfg = panel.current_obj_data.get("host_name", "") if panel.current_obj_data else ""
        if panel.current_obj_type != "host" or panel.current_obj_name != node_name or cur_cfg != host_cfg_name:
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
            iface_item = QTableWidgetItem(iface.get("iface", ""))
            iface_item.setIcon(get_icon("network"))
            table.setItem(i, 0, iface_item)
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
            lambda nn, data, h=host_cfg_name, w=worker: (
                self.on_host_services(nn, data, h),
                panel._workers_mgr.discard_worker(w)
            )
        )
        worker.signals.services_error.connect(
            lambda nn, err, h=host_cfg_name, w=worker: (
                self.on_host_services(nn, [], h),
                panel._workers_mgr.discard_worker(w)
            )
        )
        panel._workers_mgr.run_host_worker(worker)

    def on_host_services(self, node_name, services, host_cfg_name=""):
        panel = self.panel
        cur_cfg = panel.current_obj_data.get("host_name", "") if panel.current_obj_data else ""
        if panel.current_obj_type != "host" or panel.current_obj_name != node_name or cur_cfg != host_cfg_name:
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
            name_item = QTableWidgetItem(svc.get("name", ""))
            name_item.setIcon(get_icon("services"))
            table.setItem(i, 0, name_item)
            state = svc.get("state", "")
            table.setItem(i, 1, QTableWidgetItem(state))
            table.setItem(i, 2, QTableWidgetItem(svc.get("desc", "")))
        table.resizeRowsToContents()
        for r in range(table.rowCount()):
            if table.rowHeight(r) > 24:
                table.setRowHeight(r, 24)
        table.setSortingEnabled(True)

    def fetch_host_health(self, host_name, host_data):
        panel = self.panel
        node_name = host_data.get("node", "")
        host_cfg_name = host_data.get("host_name", "")
        cfg = panel._cfg_by_name.get(host_cfg_name)
        if not cfg:
            panel.host_health_stack.widget(0).setText(tr("No data"))
            panel.host_health_stack.setCurrentIndex(0)
            return
        from ..api.metrics import HealthCheckWorker
        worker = HealthCheckWorker(cfg, node_name, host_data)
        worker.signals.health_ready.connect(
            lambda nn, data, h=host_cfg_name, w=worker: (
                self.on_host_health(nn, data, h),
                panel._workers_mgr.discard_worker(w)
            )
        )
        worker.signals.health_error.connect(
            lambda nn, err, h=host_cfg_name, w=worker: (
                self.on_host_health(nn, {"status": "error", "issues": [err], "warnings": []}, h),
                panel._workers_mgr.discard_worker(w)
            )
        )
        panel._workers_mgr.run_host_worker(worker)

    def on_host_health(self, node_name, health, host_cfg_name=""):
        panel = self.panel
        cur_cfg = panel.current_obj_data.get("host_name", "") if panel.current_obj_data else ""
        if panel.current_obj_type != "host" or panel.current_obj_name != node_name or cur_cfg != host_cfg_name:
            return
        issues = health.get("issues", [])
        warnings = health.get("warnings", [])
        items = []
        for idx, msg in enumerate(issues):
            items.append({
                "id": f"issue_{idx}",
                "severity": "error",
                "title": tr("Critical"),
                "message": msg,
            })
        for idx, msg in enumerate(warnings):
            items.append({
                "id": f"warn_{idx}",
                "severity": "warning",
                "title": tr("Warning"),
                "message": msg,
            })
        if not items:
            items.append({
                "id": "ok",
                "severity": "online",
                "title": tr("Healthy"),
                "message": tr("All checks passed"),
            })
        panel.host_health_stack.setCurrentIndex(1)
        panel.host_health_list.set_items(items)

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
            lambda nn, data, h=host_cfg_name, w=worker: (
                self.on_host_disks(nn, data, h),
                panel._workers_mgr.discard_worker(w)
            )
        )
        worker.signals.disks_error.connect(
            lambda nn, err, h=host_cfg_name, w=worker: (
                self.on_host_disks(nn, [], h),
                panel._workers_mgr.discard_worker(w)
            )
        )
        panel._workers_mgr.run_host_worker(worker)

    def on_host_disks(self, node_name, disks, host_cfg_name=""):
        panel = self.panel
        cur_cfg = panel.current_obj_data.get("host_name", "") if panel.current_obj_data else ""
        if panel.current_obj_type != "host" or panel.current_obj_name != node_name or cur_cfg != host_cfg_name:
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
            dev_item = QTableWidgetItem(devpath)
            dev_item.setIcon(get_icon("disk"))
            table.setItem(i, 0, dev_item)
            table.setItem(i, 1, QTableWidgetItem(d.get("type", "")))
            table.setItem(i, 2, QTableWidgetItem(str(model)))
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
        panel._snap_nav_ctx = (host_cfg_name, node_name)
        cfg = panel._cfg_by_name.get(host_cfg_name)
        if not cfg:
            panel.host_snapshots_stack.widget(0).setText(tr("No data"))
            panel.host_snapshots_stack.setCurrentIndex(0)
            return
        vms = [vm for vm in panel.all_vms if vm.get("node") == host_name and vm.get("host_name") == host_cfg_name]
        from ..api.metrics import HostSnapshotsWorker
        worker = HostSnapshotsWorker(cfg, node_name, vms)
        worker.signals.snapshots_ready.connect(
            lambda nn, data, h=host_cfg_name, w=worker: (
                self.on_host_snapshots(nn, data, h),
                panel._workers_mgr.discard_worker(w)
            )
        )
        worker.signals.snapshots_error.connect(
            lambda nn, err, h=host_cfg_name, w=worker: (
                self.on_host_snapshots(nn, [], h),
                panel._workers_mgr.discard_worker(w)
            )
        )
        panel._workers_mgr.run_host_worker(worker)

    def on_host_snapshots(self, node_name, snapshots, host_cfg_name=""):
        panel = self.panel
        cur_cfg = panel.current_obj_data.get("host_name", "") if panel.current_obj_data else ""
        if panel.current_obj_type != "host" or panel.current_obj_name != node_name or cur_cfg != host_cfg_name:
            return
        if snapshots:
            panel.host_snapshots_stack.setCurrentIndex(1)
            self.populate_host_snapshots_tree(snapshots)
        else:
            panel.host_snapshots_stack.widget(0).setText(tr("No snapshots"))
            panel.host_snapshots_stack.setCurrentIndex(0)

    def populate_host_snapshots_tree(self, snapshots):
        from PySide6.QtWidgets import QTreeWidgetItem
        tree = self.panel.host_snapshots_tree
        tree.clear()
        nav_ctx = getattr(self.panel, "_snap_nav_ctx", ("", ""))
        host_name, node = nav_ctx
        vms_map = {}
        for snap in snapshots:
            vmid = snap.get("vmid", 0)
            vms_map.setdefault(vmid, []).append(snap)

        def make_snap_item(snap):
            name = snap.get("name", "")
            desc = snap.get("description", "") or ""
            snaptime = snap.get("snaptime", 0)
            ts = datetime.fromtimestamp(snaptime).strftime("%Y-%m-%d %H:%M:%S") if snaptime else ""
            vm_state = tr("yes") if snap.get("vmstate", 0) else tr("no")
            size_val = snap.get("size", 0)
            if isinstance(size_val, (int, float)) and size_val > 0:
                gb = size_val / (1024 ** 3)
                size_str = f"{gb / 1024:.1f} TiB" if gb >= 1024 else f"{gb:.1f} GiB"
            else:
                size_str = "—"
            parent_name = snap.get("parent", "") or ""
            return QTreeWidgetItem([name, desc, ts, vm_state, size_str, parent_name])

        for vmid in sorted(vms_map.keys()):
            vm_snaps = vms_map[vmid]
            first = vm_snaps[0]
            vm_label = f"{vmid} {first.get('vm_name', '')}"
            vm_item = QTreeWidgetItem([vm_label, "", "", "", "", ""])
            if host_name and vmid:
                try:
                    vm_item.setData(0, Qt.UserRole, (host_name, int(vmid), node))
                except (ValueError, TypeError):
                    pass
            font = vm_item.font(0)
            font.setBold(True)
            vm_item.setFont(0, font)
            snap_by_name = {s.get("name", ""): s for s in vm_snaps}
            created_names = set()
            remaining = list(vm_snaps)

            for _ in range(len(vm_snaps) + 1):
                progress = False
                still = []
                for snap in remaining:
                    parent_name = snap.get("parent", "") or ""
                    if not parent_name or parent_name == "current" or parent_name not in snap_by_name:
                        item = make_snap_item(snap)
                        vm_item.addChild(item)
                        snap["_item"] = item
                        created_names.add(snap.get("name", ""))
                        progress = True
                    elif parent_name in created_names:
                        parent_snap = snap_by_name[parent_name]
                        parent_item = parent_snap.get("_item")
                        if parent_item:
                            item = make_snap_item(snap)
                            parent_item.addChild(item)
                            snap["_item"] = item
                            created_names.add(snap.get("name", ""))
                            progress = True
                        else:
                            still.append(snap)
                    else:
                        still.append(snap)
                remaining = still
                if not progress:
                    break

            tree.addTopLevelItem(vm_item)

        tree.expandAll()
        tree.resizeColumnToContents(0)

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
        panel._workers_mgr.run_host_worker(worker)

    def on_host_metrics_fetched(self, timeframe, node_name, metrics_dict, gen):
        panel = self.panel
        if gen != panel._generation:
            return
        cache_key = ("host", node_name, timeframe)
        panel.metrics_cache[cache_key] = metrics_dict
        panel.metrics_widget.update_curves(metrics_dict)

    # ------------------------------------------------------------------
    # Backup Jobs tab
    # ------------------------------------------------------------------

    def build_backup_jobs_tab(self):
        panel = self.panel
        loading = loading_label()
        table = make_table(
            [tr("ID"), tr("Enabled"), tr("Schedule"), tr("Storage"),
             tr("VMIDs"), tr("Mode"), tr("Comment")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 60),
             (QHeaderView.Interactive, 100), (QHeaderView.Interactive, 100),
             (QHeaderView.Interactive, 120), (QHeaderView.Interactive, 80),
             (QHeaderView.Stretch, None)],
            sortable=True,
        )
        panel.backup_jobs_table = table
        table.doubleClicked.connect(lambda idx: self._on_edit_backup_job())
        toolbar = QWidget()
        btn_layout = QHBoxLayout(toolbar)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)
        add_btn = QPushButton(get_icon("add"), tr("Add"))
        add_btn.setMinimumHeight(28)
        add_btn.clicked.connect(self._on_add_backup_job)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton(tr("Edit"))
        edit_btn.setMinimumHeight(28)
        edit_btn.clicked.connect(self._on_edit_backup_job)
        btn_layout.addWidget(edit_btn)
        remove_btn = QPushButton(get_icon("remove"), tr("Remove"))
        remove_btn.setMinimumHeight(28)
        remove_btn.clicked.connect(self._on_remove_backup_job)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        panel.backup_job_add_btn = add_btn
        panel.backup_job_edit_btn = edit_btn
        panel.backup_job_remove_btn = remove_btn
        stack = QStackedWidget()
        stack.addWidget(loading)
        from ._table_utils import make_filterable_table
        stack.addWidget(make_filterable_table(table))
        stack.setCurrentIndex(0)
        panel.backup_jobs_loading = loading
        panel.backup_jobs_stack = stack
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(toolbar)
        layout.addWidget(stack)
        tab.setWidget(container)
        return tab

    # --- cluster tab population ---

    def _populate_cluster_vms(self, cluster_name, hosts):
        panel = self.panel
        host_names = {h.get("host_name", "") for h in hosts}
        node_names = {h.get("node", "") for h in hosts}
        vms = [vm for vm in panel.all_vms
               if vm.get("node") in node_names
               and vm.get("host_name") in host_names]
        card_items = []
        for vm in vms:
            vmid = vm.get("vmid", "")
            name = vm.get("name", "") or f"VM {vmid}"
            status = vm.get("status", "")
            cpu = vm.get("cpu", 0) or 0
            cpu_pct = round(cpu * 100, 1) if isinstance(cpu, float) else 0
            mem = vm.get("mem", 0) or 0
            maxmem = vm.get("maxmem", 0) or 0
            mem_gb = round(mem / (1024**3), 1) if mem else 0
            maxmem_gb = round(maxmem / (1024**3), 1) if maxmem else 0
            disk = vm.get("disk", 0) or 0
            disk_gb = round(disk / (1024**3), 1) if disk else 0
            uptime = vm.get("uptime", 0) or 0
            card_items.append({
                "vmid": vmid,
                "name": name,
                "status": status,
                "status_text": status_text(status),
                "cpu_text": f"{cpu_pct}%",
                "ram_text": f"{mem_gb}/{maxmem_gb} GiB",
                "disk_text": f"{disk_gb} GiB",
                "uptime_text": _format_uptime(uptime) if uptime else "—",
                "host_name": vm.get("host_name", ""),
                "node": vm.get("node", ""),
            })
        panel.host_vm_list.set_items(card_items)
        self._populate_vm_stats(vms)

    def _populate_cluster_storages(self, cluster_name):
        panel = self.panel
        storages = [s for s in panel.all_storages if s.get("cluster") == cluster_name]
        if not storages:
            cluster_host_names = {h.get("host_name") for h in panel.all_nodes
                                  if panel._cfg_by_name.get(h.get("host_name", ""), {}).get("cluster") == cluster_name}
            storages = [s for s in panel.all_storages
                        if not s.get("cluster")
                        and s.get("node") in {h.get("node") for h in panel.all_nodes
                                              if h.get("host_name") in cluster_host_names}
                        and s.get("host_name") in cluster_host_names]
        card_items = []
        seen = set()
        for st in storages:
            name = st.get("storage", st.get("id", ""))
            if not name or name in seen:
                continue
            seen.add(name)
            content = st.get("content", "")
            if isinstance(content, list):
                content = ", ".join(content)
            used = st.get("used", 0) or 0
            total = st.get("total", 0) or 0
            used_gb = round(used / (1024**3), 1) if used else 0
            total_gb = round(total / (1024**3), 1) if total else 0
            pct = safe_pct(used, total)
            card_items.append({
                "name": name,
                "type_text": st.get("type", ""),
                "content_text": content,
                "location_text": cluster_name,
                "used_text": f"{used_gb} GiB",
                "total_text": f"{total_gb} GiB",
                "usage_text": f"{pct}%",
                "nav_key": ("storage", name, "cluster", cluster_name),
            })
        panel.storage_list.set_items(card_items)

    def _on_vm_card_nav(self, data):
        vmid = data.get("vmid")
        host_name = data.get("host_name")
        node = data.get("node", "")
        if vmid is not None and host_name:
            try:
                self.panel.navigate_requested.emit((host_name, int(vmid), node))
            except (ValueError, TypeError):
                pass

    def _on_host_card_nav(self, data):
        key = data.get("_key", "")
        node = data.get("node", "")
        if "@" in key and node:
            host_name = key.split("@", 1)[1]
            self.panel.navigate_requested.emit(("host", node, host_name))

    def _on_cluster_card_nav(self, data):
        name = data.get("name", "")
        if name:
            self.panel.navigate_requested.emit(("cluster", name))

    def _on_snap_tree_nav(self, item, _col):
        key = item.data(0, Qt.UserRole)
        if isinstance(key, tuple) and len(key) == 3:
            self.panel.navigate_requested.emit(key)

    def _fetch_cluster_snapshots(self, hosts):
        panel = self.panel
        panel.host_snapshots_stack.setCurrentIndex(0)
        panel.host_snapshots_loading.setText(tr("Loading..."))
        panel.host_snapshots_tree.clear()
        for host in hosts:
            node_name = host.get("node", "")
            host_cfg_name = host.get("host_name", "")
            cfg = panel._cfg_by_name.get(host_cfg_name)
            if not cfg:
                continue
            vms = [vm for vm in panel.all_vms
                   if vm.get("node") == node_name and vm.get("host_name") == host_cfg_name]
            from ..api.metrics import HostSnapshotsWorker
            worker = HostSnapshotsWorker(cfg, node_name, vms)
            worker.signals.snapshots_ready.connect(
                lambda nn, data, w=worker: (
                    self._on_cluster_snapshots(nn, data),
                    panel._workers_mgr.discard_worker(w),
                )
            )
            worker.signals.snapshots_error.connect(
                lambda nn, err, w=worker: (
                    self._on_cluster_snapshots(nn, []),
                    panel._workers_mgr.discard_worker(w),
                )
            )
            panel._workers_mgr.run_host_worker(worker)

    def _on_cluster_snapshots(self, node_name, data):
        panel = self.panel
        if panel.current_obj_type != "cluster":
            return
        tree = panel.host_snapshots_tree
        vms_map = {}
        for snap in (data or []):
            vmid = snap.get("vmid", 0)
            vms_map.setdefault(vmid, []).append(snap)
        for vmid in sorted(vms_map.keys()):
            snaps = vms_map[vmid]
            vm_name = snaps[0].get("vm_name", "")
            vm_label = f"{vmid} {vm_name}".strip()
            vm_item = QTreeWidgetItem(tree, [vm_label, "", "", "", "", ""])
            vm_item.setIcon(0, get_icon("snapshot"))
            snap_host = snaps[0].get("host_name", "")
            snap_node = snaps[0].get("node", "")
            if snap_host and vmid:
                try:
                    vm_item.setData(0, Qt.UserRole, (snap_host, int(vmid), snap_node))
                except (ValueError, TypeError):
                    pass
            for snap in snaps:
                name = snap.get("name", "")
                desc = snap.get("description", "") or ""
                ctime = snap.get("snaptime", 0)
                created = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M") if ctime else ""
                parent = snap.get("parent", "") or ""
                size = snap.get("size", 0) or 0
                if isinstance(size, (int, float)) and size > 0:
                    gb = size / (1024 ** 3)
                    size_text = f"{gb / 1024:.1f} TiB" if gb >= 1024 else f"{gb:.1f} GiB"
                else:
                    size_text = ""
                QTreeWidgetItem(vm_item, [name, desc, created, "", size_text, parent])
        tree.resizeColumnToContents(0)
        tree.expandAll()
        panel.host_snapshots_stack.setCurrentIndex(1)

    def _fetch_cluster_health(self, hosts):
        panel = self.panel
        panel.host_health_stack.setCurrentIndex(0)
        panel.host_health_loading.setText(tr("Loading..."))
        panel.host_health_list.set_items([])
        panel._cluster_health_collected = []
        panel._cluster_health_total = 0
        panel._cluster_health_done = 0
        pending = [h for h in hosts if h.get("status") != "error"]
        if not pending:
            panel.host_health_loading.setText(tr("No data"))
            return
        panel._cluster_health_total = len(pending)
        for host in pending:
            node_name = host.get("node", "")
            host_cfg_name = host.get("host_name", "")
            cfg = panel._cfg_by_name.get(host_cfg_name)
            if not cfg:
                panel._cluster_health_done += 1
                continue
            from ..api.metrics import HealthCheckWorker
            worker = HealthCheckWorker(cfg, node_name, host)
            worker.signals.health_ready.connect(
                lambda nn, result, w=worker: (
                    self._on_cluster_health(nn, result),
                    panel._workers_mgr.discard_worker(w),
                )
            )
            worker.signals.health_error.connect(
                lambda nn, err, w=worker: (
                    self._on_cluster_health(nn, {"status": "error", "issues": [err], "warnings": []}),
                    panel._workers_mgr.discard_worker(w),
                )
            )
            panel._workers_mgr.run_host_worker(worker)
        if panel._cluster_health_done >= panel._cluster_health_total:
            panel.host_health_list.set_items([])
            panel.host_health_stack.setCurrentIndex(1)

    def _on_cluster_health(self, node_name, result):
        panel = self.panel
        if panel.current_obj_type != "cluster":
            return
        collected = getattr(panel, "_cluster_health_collected", None)
        if collected is None:
            collected = []
            panel._cluster_health_collected = collected
        issues = result.get("issues", []) or []
        warnings = result.get("warnings", []) or []
        for issue in issues:
            collected.append({
                "id": f"{node_name}-err-{len(collected)}",
                "severity": "error",
                "title": node_name,
                "message": issue,
            })
        for warning in warnings:
            collected.append({
                "id": f"{node_name}-warn-{len(collected)}",
                "severity": "warning",
                "title": node_name,
                "message": warning,
            })
        if result.get("status") == "ok" and not issues and not warnings:
            collected.append({
                "id": f"{node_name}-ok",
                "severity": "online",
                "title": node_name,
                "message": tr("All checks passed"),
            })
        panel._cluster_health_done += 1
        if panel._cluster_health_done >= panel._cluster_health_total:
            panel.host_health_list.set_items(collected)
            panel.host_health_stack.setCurrentIndex(1)
            panel._cluster_health_collected = None

    # --- backup jobs fetch / populate ---

    def _detect_pve_major(self, cfg_or_host):
        if isinstance(cfg_or_host, dict):
            for node in self.panel.all_nodes:
                if node.get("host_name") == cfg_or_host.get("name", ""):
                    pvever = node.get("pveversion", "")
                    if pvever:
                        v = pvever.split("/")[1] if "/" in pvever else pvever
                        major = v.split(".")[0]
                        try:
                            return int(major)
                        except ValueError:
                            pass
        return 7

    def _fetch_backup_jobs(self, cfg, context_name):
        panel = self.panel
        if not cfg:
            panel.backup_jobs_loading.setText(tr("No data"))
            panel.backup_jobs_stack.setCurrentIndex(0)
            return
        panel.backup_jobs_loading.setText(tr("Loading..."))
        panel.backup_jobs_stack.setCurrentIndex(0)
        panel.backup_jobs_table.setRowCount(0)
        panel._backup_jobs_cfg = cfg
        panel._backup_jobs_context = context_name
        pve_major = self._detect_pve_major(cfg)
        panel._backup_jobs_pve_major = pve_major
        from ...backend import ClusterJobsWorker
        worker = ClusterJobsWorker(cfg, pve_major=pve_major)
        worker.signals.jobs_ready.connect(
            lambda jobs, w=worker: (
                self._on_backup_jobs_loaded(jobs),
                panel._workers_mgr.discard_worker(w),
            )
        )
        worker.signals.jobs_error.connect(
            lambda err, w=worker: (
                self._on_backup_jobs_error(err),
                panel._workers_mgr.discard_worker(w),
            )
        )
        panel._workers_mgr.run_host_worker(worker)

    def _on_backup_jobs_loaded(self, jobs):
        panel = self.panel
        table = panel.backup_jobs_table
        table.setSortingEnabled(False)
        table.setRowCount(len(jobs))
        for i, job in enumerate(jobs):
            job_id = job.get("id", "")
            id_item = QTableWidgetItem(job_id)
            id_item.setData(Qt.UserRole, job)
            id_item.setIcon(get_icon("backup"))
            table.setItem(i, 0, id_item)
            enabled = int(job.get("enabled", 1) or 0)
            en_text = tr("Yes") if enabled else tr("No")
            en_item = QTableWidgetItem(en_text)
            en_item.setForeground(QColor(Color.STATUS_OK if enabled else Color.GRAY_400))
            table.setItem(i, 1, en_item)
            table.setItem(i, 2, QTableWidgetItem(job.get("schedule", "")))
            table.setItem(i, 3, QTableWidgetItem(job.get("storage", "")))
            vmid = job.get("vmid", "")
            table.setItem(i, 4, QTableWidgetItem(str(vmid) if vmid else ""))
            table.setItem(i, 5, QTableWidgetItem(job.get("mode", "")))
            table.setItem(i, 6, QTableWidgetItem(job.get("comment", "") or ""))
        table.setSortingEnabled(True)
        if jobs:
            panel.backup_jobs_stack.setCurrentIndex(1)
        else:
            panel.backup_jobs_loading.setText(tr("No backup jobs"))
            panel.backup_jobs_stack.setCurrentIndex(0)

    def _on_backup_jobs_error(self, err):
        panel = self.panel
        panel.backup_jobs_loading.setText(tr("Error loading jobs"))
        panel.backup_jobs_stack.setCurrentIndex(0)

    def _get_backup_jobs_storages(self):
        panel = self.panel
        ctx = getattr(panel, "_backup_jobs_context", "")
        if panel.current_obj_type == "cluster":
            return [s for s in panel.all_storages if s.get("cluster") == ctx]
        elif panel.current_obj_type == "host":
            host_cfg = getattr(panel, "_backup_jobs_host_cfg", "") or ctx
            return [s for s in panel.all_storages
                    if s.get("node") == ctx
                    and s.get("host_name") == host_cfg]
        return panel.all_storages

    def _on_add_backup_job(self):
        panel = self.panel
        cfg = getattr(panel, "_backup_jobs_cfg", None)
        if not cfg:
            return
        pve_major = getattr(panel, "_backup_jobs_pve_major", 7)
        storages = self._get_backup_jobs_storages()
        from ..backup_job_dialog import BackupJobDialog
        dlg = BackupJobDialog(panel, storages=storages)
        if dlg.exec() != BackupJobDialog.Accepted:
            return
        params = dlg.get_params()
        from ...backend import ClusterJobCreateWorker
        worker = ClusterJobCreateWorker(cfg, params, pve_major=pve_major)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self._fetch_backup_jobs(cfg, panel._backup_jobs_context),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("Job create failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    def _on_edit_backup_job(self):
        panel = self.panel
        table = panel.backup_jobs_table
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(panel, tr("Edit backup job"), tr("Select a job to edit"))
            return
        id_item = table.item(row, 0)
        if not id_item:
            return
        job = id_item.data(Qt.UserRole)
        if not job:
            return
        cfg = getattr(panel, "_backup_jobs_cfg", None)
        if not cfg:
            return
        pve_major = getattr(panel, "_backup_jobs_pve_major", 7)
        storages = self._get_backup_jobs_storages()
        from ..backup_job_dialog import BackupJobDialog
        dlg = BackupJobDialog(panel, storages=storages, job=job)
        if dlg.exec() != BackupJobDialog.Accepted:
            return
        params = dlg.get_params()
        job_id = job.get("id", "")
        from ...backend import ClusterJobUpdateWorker
        worker = ClusterJobUpdateWorker(cfg, job_id, params, pve_major=pve_major)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self._fetch_backup_jobs(cfg, panel._backup_jobs_context),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("Job update failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    def _on_remove_backup_job(self):
        panel = self.panel
        table = panel.backup_jobs_table
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(panel, tr("Remove backup job"), tr("Select a job to remove"))
            return
        id_item = table.item(row, 0)
        if not id_item:
            return
        job = id_item.data(Qt.UserRole)
        if not job:
            return
        job_id = job.get("id", "")
        if not job_id:
            return
        reply = QMessageBox.question(
            panel, tr("Remove backup job"),
            tr("Delete backup job \"{id}\"?").format(id=job_id),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        cfg = getattr(panel, "_backup_jobs_cfg", None)
        if not cfg:
            return
        pve_major = getattr(panel, "_backup_jobs_pve_major", 7)
        from ...backend import ClusterJobDeleteWorker
        worker = ClusterJobDeleteWorker(cfg, job_id, pve_major=pve_major)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self._fetch_backup_jobs(cfg, panel._backup_jobs_context),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("Job delete failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    # ------------------------------------------------------------------
    # Access Management tab
    # ------------------------------------------------------------------

    def build_access_tab(self):
        panel = self.panel
        inner = QTabWidget()

        inner.addTab(self._build_access_users_page(), get_icon("user"), tr("Users"))
        inner.addTab(self._build_access_tokens_page(), get_icon("token"), tr("API Tokens"))
        inner.addTab(self._build_access_groups_page(), get_icon("group"), tr("Groups"))
        inner.addTab(self._build_access_roles_page(), get_icon("role"), tr("Roles"))
        inner.addTab(self._build_access_acl_page(), get_icon("acl"), tr("Permissions"))

        panel.access_inner = inner
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(inner)
        return tab

    # --- Users sub-page ---

    def _build_access_users_page(self):
        panel = self.panel
        loading = loading_label()
        table = make_table(
            [tr("User ID"), tr("Enabled"), tr("Expire"), tr("Groups"),
             tr("Comment"), tr("Tokens")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 60),
             (QHeaderView.Interactive, 100), (QHeaderView.Stretch, None),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 60)],
            sortable=True,
        )
        panel.access_users_table = table
        table.doubleClicked.connect(lambda idx: self._on_edit_access_user())
        toolbar = QWidget()
        btn_layout = QHBoxLayout(toolbar)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)
        add_btn = QPushButton(get_icon("add"), tr("Add"))
        add_btn.setMinimumHeight(28)
        add_btn.clicked.connect(self._on_add_access_user)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton(tr("Edit"))
        edit_btn.setMinimumHeight(28)
        edit_btn.clicked.connect(self._on_edit_access_user)
        btn_layout.addWidget(edit_btn)
        remove_btn = QPushButton(get_icon("remove"), tr("Remove"))
        remove_btn.setMinimumHeight(28)
        remove_btn.clicked.connect(self._on_remove_access_user)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        stack = QStackedWidget()
        stack.addWidget(loading)
        from ._table_utils import make_filterable_table
        stack.addWidget(make_filterable_table(table))
        stack.setCurrentIndex(0)
        panel.access_users_loading = loading
        panel.access_users_stack = stack
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(toolbar)
        layout.addWidget(stack)
        return container

    # --- Tokens sub-page ---

    def _build_access_tokens_page(self):
        panel = self.panel
        loading = loading_label()
        table = make_table(
            [tr("Token ID"), tr("User"), tr("Comment"), tr("Priv. sep."),
             tr("Expire")],
            [(QHeaderView.Stretch, None), (QHeaderView.Stretch, None),
             (QHeaderView.Stretch, None), (QHeaderView.Interactive, 80),
             (QHeaderView.Interactive, 100)],
            sortable=True,
        )
        panel.access_tokens_table = table
        table.doubleClicked.connect(lambda idx: self._on_edit_access_token())
        toolbar = QWidget()
        btn_layout = QHBoxLayout(toolbar)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)
        add_btn = QPushButton(get_icon("add"), tr("Add"))
        add_btn.setMinimumHeight(28)
        add_btn.clicked.connect(self._on_add_access_token)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton(tr("Edit"))
        edit_btn.setMinimumHeight(28)
        edit_btn.clicked.connect(self._on_edit_access_token)
        btn_layout.addWidget(edit_btn)
        remove_btn = QPushButton(get_icon("remove"), tr("Remove"))
        remove_btn.setMinimumHeight(28)
        remove_btn.clicked.connect(self._on_remove_access_token)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        stack = QStackedWidget()
        stack.addWidget(loading)
        from ._table_utils import make_filterable_table
        stack.addWidget(make_filterable_table(table))
        stack.setCurrentIndex(0)
        panel.access_tokens_loading = loading
        panel.access_tokens_stack = stack
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(toolbar)
        layout.addWidget(stack)
        return container

    # --- Groups sub-page ---

    def _build_access_groups_page(self):
        panel = self.panel
        loading = loading_label()
        table = make_table(
            [tr("Group ID"), tr("Comment"), tr("Members")],
            [(QHeaderView.Stretch, None), (QHeaderView.Stretch, None),
             (QHeaderView.Stretch, None)],
            sortable=True,
        )
        panel.access_groups_table = table
        table.doubleClicked.connect(lambda idx: self._on_edit_access_group())
        toolbar = QWidget()
        btn_layout = QHBoxLayout(toolbar)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)
        add_btn = QPushButton(get_icon("add"), tr("Add"))
        add_btn.setMinimumHeight(28)
        add_btn.clicked.connect(self._on_add_access_group)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton(tr("Edit"))
        edit_btn.setMinimumHeight(28)
        edit_btn.clicked.connect(self._on_edit_access_group)
        btn_layout.addWidget(edit_btn)
        remove_btn = QPushButton(get_icon("remove"), tr("Remove"))
        remove_btn.setMinimumHeight(28)
        remove_btn.clicked.connect(self._on_remove_access_group)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        stack = QStackedWidget()
        stack.addWidget(loading)
        from ._table_utils import make_filterable_table
        stack.addWidget(make_filterable_table(table))
        stack.setCurrentIndex(0)
        panel.access_groups_loading = loading
        panel.access_groups_stack = stack
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(toolbar)
        layout.addWidget(stack)
        return container

    # --- Roles sub-page ---

    def _build_access_roles_page(self):
        panel = self.panel
        loading = loading_label()
        table = make_table(
            [tr("Role ID"), tr("Privileges"), tr("Built-in")],
            [(QHeaderView.Stretch, None), (QHeaderView.Stretch, None),
             (QHeaderView.Interactive, 70)],
            sortable=True,
        )
        panel.access_roles_table = table
        table.doubleClicked.connect(lambda idx: self._on_edit_access_role())
        toolbar = QWidget()
        btn_layout = QHBoxLayout(toolbar)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)
        add_btn = QPushButton(get_icon("add"), tr("Add"))
        add_btn.setMinimumHeight(28)
        add_btn.clicked.connect(self._on_add_access_role)
        btn_layout.addWidget(add_btn)
        edit_btn = QPushButton(tr("Edit"))
        edit_btn.setMinimumHeight(28)
        edit_btn.clicked.connect(self._on_edit_access_role)
        btn_layout.addWidget(edit_btn)
        remove_btn = QPushButton(get_icon("remove"), tr("Remove"))
        remove_btn.setMinimumHeight(28)
        remove_btn.clicked.connect(self._on_remove_access_role)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        stack = QStackedWidget()
        stack.addWidget(loading)
        from ._table_utils import make_filterable_table
        stack.addWidget(make_filterable_table(table))
        stack.setCurrentIndex(0)
        panel.access_roles_loading = loading
        panel.access_roles_stack = stack
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(toolbar)
        layout.addWidget(stack)
        return container

    # --- ACL / Permissions sub-page ---

    def _build_access_acl_page(self):
        panel = self.panel
        loading = loading_label()
        table = make_table(
            [tr("Path"), tr("Type"), tr("ID"), tr("Role"), tr("Propagate")],
            [(QHeaderView.Stretch, None), (QHeaderView.Interactive, 80),
             (QHeaderView.Stretch, None), (QHeaderView.Stretch, None),
             (QHeaderView.Interactive, 80)],
            sortable=True,
        )
        panel.access_acl_table = table
        toolbar = QWidget()
        btn_layout = QHBoxLayout(toolbar)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)
        add_btn = QPushButton(get_icon("add"), tr("Add"))
        add_btn.setMinimumHeight(28)
        add_btn.clicked.connect(self._on_add_access_acl)
        btn_layout.addWidget(add_btn)
        remove_btn = QPushButton(get_icon("remove"), tr("Remove"))
        remove_btn.setMinimumHeight(28)
        remove_btn.clicked.connect(self._on_remove_access_acl)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        stack = QStackedWidget()
        stack.addWidget(loading)
        from ._table_utils import make_filterable_table
        stack.addWidget(make_filterable_table(table))
        stack.setCurrentIndex(0)
        panel.access_acl_loading = loading
        panel.access_acl_stack = stack
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(toolbar)
        layout.addWidget(stack)
        return container

    # --- Fetch methods ---

    def _fetch_access_all(self, cfg):
        self._fetch_access_users(cfg)
        self._fetch_access_groups(cfg)
        self._fetch_access_roles(cfg)
        self._fetch_access_acl(cfg)

    def _fetch_access_users(self, cfg):
        panel = self.panel
        if not cfg:
            panel.access_users_loading.setText(tr("No data"))
            panel.access_users_stack.setCurrentIndex(0)
            return
        panel.access_users_loading.setText(tr("Loading..."))
        panel.access_users_stack.setCurrentIndex(0)
        panel.access_users_table.setRowCount(0)
        panel._access_cfg = cfg
        from ...backend import AccessUsersWorker
        worker = AccessUsersWorker(cfg)
        worker.signals.users_ready.connect(
            lambda data, w=worker: (
                self._on_access_users_loaded(data),
                panel._workers_mgr.discard_worker(w),
            )
        )
        worker.signals.users_error.connect(
            lambda err, w=worker: (
                self._on_access_users_error(err),
                panel._workers_mgr.discard_worker(w),
            )
        )
        panel._workers_mgr.run_host_worker(worker)

    def _on_access_users_loaded(self, data):
        panel = self.panel
        if panel.current_obj_type not in ("cluster", "host"):
            return
        panel._access_users_cache = data
        table = panel.access_users_table
        table.setSortingEnabled(False)
        table.setRowCount(len(data))
        for i, user in enumerate(data):
            uid = user.get("userid", "")
            id_item = QTableWidgetItem(uid)
            id_item.setIcon(get_icon("user"))
            id_item.setData(Qt.UserRole, user)
            table.setItem(i, 0, id_item)

            enable_val = user.get("enable", 1)
            if isinstance(enable_val, str):
                enable_val = int(enable_val)
            en_text = tr("Yes") if enable_val else tr("No")
            en_item = QTableWidgetItem(en_text)
            en_item.setForeground(QColor(
                Color.STATUS_OK if enable_val else Color.GRAY_400
            ))
            table.setItem(i, 1, en_item)

            expire = user.get("expire", 0)
            if isinstance(expire, str):
                expire = int(expire)
            if expire and expire > 0:
                from datetime import datetime as _dt
                expire_text = _dt.fromtimestamp(expire).strftime("%Y-%m-%d")
            else:
                expire_text = tr("Never")
            table.setItem(i, 2, QTableWidgetItem(expire_text))

            groups = user.get("groups", "")
            if isinstance(groups, list):
                groups = ", ".join(groups)
            table.setItem(i, 3, QTableWidgetItem(groups or ""))

            table.setItem(i, 4, QTableWidgetItem(user.get("comment", "") or ""))

            tokens = user.get("tokens", [])
            tokens_count = len(tokens) if isinstance(tokens, list) else 0
            table.setItem(i, 5, QTableWidgetItem(str(tokens_count)))

        table.setSortingEnabled(True)
        if data:
            panel.access_users_stack.setCurrentIndex(1)
        else:
            panel.access_users_loading.setText(tr("No users"))
            panel.access_users_stack.setCurrentIndex(0)
        cfg = getattr(panel, "_access_cfg", None)
        if cfg:
            self._fetch_access_tokens(cfg)

    def _on_access_users_error(self, err):
        panel = self.panel
        panel.access_users_loading.setText(tr("Error: {err}").format(err=err[:80]))
        panel.access_users_stack.setCurrentIndex(0)

    def _fetch_access_tokens(self, cfg):
        panel = self.panel
        if not cfg:
            panel.access_tokens_loading.setText(tr("No data"))
            panel.access_tokens_stack.setCurrentIndex(0)
            return
        panel.access_tokens_loading.setText(tr("Loading..."))
        panel.access_tokens_stack.setCurrentIndex(0)
        panel.access_tokens_table.setRowCount(0)
        users = getattr(panel, "_access_users_cache", [])
        if not users:
            panel.access_tokens_loading.setText(tr("No users"))
            panel.access_tokens_stack.setCurrentIndex(0)
            return
        user_ids = [u.get("userid") for u in users if u.get("userid")]
        if not user_ids:
            panel.access_tokens_loading.setText(tr("No users"))
            panel.access_tokens_stack.setCurrentIndex(0)
            return
        panel._access_tokens_epoch = getattr(panel, "_access_tokens_epoch", 0) + 1
        panel._access_tokens_pending = len(user_ids)
        this_epoch = panel._access_tokens_epoch
        from ...backend import AccessTokensWorker
        for uid in user_ids:
            worker = AccessTokensWorker(cfg, uid)
            worker.signals.tokens_ready.connect(
                lambda data, w=worker, u=uid, e=this_epoch: (
                    self._on_access_tokens_partial(data, u, e),
                    panel._workers_mgr.discard_worker(w),
                )
            )
            worker.signals.tokens_error.connect(
                lambda err, w=worker, e=this_epoch: (
                    self._on_access_tokens_done(e),
                    panel._workers_mgr.discard_worker(w),
                )
            )
            panel._workers_mgr.run_host_worker(worker)

    def _on_access_tokens_done(self, epoch=None):
        panel = self.panel
        cur = getattr(panel, "_access_tokens_epoch", 0)
        if epoch is not None and epoch != cur:
            return
        panel._access_tokens_pending = getattr(panel, "_access_tokens_pending", 0) - 1
        if panel._access_tokens_pending <= 0:
            if panel.access_tokens_table.rowCount() > 0:
                panel.access_tokens_stack.setCurrentIndex(1)
            else:
                panel.access_tokens_loading.setText(tr("No tokens"))
                panel.access_tokens_stack.setCurrentIndex(0)

    def _on_access_tokens_partial(self, data, userid, epoch=None):
        panel = self.panel
        cur = getattr(panel, "_access_tokens_epoch", 0)
        if epoch is not None and epoch != cur:
            return
        if panel.current_obj_type not in ("cluster", "host"):
            self._on_access_tokens_done(epoch)
            return
        if not isinstance(data, list):
            self._on_access_tokens_done(epoch)
            return
        table = panel.access_tokens_table
        table.setSortingEnabled(False)
        for token in data:
            row = table.rowCount()
            table.insertRow(row)
            tid = token.get("tokenid", "")
            id_item = QTableWidgetItem(tid)
            id_item.setIcon(get_icon("token"))
            id_item.setData(Qt.UserRole, {"userid": userid, **token})
            table.setItem(row, 0, id_item)
            table.setItem(row, 1, QTableWidgetItem(userid))
            table.setItem(row, 2, QTableWidgetItem(token.get("comment", "") or ""))
            privsep = token.get("privsep", 1)
            if isinstance(privsep, str):
                privsep = int(privsep)
            table.setItem(row, 3, QTableWidgetItem(tr("Yes") if privsep else tr("No")))
            expire = token.get("expire", 0)
            if isinstance(expire, str):
                expire = int(expire)
            if expire and expire > 0:
                from datetime import datetime as _dt
                expire_text = _dt.fromtimestamp(expire).strftime("%Y-%m-%d")
            else:
                expire_text = tr("Never")
            table.setItem(row, 4, QTableWidgetItem(expire_text))
        table.setSortingEnabled(True)
        if table.rowCount() > 0:
            panel.access_tokens_stack.setCurrentIndex(1)
        self._on_access_tokens_done(epoch)

    def _fetch_access_groups(self, cfg):
        panel = self.panel
        if not cfg:
            panel.access_groups_loading.setText(tr("No data"))
            panel.access_groups_stack.setCurrentIndex(0)
            return
        panel.access_groups_loading.setText(tr("Loading..."))
        panel.access_groups_stack.setCurrentIndex(0)
        panel.access_groups_table.setRowCount(0)
        from ...backend import AccessGroupsWorker
        worker = AccessGroupsWorker(cfg)
        worker.signals.groups_ready.connect(
            lambda data, w=worker: (
                self._on_access_groups_loaded(data),
                panel._workers_mgr.discard_worker(w),
            )
        )
        worker.signals.groups_error.connect(
            lambda err, w=worker: (
                panel.access_groups_loading.setText(tr("Error: {err}").format(err=err[:80])),
                panel.access_groups_stack.setCurrentIndex(0),
                panel._workers_mgr.discard_worker(w),
            )
        )
        panel._workers_mgr.run_host_worker(worker)

    def _on_access_groups_loaded(self, data):
        panel = self.panel
        if panel.current_obj_type not in ("cluster", "host"):
            return
        panel._access_groups_cache = data
        table = panel.access_groups_table
        table.setSortingEnabled(False)
        table.setRowCount(len(data))
        for i, group in enumerate(data):
            gid = group.get("groupid", "")
            id_item = QTableWidgetItem(gid)
            id_item.setIcon(get_icon("group"))
            id_item.setData(Qt.UserRole, group)
            table.setItem(i, 0, id_item)
            table.setItem(i, 1, QTableWidgetItem(group.get("comment", "") or ""))
            members = group.get("users", "")
            if isinstance(members, list):
                members = ", ".join(members)
            table.setItem(i, 2, QTableWidgetItem(members or ""))
        table.setSortingEnabled(True)
        if data:
            panel.access_groups_stack.setCurrentIndex(1)
        else:
            panel.access_groups_loading.setText(tr("No groups"))
            panel.access_groups_stack.setCurrentIndex(0)

    def _fetch_access_roles(self, cfg):
        panel = self.panel
        if not cfg:
            panel.access_roles_loading.setText(tr("No data"))
            panel.access_roles_stack.setCurrentIndex(0)
            return
        panel.access_roles_loading.setText(tr("Loading..."))
        panel.access_roles_stack.setCurrentIndex(0)
        panel.access_roles_table.setRowCount(0)
        from ...backend import AccessRolesWorker
        worker = AccessRolesWorker(cfg)
        worker.signals.roles_ready.connect(
            lambda data, w=worker: (
                self._on_access_roles_loaded(data),
                panel._workers_mgr.discard_worker(w),
            )
        )
        worker.signals.roles_error.connect(
            lambda err, w=worker: (
                panel.access_roles_loading.setText(tr("Error: {err}").format(err=err[:80])),
                panel.access_roles_stack.setCurrentIndex(0),
                panel._workers_mgr.discard_worker(w),
            )
        )
        panel._workers_mgr.run_host_worker(worker)

    def _on_access_roles_loaded(self, data):
        panel = self.panel
        if panel.current_obj_type not in ("cluster", "host"):
            return
        panel._access_roles_cache = data
        table = panel.access_roles_table
        table.setSortingEnabled(False)
        table.setRowCount(len(data))
        for i, role in enumerate(data):
            rid = role.get("roleid", "")
            id_item = QTableWidgetItem(rid)
            id_item.setIcon(get_icon("role"))
            id_item.setData(Qt.UserRole, role)
            table.setItem(i, 0, id_item)
            privs = role.get("privs", "") or ""
            table.setItem(i, 1, QTableWidgetItem(privs))
            special = role.get("special", 0)
            if isinstance(special, str):
                special = int(special)
            sp_text = tr("Yes") if special else ""
            sp_item = QTableWidgetItem(sp_text)
            if special:
                sp_item.setForeground(QColor(Color.GRAY_400))
            table.setItem(i, 2, sp_item)
        table.setSortingEnabled(True)
        if data:
            panel.access_roles_stack.setCurrentIndex(1)
        else:
            panel.access_roles_loading.setText(tr("No roles"))
            panel.access_roles_stack.setCurrentIndex(0)

    def _fetch_access_acl(self, cfg):
        panel = self.panel
        if not cfg:
            panel.access_acl_loading.setText(tr("No data"))
            panel.access_acl_stack.setCurrentIndex(0)
            return
        panel.access_acl_loading.setText(tr("Loading..."))
        panel.access_acl_stack.setCurrentIndex(0)
        panel.access_acl_table.setRowCount(0)
        from ...backend import AccessAclWorker
        worker = AccessAclWorker(cfg)
        worker.signals.acl_ready.connect(
            lambda data, w=worker: (
                self._on_access_acl_loaded(data),
                panel._workers_mgr.discard_worker(w),
            )
        )
        worker.signals.acl_error.connect(
            lambda err, w=worker: (
                panel.access_acl_loading.setText(tr("Error: {err}").format(err=err[:80])),
                panel.access_acl_stack.setCurrentIndex(0),
                panel._workers_mgr.discard_worker(w),
            )
        )
        panel._workers_mgr.run_host_worker(worker)

    def _on_access_acl_loaded(self, data):
        panel = self.panel
        if panel.current_obj_type not in ("cluster", "host"):
            return
        table = panel.access_acl_table
        table.setSortingEnabled(False)
        table.setRowCount(len(data))
        for i, entry in enumerate(data):
            path = entry.get("path", "")
            path_item = QTableWidgetItem(path)
            path_item.setData(Qt.UserRole, entry)
            table.setItem(i, 0, path_item)
            table.setItem(i, 1, QTableWidgetItem(entry.get("type", "")))
            table.setItem(i, 2, QTableWidgetItem(entry.get("ugid", "")))
            table.setItem(i, 3, QTableWidgetItem(entry.get("roleid", "")))
            propagate = entry.get("propagate", 1)
            if isinstance(propagate, str):
                propagate = int(propagate)
            table.setItem(i, 4, QTableWidgetItem(tr("Yes") if propagate else tr("No")))
        table.setSortingEnabled(True)
        if data:
            panel.access_acl_stack.setCurrentIndex(1)
        else:
            panel.access_acl_loading.setText(tr("No permissions"))
            panel.access_acl_stack.setCurrentIndex(0)

    # --- User CRUD ---

    def _on_add_access_user(self):
        panel = self.panel
        cfg = getattr(panel, "_access_cfg", None)
        if not cfg:
            return
        groups = getattr(panel, "_access_groups_cache", [])
        from ..user_dialog import UserDialog
        dlg = UserDialog(panel, groups=groups)
        if dlg.exec() != UserDialog.Accepted:
            return
        params = dlg.get_params()
        if not params:
            return
        from ...backend import AccessUserCreateWorker
        worker = AccessUserCreateWorker(cfg, params)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self._fetch_access_users(cfg),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("User create failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    def _on_edit_access_user(self):
        panel = self.panel
        cfg = getattr(panel, "_access_cfg", None)
        if not cfg:
            return
        table = panel.access_users_table
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(panel, tr("Edit user"), tr("Select a user to edit"))
            return
        item = table.item(row, 0)
        if not item:
            return
        user = item.data(Qt.UserRole)
        if not user:
            return
        groups = getattr(panel, "_access_groups_cache", [])
        from ..user_dialog import UserDialog
        dlg = UserDialog(panel, user=user, groups=groups)
        if dlg.exec() != UserDialog.Accepted:
            return
        params = dlg.get_params()
        if not params:
            return
        userid = user.get("userid", "")
        from ...backend import AccessUserUpdateWorker
        worker = AccessUserUpdateWorker(cfg, userid, params)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self._fetch_access_users(cfg),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("User update failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    def _on_remove_access_user(self):
        panel = self.panel
        cfg = getattr(panel, "_access_cfg", None)
        if not cfg:
            return
        table = panel.access_users_table
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(panel, tr("Remove user"), tr("Select a user to remove"))
            return
        item = table.item(row, 0)
        if not item:
            return
        user = item.data(Qt.UserRole)
        if not user:
            return
        userid = user.get("userid", "")
        reply = QMessageBox.question(
            panel, tr("Remove user"),
            tr("Delete user \"{id}\"?").format(id=userid),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        from ...backend import AccessUserDeleteWorker
        worker = AccessUserDeleteWorker(cfg, userid)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self._fetch_access_users(cfg),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("User delete failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    # --- Token CRUD ---

    def _on_add_access_token(self):
        panel = self.panel
        cfg = getattr(panel, "_access_cfg", None)
        if not cfg:
            return
        users = getattr(panel, "_access_users_cache", [])
        if not users:
            panel.config_update_result.emit(tr("No users found"))
            return
        from ..token_dialog import TokenDialog
        dlg = TokenDialog(panel, users=users)
        if dlg.exec() != TokenDialog.Accepted:
            return
        userid = dlg.get_userid()
        tokenid = dlg.get_tokenid()
        params = dlg.get_params()
        if not userid or not tokenid:
            return
        from ...backend import AccessTokenCreateWorker
        worker = AccessTokenCreateWorker(cfg, userid, tokenid, params)
        worker.signals.result.connect(
            lambda msg, full, value, w=worker: (
                panel.config_update_result.emit(msg),
                self._show_token_value(full, value) if full else None,
                self._fetch_access_tokens(cfg),
                panel._workers_mgr.discard_worker(w),
            )
        )
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("Token create failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    def _on_edit_access_token(self):
        panel = self.panel
        cfg = getattr(panel, "_access_cfg", None)
        if not cfg:
            return
        table = panel.access_tokens_table
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(panel, tr("Edit token"), tr("Select a token to edit"))
            return
        item = table.item(row, 0)
        if not item:
            return
        token_data = item.data(Qt.UserRole)
        if not token_data:
            return
        userid = token_data.get("userid", "")
        from ..token_dialog import TokenDialog
        dlg = TokenDialog(panel, userid=userid, token=token_data)
        if dlg.exec() != TokenDialog.Accepted:
            return
        tokenid = dlg.get_tokenid()
        params = dlg.get_params()
        if not tokenid:
            return
        from ...backend import AccessTokenUpdateWorker
        worker = AccessTokenUpdateWorker(cfg, userid, tokenid, params)
        worker.signals.result.connect(
            lambda msg, full, value, w=worker: (
                panel.config_update_result.emit(msg),
                self._show_token_value(full, value) if full else None,
                self._fetch_access_tokens(cfg),
                panel._workers_mgr.discard_worker(w),
            )
        )
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("Token update failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    def _on_remove_access_token(self):
        panel = self.panel
        cfg = getattr(panel, "_access_cfg", None)
        if not cfg:
            return
        table = panel.access_tokens_table
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(panel, tr("Remove token"), tr("Select a token to remove"))
            return
        item = table.item(row, 0)
        if not item:
            return
        token_data = item.data(Qt.UserRole)
        if not token_data:
            return
        userid = token_data.get("userid", "")
        tokenid = token_data.get("tokenid", "")
        reply = QMessageBox.question(
            panel, tr("Remove token"),
            tr("Delete token \"{id}\" for user \"{user}\"?").format(id=tokenid, user=userid),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        from ...backend import AccessTokenDeleteWorker
        worker = AccessTokenDeleteWorker(cfg, userid, tokenid)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self._fetch_access_tokens(cfg),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("Token delete failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    def _show_token_value(self, full_tokenid, value):
        from ..token_dialog import TokenValueDialog
        dlg = TokenValueDialog(self.panel, full_tokenid, value)
        dlg.exec()

    # --- Group CRUD ---

    def _on_add_access_group(self):
        panel = self.panel
        cfg = getattr(panel, "_access_cfg", None)
        if not cfg:
            return
        from ..group_dialog import GroupDialog
        dlg = GroupDialog(panel)
        if dlg.exec() != GroupDialog.Accepted:
            return
        params = dlg.get_params()
        if not params:
            return
        from ...backend import AccessGroupCreateWorker
        worker = AccessGroupCreateWorker(cfg, params)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self._fetch_access_groups(cfg),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("Group create failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    def _on_edit_access_group(self):
        panel = self.panel
        cfg = getattr(panel, "_access_cfg", None)
        if not cfg:
            return
        table = panel.access_groups_table
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(panel, tr("Edit group"), tr("Select a group to edit"))
            return
        item = table.item(row, 0)
        if not item:
            return
        group = item.data(Qt.UserRole)
        if not group:
            return
        from ..group_dialog import GroupDialog
        dlg = GroupDialog(panel, group=group)
        if dlg.exec() != GroupDialog.Accepted:
            return
        params = dlg.get_params()
        if not params:
            return
        gid = group.get("groupid", "")
        from ...backend import AccessGroupUpdateWorker
        worker = AccessGroupUpdateWorker(cfg, gid, params)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self._fetch_access_groups(cfg),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("Group update failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    def _on_remove_access_group(self):
        panel = self.panel
        cfg = getattr(panel, "_access_cfg", None)
        if not cfg:
            return
        table = panel.access_groups_table
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(panel, tr("Remove group"), tr("Select a group to remove"))
            return
        item = table.item(row, 0)
        if not item:
            return
        group = item.data(Qt.UserRole)
        if not group:
            return
        gid = group.get("groupid", "")
        reply = QMessageBox.question(
            panel, tr("Remove group"),
            tr("Delete group \"{id}\"?").format(id=gid),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        from ...backend import AccessGroupDeleteWorker
        worker = AccessGroupDeleteWorker(cfg, gid)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self._fetch_access_groups(cfg),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("Group delete failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    # --- Role CRUD ---

    def _on_add_access_role(self):
        panel = self.panel
        cfg = getattr(panel, "_access_cfg", None)
        if not cfg:
            return
        from ..role_dialog import RoleDialog
        dlg = RoleDialog(panel)
        if dlg.exec() != RoleDialog.Accepted:
            return
        params = dlg.get_params()
        if not params:
            return
        from ...backend import AccessRoleCreateWorker
        worker = AccessRoleCreateWorker(cfg, params)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self._fetch_access_roles(cfg),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("Role create failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    def _on_edit_access_role(self):
        panel = self.panel
        cfg = getattr(panel, "_access_cfg", None)
        if not cfg:
            return
        table = panel.access_roles_table
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(panel, tr("Edit role"), tr("Select a role to edit"))
            return
        item = table.item(row, 0)
        if not item:
            return
        role = item.data(Qt.UserRole)
        if not role:
            return
        rid = role.get("roleid", "")
        from ..role_dialog import RoleDialog
        dlg = RoleDialog(panel, role=role)
        if dlg.exec() != RoleDialog.Accepted:
            return
        params = dlg.get_params()
        if not params:
            return
        from ...backend import AccessRoleUpdateWorker
        worker = AccessRoleUpdateWorker(cfg, rid, params)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self._fetch_access_roles(cfg),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("Role update failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    def _on_remove_access_role(self):
        panel = self.panel
        cfg = getattr(panel, "_access_cfg", None)
        if not cfg:
            return
        table = panel.access_roles_table
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(panel, tr("Remove role"), tr("Select a role to remove"))
            return
        item = table.item(row, 0)
        if not item:
            return
        role = item.data(Qt.UserRole)
        if not role:
            return
        special = role.get("special", 0)
        if isinstance(special, str):
            special = int(special)
        if special:
            QMessageBox.information(panel, tr("Remove role"), tr("Built-in roles cannot be deleted"))
            return
        rid = role.get("roleid", "")
        reply = QMessageBox.question(
            panel, tr("Remove role"),
            tr("Delete role \"{id}\"?").format(id=rid),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        from ...backend import AccessRoleDeleteWorker
        worker = AccessRoleDeleteWorker(cfg, rid)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self._fetch_access_roles(cfg),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("Role delete failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    # --- ACL CRUD ---

    def _on_add_access_acl(self):
        panel = self.panel
        cfg = getattr(panel, "_access_cfg", None)
        if not cfg:
            return
        roles = getattr(panel, "_access_roles_cache", [])
        users = getattr(panel, "_access_users_cache", [])
        groups = getattr(panel, "_access_groups_cache", [])
        tokens = []
        table = panel.access_tokens_table
        for r in range(table.rowCount()):
            item = table.item(r, 0)
            if item:
                td = item.data(Qt.UserRole)
                if td:
                    tokens.append({
                        "full-tokenid": f"{td.get('userid', '')}!{td.get('tokenid', '')}"
                    })
        from ..acl_dialog import AclDialog
        dlg = AclDialog(panel, roles=roles, users=users, groups=groups, tokens=tokens)
        if dlg.exec() != AclDialog.Accepted:
            return
        params = dlg.get_params()
        if not params:
            return
        from ...backend import AccessAclUpdateWorker
        worker = AccessAclUpdateWorker(cfg, params)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self._fetch_access_acl(cfg),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("Permission add failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)

    def _on_remove_access_acl(self):
        panel = self.panel
        cfg = getattr(panel, "_access_cfg", None)
        if not cfg:
            return
        table = panel.access_acl_table
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(panel, tr("Remove permissions"), tr("Select an entry to remove"))
            return
        item = table.item(row, 0)
        if not item:
            return
        entry = item.data(Qt.UserRole)
        if not entry:
            return
        path = entry.get("path", "")
        roleid = entry.get("roleid", "")
        etype = entry.get("type", "")
        ugid = entry.get("ugid", "")
        reply = QMessageBox.question(
            panel, tr("Remove permissions"),
            tr("Remove permission: role \"{role}\" for \"{ugid}\" on \"{path}\"?").format(
                role=roleid, ugid=ugid, path=path),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        params = {"path": path, "roles": roleid, "delete": 1}
        if etype == "user":
            params["users"] = ugid
        elif etype == "group":
            params["groups"] = ugid
        elif etype == "token":
            params["tokens"] = ugid
        from ...backend import AccessAclUpdateWorker
        worker = AccessAclUpdateWorker(cfg, params)
        worker.signals.result.connect(lambda msg, w=worker: (
            panel.config_update_result.emit(msg),
            self._fetch_access_acl(cfg),
            panel._workers_mgr.discard_worker(w),
        ))
        worker.signals.error.connect(lambda err, w=worker: (
            panel.config_update_result.emit(tr("Permission remove failed: {err}").format(err=err)),
            panel._workers_mgr.discard_worker(w),
        ))
        panel._workers_mgr.run_host_worker(worker)
