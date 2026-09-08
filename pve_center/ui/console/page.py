"""HTML-страница noVNC для QWebEngineView.

Страница подключается к локальному WsBridge (ws://127.0.0.1:{port}) и
запускает RFB из вендоренного noVNC. Авторизация VNC — одноразовый ticket
(vncproxy), передаётся как RFB-пароль (PVE делает set_password на qemu).
"""

import json

_PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>noVNC</title>
<style>
html, body { margin: 0; padding: 0; height: 100%; background: #141414; overflow: hidden; }
#screen { width: 100%; height: 100%; }
#status {
    position: absolute; top: 8px; left: 12px; z-index: 10;
    font: 12px monospace; color: #c8c8c8; background: rgba(0,0,0,0.55);
    padding: 3px 8px; border-radius: 4px; pointer-events: none;
}
</style>
</head>
<body>
<div id="screen"></div>
<div id="status">connecting...</div>
<script type="module">
import RFB from "./core/rfb.js";

const cfg = {port: {port}, ticket: {ticket}};
const screen = document.getElementById("screen");
const status = document.getElementById("status");

const rfb = new RFB(screen, "ws://127.0.0.1:" + cfg.port + "/",
    {shared: false, credentials: {password: cfg.ticket}});
rfb.scaleViewport = true;
rfb.resizeSession = false;
rfb.background = "#141414";

rfb.addEventListener("connect", () => { status.textContent = "connected"; });
rfb.addEventListener("disconnect", (e) => {
    status.textContent = e.detail.clean ? "disconnected" : "connection failed";
});
rfb.addEventListener("credentialsrequired", () => {
    rfb.sendCredentials({password: cfg.ticket});
});

window.rfb = rfb;
</script>
</body>
</html>
"""


def build_console_html(port: int, ticket: str) -> str:
    r"""Собирает страницу, безопасно подставляя порт и ticket.

    Внутри <script> HTML-entities не декодируются, поэтому ticket подставляется
    как JSON-строка; от выхода из script-контекста защищает разрыв "</"
    (стандартный приём: `</` → `<\/`).
    """
    ticket_js = json.dumps(str(ticket)).replace("</", "<\\/")
    return _PAGE.replace("{port}", str(int(port))).replace("{ticket}", ticket_js)


def sticky_key_js(keysym: int, code: str, down: bool) -> str:
    r"""JS для зажатия/отпускания клавиши-модификатора в RFB-сессии страницы.

    down=True — «залипающая» клавиша нажата (key-down) и удерживается в
    госте до обратного события; down=False — отпускается. Остальные клавиши
    сочетания пользователь вводит прямо в консоли.
    """
    payload = json.dumps([int(keysym), str(code), bool(down)])
    return f"if (window.rfb) rfb.sendKey({payload[1:-1]});"
