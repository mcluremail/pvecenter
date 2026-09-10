"""Tests for B11: custom metric time range + CSV export."""
from datetime import datetime

import pytest

from pve_center.ui.widgets import vm_metrics_widget as vmw
from pve_center.ui.widgets.time_range import (
    RangeDialog,
    covering_preset,
    filter_series,
    write_metrics_csv,
)


def _pt(t, v=1.0):
    return {"time": t, "value": v}


class TestCoveringPreset:
    @pytest.mark.parametrize("start,end,expected", [
        (0, 0, "hour"),
        (0, 3600, "hour"),
        (0, 3601, "day"),
        (0, 86400, "day"),
        (0, 604800, "week"),
        (0, 2592000, "month"),
        (0, 2592001, "year"),
        (0, 10**9, "year"),
    ])
    def test_boundaries(self, start, end, expected):
        assert covering_preset(start, end) == expected


class TestFilterSeries:
    def test_none_range_returns_all(self):
        series = [_pt(1), _pt(2)]
        out = filter_series(series, None, None)
        assert out == series and out is not series

    def test_inclusive_bounds(self):
        series = [_pt(10), _pt(20), _pt(30), _pt(40)]
        out = filter_series(series, 20, 30)
        assert [p["time"] for p in out] == [20, 30]

    def test_none_series(self):
        assert filter_series(None, 0, 10) == []


class TestWriteMetricsCsv:
    def test_union_rows_and_gaps(self, tmp_path):
        path = tmp_path / "out.csv"
        write_metrics_csv(path, {
            "a": [_pt(2, 0.2), _pt(1, 0.1)],
            "b": [_pt(2, 5), _pt(3, 6)],
        })
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert lines[0] == "time,a,b"
        assert len(lines) == 4  # header + 3 union times
        assert lines[1].endswith(",0.1,")
        assert lines[2].endswith(",0.2,5")
        assert lines[3].endswith(",,6")
        # time column is ISO 8601
        t = lines[1].split(",")[0]
        datetime.fromisoformat(t)

    def test_empty_series(self, tmp_path):
        path = tmp_path / "out.csv"
        write_metrics_csv(path, {})
        assert path.read_text(encoding="utf-8").strip() == "time"


class TestRangeDialog:
    def test_defaults_and_bounds(self, qtbot):
        dlg = RangeDialog()
        qtbot.addWidget(dlg)
        s, e = dlg.values()
        assert e > s
        # end is bounded to [from, from + MAX_SPAN_DAYS]
        dlg._from.setDateTime(dlg._from.dateTime())
        to_min = dlg._to.minimumDateTime().toSecsSinceEpoch()
        to_max = dlg._to.maximumDateTime().toSecsSinceEpoch()
        assert to_min == s
        assert to_max - s == 365 * 86400

    def test_values_roundtrip(self, qtbot):
        dlg = RangeDialog()
        qtbot.addWidget(dlg)
        dlg._from.setDateTime(dlg._from.dateTime().addSecs(-100))
        s, e = dlg.values()
        assert e > s


@pytest.fixture()
def widget(qtbot):
    w = vmw.VmMetricsWidget()
    qtbot.addWidget(w)
    w.ensure_plot()
    return w


class TestVmMetricsWidgetCustomRange:
    def test_custom_accept_emits_and_sets_range(self, widget, qtbot):
        widget._ask_range = lambda: (100, 200)
        emitted = []
        widget.timeframe_changed.connect(emitted.append)
        widget.timeframe_combo.setCurrentIndex(widget.timeframe_combo.count() - 1)
        assert emitted == ["custom"]
        assert widget.custom_range() == (100, 200)
        assert widget.fetch_timeframe() == ("hour", (100, 200))

    def test_custom_cancel_reverts_without_emit(self, widget, qtbot):
        widget._ask_range = lambda: None
        emitted = []
        widget.timeframe_changed.connect(emitted.append)
        prev = widget.timeframe_combo.currentIndex()
        widget.timeframe_combo.setCurrentIndex(widget.timeframe_combo.count() - 1)
        assert emitted == []
        assert widget.timeframe_combo.currentIndex() == prev
        assert widget.custom_range() is None

    def test_preset_clears_range(self, widget, qtbot):
        widget._ask_range = lambda: (100, 200)
        widget.timeframe_combo.setCurrentIndex(widget.timeframe_combo.count() - 1)
        assert widget.custom_range() == (100, 200)
        widget.timeframe_combo.setCurrentIndex(0)
        assert widget.custom_range() is None
        assert widget.fetch_timeframe() == ("hour", None)

    def test_render_filters_points(self, widget, qtbot):
        widget._ask_range = lambda: (150, 250)
        widget.timeframe_combo.setCurrentIndex(widget.timeframe_combo.count() - 1)
        widget.update_curves({
            "cpu": [_pt(100, 1), _pt(200, 2), _pt(300, 3)],
            "mem": [_pt(100, 1), _pt(200, 2), _pt(300, 3)],
        })
        x, _y = widget.curve.getData()
        assert list(x) == [200]


class TestVmMetricsWidgetCsv:
    def test_export_filtered_current_metric(self, widget, qtbot, tmp_path, monkeypatch):
        out = tmp_path / "m.csv"
        monkeypatch.setattr(
            vmw.QFileDialog, "getSaveFileName",
            staticmethod(lambda *a, **k: (str(out), "")),
        )
        widget._ask_range = lambda: (150, 250)
        widget.timeframe_combo.setCurrentIndex(widget.timeframe_combo.count() - 1)
        widget.update_curves({
            "cpu": [_pt(100, 0.1), _pt(200, 0.2), _pt(300, 0.3)],
            "mem": [_pt(100, 1), _pt(200, 2), _pt(300, 3)],
        })
        widget._export_btn.click()
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert lines[0] == "time,cpu"
        assert len(lines) == 2  # only the in-range point

    def test_export_no_data_writes_nothing(self, widget, tmp_path, monkeypatch):
        out = tmp_path / "none.csv"
        monkeypatch.setattr(
            vmw.QFileDialog, "getSaveFileName",
            staticmethod(lambda *a, **k: (str(out), "")),
        )
        widget._cached_data = {"cpu": []}
        widget._export_btn.click()
        assert not out.exists()
