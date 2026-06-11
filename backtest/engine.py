"""
Event-driven backtest engine (weekly rebalance, long-only, equal-weight).

Execution lag: signals generated at bar T are executed at bar T+1 prices,
eliminating same-bar look-ahead bias.
"""
from __future__ import annotations

import warnings
import pandas as pd
import numpy as np

import config
from rrg.calculator import compute_rrg
from rrg.quadrant import classify_frame
from strategy.base import BaseStrategy


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rebalance_dates(index: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    """Snap a pandas date_range at `freq` to the nearest available bar in index."""
    try:
        rebal = pd.date_range(index[0], index[-1], freq=freq)
    except ValueError:
        # For intraday freq strings like '1h' that aren't valid DateOffset aliases
        rebal = index  # rebalance every bar for intraday

    snapped = []
    for d in rebal:
        pos = index.searchsorted(d, side="left")
        if pos < len(index):
            snapped.append(index[pos])
    return pd.DatetimeIndex(sorted(set(snapped)))


def _benchmark_metrics(benchmark: pd.Series, equity_index: pd.DatetimeIndex) -> dict:
    """Compute SPY buy-and-hold metrics aligned to the strategy equity index."""
    bm = benchmark.reindex(equity_index).ffill().dropna()
    if bm.empty or len(bm) < 2:
        return {}
    rets  = bm.pct_change().dropna()
    total = bm.iloc[-1] / bm.iloc[0] - 1
    years = (bm.index[-1] - bm.index[0]).days / 365.25
    cagr  = (1 + total) ** (1 / years) - 1 if years > 0 else np.nan
    vol   = rets.std() * np.sqrt(52)
    sharpe = (rets.mean() * 52) / vol if vol > 0 else np.nan
    dd    = (bm / bm.cummax() - 1).min()
    return {
        "BM Total Return":    f"{total:.1%}",
        "BM CAGR":            f"{cagr:.1%}",
        "BM Ann. Volatility": f"{vol:.1%}",
        "BM Sharpe Ratio":    f"{sharpe:.2f}",
        "BM Max Drawdown":    f"{dd:.1%}",
    }


# ── Public API ────────────────────────────────────────────────────────────────

def run(
    universe: pd.DataFrame,
    benchmark: pd.Series,
    strategy: BaseStrategy,
    initial_capital: float = config.INITIAL_CAPITAL,
    commission_pct: float = config.COMMISSION_PCT,
    rebalance_freq: str = config.REBALANCE_FREQ,
    timeframe: str = config.DEFAULT_TIMEFRAME,
    _precomputed_rrg: tuple | None = None,
) -> dict:
    """
    Run the backtest.

    Returns a dict with:
        equity      – pd.Series of portfolio value
        trades      – pd.DataFrame of trade records
        positions   – pd.DataFrame of held symbols at each rebalance
        rs_ratio    – pd.DataFrame
        rs_momentum – pd.DataFrame
        quadrants   – pd.DataFrame
    """
    if _precomputed_rrg is not None:
        rs_ratio, rs_momentum, quadrants = _precomputed_rrg
    else:
        tf_cfg = config.TIMEFRAMES[timeframe]
        rs_ratio, rs_momentum = compute_rrg(
            universe, benchmark,
            ratio_period=tf_cfg["ratio_period"],
            momentum_period=tf_cfg["momentum_period"],
            timeframe=timeframe,
        )
        quadrants = classify_frame(rs_ratio, rs_momentum)

    prices = universe.reindex(rs_ratio.index).ffill()
    rebal_dates = _rebalance_dates(prices.index, rebalance_freq)

    cash = initial_capital
    holdings: dict[str, float] = {}
    equity_records: list[tuple]  = []
    trade_records:  list[dict]   = []
    position_records: list[dict] = []

    price_arr = prices.values
    sym_list  = list(prices.columns)
    sym_idx   = {s: i for i, s in enumerate(sym_list)}   # O(1) column lookup
    rebal_set = set(rebal_dates)

    for i, date in enumerate(prices.index):
        row_prices = price_arr[i]

        port_value = cash + sum(
            shares * row_prices[sym_idx[sym]]
            for sym, shares in holdings.items()
            if sym in sym_idx
        )
        equity_records.append((date, port_value))

        if date not in rebal_set:
            continue

        # ── Execution-lag: use next bar's prices for all orders ──────────────
        exec_idx = i + 1
        if exec_idx >= len(prices):
            continue   # no next bar to execute on; skip last rebalance date

        exec_prices_row = price_arr[exec_idx]

        def _exec_price(sym: str, _ep=exec_prices_row, _si=sym_idx) -> float:
            j = _si.get(sym, -1)
            return float(_ep[j]) if j >= 0 else np.nan

        current_row_ratio = rs_ratio.loc[date]
        current_row_mom   = rs_momentum.loc[date]
        current_row_quad  = quadrants.loc[date]
        current_row_price = prices.loc[date]   # for strategy context only
        current_syms      = list(holdings.keys())

        target_syms = strategy.select(
            date=date,
            rs_ratio=current_row_ratio,
            rs_momentum=current_row_mom,
            quadrants=current_row_quad,
            prices=current_row_price,
            current_positions=current_syms,
        )

        position_records.append({"date": date, "symbols": target_syms})

        # Sell positions not in target (at next bar price)
        to_sell = [s for s in current_syms if s not in target_syms]
        for sym in to_sell:
            shares = holdings.pop(sym)
            price  = _exec_price(sym)
            if np.isnan(price):
                continue
            proceeds = shares * price * (1 - commission_pct)
            cash += proceeds
            trade_records.append({
                "date": date, "symbol": sym, "action": "SELL",
                "shares": round(shares, 6), "price": price,
                "value": round(proceeds, 2),
            })

        # Buy new positions at next bar price (equal-weight on total target)
        to_buy = [s for s in target_syms if s not in holdings]
        if to_buy and target_syms:
            alloc_per_sym = cash / len(target_syms)
            for sym in to_buy:
                price = _exec_price(sym)
                if np.isnan(price) or price <= 0:
                    continue
                cost_per_share = price * (1 + commission_pct)
                shares = alloc_per_sym / cost_per_share
                holdings[sym] = shares
                cash -= shares * cost_per_share
                trade_records.append({
                    "date": date, "symbol": sym, "action": "BUY",
                    "shares": round(shares, 6), "price": price,
                    "value": round(shares * price, 2),
                })

    equity    = pd.Series({d: v for d, v in equity_records}, name="equity")
    trades    = pd.DataFrame(trade_records)
    positions = pd.DataFrame(position_records)

    return {
        "equity":      equity,
        "trades":      trades,
        "positions":   positions,
        "rs_ratio":    rs_ratio,
        "rs_momentum": rs_momentum,
        "quadrants":   quadrants,
    }


def performance_summary(
    equity: pd.Series,
    benchmark: pd.Series | None = None,
    num_trades: int = 0,
) -> pd.Series:
    """
    Key performance metrics from an equity curve.
    If benchmark is provided, appends side-by-side SPY buy-and-hold metrics.
    Warns when the backtest period is short or trade count is low.
    """
    returns = equity.pct_change().dropna()
    total   = equity.iloc[-1] / equity.iloc[0] - 1
    years   = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr    = (1 + total) ** (1 / years) - 1 if years > 0 else np.nan
    vol     = returns.std() * np.sqrt(52)
    sharpe  = (returns.mean() * 52) / vol if vol > 0 else np.nan
    max_dd  = (equity / equity.cummax() - 1).min()

    if years < 3:
        warnings.warn(
            f"Backtest covers only {years:.1f} years (< 3). "
            "Performance metrics may not be statistically meaningful.",
            stacklevel=2,
        )
    if num_trades < 30:
        warnings.warn(
            f"Only {num_trades} trades executed (< 30). "
            "Results may not be reliable.",
            stacklevel=2,
        )

    metrics: dict[str, str | int] = {
        "Total Return":    f"{total:.1%}",
        "CAGR":            f"{cagr:.1%}",
        "Ann. Volatility": f"{vol:.1%}",
        "Sharpe Ratio":    f"{sharpe:.2f}",
        "Max Drawdown":    f"{max_dd:.1%}",
        "Num Trades":      num_trades,
    }

    if benchmark is not None:
        metrics.update(_benchmark_metrics(benchmark, equity.index))

    return pd.Series(metrics)
