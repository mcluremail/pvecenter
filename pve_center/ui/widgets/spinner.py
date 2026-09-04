"""Animated spinner for asynchronous loading states.

The timer runs only while the widget is visible: showEvent starts it,
hideEvent stops it, so embedding the spinner in a stacked loading page
needs no manual start/stop wiring.
"""
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..theme import Color


class SpinnerWidget(QWidget):
    def __init__(self, diameter=28, parent=None, color=None):
        super().__init__(parent)
        self._diameter = diameter
        self._color = QColor(color or Color.ACCENT)
        self._angle = 0
        self._span = 100 * 16  # arc sweep, 1/16 degree units
        self.setFixedSize(diameter, diameter)
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._tick)
        self.hide()

    @property
    def is_running(self):
        return self._timer.isActive()

    def start(self):
        self.show()

    def stop(self):
        self.hide()

    def _tick(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self._color, max(2.0, self._diameter / 10.0))
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        margin = pen.widthF() / 2 + 1
        rect = QRectF(
            margin, margin,
            self._diameter - 2 * margin, self._diameter - 2 * margin,
        )
        painter.drawArc(rect, -self._angle * 16, self._span)
