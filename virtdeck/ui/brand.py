"""Бренд VirtDeck: знак и локап для интерфейса.

Знак — вариант «оранжевая X с серверной стойкой» (выбран владельцем,
2026-09-14): скрещённые оранжевые ленты + тёмная стойка со светлыми
полками и акцентными точками. Цвета знака фиксированы (бренд не
перекрашивается темами); слово «Deck» в локапе следует цвету текста
темы (Color.TEXT).
"""

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

ORANGE = "#f97316"
DARK = "#242b33"

MARK_SVG = f"""<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
<line x1="12" y1="12" x2="52" y2="52" stroke="{ORANGE}" stroke-width="14" stroke-linecap="round"/>
<line x1="52" y1="12" x2="12" y2="52" stroke="{ORANGE}" stroke-width="14" stroke-linecap="round"/>
<rect x="19" y="16" width="26" height="32" rx="4" fill="{DARK}"/>
<rect x="23" y="21" width="18" height="6" rx="2" fill="#eef2f5"/>
<rect x="23" y="29" width="18" height="6" rx="2" fill="#eef2f5"/>
<rect x="23" y="37" width="18" height="6" rx="2" fill="#eef2f5"/>
<circle cx="36.5" cy="24" r="1.4" fill="#94a3b8"/>
<circle cx="39.5" cy="24" r="1.4" fill="{ORANGE}"/>
<circle cx="36.5" cy="32" r="1.4" fill="#94a3b8"/>
<circle cx="39.5" cy="32" r="1.4" fill="{ORANGE}"/>
<circle cx="36.5" cy="40" r="1.4" fill="#94a3b8"/>
<circle cx="39.5" cy="40" r="1.4" fill="{ORANGE}"/>
</svg>"""


def render_pixmap(size: int) -> QPixmap:
    """Знак в виде QPixmap заданного размера (чёткий векторный рендер)."""
    renderer = QSvgRenderer(QByteArray(MARK_SVG.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def make_logo_icon(size: int = 256) -> QIcon:
    """Иконка приложения (окно, панель задач, трей)."""
    return QIcon(render_pixmap(size))


class BrandWidget(QWidget):
    """Локап в тулбаре: знак + «VirtDeck» (Virt оранжевый, Deck — тема)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(6)
        mark = QLabel(self)
        mark.setPixmap(render_pixmap(22))
        mark.setFixedSize(22, 22)
        self._wordmark = QLabel(self)
        layout.addWidget(mark)
        layout.addWidget(self._wordmark)
        self.restyle()

    def restyle(self):
        """Перекраска слово-части под активную тему (движок тем)."""
        from .theme import Color

        self._wordmark.setText(
            f'<span style="color:{ORANGE};">Virt</span>'
            f'<span style="color:{Color.TEXT};">Deck</span>'
        )


def make_brand_widget(parent=None) -> BrandWidget:
    return BrandWidget(parent)
