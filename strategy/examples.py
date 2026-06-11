"""
Ready-to-use example strategies.  Use these as templates for your custom rules.
"""
from __future__ import annotations

import pandas as pd

import config
from rrg.quadrant import Quadrant
from strategy.base import BaseStrategy


class LeadingOnlyStrategy(BaseStrategy):
    """Hold top-N in Leading ranked by RS-Ratio. Exit when leaving Leading."""

    def __init__(self, max_positions: int = config.MAX_POSITIONS):
        self.max_positions = max_positions

    def select(self, date, rs_ratio, rs_momentum, quadrants, prices, current_positions):
        leading = quadrants[quadrants == Quadrant.LEADING]
        if leading.empty:
            return []
        return rs_ratio[leading.index].nlargest(self.max_positions).index.tolist()


class MomentumRotationStrategy(BaseStrategy):
    """Top-N by composite score = (RS-Ratio-100)+(RS-Momentum-100) in Leading+Improving."""

    def __init__(self, max_positions: int = config.MAX_POSITIONS):
        self.max_positions = max_positions

    def select(self, date, rs_ratio, rs_momentum, quadrants, prices, current_positions):
        eligible = quadrants[quadrants.isin([Quadrant.LEADING, Quadrant.IMPROVING])]
        if eligible.empty:
            return []
        score = (rs_ratio[eligible.index] - 100) + (rs_momentum[eligible.index] - 100)
        return score.nlargest(self.max_positions).index.tolist()


class CustomStrategy(BaseStrategy):
    """Skeleton for your own rules. Fill in the select() method."""

    def select(self, date, rs_ratio, rs_momentum, quadrants, prices, current_positions):
        candidates = [
            sym for sym in quadrants.index
            if quadrants[sym] == Quadrant.LEADING and rs_ratio[sym] > 102
        ]
        return candidates[: config.MAX_POSITIONS]


# ── Improved strategies ───────────────────────────────────────────────────────

class EarlyRotationStrategy(BaseStrategy):
    """
    Front-runs the consensus Leading trade by entering when a sector freshly
    rotates INTO Improving from any other quadrant.  Holds through Leading.
    Exits only when the sector enters Weakening or Lagging.
    Ranked by RS-Momentum (momentum drives early-stage moves).
    """

    def __init__(self, max_positions: int = config.MAX_POSITIONS):
        self.max_positions = max_positions
        self._prev_quadrants: pd.Series | None = None

    def select(self, date, rs_ratio, rs_momentum, quadrants, prices, current_positions):
        # Keep positions still riding Improving or Leading
        hold = [
            s for s in current_positions
            if s in quadrants.index
            and quadrants[s] in (Quadrant.IMPROVING, Quadrant.LEADING)
        ]

        # Find sectors freshly entering Improving this bar
        if self._prev_quadrants is not None:
            fresh = [
                s for s in quadrants.index
                if quadrants[s] == Quadrant.IMPROVING
                and s in self._prev_quadrants.index
                and self._prev_quadrants[s] != Quadrant.IMPROVING
            ]
        else:
            fresh = list(quadrants[quadrants == Quadrant.IMPROVING].index)

        self._prev_quadrants = quadrants.copy()

        candidates = list(dict.fromkeys(hold + fresh))
        if not candidates:
            return []
        common = [s for s in candidates if s in rs_momentum.index]
        if not common:
            return candidates[: self.max_positions]
        return rs_momentum[common].nlargest(self.max_positions).index.tolist()


class RegimeFilteredStrategy(BaseStrategy):
    """
    Leading-only strategy that goes fully to cash when SPY is below its
    10-week MA — sidesteps broad bear markets where sector rotation fails.
    """

    def __init__(
        self,
        benchmark: pd.Series,
        ma_period: int = 10,
        max_positions: int = config.MAX_POSITIONS,
    ):
        self.max_positions = max_positions
        self._spy_price    = benchmark
        self._spy_ma       = benchmark.rolling(ma_period, min_periods=1).mean()

    def select(self, date, rs_ratio, rs_momentum, quadrants, prices, current_positions):
        try:
            if float(self._spy_price.loc[date]) < float(self._spy_ma.loc[date]):
                return []
        except (KeyError, TypeError):
            pass

        leading = quadrants[quadrants == Quadrant.LEADING]
        if leading.empty:
            return []
        return rs_ratio[leading.index].nlargest(self.max_positions).index.tolist()


class ConfirmationStrategy(BaseStrategy):
    """
    Leading-entry with a 2-bar confirmation filter.  A sector must appear in
    Leading for 2 consecutive rebalance bars before a position is opened,
    reducing false-breakout whipsaws.
    """

    def __init__(self, required_bars: int = 2, max_positions: int = config.MAX_POSITIONS):
        self.required_bars  = required_bars
        self.max_positions  = max_positions
        self._consecutive: dict[str, int] = {}

    def select(self, date, rs_ratio, rs_momentum, quadrants, prices, current_positions):
        leading_syms = set(quadrants[quadrants == Quadrant.LEADING].index)

        # Reset count for any symbol that left Leading; increment those still in it
        for sym in list(self._consecutive):
            if sym not in leading_syms:
                del self._consecutive[sym]
        for sym in leading_syms:
            self._consecutive[sym] = self._consecutive.get(sym, 0) + 1

        confirmed = [s for s in leading_syms
                     if self._consecutive.get(s, 0) >= self.required_bars]

        if not confirmed:
            # Hold existing positions still in Leading while confirmation builds
            return [s for s in current_positions if s in leading_syms][: self.max_positions]

        return rs_ratio[confirmed].nlargest(self.max_positions).index.tolist()


class ScoreWeightedStrategy(BaseStrategy):
    """
    Leading + Improving, with capital allocated proportionally to each
    symbol's composite RRG score (RS-Ratio-100)+(RS-Momentum-100).
    Higher-conviction signals receive larger position sizes.
    """

    def __init__(self, max_positions: int = config.MAX_POSITIONS):
        self.max_positions = max_positions

    def select(self, date, rs_ratio, rs_momentum, quadrants, prices, current_positions):
        eligible = quadrants[quadrants.isin([Quadrant.LEADING, Quadrant.IMPROVING])]
        if eligible.empty:
            return []
        score = (rs_ratio[eligible.index] - 100) + (rs_momentum[eligible.index] - 100)
        return score.nlargest(self.max_positions).index.tolist()

    def get_weights(self, symbols, rs_ratio, rs_momentum) -> dict[str, float]:
        if not symbols:
            return {}
        raw = {
            s: (float(rs_ratio.get(s, 100)) - 100) + (float(rs_momentum.get(s, 100)) - 100)
            for s in symbols
        }
        # Shift so minimum weight = 0.01 (preserves relative ordering)
        min_v   = min(raw.values())
        shifted = {s: v - min_v + 0.01 for s, v in raw.items()}
        total   = sum(shifted.values())
        return {s: v / total for s, v in shifted.items()}


class MomentumAccelerationStrategy(BaseStrategy):
    """
    Leading quadrant only, but exits any sector where RS-Momentum is declining
    bar-over-bar (second derivative < 0) — avoids holding toppy sectors that
    are still in Leading but already rolling over.
    """

    def __init__(self, max_positions: int = config.MAX_POSITIONS):
        self.max_positions  = max_positions
        self._prev_momentum: pd.Series | None = None

    def select(self, date, rs_ratio, rs_momentum, quadrants, prices, current_positions):
        leading = quadrants[quadrants == Quadrant.LEADING]

        if self._prev_momentum is not None and not leading.empty:
            eligible = [
                s for s in leading.index
                if float(rs_momentum.get(s, 100)) >= float(self._prev_momentum.get(s, 100))
            ]
        else:
            eligible = list(leading.index)

        self._prev_momentum = rs_momentum.copy()

        if not eligible:
            return []
        return rs_ratio[eligible].nlargest(self.max_positions).index.tolist()
