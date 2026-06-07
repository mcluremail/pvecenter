from PySide6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QVBoxLayout, QHBoxLayout,
                               QWidget, QAbstractItemView, QPushButton)
from PySide6.QtCore import Signal, QSettings, Qt, QSize, QTimer
from PySide6.QtGui import QIcon
from collections import defaultdict
from datetime import timedelta

from .icons import get_icon, init_icons, _make_loading_icon
from datetime import timedelta

from .icons import get_icon, init_icons, _make_loading_icon

VM_KEY_ROLE = Qt.UserRole + 1
ITEM_KEY_ROLE = Qt.UserRole + 2

def _vm_count_str(vms):
    total = len(vms)
    running = sum(1 for v in vms if v.get("status") == "running")
    return f"[{running}/{total}]"

class TreePanel(QWidget):
    item_selected = Signal(str, str, dict)
    add_server_requested_context = Signal(str)

    def __init__(self, nodes_cfg):
        super().__init__()
        self.nodes_cfg = nodes_cfg
        self.all_nodes = []
        self.all_vms = []

        self.settings = QSettings("PVECenter", "Dashboard")

        self.tree = QTreeWidget()
        self.tree.setColumnCount(1)
        self.tree.setHeaderHidden(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setIndentation(20)
        self.tree.setIconSize(QSize(22, 22))
        self.tree.setRootIsDecorated(True)
        self.tree.setAnimated(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.currentItemChanged.connect(self._on_current_item_changed)
        self._building = False
        self._nav_timer = QTimer()
        self._nav_timer.setSingleShot(True)
        self._nav_timer.setInterval(300)
        self._nav_timer.timeout.connect(self._flush_nav)

        self._loading_hosts = set()
        self._spinner_angle = 0
        self._spin_timer = QTimer()
        self._spin_timer.setInterval(150)
        self._spin_timer.timeout.connect(self._tick_spinner)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(4, 2, 4, 0)
        init_icons()
        self._toggle_btn = QPushButton()
        self._toggle_btn.setIcon(get_icon("expand"))
        self._toggle_btn.setFixedSize(22, 22)
        self._toggle_btn.setToolTip("Развернуть всё")
        self._toggled = False
        self._toggle_btn.clicked.connect(self._toggle_expand)
        btn_layout.addStretch()
        btn_layout.addWidget(self._toggle_btn)
        layout.addLayout(btn_layout)

        layout.addWidget(self.tree)
        self.setLayout(layout)

    def _toggle_expand(self):
        self._toggled = not self._toggled
        if self._toggled:
            self.tree.expandAll()
            self._toggle_btn.setIcon(get_icon("collapse"))
            self._toggle_btn.setToolTip("Свернуть всё")
        else:
            self.tree.collapseAll()
            self._toggle_btn.setIcon(get_icon("expand"))
            self._toggle_btn.setToolTip("Развернуть всё")

    def _make_section_item(self, parent, label):
        item = QTreeWidgetItem(parent)
        item.setData(0, ITEM_KEY_ROLE, ("section", label))
        item.setText(0, label)
        item.setIcon(0, get_icon("folder"))
        item.setExpanded(True)

        context_map = {"Кластеры": "cluster", "Отдельные хосты": "standalone"}
        ctx = context_map.get(label, "")
        if not ctx:
            return item

        w = QWidget()
        w.setAttribute(Qt.WA_TranslucentBackground)
        hbox = QHBoxLayout(w)
        hbox.setContentsMargins(0, 0, 4, 0)
        hbox.addStretch()
        btn = QPushButton("+")
        btn.setFixedSize(20, 20)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setStyleSheet(
            "QPushButton { border: 1px solid #cbd5e1; border-radius: 3px; "
            "background: #f1f5f9; font-size: 13px; font-weight: bold; "
            "color: #475569; padding: 0; outline: none; }"
            "QPushButton:hover { background: #e2e8f0; border-color: #94a3b8; color: #334155; }"
        )
        btn.setToolTip(f"Добавить хост в «{label}»")
        btn.clicked.connect(lambda checked, c=ctx: self.add_server_requested_context.emit(c))
        hbox.addWidget(btn)
        self.tree.setItemWidget(item, 0, w)

        return item

    def _tick_spinner(self):
        self._spinner_angle = (self._spinner_angle + 45) % 360
        icon = _make_loading_icon(self._spinner_angle)
        def spin(item):
            key = item.data(0, ITEM_KEY_ROLE)
            if key and isinstance(key, tuple):
                if key[0] == "host" and key[1] in self._loading_hosts:
                    item.setIcon(0, icon)
                elif key[0] == "cluster" and f"cluster:{key[1]}" in self._loading_hosts:
                    item.setIcon(0, icon)
            for i in range(item.childCount()):
                spin(item.child(i))
        for i in range(self.tree.topLevelItemCount()):
            spin(self.tree.topLevelItem(i))

    def update_data(self, all_nodes, all_vms, all_storages=None):
        self.all_nodes = all_nodes
        self.all_vms = all_vms
        self.all_storages = all_storages or []
        self._loading_hosts.clear()
        self._spin_timer.stop()
        self._build_tree()
        self._restore_expanded_state()
        self._sync_toggle_button()

    def start_loading(self):
        self.tree.clear()
        self._building = True
        self._loading_hosts.clear()

        hosts_by_cluster = {}
        standalone = []
        for cfg in self.nodes_cfg:
            if cfg.get("skip", False):
                continue
            name = cfg.get("name", "")
            cluster = cfg.get("cluster")
            if cluster and cluster not in (False, None, "Standalone"):
                hosts_by_cluster.setdefault(cluster, []).append(name)
            else:
                standalone.append(name)

        if hosts_by_cluster:
            folder = self._make_section_item(self.tree, "Кластеры")
            for cl_name in sorted(hosts_by_cluster.keys(), key=str.lower):
                cl_item = QTreeWidgetItem(folder)
                cl_item.setText(0, cl_name)
                cl_item.setIcon(0, _make_loading_icon(0))
                cl_item.setData(0, ITEM_KEY_ROLE, ("cluster", cl_name))
                cl_item.setExpanded(True)
                self._loading_hosts.add(f"cluster:{cl_name}")

        if standalone:
            folder = self._make_section_item(self.tree, "Отдельные хосты")
            for hname in sorted(standalone, key=str.lower):
                hi = QTreeWidgetItem(folder)
                hi.setText(0, hname)
                hi.setIcon(0, _make_loading_icon(0))
                hi.setData(0, ITEM_KEY_ROLE, ("host", hname))
                self._loading_hosts.add(hname)

        self.tree.expandAll()
        self._building = False
        self._spin_timer.start()

    def _sync_toggle_button(self):
        if self.tree.topLevelItemCount() == 0:
            return
        expanded = all(self._subtree_expanded(self.tree.topLevelItem(i))
                       for i in range(self.tree.topLevelItemCount()))
        self._toggled = expanded
        if expanded:
            self._toggle_btn.setIcon(get_icon("collapse"))
            self._toggle_btn.setToolTip("Свернуть всё")
        else:
            self._toggle_btn.setIcon(get_icon("expand"))
            self._toggle_btn.setToolTip("Развернуть всё")

    @staticmethod
    def _subtree_expanded(item):
        if not item.isExpanded() and item.childCount() > 0:
            return False
        for i in range(item.childCount()):
            if not TreePanel._subtree_expanded(item.child(i)):
                return False
        return True

    def _on_current_item_changed(self, current, previous):
        if self._building or not current:
            return
        self._nav_timer.start()

    def _flush_nav(self):
        item = self.tree.currentItem()
        if item:
            self._on_item_clicked(item, 0)

    def _add_vm_item(self, parent, vm):
        vm_item = QTreeWidgetItem(parent)
        vm_name = vm.get("name") or f"VM {vm.get('vmid')}"
        vm_item.setText(0, vm_name)
        vm_item.setIcon(0, get_icon("vm", vm.get("status")))
        vm_item.setData(0, VM_KEY_ROLE, (vm.get("host_name", ""), vm.get("vmid", 0)))
        cpu = vm.get("cpu", 0)
        if isinstance(cpu, float):
            cpu_pct = round(cpu * 100, 1)
        else:
            cpu_pct = cpu
        mem = vm.get("mem", 0) or 0
        maxmem = vm.get("maxmem", 1) or 1
        mem_pct = int((mem / maxmem) * 100) if maxmem else 0
        status = vm.get("status", "")
        vm_item.setToolTip(0, f"Статус: {status}\nЦП: {cpu_pct}%\nRAM: {mem_pct}%")
        return vm_item

    def _build_tree(self):
        self._building = True
        self.tree.clear()

        cluster_nodes = defaultdict(list)
        standalone_nodes = []

        for node in self.all_nodes:
            host_name = node.get("host_name", "")
            cfg = next((c for c in self.nodes_cfg if c["name"] == host_name), None)
            cluster_name = cfg.get("cluster") if cfg else None
            if cluster_name and cluster_name not in (False, None, "Standalone"):
                cluster_nodes[cluster_name].append(node)
            else:
                standalone_nodes.append(node)

        if cluster_nodes:
            cluster_folder = self._make_section_item(self.tree, "Кластеры")

            for cluster_name in sorted(cluster_nodes.keys(), key=str.lower):
                cl_item = QTreeWidgetItem(cluster_folder)
                vms_in_cl = [vm for vm in self.all_vms
                             if any(vm.get("node") == n.get("node") for n in cluster_nodes[cluster_name])]
                cl_item.setText(0, f"{cluster_name}  {_vm_count_str(vms_in_cl)}")
                cl_item.setIcon(0, get_icon("cluster"))
                cl_item.setData(0, ITEM_KEY_ROLE, ("cluster", cluster_name))
                cl_item.setExpanded(True)

                hosts_in_cl = cluster_nodes[cluster_name]
                for node in sorted(hosts_in_cl, key=lambda n: (n.get("_display_name") or n.get("node", "")).lower()):
                    node_name = node.get("node", "?")
                    display_name = node.get("_display_name") or node_name
                    vms_on_node = [vm for vm in vms_in_cl if vm.get("node") == node_name and vm.get("host_name") == node.get("host_name")]
                    host_item = QTreeWidgetItem(cl_item)
                    host_item.setText(0, f"{display_name}  {_vm_count_str(vms_on_node)}")
                    host_item.setIcon(0, get_icon("host", node.get("status")))
                    host_item.setData(0, ITEM_KEY_ROLE, ("host", node_name))
                    cpu = node.get("cpu", 0)
                    if isinstance(cpu, float):
                        cpu = round(cpu * 100, 1)
                    mem = node.get("mem", 0) or 0
                    maxmem = node.get("maxmem", 1) or 1
                    mem_pct = int((mem / maxmem) * 100) if maxmem else 0
                    uptime = node.get("uptime", 0)
                    uptime_str = str(timedelta(seconds=int(uptime))) if uptime else "?"
                    host_item.setToolTip(0,
                        f"ЦП: {cpu}%\nRAM: {mem_pct}%\n"
                        f"Аптайм: {uptime_str}"
                    )


                pool_groups = defaultdict(list)
                no_pool_vms = []
                for vm in vms_in_cl:
                    pool = vm.get("pool")
                    if pool and pool not in ("", "No pool"):
                        pool_groups[pool].append(vm)
                    else:
                        no_pool_vms.append(vm)

                for pool_name in sorted(pool_groups.keys(), key=str.lower):
                    vms_list = pool_groups[pool_name]
                    pool_item = QTreeWidgetItem(cl_item)
                    pool_item.setText(0, f"{pool_name}  {_vm_count_str(vms_list)}")
                    pool_item.setIcon(0, get_icon("pool"))
                    pool_item.setData(0, ITEM_KEY_ROLE, ("pool", pool_name))
                    pool_item.setExpanded(True)

                    for vm in sorted(vms_list, key=lambda v: (v.get("name") or f"VM {v.get('vmid')}").lower()):
                        self._add_vm_item(pool_item, vm)

                for vm in sorted(no_pool_vms, key=lambda v: (v.get("name") or f"VM {v.get('vmid')}").lower()):
                    self._add_vm_item(cl_item, vm)

        if standalone_nodes:
            st_folder = self._make_section_item(self.tree, "Отдельные хосты")

            for node in sorted(standalone_nodes, key=lambda n: (n.get("_display_name") or n.get("node", "")).lower()):
                node_name = node.get("node", "?")
                display_name = node.get("_display_name") or node_name
                host_name = node.get("host_name", "")
                vms_on_host = [vm for vm in self.all_vms
                               if vm.get("node") == node_name
                               and vm.get("host_name") == host_name]
                host_item = QTreeWidgetItem(st_folder)
                host_item.setText(0, f"{display_name}  {_vm_count_str(vms_on_host)}")
                host_item.setIcon(0, get_icon("host", node.get("status")))
                host_item.setData(0, ITEM_KEY_ROLE, ("host", node_name))
                host_item.setExpanded(True)
                cpu = node.get("cpu", 0)
                if isinstance(cpu, float):
                    cpu = round(cpu * 100, 1)
                mem = node.get("mem", 0) or 0
                maxmem = node.get("maxmem", 1) or 1
                mem_pct = int((mem / maxmem) * 100) if maxmem else 0
                uptime = node.get("uptime", 0)
                uptime_str = str(timedelta(seconds=int(uptime))) if uptime else "?"
                host_item.setToolTip(0,
                    f"ЦП: {cpu}%\nRAM: {mem_pct}%\nАптайм: {uptime_str}"
                )

                vms_on_host = [vm for vm in self.all_vms if vm.get("node") == node_name]
                pool_groups = defaultdict(list)
                no_pool_vms = []
                for vm in vms_on_host:
                    pool = vm.get("pool")
                    if pool and pool not in ("", "No pool"):
                        pool_groups[pool].append(vm)
                    else:
                        no_pool_vms.append(vm)

                for pool_name in sorted(pool_groups.keys(), key=str.lower):
                    pool_item = QTreeWidgetItem(host_item)
                    pool_item.setText(0, f"{pool_name}  {_vm_count_str(pool_groups[pool_name])}")
                    pool_item.setIcon(0, get_icon("pool"))
                    pool_item.setData(0, ITEM_KEY_ROLE, ("pool", pool_name))
                    pool_item.setExpanded(True)

                    for vm in sorted(pool_groups[pool_name], key=lambda v: (v.get("name") or f"VM {v.get('vmid')}").lower()):
                        self._add_vm_item(pool_item, vm)

                for vm in sorted(no_pool_vms, key=lambda v: (v.get("name") or f"VM {v.get('vmid')}").lower()):
                    self._add_vm_item(host_item, vm)

        # Хранилища
        if self.all_storages:
            st_folder = self._make_section_item(self.tree, "Хранилища")

            # Группируем storage по кластеру для дерева
            cluster_storages = defaultdict(list)
            standalone_storages = []
            for st in self.all_storages:
                cluster = st.get("cluster")
                if cluster:
                    cluster_storages[cluster].append(st)
                else:
                    standalone_storages.append(st)

            seen_standalone_keys = set()
            for cluster_name in sorted(cluster_storages.keys(), key=str.lower):
                cl_item = QTreeWidgetItem(st_folder)
                cl_item.setText(0, cluster_name)
                cl_item.setIcon(0, get_icon("cluster"))
                cl_item.setData(0, ITEM_KEY_ROLE, ("storage_section", cluster_name))
                cl_item.setExpanded(True)

                seen_names = set()
                for st in cluster_storages[cluster_name]:
                    sname = st.get("storage", "")
                    if sname not in seen_names:
                        seen_names.add(sname)
                        si = QTreeWidgetItem(cl_item)
                        si.setText(0, f"{sname} (@{cluster_name})")
                        si.setIcon(0, get_icon("storage"))
                        si.setData(0, ITEM_KEY_ROLE, ("storage", sname, cluster_name))

            if standalone_storages:
                so_item = QTreeWidgetItem(st_folder)
                so_item.setText(0, "Отдельные")
                so_item.setIcon(0, get_icon("folder"))
                so_item.setData(0, ITEM_KEY_ROLE, ("storage_section", "Отдельные"))
                so_item.setExpanded(True)

                seen_keys = set()
                for st in standalone_storages:
                    sname = st.get("storage", "")
                    shost = st.get("host_name", "")
                    key = (sname, shost)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        si = QTreeWidgetItem(so_item)
                        si.setText(0, f"{sname} ({shost})")
                        si.setIcon(0, get_icon("storage"))
                        si.setData(0, ITEM_KEY_ROLE, ("storage", sname, shost))

        self.tree.expandAll()
        self._building = False

    def update_node_statuses(self, all_nodes, all_vms):
        self._loading_hosts.clear()
        self._spin_timer.stop()
        def traverse(item):
            for i in range(item.childCount()):
                child = item.child(i)
                vm_key = child.data(0, VM_KEY_ROLE)
                if vm_key is not None:
                    host_name, vmid = vm_key
                    vm = next((v for v in all_vms
                               if v.get("host_name") == host_name and v.get("vmid") == vmid), None)
                    if vm:
                        child.setIcon(0, get_icon("vm", vm.get("status")))
                    continue

                key = child.data(0, ITEM_KEY_ROLE)
                if key and isinstance(key, tuple) and key[0] == "host":
                    host_name = key[1]
                    host = next((n for n in all_nodes if n.get("node") == host_name or n.get("host_name") == host_name), None)
                    if host:
                        child.setIcon(0, get_icon("host", host.get("status")))
                    traverse(child)
                else:
                    traverse(child)
        for i in range(self.tree.topLevelItemCount()):
            traverse(self.tree.topLevelItem(i))

    @staticmethod
    def _strip_count(text):
        """Убирает суффикс VM-счётчика вида '[3/5]' для стабильных путей."""
        import re as _re
        return _re.sub(r'\s+\[\d+/\d+\]$', '', text)

    def _save_expanded_state(self):
        key = "expandedTreePaths"
        paths = []
        def collect_paths(item, path=""):
            label = self._strip_count(item.text(0))
            current = path + "|" + label if path else label
            if item.isExpanded():
                paths.append(current)
            for i in range(item.childCount()):
                collect_paths(item.child(i), current)
        for i in range(self.tree.topLevelItemCount()):
            collect_paths(self.tree.topLevelItem(i))
        self.settings.setValue(key, paths)

    def _restore_expanded_state(self):
        key = "expandedTreePaths"
        saved_paths = self.settings.value(key, [])
        if not saved_paths:
            return
        def match_and_expand(item, path=""):
            label = self._strip_count(item.text(0))
            current = path + "|" + label if path else label
            if current in saved_paths:
                item.setExpanded(True)
            else:
                item.setExpanded(False)
            for i in range(item.childCount()):
                match_and_expand(item.child(i), current)
        for i in range(self.tree.topLevelItemCount()):
            match_and_expand(self.tree.topLevelItem(i))

    def save_state(self):
        self._save_expanded_state()

    def select_first_item(self):
        if self.tree.topLevelItemCount() > 0:
            item = self.tree.topLevelItem(0)
            self.tree.setCurrentItem(item)
            self._on_item_clicked(item, 0)

    def find_item_by_key(self, key_data):
        def search(item):
            if item.data(0, VM_KEY_ROLE) == key_data:
                return item
            if item.data(0, ITEM_KEY_ROLE) == key_data:
                return item
            for i in range(item.childCount()):
                found = search(item.child(i))
                if found:
                    return found
            return None
        for i in range(self.tree.topLevelItemCount()):
            found = search(self.tree.topLevelItem(i))
            if found:
                return found
        return None

    def get_current_item_key(self):
        item = self.tree.currentItem()
        if not item:
            return None
        vm_key = item.data(0, VM_KEY_ROLE)
        if vm_key is not None:
            return vm_key
        return item.data(0, ITEM_KEY_ROLE)

    def _on_item_clicked(self, item, column):
        self._nav_timer.stop()

        vm_key = item.data(0, VM_KEY_ROLE)
        if vm_key is not None:
            host_name, vmid = vm_key
            vm = next((v for v in self.all_vms
                       if v.get("host_name") == host_name and v.get("vmid") == vmid), None)
            if vm is not None:
                self.item_selected.emit("vm", vm.get("name") or f"VM {vmid}", vm)
                return
            self.item_selected.emit("unknown", str(vmid), {})
            return

        key = item.data(0, ITEM_KEY_ROLE)
        if key is None or not isinstance(key, tuple):
            self.item_selected.emit("unknown", "", {})
            return

        item_type = key[0]
        item_name = key[1] if len(key) > 1 else ""

        if item_type == "section":
            if item_name == "Кластеры":
                self.item_selected.emit("cluster_folder", item_name, {})
            elif item_name == "Отдельные хосты":
                self.item_selected.emit("standalone_folder", item_name, {})
            elif item_name == "Хранилища":
                self.item_selected.emit("storage_folder", item_name, {})
            return

        if item_type == "cluster":
            self.item_selected.emit("cluster", item_name, {})
            return

        if item_type == "host":
            host_data = next((n for n in self.all_nodes if n.get("node") == item_name), None)
            self.item_selected.emit("host", item_name, host_data or {})
            return

        if item_type == "pool":
            self.item_selected.emit("pool", item_name, {})
            return

        if item_type == "storage":
            data = {"storage_name": item_name}
            if len(key) >= 3:
                val = key[2]
                # Если третий элемент похож на хост-имя (с точками или длинное) — это standalone
                if val and (val.count(".") > 0 or "/" in val):
                    data["host_name"] = val
                else:
                    data["cluster"] = val
            self.item_selected.emit("storage", item_name, data)
            return

        if item_type == "storage_section":
            self.item_selected.emit("storage_section", item_name, {})
            return

        self.item_selected.emit("unknown", item_name, {})