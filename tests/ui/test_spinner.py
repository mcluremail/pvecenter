"""Tests for the animated SpinnerWidget (v2.11.2 loading indicators)."""
from PySide6.QtGui import QPixmap

from pve_center.ui.widgets.spinner import SpinnerWidget


class TestSpinnerWidget:
    def test_start_stop(self, qtbot):
        s = SpinnerWidget(24)
        qtbot.addWidget(s)
        assert not s.isVisible()
        assert not s.is_running
        s.start()
        assert s.isVisible()
        assert s.is_running
        s.stop()
        assert not s.isVisible()
        assert not s.is_running

    def test_tick_rotates_and_renders(self, qtbot):
        s = SpinnerWidget(24)
        qtbot.addWidget(s)
        s.show()
        angle0 = s._angle
        s._tick()
        assert s._angle != angle0
        # Paint smoke test: render must not raise and produce pixels.
        pm = QPixmap(24, 24)
        s.render(pm)
        assert not pm.isNull()

    def test_fixed_size(self, qtbot):
        s = SpinnerWidget(32)
        qtbot.addWidget(s)
        assert s.width() == 32
        assert s.height() == 32

    def test_hide_stops_timer(self, qtbot):
        s = SpinnerWidget(24)
        qtbot.addWidget(s)
        s.start()
        assert s.is_running
        s.hide()
        assert not s.is_running
