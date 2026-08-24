import sys
import threading
import time
from datetime import datetime, timezone


class TerminalDisplay:
    def __init__(self, mode: str = "in_place", only_breakouts: bool = True, price_decimals: int = 8, boll_decimals: int = 8, refresh_seconds: float = 0.0):
        if mode not in {"in_place", "append", "off"}:
            raise ValueError("display.mode must be in_place, append, or off")
        self.mode = mode
        self.only_breakouts = only_breakouts
        self.price_decimals = price_decimals
        self.boll_decimals = boll_decimals
        self.refresh_seconds = max(0.0, refresh_seconds)
        self._last_render = 0.0
        self._rows: dict[str, str] = {}
        self._lock = threading.Lock()

    def update(self, symbol: str, price: float, book, intervals: tuple[str, ...]) -> None:
        parts = []
        for interval in intervals:
            bars = book.bars(interval)
            if not bars or bars[-1].middle is None:
                continue
            bar = bars[-1]
            if self.only_breakouts and bar.lower <= price <= bar.upper:
                continue
            decimals = self.boll_decimals
            values = f"U={bar.upper:.{decimals}f},M={bar.middle:.{decimals}f},L={bar.lower:.{decimals}f}"
            if self.only_breakouts:
                side = "UP" if price > bar.upper else "DOWN"
                parts.append(f"{interval}={side}({values})")
            else:
                parts.append(f"{interval}=({values})")
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        row = f"{timestamp} {symbol:<12} price={price:.{self.price_decimals}f}"
        if parts:
            row += " " + ",".join(parts)
        elif self.only_breakouts:
            row += " -"
        with self._lock:
            self._rows[symbol] = row
            if self.mode == "append":
                print(row, flush=True)
            elif self.mode == "in_place":
                now = time.monotonic()
                if self.refresh_seconds == 0 or now - self._last_render >= self.refresh_seconds:
                    self._render()
                    self._last_render = now

    def _render(self) -> None:
        output = "\033[H\033[2J" + "\n".join(self._rows.values())
        sys.stdout.write(output + "\n")
        sys.stdout.flush()