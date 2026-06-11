"""
Ready-to-use example strategies.  Use these as templates for your custom rules.
"""
import pandas as pd

import config
from rrg.quadrant import Quadrant
from strategy.base import BaseStrategy


class LeadingOnlyStrategy(BaseStrategy):
    """
    Hold the top-N symbols in the Leading quadrant, ranked by RS-Ratio.
    Exit any holding that leaves Leading (enters Weakening or Lagging).
    """

    def __init__(self, max_positions: int = config.MAX_POSITIONS):
        self.max_positions = max_positions

    def select(self, date, rs_ratio, rs_momentum, quadrants, prices, current_positions):
        leading = quadrants[quadrants == Quadrant.LEADING]
        if leading.empty:
            return []
        ranked = rs_ratio[leading.index].nlargest(self.max_positions)
        return ranked.index.tolist()


class MomentumRotationStrategy(BaseStrategy):
    """
    Each week pick the top-N symbols ranked by a composite score:
        score = (RS-Ratio - 100) + (RS-Momentum - 100)
    Only considers Leading and Improving quadrants.
    """

    def __init__(self, max_positions: int = config.MAX_POSITIONS):
        self.max_positions = max_positions

    def select(self, date, rs_ratio, rs_momentum, quadrants, prices, current_positions):
        eligible = quadrants[quadrants.isin([Quadrant.LEADING, Quadrant.IMPROVING])]
        if eligible.empty:
            return []
        score = (rs_ratio[eligible.index] - 100) + (rs_momentum[eligible.index] - 100)
        return score.nlargest(self.max_positions).index.tolist()


class CustomStrategy(BaseStrategy):
    """
    Skeleton for your own rules.  Fill in the select() method.
    """

    def select(self, date, rs_ratio, rs_momentum, quadrants, prices, current_positions):
        # ── YOUR LOGIC HERE ───────────────────────────────────────────────────
        # Example: hold anything in Leading with RS-Ratio > 102
        candidates = [
            sym for sym in quadrants.index
            if quadrants[sym] == Quadrant.LEADING and rs_ratio[sym] > 102
        ]
        return candidates[: config.MAX_POSITIONS]
