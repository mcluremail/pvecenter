"""Tests for ClusterTasksWidget with domain Task objects."""
from PySide6.QtCore import Qt

from pve_center.domain.task import Task
from pve_center.ui.widgets.cluster_tasks_widget import ClusterTasksWidget


def _task(upid, starttime=100.0, endtime=0.0, status="OK", node="n1",
          task_type="qmstart", user="root@pam", vmid=100,
          display_name=None, vm_name=None):
    return Task(upid=upid, node=node, task_type=task_type, status=status,
                starttime=starttime, endtime=endtime, user=user, vmid=vmid,
                display_name=display_name, vm_name=vm_name)


class TestClusterTasksWidget:
    def test_set_tasks_rows(self, qtbot):
        w = ClusterTasksWidget()
        qtbot.addWidget(w)
        tasks = [
            _task("UPID:n1:1:2:100:qmstart:100:root@pam:",
                  endtime=110.0, display_name="n1 (h1)", vm_name="alpha"),
            _task("UPID:n1:1:2:200:vzdump:200:root@pam:",
                  status="RUNNING", task_type="vzdump", vmid=200),
        ]
        w.set_tasks(tasks)
        assert w.table.rowCount() == 2
        # Host column: display_name if present, else node
        assert w.table.item(0, 2).text() == "n1 (h1)"
        assert w.table.item(1, 2).text() == "n1"
        # Description column
        assert "alpha" in w.table.item(0, 4).text()
        assert "(100)" in w.table.item(0, 4).text()
        assert "Backup" in w.table.item(1, 4).text()
        assert "200" in w.table.item(1, 4).text()
        # Running task: end column shows running...
        assert w.table.item(1, 1).text() != ""

    def test_sort_tasks(self, qtbot):
        w = ClusterTasksWidget()
        qtbot.addWidget(w)
        t_new = _task("UPID:n1:1:2:200:qmstart:100:root@pam:", starttime=200.0)
        t_old = _task("UPID:n1:1:2:100:qmstop:100:root@pam:", starttime=100.0)
        w.set_tasks([t_old, t_new])
        # Default sort: col 0, descending -> newest first
        assert w._all_tasks[0] is t_old  # set order preserved in _all_tasks
        sorted_desc = w._sort_tasks([t_old, t_new], 0, Qt.SortOrder.DescendingOrder)
        assert sorted_desc[0] is t_new
        sorted_asc = w._sort_tasks([t_old, t_new], 0, Qt.SortOrder.AscendingOrder)
        assert sorted_asc[0] is t_old

    def test_filter_by_text_and_status(self, qtbot):
        w = ClusterTasksWidget()
        qtbot.addWidget(w)
        ok_task = _task("UPID:n1:1:2:100:qmstart:100:root@pam:", vm_name="alpha")
        err_task = _task("UPID:n2:1:2:200:vzdump:200:root@pam:",
                         status="interrupted", node="n2", task_type="vzdump",
                         vmid=200)
        w.set_tasks([ok_task, err_task])

        w._filter_input.setText("alpha")
        w._apply_filter()
        assert w.table.rowCount() == 1
        w._filter_input.setText("")
        w._status_filter.setCurrentIndex(1)  # OK
        w._apply_filter()
        assert w.table.rowCount() == 1
        w._status_filter.setCurrentIndex(2)  # Errors (not OK)
        w._apply_filter()
        assert w.table.rowCount() == 1
        w._status_filter.setCurrentIndex(0)  # All
        w._apply_filter()
        assert w.table.rowCount() == 2
