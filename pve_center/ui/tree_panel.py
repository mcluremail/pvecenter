import json
import re
from collections import defaultdict
from datetime import timedelta

from PySide6.QtCore import QMimeData, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QDrag
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from ..config import load_ui_state, save_ui_state
from .i18n import tr
from .icons import get_icon, init_icons, make_loading_icon
from .theme import Color
from .utils import build_cfg_index, status_text
from .vm_actions import VM_ACTION_ICONS

VM_KEY_ROLE = Qt.UserRole + 1
ITEM_KEY_ROLE = Qt.UserRole + 2

def _vm_count_str(vms):
    total = len(vms)
    running = sum(1 for v in vms if v.get("status") == "running")
    return f"[{running}/{total}]"


def _node_tooltip(node):
    cpu = node.get("cpu", 0)
    if isinstance(cpu, float):
        cpu = round(cpu * 100, 1)
    mem = node.get("mem", 0) or 0
    maxmem = node.get("maxmem", 0) or 0
    mem_pct = int(max(0, min(100, (mem / maxmem) * 100))) if maxmem else 0
    uptime = node.get("uptime", 0)
    uptime_str = str(timedelta(seconds=int(uptime))) if uptime else "?"
    return tr("CPU") + f": {cpu}%\n" + tr("RAM") + f": {mem_pct}%\n" + tr("Uptime") + f": {uptime_str}"


GROUP_MIME = "application/x-pvecenter-hostgroup"


class GroupTreeWidget(QTreeWidget):
    """QTreeWidget with drag&drop for host groups (B16).

    Dragging a host/cluster item onto a group item emits
    group_move_requested(kind, name, group); dropping onto the
    Clusters/Standalone hosts section removes the item from its group.
    The tree is never mutated directly — the panel rebuilds it.
    """

    def __init__(self, panel):
        super().__init__()
        self._panel = panel
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def _drag_payload(self, item):
        """Payload dict for a draggable item, or None if not draggable."""
        if item is None:
            return None
        key = item.data(0, ITEM_KEY_ROLE)
        if not isinstance(key, tuple):
            return None
        if key[0] == "host" and len(key) > 2:
            return {"kind": "host", "name": key[2]}
        if key[0] == "cluster" and len(key) > 1:
            return {"kind": "cluster", "name": key[1]}
        return None

    def startDrag(self, supported_actions):
        payload = self._drag_payload(self.currentItem())
        if not payload:
            return
        mime = QMimeData()
        mime.setData(GROUP_MIME, json.dumps(payload).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def _decode(self, event):
        mime = event.mimeData()
        if mime is None or not mime.hasFormat(GROUP_MIME):
            return None
        try:
            payload = json.loads(bytes(mime.data(GROUP_MIME)).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        if payload.get("kind") not in ("host", "cluster") or not payload.get("name"):
            return None
        return payload

    def _drop_group(self, item):
        """Group name for the drop target item:
        group item -> its name; Clusters/Standalone hosts section -> ''
        (remove from group); host/cluster directly inside a group -> that
        group; anything else -> None (drop not allowed)."""
        while item is not None:
            key = item.data(0, ITEM_KEY_ROLE)
            if isinstance(key, tuple):
                if key[0] == "group":
                    return key[1]
                if key[0] == "section":
                    if key[1] in (tr("Clusters"), tr("Standalone hosts")):
                        return ""
                    return None
                if key[0] in ("host", "cluster"):
                    parent = item.parent()
                    if parent is not None:
                        pkey = parent.data(0, ITEM_KEY_ROLE)
                        if isinstance(pkey, tuple) and pkey[0] == "group":
                            return pkey[1]
                    return None
            item = item.parent()
        return None

    def dragEnterEvent(self, event):
        if self._decode(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if not self._decode(event):
            event.ignore()
            return
        if self._drop_group(self.itemAt(event.position().toPoint())) is None:
            event.ignore()
        else:
            event.acceptProposedAction()

    def dropEvent(self, event):
        payload = self._decode(event)
        if not payload:
            event.ignore()
            return
        group = self._drop_group(self.itemAt(event.position().toPoint()))
        if group is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self._panel.group_move_requested.emit(payload["kind"], payload["name"], group)


class TreePanel(QWidget):
    item_selected = Signal(str, str, object)
    add_server_requested_context = Signal(str)
    host_remove_requested = Signal(str, str)
    host_token_refresh_requested = Signal(str)
    host_trust_ssl_changed = Signal(str, bool)
    vm_create_requested = Signal(str, str)
    vm_delete_requested = Signal(str, str, int)
    vm_action_requested = Signal(str, str, int, str)
    vm_migrate_requested = Signal(str, str, int)
    vm_clone_requested = Signal(str, str, int)
    vm_convert_requested = Signal(str, str, int, str)  # (host_name, node, vmid, direction)
    vm_clone_from_template_requested = Signal(str, str)  # (host_name, node)
    vm_ha_add_requested = Signal(str, str, int)  # (host_name, node, vmid)
    vm_ha_remove_requested = Signal(str, str, int)  # (host_name, node, vmid)
    console_requested = Signal(str, str, int)
    bulk_vm_action_requested = Signal(list, str)  # ([(host_name, vmid, node)], action)
    group_move_requested = Signal(str, str, str)  # kind ("host"|"cluster"), name, group ("" = none)
    group_rename_requested = Signal(str, str)     # old group name, new group name
    group_delete_requested = Signal(str)          # group name

    def __init__(self, nodes_cfg):
        super().__init__()
        self.nodes_cfg = nodes_cfg
        self._cfg_by_name = build_cfg_index(self.nodes_cfg)
        self.all_nodes = []
        self._node_repo = None
        self.all_vms = []
        self._vm_repo = None

        self._building = False
        self._nav_timer = QTimer()
        self._nav_timer.setSingleShot(True)
        self._nav_timer.setInterval(300)
        self._nav_timer.timeout.connect(self._flush_nav)

        self._rebuild_timer = QTimer()
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.setInterval(150)
        self._rebuild_timer.timeout.connect(self._do_rebuild)

        self._loading_hosts = set()
        self._spinner_angle = 0
        self._spin_timer = QTimer()
        self._spin_timer.setInterval(150)
        self._spin_timer.timeout.connect(self._tick_spinner)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        init_icons()

        self._toggle_btn = QToolButton()
        self._toggle_btn.setIcon(get_icon("expand"))
        self._toggle_btn.setFixedSize(22, 22)
        self._toggle_btn.setIconSize(QSize(14, 14))
        self._toggle_btn.setToolTip(tr("Expand all"))
        self._toggle_btn.setAutoRaise(True)
        self._toggled = False
        self._toggle_btn.clicked.connect(self._toggle_expand)

        self._empty_label = QLabel(tr("No servers added.\nPress + to add"))
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setStyleSheet(f"color: {Color.GRAY_400}; font-size: 13px; padding: 40px 20px;")
        layout.addWidget(self._empty_label)

        self.tree = GroupTreeWidget(self)
        self.tree.setColumnCount(1)
        self.tree.setHeaderHidden(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setIndentation(20)
        self.tree.setIconSize(QSize(22, 22))
        self.tree.setRootIsDecorated(True)
        self.tree.setAnimated(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.currentItemChanged.connect(self._on_current_item_changed)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)

        layout.addWidget(self.tree)

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(4, 2, 4, 2)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self._toggle_btn)
        layout.addLayout(bottom_layout)

        self.setLayout(layout)

    def set_servers(self, nodes_cfg):
        self.nodes_cfg = nodes_cfg
        self._cfg_by_name = build_cfg_index(self.nodes_cfg)
        self._build_tree()

    def _toggle_expand(self):
        self._toggled = not self._toggled
        if self._toggled:
            self.tree.expandAll()
            self._toggle_btn.setIcon(get_icon("collapse"))
            self._toggle_btn.setToolTip(tr("Collapse all"))
        else:
            self.tree.collapseAll()
            self._toggle_btn.setIcon(get_icon("expand"))
            self._toggle_btn.setToolTip(tr("Expand all"))

    def _on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return

        vm_key = item.data(0, VM_KEY_ROLE)
        if vm_key is not None:
            host_name, vmid, node = vm_key
            vm = self._vm_repo.get(host_name, vmid) if self._vm_repo else None
            menu = QMenu(self.tree)
            menu.setStyleSheet(
                "QMenu { font-size: 12px; padding: 2px; }"
                "QMenu::item { padding: 4px 12px; }"
                f"QMenu::item:selected {{ background: {Color.GRAY_200}; }}"
            )
            vm_status = vm.get("status", "") if vm else ""
            is_template = bool(vm and vm.get("template"))
            is_qemu = vm and vm.get("type", "qemu") == "qemu"
            selected_vm_keys = self.selected_vm_keys()
            if len(selected_vm_keys) > 1:
                for act_key, act_label in [("start", tr("Start all")),
                                           ("shutdown", tr("Shutdown all")),
                                           ("reboot", tr("Reboot all")),
                                           ("stop", tr("Stop all"))]:
                    act = QAction(act_label, self.tree)
                    act.setIcon(get_icon(VM_ACTION_ICONS[act_key]))
                    act.triggered.connect(
                        lambda checked, keys=selected_vm_keys, a=act_key:
                            self.bulk_vm_action_requested.emit(keys, a)
                    )
                    menu.addAction(act)
                menu.addSeparator()
            for act_key, act_label in [("start", tr("Start")), ("shutdown", tr("Shutdown")),
                                       ("reboot", tr("Reboot")), ("stop", tr("Stop")),
                                       ("reset", tr("Reset")), ("resume", tr("Resume"))]:
                act = QAction(act_label, self.tree)
                act.setIcon(get_icon(VM_ACTION_ICONS[act_key]))
                act.triggered.connect(
                    lambda checked, hn=host_name, nd=node, vid=vmid, a=act_key:
                        self.vm_action_requested.emit(hn, nd, vid, a)
                )
                if is_template:
                    act.setEnabled(False)
                elif act_key in ("shutdown", "reboot", "stop", "reset") and vm_status != "running":
                    act.setEnabled(False)
                if act_key == "resume" and vm_status != "paused":
                    act.setEnabled(False)
                if act_key == "start" and vm_status == "running":
                    act.setEnabled(False)
                menu.addAction(act)
            console_act = QAction(tr("Console"), self.tree)
            console_act.setIcon(get_icon("console"))
            console_act.triggered.connect(
                lambda checked, hn=host_name, nd=node, vid=vmid:
                    self.console_requested.emit(hn, nd, vid)
            )
            console_act.setEnabled(vm_status == "running" and not is_template)
            menu.addAction(console_act)
            menu.addSeparator()
            migrate_act = QAction(tr("Migrate"), self.tree)
            migrate_act.setIcon(get_icon("migrate"))
            migrate_act.triggered.connect(
                lambda checked, hn=host_name, nd=node, vid=vmid: self.vm_migrate_requested.emit(hn, nd, vid)
            )
            migrate_act.setEnabled(not is_template)
            menu.addAction(migrate_act)
            clone_act = QAction(tr("Clone"), self.tree)
            clone_act.setIcon(get_icon("clone"))
            clone_act.triggered.connect(
                lambda checked, hn=host_name, nd=node, vid=vmid: self.vm_clone_requested.emit(hn, nd, vid)
            )
            menu.addAction(clone_act)
            if is_qemu:
                menu.addSeparator()
                if is_template:
                    convert_act = QAction(tr("Convert to VM"), self.tree)
                    convert_act.setIcon(get_icon("vm"))
                    convert_act.triggered.connect(
                        lambda checked, hn=host_name, nd=node, vid=vmid:
                            self.vm_convert_requested.emit(hn, nd, vid, "to_vm")
                    )
                    menu.addAction(convert_act)
                else:
                    convert_act = QAction(tr("Convert to Template"), self.tree)
                    convert_act.setIcon(get_icon("template"))
                    convert_act.setEnabled(vm_status != "running")
                    convert_act.triggered.connect(
                        lambda checked, hn=host_name, nd=node, vid=vmid:
                            self.vm_convert_requested.emit(hn, nd, vid, "to_template")
                    )
                    menu.addAction(convert_act)
            menu.addSeparator()
            ha_add_act = QAction(tr("Add to HA"), self.tree)
            ha_add_act.setIcon(get_icon("ha"))
            ha_add_act.triggered.connect(
                lambda checked, hn=host_name, nd=node, vid=vmid:
                    self.vm_ha_add_requested.emit(hn, nd, vid)
            )
            ha_add_act.setEnabled(not is_template)
            menu.addAction(ha_add_act)
            ha_remove_act = QAction(tr("Remove from HA"), self.tree)
            ha_remove_act.setIcon(get_icon("ha"))
            ha_remove_act.triggered.connect(
                lambda checked, hn=host_name, nd=node, vid=vmid:
                    self.vm_ha_remove_requested.emit(hn, nd, vid)
            )
            menu.addAction(ha_remove_act)
            menu.addSeparator()
            delete_action = QAction(tr("Delete VM"), self.tree)
            delete_action.triggered.connect(
                lambda checked, hn=host_name, nd=node, vid=vmid: self.vm_delete_requested.emit(hn, nd, vid)
            )
            menu.addAction(delete_action)
            menu.exec(self.tree.viewport().mapToGlobal(pos))
            return

        key = item.data(0, ITEM_KEY_ROLE)
        if not key or not isinstance(key, tuple):
            return
        item_type = key[0]
        item_name = key[1] if len(key) > 1 else ""

        menu = QMenu(self.tree)
        menu.setStyleSheet(
            "QMenu { font-size: 12px; padding: 2px; }"
            "QMenu::item { padding: 4px 12px; }"
            f"QMenu::item:selected {{ background: {Color.GRAY_200}; }}"
        )

        if item_type == "host":
            host_name = key[2] if len(key) > 2 else ""
            if not host_name:
                host = next((n for n in self.all_nodes if n.get("node") == item_name), None)
                host_name = host.get("host_name", "") if host else ""
            if host_name:
                create_vm_action = QAction(tr("Create VM"), self.tree)
                create_vm_action.setIcon(get_icon("vm"))
                create_vm_action.triggered.connect(
                    lambda checked, nn=item_name, hn=host_name: self.vm_create_requested.emit(nn, hn)
                )
                menu.addAction(create_vm_action)
                templates = [vm for vm in self.all_vms
                             if vm.get("template") and vm.get("host_name") == host_name]
                if templates:
                    clone_from_tmpl = QAction(tr("Clone from Template"), self.tree)
                    clone_from_tmpl.setIcon(get_icon("template"))
                    clone_from_tmpl.triggered.connect(
                        lambda checked, nn=item_name, hn=host_name:
                            self.vm_clone_from_template_requested.emit(hn, nn)
                    )
                    menu.addAction(clone_from_tmpl)
                menu.addSeparator()
                delete_action = QAction(tr("Delete host"), self.tree)
                delete_action.triggered.connect(lambda: self.host_remove_requested.emit("host", host_name))
                menu.addAction(delete_action)
                refresh_action = QAction(tr("Refresh token"), self.tree)
                refresh_action.setIcon(get_icon("refresh"))
                refresh_action.triggered.connect(lambda: self.host_token_refresh_requested.emit(host_name))
                menu.addAction(refresh_action)
                menu.addSeparator()
                trust_cfg = next((c for c in self.nodes_cfg if c.get("name") == host_name), None)
                trust_ssl_current = bool(trust_cfg.get("trust_ssl", True)) if trust_cfg else True
                if trust_ssl_current:
                    trust_action = QAction(tr("Trust SSL certificate") + " — " + tr("trusted"), self.tree)
                    trust_action.setIcon(get_icon("lock"))
                else:
                    trust_action = QAction(tr("Trust SSL certificate") + " — " + tr("untrusted"), self.tree)
                    trust_action.setIcon(get_icon("unlock"))
                trust_action.triggered.connect(
                    lambda checked, hn=host_name: self.host_trust_ssl_changed.emit(hn, not trust_ssl_current)
                )
                menu.addAction(trust_action)
                self._add_group_menu(menu, "host", host_name)

        elif item_type == "cluster":
            cl_hosts = [c for c in self.nodes_cfg if c.get("cluster") == item_name]
            if cl_hosts:
                first = cl_hosts[0]
                cl_node_name = first.get("node", "")
                cl_host_name = first.get("name", "")
                create_vm_action = QAction(tr("Create VM"), self.tree)
                create_vm_action.setIcon(get_icon("vm"))
                create_vm_action.triggered.connect(
                    lambda checked, nn=cl_node_name, hn=cl_host_name:
                        self.vm_create_requested.emit(nn, hn)
                )
                menu.addAction(create_vm_action)
                menu.addSeparator()
            delete_action = QAction(tr("Delete cluster"), self.tree)
            delete_action.triggered.connect(lambda: self.host_remove_requested.emit("cluster", item_name))
            menu.addAction(delete_action)
            self._add_group_menu(menu, "cluster", item_name)

        elif item_type == "group":
            rename_action = QAction(tr("Rename group…"), self.tree)
            rename_action.triggered.connect(
                lambda checked=False, g=item_name: self._rename_group_dialog(g))
            menu.addAction(rename_action)
            delete_action = QAction(tr("Delete group"), self.tree)
            delete_action.triggered.connect(
                lambda checked=False, g=item_name: self.group_delete_requested.emit(g))
            menu.addAction(delete_action)

        elif item_type == "section" and item_name in (tr("Clusters"), tr("Standalone hosts")):
            delete_action = QAction(tr("Remove all hosts from") + f' "{item_name}"', self.tree)
            delete_action.triggered.connect(lambda: self.host_remove_requested.emit("section", item_name))
            menu.addAction(delete_action)

        if not menu.actions():
            return
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _make_section_item(self, parent, label):
        item = QTreeWidgetItem(parent)
        item.setData(0, ITEM_KEY_ROLE, ("section", label))
        item.setText(0, label)
        item.setIcon(0, get_icon("folder"))

        context_map = {tr("Clusters"): "cluster", tr("Standalone hosts"): "standalone"}
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
            f"QPushButton {{ border: 1px solid {Color.SLATE_300}; border-radius: 3px; "
            f"background: {Color.SLATE_100}; font-size: 13px; font-weight: bold; "
            f"color: {Color.SLATE_500}; padding: 0; outline: none; }}"
            f"QPushButton:hover {{ background: {Color.SLATE_200}; border-color: {Color.SLATE_400}; color: {Color.SLATE_700}; }}"
        )
        btn.setToolTip(tr("Add host to") + f' "{label}"')
        btn.clicked.connect(lambda checked, c=ctx: self.add_server_requested_context.emit(c))
        hbox.addWidget(btn)
        self.tree.setItemWidget(item, 0, w)

        return item

    def _tick_spinner(self):
        self._spinner_angle = (self._spinner_angle + 45) % 360
        icon = make_loading_icon(self._spinner_angle)
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

    def update_data(self, all_nodes, all_vms, all_storages=None, final=False, node_repo=None, vm_repo=None):
        self.all_nodes = all_nodes
        self.all_vms = all_vms
        self._node_repo = node_repo
        self._vm_repo = vm_repo
        self.all_storages = all_storages or []
        if final:
            self._loading_hosts.clear()
            self._spin_timer.stop()
            self._rebuild_timer.stop()
            self._build_tree()
            self._sync_toggle_button()
            self._update_empty_visibility()
        else:
            self._rebuild_timer.start()

    def _do_rebuild(self):
        self._build_tree()
        self._sync_toggle_button()
        self._update_empty_visibility()

    def start_loading(self):
        self.tree.clear()
        self._empty_label.setVisible(False)
        self.tree.setVisible(True)
        self._toggle_btn.setVisible(True)
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

        folder = self._make_section_item(self.tree, tr("Clusters"))
        for cl_name in sorted(hosts_by_cluster.keys(), key=str.lower):
            cl_item = QTreeWidgetItem(folder)
            cl_item.setText(0, cl_name)
            cl_item.setIcon(0, make_loading_icon(0))
            cl_item.setData(0, ITEM_KEY_ROLE, ("cluster", cl_name))
            cl_item.setExpanded(True)
            self._loading_hosts.add(f"cluster:{cl_name}")

        folder_standalone = self._make_section_item(self.tree, tr("Standalone hosts"))
        if standalone:
            for hname in sorted(standalone, key=str.lower):
                hi = QTreeWidgetItem(folder_standalone)
                hi.setText(0, hname)
                hi.setIcon(0, make_loading_icon(0))
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
            self._toggle_btn.setToolTip(tr("Collapse all"))
        else:
            self._toggle_btn.setIcon(get_icon("expand"))
            self._toggle_btn.setToolTip(tr("Expand all"))

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
        if vm.get("template"):
            vm_item.setIcon(0, get_icon("template"))
        else:
            vm_item.setIcon(0, get_icon("vm", vm.get("status")))
        vm_item.setData(0, VM_KEY_ROLE, (vm.get("host_name", ""), vm.get("vmid", 0), vm.get("node", "")))
        cpu = vm.get("cpu", 0)
        if isinstance(cpu, float):
            cpu_pct = round(cpu * 100, 1)
        else:
            cpu_pct = cpu
        mem = vm.get("mem", 0) or 0
        maxmem = vm.get("maxmem", 0) or 0
        mem_pct = int(max(0, min(100, (mem / maxmem) * 100))) if maxmem else 0
        status = vm.get("status", "")
        vm_item.setToolTip(0, tr("Status") + f": {status_text(status)}\n" + tr("CPU") + f": {cpu_pct}%\n" + tr("RAM") + f": {mem_pct}%")
        return vm_item

    def _add_group_menu(self, menu, kind, name):
        """B16: 'Move to group' submenu for host/cluster items."""
        groups = sorted({(c.get("group") or "").strip() for c in self.nodes_cfg
                         if (c.get("group") or "").strip()}, key=str.lower)
        current = ""
        if kind == "host":
            cfg = next((c for c in self.nodes_cfg if c.get("name") == name), None)
            current = (cfg.get("group") or "").strip() if cfg else ""
        else:
            current = next(((c.get("group") or "").strip() for c in self.nodes_cfg
                            if c.get("cluster") == name and (c.get("group") or "").strip()), "")
        submenu = menu.addMenu(tr("Move to group"))
        none_act = submenu.addAction(tr("Remove from group"))
        none_act.setEnabled(bool(current))
        none_act.triggered.connect(
            lambda checked=False, k=kind, n=name: self.group_move_requested.emit(k, n, ""))
        submenu.addSeparator()
        for g in groups:
            act = submenu.addAction(g)
            act.setCheckable(True)
            act.setChecked(g == current)
            act.triggered.connect(
                lambda checked=False, gg=g, k=kind, n=name:
                    self.group_move_requested.emit(k, n, gg))
        submenu.addSeparator()
        new_act = submenu.addAction(tr("New group…"))
        new_act.triggered.connect(
            lambda checked=False, k=kind, n=name: self._new_group_dialog(k, n))

    def _new_group_dialog(self, kind, name):
        text, ok = QInputDialog.getText(self, tr("New group…"), tr("Group name"))
        if not ok:
            return
        group = text.strip()
        if group:
            self.group_move_requested.emit(kind, name, group)

    def _rename_group_dialog(self, old_name):
        text, ok = QInputDialog.getText(self, tr("Rename group…"), tr("Group name"),
                                        text=old_name)
        if not ok:
            return
        new_name = text.strip()
        if new_name and new_name != old_name:
            self.group_rename_requested.emit(old_name, new_name)

    def _make_cluster_item(self, parent, cluster_name, nodes_in_cl):
        """Create a cluster item (with hosts, pools and VMs) under parent."""
        cl_item = QTreeWidgetItem(parent)
        if not nodes_in_cl:
            cl_item.setText(0, cluster_name)
            cl_item.setIcon(0, make_loading_icon(self._spinner_angle))
            cl_item.setData(0, ITEM_KEY_ROLE, ("cluster", cluster_name))
            return cl_item
        cluster_host_names = {n.get("host_name") for n in nodes_in_cl}
        vms_in_cl = [vm for vm in self.all_vms
                     if vm.get("node") in {n.get("node") for n in nodes_in_cl}
                     and vm.get("host_name") in cluster_host_names]
        cl_item.setText(0, f"{cluster_name}  {_vm_count_str(vms_in_cl)}")
        cl_item.setIcon(0, get_icon("cluster"))
        cl_item.setData(0, ITEM_KEY_ROLE, ("cluster", cluster_name))

        for node in sorted(nodes_in_cl, key=lambda n: (n.get("_display_name") or n.get("node", "")).lower()):
            node_name = node.get("node", "?")
            display_name = node.get("_display_name") or node_name
            vms_on_node = [vm for vm in vms_in_cl if vm.get("node") == node_name and vm.get("host_name") == node.get("host_name")]
            host_item = QTreeWidgetItem(cl_item)
            host_item.setText(0, f"{display_name}  {_vm_count_str(vms_on_node)}")
            host_item.setIcon(0, get_icon("host", node.get("status")))
            host_item.setData(0, ITEM_KEY_ROLE, ("host", node_name, node.get("host_name", "")))
            host_item.setToolTip(0, _node_tooltip(node))

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

            for vm in sorted(vms_list, key=lambda v: (v.get("name") or f"VM {v.get('vmid')}").lower()):
                self._add_vm_item(pool_item, vm)

        for vm in sorted(no_pool_vms, key=lambda v: (v.get("name") or f"VM {v.get('vmid')}").lower()):
            self._add_vm_item(cl_item, vm)
        return cl_item

    def _make_host_item(self, parent, node):
        """Create a standalone host item (with pools and VMs) under parent."""
        node_name = node.get("node", "?")
        display_name = node.get("_display_name") or node_name
        host_name = node.get("host_name", "")
        vms_on_host = [vm for vm in self.all_vms
                       if vm.get("node") == node_name
                       and vm.get("host_name") == host_name]
        host_item = QTreeWidgetItem(parent)
        if node.get("status") == "loading":
            host_item.setText(0, display_name)
            host_item.setIcon(0, make_loading_icon(self._spinner_angle))
            host_item.setData(0, ITEM_KEY_ROLE, ("host", node_name, host_name))
            return host_item
        host_item.setText(0, f"{display_name}  {_vm_count_str(vms_on_host)}")
        host_item.setIcon(0, get_icon("host", node.get("status")))
        host_item.setData(0, ITEM_KEY_ROLE, ("host", node_name, host_name))
        host_item.setToolTip(0, _node_tooltip(node))

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

            for vm in sorted(pool_groups[pool_name], key=lambda v: (v.get("name") or f"VM {v.get('vmid')}").lower()):
                self._add_vm_item(pool_item, vm)

        for vm in sorted(no_pool_vms, key=lambda v: (v.get("name") or f"VM {v.get('vmid')}").lower()):
            self._add_vm_item(host_item, vm)
        return host_item

    def _build_tree(self):
        self._building = True
        saved_key = self.get_current_item_key()
        scroll_val = self.tree.verticalScrollBar().value()
        self.tree.clear()

        # B16: host groups — cfg["group"] per host; cluster group via any member cfg
        host_group = {}
        cluster_group = {}
        for cfg in self.nodes_cfg:
            g = (cfg.get("group") or "").strip()
            if not g or not cfg.get("name"):
                continue
            host_group[cfg["name"]] = g
            cl = cfg.get("cluster")
            if cl and cl not in (False, None, "Standalone"):
                cluster_group.setdefault(cl, g)

        cluster_nodes = defaultdict(list)
        standalone_nodes = []
        group_clusters = defaultdict(dict)     # group -> {cluster_name: [nodes]}
        group_standalone = defaultdict(list)   # group -> [nodes]

        for node in self.all_nodes:
            host_name = node.get("host_name", "")
            cfg = self._cfg_by_name.get(host_name)
            cluster_name = cfg.get("cluster") if cfg else None
            if cluster_name and cluster_name not in (False, None, "Standalone"):
                g = cluster_group.get(cluster_name)
                if g:
                    group_clusters[g].setdefault(cluster_name, []).append(node)
                else:
                    cluster_nodes[cluster_name].append(node)
            else:
                g = host_group.get(host_name)
                if g:
                    group_standalone[g].append(node)
                else:
                    standalone_nodes.append(node)

        for cfg in self.nodes_cfg:
            if cfg.get("skip"):
                continue
            cluster_name = cfg.get("cluster")
            if cluster_name and cluster_name not in (False, None, "Standalone"):
                g = cluster_group.get(cluster_name)
                if g:
                    if cluster_name not in group_clusters[g]:
                        group_clusters[g][cluster_name] = []
                        if f"cluster:{cluster_name}" not in self._loading_hosts:
                            self._loading_hosts.add(f"cluster:{cluster_name}")
                elif cluster_name not in cluster_nodes:
                    cluster_nodes[cluster_name] = []
                    if f"cluster:{cluster_name}" not in self._loading_hosts:
                        self._loading_hosts.add(f"cluster:{cluster_name}")

        standalone_names = {n.get("host_name", "") for n in standalone_nodes}
        grouped_standalone_names = {n.get("host_name", "") for nodes in group_standalone.values() for n in nodes}
        for cfg in self.nodes_cfg:
            if cfg.get("skip"):
                continue
            host_name = cfg.get("name", "")
            cluster = cfg.get("cluster")
            if cluster and cluster not in (False, None, "Standalone"):
                continue
            g = host_group.get(host_name)
            if g:
                if host_name not in grouped_standalone_names:
                    group_standalone[g].append({
                        "node": host_name,
                        "host_name": host_name,
                        "_display_name": host_name,
                        "status": "loading",
                    })
                    self._loading_hosts.add(host_name)
                    grouped_standalone_names.add(host_name)
                continue
            if host_name not in standalone_names:
                standalone_nodes.append({
                    "node": host_name,
                    "host_name": host_name,
                    "_display_name": host_name,
                    "status": "loading",
                })
                self._loading_hosts.add(host_name)

        for node in self.all_nodes:
            hn = node.get("host_name", "")
            self._loading_hosts.discard(hn)
            if node.get("_is_cluster"):
                cfg = self._cfg_by_name.get(hn)
                if cfg:
                    cl_name = cfg.get("cluster", "")
                    if cl_name:
                        self._loading_hosts.discard(f"cluster:{cl_name}")

        # B16: group items at top level, above Clusters/Standalone sections
        group_names = sorted(set(group_clusters) | set(group_standalone), key=str.lower)
        for g in group_names:
            g_item = QTreeWidgetItem(self.tree)
            g_item.setData(0, ITEM_KEY_ROLE, ("group", g))
            g_nodes = group_standalone.get(g, [])
            g_cl_nodes = [n for nodes in group_clusters.get(g, {}).values() for n in nodes]
            g_host_names = {n.get("host_name") for n in g_nodes + g_cl_nodes}
            g_vms = [vm for vm in self.all_vms if vm.get("host_name") in g_host_names]
            g_item.setText(0, f"{g}  {_vm_count_str(g_vms)}")
            g_item.setIcon(0, get_icon("folder"))
            for cl_name in sorted(group_clusters.get(g, {}), key=str.lower):
                self._make_cluster_item(g_item, cl_name, group_clusters[g][cl_name])
            for node in sorted(g_nodes, key=lambda n: (n.get("_display_name") or n.get("node", "")).lower()):
                self._make_host_item(g_item, node)

        cluster_folder = self._make_section_item(self.tree, tr("Clusters"))
        standalone_folder = self._make_section_item(self.tree, tr("Standalone hosts"))

        if cluster_nodes:
            for cluster_name in sorted(cluster_nodes.keys(), key=str.lower):
                self._make_cluster_item(cluster_folder, cluster_name, cluster_nodes[cluster_name])

        if standalone_nodes:
            for node in sorted(standalone_nodes, key=lambda n: (n.get("_display_name") or n.get("node", "")).lower()):
                self._make_host_item(standalone_folder, node)

        if self.all_storages:
            st_folder = self._make_section_item(self.tree, tr("Storage"))

            cluster_storages = defaultdict(list)
            standalone_storages = []
            for st in self.all_storages:
                cluster = st.get("cluster")
                if cluster:
                    cluster_storages[cluster].append(st)
                else:
                    standalone_storages.append(st)

            for cluster_name in sorted(cluster_storages.keys(), key=str.lower):
                cl_item = QTreeWidgetItem(st_folder)
                cl_item.setText(0, cluster_name)
                cl_item.setIcon(0, get_icon("cluster"))
                cl_item.setData(0, ITEM_KEY_ROLE, ("storage_section", cluster_name))
                cl_item.setFlags(cl_item.flags() & ~Qt.ItemIsSelectable)

                seen_names = set()
                for st in cluster_storages[cluster_name]:
                    sname = st.get("storage", "")
                    if sname not in seen_names:
                        seen_names.add(sname)
                        si = QTreeWidgetItem(cl_item)
                        si.setText(0, f"{sname} (@{cluster_name})")
                        si.setIcon(0, get_icon("storage"))
                        si.setData(0, ITEM_KEY_ROLE, ("storage", sname, "cluster", cluster_name))

            if standalone_storages:
                so_item = QTreeWidgetItem(st_folder)
                so_item.setText(0, tr("Standalone"))
                so_item.setIcon(0, get_icon("folder"))
                so_item.setData(0, ITEM_KEY_ROLE, ("storage_section", tr("Standalone")))
                so_item.setFlags(so_item.flags() & ~Qt.ItemIsSelectable)

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
                        si.setData(0, ITEM_KEY_ROLE, ("storage", sname, "host", shost))

        raw = load_ui_state("expandedTreePaths")
        if raw:
            self._restore_expanded_state()
        else:
            self.tree.expandAll()
        if saved_key is not None:
            item = self.find_item_by_key(saved_key)
            if item is not None:
                self.tree.setCurrentItem(item)
        self.tree.verticalScrollBar().setValue(scroll_val)
        self._building = False

    def update_node_statuses(self, all_nodes, all_vms, node_repo=None, vm_repo=None):
        self.all_nodes = all_nodes
        self._node_repo = node_repo or self._node_repo
        for node in list(all_nodes):
            hn = node.get("host_name", "")
            self._loading_hosts.discard(hn)
            if node.get("_is_cluster"):
                cfg = self._cfg_by_name.get(hn)
                if cfg:
                    cluster_name = cfg.get("cluster", "")
                    if cluster_name:
                        self._loading_hosts.discard(f"cluster:{cluster_name}")
        if not self._loading_hosts:
            self._spin_timer.stop()

        it = QTreeWidgetItemIterator(self.tree)
        while it.value() is not None:
            item = it.value()
            vm_key = item.data(0, VM_KEY_ROLE)
            if vm_key is not None:
                host_name, vmid, _node = vm_key
                vm = self._vm_repo.get(host_name, vmid) if self._vm_repo else None
                if vm:
                    if vm.get("template"):
                        item.setIcon(0, get_icon("template"))
                    else:
                        item.setIcon(0, get_icon("vm", vm.get("status")))
            else:
                key = item.data(0, ITEM_KEY_ROLE)
                if key and isinstance(key, tuple) and key[0] == "host":
                    hn = key[2] if len(key) > 2 else None
                    node_name = key[1]
                    if hn:
                        host = self._node_repo.get(hn, node_name) if self._node_repo else None
                    else:
                        host = next((n for n in self.all_nodes if n.get("node") == node_name), None)
                    if host:
                        item.setIcon(0, get_icon("host", host.get("status")))
            it += 1

    @staticmethod
    def _strip_count(text):
        """Remove VM count suffix like '[3/5]' for stable paths."""
        return re.sub(r'\s+\[\d+/\d+\]$', '', text)

    def _save_expanded_state(self):
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
        save_ui_state("expandedTreePaths", json.dumps(paths))

    def _restore_expanded_state(self):
        raw = load_ui_state("expandedTreePaths")
        if not raw:
            return
        try:
            saved_paths = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return
        if not saved_paths:
            return
        def match_and_expand(item, path=""):
            label = self._strip_count(item.text(0))
            current = path + "|" + label if path else label
            if current in saved_paths:
                item.setExpanded(True)
            for i in range(item.childCount()):
                match_and_expand(item.child(i), current)
        for i in range(self.tree.topLevelItemCount()):
            match_and_expand(self.tree.topLevelItem(i))

    def save_state(self):
        self._save_expanded_state()

    def _update_empty_visibility(self):
        """Show/hide the hint when the tree is empty."""
        has_items = self.tree.topLevelItemCount() > 0
        self._empty_label.setVisible(not has_items)
        self.tree.setVisible(has_items)
        self._toggle_btn.setVisible(has_items)

    def select_first_item(self):
        if self.tree.topLevelItemCount() > 0:
            item = self.tree.topLevelItem(0)
            self.tree.setCurrentItem(item)
            self._on_item_clicked(item, 0)

    def find_item_by_key(self, key_data):
        if not isinstance(key_data, tuple) or len(key_data) < 2:
            return None
        is_vm_key = isinstance(key_data[1], int)
        def search(item):
            if is_vm_key:
                if item.data(0, VM_KEY_ROLE) == key_data:
                    return item
            else:
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

    def selected_vm_keys(self):
        """Return VM keys (host_name, vmid, node) for all selected VM items."""
        keys = []
        for item in self.tree.selectedItems():
            vm_key = item.data(0, VM_KEY_ROLE)
            if vm_key is not None:
                keys.append(vm_key)
        return keys

    def find_and_select(self, key_data):
        """Find a tree item by key tuple, expand parents, scroll to it, and select it."""
        item = self.find_item_by_key(key_data)
        if not item:
            return
        parent = item.parent()
        while parent:
            parent.setExpanded(True)
            parent = parent.parent()
        self.tree.scrollToItem(item)
        self.tree.setCurrentItem(item)
        self._on_item_clicked(item, 0)

    def request_delete_current(self):
        """Trigger delete on currently selected item (for Del shortcut)."""
        item = self.tree.currentItem()
        if not item:
            return
        vm_key = item.data(0, VM_KEY_ROLE)
        if vm_key is not None:
            host_name, vmid, node = vm_key
            self.vm_delete_requested.emit(host_name, node, vmid)
            return
        key = item.data(0, ITEM_KEY_ROLE)
        if not key or not isinstance(key, tuple):
            return
        item_type = key[0]
        item_name = key[1] if len(key) > 1 else ""
        if item_type == "host":
            host_name = key[2] if len(key) > 2 else ""
            if not host_name:
                host = next((n for n in self.all_nodes if n.get("node") == item_name), None)
                host_name = host.get("host_name", "") if host else ""
            if host_name:
                self.host_remove_requested.emit("host", host_name)
        elif item_type in ("cluster", "section"):
            self.host_remove_requested.emit(item_type, item_name)

    def _on_item_clicked(self, item, column):
        self._nav_timer.stop()

        vm_key = item.data(0, VM_KEY_ROLE)
        if vm_key is not None:
            host_name, vmid, _node = vm_key
            vm = self._vm_repo.get(host_name, vmid) if self._vm_repo else None
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
            if item_name == tr("Clusters"):
                self.item_selected.emit("cluster_folder", item_name, {})
            elif item_name == tr("Standalone hosts"):
                self.item_selected.emit("standalone_folder", item_name, {})
            elif item_name == tr("Storage"):
                self.item_selected.emit("storage_folder", item_name, {})
            return

        if item_type == "cluster":
            self.item_selected.emit("cluster", item_name, {})
            return

        if item_type == "group":
            self.item_selected.emit("group", item_name, {})
            return

        if item_type == "host":
            host_name_key = key[2] if len(key) > 2 else None
            if host_name_key:
                host_data = self._node_repo.get(host_name_key, item_name) if self._node_repo else None
                if host_data is None:
                    host_data = next((n for n in self.all_nodes
                                      if n.get("host_name") == host_name_key), None)
            else:
                host_data = next((n for n in self.all_nodes if n.get("node") == item_name), None)
            self.item_selected.emit("host", item_name, host_data or {})
            return

        if item_type == "pool":
            self.item_selected.emit("pool", item_name, {})
            return

        if item_type == "storage":
            data = {"storage_name": item_name}
            if len(key) >= 4:
                kind = key[2]
                val = key[3]
                if kind == "cluster":
                    data["cluster"] = val
                elif kind == "host":
                    data["host_name"] = val
            self.item_selected.emit("storage", item_name, data)
            return

        self.item_selected.emit("unknown", item_name, {})
