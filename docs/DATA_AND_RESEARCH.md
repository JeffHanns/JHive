# Forex data and first research engine

## Selected first release

- Market: forex
- Data: free historical files, loaded manually from CSV
- Execution: paper research only; no broker or order API is used

## First input source

The initial adapter reads the HistData generic ASCII M1 format. HistData documents rows as `timestamp;open;high;low;close;volume`, with timestamps formatted `YYYYMMDD HHMMSS`. Its documentation describes the timestamps as EST without daylight-saving adjustment. JHive therefore retains the timestamp as naive source time; users must not interpret it as UTC without an explicit conversion rule. See [HistData file specification](https://www.histdata.com/f-a-q/data-files-detailed-specification/) and [free download page](https://www.histdata.com/download-free-forex-data/).

HistData describes downloads as free, but says the data is provided without warranty. “Free” does not by itself establish a right to redistribute data. Keep original files local, review the provider's current terms before sharing data, and record source, download date, symbol, coverage, file checksum, and timezone with each future dataset registration. There is no automatic downloader or live feed in this release.

## Implemented simulation

`jhive.research.read_histdata_ascii` rejects malformed rows, invalid/non-finite values, inconsistent OHLC ranges, and non-increasing timestamps. `sma_crossover_backtest` is a long-only baseline for exploring the pipeline:

1. It computes fast and slow simple moving averages over completed closes.
2. It enters on an upward crossover and exits on a downward crossover.
3. It fills at the next bar's open to avoid using the signal bar's close as an execution price.
4. It charges configurable basis-point costs on both entry and exit notional.
5. It closes a remaining position at the last close and labels that exit `end_of_data`.

This is a deliberately small baseline, not a recommendation. The initial costs are a single user-supplied rate; they do not model variable bid/ask spread, slippage, financing/rollover, liquidity, gaps, market impact, leverage, margin, pip value, or broker-specific fills. No short positions, position sizing, or multi-pair portfolio are supported. Do not use the resulting metrics as evidence of expected live returns.

## Reproducibility work still required

Before strategy comparisons, JHive needs an immutable dataset registry and checksum, quality/gap reports, clear pair-specific cost assumptions, a benchmark, a time-separated holdout, and walk-forward evaluation. Persist the exact strategy parameters and input dataset identity with every run. Results should be shown separately from the dashboard's current sample figures until those values are connected to recorded paper-account events.
