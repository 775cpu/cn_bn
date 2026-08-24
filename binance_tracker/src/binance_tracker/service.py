import asyncio
import logging
import time
import threading
import aiohttp
from .aggregator import SymbolBook
from .client import BinanceClient
from .config import Settings
from .logging_setup import setup_symbol_calibration_logging
from .display import TerminalDisplay

app_log = logging.getLogger("app")
calibration_log = logging.getLogger("calibration")
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

    async def start(self) -> None:
        if self._client is not None:
            return
        self._client = BinanceClient(self.settings.rest_url, self.settings.ws_url, self.settings.http_proxy, self.settings.ws_proxy, self.settings.direct_ip, self.settings.direct_ws_ip, self.settings.verify_ssl)
        self._loop = asyncio.get_running_loop()
        await self._client.__aenter__()
        self._stop.clear()
        self._tasks = [asyncio.create_task(self._stream_loop()), asyncio.create_task(self._clock_loop())]
        await asyncio.gather(*(self._calibrate_symbol(symbol) for symbol in tuple(self._symbols)))
        self._tasks.append(asyncio.create_task(self._calibration_loop()))

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

    async def _calibrate_symbol(self, symbol: str) -> None:
        assert self._client is not None
        book = self.books[symbol]
        symbol_log = setup_symbol_calibration_logging(self.settings.log_dir, symbol, self.settings.log_max_bytes, self.settings.log_backup_count)
        symbol_log.info("calibration started intervals=%s", ",".join(self.settings.intervals))
        for interval in self.settings.intervals:
            try:
                incoming = await self._client.klines(symbol, interval, self.settings.history_limit)
                old = {bar.open_time: bar for bar in book.bars(interval)}
                for bar in incoming:
                    prior = old.get(bar.open_time)
                    if prior and prior.closed and bar.closed:
                        fields = ("open", "high", "low", "close", "volume", "quote_volume", "trades")
                        differences = {field: {"live": getattr(prior, field), "rest": getattr(bar, field)} for field in fields if getattr(prior, field) != getattr(bar, field)}
                        if differences:
                            message = "mismatch interval=%s open_time=%d closed=%s fields=%s live=%s rest=%s"
                            values = (interval, bar.open_time, bar.closed, differences, prior.as_dict(), bar.as_dict())
                            if bar.closed:
                                symbol_log.error(message, *values)
                            else:
                                symbol_log.warning("active_candle_drift " + message, *values)
                book.merge_calibration(interval, incoming)
                app_log.info("calibration symbol=%s interval=%s rows=%d", symbol, interval, len(incoming))
                symbol_log.info("calibration completed interval=%s rows=%d", interval, len(incoming))
            except Exception:
                symbol_log.exception("calibration failed interval=%s", interval)
                error_log.exception("calibration failed symbol=%s interval=%s", symbol, interval)

    async def _calibration_loop(self) -> None:
        while not self._stop.is_set():
            for symbol in tuple(self._symbols):
                await self._calibrate_symbol(symbol)
            try:
                await asyncio.wait_for(self._stop.wait(), self.settings.calibration_seconds)
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
                ws = await self._client.stream(symbols)
                app_log.info("WebSocket connected symbols=%s", sorted(symbols))
                while symbols == self._symbols and not self._stop.is_set():
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
