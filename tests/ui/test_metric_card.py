"""Regression tests for MetricCard (v2.11.1 hotfix, v2.11.2 loading).

set_value() must accept an optional ``subtitle`` keyword — the cluster
quorum card calls it as ``set_value("2/4", subtitle=...)``.
"""
from pve_center.ui.widgets.metric_card import MetricCard


class TestSetValueSubtitle:
    def test_set_value_with_subtitle(self, qtbot):
        card = MetricCard("Quorum", "—")
        qtbot.addWidget(card)
        card.set_value("2/4", subtitle="Quorum: OK")
        assert card._value_label.text() == "2/4"
        assert card._subtitle_label.text() == "Quorum: OK"
        assert not card._subtitle_label.isHidden()

    def test_set_value_without_subtitle_keeps_state(self, qtbot):
        card = MetricCard("Quorum", "—")
        qtbot.addWidget(card)
        card.set_value("2/4", subtitle="Quorum: OK")
        card.set_value("3/4")
        assert card._value_label.text() == "3/4"
        assert card._subtitle_label.text() == "Quorum: OK"
        assert not card._subtitle_label.isHidden()

    def test_set_value_empty_subtitle_hides(self, qtbot):
        card = MetricCard("CPU", "5%")
        qtbot.addWidget(card)
        card.set_value("5%", subtitle="")
        assert card._subtitle_label.isHidden()

    def test_loading_state(self, qtbot):
        """v2.11.2: start_loading hides the value and spins; set_value
        stops the spinner and shows the new value."""
        card = MetricCard("Quorum", "—")
        qtbot.addWidget(card)
        card.show()
        card.start_loading()
        assert card._value_label.isHidden()
        assert card._spinner.isVisible()
        assert card._spinner.is_running
        card.set_value("2/4", subtitle="Quorum: OK")
        assert not card._value_label.isHidden()
        assert not card._spinner.isVisible()
        assert not card._spinner.is_running
        assert card._value_label.text() == "2/4"

    def test_stop_loading_direct(self, qtbot):
        card = MetricCard("CPU", "—")
        qtbot.addWidget(card)
        card.start_loading()
        card.stop_loading()
        assert not card._value_label.isHidden()
        assert not card._spinner.is_running
