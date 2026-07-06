from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget

from ..theme import Color


class MetricCard(QWidget):
    def __init__(self, title="", value="", subtitle="", show_progress=False, parent=None):
        super().__init__(parent)
        self._show_progress = show_progress
        self._progress = 0

        self.setStyleSheet(f"""
            MetricCard {{
                background: {Color.PANEL};
                border: 1px solid {Color.BORDER};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(
            f"color: {Color.TEXT_SEC}; font-size: 11px; font-weight: 600;"
            " text-transform: uppercase; letter-spacing: 0.5px;"
        )
        layout.addWidget(self._title_label)

        self._value_label = QLabel(value)
        f = QFont()
        f.setPointSize(16)
        f.setBold(True)
        self._value_label.setFont(f)
        self._value_label.setStyleSheet(f"color: {Color.TEXT};")
        layout.addWidget(self._value_label)

        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setStyleSheet(f"color: {Color.TEXT_DIM}; font-size: 11px;")
        if subtitle:
            self._subtitle_label.show()
        else:
            self._subtitle_label.hide()
        layout.addWidget(self._subtitle_label)

        if show_progress:
            self._bar = QProgressBar()
            self._bar.setRange(0, 100)
            self._bar.setFixedHeight(6)
            self._bar.setTextVisible(False)
            self._bar.setStyleSheet(
                f"QProgressBar {{ background: {Color.GRAY_100}; border: none; border-radius: 3px; }}"
                f"QProgressBar::chunk {{ background: {Color.STATUS_OK}; border-radius: 3px; }}"
            )
            layout.addSpacing(4)
            layout.addWidget(self._bar)
        else:
            self._bar = None

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_title(self, title):
        self._title_label.setText(title)

    def set_value(self, value):
        self._value_label.setText(str(value))

    def set_subtitle(self, subtitle):
        self._subtitle_label.setText(str(subtitle))
        self._subtitle_label.show() if subtitle else self._subtitle_label.hide()

    def set_progress(self, pct, color=None):
        if not self._bar:
            return
        self._progress = max(0, min(100, int(pct)))
        self._bar.setValue(self._progress)
        if color:
            self._bar.setStyleSheet(
                f"QProgressBar {{ background: {Color.GRAY_100}; border: none; border-radius: 3px; }}"
                f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}"
            )

    def set_value_color(self, color):
        self._value_label.setStyleSheet(f"color: {color};")
