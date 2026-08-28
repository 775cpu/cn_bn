import asyncio
import json
from urllib.parse import parse_qs, urlsplit
import logging
import math
import time
import threading
import aiohttp
from .aggregator import SymbolBook
from .client import BinanceClient
from .config import Settings
from .logging_setup import setup_symbol_mismatch_logging
from .display import TerminalDisplay

app_log = logging.getLogger("app")
mismatch_log = logging.getLogger("mismatch")
error_log = logging.getLogger("error")

class BinanceTracker:
    def __init__(self, settings: Settings | None = None, display: TerminalDisplay | None = None):
        self.settings = settings or Settings()
        self.books: dict[str, SymbolBook] = {}
        self._symbols: set[str] = set()
        self._changed = asyncio.Event()
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._client: BinanceClient | None = None
        self._symbols_lock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._chart_clients: set = set()
        self._chart_clients_lock = threading.RLock()
        self._price_precisions: dict[str, int] = {}
        self.display = display or TerminalDisplay(self.settings.display_mode, self.settings.display_only_breakouts, self.settings.display_price_decimals, self.settings.display_boll_decimals, self.settings.display_refresh_seconds)

    @property
    def subscribed_symbols(self) -> frozenset[str]:
        return frozenset(self._symbols)

    def add_symbols(self, *symbols: str) -> None:
        normalized_symbols = []
        for symbol in symbols:
            normalized = symbol.upper().strip()
            if not normalized or not normalized.isalnum():
                raise ValueError(f"invalid symbol: {symbol!r}")
            normalized_symbols.append(normalized)
        with self._symbols_lock:
            for normalized in normalized_symbols:
                self._symbols.add(normalized)
                self.books.setdefault(normalized, SymbolBook(normalized, self.settings.intervals, self.settings.boll_period, self.settings.boll_stddev))
        self._notify_changed()

    def remove_symbols(self, *symbols: str) -> None:
        with self._symbols_lock:
            self._symbols.difference_update(symbol.upper().strip() for symbol in symbols)
        self._notify_changed()

    def _notify_changed(self) -> None:
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._changed.set)

    def get_snapshot(self, symbol: str, interval: str = "1m", count: int = 1) -> list[dict]:
        symbol, interval = symbol.upper(), interval
        if symbol not in self.books:
            raise KeyError(symbol)
        if interval not in self.settings.intervals:
            raise KeyError(interval)
        return self.books[symbol].snapshot(interval, count)

    def _chart_send(self, connection, message: dict) -> None:
        try:
            connection.send(json.dumps(message, ensure_ascii=False))
        except (ConnectionError, OSError):
            with self._chart_clients_lock:
                self._chart_clients.discard(connection)

    def _chart_snapshot(self, symbol: str, interval: str, count: int = 200) -> dict:
        return {"type": "snapshot", "symbol": symbol, "interval": interval,
                "bars": self.get_snapshot(symbol, interval, count),
                "price_precision": self._price_precisions.get(symbol, self.settings.display_price_decimals),
                "server_time": int(time.time() * 1000)}

    def chart_websocket(self, connection, request) -> None:
        symbol = next(iter(self.subscribed_symbols), "")
        interval = self.settings.intervals[0]
        query = parse_qs(urlsplit(request.path).query)
        symbol = query.get("symbol", [symbol])[0].upper()
        interval = query.get("interval", [interval])[0]
        if symbol not in self.books:
            symbol = next(iter(self.subscribed_symbols), "")
        if interval not in self.settings.intervals:
            interval = self.settings.intervals[0]
        connection.chart_subscription = (symbol, interval)
        with self._chart_clients_lock:
            self._chart_clients.add(connection)
        try:
            self._chart_send(connection, self._chart_snapshot(symbol, interval))
            while True:
                raw = connection.receive()
                if raw is None:
                    break
                message = json.loads(raw)
                if message.get("type") == "subscribe":
                    symbol = str(message.get("symbol", symbol)).upper()
                    interval = str(message.get("interval", interval))
                    if symbol not in self.books or interval not in self.settings.intervals:
                        self._chart_send(connection, {"type": "error", "message": "无效的 symbol 或周期"})
                        continue
                    connection.chart_subscription = (symbol, interval)
                    self._chart_send(connection, self._chart_snapshot(symbol, interval))
                elif message.get("type") == "ping":
                    self._chart_send(connection, {"type": "pong", "sent_at": message.get("sent_at"), "server_time": int(time.time() * 1000)})
        except (ConnectionError, OSError, ValueError):
            pass
        finally:
            with self._chart_clients_lock:
                self._chart_clients.discard(connection)

    def _notify_chart(self, symbol: str) -> None:
        with self._chart_clients_lock:
            clients = tuple(self._chart_clients)
        for connection in clients:
            state = getattr(connection, "chart_subscription", None)
            if state and state[0] == symbol:
                bars = self.books[symbol].snapshot(state[1], 1)
                if bars:
                    self._chart_send(connection, {
                        "type": "update", "symbol": symbol, "interval": state[1],
                        "bar": bars[0], "server_time": int(time.time() * 1000),
                    })

    async def start(self) -> None:
        if self._client is not None:
            return
        self._client = BinanceClient(self.settings.rest_url, self.settings.ws_url, self.settings.http_proxy, self.settings.ws_proxy, self.settings.direct_ip, self.settings.direct_ws_ip, self.settings.verify_ssl, self.settings.direct_ips, self.settings.ip_ping_timeout, self.settings.rest_ips, self.settings.ws_ips, self.settings.ip_switch_min_ms, self.settings.ip_switch_min_ratio)
        self._loop = asyncio.get_running_loop()
        try:
            await self._client.__aenter__()
            self._stop.clear()
            print(f"[启动] symbols={','.join(sorted(self._symbols))}", flush=True)
            print(f"[启动] network_mode={self.settings.network_mode} ssl_verify={self.settings.verify_ssl}", flush=True)
            if self._client.rest_ips or self._client.ws_ips:
                print(f"[网络] 正在测速 REST={len(self._client.rest_ips)} 个 IP, WS={len(self._client.ws_ips)} 个 IP ...", flush=True)
                await self._client.select_best_ip()
                print(f"[网络] 当前 REST={self._client.current_rest_ip or 'domain'} WS={self._client.current_ws_ip or 'domain'}", flush=True)
            else:
                print("[网络] 使用域名直连", flush=True)
            await self._load_price_precisions()
            self._tasks = [asyncio.create_task(self._stream_loop()), asyncio.create_task(self._clock_loop()), asyncio.create_task(self._ip_selection_loop())]
            await asyncio.gather(*(self._check_mismatch_symbol(symbol) for symbol in tuple(self._symbols)))
            self._tasks.append(asyncio.create_task(self._mismatch_loop()))
            print("[启动] 初始校准完成，正在接收实时数据", flush=True)
        except Exception:
            await self._client.__aexit__(None, None, None)
            self._client = None
            raise

    async def _load_price_precisions(self, retries: int = 3) -> bool:
        """Load symbol-specific display precision; return whether any value was loaded."""
        assert self._client is not None and self._client.session is not None
        params = {"symbols": json.dumps(sorted(self.subscribed_symbols), separators=(",", ":"))}
        for attempt in range(1, retries + 1):
            try:
                async with self._client.session.get(
                    f"{self._client.rest_url}/api/v3/exchangeInfo",
                    params=params, headers=self._client.rest_headers,
                    ssl=False if self._client.rest_headers else self.settings.verify_ssl,
                ) as response:
                    response.raise_for_status()
                    payload = await response.json()
                loaded = 0
                for item in payload.get("symbols", []):
                    rule = next((rule for rule in item.get("filters", []) if rule.get("filterType") == "PRICE_FILTER"), None)
                    if rule:
                        tick_size = rule["tickSize"].rstrip("0")
                        self._price_precisions[item["symbol"]] = len(tick_size.split(".", 1)[1]) if "." in tick_size else 0
                        loaded += 1
                app_log.info("price precisions loaded symbols=%d attempt=%d", loaded, attempt)
                return loaded > 0
            except Exception:
                if attempt == retries:
                    app_log.exception("failed to load symbol price precisions after %d attempts; using defaults", retries)
                else:
                    app_log.warning("price precision load failed attempt=%d/%d; retrying", attempt, retries, exc_info=True)
                    await asyncio.sleep(2 ** (attempt - 1))
        return False

    async def reload_price_precisions(self) -> bool:
        return await self._load_price_precisions()

    async def stop(self) -> None:
        self._stop.set()
        self._changed.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def _check_mismatch_symbol(self, symbol: str) -> None:
        assert self._client is not None
        book = self.books[symbol]
        symbol_log = setup_symbol_mismatch_logging(self.settings.log_dir, symbol, self.settings.log_max_bytes, self.settings.log_backup_count)
        for interval in self.settings.intervals:
            try:
                incoming = await self._client.klines(symbol, interval, self.settings.history_limit)
                old = {bar.open_time: bar for bar in book.bars(interval)}
                for bar in incoming:
                    prior = old.get(bar.open_time)
                    if prior and prior.closed and bar.closed:
                        fields = ("open", "high", "low", "close", "volume", "quote_volume")
                        differences = {
                            field: {"live": getattr(prior, field), "rest": getattr(bar, field)}
                            for field in fields
                            if not math.isclose(getattr(prior, field), getattr(bar, field), rel_tol=1e-12, abs_tol=1e-8)
                        }
                        if differences:
                            message = "mismatch interval=%s open_time=%d closed=%s fields=%s live=%s rest=%s"
                            values = (interval, bar.open_time, bar.closed, differences, prior.as_dict(), bar.as_dict())
                            symbol_log.error(message, *values)
                book.merge_mismatch(interval, incoming)
            except Exception:
                symbol_log.exception("mismatch check failed interval=%s", interval)
                error_log.exception("mismatch check failed symbol=%s interval=%s", symbol, interval)

    async def _mismatch_loop(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            app_log.info(
                "periodic calibration started symbols=%s intervals=%s history_limit=%d interval_seconds=%d",
                sorted(self._symbols),
                ",".join(self.settings.intervals),
                self.settings.history_limit,
                self.settings.mismatch_check_seconds,
            )
            await asyncio.gather(*(self._check_mismatch_symbol(symbol) for symbol in tuple(self._symbols)))
            app_log.info("periodic calibration completed elapsed_seconds=%.1f", time.monotonic() - started)
            try:
                await asyncio.wait_for(self._stop.wait(), self.settings.mismatch_check_seconds)
            except asyncio.TimeoutError:
                pass

    async def _clock_loop(self) -> None:
        while not self._stop.is_set():
            now_ms = int(time.time() * 1000)
            for symbol in tuple(self._symbols):
                self.books[symbol].advance(now_ms)
            try:
                await asyncio.wait_for(self._stop.wait(), 1)
            except asyncio.TimeoutError:
                pass

    async def _ip_selection_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), self.settings.ip_select_seconds)
            except asyncio.TimeoutError:
                if self._client and (self._client.rest_ips or self._client.ws_ips):
                    try:
                        changed = await self._client.select_best_ip()
                        if changed:
                            self._changed.set()
                            app_log.info("Binance IP changed REST=%s WS=%s; reconnecting WebSocket", self._client.current_rest_ip, self._client.current_ws_ip)
                    except Exception:
                        error_log.exception("periodic Binance IP selection failed")

    async def _stream_loop(self) -> None:
        while not self._stop.is_set():
            symbols = set(self._symbols)
            if not symbols:
                self._changed.clear()
                await self._changed.wait()
                continue
            ws = None
            try:
                assert self._client is not None
                self._changed.clear()
                ws = await self._client.stream(symbols)
                app_log.info("WebSocket connected symbols=%s", sorted(symbols))
                while symbols == self._symbols and not self._stop.is_set():
                    if self._changed.is_set():
                        break
                    try:
                        message = await ws.receive(timeout=5)
                    except asyncio.TimeoutError:
                        continue
                    if message.type == aiohttp.WSMsgType.TEXT:
                        raw = message.json()
                        payload = raw.get("data", raw)
                        if payload.get("e") != "aggTrade":
                            continue
                        symbol = payload["s"].upper()
                        if symbol in self.books:
                            price = float(payload["p"])
                            self.books[symbol].update_trade(price, float(payload["q"]), int(payload["T"]), price * float(payload["q"]))
                            self._notify_chart(symbol)
                            self.display.update(symbol, price, self.books[symbol], self.settings.intervals)
                    elif message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        raise ConnectionError(f"WebSocket closed: {message.type}")
            except asyncio.CancelledError:
                raise
            except Exception:
                error_log.exception("WebSocket loop failed; reconnecting")
                await asyncio.sleep(3)
            finally:
                if ws is not None:
                    await ws.close()
