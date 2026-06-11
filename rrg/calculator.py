"""
Correct JdK RS-Ratio and RS-Momentum implementation.

Source: Julius de Kempenaer / relativerotationgraphs.com

RS-Ratio  = WMA(RS, n) / WMA(WMA(RS, n), n) * 100
RS-Momentum = RS_Ratio[t] / RS_Ratio[t - m] * 100

Both series are centred at 100:
  > 100  outperforming / accelerating vs benchmark
  < 100  underperforming / decelerating vs benchmark

Warm-up rows needed before the series are valid:
  RS-Ratio    requires 2 * ratio_period bars
  RS-Momentum requires 2 * ratio_period + momentum_period bars
"""
from __future__ import annotations

import pandas as pd
import numpy as np

import config


# ── Moving average helpers ────────────────────────────────────────────────────

def _wma(series: pd.Series, period: int) -> pd.Series:
    """Weighted Moving Average — linearly increasing weights."""
    weights = np.arange(1, period + 1, dtype=float)
    weights /= weights.sum()
    values = series.to_numpy(dtype=float)
    n = len(values)
    result = np.full(n, np.nan)
    if n >= period:
        windows = np.lib.stride_tricks.sliding_window_view(values, period)
        dot = windows @ weights
        dot[np.isnan(windows).any(axis=1)] = np.nan
        result[period - 1:] = dot
    return pd.Series(result, index=series.index, dtype=float)


def _wma_df(df: pd.DataFrame, period: int) -> pd.DataFrame:
    """WMA applied to all DataFrame columns at once — vectorised, no Python-level rolling loop."""
    weights = np.arange(1, period + 1, dtype=float)
    weights /= weights.sum()
    arr = df.to_numpy(dtype=float)
    n, m = arr.shape
    result = np.full((n, m), np.nan)
    if n >= period:
        for j in range(m):
            col = arr[:, j]
            windows = np.lib.stride_tricks.sliding_window_view(col, period)
            dot = windows @ weights
            dot[np.isnan(windows).any(axis=1)] = np.nan
            result[period - 1:, j] = dot
    return pd.DataFrame(result, index=df.index, columns=df.columns)


# ── Core calculations ─────────────────────────────────────────────────────────

def compute_rs(universe: pd.DataFrame, benchmark: pd.Series) -> pd.DataFrame:
    """Raw relative strength: (symbol / benchmark) * 100."""
    return universe.div(benchmark, axis=0) * 100.0


def compute_rs_ratio(
    universe: pd.DataFrame,
    benchmark: pd.Series,
    ratio_period: int = config.TIMEFRAMES[config.DEFAULT_TIMEFRAME]["ratio_period"],
) -> pd.DataFrame:
    """
    JdK RS-Ratio = WMA(RS, n) / WMA(WMA(RS, n), n) * 100

    Measures whether a security is in a relative UPtrend (>100) or
    DOWNtrend (<100) vs the benchmark.
    """
    rs          = compute_rs(universe, benchmark)
    rs_smooth   = _wma_df(rs, ratio_period)
    rs_baseline = _wma_df(rs_smooth, ratio_period)
    return (rs_smooth / rs_baseline) * 100.0


def compute_rs_momentum(
    rs_ratio: pd.DataFrame,
    momentum_period: int = config.TIMEFRAMES[config.DEFAULT_TIMEFRAME]["momentum_period"],
) -> pd.DataFrame:
    """
    JdK RS-Momentum = (RS_Ratio[t] / RS_Ratio[t - m]) * 100

    Measures whether the relative trend is accelerating (>100) or
    decelerating (<100).
    """
    return (rs_ratio / rs_ratio.shift(momentum_period)) * 100.0


def compute_rrg(
    universe: pd.DataFrame,
    benchmark: pd.Series,
    ratio_period: int | None = None,
    momentum_period: int | None = None,
    normalize_window: int | None = None,   # kept for API compat, not used
    timeframe: str = config.DEFAULT_TIMEFRAME,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Full JdK RRG pipeline for a given timeframe.

    Returns (rs_ratio_df, rs_momentum_df) with warm-up rows trimmed.
    Warm-up = 2 * ratio_period + momentum_period bars.
    """
    tf  = config.TIMEFRAMES[timeframe]
    rp  = ratio_period    or tf["ratio_period"]
    mp  = momentum_period or tf["momentum_period"]

    rs_ratio    = compute_rs_ratio(universe, benchmark, rp)
    rs_momentum = compute_rs_momentum(rs_ratio, mp)

    warm_up = 2 * rp + mp
    return rs_ratio.iloc[warm_up:], rs_momentum.iloc[warm_up:]
