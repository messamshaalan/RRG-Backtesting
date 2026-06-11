"""
Base strategy interface. Subclass this to implement your own RRG-based rules.
"""
from abc import ABC, abstractmethod
import pandas as pd


class BaseStrategy(ABC):
    """
    At each rebalance date, select() receives the current RRG snapshot and
    must return the list of symbols to hold.

    Parameters passed to select():
        date         – current rebalance date
        rs_ratio     – pd.Series(symbol → RS-Ratio value)
        rs_momentum  – pd.Series(symbol → RS-Momentum value)
        quadrants    – pd.Series(symbol → quadrant string)
        prices       – pd.Series(symbol → latest close price)
        current_pos  – list of symbols currently held

    Returns:
        list of symbols to hold after this rebalance (empty = all cash)
    """

    @abstractmethod
    def select(
        self,
        date: pd.Timestamp,
        rs_ratio: pd.Series,
        rs_momentum: pd.Series,
        quadrants: pd.Series,
        prices: pd.Series,
        current_positions: list[str],
    ) -> list[str]:
        ...
