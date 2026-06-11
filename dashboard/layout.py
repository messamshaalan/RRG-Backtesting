"""
Full-page dark layout: sidebar + main content area with timeframe tabs.
All Dash component IDs are defined here; callbacks reference these same IDs.
"""
from __future__ import annotations

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

import config

_TF_OPTIONS = [
    {"label": v["label"], "value": k}
    for k, v in config.TIMEFRAMES.items()
]

_STAT_OPTIONS = [
    {"label": "Average bars",  "value": "mean_bars"},
    {"label": "Median bars",   "value": "median_bars"},
    {"label": "Maximum bars",  "value": "max_bars"},
    {"label": "Minimum bars",  "value": "min_bars"},
]


def _empty_fig() -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(21,24,32,1)",
        annotations=[dict(
            text="Loading…", showarrow=False,
            font=dict(size=14, color="#555e7a"),
            xref="paper", yref="paper", x=0.5, y=0.5,
        )],
    )
    return fig


def _sidebar() -> html.Div:
    return html.Div(id="sidebar", children=[
        # Logo
        html.Div(className="sidebar-logo", children=[
            html.Div("RRG", className="sidebar-logo-icon"),
            html.Div([
                html.Div("Sector Radar", className="sidebar-logo-text"),
                html.Div("SPY ETF Dashboard", className="sidebar-logo-sub"),
            ]),
        ]),

        # Timeframe
        html.Div([
            html.Div("Timeframe", className="sidebar-section-label"),
            dcc.RadioItems(
                id="tf-selector",
                options=_TF_OPTIONS,
                value=config.DEFAULT_TIMEFRAME,
                labelStyle={"display": "flex", "alignItems": "center",
                            "gap": "8px", "padding": "6px 0",
                            "cursor": "pointer", "color": "var(--text-secondary)",
                            "fontSize": "0.85rem"},
                inputStyle={"accentColor": "var(--accent)"},
                className="tf-radio",
            ),
        ]),

        # Universe
        html.Div([
            html.Div("Sectors", className="sidebar-section-label"),
            dcc.Checklist(
                id="symbol-filter",
                options=[{"label": f" {s}", "value": s} for s in config.SYMBOLS],
                value=config.SYMBOLS,
                labelStyle={"display": "flex", "alignItems": "center",
                            "gap": "6px", "padding": "4px 0",
                            "cursor": "pointer", "color": "var(--text-secondary)",
                            "fontSize": "0.8rem"},
                inputStyle={"accentColor": "var(--accent)"},
            ),
        ]),

        # RRG trail length
        html.Div([
            html.Div("Trail length (bars)", className="sidebar-section-label"),
            dcc.Slider(
                id="trail-slider",
                min=3, max=26, step=1, value=10,
                marks={3: "3", 10: "10", 26: "26"},
                tooltip={"placement": "bottom", "always_visible": False},
            ),
        ]),

        # Refresh button
        html.Div([
            html.Button("↺ Refresh Data", id="refresh-btn",
                        style={
                            "width": "100%", "padding": "8px",
                            "background": "var(--accent-glow)",
                            "border": "1px solid var(--accent)",
                            "borderRadius": "var(--radius-sm)",
                            "color": "var(--accent)", "cursor": "pointer",
                            "fontSize": "0.8rem", "fontWeight": "600",
                            "marginTop": "4px",
                        }),
        ]),

        # Data status
        html.Div(id="data-status",
                 style={"fontSize": "0.72rem", "color": "var(--text-muted)", "marginTop": "6px"}),

        # Spacer + version
        html.Div(style={"flex": "1"}),
        html.Div("v1.0 · yfinance · Plotly Dash",
                 style={"fontSize": "0.68rem", "color": "var(--text-muted)", "marginTop": "auto"}),
    ])


def _page_header() -> html.Div:
    return html.Div(id="page-header", children=[
        html.Div([
            html.H2("Relative Rotation Graph", style={"margin": 0, "color": "var(--text-primary)"}),
            html.P("SPY Sector ETFs · Quadrant Entry Backtesting",
                   style={"margin": 0, "fontSize": "0.8rem"}),
        ]),
        html.Div([
            html.Span(id="current-date-label",
                      style={"fontSize": "0.8rem", "color": "var(--text-muted)"}),
        ]),
    ])


def _rrg_tab() -> dbc.Tab:
    return dbc.Tab(label="RRG Chart", tab_id="tab-rrg", children=[
        html.Div(style={"padding": "20px 0", "display": "flex", "flexDirection": "column", "gap": "16px"}, children=[

            # Animate toggle + date display
            html.Div(style={"display": "flex", "alignItems": "center", "gap": "16px"}, children=[
                dcc.Checklist(
                    id="animate-toggle",
                    options=[{"label": " Enable animation slider", "value": "on"}],
                    value=[],
                    labelStyle={"color": "var(--text-secondary)", "fontSize": "0.82rem", "cursor": "pointer"},
                    inputStyle={"accentColor": "var(--accent)"},
                ),
                html.Span("Animation may take a few seconds to build.",
                          style={"color": "var(--text-muted)", "fontSize": "0.75rem"}),
            ]),

            # RRG chart + symbol status table
            html.Div(className="chart-card", children=[
                html.Div("Live RRG — Latest Position", className="chart-title"),
                dcc.Loading(type="circle", color="var(--accent)", children=[
                    dcc.Graph(id="rrg-graph", figure=_empty_fig(),
                              config={"displayModeBar": True, "displaylogo": False},
                              style={"borderRadius": "var(--radius-md)"}),
                ]),
                dcc.Loading(type="dot", color="var(--accent)", children=[
                    html.Div(id="rrg-symbol-table"),
                ]),
            ]),

            # Date slider (shown when animation is off — for manual scrubbing)
            html.Div(id="date-slider-container", children=[
                html.Div("Scrub date", className="chart-title"),
                dcc.Slider(id="date-slider", min=0, max=1, step=1, value=0,
                           marks={}, tooltip={"placement": "bottom", "always_visible": True}),
            ], style={"display": "block"}),
        ]),
    ])


def _backtest_tab() -> dbc.Tab:
    return dbc.Tab(label="Backtest", tab_id="tab-backtest", children=[
        html.Div(style={"padding": "20px 0", "display": "flex", "flexDirection": "column", "gap": "20px"}, children=[

            # Stats cards row
            dcc.Loading(type="circle", color="var(--accent)", children=[
                html.Div(id="stats-cards-container", className="chart-card"),
            ]),

            # Equity comparison chart
            html.Div(className="chart-card", children=[
                html.Div("Equity Curve — Entry Quadrant Comparison", className="chart-title"),
                dcc.Loading(type="circle", color="var(--accent)", children=[
                    dcc.Graph(id="equity-graph", figure=_empty_fig(),
                              config={"displayModeBar": True, "displaylogo": False}),
                ]),
            ]),

            # Comparison table
            dcc.Loading(type="circle", color="var(--accent)", children=[
                html.Div(id="comparison-table-container"),
            ]),
        ]),
    ])


def _holding_tab() -> dbc.Tab:
    return dbc.Tab(label="Holding Time", tab_id="tab-holding", children=[
        html.Div(style={"padding": "20px 0", "display": "flex", "flexDirection": "column", "gap": "20px"}, children=[

            # Controls row
            html.Div(style={"display": "flex", "alignItems": "center", "gap": "16px"}, children=[
                html.Span("Stat:", style={"color": "var(--text-secondary)", "fontSize": "0.82rem"}),
                dcc.Dropdown(
                    id="holding-stat-selector",
                    options=_STAT_OPTIONS,
                    value="mean_bars",
                    clearable=False,
                    style={"width": "200px", "fontSize": "0.82rem"},
                ),
            ]),

            # Heatmap
            html.Div(className="chart-card", children=[
                html.Div("Bars Spent in Each Quadrant Before Rotation (All Timeframes)", className="chart-title"),
                dcc.Loading(type="circle", color="var(--accent)", children=[
                    dcc.Graph(id="holding-heatmap", figure=_empty_fig(),
                              config={"displayModeBar": False, "displaylogo": False}),
                ]),
            ]),

            # Bar chart for selected timeframe
            html.Div(className="chart-card", children=[
                html.Div("Holding Duration Distribution (Selected Timeframe)", className="chart-title"),
                dcc.Loading(type="circle", color="var(--accent)", children=[
                    dcc.Graph(id="holding-bar-chart", figure=_empty_fig(),
                              config={"displayModeBar": False, "displaylogo": False}),
                ]),
            ]),
        ]),
    ])


def _main_content() -> html.Div:
    return html.Div(id="main-content", children=[
        _page_header(),

        # Hidden data stores (avoid re-running heavy computations on every callback)
        dcc.Store(id="store-study-results"),    # serialised summary stats
        dcc.Store(id="store-rs-ratio"),         # current timeframe rs_ratio JSON
        dcc.Store(id="store-rs-momentum"),
        dcc.Store(id="store-quadrants"),
        dcc.Store(id="store-benchmark"),
        dcc.Store(id="store-streaks"),          # holding time streaks per tf
        dcc.Store(id="store-date-list"),        # sorted date index as string list

        html.Div(id="page-body", children=[
            dbc.Tabs(id="main-tabs", active_tab="tab-rrg", children=[
                _rrg_tab(),
                _backtest_tab(),
                _holding_tab(),
            ]),
        ]),
    ])


def build_layout() -> html.Div:
    """Return the complete app layout."""
    return html.Div(id="app-shell", children=[
        _sidebar(),
        _main_content(),
    ])
