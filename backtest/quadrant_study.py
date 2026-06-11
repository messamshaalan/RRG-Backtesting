"""
Quadrant entry study: runs all entry strategies and compares equity curves.

run_study() returns a dict keyed by (timeframe, strategy_label) with backtest
results so the dashboard can overlay all equity curves and compare stats.
"""
from __future__ import annotations

import pandas as pd

import config
from data.fetcher import load_all
from backtest.engine import run, performance_summary
from rrg.quadrant import Quadrant
from strategy.base import BaseStrategy


# ── Original single-quadrant strategies ──────────────────────────────────────

class _QuadrantEntryStrategy(BaseStrategy):
    """Generic single-quadrant entry: buy top-N by RS-Ratio, exit when leaving."""

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
        return rs_ratio[eligible.index].nlargest(self.max_positions).index.tolist()


class LeadingEntryStrategy(_QuadrantEntryStrategy):
    def __init__(self, max_positions: int = config.MAX_POSITIONS):
        super().__init__(Quadrant.LEADING, max_positions)


class ImprovingEntryStrategy(_QuadrantEntryStrategy):
    def __init__(self, max_positions: int = config.MAX_POSITIONS):
        super().__init__(Quadrant.IMPROVING, max_positions)


class LaggingEntryStrategy(_QuadrantEntryStrategy):
    def __init__(self, max_positions: int = config.MAX_POSITIONS):
        super().__init__(Quadrant.LAGGING, max_positions)


class WeakeningEntryStrategy(_QuadrantEntryStrategy):
    def __init__(self, max_positions: int = config.MAX_POSITIONS):
        super().__init__(Quadrant.WEAKENING, max_positions)


# ── Strategy factory ──────────────────────────────────────────────────────────

def _make_strategies(benchmark: pd.Series) -> dict[str, BaseStrategy]:
    """Instantiate all strategies for a given run. benchmark needed for RegimeFilter."""
    from strategy.examples import (
        EarlyRotationStrategy,
        RegimeFilteredStrategy,
        ConfirmationStrategy,
        ScoreWeightedStrategy,
        MomentumAccelerationStrategy,
        BuyHoldStrategy,
    )
    strategies: dict[str, BaseStrategy] = {
        "Leading":        LeadingEntryStrategy(),
        "Improving":      ImprovingEntryStrategy(),
        "Weakening":      WeakeningEntryStrategy(),
        "Lagging":        LaggingEntryStrategy(),
        "Early Rotation": EarlyRotationStrategy(),
        "Regime Filter":  RegimeFilteredStrategy(benchmark),
        "Confirmation":   ConfirmationStrategy(),
        "Score Weighted": ScoreWeightedStrategy(),
        "Mom. Accel.":    MomentumAccelerationStrategy(),
    }
    # Individual ETF buy & holds — one per symbol in the universe
    for sym in config.SYMBOLS:
        strategies[f"B&H {sym}"] = BuyHoldStrategy(sym)
    return strategies


# ── Study runner ──────────────────────────────────────────────────────────────

StudyKey    = tuple[str, str]   # (timeframe, strategy_label)
StudyResult = dict              # engine output dict + "summary" key


def run_study(
    timeframes: list[str] | None = None,
    force_refresh: bool = False,
    precomputed: dict[str, tuple] | None = None,
) -> dict[StudyKey, StudyResult]:
    """
    Run all strategies across all requested timeframes.

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
        strategies = _make_strategies(benchmark)

        for label, strategy in strategies.items():
            print(f"   Running {label}…")
            result = run(
                universe, benchmark, strategy,
                rebalance_freq=rebal_freq,
                timeframe=tf,
                _precomputed_rrg=rrg_tuple,
            )
            result["summary"] = performance_summary(
                result["equity"],
                benchmark=benchmark,
                num_trades=len(result["trades"]),
            )
            results[(tf, label)] = result

    return results


def summary_table(study: dict[StudyKey, StudyResult]) -> pd.DataFrame:
    """Pivot study results into rows=(timeframe, strategy), cols=metrics."""
    rows = []
    for (tf, label), res in study.items():
        row = {"Timeframe": config.TIMEFRAMES[tf]["label"], "Entry": label}
        row.update(res["summary"].to_dict())
        rows.append(row)
    return pd.DataFrame(rows).set_index(["Timeframe", "Entry"])
