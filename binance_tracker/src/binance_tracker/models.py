from dataclasses import dataclass

@dataclass(slots=True)
class Kline:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    quote_volume: float = 0.0
    trades: int = 0
    closed: bool = False
    middle: float | None = None
    upper: float | None = None
    lower: float | None = None

    def as_dict(self) -> dict:
        return {"open_time": self.open_time, "open": self.open, "high": self.high, "low": self.low, "close": self.close, "volume": self.volume, "quote_volume": self.quote_volume, "trades": self.trades, "closed": self.closed, "boll": {"upper": self.upper, "middle": self.middle, "lower": self.lower}}
