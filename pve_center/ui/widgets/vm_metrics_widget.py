from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..i18n import tr
from ..theme import Color

try:
    import pyqtgraph as pg
    pg.setConfigOption('background', 'w')
    pg.setConfigOption('foreground', 'k')
    _HAS_PG = True
except ImportError:
    pg = None
    _HAS_PG = False

_METRIC_KEYS = [("cpu", "CPU"), ("ram", "RAM"), ("net", "Network"), ("disk", "Disk")]


def _metric_label(key):
    for k, label in _METRIC_KEYS:
        if k == key:
            return tr(label)
    return key


class VmMetricsWidget(QWidget):
    timeframe_changed = Signal(str)
    metric_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._has_plot = False
        self._cached_data = None
        self._disk_visible = True

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        top.addWidget(QLabel(tr("Metric") + ":"))
        self.metric_combo = QComboBox()
        for key, _ in _METRIC_KEYS:
            self.metric_combo.addItem(_metric_label(key), key)
        self.metric_combo.setCurrentIndex(0)
        self.metric_combo.currentIndexChanged.connect(self._on_metric_changed)
        top.addWidget(self.metric_combo)
        top.addSpacing(16)
        top.addWidget(QLabel(tr("Interval") + ":"))
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItem(tr("hour"), "hour")
        self.timeframe_combo.addItem(tr("day"), "day")
        self.timeframe_combo.addItem(tr("week"), "week")
        self.timeframe_combo.addItem(tr("month"), "month")
        self.timeframe_combo.addItem(tr("year"), "year")
        self.timeframe_combo.setCurrentIndex(0)
        self.timeframe_combo.currentIndexChanged.connect(
            lambda: self.timeframe_changed.emit(self.timeframe_combo.currentData())
        )
        top.addWidget(self.timeframe_combo)
        top.addStretch()
        self._layout.addLayout(top)

        if _HAS_PG:
            date_axis = pg.DateAxisItem(orientation='bottom')
            self.plot = pg.PlotWidget(axisItems={'bottom': date_axis}, title=tr("CPU, %"))
            self.plot.setLabel('left', '%')
            self.plot.showGrid(x=True, y=True)
            self.plot.enableAutoRange(axis='y')
            self.curve = self.plot.plot([], [], pen=pg.mkPen(Color.SLATE_900, width=2))
            self.plot.setMouseEnabled(x=False, y=False)
            self._legend = self.plot.addLegend()
            self._layout.addWidget(self.plot, 1)
            self._has_plot = True
        else:
            self._layout.addWidget(QLabel(tr("PyQtGraph not installed. Charts unavailable.")))

    def _on_metric_changed(self):
        key = self.metric_combo.currentData()
        self.metric_changed.emit(key)
        self._render_current_metric()

    def show_disk_io(self, visible=True):
        self._disk_visible = visible
        current_key = self.metric_combo.currentData()
        expected_keys = [k for k, _ in _METRIC_KEYS if visible or k != "disk"]
        current_keys = [self.metric_combo.itemData(i) for i in range(self.metric_combo.count())]
        if current_keys == expected_keys:
            return
        self.metric_combo.blockSignals(True)
        self.metric_combo.clear()
        for key in expected_keys:
            self.metric_combo.addItem(_metric_label(key), key)
        self.metric_combo.blockSignals(False)
        if current_key in expected_keys:
            idx = expected_keys.index(current_key)
        else:
            idx = 0
        self.metric_combo.setCurrentIndex(idx)
        self._on_metric_changed()

    def clear_curves(self):
        self._cached_data = None
        if self._has_plot:
            self.plot.clear()
            self.curve = self.plot.plot([], [], pen=pg.mkPen(Color.SLATE_900, width=2))

    def update_curves(self, metrics_dict):
        self._cached_data = metrics_dict
        self._render_current_metric()

    def _render_current_metric(self):
        if not self._has_plot or self._cached_data is None:
            return
        metric = self.metric_combo.currentData()
        data = self._cached_data

        self.plot.clear()
        if self._legend:
            self._legend.clear()
        self.curve = self.plot.plot([], [], pen=pg.mkPen(Color.SLATE_900, width=2))

        if metric == "cpu":
            cpu = data.get('cpu', [])
            if cpu:
                self.curve.setData([d['time'] for d in cpu], [d['value'] for d in cpu])
            self.plot.setTitle(tr("CPU, %"))
            self.plot.setLabel('left', '%')

        elif metric == "ram":
            mem = data.get('mem', [])
            if mem:
                self.curve.setData([d['time'] for d in mem],
                                   [d['value'] / (1024**3) for d in mem])
                maxmem = data.get('maxmem', 0)
                if maxmem > 0:
                    self.plot.setYRange(0, (maxmem / (1024**3)) * 1.05)
            self.plot.setTitle(tr("RAM, GiB"))
            self.plot.setLabel('left', 'GiB')

        elif metric == "net":
            netin = data.get('netin', [])
            netout = data.get('netout', [])
            self._render_dual(netin, netout, tr("Network traffic"), "B")

        elif metric == "disk":
            diskread = data.get('diskread', [])
            diskwrite = data.get('diskwrite', [])
            self._render_dual(diskread, diskwrite, tr("Disk I/O"), "B")

    def _render_dual(self, data1, data2, title, default_unit):
        all_data = data1 + data2
        self.plot.setTitle(title)
        if not all_data:
            self.plot.setLabel('left', default_unit)
            return
        max_val = max(abs(d['value']) for d in all_data)
        if max_val < 1024:
            unit, div = 'B', 1
        elif max_val < 1024**2:
            unit, div = 'KB', 1024
        elif max_val < 1024**3:
            unit, div = 'MB', 1024**2
        else:
            unit, div = 'GB', 1024**3

        label_in = tr("In") if title == tr("Network traffic") else tr("Read")
        label_out = tr("Out") if title == tr("Network traffic") else tr("Write")
        self.plot.plot([d['time'] for d in data1], [d['value'] / div for d in data1],
                       pen=pg.mkPen(Color.SLATE_900, width=2), name=label_in)
        self.plot.plot([d['time'] for d in data2], [d['value'] / div for d in data2],
                       pen=pg.mkPen(Color.GRAY_400, width=2), name=label_out)
        self.plot.setLabel('left', unit)
