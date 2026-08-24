from collections import deque
from datetime import datetime, timezone
from .config import INTERVAL_MS
from .indicators import bollinger
from .models import Kline

class SymbolBook:
    def __init__(self, symbol: str, intervals: tuple[str, ...], boll_period: int = 20, boll_stddev: float = 2.0, maxlen: int = 500):
        self.symbol = symbol.upper()
        self.intervals = intervals
        self._bars = {interval: deque(maxlen=maxlen) for interval in intervals}
        self.boll_period, self.boll_stddev = boll_period, boll_stddev

    def _new_bar(self, interval: str, open_time: int, price: float) -> Kline:
        return Kline(open_time, price, price, price, price)

    @staticmethod
    def _bucket(interval: str, timestamp_ms: int) -> int:
        if interval != "1M":
            step = INTERVAL_MS[interval]
            return timestamp_ms - timestamp_ms % step
        date = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        return int(datetime(date.year, date.month, 1, tzinfo=timezone.utc).timestamp() * 1000)

    @staticmethod
    def _next_bucket(interval: str, open_time: int) -> int:
        if interval != "1M":
            return open_time + INTERVAL_MS[interval]
        date = datetime.fromtimestamp(open_time / 1000, tz=timezone.utc)
        year, month = (date.year + 1, 1) if date.month == 12 else (date.year, date.month + 1)
        return int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp() * 1000)

    def _advance(self, interval: str, timestamp_ms: int) -> None:
        bars = self._bars[interval]
        if not bars:
            return
        target = self._bucket(interval, timestamp_ms)
        while bars[-1].open_time < target:
            bars[-1].closed = True
            bars.append(self._new_bar(interval, self._next_bucket(interval, bars[-1].open_time), bars[-1].close))

    def _update_latest_boll(self, interval: str) -> None:
        bars = self._bars[interval]
        if bars:
            closes = [item.close for item in list(bars)[-self.boll_period:]]
            bars[-1].upper, bars[-1].middle, bars[-1].lower = bollinger(closes, self.boll_period, self.boll_stddev)

    def update_trade(self, price: float, quantity: float, timestamp_ms: int, quote_quantity: float = 0.0) -> None:
        for interval in self.intervals:
            bucket = self._bucket(interval, timestamp_ms)
            bars = self._bars[interval]
            if not bars:
                bars.append(self._new_bar(interval, bucket, price))
            else:
                self._advance(interval, timestamp_ms)
                if bars[-1].open_time < bucket:
                    bars[-1].closed = True
                    bars.append(self._new_bar(interval, bucket, price))
            bar = bars[-1]
            if bar.trades == 0:
                bar.open = bar.high = bar.low = price
            bar.high = max(bar.high, price)
            bar.low = min(bar.low, price)
            bar.close = price
            bar.volume += quantity
            bar.quote_volume += quote_quantity
            bar.trades += 1
            closes = [item.close for item in list(bars)[-self.boll_period:]]
            bar.upper, bar.middle, bar.lower = bollinger(closes, self.boll_period, self.boll_stddev)

    def advance(self, timestamp_ms: int) -> None:
        for interval in self.intervals:
            self._advance(interval, timestamp_ms)
            self._update_latest_boll(interval)

    def replace(self, interval: str, klines: list[Kline]) -> None:
        self._bars[interval].clear()
        self._bars[interval].extend(klines)
        closes: list[float] = []
        for bar in self._bars[interval]:
            closes.append(bar.close)
            bar.upper, bar.middle, bar.lower = bollinger(closes, self.boll_period, self.boll_stddev)

    def merge_mismatch(self, interval: str, klines: list[Kline]) -> None:
        """Replace closed history while retaining the locally newer active bar."""
        current = self._bars[interval][-1] if self._bars[interval] else None
        active = current if current and not current.closed else None
        if active and klines and klines[-1].open_time == active.open_time and not klines[-1].closed:
            klines = klines[:-1]
        merged = list(klines)
        if active:
            merged.append(active)
        self.replace(interval, merged)

    def bars(self, interval: str) -> tuple[Kline, ...]:
        return tuple(self._bars[interval])

    def snapshot(self, interval: str, count: int = 1) -> list[dict]:
        return [bar.as_dict() for bar in list(self._bars[interval])[-count:]]
