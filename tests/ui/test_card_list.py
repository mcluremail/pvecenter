"""Tests for CardList/CardRow with domain objects."""
from pve_center.ui.widgets.card_list import CardList, CardRow, _get_field, _status_dot


class TestGetField:
    """_get_field works with dicts and objects."""

    def test_dict(self):
        assert _get_field({"name": "x"}, "name") == "x"

    def test_dict_default(self):
        assert _get_field({}, "missing", "d") == "d"

    def test_object(self, make_node):
        n = make_node(node="srv")
        assert _get_field(n, "node") == "srv"

    def test_object_default(self, make_node):
        n = make_node()
        assert _get_field(n, "missing", "d") == "d"

    def test_object_property(self, make_node):
        n = make_node(cpu_fraction=0.42)
        assert _get_field(n, "cpu_pct") == 42.0


class TestStatusDot:
    def test_running(self):
        assert _status_dot("running") == "ok"

    def test_online(self):
        assert _status_dot("online") == "ok"

    def test_stopped(self):
        assert _status_dot("stopped") == "off"

    def test_offline(self):
        assert _status_dot("offline") == "off"

    def test_error(self):
        assert _status_dot("error") == "err"

    def test_none(self):
        assert _status_dot(None) is None

    def test_empty(self):
        assert _status_dot("") is None

    def test_domain_enum(self, make_vm):
        from pve_center.domain.enums import VmStatus
        vm = make_vm(status=VmStatus.RUNNING)
        assert _status_dot(vm.status_value) == "ok"


class TestCardRowDomain:
    """CardRow built from domain objects reads properties correctly."""

    def test_title_from_node(self, qtbot, make_node):
        n = make_node(node="pve01")
        row = CardRow(n, {"title": "display_name"})
        qtbot.addWidget(row)
        assert row._title_label.text() == "pve01"

    def test_title_from_vm(self, qtbot, make_vm):
        vm = make_vm(name="web-server")
        row = CardRow(vm, {"title": "display_name"})
        qtbot.addWidget(row)
        assert row._title_label.text() == "web-server"

    def test_fields_from_vm(self, qtbot, make_vm):
        vm = make_vm(cpu_fraction=0.5)
        row = CardRow(vm, {"title": "name", "fields": [("cpu_text", 60)]})
        qtbot.addWidget(row)
        assert row._field_labels[0][1].text() == "50.0%"

    def test_dot_from_node(self, qtbot, make_node):
        from pve_center.domain.enums import NodeStatus
        n = make_node(status=NodeStatus.ONLINE)
        row = CardRow(n, {"dot": "status_value"})
        qtbot.addWidget(row)
        assert row._dot_label is not None

    def test_update_fields_domain(self, qtbot, make_vm):
        from pve_center.domain.enums import VmStatus
        vm1 = make_vm(vmid=100, name="old", status=VmStatus.STOPPED)
        row = CardRow(vm1, {"title": "display_name", "fields": [("cpu_text", 60)]})
        qtbot.addWidget(row)
        assert row._title_label.text() == "old"

        vm2 = make_vm(vmid=100, name="new", status=VmStatus.RUNNING, cpu_fraction=0.8)
        row.update_fields(vm2)
        assert row._title_label.text() == "new"
        assert row._field_labels[0][1].text() == "80.0%"


class TestCardListDomain:
    """CardList.set_items / update_item / update_all with domain objects."""

    COLUMNS = {
        "key": "_key",
        "title": "display_name",
        "dot": "status_value",
        "fields": [("cpu_text", 60), ("ram_text", 120)],
    }

    def test_set_items(self, qtbot, make_vm):
        vms = [
            make_vm(vmid=100, name="alpha"),
            make_vm(vmid=101, name="beta"),
        ]
        cl = CardList(self.COLUMNS)
        qtbot.addWidget(cl)
        cl.set_items(vms)
        assert len(cl._rows) == 2
        assert cl._rows[0]._title_label.text() == "alpha"
        assert cl._rows[1]._title_label.text() == "beta"

    def test_empty(self, qtbot):
        cl = CardList(self.COLUMNS)
        qtbot.addWidget(cl)
        cl.set_items([])
        assert len(cl._rows) == 0
        assert not cl._empty_label.isHidden()

    def test_update_item(self, qtbot, make_vm):
        vm = make_vm(vmid=100, name="old", cpu_fraction=0.1)
        cl = CardList(self.COLUMNS)
        qtbot.addWidget(cl)
        cl.set_items([vm])
        new_vm = make_vm(vmid=100, name="new", cpu_fraction=0.9)
        cl.update_item("100", new_vm)
        assert cl._rows[0]._title_label.text() == "new"
        assert cl._rows[0]._field_labels[0][1].text() == "90.0%"

    def test_update_all(self, qtbot, make_vm):
        vms = [
            make_vm(vmid=100, name="a", cpu_fraction=0.1),
            make_vm(vmid=101, name="b", cpu_fraction=0.2),
        ]
        cl = CardList(self.COLUMNS)
        qtbot.addWidget(cl)
        cl.set_items(vms)
        updated = [
            make_vm(vmid=100, name="a2", cpu_fraction=0.5),
            make_vm(vmid=101, name="b2", cpu_fraction=0.6),
        ]
        cl.update_all(updated)
        assert cl._rows[0]._title_label.text() == "a2"
        assert cl._rows[1]._title_label.text() == "b2"
        assert cl._rows[0]._field_labels[0][1].text() == "50.0%"
        assert cl._rows[1]._field_labels[0][1].text() == "60.0%"

    def test_filter(self, qtbot, make_vm):
        vms = [
            make_vm(vmid=100, name="alpha"),
            make_vm(vmid=101, name="beta"),
        ]
        cl = CardList(self.COLUMNS, filterable=True)
        qtbot.addWidget(cl)
        cl.set_items(vms)
        cl._filter.setText("alpha")
        assert not cl._rows[0].isHidden()
        assert cl._rows[1].isHidden()

    def test_clear(self, qtbot, make_vm):
        cl = CardList(self.COLUMNS)
        qtbot.addWidget(cl)
        cl.set_items([make_vm()])
        assert len(cl._rows) == 1
        cl.clear()
        assert len(cl._rows) == 0
