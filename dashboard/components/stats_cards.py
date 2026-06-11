"""
KPI stat cards and comparison table for each entry strategy.
Returns Dash HTML components — no Plotly figure, pure HTML/CSS layout.
"""
from __future__ import annotations

import pandas as pd
from dash import html

import config

STRATEGY_COLORS = {
    "Leading":   "#2ecc71",
    "Improving": "#3498db",
    "Weakening": "#f39c12",
    "Lagging":   "#e74c3c",
}

METRIC_KEYS = [
    ("Total Return",    "Total Return"),
    ("CAGR",            "CAGR"),
    ("Ann. Volatility", "Ann. Volatility"),
    ("Sharpe Ratio",    "Sharpe Ratio"),
    ("Max Drawdown",    "Max Drawdown"),
    ("Num Trades",      "Num Trades"),
]

BM_METRIC_KEYS = [
    ("BM Total Return", "BM Return"),
    ("BM CAGR",         "BM CAGR"),
    ("BM Sharpe Ratio", "BM Sharpe"),
    ("BM Max Drawdown", "BM Max DD"),
]


def _colour_class(key: str, value: str) -> str:
    """Assign kpi-positive / kpi-negative / kpi-neutral CSS class."""
    try:
        num = float(value.replace("%", ""))
    except (ValueError, AttributeError):
        return "kpi-neutral"
    if key in ("Total Return", "CAGR", "Sharpe Ratio", "BM Total Return", "BM CAGR", "BM Sharpe Ratio"):
        return "kpi-positive" if num >= 0 else "kpi-negative"
    if key in ("Max Drawdown", "Ann. Volatility", "BM Max Drawdown"):
        return "kpi-negative" if num < -15 else "kpi-neutral"
    return "kpi-neutral"


def _kpi_card(label: str, value: str, color_class: str, accent: str) -> html.Div:
    return html.Div(className="kpi-card", style={"borderTopColor": accent, "borderTopWidth": "2px"}, children=[
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className=f"kpi-value {color_class}"),
    ])


def build_stats_row(
    study_results: dict,
    timeframe: str,
) -> html.Div:
    """
    Returns a grid of metric cards for each entry strategy in the given timeframe.
    """
    tf_label = config.TIMEFRAMES[timeframe]["label"]
    cards_by_strategy: list[html.Div] = []

    for label in ["Leading", "Improving", "Weakening", "Lagging"]:
        key = (timeframe, label)
        if key not in study_results:
            continue
        summary = study_results[key]["summary"]
        color   = STRATEGY_COLORS[label]

        metric_cards = []
        for raw_key, display_label in METRIC_KEYS:
            val = summary.get(raw_key, "—")
            metric_cards.append(_kpi_card(
                display_label, str(val),
                _colour_class(raw_key, str(val)), color,
            ))

        cards_by_strategy.append(html.Div([
            html.Div([
                html.Span(className="quadrant-badge",
                          style={"background": f"rgba({','.join(str(int(c,16)) for c in [color[1:3],color[3:5],color[5:7]])},0.12)",
                                 "color": color, "border": f"1px solid {color}",
                                 "borderRadius": "999px", "padding": "2px 12px",
                                 "fontSize": "0.75rem", "fontWeight": "700"},
                          children=label),
            ], style={"marginBottom": "12px"}),
            html.Div(metric_cards, className="kpi-grid"),
        ], style={
            "background": "var(--bg-elevated)",
            "border": "1px solid var(--border)",
            "borderRadius": "var(--radius-md)",
            "padding": "16px",
        }))

    return html.Div([
        html.Div(f"Strategy Comparison — {tf_label}", className="card-header",
                 style={"marginBottom": "16px"}),
        html.Div(cards_by_strategy, style={
            "display": "grid",
            "gridTemplateColumns": "repeat(auto-fit, minmax(260px, 1fr))",
            "gap": "16px",
        }),
    ])


def build_comparison_table(
    study_results: dict,
    timeframe: str,
) -> html.Div:
    """
    Returns an HTML table comparing all strategies for a given timeframe.
    Rows = strategies, Columns = key metrics.
    """
    headers = ["Entry"] + [d for _, d in METRIC_KEYS] + [d for _, d in BM_METRIC_KEYS]

    rows_html = [
        html.Tr([html.Th(h) for h in headers])
    ]

    for label in ["Leading", "Improving", "Weakening", "Lagging"]:
        key = (timeframe, label)
        if key not in study_results:
            continue
        summary = study_results[key]["summary"]
        color   = STRATEGY_COLORS[label]

        cells = [
            html.Td(html.B(label, style={"color": color}))
        ]
        for raw_key, _ in METRIC_KEYS:
            val = summary.get(raw_key, "—")
            cells.append(html.Td(str(val), style={
                "color": _colour_class(raw_key, str(val)).replace(
                    "kpi-positive", "var(--leading)").replace(
                    "kpi-negative", "var(--lagging)").replace(
                    "kpi-neutral", "var(--text-secondary)")
            }))
        for raw_key, _ in BM_METRIC_KEYS:
            val = summary.get(raw_key, "—")
            cells.append(html.Td(str(val), style={"color": "var(--text-muted)"}))

        rows_html.append(html.Tr(cells))

    return html.Div([
        html.Div("Metrics Table", className="card-header"),
        html.Div(
            html.Table(rows_html, className="data-table"),
            style={"overflowX": "auto"},
        ),
    ], className="chart-card", style={"marginTop": "16px"})
