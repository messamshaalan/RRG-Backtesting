"""
Downloads and caches OHLCV data from Yahoo Finance for multiple timeframes.

Supported intervals: '1h', '1d', '1wk'
Cache location: data/.cache/{symbol}_{interval}.parquet

yfinance 1H limitation: intraday data is capped at the last 730 calendar days.
"""
from __future__ import annotations

import os
import warnings
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

import config

_CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _cache_path(symbol: str, interval: str) -> str:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    return os.path.join(_CACHE_DIR, f"{symbol}_{interval}.parquet")


def _effective_dates(interval: str) -> tuple[str, str]:
    """
    Return (start, end) dates for a given interval.
    For 1H, yfinance only provides the last 730 calendar days regardless of
    what start date is requested — we cap it so the cache key is stable.
    """
    tf = config.TIMEFRAMES[interval]
    end = config.END_DATE

    # If end date is in the future vs today, clamp to today
    today = datetime.utcnow().date()
    end_dt = datetime.strptime(end, "%Y-%m-%d").date()
    if end_dt > today:
        end = str(today)

    max_days = tf.get("max_history_days")
    if max_days is not None:
        earliest = (datetime.utcnow() - timedelta(days=max_days)).strftime("%Y-%m-%d")
        start = max(config.START_DATE, earliest)
    else:
        start = config.START_DATE

    return start, end


def _flatten_columns(df: pd.DataFrame, symbol: str) -> pd.Series:
    """
    yfinance sometimes returns a MultiIndex column (Price, Ticker).
    Flatten it and extract the configured PRICE_COL for a single symbol.
    """
    if isinstance(df.columns, pd.MultiIndex):
        # Level 0 = price type, Level 1 = ticker
        df.columns = df.columns.droplevel(1)

    if df.empty:
        raise ValueError(f"No data returned for {symbol!r}")

    if config.PRICE_COL not in df.columns:
        raise KeyError(
            f"Column '{config.PRICE_COL}' not found for {symbol!r}. "
            f"Available: {list(df.columns)}"
        )

    series = df[config.PRICE_COL].squeeze()
    series.name = symbol
    return series


def _validate_series(series: pd.Series, symbol: str, interval: str) -> None:
    """Warn if the downloaded series has gaps or falls short of the expected span."""
    if series.empty:
        raise ValueError(f"Empty price series for {symbol!r} [{interval}].")

    tf = config.TIMEFRAMES[interval]
    start, end = _effective_dates(interval)
    expected_start = pd.Timestamp(start)
    expected_end   = pd.Timestamp(end)
    actual_start   = series.index[0]
    actual_end     = series.index[-1]

    # Allow 5-bar tolerance for holidays / weekends at boundaries
    bar_map = {"1h": timedelta(hours=5), "1d": timedelta(days=5), "1wk": timedelta(weeks=5)}
    tol = bar_map.get(interval, timedelta(days=10))

    if actual_start > expected_start + tol:
        warnings.warn(
            f"[{symbol}/{interval}] Data starts {actual_start.date()} "
            f"(expected ~{expected_start.date()}). History may be shorter than configured.",
            stacklevel=3,
        )

    if actual_end < expected_end - tol:
        warnings.warn(
            f"[{symbol}/{interval}] Data ends {actual_end.date()} "
            f"(expected ~{expected_end.date()}). May be missing recent bars.",
            stacklevel=3,
        )

    total_years = (actual_end - actual_start).days / 365.25
    if total_years < 1:
        warnings.warn(
            f"[{symbol}/{interval}] Only {total_years:.1f} years of data available. "
            "RRG warm-up will consume most of it; results may be unreliable.",
            stacklevel=3,
        )


def _download(symbol: str, interval: str) -> pd.Series:
    start, end = _effective_dates(interval)
    df = yf.download(
        symbol,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=True,
        progress=False,
        multi_level_index=False,   # suppress MultiIndex in newer yfinance versions
    )
    series = _flatten_columns(df, symbol)
    series.index = pd.to_datetime(series.index)
    series = series.sort_index().dropna()
    _validate_series(series, symbol, interval)
    return series


# ── Public API ────────────────────────────────────────────────────────────────

def load_prices(
    symbols: list[str],
    interval: str = config.DEFAULT_TIMEFRAME,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Return a DataFrame of closing prices indexed by datetime.
    Rows = bars, Columns = symbols.
    Data is cached per (symbol, interval) as parquet in data/.cache/.
    """
    if interval not in config.TIMEFRAMES:
        raise ValueError(
            f"Unknown interval {interval!r}. Choose from: {list(config.TIMEFRAMES)}"
        )

    series_list: list[pd.Series] = []
    for sym in symbols:
        path = _cache_path(sym, interval)
        if not force_refresh and os.path.exists(path):
            s = pd.read_parquet(path).squeeze()
            s.name = sym
            s.index = pd.to_datetime(s.index)
        else:
            print(f"  Downloading {sym} [{interval}]...")
            s = _download(sym, interval)
            s.to_frame().to_parquet(path)
        series_list.append(s)

    prices = pd.concat(series_list, axis=1).sort_index()

    # yfinance weekly data can report on inconsistent weekdays (Monday vs Thursday)
    # across different ETFs or download runs, causing misaligned indexes with many NaN
    # rows after concat.  Resample to a single canonical anchor per interval so all
    # symbols share the same date index.
    _resample_anchor = {"1wk": "W-FRI", "1d": "B"}
    if interval in _resample_anchor:
        prices = prices.resample(_resample_anchor[interval]).last()

    # Drop rows where ALL symbols are NaN (e.g. pre-inception dates for newer ETFs)
    prices = prices.dropna(how="all")

    return prices


def load_all(
    interval: str = config.DEFAULT_TIMEFRAME,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Convenience loader.
    Returns (universe_prices, benchmark_prices) for the given interval.
    """
    all_syms = [config.BENCHMARK] + config.SYMBOLS
    prices = load_prices(all_syms, interval=interval, force_refresh=force_refresh)

    benchmark = prices[config.BENCHMARK]
    # Keep only universe symbols that exist in the downloaded frame
    available = [s for s in config.SYMBOLS if s in prices.columns]
    universe  = prices[available]

    # Drop rows where benchmark is NaN — RS = ETF/SPY can't be computed without it.
    # This removes tail stubs created by resample anchoring past the last trading day.
    valid_idx = benchmark.dropna().index
    benchmark = benchmark.loc[valid_idx]
    universe  = universe.loc[valid_idx]

    return universe, benchmark
