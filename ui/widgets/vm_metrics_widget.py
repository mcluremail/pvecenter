# pve_center/ui/widgets/vm_metrics_widget.py
from PySide6.QtWidgets import QVBoxLayout, QWidget, QComboBox, QHBoxLayout, QLabel
from PySide6.QtCore import Signal

try:
    import pyqtgraph as pg
    pg.setConfigOption('background', 'w')
    pg.setConfigOption('foreground', 'k')
    _HAS_PG = True
except ImportError:
    pg = None
    _HAS_PG = False

METRICS = ["ЦП", "ОЗУ", "Сеть", "Диск"]

class VmMetricsWidget(QWidget):
    timeframe_changed = Signal(str)
    metric_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot_widget = False
        self._cached_data = None
        self._disk_visible = True

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # Верхняя панель: выбор метрики + интервал
        top = QHBoxLayout()
        top.addWidget(QLabel("Метрика:"))
        self.metric_combo = QComboBox()
        self.metric_combo.addItems(METRICS)
        self.metric_combo.setCurrentText("ЦП")
        self.metric_combo.currentTextChanged.connect(self._on_metric_changed)
        top.addWidget(self.metric_combo)
        top.addSpacing(16)
        top.addWidget(QLabel("Интервал:"))
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItem("час", "hour")
        self.timeframe_combo.addItem("день", "day")
        self.timeframe_combo.addItem("неделя", "week")
        self.timeframe_combo.addItem("месяц", "month")
        self.timeframe_combo.addItem("год", "year")
        self.timeframe_combo.setCurrentIndex(0)
        self.timeframe_combo.currentIndexChanged.connect(
            lambda: self.timeframe_changed.emit(self.timeframe_combo.currentData())
        )
        top.addWidget(self.timeframe_combo)
        top.addStretch()
        self._layout.addLayout(top)

        if _HAS_PG:
            date_axis = pg.DateAxisItem(orientation='bottom')
            self.plot = pg.PlotWidget(axisItems={'bottom': date_axis}, title="ЦП, %")
            self.plot.setLabel('left', '%')
            self.plot.showGrid(x=True, y=True)
            self.plot.enableAutoRange(axis='y')
            self.curve = self.plot.plot([], [], pen=pg.mkPen('#374151', width=2))
            self.plot.setMouseEnabled(x=False, y=False)
            self._layout.addWidget(self.plot, 1)

            self.plot_widget = True
        else:
            self._layout.addWidget(QLabel("PyQtGraph не установлен. Графики недоступны."))

    def _on_metric_changed(self, metric):
        self.metric_changed.emit(metric)
        self._render_current_metric()

    def show_disk_io(self, visible=True):
        self._disk_visible = visible
        current = self.metric_combo.currentText()
        if visible:
            self.metric_combo.clear()
            self.metric_combo.addItems(METRICS)
        else:
            self.metric_combo.clear()
            self.metric_combo.addItems([m for m in METRICS if m != "Диск"])
        if current in [self.metric_combo.itemText(i) for i in range(self.metric_combo.count())]:
            self.metric_combo.setCurrentText(current)
        else:
            self.metric_combo.setCurrentText("ЦП")

    def clear_curves(self):
        self._cached_data = None
        if self.plot_widget:
            self.curve.setData([], [])

    def set_ram_range(self, max_bytes):
        pass

    def update_curves(self, metrics_dict):
        self._cached_data = metrics_dict
        self._render_current_metric()

    def _render_current_metric(self):
        if not self.plot_widget or self._cached_data is None:
            return
        metric = self.metric_combo.currentText()
        data = self._cached_data

        if metric == "ЦП":
            cpu = data.get('cpu', [])
            if cpu:
                self.curve.setData([d['time'] for d in cpu], [d['value'] for d in cpu])
            else:
                self.curve.setData([], [])
            self.plot.setTitle("ЦП, %")
            self.plot.setLabel('left', '%')

        elif metric == "ОЗУ":
            mem = data.get('mem', [])
            if mem:
                self.curve.setData([d['time'] for d in mem],
                                   [d['value'] / (1024**3) for d in mem])
                maxmem = data.get('maxmem', 0)
                if maxmem > 0:
                    self.plot.setYRange(0, (maxmem / (1024**3)) * 1.05)
            else:
                self.curve.setData([], [])
            self.plot.setTitle("ОЗУ, GiB")
            self.plot.setLabel('left', 'GiB')

        elif metric == "Сеть":
            netin = data.get('netin', [])
            netout = data.get('netout', [])
            self._format_and_set(netin, netout, "Сетевой трафик", "B")

        elif metric == "Диск":
            diskread = data.get('diskread', [])
            diskwrite = data.get('diskwrite', [])
            self._format_and_set(diskread, diskwrite, "Дисковый ввод/вывод", "B")

    def _format_and_set(self, data1, data2, title, default_unit):
        all_data = data1 + data2
        if not all_data:
            self.curve.setData([], [])
            self.plot.setTitle(title)
            self.plot.setLabel('left', default_unit)
            self.plot.clear()
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

        self.plot.clear()
        label_in = 'In' if title == "Сетевой трафик" else 'Read'
        label_out = 'Out' if title == "Сетевой трафик" else 'Write'
        self.plot.plot([d['time'] for d in data1], [d['value'] / div for d in data1],
                       pen=pg.mkPen('#374151', width=2), name=label_in)
        self.plot.plot([d['time'] for d in data2], [d['value'] / div for d in data2],
                       pen=pg.mkPen('#9ca3af', width=2), name=label_out)
        self.plot.setTitle(title)
        self.plot.setLabel('left', unit)
        self.plot.addLegend()

