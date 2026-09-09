"""Колонки должны перетаскиваться во всех таблицах и деревьях.

В Qt6 QHeaderView у QTableWidget создаётся с sectionsMovable=False,
поэтому каждое место с таблицей явно вызывает enable_column_reorder().
Плюс: колонки в ResizeToContents/Fixed нельзя тянуть мышью — такие
колонки переводятся в Interactive с автоподбором ширины по содержимому.
"""
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QPointingDevice
from PySide6.QtWidgets import QApplication, QHeaderView, QTableWidgetItem

from pve_center.ui.detail_panel._table_utils import make_table


class TestMakeTable:
    def test_columns_movable(self, qtbot):
        t = make_table(
            ["A", "B"],
            [(QHeaderView.Interactive, 80), (QHeaderView.Stretch, None)],
        )
        qtbot.addWidget(t)
        assert t.horizontalHeader().sectionsMovable()

    def test_resize_to_contents_becomes_interactive(self, qtbot):
        t = make_table(
            ["A", "B"],
            [(QHeaderView.ResizeToContents, None), (QHeaderView.Stretch, None)],
        )
        qtbot.addWidget(t)
        assert t.horizontalHeader().sectionResizeMode(0) == QHeaderView.Interactive

    def test_stretch_becomes_interactive(self, qtbot):
        """Stretch тоже нельзя тянуть — все колонки Interactive, последняя
        становится заполнителем (stretchLastSection)."""
        t = make_table(
            ["A", "B", "C"],
            [(QHeaderView.Stretch, None), (QHeaderView.Stretch, None),
             (QHeaderView.Stretch, None)],
        )
        qtbot.addWidget(t)
        h = t.horizontalHeader()
        for col in range(3):
            assert h.sectionResizeMode(col) == QHeaderView.Interactive, col
        assert h.stretchLastSection()
        assert t.property("_pve_autofit_cols") == {0, 1}

    def test_autofit_capped(self, qtbot):
        t = make_table(
            ["A", "B"],
            [(QHeaderView.Stretch, None), (QHeaderView.Stretch, None)],
        )
        qtbot.addWidget(t)
        t.setRowCount(1)
        t.setItem(0, 0, QTableWidgetItem("x" * 300))
        qtbot.wait(150)
        assert t.columnWidth(0) <= 480


class TestTableAutofit:
    """RTC/Fixed -> Interactive + автоподбор ширины до ручного ресайза."""

    def test_autofit_after_fill(self, qtbot):
        t = make_table(
            ["A", "B"],
            [(QHeaderView.ResizeToContents, None), (QHeaderView.Stretch, None)],
        )
        qtbot.addWidget(t)
        default = t.columnWidth(0)
        t.setRowCount(1)
        t.setItem(0, 0, QTableWidgetItem("x" * 60))
        qtbot.wait(150)  # debounce 60ms
        assert t.columnWidth(0) > default

    def test_user_press_disables_autofit(self, qtbot):
        t = make_table(
            ["A", "B"],
            [(QHeaderView.ResizeToContents, None), (QHeaderView.Stretch, None)],
        )
        qtbot.addWidget(t)
        header = t.horizontalHeader()
        x = header.sectionViewportPosition(0) + 5
        QApplication.sendEvent(header.viewport(), QMouseEvent(
            QEvent.Type.MouseButtonPress, QPointF(x, 5), QPointF(x, 5),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPointingDevice.primaryPointingDevice()))
        t.setRowCount(1)
        t.setItem(0, 0, QTableWidgetItem("x" * 60))
        qtbot.wait(150)
        assert 0 not in t.property("_pve_autofit_cols")


class TestDirectTables:
    """Виджеты со самодельными таблицами (мимо make_table)."""

    @pytest.mark.parametrize(
        "factory",
        [
            lambda: _mk("pve_center.ui.widgets.vm_options_widget",
                        "VmOptionsWidget"),
            lambda: _mk("pve_center.ui.widgets.vm_hardware_widget",
                        "VmHardwareWidget"),
            lambda: _mk("pve_center.ui.widgets.vm_pool_widget",
                        "VmPoolWidget"),
            lambda: _mk("pve_center.ui.widgets.vm_task_history_widget",
                        "VmTaskHistoryWidget"),
            lambda: _mk("pve_center.ui.widgets.cluster_tasks_widget",
                        "ClusterTasksWidget"),
        ],
        ids=["options", "hardware", "pool", "task_history", "cluster_tasks"],
    )
    def test_table_columns_movable(self, qtbot, factory):
        w = factory()
        qtbot.addWidget(w)
        assert w.table.horizontalHeader().sectionsMovable()

    @pytest.mark.parametrize(
        "factory, resizable_cols",
        [
            (lambda: _mk("pve_center.ui.widgets.vm_options_widget",
                         "VmOptionsWidget"), [0]),
            (lambda: _mk("pve_center.ui.widgets.vm_hardware_widget",
                         "VmHardwareWidget"), [0]),
            (lambda: _mk("pve_center.ui.widgets.vm_pool_widget",
                         "VmPoolWidget"), [1, 2, 3, 4, 5]),
            (lambda: _mk("pve_center.ui.widgets.vm_task_history_widget",
                         "VmTaskHistoryWidget"), [0, 1, 2, 3]),
            (lambda: _mk("pve_center.ui.widgets.cluster_tasks_widget",
                         "ClusterTasksWidget"), [2, 3]),
        ],
        ids=["options", "hardware", "pool", "task_history", "cluster_tasks"],
    )
    def test_no_resize_to_contents(self, qtbot, factory, resizable_cols):
        """Бывшие RTC/Stretch-колонки должны быть Interactive (тянуться
        мышью); последняя колонка — заполнитель."""
        w = factory()
        qtbot.addWidget(w)
        header = w.table.horizontalHeader()
        for col in range(w.table.columnCount()):
            mode = header.sectionResizeMode(col)
            if col in resizable_cols:
                assert mode == QHeaderView.Interactive, (col, mode)
            else:
                assert mode != QHeaderView.ResizeToContents, (col, mode)
                assert mode != QHeaderView.Stretch, (col, mode)
        assert header.stretchLastSection()

    def test_pbs_panel_tables_movable(self, qtbot):
        from pve_center.ui.pbs_panel import PbsPanel
        panel = PbsPanel()
        qtbot.addWidget(panel)
        for name in ("_ds_table", "_snap_table", "_jobs_table"):
            table = getattr(panel, name)
            header = table.horizontalHeader()
            assert header.sectionsMovable(), name
            assert header.stretchLastSection(), name
            for col in range(table.columnCount()):
                assert header.sectionResizeMode(
                    col) != QHeaderView.Stretch, (name, col)

    def test_search_dialog_tree_movable(self, qtbot):
        from pve_center.ui.search_dialog import GlobalSearchDialog
        dlg = GlobalSearchDialog(lambda: (object(), object(), object(), object()))
        qtbot.addWidget(dlg)
        assert dlg._tree.header().sectionsMovable()


class TestTreePanelHeader:
    def test_header_visible_and_movable(self, qtbot):
        from pve_center.ui.tree_panel import TreePanel
        tp = TreePanel([])
        qtbot.addWidget(tp)
        assert not tp.tree.isHeaderHidden()
        assert tp.tree.header().sectionsMovable()
        assert tp.tree.headerItem().text(0)
        assert tp.tree.headerItem().text(1)

    def test_column_order_persisted(self, qtbot, monkeypatch):
        import pve_center.ui.tree_panel as tp_mod
        from pve_center.ui.tree_panel import TreePanel

        state = {}
        monkeypatch.setattr(tp_mod, "load_ui_state", lambda k: state.get(k))
        monkeypatch.setattr(
            tp_mod, "save_ui_state", lambda k, v: state.__setitem__(k, v))

        tp = TreePanel([])
        qtbot.addWidget(tp)
        header = tp.tree.header()
        header.moveSection(1, 0)  # пользователь перетащил "Info" вперёд
        tp._save_tree_columns()
        assert state.get("tree_header_state")

        tp2 = TreePanel([])
        qtbot.addWidget(tp2)
        assert tp2.tree.header().visualIndex(1) == 0
        assert tp2.tree.header().visualIndex(0) == 1

    def test_early_layout_save_skipped(self, qtbot, monkeypatch):
        """sectionResized при раскладке не должен затирать сохранённое
        состояние дефолтными ширинами (в конфиг попадало 100/100)."""
        import pve_center.ui.tree_panel as tp_mod
        from pve_center.ui.tree_panel import TreePanel

        writes = []
        monkeypatch.setattr(tp_mod, "load_ui_state", lambda key: None)
        monkeypatch.setattr(
            tp_mod, "save_ui_state", lambda key, val: writes.append(key))

        tp = TreePanel([])
        qtbot.addWidget(tp)
        tp._save_tree_columns()
        assert writes == ["tree_header_state"]
        tp._save_tree_columns()  # то же состояние -> не пишется повторно
        assert writes == ["tree_header_state"]

        header = tp.tree.header()
        header.moveSection(1, 0)  # реальное действие пользователя
        tp._save_tree_columns()
        assert writes == ["tree_header_state", "tree_header_state"]


def _mk(module_name, class_name):
    """Импорт и создание виджета (чтобы параметризация оставалась лаконичной)."""
    import importlib
    mod = importlib.import_module(module_name)
    return getattr(mod, class_name)()
