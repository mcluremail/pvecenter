"""Built-in themes (ThemePlugin v1).

Точечные значения палитр взяты из схем KDE: breeze (colors/BreezeLight.
colors, BreezeDark.colors) и oxygen (color-schemes/Oxygen.colors).
Значения с комментарием «derived» в схемах отсутствуют — выведены из
базовых цветов схем (Breeze рисует disabled через ColorEffects, бордеров
в схемах нет). Graphite — собственная нейтральная тема.
"""

from __future__ import annotations

from ..ui.theme import LIGHT_TOKENS
from .base import ThemePlugin


class LightTheme:
    """Светлая тема — встроенный плагин поверх дефолтной палитры."""

    _tokens: dict[str, str] | None = None

    @property
    def id(self) -> str:
        return "light"

    @property
    def name(self) -> str:
        return "Light"

    def tokens(self) -> dict[str, str]:
        # Снимок делается лениво при первом tokens(): к этому моменту
        # Color ещё держит дефолтную (светлую) палитру, а повторные
        # активации не должны наследовать значения чужих тем.
        if LightTheme._tokens is None:
            LightTheme._tokens = dict(LIGHT_TOKENS)
        return dict(LightTheme._tokens)

    def extra_qss(self) -> str:
        return ""

    def icons(self) -> dict[str, str] | None:
        return None

    @property
    def icon_size(self) -> int:
        return 16


# ── Breeze (KDE Plasma) ─────────────────────────────────────────────

BREEZE_ICONS = {
    "vm": """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
<rect x="2.5" y="3.5" width="19" height="13" rx="2" fill="none" stroke="{c}" stroke-width="1.8"/>
<path d="M8 20.5 L8 17 M16 20.5 L16 17 M5.5 20.5 L18.5 20.5" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>
</svg>""",
    "host": """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
<rect x="3" y="2.5" width="18" height="19" rx="2" fill="none" stroke="{c}" stroke-width="1.8"/>
<line x1="6.5" y1="7.5" x2="13" y2="7.5" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>
<line x1="6.5" y1="12" x2="15" y2="12" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>
<line x1="6.5" y1="16.5" x2="10" y2="16.5" stroke="{c2}" stroke-width="1.8" stroke-linecap="round"/>
</svg>""",
    "cluster": """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
<circle cx="12" cy="12" r="3" fill="{c2}" stroke="{c}" stroke-width="1.8"/>
<circle cx="4.5" cy="5" r="2.25" fill="none" stroke="{c}" stroke-width="1.8"/>
<circle cx="19.5" cy="5" r="2.25" fill="none" stroke="{c}" stroke-width="1.8"/>
<circle cx="4.5" cy="19" r="2.25" fill="none" stroke="{c}" stroke-width="1.8"/>
<circle cx="19.5" cy="19" r="2.25" fill="none" stroke="{c}" stroke-width="1.8"/>
<line x1="12" y1="9" x2="6.2" y2="6.8" stroke="{c}" stroke-width="1.6"/>
<line x1="12" y1="9" x2="17.8" y2="6.8" stroke="{c}" stroke-width="1.6"/>
<line x1="12" y1="15" x2="6.2" y2="17.2" stroke="{c}" stroke-width="1.6"/>
<line x1="12" y1="15" x2="17.8" y2="17.2" stroke="{c}" stroke-width="1.6"/>
</svg>""",
    "pool": """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
<path d="M2 6 L7 6 L9 4 L22 4 L22 19 L2 19 Z" fill="none" stroke="{c}" stroke-width="1.8" stroke-linejoin="round"/>
<rect x="7" y="10.5" width="10" height="5.5" rx="1" fill="none" stroke="{c}" stroke-width="1.6"/>
<line x1="9.5" y1="16" x2="14.5" y2="16" stroke="{c}" stroke-width="1.6" stroke-linecap="round"/>
</svg>""",
    "storage": """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
<ellipse cx="12" cy="5.5" rx="8.5" ry="3" fill="none" stroke="{c}" stroke-width="1.8"/>
<path d="M3.5 5.5 L3.5 18.5 A8.5 3 0 0 0 20.5 18.5 L20.5 5.5" fill="none" stroke="{c}" stroke-width="1.8"/>
<circle cx="16.5" cy="17.5" r="1.5" fill="{c2}"/>
</svg>""",
    "backup": """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
<path d="M6 2.5 L14 2.5 L18.5 7 L18.5 21.5 L6 21.5 Z" fill="none" stroke="{c}" stroke-width="1.8" stroke-linejoin="round"/>
<path d="M14 2.5 L14 7 L18.5 7" fill="none" stroke="{c}" stroke-width="1.6" stroke-linejoin="round"/>
<path d="M12 18 L12 11.5 M9.5 14 L12 11.5 L14.5 14" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "refresh": """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
<path d="M4.5 12 A7.5 7.5 0 0 1 18 7.5" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"/>
<polyline points="18.5,3.5 18.5,8 14,8" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M19.5 12 A7.5 7.5 0 0 1 6 16.5" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"/>
<polyline points="5.5,20.5 5.5,16 10,16" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "search": """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
<circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="{c}" stroke-width="2"/>
<line x1="15.3" y1="15.3" x2="20.5" y2="20.5" stroke="{c}" stroke-width="2" stroke-linecap="round"/>
</svg>""",
}

_BREEZE_DENSITY_QSS = """
/* Плотность под иконки 24px (Breeze) */
QTreeWidget::item, QTreeView::item { padding: 3px 2px; }
QToolBar QToolButton { padding: 3px; margin: 1px; }
"""


class BreezeTheme:
    """Breeze Light — светлая тема KDE Plasma (иконки 24px)."""

    _TOKENS: dict[str, str] = {
        "BG": "#eff0f1",            # Window
        "PANEL": "#fcfcfc",         # Button
        "RAISED": "#ffffff",        # View
        "TRACK": "#e3e5e7",         # Window alternate
        "ALT_ROW": "#f7f7f7",       # View alternate
        "BORDER": "#c3c7cb",        # derived
        "BORDER_LIGHT": "#d8dbde",  # derived
        "BORDER_STRONG": "#a7abaf",  # derived
        "TEXT": "#232629",          # Window foreground
        "TEXT_SEC": "#707d8a",      # Window inactive
        "TEXT_DIM": "#98a2ab",      # derived
        "DISABLED": "#a7abaf",      # derived (ColorEffects:Disabled)
        "ON_ACCENT": "#ffffff",     # Selection foreground
        "ACCENT": "#3daee9",        # DecorationFocus
        "ACCENT_HOVER": "#55b8ec",  # derived
        "ACCENT_LIGHT": "#a3d4fa",  # Button alternate (inactive selection)
        "ACCENT_PRESSED": "#2f96d3",  # derived
        "SUCCESS": "#27ae60",       # Positive
        "SUCCESS_LIGHT": "#e2f6ea",  # derived
        "WARNING": "#f67400",       # Neutral
        "WARNING_TEXT": "#a95400",  # derived
        "DANGER": "#da4453",        # Negative
        "DANGER_SOLID": "#da4453",
        "DANGER_SOLID_HOVER": "#e36a76",  # derived
        "DANGER_SOLID_PRESSED": "#b03745",  # Selection negative
        "STATUS_OK": "#27ae60",
        "STATUS_WARN": "#f67400",
        "STATUS_ERR": "#da4453",
        "HOVER": "#e3e5e7",         # Window alternate
        "ROW_WARN": "#fdf1e3",      # derived (warning tint)
        "TOAST_BG": "#2a2e32",      # Complementary background
        "SCROLLBAR_BG": "#f0f1f2",  # derived
        "SCROLLBAR_HANDLE": "#b9bec4",  # derived
        "SCROLLBAR_HOVER": "#9fa6ad",  # derived
        "ICON_FG": "#232629",
        "ICON_FG_DIM": "#707d8a",
    }

    @property
    def id(self) -> str:
        return "breeze"

    @property
    def name(self) -> str:
        return "Breeze"

    def tokens(self) -> dict[str, str]:
        return dict(self._TOKENS)

    def extra_qss(self) -> str:
        return _BREEZE_DENSITY_QSS

    def icons(self) -> dict[str, str] | None:
        return BREEZE_ICONS

    @property
    def icon_size(self) -> int:
        return 24


class BreezeDarkTheme(BreezeTheme):
    """Breeze Dark — тёмная тема KDE Plasma (иконки 24px)."""

    _TOKENS: dict[str, str] = {
        "BG": "#202326",            # Window
        "PANEL": "#292c30",         # Button
        "RAISED": "#141618",        # View
        "TRACK": "#2c3034",         # derived
        "ALT_ROW": "#1d1f22",       # View alternate
        "BORDER": "#3b4046",        # derived
        "BORDER_LIGHT": "#34383d",  # derived
        "BORDER_STRONG": "#4d5359",  # derived
        "TEXT": "#fcfcfc",          # Window foreground
        "TEXT_SEC": "#a1a9b1",      # Window inactive
        "TEXT_DIM": "#7d868e",      # derived
        "DISABLED": "#6a7178",      # derived (ColorEffects:Disabled)
        "ON_ACCENT": "#fcfcfc",     # Selection foreground
        "ACCENT": "#3daee9",        # DecorationFocus
        "ACCENT_HOVER": "#55b8ec",  # derived
        "ACCENT_LIGHT": "#1e5774",  # Button alternate (inactive selection)
        "ACCENT_PRESSED": "#2f96d3",  # derived
        "SUCCESS": "#27ae60",
        "SUCCESS_LIGHT": "#1c3827",  # derived
        "WARNING": "#f67400",
        "WARNING_TEXT": "#f89b47",  # derived
        "DANGER": "#da4453",
        "DANGER_SOLID": "#da4453",
        "DANGER_SOLID_HOVER": "#e36a76",  # derived
        "DANGER_SOLID_PRESSED": "#b03745",  # Selection negative
        "STATUS_OK": "#27ae60",
        "STATUS_WARN": "#f67400",
        "STATUS_ERR": "#da4453",
        "HOVER": "#34383d",         # derived
        "ROW_WARN": "#44331a",      # derived (warning tint)
        "TOAST_BG": "#17191c",      # derived (darker than BG)
        "SCROLLBAR_BG": "#202326",  # derived
        "SCROLLBAR_HANDLE": "#4a5058",  # derived
        "SCROLLBAR_HOVER": "#5b6269",  # derived
        "ICON_FG": "#fcfcfc",
        "ICON_FG_DIM": "#a1a9b1",
    }

    @property
    def id(self) -> str:
        return "breeze_dark"

    @property
    def name(self) -> str:
        return "Breeze Dark"


class OxygenTheme:
    """Oxygen — классическая тема KDE 4 (иконки 16px)."""

    _TOKENS: dict[str, str] = {
        "BG": "#d6d2d0",            # Window
        "PANEL": "#dfdcdb",         # Button
        "RAISED": "#ffffff",        # View
        "TRACK": "#cfcbc9",         # derived
        "ALT_ROW": "#f8f7f6",       # View alternate
        "BORDER": "#aaa7a5",        # derived
        "BORDER_LIGHT": "#c0bdbb",  # derived
        "BORDER_STRONG": "#8f8c8a",  # derived
        "TEXT": "#1f1c1b",          # View foreground
        "TEXT_SEC": "#898887",      # Window inactive
        "TEXT_DIM": "#9c9a99",      # derived
        "DISABLED": "#b0aeac",      # derived
        "ON_ACCENT": "#ffffff",     # Selection foreground
        "ACCENT": "#3aa7dd",        # DecorationFocus
        "ACCENT_HOVER": "#6ed6ff",  # DecorationHover
        "ACCENT_LIGHT": "#cbe9f9",  # derived
        "ACCENT_PRESSED": "#3e8acc",  # Selection alternate
        "SUCCESS": "#006e28",       # Positive
        "SUCCESS_LIGHT": "#ddf0e2",  # derived
        "WARNING": "#b08000",       # Neutral
        "WARNING_TEXT": "#8a6600",  # derived
        "DANGER": "#bf0303",        # Negative
        "DANGER_SOLID": "#bf0303",
        "DANGER_SOLID_HOVER": "#d63c3c",  # derived
        "DANGER_SOLID_PRESSED": "#9c0e0e",  # Selection negative
        "STATUS_OK": "#006e28",
        "STATUS_WARN": "#b08000",
        "STATUS_ERR": "#bf0303",
        "HOVER": "#dad9d8",         # Window alternate
        "ROW_WARN": "#f5ecd9",      # derived (warning tint)
        "TOAST_BG": "#181513",      # Tooltip background
        "SCROLLBAR_BG": "#d6d2d0",  # derived
        "SCROLLBAR_HANDLE": "#a3a09d",  # derived
        "SCROLLBAR_HOVER": "#8a8785",  # derived
        "ICON_FG": "#221f1e",       # Window foreground
        "ICON_FG_DIM": "#676563",   # derived
    }

    @property
    def id(self) -> str:
        return "oxygen"

    @property
    def name(self) -> str:
        return "Oxygen"

    def tokens(self) -> dict[str, str]:
        return dict(self._TOKENS)

    def extra_qss(self) -> str:
        return ""

    def icons(self) -> dict[str, str] | None:
        return None

    @property
    def icon_size(self) -> int:
        return 16


class GraphiteTheme:
    """Graphite — собственная нейтральная тёмная тема (иконки 16px)."""

    _TOKENS: dict[str, str] = {
        "BG": "#2b2d2f",
        "PANEL": "#333537",
        "RAISED": "#26282a",
        "TRACK": "#222425",
        "ALT_ROW": "#313335",
        "BORDER": "#3e4144",
        "BORDER_LIGHT": "#36393c",
        "BORDER_STRONG": "#4a4d50",
        "TEXT": "#e8eaec",
        "TEXT_SEC": "#a9adb1",
        "TEXT_DIM": "#7e8286",
        "DISABLED": "#6f7377",
        "ON_ACCENT": "#1d1f21",
        "ACCENT": "#8fa6bb",        # светлая сталь
        "ACCENT_HOVER": "#a1b5c7",
        "ACCENT_LIGHT": "#37424c",
        "ACCENT_PRESSED": "#7d94a9",
        "SUCCESS": "#7fbf8e",
        "SUCCESS_LIGHT": "#2c3a2f",
        "WARNING": "#d9a05b",
        "WARNING_TEXT": "#e0b077",
        "DANGER": "#d97379",
        "DANGER_SOLID": "#b8555c",
        "DANGER_SOLID_HOVER": "#c6676e",
        "DANGER_SOLID_PRESSED": "#9c454c",
        "STATUS_OK": "#7fbf8e",
        "STATUS_WARN": "#d9a05b",
        "STATUS_ERR": "#d97379",
        "HOVER": "#383b3e",
        "ROW_WARN": "#3d3527",
        "TOAST_BG": "#1e2022",
        "SCROLLBAR_BG": "#2b2d2f",
        "SCROLLBAR_HANDLE": "#45484c",
        "SCROLLBAR_HOVER": "#565a5e",
        "ICON_FG": "#c9cdd1",
        "ICON_FG_DIM": "#8f9397",
    }

    @property
    def id(self) -> str:
        return "graphite"

    @property
    def name(self) -> str:
        return "Graphite"

    def tokens(self) -> dict[str, str]:
        return dict(self._TOKENS)

    def extra_qss(self) -> str:
        return ""

    def icons(self) -> dict[str, str] | None:
        return None

    @property
    def icon_size(self) -> int:
        return 16


# ── System (следует схеме ОС) ───────────────────────────────────────

_scheme_resolver = None


def set_scheme_resolver(fn) -> None:
    """Хук движка: fn() -> "light" | "dark" (текущая схема ОС)."""
    global _scheme_resolver
    _scheme_resolver = fn


def _resolved_breeze():
    resolver = _scheme_resolver or (lambda: "light")
    return BreezeDarkTheme() if resolver() == "dark" else BreezeTheme()


class SystemTheme:
    """Системная тема: Breeze Light/Dark по colorScheme окружения."""

    @property
    def id(self) -> str:
        return "system"

    @property
    def name(self) -> str:
        return "System"

    def tokens(self) -> dict[str, str]:
        return _resolved_breeze().tokens()

    def extra_qss(self) -> str:
        return _resolved_breeze().extra_qss()

    def icons(self) -> dict[str, str] | None:
        return _resolved_breeze().icons()

    @property
    def icon_size(self) -> int:
        return _resolved_breeze().icon_size


# Явная проверка контракта при импорте модуля.
assert isinstance(LightTheme(), ThemePlugin)
for _plugin in (BreezeTheme(), BreezeDarkTheme(), OxygenTheme(),
                GraphiteTheme(), SystemTheme()):
    assert isinstance(_plugin, ThemePlugin)
