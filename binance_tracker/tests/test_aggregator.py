from binance_tracker.aggregator import SymbolBook
from binance_tracker.models import Kline


def test_trade_rolls_1m_and_updates_higher_period():
    book = SymbolBook("BTCUSDT", ("1m", "3m"), boll_period=2)
    book.update_trade(100, 2, 0, 200)
    book.update_trade(105, 1, 59_000, 105)
    book.update_trade(101, 3, 60_000, 303)

    one_minute = book.snapshot("1m", 2)
    assert one_minute[0]["open"] == 100
    assert one_minute[0]["high"] == 105
    assert one_minute[0]["close"] == 105
    assert one_minute[0]["closed"] is True
    assert one_minute[1]["open"] == 101

    three_minute = book.snapshot("3m", 1)[0]
    assert three_minute["open"] == 100
    assert three_minute["high"] == 105
    assert three_minute["low"] == 100
    assert three_minute["close"] == 101


def test_gap_is_filled_with_last_close():
    book = SymbolBook("BTCUSDT", ("1m",), boll_period=2)
    book.update_trade(100, 1, 0)
    book.update_trade(103, 1, 180_000)
    bars = book.snapshot("1m", 4)
    assert [bar["open"] for bar in bars] == [100, 100, 100, 103]
    assert bars[1]["volume"] == 0
    assert bars[2]["closed"] is True


def test_bollinger_is_calculated_from_latest_closes():
    book = SymbolBook("BTCUSDT", ("1m",), boll_period=2, boll_stddev=2)
    book.replace("1m", [Kline(0, 1, 1, 1, 1), Kline(60_000, 3, 3, 3, 3)])
    boll = book.snapshot("1m")[0]["boll"]
    assert boll["middle"] == 2
    assert round(boll["upper"], 6) == round(2 + 2 * 1, 6)
    assert round(boll["lower"], 6) == 0


def test_mismatch_does_not_rewind_active_bar():
    book = SymbolBook("BTCUSDT", ("1m",), boll_period=2)
    book.update_trade(100, 1, 60_000)
    rest = [Kline(0, 90, 110, 80, 100, 20, 2000, 10, True), Kline(60_000, 99, 105, 95, 99, 9, 891, 9, False)]
    book.merge_mismatch("1m", rest)
    latest = book.snapshot("1m", 1)[0]
    assert latest["open_time"] == 60_000
    assert latest["close"] == 100
    assert latest["volume"] == 1


def test_mismatch_drops_stale_active_bar_when_rest_is_newer():
    book = SymbolBook("BTCUSDT", ("1m",), boll_period=2)
    book.update_trade(100, 1, 60_000)
    rest = [
        Kline(0, 90, 110, 80, 100, 20, 2000, 10, True),
        Kline(120_000, 120, 125, 119, 123, 5, 615, 5, False),
    ]

    book.merge_mismatch("1m", rest)

    bars = book.bars("1m")
    assert [bar.open_time for bar in bars] == [0, 120_000]


def test_replace_keeps_bars_strictly_ordered_and_unique():
    book = SymbolBook("BTCUSDT", ("1m",), boll_period=2)
    book.replace("1m", [Kline(60_000, 2, 2, 2, 2), Kline(0, 1, 1, 1, 1), Kline(60_000, 3, 3, 3, 3)])

    bars = book.bars("1m")
    assert [bar.open_time for bar in bars] == [0, 60_000]
    assert bars[-1].close == 3
