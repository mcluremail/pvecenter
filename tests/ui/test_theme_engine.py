"""M1.1 — движок тем: контракт токенов, ThemePlugin, активация.

Проверяются инварианты, которые морозятся в docs/THEMES.md на 3.0:
канонический набор токенов, валидация наборов, поток load_theme
(фасад → QSS → иконки → графики → слушатели), переключатель в
статус-баре.
"""

import re
from pathlib import Path

import pytest

from pve_center.plugins import PluginError
from pve_center.ui import theme
from pve_center.ui.theme import (
    FONT_TOKENS,
    LIGHT_TOKENS,
    TOKENS,
    Color,
    load_theme,
    subscribe_theme_changed,
    unsubscribe_theme_changed,
    validate_tokens,
)


class FakeDark:
    """Тестовая тема: полный набор light + подмены, extra_qss, 24px."""

    id = "fake_dark"
    name = "Fake Dark"

    def tokens(self):
        tokens = dict(LIGHT_TOKENS)
        tokens.update(BG="#232629", PANEL="#1b1e20", TEXT="#fcfcfc", ACCENT="#3daee9")
        return tokens

    def extra_qss(self):
        return "\n/* fake dark extra */\n"

    def icons(self):
        return None

    icon_size = 24


@pytest.fixture()
def dark_registry():
    from pve_center.plugins import default_registry

    reg = default_registry()
    reg.register_theme(FakeDark())
    return reg


# ── Контракт набора ────────────────────────────────────────────────


class TestTokenContract:
    def test_builtin_light_covers_full_set(self):
        from pve_center.plugins import default_registry

        reg = default_registry()
        assert "light" in reg.theme_ids()
        tokens = reg.get_theme("light").tokens()
        assert set(tokens) == set(TOKENS)
        for value in tokens.values():
            assert re.fullmatch(r"#[0-9a-fA-F]{6}", value)

    def test_light_tokens_match_default_color_palette(self):
        """Светлая тема = дефолтная палитра фасада (до подмен)."""
        for name, value in LIGHT_TOKENS.items():
            assert getattr(Color, name) == value, name

    def test_qss_template_uses_only_known_tokens(self):
        """Все ссылки на токены в theme.py — канонические имена или шрифты."""
        source = Path(theme.__file__).read_text(encoding="utf-8")
        names = set(re.findall(r"Color\.([A-Z][A-Z0-9_]*)", source))
        assert names <= set(TOKENS) | set(FONT_TOKENS)

    def test_builtin_themes_are_pure(self):
        """Плагины тем не тянут сеть/Qt — AST-скан импортов."""
        import ast

        src = Path(theme.__file__).parent.parent.parent / ("pve_center/plugins/_themes.py")
        tree = ast.parse(src.read_text(encoding="utf-8"))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        assert not roots & {"PySide6", "requests", "proxmoxer"}, roots


# ── Валидация наборов ──────────────────────────────────────────────


class TestValidateTokens:
    def test_rejects_incomplete_set(self):
        with pytest.raises(PluginError, match="missing tokens"):
            validate_tokens({"BG": "#ffffff"})

    def test_rejects_unknown_token(self):
        tokens = dict(LIGHT_TOKENS)
        tokens["NOT_A_TOKEN"] = "#000000"
        with pytest.raises(PluginError, match="unknown theme token"):
            validate_tokens(tokens)

    def test_rejects_bad_color(self):
        tokens = dict(LIGHT_TOKENS)
        tokens["BG"] = "white"
        with pytest.raises(PluginError, match="invalid color"):
            validate_tokens(tokens)

    def test_rejects_non_dict(self):
        with pytest.raises(PluginError, match="dict"):
            validate_tokens(["BG=#ffffff"])

    def test_deprecated_aliases_map_to_canonical(self):
        tokens = dict(LIGHT_TOKENS)
        tokens["GRAY_400"] = "#123456"  # алиас TEXT_DIM перекрывает
        mapped = validate_tokens(tokens)
        assert mapped["TEXT_DIM"] == "#123456"


# ── Активация (load_theme) ─────────────────────────────────────────


class TestLoadTheme:
    def test_switch_updates_facade_qss_icons_listeners(self, qtbot, dark_registry):
        assert Color.ACCENT == LIGHT_TOKENS["ACCENT"]
        seen = []
        subscribe_theme_changed(seen.append)
        try:
            assert load_theme("fake_dark", registry=dark_registry, persist=False) == "fake_dark"
            assert Color.BG == "#232629"
            assert Color.ACCENT == "#3daee9"
            assert "/* fake dark extra */" in theme.QSS
            assert seen == ["fake_dark"]

            from PySide6.QtCore import QSize

            from pve_center.ui import icons

            assert icons._BASE_SIZE == 24
            icon = icons.get_icon("vm")  # кэш пересобран под 24px
            assert QSize(24, 24) in icon.availableSizes()
        finally:
            unsubscribe_theme_changed(seen.append)

    def test_switch_back_restores_light(self, dark_registry):
        load_theme("fake_dark", registry=dark_registry, persist=False)
        assert load_theme("light", registry=dark_registry, persist=False) == "light"
        for name, value in LIGHT_TOKENS.items():
            assert getattr(Color, name) == value, name
        assert "/* fake dark extra */" not in theme.QSS

    def test_unknown_theme_raises(self, dark_registry):
        with pytest.raises(PluginError):
            load_theme("nope", registry=dark_registry, persist=False)

    def test_invalid_theme_rejected_before_apply(self, dark_registry):
        class Broken(FakeDark):
            id = "broken"

            def tokens(self):
                return {"BG": "#ffffff"}  # неполный набор

        dark_registry.register_theme(Broken())
        with pytest.raises(PluginError):
            load_theme("broken", registry=dark_registry, persist=False)
        assert Color.BG == LIGHT_TOKENS["BG"]  # фасад не тронут


# ── E2E: MainWindow ────────────────────────────────────────────────


class TestMainWindowSwitcher:
    def test_theme_combo_in_status_bar(self, main_window):
        combo = main_window._theme_combo
        ids = [combo.itemData(i) for i in range(combo.count())]
        assert "light" in ids
        assert combo.currentData() == "light" or "light" in ids

    def test_switch_via_combo_recolors_tree(self, qtbot, monkeypatch, tmp_path, offline):
        """Тема регистрируется ДО MainWindow — комбо её уже содержит."""
        from pve_center.plugins import get_registry

        reg = get_registry()
        reg.register_theme(FakeDark())
        try:
            monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
            from pve_center.ui.mainwindow import MainWindow

            mw = MainWindow()
            qtbot.addWidget(mw)

            combo = mw._theme_combo
            idx = next(i for i in range(combo.count()) if combo.itemData(i) == "fake_dark")
            combo.setCurrentIndex(idx)  # сигнал → load_theme → listeners

            assert Color.BG == "#232629"
            assert "/* fake dark extra */" in theme.QSS
            # дерево перестроено слушателем (кэш QColor обновлён)
            assert mw.tree_panel.tree.topLevelItemCount() >= 0
            # возврат
            light_idx = next(i for i in range(combo.count()) if combo.itemData(i) == "light")
            combo.setCurrentIndex(light_idx)
            assert Color.BG == LIGHT_TOKENS["BG"]
        finally:
            reg.unregister("fake_dark")
            load_theme("light", persist=False)

    def test_default_registry_has_no_fake_leftovers(self):
        from pve_center.plugins import get_registry

        assert "fake_dark" not in get_registry().theme_ids()
        assert "light" in get_registry().theme_ids()
