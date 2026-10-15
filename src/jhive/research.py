"""Small, deterministic and offline forex research tools.

This module deliberately has no networking, broker, or order-submission code.
HistData generic ASCII minute bars can be loaded for offline paper research.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from pathlib import Path


@dataclass(frozen=True)
class Bar:
    """A validated OHLCV bar. Timestamps retain the source's stated timezone."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Trade:
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    units: float
    pnl: float
    return_pct: float
    exit_reason: str


@dataclass(frozen=True)
class BacktestResult:
    trades: tuple[Trade, ...]
    starting_cash: float
    ending_cash: float
    net_pnl: float
    max_drawdown_pct: float
    bars: int


def read_histdata_ascii(path: str | Path) -> list[Bar]:
    """Read semicolon-delimited HistData generic ASCII M1 bars.

    The source documents timestamps as fixed EST without daylight-saving
    adjustment. They are kept naive so callers cannot mistake them for UTC.
    """
    bars: list[Bar] = []
    previous: datetime | None = None
    with Path(path).open("r", encoding="utf-8-sig", newline="") as source:
        for line_number, row in enumerate(csv.reader(source, delimiter=";"), start=1):
            if not row or (len(row) == 1 and not row[0].strip()):
                continue
            if len(row) != 6:
                raise ValueError(f"line {line_number}: expected 6 semicolon-separated fields")
            try:
                timestamp = datetime.strptime(row[0].strip(), "%Y%m%d %H%M%S")
                open_price, high, low, close, volume = map(float, row[1:])
            except ValueError as exc:
                raise ValueError(f"line {line_number}: invalid timestamp or numeric field") from exc
            values = (open_price, high, low, close, volume)
            if any(not math.isfinite(value) for value in values):
                raise ValueError(f"line {line_number}: values must be finite")
            if min(open_price, high, low, close) <= 0 or volume < 0:
                raise ValueError(f"line {line_number}: prices must be positive and volume non-negative")
            if high < max(open_price, close, low) or low > min(open_price, close, high):
                raise ValueError(f"line {line_number}: inconsistent OHLC range")
            if previous is not None and timestamp <= previous:
                raise ValueError(f"line {line_number}: timestamps must be strictly increasing")
            bars.append(Bar(timestamp, open_price, high, low, close, volume))
            previous = timestamp
    if not bars:
        raise ValueError("file contains no bars")
    return bars


def sma_crossover_backtest(
    bars: Iterable[Bar],
    *,
    fast_window: int = 10,
    slow_window: int = 30,
    starting_cash: float = 10_000.0,
    units: float = 1_000.0,
    cost_bps_per_side: float = 2.0,
) -> BacktestResult:
    """Run a long-only SMA crossover simulation with next-bar-open fills.

    Costs are charged in quote-currency units as basis points of traded
    notional on each side. Signals use completed closes; entries/exits happen
    at the next bar open. Any final open position is marked out at the last
    close and labeled ``end_of_data``. This is research output, not a forecast.
    """
    data = list(bars)
    if fast_window < 1 or slow_window <= fast_window:
        raise ValueError("windows must satisfy 1 <= fast_window < slow_window")
    if starting_cash <= 0 or units <= 0 or cost_bps_per_side < 0:
        raise ValueError("cash and units must be positive; costs cannot be negative")
    if len(data) < slow_window + 1:
        raise ValueError(f"at least {slow_window + 1} bars are required")
    if any(right.timestamp <= left.timestamp for left, right in pairwise(data)):
        raise ValueError("bar timestamps must be strictly increasing")

    closes = [bar.close for bar in data]

    def average(end: int, window: int) -> float:
        return sum(closes[end - window + 1 : end + 1]) / window

    trades: list[Trade] = []
    entry: tuple[int, float] | None = None
    cash = starting_cash
    peak = starting_cash
    max_drawdown = 0.0
    cost_rate = cost_bps_per_side / 10_000

    for fill_index in range(slow_window, len(data)):
        signal_index = fill_index - 1
        prior_index = signal_index - 1
        if prior_index >= slow_window - 1:
            fast_now, slow_now = average(signal_index, fast_window), average(signal_index, slow_window)
            fast_before, slow_before = average(prior_index, fast_window), average(prior_index, slow_window)
            crossed_up = fast_before <= slow_before and fast_now > slow_now
            crossed_down = fast_before >= slow_before and fast_now < slow_now
            if entry is None and crossed_up:
                price = data[fill_index].open
                cash -= units * price * cost_rate
                entry = (fill_index, price)
            elif entry is not None and crossed_down:
                entry_index, entry_price = entry
                exit_price = data[fill_index].open
                pnl = units * (exit_price - entry_price) - units * (entry_price + exit_price) * cost_rate
                cash += units * (exit_price - entry_price) - units * exit_price * cost_rate
                trades.append(Trade(data[entry_index].timestamp, data[fill_index].timestamp,
                                    entry_price, exit_price, units, pnl,
                                    (exit_price / entry_price - 1) * 100, "signal"))
                entry = None
        unrealized = units * (data[fill_index].close - entry[1]) if entry else 0.0
        equity = cash + unrealized
        peak = max(peak, equity)
        if peak:
            max_drawdown = max(max_drawdown, (peak - equity) / peak * 100)

    if entry is not None:
        entry_index, entry_price = entry
        exit_price = data[-1].close
        pnl = units * (exit_price - entry_price) - units * (entry_price + exit_price) * cost_rate
        cash += units * (exit_price - entry_price) - units * exit_price * cost_rate
        trades.append(Trade(data[entry_index].timestamp, data[-1].timestamp,
                            entry_price, exit_price, units, pnl,
                            (exit_price / entry_price - 1) * 100, "end_of_data"))
    return BacktestResult(tuple(trades), starting_cash, cash, cash - starting_cash,
                          max_drawdown, len(data))
