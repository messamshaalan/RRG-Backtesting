"""
Holding time heatmap: shows how long each sector ETF stays in each quadrant
before rotating out, across all timeframes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import config
from rrg.quadrant import Quadrant

QUAD_ORDER  = [Quadrant.LEADING, Quadrant.IMPROVING, Quadrant.WEAKENING, Quadrant.LAGGING]
QUAD_COLORS = {
    Quadrant.LEADING:   "#2ecc71",
    Quadrant.IMPROVING: "#3498db",
    Quadrant.WEAKENING: "#f39c12",
    Quadrant.LAGGING:   "#e74c3c",
}
# Heatmap colour scales per quadrant (light→dark of each colour)
COLORSCALES = {
    Quadrant.LEADING:   [[0, "#0d1f15"], [1, "#2ecc71"]],
    Quadrant.IMPROVING: [[0, "#0d1520"], [1, "#3498db"]],
    Quadrant.WEAKENING: [[0, "#1f1a0d"], [1, "#f39c12"]],
    Quadrant.LAGGING:   [[0, "#1f0d0d"], [1, "#e74c3c"]],
}


def build_holding_heatmap(
    streaks_by_tf: dict[str, pd.DataFrame],   # {timeframe_key: streaks_df}
    stat: str = "mean_bars",
    height: int = 500,
) -> go.Figure:
    """
    Build a grouped heatmap showing holding time per (symbol, quadrant) for each timeframe.

    Parameters
    ----------
    streaks_by_tf : output of analysis.holding_time.compute_all_timeframes()
    stat          : which stat to plot — 'mean_bars', 'max_bars', 'median_bars', 'min_bars'
    """
    from analysis.holding_time import holding_heatmap_data

    tf_keys = list(streaks_by_tf.keys())
    n_tf    = len(tf_keys)

    fig = make_subplots(
        rows=1, cols=n_tf,
        subplot_titles=[config.TIMEFRAMES[tf]["label"] for tf in tf_keys],
        horizontal_spacing=0.06,
    )

    for col_idx, tf in enumerate(tf_keys, start=1):
        streaks = streaks_by_tf[tf]
        pivot   = holding_heatmap_data(streaks, stat=stat)
        if pivot.empty:
            continue

        symbols = pivot.index.tolist()
        quads   = [q for q in QUAD_ORDER if q in pivot.columns]

        z    = pivot[quads].values
        text = np.where(np.isnan(z.astype(float)), "", np.round(z.astype(float), 1).astype(str))

        fig.add_trace(go.Heatmap(
            z=z,
            x=quads,
            y=[config.SECTOR_NAMES.get(s, s) for s in symbols],
            text=text,
            texttemplate="%{text}",
            textfont=dict(size=10, color="#e8eaf0"),
            colorscale=[
                [i / (len(quads) - 1), QUAD_COLORS[q]]
                for i, q in enumerate(quads)
            ] if len(quads) > 1 else [[0, "#2ecc71"], [1, "#2ecc71"]],
            showscale=False,
            hovertemplate="<b>%{y}</b><br>%{x}: %{z:.1f} bars<extra></extra>",
            xgap=2, ygap=2,
        ), row=1, col=col_idx)

        fig.update_xaxes(
            tickfont=dict(size=9, color="#8b92a8"),
            tickangle=-20,
            row=1, col=col_idx,
        )
        fig.update_yaxes(
            tickfont=dict(size=9, color="#8b92a8"),
            showticklabels=(col_idx == 1),
            row=1, col=col_idx,
        )

    stat_labels = {
        "mean_bars": "Average", "max_bars": "Maximum",
        "median_bars": "Median", "min_bars": "Minimum",
    }
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(21,24,32,1)",
        font=dict(family="Inter, sans-serif", color="#8b92a8"),
        height=height,
        margin=dict(l=120, r=20, t=60, b=60),
        title=dict(
            text=f"{stat_labels.get(stat,'Holding Time')} Bars in Quadrant Before Rotation",
            font=dict(size=14, color="#e8eaf0"),
            x=0.01, xanchor="left",
        ),
    )
    return fig


def build_holding_bar_chart(
    streaks: pd.DataFrame,
    timeframe: str,
    height: int = 380,
) -> go.Figure:
    """
    Bar chart: distribution of streak lengths per quadrant for a single timeframe.
    Shows min / median / max as grouped bars.
    """
    from analysis.holding_time import overall_summary

    summary = overall_summary(streaks)
    if summary.empty:
        return go.Figure()

    quads    = [q for q in QUAD_ORDER if q in summary.index]
    tf_label = config.TIMEFRAMES[timeframe]["label"]

    fig = go.Figure()
    for metric, dash in [("min_bars", "dot"), ("median_bars", "solid"), ("max_bars", "dash")]:
        vals = [float(summary.loc[q, metric]) if q in summary.index else 0 for q in quads]
        fig.add_trace(go.Bar(
            name=metric.replace("_bars", "").capitalize(),
            x=quads,
            y=vals,
            marker_color=[QUAD_COLORS[q] for q in quads],
            marker_opacity=0.4 if metric == "min_bars" else (0.75 if metric == "median_bars" else 1.0),
            hovertemplate="%{x}: %{y:.1f} bars<extra></extra>",
        ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(21,24,32,1)",
        font=dict(family="Inter, sans-serif", color="#8b92a8"),
        barmode="group",
        height=height,
        margin=dict(l=40, r=20, t=50, b=40),
        title=dict(
            text=f"Quadrant Holding Duration — {tf_label}",
            font=dict(size=13, color="#e8eaf0"),
            x=0.01, xanchor="left",
        ),
        legend=dict(
            bgcolor="rgba(21,24,32,0.8)",
            bordercolor="rgba(42,47,69,0.8)",
            borderwidth=1,
            font=dict(size=10),
            orientation="h", x=0, y=1.12,
        ),
        xaxis=dict(gridcolor="rgba(42,47,69,0.4)"),
        yaxis=dict(title="Bars", gridcolor="rgba(42,47,69,0.4)"),
    )
    return fig
