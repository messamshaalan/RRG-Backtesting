"""
Holding time analysis: how long each sector stays in each RRG quadrant
before flipping to an adjacent one.

compute_streaks()   → raw streak records (symbol, quadrant, start, end, bars)
streak_summary()    → per-symbol × per-quadrant stats (min/mean/max bars)
overall_summary()   → universe-level stats (ignoring symbol dimension)
"""
from __future__ import annotations

import pandas as pd
import numpy as np

from rrg.quadrant import Quadrant

ALL_QUADRANTS = [Quadrant.LEADING, Quadrant.IMPROVING, Quadrant.WEAKENING, Quadrant.LAGGING]


def compute_streaks(quadrants_df: pd.DataFrame) -> pd.DataFrame:
    """
    Find every continuous streak a symbol spends in one quadrant.

    Parameters
    ----------
    quadrants_df : shape (bars, symbols) — quadrant string per cell

    Returns
    -------
    DataFrame with columns:
        symbol, quadrant, start_date, end_date, bars
    """
    records: list[dict] = []

    for sym in quadrants_df.columns:
        series = quadrants_df[sym].dropna()
        if series.empty:
            continue

        streak_quad  = series.iloc[0]
        streak_start = series.index[0]
        streak_len   = 1

        for dt, quad in series.iloc[1:].items():
            if quad == streak_quad:
                streak_len += 1
            else:
                records.append({
                    "symbol":     sym,
                    "quadrant":   streak_quad,
                    "start_date": streak_start,
                    "end_date":   series.index[series.index.get_loc(dt) - 1],
                    "bars":       streak_len,
                })
                streak_quad  = quad
                streak_start = dt
                streak_len   = 1

        # flush last streak
        records.append({
            "symbol":     sym,
            "quadrant":   streak_quad,
            "start_date": streak_start,
            "end_date":   series.index[-1],
            "bars":       streak_len,
        })

    return pd.DataFrame(records)


def streak_summary(streaks: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate streaks per symbol × quadrant.

    Returns DataFrame indexed by (symbol, quadrant) with:
        count, min_bars, mean_bars, max_bars, median_bars
    """
    if streaks.empty:
        return pd.DataFrame()

    agg = (
        streaks.groupby(["symbol", "quadrant"])["bars"]
        .agg(count="count", min_bars="min", mean_bars="mean",
             median_bars="median", max_bars="max")
        .round(1)
    )
    return agg


def overall_summary(streaks: pd.DataFrame) -> pd.DataFrame:
    """
    Universe-level holding time stats per quadrant (pooled across all symbols).

    Returns DataFrame indexed by quadrant with:
        count, min_bars, mean_bars, median_bars, max_bars
    """
    if streaks.empty:
        return pd.DataFrame()

    agg = (
        streaks.groupby("quadrant")["bars"]
        .agg(count="count", min_bars="min", mean_bars="mean",
             median_bars="median", max_bars="max")
        .round(1)
        .reindex(ALL_QUADRANTS)
    )
    return agg


def holding_heatmap_data(
    streaks: pd.DataFrame,
    stat: str = "mean_bars",
) -> pd.DataFrame:
    """
    Pivot for the dashboard heatmap.
    Rows = symbols, Columns = quadrants, values = stat (e.g. 'mean_bars').

    stat options: 'min_bars', 'mean_bars', 'median_bars', 'max_bars', 'count'
    """
    summary = streak_summary(streaks)
    if summary.empty:
        return pd.DataFrame()

    summary = summary.reset_index()
    pivot = summary.pivot(index="symbol", columns="quadrant", values=stat)
    # Reorder columns to clock-wise quadrant order
    cols = [q for q in ALL_QUADRANTS if q in pivot.columns]
    return pivot[cols].round(1)


def compute_all_timeframes(
    timeframe_quadrants: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """
    Convenience: run compute_streaks for each timeframe.

    Parameters
    ----------
    timeframe_quadrants : {timeframe_label: quadrants_df}

    Returns
    -------
    {timeframe_label: streaks_df}
    """
    return {tf: compute_streaks(qdf) for tf, qdf in timeframe_quadrants.items()}
