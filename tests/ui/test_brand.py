"""Бренд: знак рендерится, локап в тулбаре, перекраска под тему."""

from pve_center.ui import brand


class TestMark:
    def test_render_pixmap(self, qtbot):
        pm = brand.render_pixmap(64)
        assert not pm.isNull() and pm.width() == 64

    def test_logo_icon(self, qtbot):
        icon = brand.make_logo_icon(256)
        assert not icon.isNull()


class TestBrandWidget:
    def test_toolbar_lockup(self, main_window):
        """Локап заменяет текстовую надпись справа в тулбаре."""
        widget = main_window._brand
        assert isinstance(widget, brand.BrandWidget)
        assert "PVE" in widget._wordmark.text()
        assert "Center" in widget._wordmark.text()

    def test_restyle_follows_theme_text(self, main_window):
        from pve_center.ui.theme import LIGHT_TOKENS, Color

        assert f"color:{Color.TEXT}" in main_window._brand._wordmark.text()
        old = Color.TEXT
        try:
            Color.TEXT = "#010203"
            main_window._brand.restyle()
            assert "color:#010203" in main_window._brand._wordmark.text()
        finally:
            Color.TEXT = old
        assert LIGHT_TOKENS["TEXT"] == old
