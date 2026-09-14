"""Arbitrary time-range selection for RRD metric charts (B11).

PVE ``/rrddata`` only accepts preset timeframes (hour/day/week/month/year),
each covering a fixed look-back window. A custom range is served by
requesting the smallest preset that fully covers the span and filtering
the returned points client-side.
"""

import csv
from datetime import datetime

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
)

from ..i18n import tr

# Preset -> maximum span (seconds) it fully covers.
_PRESET_SPANS = [
    ("hour", 3600),
    ("day", 86400),
    ("week", 7 * 86400),
    ("month", 30 * 86400),
]

MAX_SPAN_DAYS = 365


def covering_preset(start, end):
    """Smallest PVE rrddata preset covering the [start, end] epoch span."""
    span = max(0, end - start)
    for tf, limit in _PRESET_SPANS:
        if span <= limit:
            return tf
    return "year"


def filter_series(series, start, end):
    """Keep points with start <= time <= end (bounds inclusive)."""
    if start is None or end is None:
        return list(series or [])
    return [pt for pt in (series or []) if start <= pt["time"] <= end]


def write_metrics_csv(path, series_map):
    """Write named series (dict name -> [{'time', 'value'}, ...]) as CSV.

    Rows are the union of point times (sorted); a series missing a point
    for a given time gets an empty cell.
    """
    rows = {}
    times = set()
    for name, series in series_map.items():
        for pt in series or []:
            times.add(pt["time"])
            rows.setdefault(pt["time"], {})[name] = pt["value"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time"] + list(series_map.keys()))
        for t in sorted(times):
            row = rows.get(t, {})
            w.writerow(
                [datetime.fromtimestamp(t).isoformat(timespec="seconds")]
                + [row.get(c, "") for c in series_map.keys()]
            )


class RangeDialog(QDialog):
    """Pick a [from, to] range; the end is bounded to the preset coverage."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Select time range"))
        self.setMinimumWidth(340)

        form = QFormLayout(self)
        self._from = QDateTimeEdit(QDateTime.currentDateTime().addDays(-1))
        self._from.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._to = QDateTimeEdit(QDateTime.currentDateTime())
        self._to.setDisplayFormat("yyyy-MM-dd HH:mm")
        form.addRow(tr("From:"), self._from)
        form.addRow(tr("To:"), self._to)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        form.addRow(self._buttons)

        self._from.dateTimeChanged.connect(self._sync_bounds)
        self._sync_bounds()

    def _sync_bounds(self):
        start = self._from.dateTime()
        self._to.setMinimumDateTime(start)
        self._to.setMaximumDateTime(start.addDays(MAX_SPAN_DAYS))

    def values(self):
        """Selected range as (start_epoch, end_epoch) seconds."""
        return (
            self._from.dateTime().toSecsSinceEpoch(),
            self._to.dateTime().toSecsSinceEpoch(),
        )
