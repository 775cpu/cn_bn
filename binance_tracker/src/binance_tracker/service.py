import asyncio
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import logging
import math
import os
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


def normalize_symbol(symbol) -> str:
    """Normalize and validate one Binance trading symbol.

    Symbols are single tokens used verbatim with Binance REST/WS APIs. They are
    NOT guaranteed ASCII: spot base assets may contain non-ASCII characters
    (e.g. CJK meme coins such as 币安人生USDT). Only reject what is meaningless
    or would break the RPC expression embedding: empty after trim, whitespace,
    control characters, or quote characters.
    """
    normalized = str(symbol or "").upper().strip()
    if len(normalized) < 2 or any(
        ch.isspace() or ord(ch) < 0x20 or ch in ("'", '"') for ch in normalized
    ):
        raise ValueError(f"invalid symbol: {symbol!r}")
    return normalized


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
        self._ticker24h: list[dict] = []
        self._ticker24h_time_ms: int = 0
        # Compact in-memory index of exchangeInfo: symbol -> {"status", "baseAsset", "quoteAsset"}.
        # The full ~16MB exchangeInfo snapshot is only kept on disk.
        self._exchange_info_index: dict[str, dict] = {}
        self._exchange_info_time_ms: int = 0
        self._exchange_info_path = Path(self.settings.log_dir) / "exchange_info.json"
        self._exchange_info_extra_path = Path(self.settings.log_dir) / "exchange_info_extra.json"
        self.display = display or TerminalDisplay(self.settings.display_mode, self.settings.display_only_breakouts, self.settings.display_price_decimals, self.settings.display_boll_decimals, self.settings.display_refresh_seconds)

    @property
    def subscribed_symbols(self) -> frozenset[str]:
        return frozenset(self._symbols)

    def add_symbols(self, *symbols: str) -> None:
        normalized_symbols = [normalize_symbol(symbol) for symbol in symbols]
        with self._symbols_lock:
            for normalized in normalized_symbols:
                self._symbols.add(normalized)
                self.books.setdefault(normalized, SymbolBook(normalized, self.settings.intervals, self.settings.boll_period, self.settings.boll_stddev))
        self._notify_changed()

    def remove_symbols(self, *symbols: str) -> None:
        normalized = {symbol.upper().strip() for symbol in symbols}
        with self._symbols_lock:
            self._symbols.difference_update(normalized)
            for symbol in normalized:
                self.books.pop(symbol, None)
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
            if symbol:
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
            await self._load_exchange_info()
            await self._refresh_ticker24h()
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
        assert self._client is not None
        for attempt in range(1, retries + 1):
            try:
                # Go through the shared client entry point: it handles non-ASCII symbol encoding
                # (ensure_ascii=False), proxy/SSL/direct-IP options, and retries network errors.
                payload = await self._client.exchange_info(symbols=sorted(self.subscribed_symbols))
                loaded = 0
                for item in payload.get("symbols", []):
                    rule = next((rule for rule in item.get("filters", []) if rule.get("filterType") == "PRICE_FILTER"), None)
                    if rule:
                        tick_size = rule["tickSize"].rstrip("0")
                        self._price_precisions[item["symbol"]] = len(tick_size.split(".", 1)[1]) if "." in tick_size else 0
                        loaded += 1
                app_log.info("price precisions loaded symbols=%d attempt=%d", loaded, attempt)
                return loaded > 0
            except Exception as exc:
                # 4xx (e.g. HTTP 400 / -1121 invalid symbol) is a permanent client-side error; retrying is pointless.
                if isinstance(exc, aiohttp.ClientResponseError) and 400 <= exc.status < 500:
                    app_log.error("price precision load rejected by Binance status=%s; using defaults", exc.status)
                    return False
                if attempt == retries:
                    app_log.exception("failed to load symbol price precisions after %d attempts; using defaults", retries)
                else:
                    app_log.warning("price precision load failed attempt=%d/%d; retrying", attempt, retries, exc_info=True)
                    await asyncio.sleep(2 ** (attempt - 1))
        return False

    async def reload_price_precisions(self) -> bool:
        return await self._load_price_precisions()

    @staticmethod
    def _build_exchange_index(payload: dict) -> dict[str, dict]:
        """Extract a compact symbol -> {status, baseAsset, quoteAsset} index from an exchangeInfo payload."""
        index: dict[str, dict] = {}
        for item in payload.get("symbols", []):
            symbol = item.get("symbol")
            if not symbol:
                continue
            index[symbol] = {
                "status": item.get("status", ""),
                "baseAsset": item.get("baseAsset", ""),
                "quoteAsset": item.get("quoteAsset", ""),
            }
        return index

    def _write_json_atomic(self, path: Path, payload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp_path, path)

    def _load_exchange_info_from_disk(self) -> bool:
        """Rebuild the compact index from the on-disk full snapshot (+ sidecar of later-added symbols)."""
        try:
            if self._exchange_info_path.exists():
                payload = json.loads(self._exchange_info_path.read_text(encoding="utf-8"))
                self._exchange_info_index = self._build_exchange_index(payload)
                self._exchange_info_time_ms = int(self._exchange_info_path.stat().st_mtime * 1000)
            if self._exchange_info_extra_path.exists():
                extra = json.loads(self._exchange_info_extra_path.read_text(encoding="utf-8"))
                self._exchange_info_index.update(extra.get("symbols", {}))
            if self._exchange_info_index:
                app_log.info("exchangeInfo index restored from disk symbols=%d", len(self._exchange_info_index))
                return True
        except Exception:
            error_log.exception("failed to load exchangeInfo snapshot from disk")
        return False

    async def _load_exchange_info(self) -> bool:
        """Load the full exchangeInfo snapshot once: write the raw ~16MB payload to disk,
        keep only the compact symbol index in memory."""
        assert self._client is not None
        try:
            payload = await self._client.exchange_info()
            index = self._build_exchange_index(payload)
            if not index:
                raise RuntimeError("exchangeInfo payload contained no symbols")
            self._write_json_atomic(self._exchange_info_path, payload)
            self._exchange_info_index = index
            self._exchange_info_time_ms = int(time.time() * 1000)
            app_log.info("exchangeInfo full snapshot cached on disk symbols=%d path=%s", len(index), self._exchange_info_path)
            return True
        except Exception:
            error_log.exception("full exchangeInfo load failed; trying on-disk snapshot")
            return self._load_exchange_info_from_disk()

    async def _ensure_symbols_in_index(self, symbols) -> None:
        """Look up symbols missing from the exchangeInfo index via per-symbol exchangeInfo requests
        (newly listed pairs seen in the 24hr ticker), then persist them to the small sidecar file."""
        assert self._client is not None
        missing = sorted(symbol for symbol in symbols if symbol and symbol not in self._exchange_info_index)
        if not missing:
            return
        fetched: dict[str, dict] = {}
        for symbol in missing:
            try:
                payload = await self._client.exchange_info([symbol])
                fetched.update(self._build_exchange_index(payload))
            except Exception:
                error_log.warning("exchangeInfo lookup failed for new symbol=%s", symbol, exc_info=True)
        if not fetched:
            return
        self._exchange_info_index.update(fetched)
        try:
            extra = {"time": int(time.time() * 1000), "symbols": {}}
            if self._exchange_info_extra_path.exists():
                extra = json.loads(self._exchange_info_extra_path.read_text(encoding="utf-8"))
            extra.setdefault("symbols", {}).update(fetched)
            self._write_json_atomic(self._exchange_info_extra_path, extra)
        except Exception:
            error_log.exception("failed to persist exchange_info sidecar")
        app_log.info("exchangeInfo index extended new_symbols=%d", len(fetched))

    async def _refresh_ticker24h(self) -> bool:
        """Fetch /api/v3/ticker/24hr (all spot symbols) and cache a compact list for the symbol picker.

        Cached fields are bound 1:1 to the real API response:
        symbol / lastPrice / priceChangePercent, plus quoteAsset from the exchangeInfo index.
        Only TRADING pairs are kept (the ticker still returns BREAK/delisted pairs such as NFPTRY).
        """
        assert self._client is not None
        try:
            payload = await self._client.ticker_24hr()
        except Exception:
            error_log.exception("24hr ticker refresh failed; keeping previous cache of %d symbols", len(self._ticker24h))
            return False
        # Refresh the full exchangeInfo snapshot once a day so BREAK/status flips are picked up.
        if self._exchange_info_index and time.time() * 1000 - self._exchange_info_time_ms > 86_400_000:
            await self._load_exchange_info()
        await self._ensure_symbols_in_index({item.get("symbol") for item in payload})
        cached: list[dict] = []
        skipped_inactive = 0
        for item in payload:
            symbol = item.get("symbol")
            if not symbol:
                continue
            info = self._exchange_info_index.get(symbol)
            if info is not None and info.get("status") != "TRADING":
                skipped_inactive += 1
                continue
            try:
                last_price = float(item.get("lastPrice") or 0.0)
                change_percent = float(item.get("priceChangePercent") or 0.0)
                # quoteVolume = 24h turnover denominated in the quote asset (comparable within a quoteAsset group)
                quote_volume = float(item.get("quoteVolume") or 0.0)
            except (TypeError, ValueError):
                continue
            if last_price <= 0:
                continue
            cached.append({"symbol": symbol, "lastPrice": last_price, "priceChangePercent": change_percent,
                           "quoteVolume": quote_volume,
                           "quoteAsset": (info or {}).get("quoteAsset", "")})
        if not cached:
            app_log.warning("24hr ticker refresh returned no usable symbols; keeping previous cache")
            return False
        self._ticker24h = cached
        self._ticker24h_time_ms = int(time.time() * 1000)
        app_log.info("24hr ticker cached symbols=%d skipped_inactive=%d", len(cached), skipped_inactive)
        return True

    def get_ticker24h(self) -> dict:
        """Return the cached 24hr ticker list (safe to call from the RPC thread)."""
        return {"time": self._ticker24h_time_ms, "tickers": self._ticker24h}

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
        if symbol not in self.books:
            return
        symbol_log = setup_symbol_mismatch_logging(self.settings.log_dir, symbol, self.settings.log_max_bytes, self.settings.log_backup_count)
        for interval in self.settings.intervals:
            await self._calibrate_interval(symbol, interval, symbol_log)

    async def _calibrate_interval(self, symbol: str, interval: str, symbol_log=None) -> bool:
        """Fetch REST klines for one interval, log live/rest differences and merge them. Returns whether bars were loaded."""
        assert self._client is not None
        book = self.books.get(symbol)
        if book is None:
            return False
        if symbol_log is None:
            symbol_log = setup_symbol_mismatch_logging(self.settings.log_dir, symbol, self.settings.log_max_bytes, self.settings.log_backup_count)
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
            return bool(incoming)
        except Exception:
            symbol_log.exception("mismatch check failed interval=%s", interval)
            error_log.exception("mismatch check failed symbol=%s interval=%s", symbol, interval)
            return False

    async def calibrate_new_symbol(self, symbol: str) -> None:
        """Calibrate a symbol added at runtime: validate it, REST-calibrate every interval in parallel and load its price precision."""
        if self._client is None:
            raise RuntimeError("行情服务尚未准备完成")
        symbol = symbol.upper().strip()
        if symbol not in self.books:
            raise KeyError(symbol)
        symbol_log = setup_symbol_mismatch_logging(self.settings.log_dir, symbol, self.settings.log_max_bytes, self.settings.log_backup_count)
        try:
            probe = await self._client.klines(symbol, self.settings.intervals[0], 1)
        except Exception as exc:
            raise ValueError(f"无效的 symbol: {symbol}") from exc
        if not probe:
            raise ValueError(f"无效的 symbol: {symbol}")
        app_log.info("new symbol calibration started symbol=%s intervals=%d", symbol, len(self.settings.intervals))
        results = await asyncio.gather(*(self._calibrate_interval(symbol, interval, symbol_log) for interval in self.settings.intervals))
        book = self.books.get(symbol)
        if book is None or not book.bars(self.settings.intervals[0]):
            raise ValueError(f"无法获取 {symbol} 的 K 线数据，请稍后重试")
        await self._load_price_precisions()
        app_log.info("new symbol calibration completed symbol=%s intervals_ok=%d/%d", symbol, sum(1 for ok in results if ok), len(results))

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
            await self._refresh_ticker24h()
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
