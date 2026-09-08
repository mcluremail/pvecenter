"""Локальный WebSocket-мост для noVNC-консоли.

Туннель: noVNC (ws://127.0.0.1:{порт}) → PVE (wss://host:8006/.../vncwebsocket).
Авторизация — Authorization-заголовок с API-токеном; TLS-проверка по trust_ssl.
Соединение держится websocket-ping'ами (ping_interval) — сервер PVE отвечает
pong (PVE::APIServer::AnyEvent, opcode 9). Фреймы relay'ятся без изменений.
"""

import asyncio
import logging
import ssl
import threading

try:
    import websockets
except ImportError:  # минимальная сборка без websockets — noVNC недоступен
    websockets = None
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class WsBridge(QObject):
    """Асинхронный мост в отдельном потоке со своим asyncio-циклом."""

    port_ready = Signal(int)  # локальный порт моста
    error = Signal(str)
    stopped = Signal()

    def __init__(self, ws_url, auth_header, verify_ssl, parent=None):
        super().__init__(parent)
        self._ws_url = ws_url
        self._auth_header = auth_header
        self._verify_ssl = verify_ssl
        self._loop = None
        self._server = None
        self._upstream = None
        self._error_sent = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        if websockets is None:
            self.error.emit(
                "The 'websockets' module is not installed — noVNC console is unavailable")
            return
        self._thread.start()

    def stop(self):
        if self._loop is None:
            return
        try:
            self._loop.call_soon_threadsafe(self._shutdown)
        except RuntimeError:
            pass

    def _emit_error(self, msg):
        logger.warning("noVNC bridge error: %s", msg)
        if self._error_sent:
            return
        self._error_sent = True
        try:
            self.error.emit(msg)
        except RuntimeError:
            pass

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
            self._loop.run_forever()
        except Exception as e:
            self._emit_error(str(e))
        finally:
            self._loop.close()
            try:
                self.stopped.emit()
            except RuntimeError:
                pass

    async def _serve(self):
        self._server = await websockets.serve(
            self._handle_client, "127.0.0.1", 0, max_size=None,
        )
        sock = list(self._server.sockets)[0]
        self.port_ready.emit(sock.getsockname()[1])

    def _ssl_context(self):
        ctx = ssl.create_default_context()
        if not self._verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    async def _handle_client(self, client):
        try:
            async with websockets.connect(
                self._ws_url,
                ssl=self._ssl_context(),
                additional_headers={"Authorization": self._auth_header},
                ping_interval=25,
                max_size=None,
            ) as upstream:
                self._upstream = upstream
                logger.info("noVNC tunnel established: %s",
                            self._ws_url.split("?")[0])
                await asyncio.gather(
                    self._pump(client, upstream),
                    self._pump(upstream, client),
                    return_exceptions=True,
                )
        except Exception as e:
            self._emit_error(str(e))

    @staticmethod
    async def _pump(src, dst):
        try:
            async for msg in src:
                await dst.send(msg)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    def _shutdown(self):
        async def _close():
            if self._server is not None:
                self._server.close()
                await self._server.wait_closed()
            if self._upstream is not None:
                await self._upstream.close()
        try:
            asyncio.ensure_future(_close())
            self._loop.call_later(0.5, self._loop.stop)
        except RuntimeError:
            pass
