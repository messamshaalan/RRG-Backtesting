"""
Central configuration for the RRG backtesting project.
Edit this file to change the universe, benchmark, and RRG parameters.
"""
from __future__ import annotations

import datetime as _dt

# ── Universe ─────────────────────────────────────────────────────────────────
BENCHMARK = "SPY"

SYMBOLS = [
    "XLK",   # Technology
    "XLF",   # Financials
    "XLV",   # Health Care
    "XLE",   # Energy
    "XLI",   # Industrials
    "XLY",   # Consumer Discretionary
    "XLP",   # Consumer Staples
    "XLB",   # Materials
    "XLRE",  # Real Estate
    "XLU",   # Utilities
    "XLC",   # Communication Services
]

SECTOR_NAMES: dict[str, str] = {
    "XLK":  "Technology",
    "XLF":  "Financials",
    "XLV":  "Health Care",
    "XLE":  "Energy",
    "XLI":  "Industrials",
    "XLY":  "Cons. Discretionary",
    "XLP":  "Cons. Staples",
    "XLB":  "Materials",
    "XLRE": "Real Estate",
    "XLU":  "Utilities",
    "XLC":  "Communication",
    "SPY":  "S&P 500 (Benchmark)",
}

# ── Data ─────────────────────────────────────────────────────────────────────
START_DATE = "2015-01-01"
END_DATE   = _dt.date.today().strftime("%Y-%m-%d")
PRICE_COL  = "Close"

# ── Per-Timeframe RRG Parameters ─────────────────────────────────────────────
# Each entry: interval → yfinance interval string, plus RRG computation windows.
# Shorter timeframes use tighter windows to stay responsive.
# 1H note: yfinance limits intraday history to the last 730 calendar days.

TIMEFRAMES: dict[str, dict] = {
    "1h": {
        "label":            "1 Hour",
        "interval":         "1h",
        "ratio_period":     10,     # WMA period for RS-Ratio double-smoothing
        "momentum_period":  10,     # lookback bars for RS-Momentum ROC
        "trail_bars":       14,     # tail length on RRG chart
        "rebalance_freq":   "1h",
        "max_history_days": 729,    # yfinance hard cap for 1H data
    },
    "1d": {
        "label":            "Daily",
        "interval":         "1d",
        "ratio_period":     10,
        "momentum_period":  10,
        "trail_bars":       14,
        "rebalance_freq":   "W-FRI",
        "max_history_days": None,
    },
    "1wk": {
        "label":            "Weekly",
        "interval":         "1wk",
        "ratio_period":     10,
        "momentum_period":  10,
        "trail_bars":       12,
        "rebalance_freq":   "W-FRI",
        "max_history_days": None,
    },
}

DEFAULT_TIMEFRAME = "1wk"

# ── RRG Centre ────────────────────────────────────────────────────────────────
CENTER = 100.0

# ── Rebalance (weekly CLI backtest) ──────────────────────────────────────────
REBALANCE_FREQ = "W-FRI"

# ── Backtest ─────────────────────────────────────────────────────────────────
INITIAL_CAPITAL   = 100_000.0
COMMISSION_PCT    = 0.001    # 0.1 % per trade (one-way)
MAX_POSITIONS     = 5
POSITION_SIZE_PCT = 0.20

# ── Output ────────────────────────────────────────────────────────────────────
OUTPUT_DIR = "output"

# ── Dashboard ────────────────────────────────────────────────────────────────
DASH_PORT  = 8050
DASH_DEBUG = True
