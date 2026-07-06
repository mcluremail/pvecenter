from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
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
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        tab.setWidget(self.panel.host_vm_list)
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
            [tr("Interface"), tr("Type"), tr("State"), "Method", "CIDR"],
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
        loading = loading_label()
        table = make_table(
            [tr("VM"), tr("Snapshot"), tr("Description"), tr("Created"), tr("Current")],
            [(QHeaderView.Stretch, None), (QHeaderView.Stretch, None),
             (QHeaderView.Stretch, None), (QHeaderView.Stretch, None),
             (QHeaderView.Interactive, 50)],
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
        from ..widgets.card_list import CardList
        host_columns = {
            "key": "node",
            "dot": "status",
            "title": "name",
            "fields": [
                ("status_text", 90),
                ("address", 110),
                ("cpu_text", 55),
                ("ram_text", 125),
                ("uptime_text", 125),
            ],
        }
        self.panel.host_summary_list = CardList(host_columns)

        cluster_columns = {
            "key": "name",
            "title": "name",
            "fields": [
                ("hosts_text", 70),
                ("vms_text", 70),
                ("cpu_text", 55),
                ("ram_text", 125),
            ],
        }
        self.panel.cluster_summary_list = CardList(cluster_columns)

        from PySide6.QtWidgets import QStackedWidget
        self.panel.summary_stack = QStackedWidget()
        self.panel.summary_stack.addWidget(self.panel.host_summary_list)
        self.panel.summary_stack.addWidget(self.panel.cluster_summary_list)

        tab = QScrollArea()
        tab.setWidgetResizable(True)
        tab.setWidget(self.panel.summary_stack)
        return tab

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
            card_items.append({
                "node": node.get("node", ""),
                "name": node_name,
                "status": status,
                "status_text": status_text(status),
                "address": cfg.get("host", "") if cfg else "",
                "cpu_text": f"{cpu_pct}%",
                "ram_text": f"{mem_gb}/{maxmem_gb} GiB",
                "uptime_text": uptime_str,
            })
        panel.host_summary_list.set_items(card_items)

    def show_cluster_folder(self, name):
        panel = self.panel
        panel.detail_label.setText(tr("Clusters"))
        panel.detail_sublabel.setText("")
        panel.detail_sublabel.setVisible(False)
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
        panel.summary_stack.setCurrentIndex(1)
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

    def show_standalone_folder(self, name):
        panel = self.panel
        panel.detail_label.setText(tr("Standalone hosts"))
        panel.detail_sublabel.setText("")
        panel.detail_sublabel.setVisible(False)
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
        for node in panel.all_nodes:
            host_name = node.get("host_name", "")
            cfg = panel._cfg_by_name.get(host_name)
            if cfg and cfg.get("cluster") == cluster_name:
                hosts.append(node)
        panel.detail_label.setText(cluster_name)
        hosts_count = len(hosts)
        running = sum(1 for h in hosts if h.get("status") == "online")
        panel.detail_sublabel.setText(f"{hosts_count} {tr('hosts')} · {running} {tr('online')}")
        panel.detail_sublabel.setVisible(True)
        panel.tabs.setTabVisible(TabIndex.MONITOR, False)
        panel.tabs.setTabVisible(TabIndex.HARDWARE, False)
        panel.tabs.setTabVisible(TabIndex.HOST_VMS, False)
        panel.tabs.setTabVisible(TabIndex.SUMMARY, True)
        panel.tabs.setTabVisible(TabIndex.POOL_VMS, False)
        panel.tabs.setCurrentIndex(TabIndex.SUMMARY)
        self.populate_host_summary(hosts)

    def show_host_info(self, host_name, host_data):
        panel = self.panel
        node = next((n for n in panel.all_nodes if n.get("node") == host_name), None)
        display_name = node.get("_display_name") if node else host_name
        panel.detail_label.setText(display_name)
        panel.detail_sublabel.setText(" · ".join(self._host_subtitle(host_data, host_name)))
        panel.detail_sublabel.setVisible(True)

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
            card_updates.append({
                "node": node.get("node", ""),
                "name": node_name,
                "status": status,
                "status_text": status_text(status),
                "address": cfg.get("host", "") if cfg else "",
                "cpu_text": f"{cpu_pct}%",
                "ram_text": f"{mem_gb}/{maxmem_gb} GiB",
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
