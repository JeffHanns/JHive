from datetime import datetime, timedelta

import pytest

from jhive.research import Bar, read_histdata_ascii, sma_crossover_backtest


def bars_from_closes(closes):
    origin = datetime(2026, 1, 1)
    return [Bar(origin + timedelta(minutes=i), price, price, price, price, 0)
            for i, price in enumerate(closes)]


def test_reads_histdata_ascii_and_keeps_source_timezone_naive(tmp_path):
    source = tmp_path / "EURUSD.csv"
    source.write_text("20260101 000000;1.10000;1.10100;1.09900;1.10050;0\n", encoding="utf-8")
    result = read_histdata_ascii(source)
    assert result[0].close == 1.1005
    assert result[0].timestamp.tzinfo is None


@pytest.mark.parametrize("row, message", [
    ("20260101 000000;1;2;0;1;0;extra", "expected 6"),
    ("bad;1;2;0;1;0", "invalid timestamp"),
    ("20260101 000000;1;0.9;0.8;1;0", "inconsistent OHLC"),
    ("20260101 000000;1;2;0;1;-1", "non-negative"),
])
def test_rejects_bad_rows(tmp_path, row, message):
    source = tmp_path / "bad.csv"
    source.write_text(row + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        read_histdata_ascii(source)


def test_rejects_duplicate_or_out_of_order_timestamps(tmp_path):
    source = tmp_path / "unordered.csv"
    source.write_text(
        "20260101 000100;1;2;0.5;1;0\n20260101 000100;1;2;0.5;1;0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="strictly increasing"):
        read_histdata_ascii(source)


def test_sma_backtest_uses_next_bar_open_and_charges_both_sides():
    bars = bars_from_closes([10, 10, 10, 12, 14, 16, 10, 9])
    result = sma_crossover_backtest(bars, fast_window=2, slow_window=3,
                                    starting_cash=1_000, units=10, cost_bps_per_side=10)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_time == bars[4].timestamp
    assert trade.exit_time == bars[7].timestamp
    assert trade.entry_price == 14
    assert trade.exit_price == 9
    assert trade.exit_reason == "signal"
    assert result.ending_cash == pytest.approx(949.77)
    assert result.net_pnl == pytest.approx(-50.23)


def test_open_position_is_marked_out_at_end_of_data():
    result = sma_crossover_backtest(bars_from_closes([10, 10, 10, 12, 14]),
                                    fast_window=2, slow_window=3, units=1,
                                    cost_bps_per_side=0)
    assert result.trades[0].exit_reason == "end_of_data"
    assert result.trades[0].exit_price == 14


def test_sma_backtest_validates_windows_and_data_length():
    data = bars_from_closes([1, 2, 3, 4])
    with pytest.raises(ValueError, match="windows"):
        sma_crossover_backtest(data, fast_window=3, slow_window=2)
    with pytest.raises(ValueError, match="at least 5 bars"):
        sma_crossover_backtest(data, fast_window=2, slow_window=4)
