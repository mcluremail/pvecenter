"""Built-in themes (ThemePlugin v1).

Themes are plugins like data sources. The light theme mirrors the
default Color palette (see ui/theme.LIGHT_TOKENS); dark variants land
with M1.2 (Breeze, Breeze Dark, Oxygen, Graphite).
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


# Явная проверка контракта при импорте модуля.
assert isinstance(LightTheme(), ThemePlugin)
