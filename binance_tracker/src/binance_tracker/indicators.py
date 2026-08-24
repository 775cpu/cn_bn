from collections import deque
from math import sqrt


def bollinger(closes: list[float], boll_period: int, boll_stddev: float) -> tuple[float | None, float | None, float | None]:
    if len(closes) < boll_period:
        return None, None, None
    values = closes[-boll_period:]
    mean = sum(values) / boll_period
    variance = sum((value - mean) ** 2 for value in values) / boll_period
    width = boll_stddev * sqrt(variance)
    return mean + width, mean, mean - width


class Bollinger:
    def __init__(self, boll_period: int, boll_stddev: float):
        self.boll_period = boll_period
        self.boll_stddev = boll_stddev
        self.closes = deque(maxlen=boll_period)

    def update(self, close: float) -> tuple[float | None, float | None, float | None]:
        self.closes.append(close)
        return bollinger(list(self.closes), self.boll_period, self.boll_stddev)
