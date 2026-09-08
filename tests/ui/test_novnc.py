"""Tests for the noVNC console plumbing (worker URL/ticket, page html, provider call)."""

from unittest.mock import MagicMock

from pve_center.backend import NoVncWorker
from pve_center.ui.console.page import build_console_html


class TestBuildWsUrl:
    def test_qemu_path_and_port(self):
        url = NoVncWorker.build_ws_url("pve.host", "n1", 100, "qemu", 5900, "TICKET")
        assert url == ("wss://pve.host:8006/api2/json/nodes/n1/qemu/100/"
                       "vncwebsocket?port=5900&vncticket=TICKET")

    def test_lxc_path(self):
        url = NoVncWorker.build_ws_url("pve.host", "n1", 200, "lxc", 5901, "T")
        assert "/lxc/200/vncwebsocket" in url

    def test_ticket_is_quoted(self):
        url = NoVncWorker.build_ws_url("pve.host", "n1", 100, "qemu", 5900,
                                       "a b&c=d/e?плюс")
        assert "vncticket=a%20b%26c%3Dd%2Fe%3F%D0%BF%D0%BB%D1%8E%D1%81" in url

    def test_host_is_quoted(self):
        url = NoVncWorker.build_ws_url("p ve.host", "n 1", 100, "qemu", 5900, "T")
        assert url.startswith("wss://p%20ve.host:8006/api2/json/nodes/n%201/")


class TestExtractTicket:
    def test_password_preferred(self):
        assert NoVncWorker.extract_ticket(
            {"password": "p", "ticket": "t"}) == "p"

    def test_ticket_fallback(self):
        assert NoVncWorker.extract_ticket({"ticket": "t"}) == "t"

    def test_empty(self):
        assert NoVncWorker.extract_ticket({}) == ""


class TestBuildConsoleHtml:
    def test_contains_rfb_with_credentials(self):
        html = build_console_html(5910, "TICKET</script>")
        assert '"ws://127.0.0.1:" + cfg.port + "/"' in html
        assert "new RFB(" in html
        # ticket вставлен как JSON-строка с разрывом "</"
        assert 'TICKET<\\/script>' in html

    def test_ticket_not_raw_in_html(self):
        html = build_console_html(5910, "<script>alert(1)</script>")
        # закрывающий тег не должен остаться живым html
        assert "alert(1)</script>" not in html
        assert '<script>alert(1)<\\/script>' in html

    def test_no_html_entities_in_script(self):
        # регресс: html.escape превращал " в &quot; → SyntaxError в <script>
        html = build_console_html(5910, 'a"b&c<d')
        assert "&quot;" not in html
        assert "&amp;" not in html
        assert '"a\\"b&c<d"' in html

    def test_exposes_rfb_to_page(self):
        html = build_console_html(5910, "T")
        assert "window.rfb = rfb;" in html


class TestStickyKeyJs:
    def test_press_and_release(self):
        from pve_center.ui.console.page import sticky_key_js
        assert sticky_key_js(0xFFE3, "ControlLeft", True) == (
            'if (window.rfb) rfb.sendKey(65507, "ControlLeft", true);')
        assert sticky_key_js(0xFFE1, "ShiftLeft", False) == (
            'if (window.rfb) rfb.sendKey(65505, "ShiftLeft", false);')

    def test_guard_when_rfb_missing(self):
        from pve_center.ui.console.page import sticky_key_js
        assert sticky_key_js(0xFFEB, "MetaLeft", True).startswith(
            "if (window.rfb) ")


class TestProviderVncWebsocket:
    @staticmethod
    def _api():
        from pve_center.provider import VmAPI
        mock_session = MagicMock()
        mock_session.call = MagicMock(
            side_effect=lambda fn, *a, **kw: fn(*a, **kw))
        return VmAPI(mock_session), mock_session

    def test_get_vnc_websocket_qemu(self):
        api, s = self._api()
        chain = s.proxmox.nodes
        qemu_chain = chain.return_value.qemu
        qemu_chain.return_value.vncwebsocket.get = MagicMock(
            return_value={"port": "5900"})
        result = api.get_vnc_websocket("n1", 100, "qemu", 5900, "T")
        assert result == {"port": "5900"}
        qemu_chain.return_value.vncwebsocket.get.assert_called_once_with(
            port=5900, vncticket="T")

    def test_get_vnc_websocket_lxc(self):
        api, s = self._api()
        chain = s.proxmox.nodes
        lxc_chain = chain.return_value.lxc
        lxc_chain.return_value.vncwebsocket.get = MagicMock(
            return_value={"port": "5901"})
        result = api.get_vnc_websocket("n1", 200, "lxc", 5901, "T")
        assert result == {"port": "5901"}
        lxc_chain.return_value.vncwebsocket.get.assert_called_once_with(
            port=5901, vncticket="T")

    def test_get_vnc_proxy_without_proxy_param(self):
        """noVNC-путь не шлёт proxy (опционален, некоторыми версиями PVE
        отклоняется), но шлёт websocket=1 — без него PVE не поднимает
        websocket-подготовленный листенер."""
        from pve_center.provider import VmAPI
        mock_session = MagicMock()
        mock_session.call = MagicMock(
            side_effect=lambda fn, *a, **kw: fn(*a, **kw))
        chain = mock_session.proxmox.nodes
        post = chain.return_value.qemu.return_value.vncproxy.post
        post = MagicMock(return_value={"port": 5900})
        chain.return_value.qemu.return_value.vncproxy.post = post
        api = VmAPI(mock_session)
        api.get_vnc_proxy("n1", 100, "qemu")
        post.assert_called_once_with(websocket=1)


class TestNoVncWindowToolbar:
    @staticmethod
    def _host_cfg():
        return {"name": "h1", "host": "pve.test", "user": "u@pam",
                "token_name": "tok", "token_value": "sec", "trust_ssl": False}

    def test_sticky_modifiers_toggle(self, qtbot, monkeypatch):
        from PySide6.QtWidgets import QToolBar, QWidget

        from pve_center.ui.console import window as win_mod

        class _FakeView(QWidget):
            def __init__(self):
                super().__init__()
                self._page = MagicMock()

            def page(self):
                return self._page

        monkeypatch.setattr(win_mod, "QWebEngineView", _FakeView)
        monkeypatch.setattr(win_mod, "WsBridge", MagicMock())

        win = win_mod.NoVncWindow(
            self._host_cfg(), "n1", 100, "qemu", "wss://pve.test", "T")
        qtbot.addWidget(win)

        toolbar = win.findChild(QToolBar)
        assert toolbar is not None
        labels = [a.text() for a in toolbar.actions()]
        assert labels == ["Shift", "Ctrl", "Alt", "Win"]

        js = win.view.page().runJavaScript
        # до загрузки страницы кнопки заблокированы
        assert not any(a.isEnabled() for a in toolbar.actions())
        win._on_page_loaded(True)
        assert all(a.isEnabled() for a in toolbar.actions())

        ctrl = toolbar.actions()[1]
        ctrl.setChecked(True)
        js.assert_called_with(
            'if (window.rfb) rfb.sendKey(65507, "ControlLeft", true);')
        ctrl.setChecked(False)
        js.assert_called_with(
            'if (window.rfb) rfb.sendKey(65507, "ControlLeft", false);')

        toolbar.actions()[3].setChecked(True)
        js.assert_called_with(
            'if (window.rfb) rfb.sendKey(65515, "MetaLeft", true);')
