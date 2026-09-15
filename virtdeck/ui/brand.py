"""Бренд VirtDeck: фирменный кит дизайнера (монограмма V+D, 2026-09-15).

Ассеты — векторные SVG из `virtdeck/ui/brand_assets/`: иконки приложения
(светлая/тёмная плитка), локапы, знаки (в т.ч. монохромные) и трей-набор
с состояниями ok/error/offline/update. Цвета бренда фиксированы; тема
выбирает только светлый/тёмный вариант (по яркости Color.BG).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

ASSETS = Path(__file__).parent / "brand_assets"
TRAY_STATES = ("ok", "error", "offline", "update")
MARK_VARIANTS = ("light", "dark", "mono", "mono-white")

# Кэш иконок: трей перерисовывается каждый цикл refresh, рендер SVG не нужен
_ICON_CACHE: dict[tuple, QIcon] = {}

_LOCKUP_ASPECT = 1240 / 320  # viewBox локапа дизайнера


def _svg_bytes(name: str) -> QByteArray:
    return QByteArray((ASSETS / f"{name}.svg").read_bytes())


def _render(name: str, width: int, height: int) -> QPixmap:
    renderer = QSvgRenderer(_svg_bytes(name))
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def is_dark() -> bool:
    """Текущая тема тёмная? Эвристика по яркости фона Color.BG."""
    from .theme import Color

    hexval = Color.BG.lstrip("#")
    try:
        r, g, b = (int(hexval[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return False
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0 < 0.5


def _variant(variant: str | None) -> str:
    """Разрешение варианта: 'light'|'dark' (None → по теме)."""
    v = variant or ("dark" if is_dark() else "light")
    if v not in ("light", "dark"):
        raise ValueError(f"unknown brand variant: {variant!r}")
    return v


def render_pixmap(size: int, variant: str = "light") -> QPixmap:
    """Знак (монограмма без плитки) в виде QPixmap заданного размера.

    Варианты знака: light/dark (цветные) и mono/mono-white (монохром).
    """
    if variant not in MARK_VARIANTS:
        raise ValueError(f"unknown mark variant: {variant!r}")
    return _render(f"mark-{variant}", size, size)


def lockup_pixmap(height: int = 22, variant: str | None = None) -> QPixmap:
    """Локап «знак + VirtDeck» с сохранением пропорций дизайнера."""
    width = max(1, round(height * _LOCKUP_ASPECT))
    return _render(f"lockup-{_variant(variant)}", width, height)


def make_logo_icon(size: int = 256, variant: str | None = None) -> QIcon:
    """Иконка приложения (плитка дизайнера: окно, панель задач)."""
    v = _variant(variant)
    key = ("logo", v, size)
    icon = _ICON_CACHE.get(key)
    if icon is None:
        icon = QIcon(_render(f"icon-{v}", size, size))
        _ICON_CACHE[key] = icon
    return icon


def tray_icon(state: str = "ok", variant: str | None = None,
              compact: bool = False) -> QIcon:
    """Трей-иконка состояния: ok | error | offline | update."""
    if state not in TRAY_STATES:
        raise ValueError(f"unknown tray state: {state!r}")
    v = _variant(variant)
    name = f"tray-{state}-{v}" + ("-compact" if compact else "")
    key = ("tray", name)
    icon = _ICON_CACHE.get(key)
    if icon is None:
        icon = QIcon(_render(name, 64, 64))
        _ICON_CACHE[key] = icon
    return icon


class BrandWidget(QWidget):
    """Локап в тулбаре: векторный локап дизайнера, вариант по теме."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(0)
        self._label = QLabel(self)
        self._variant: str | None = None
        layout.addWidget(self._label)
        self.restyle()

    def restyle(self):
        """Переключение варианта локапа под активную тему (движок тем)."""
        v = _variant(None)
        if v == self._variant and not self._label.pixmap().isNull():
            return
        self._variant = v
        self._label.setPixmap(lockup_pixmap(22, v))
        self._label.setFixedSize(self._label.pixmap().size())


def make_brand_widget(parent=None) -> BrandWidget:
    return BrandWidget(parent)
