"""
Visualisation helpers: RRG scatter chart, equity curve, drawdown chart.
"""
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

import config

QUADRANT_COLORS = {
    "Leading":   "#27ae60",   # green
    "Weakening": "#e67e22",   # orange
    "Lagging":   "#e74c3c",   # red
    "Improving": "#3498db",   # blue
}

plt.style.use("seaborn-v0_8-darkgrid")


def rrg_chart(
    rs_ratio: pd.DataFrame,
    rs_momentum: pd.DataFrame,
    quadrants: pd.DataFrame,
    date: pd.Timestamp | None = None,
    trail_periods: int = 5,
    save_path: str | None = None,
) -> plt.Figure:
    """
    RRG scatter chart for a single date (with optional trail).
    date defaults to the latest available date.
    """
    if date is None:
        date = rs_ratio.index[-1]

    idx = rs_ratio.index.get_loc(date)
    start = max(0, idx - trail_periods + 1)
    trail_idx = rs_ratio.index[start : idx + 1]

    fig, ax = plt.subplots(figsize=(9, 8))

    # quadrant background
    c = config.CENTER
    span = 10
    ax.axhline(c, color="white", linewidth=1, alpha=0.6)
    ax.axvline(c, color="white", linewidth=1, alpha=0.6)
    for (xmin, xmax, ymin, ymax), color in [
        ((c, c+span, c, c+span), "#27ae60"),   # Leading (top-right)
        ((c, c+span, c-span, c), "#e67e22"),   # Weakening (bottom-right)
        ((c-span, c, c-span, c), "#e74c3c"),   # Lagging (bottom-left)
        ((c-span, c, c, c+span), "#3498db"),   # Improving (top-left)
    ]:
        ax.fill_between([xmin, xmax], ymin, ymax, color=color, alpha=0.08)

    for sym in rs_ratio.columns:
        x_trail = rs_ratio.loc[trail_idx, sym]
        y_trail = rs_momentum.loc[trail_idx, sym]
        color   = QUADRANT_COLORS.get(quadrants.loc[date, sym], "grey")

        # trail line
        ax.plot(x_trail, y_trail, color=color, linewidth=1.2, alpha=0.5)
        # current dot
        ax.scatter(x_trail.iloc[-1], y_trail.iloc[-1], color=color, s=80, zorder=5)
        ax.annotate(
            sym,
            (x_trail.iloc[-1], y_trail.iloc[-1]),
            textcoords="offset points", xytext=(5, 4),
            fontsize=8, color=color,
        )

    ax.set_xlabel("RS-Ratio", fontsize=11)
    ax.set_ylabel("RS-Momentum", fontsize=11)
    ax.set_title(f"Relative Rotation Graph — {date.date()}", fontsize=13)

    for label, color in QUADRANT_COLORS.items():
        ax.annotate(label, xy=(0.02 if "Lag" in label or "Imp" in label else 0.72,
                               0.92 if "Lead" in label or "Imp" in label else 0.04),
                    xycoords="axes fraction", fontsize=9, color=color, alpha=0.8)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig


def equity_curve(
    equity: pd.Series,
    benchmark_equity: pd.Series | None = None,
    save_path: str | None = None,
) -> plt.Figure:
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                              gridspec_kw={"height_ratios": [3, 1]})

    norm = equity / equity.iloc[0] * 100
    axes[0].plot(norm, label="Strategy", linewidth=1.5, color="#2ecc71")
    if benchmark_equity is not None:
        bnorm = benchmark_equity.reindex(equity.index).ffill()
        bnorm = bnorm / bnorm.iloc[0] * 100
        axes[0].plot(bnorm, label=config.BENCHMARK, linewidth=1.2,
                     color="#95a5a6", linestyle="--")
    axes[0].set_ylabel("Normalised Value (100 = start)")
    axes[0].legend()
    axes[0].set_title("Equity Curve")

    drawdown = equity / equity.cummax() - 1
    axes[1].fill_between(drawdown.index, drawdown, 0, color="#e74c3c", alpha=0.4)
    axes[1].set_ylabel("Drawdown")
    axes[1].set_xlabel("Date")

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig
