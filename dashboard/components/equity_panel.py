"""
Equity comparison panel: overlays Leading / Improving / Weakening / Lagging
entry strategies on one chart alongside the SPY buy-and-hold benchmark.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

import config

STRATEGY_COLORS = {
    "Leading":   "#2ecc71",
    "Improving": "#3498db",
    "Weakening": "#f39c12",
    "Lagging":   "#e74c3c",
}
SPY_COLOR  = "#8b92a8"
DD_ALPHA   = "0.35"


def _normalise(series: pd.Series) -> pd.Series:
    first = series.dropna().iloc[0] if not series.dropna().empty else 1
    return (series / first) * 100


def build_equity_figure(
    study_results: dict,          # {(timeframe, entry_label): engine_result_dict}
    benchmark: pd.Series,
    timeframe: str,
    show_drawdown: bool = True,
    height: int = 500,
) -> go.Figure:
    """Build an equity-curve comparison figure for one timeframe."""
    tf_label = config.TIMEFRAMES[timeframe]["label"]

    equity_traces:   list[go.BaseTraceType] = []
    drawdown_traces: list[go.BaseTraceType] = []

    # Benchmark
    ref_equity: pd.Series | None = None
    for (tf, label), res in study_results.items():
        if tf == timeframe:
            ref_equity = res["equity"]
            break

    if ref_equity is not None:
        bm = benchmark.reindex(ref_equity.index).ffill()
        bm_norm = _normalise(bm)
        bm_dd   = (bm / bm.cummax() - 1) * 100

        equity_traces.append(go.Scatter(
            x=bm_norm.index, y=bm_norm.values,
            name=f"SPY (B&H)",
            line=dict(color=SPY_COLOR, width=1.5, dash="dot"),
            hovertemplate="SPY: %{y:.1f}<extra></extra>",
        ))
        drawdown_traces.append(go.Scatter(
            x=bm_dd.index, y=bm_dd.values,
            name="SPY DD",
            line=dict(color=SPY_COLOR, width=1, dash="dot"),
            fill="tozeroy", fillcolor=f"rgba(139,146,168,0.1)",
            showlegend=False,
            hovertemplate="SPY DD: %{y:.1f}%<extra></extra>",
        ))

    # Strategy curves
    for (tf, label), res in study_results.items():
        if tf != timeframe:
            continue
        eq    = res["equity"]
        eq_n  = _normalise(eq)
        dd    = (eq / eq.cummax() - 1) * 100
        color = STRATEGY_COLORS.get(label, "#ffffff")

        equity_traces.append(go.Scatter(
            x=eq_n.index, y=eq_n.values,
            name=label,
            line=dict(color=color, width=2),
            hovertemplate=f"{label}: %{{y:.1f}}<extra></extra>",
        ))
        drawdown_traces.append(go.Scatter(
            x=dd.index, y=dd.values,
            name=f"{label} DD",
            line=dict(color=color, width=1),
            fill="tozeroy",
            fillcolor=f"rgba({','.join(str(int(c,16)) for c in [color[1:3],color[3:5],color[5:7]])},{DD_ALPHA})",
            showlegend=False,
            hovertemplate=f"{label} DD: %{{y:.1f}}%<extra></extra>",
        ))

    if show_drawdown:
        rows, row_heights = 2, [0.68, 0.32]
        from plotly.subplots import make_subplots
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            row_heights=row_heights, vertical_spacing=0.04,
            subplot_titles=["Normalised Equity (100 = start)", "Drawdown (%)"],
        )
        for tr in equity_traces:
            fig.add_trace(tr, row=1, col=1)
        for tr in drawdown_traces:
            fig.add_trace(tr, row=2, col=1)

        fig.update_yaxes(title_text="Value", row=1, col=1,
                         gridcolor="rgba(42,47,69,0.6)", tickfont=dict(size=10))
        fig.update_yaxes(title_text="DD %", row=2, col=1,
                         gridcolor="rgba(42,47,69,0.6)", tickfont=dict(size=10))
        fig.update_xaxes(gridcolor="rgba(42,47,69,0.6)", tickfont=dict(size=10))
    else:
        fig = go.Figure(data=equity_traces)
        fig.update_yaxes(title_text="Value (100 = start)",
                         gridcolor="rgba(42,47,69,0.6)")

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(21,24,32,1)",
        font=dict(family="Inter, sans-serif", color="#8b92a8"),
        height=height,
        margin=dict(l=50, r=20, t=50, b=40),
        title=dict(
            text=f"Entry Quadrant Comparison — {tf_label}",
            font=dict(size=14, color="#e8eaf0"),
            x=0.01, xanchor="left",
        ),
        legend=dict(
            bgcolor="rgba(21,24,32,0.85)",
            bordercolor="rgba(42,47,69,0.8)",
            borderwidth=1,
            font=dict(size=10),
            orientation="h",
            x=0, y=1.08,
        ),
        hovermode="x unified",
    )
    return fig
