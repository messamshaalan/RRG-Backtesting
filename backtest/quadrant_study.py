"""
Quadrant entry study: compares returns when buying at Leading, Improving, or Lagging.

run_study() returns a dict keyed by (timeframe, entry_quadrant) with backtest
results so the dashboard can overlay all three equity curves and compare stats.
"""
from __future__ import annotations

import pandas as pd

import config
from data.fetcher import load_all
from backtest.engine import run, performance_summary
from rrg.quadrant import Quadrant
from strategy.base import BaseStrategy


# ── Entry strategies ──────────────────────────────────────────────────────────

class _QuadrantEntryStrategy(BaseStrategy):
    """
    Generic single-quadrant entry strategy.
    Buys the top-N symbols in `target_quadrant` ranked by RS-Ratio.
    Exits when a holding leaves that quadrant.
    """

    def __init__(self, target_quadrant: str, max_positions: int = config.MAX_POSITIONS):
        self.target_quadrant = target_quadrant
        self.max_positions   = max_positions

    def select(
        self,
        date: pd.Timestamp,
        rs_ratio: pd.Series,
        rs_momentum: pd.Series,
        quadrants: pd.Series,
        prices: pd.Series,
        current_positions: list[str],
    ) -> list[str]:
        eligible = quadrants[quadrants == self.target_quadrant]
        if eligible.empty:
            return []
        ranked = rs_ratio[eligible.index].nlargest(self.max_positions)
        return ranked.index.tolist()


class LeadingEntryStrategy(_QuadrantEntryStrategy):
    """Buy top-N symbols in the Leading quadrant."""
    def __init__(self, max_positions: int = config.MAX_POSITIONS):
        super().__init__(Quadrant.LEADING, max_positions)


class ImprovingEntryStrategy(_QuadrantEntryStrategy):
    """Buy top-N symbols in the Improving quadrant (early rotation)."""
    def __init__(self, max_positions: int = config.MAX_POSITIONS):
        super().__init__(Quadrant.IMPROVING, max_positions)


class LaggingEntryStrategy(_QuadrantEntryStrategy):
    """Buy top-N symbols in the Lagging quadrant (contrarian / mean-reversion)."""
    def __init__(self, max_positions: int = config.MAX_POSITIONS):
        super().__init__(Quadrant.LAGGING, max_positions)


class WeakeningEntryStrategy(_QuadrantEntryStrategy):
    """Buy top-N symbols in the Weakening quadrant."""
    def __init__(self, max_positions: int = config.MAX_POSITIONS):
        super().__init__(Quadrant.WEAKENING, max_positions)


ENTRY_STRATEGIES: dict[str, type[_QuadrantEntryStrategy]] = {
    "Leading":   LeadingEntryStrategy,
    "Improving": ImprovingEntryStrategy,
    "Weakening": WeakeningEntryStrategy,
    "Lagging":   LaggingEntryStrategy,
}


# ── Study runner ──────────────────────────────────────────────────────────────

StudyKey   = tuple[str, str]   # (timeframe, entry_label)
StudyResult = dict             # engine output dict + "summary" key


def run_study(
    timeframes: list[str] | None = None,
    force_refresh: bool = False,
    precomputed: dict[str, tuple] | None = None,
) -> dict[StudyKey, StudyResult]:
    """
    Run all four entry strategies across all requested timeframes.

    precomputed: optional {tf: (universe, benchmark, rs_ratio, rs_momentum, quadrants_df)}
      If supplied for a timeframe, skips data loading and RRG computation entirely.

    Returns:
        {("1wk", "Leading"): {equity, trades, positions, rs_ratio, ..., summary}, ...}
    """
    if timeframes is None:
        timeframes = list(config.TIMEFRAMES.keys())
    precomputed = precomputed or {}

    results: dict[StudyKey, StudyResult] = {}

    for tf in timeframes:
        print(f"\n-- Timeframe: {config.TIMEFRAMES[tf]['label']} --")

        if tf in precomputed:
            universe, benchmark, rs_ratio, rs_momentum, quadrants_df = precomputed[tf]
            rrg_tuple: tuple | None = (rs_ratio, rs_momentum, quadrants_df)
        else:
            universe, benchmark = load_all(interval=tf, force_refresh=force_refresh)
            rrg_tuple = None

        tf_cfg     = config.TIMEFRAMES[tf]
        rebal_freq = tf_cfg["rebalance_freq"]

        for label, StratCls in ENTRY_STRATEGIES.items():
            print(f"   Running {label} entry strategy...")
            strategy = StratCls()
            result   = run(
                universe, benchmark, strategy,
                rebalance_freq=rebal_freq,
                timeframe=tf,
                _precomputed_rrg=rrg_tuple,
            )
            num_trades = len(result["trades"])
            result["summary"] = performance_summary(
                result["equity"],
                benchmark=benchmark,
                num_trades=num_trades,
            )
            results[(tf, label)] = result

    return results


def summary_table(study: dict[StudyKey, StudyResult]) -> pd.DataFrame:
    """
    Pivot the study results into a DataFrame:
    rows = (timeframe, entry), columns = metric names.
    """
    rows = []
    for (tf, label), res in study.items():
        row = {"Timeframe": config.TIMEFRAMES[tf]["label"], "Entry": label}
        row.update(res["summary"].to_dict())
        rows.append(row)
    df = pd.DataFrame(rows).set_index(["Timeframe", "Entry"])
    return df
