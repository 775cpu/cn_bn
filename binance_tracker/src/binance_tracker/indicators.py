from collections import deque
from math import sqrt


def bollinger(closes: list[float], period: int, deviations: float) -> tuple[float | None, float | None, float | None]:
    if len(closes) < period:
        return None, None, None
    values = closes[-period:]
    mean = sum(values) / period
    variance = sum((value - mean) ** 2 for value in values) / period
    width = deviations * sqrt(variance)
    return mean + width, mean, mean - width


class Bollinger:
    def __init__(self, period: int, deviations: float):
        self.period = period
        self.deviations = deviations
        self.closes = deque(maxlen=period)

    def update(self, close: float) -> tuple[float | None, float | None, float | None]:
        self.closes.append(close)
        return bollinger(list(self.closes), self.period, self.deviations)
