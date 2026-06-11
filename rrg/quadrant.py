"""
Classifies each symbol into one of the four RRG quadrants each period.

                   RS-Momentum > 100
                         │
          IMPROVING       │      LEADING
   (low ratio, rising)    │  (high ratio, rising)
                          │
  ────────────────────────┼──────────────────────── RS-Ratio > 100
                          │
          LAGGING         │      WEAKENING
   (low ratio, falling)   │  (high ratio, falling)
                          │
                   RS-Momentum < 100
"""
import pandas as pd

CENTER = 100.0


class Quadrant:
    LEADING   = "Leading"
    WEAKENING = "Weakening"
    LAGGING   = "Lagging"
    IMPROVING = "Improving"


def classify(rs_ratio: float, rs_momentum: float) -> str:
    above_ratio    = rs_ratio    >= CENTER
    above_momentum = rs_momentum >= CENTER
    if above_ratio and above_momentum:
        return Quadrant.LEADING
    if above_ratio and not above_momentum:
        return Quadrant.WEAKENING
    if not above_ratio and above_momentum:
        return Quadrant.IMPROVING
    return Quadrant.LAGGING


def classify_frame(
    rs_ratio_df: pd.DataFrame,
    rs_momentum_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Returns a DataFrame of quadrant strings, same shape as inputs.
    """
    result = pd.DataFrame(index=rs_ratio_df.index, columns=rs_ratio_df.columns, dtype=str)
    for col in rs_ratio_df.columns:
        result[col] = [
            classify(r, m)
            for r, m in zip(rs_ratio_df[col], rs_momentum_df[col])
        ]
    return result


def leading_symbols(quadrants_row: pd.Series) -> list[str]:
    return [sym for sym, q in quadrants_row.items() if q == Quadrant.LEADING]


def improving_symbols(quadrants_row: pd.Series) -> list[str]:
    return [sym for sym, q in quadrants_row.items() if q == Quadrant.IMPROVING]
