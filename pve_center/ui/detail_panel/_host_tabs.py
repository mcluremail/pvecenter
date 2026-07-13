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
        cluster_storages = [s for s in panel.all_storages if s.get("cluster")]
        if not cluster_storages:
            cluster_name = hosts[0].get("host_name", "") if hosts else ""
            cfg = panel._cfg_by_name.get(cluster_name)
            cn = cfg.get("cluster") if cfg else None
            if cn:
                cluster_storages = [s for s in panel.all_storages if s.get("cluster") == cn]
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
                if cfg.get("cluster_rep"):
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
        panel.tabs.setTabVisible(TabIndex.POOL_VMS, False)
        panel.tabs.setCurrentIndex(TabIndex.SUMMARY)
        self.populate_host_summary(hosts)
        self._populate_cluster_summary_cards(hosts)
        self._populate_cluster_vms(cluster_name, hosts)
        self._populate_cluster_storages(cluster_name)
        self._fetch_cluster_snapshots(hosts)
        self._fetch_cluster_health(hosts)
        self._fetch_backup_jobs(cluster_cfg, cluster_name)

    def show_host_info(self, host_name, host_data):
        panel = self.panel
        node = next((n for n in panel.all_nodes if n.get("node") == host_name), None)
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

            vms_count = sum(1 for v in panel.all_vms if v.get("node") == host_name)
            vms_running = sum(1 for v in panel.all_vms
                              if v.get("node") == host_name and v.get("status") == "running")
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
                self._fetch_backup_jobs(host_cfg, host_name)

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

            vms_count = sum(1 for v in panel.all_vms if v.get("node") == host_name)
            vms_running = sum(1 for v in panel.all_vms
                              if v.get("node") == host_name and v.get("status") == "running")
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
        panel._workers_mgr.run_host_worker(worker)

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
        panel._workers_mgr.run_host_worker(worker)

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
            lambda nn, data, w=worker: (
                self.on_host_health(nn, data),
                panel._workers_mgr.discard_worker(w)
            )
        )
        worker.signals.health_error.connect(
            lambda nn, err, w=worker: (
                self.on_host_health(nn, {"status": "error", "issues": [err], "warnings": []}),
                panel._workers_mgr.discard_worker(w)
            )
        )
        panel._workers_mgr.run_host_worker(worker)

    def on_host_health(self, node_name, health):
        panel = self.panel
        if panel.current_obj_type != "host" or panel.current_obj_name != node_name:
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
        panel._workers_mgr.run_host_worker(worker)

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
        panel._workers_mgr.run_host_worker(worker)

    def on_host_snapshots(self, node_name, snapshots):
        panel = self.panel
        if panel.current_obj_type != "host" or panel.current_obj_name != node_name:
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
            })
        panel.host_vm_list.set_items(card_items)
        self._populate_vm_stats(vms)

    def _populate_cluster_storages(self, cluster_name):
        panel = self.panel
        storages = [s for s in panel.all_storages if s.get("cluster") == cluster_name]
        if not storages:
            storages = [s for s in panel.all_storages
                        if not s.get("cluster")
                        and any(s.get("node") == h.get("node") for h in panel.all_nodes
                                if panel._cfg_by_name.get(h.get("host_name", ""), {}).get("cluster") == cluster_name)]
        from ..widgets.card_list import CardList
        if not hasattr(panel, "storage_list") or panel.storage_list is None:
            panel.storage_list = CardList({
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
            })
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
            })
        panel.storage_list.set_items(card_items)

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
                lambda nn, err, w=worker: panel._workers_mgr.discard_worker(w)
            )
            panel._workers_mgr.run_host_worker(worker)

    def _on_cluster_snapshots(self, node_name, data):
        panel = self.panel
        if panel.current_obj_type != "cluster":
            return
        tree = panel.host_snapshots_tree
        for vmid, snaps in (data or {}).items():
            vm_label = tr("VM {vmid}").format(vmid=vmid)
            vm_item = QTreeWidgetItem(tree, [vm_label, "", "", "", "", ""])
            vm_item.setIcon(0, get_icon("snapshot"))
            vm_item.setExpanded(False)
            for snap in snaps:
                name = snap.get("name", "")
                desc = snap.get("description", "") or ""
                ctime = snap.get("snaptime", 0)
                created = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M") if ctime else ""
                parent = snap.get("parent", "") or ""
                size = snap.get("size", 0) or 0
                size_text = f"{round(size / (1024**3), 1)} GiB" if size else ""
                QTreeWidgetItem(vm_item, [name, desc, created, "", size_text, parent])
        tree.resizeColumnToContents(0)
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
            return [s for s in panel.all_storages if s.get("node") == ctx]
        return panel.all_storages

    def _on_add_backup_job(self):
        panel = self.panel
        cfg = getattr(panel, "_backup_jobs_cfg", None)
        if not cfg:
            return
        pve_major = getattr(panel, "_backup_jobs_pve_major", 7)
        storages = self._get_backup_jobs_storages()
        from ..backup_job_dialog import BackupJobDialog
        dlg = BackupJobDialog(panel, storages=storages, is_pve8=pve_major >= 8)
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
        dlg = BackupJobDialog(panel, storages=storages, job=job, is_pve8=pve_major >= 8)
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
