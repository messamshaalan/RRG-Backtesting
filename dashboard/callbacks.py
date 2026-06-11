"""
Dash callbacks: wire sidebar controls → data stores → chart components.

Data flow:
  1. tf-selector / symbol-filter / refresh-btn  →  store-* (heavy compute, runs once per TF change)
  2. store-*  →  charts (fast render from cached data)
"""
from __future__ import annotations

import json
import warnings

import pandas as pd
from dash import Input, Output, State, callback, no_update
from dash.exceptions import PreventUpdate

import config
from data.fetcher import load_all
from rrg.calculator import compute_rrg
from rrg.quadrant import classify_frame
from backtest.quadrant_study import run_study, summary_table
from analysis.holding_time import compute_streaks, compute_all_timeframes
from dashboard.components.rrg_chart import build_rrg_figure, build_symbol_table
from dashboard.components.equity_panel import build_equity_figure
from dashboard.components.stats_cards import build_stats_row, build_comparison_table
from dashboard.components.holding_panel import build_holding_heatmap, build_holding_bar_chart


# ── In-process cache (avoids redundant computation within a session) ──────────
# Key: (timeframe, symbols_tuple) → 8-element output tuple returned by the callback.
_cache: dict = {}
_last_refresh_clicks: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Callback 1: Run data load + backtest when timeframe or refresh changes
# ─────────────────────────────────────────────────────────────────────────────
def register_callbacks(app):  # noqa: C901

    @app.callback(
        Output("store-rs-ratio",      "data"),
        Output("store-rs-momentum",   "data"),
        Output("store-quadrants",     "data"),
        Output("store-benchmark",     "data"),
        Output("store-date-list",     "data"),
        Output("store-study-results", "data"),
        Output("store-streaks",       "data"),
        Output("data-status",         "children"),
        Input("tf-selector",          "value"),
        Input("refresh-btn",          "n_clicks"),
        State("symbol-filter",        "value"),
        prevent_initial_call=False,
    )
    def load_and_compute(timeframe: str, _refresh_clicks, symbol_filter: list[str]):
        global _last_refresh_clicks, _cache

        # Only treat as a forced refresh when the button was *just* clicked
        clicks_now    = int(_refresh_clicks or 0)
        force_refresh = clicks_now > _last_refresh_clicks
        _last_refresh_clicks = clicks_now

        symbols_key = tuple(sorted(symbol_filter or config.SYMBOLS))
        cache_key   = (timeframe, symbols_key)

        if not force_refresh and cache_key in _cache:
            return _cache[cache_key]

        try:
            universe_full, benchmark = load_all(interval=timeframe, force_refresh=force_refresh)

            # Filter to user-selected symbols
            available = [s for s in (symbol_filter or config.SYMBOLS) if s in universe_full.columns]
            universe  = universe_full[available]

            tf_cfg = config.TIMEFRAMES[timeframe]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                rs_ratio, rs_momentum = compute_rrg(
                    universe, benchmark,
                    ratio_period=tf_cfg["ratio_period"],
                    momentum_period=tf_cfg["momentum_period"],
                    timeframe=timeframe,
                )
            quadrants = classify_frame(rs_ratio, rs_momentum)

            # Pass precomputed RRG so run_study doesn't recompute it 4x (once per strategy)
            precomp = {timeframe: (universe, benchmark, rs_ratio, rs_momentum, quadrants)}
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                study = run_study(
                    timeframes=[timeframe],
                    force_refresh=False,
                    precomputed=precomp,
                )

            # Serialise study results (only summary + equity, not full DFs)
            study_serial: dict = {}
            for (tf, label), res in study.items():
                key = f"{tf}|{label}"
                study_serial[key] = {
                    "summary":      res["summary"].to_dict(),
                    "equity_dates": [str(d) for d in res["equity"].index],
                    "equity_vals":  res["equity"].tolist(),
                }

            # Holding time streaks
            streaks_df     = compute_streaks(quadrants)
            streaks_serial = streaks_df.astype(str).to_dict("records")

            status = (
                f"Loaded {len(available)} sectors x {len(rs_ratio)} bars "
                f"({rs_ratio.index[0].strftime('%Y-%m-%d')} to {rs_ratio.index[-1].strftime('%Y-%m-%d')})"
            )

            output = (
                rs_ratio.to_json(date_format="iso"),
                rs_momentum.to_json(date_format="iso"),
                quadrants.to_json(date_format="iso"),
                benchmark.to_json(date_format="iso"),
                [str(d) for d in rs_ratio.index],
                study_serial,
                streaks_serial,
                status,
            )
            _cache[cache_key] = output
            return output

        except Exception as exc:
            err_msg = f"Error: {exc}"
            empty = "{}"
            return empty, empty, empty, empty, [], {}, [], err_msg


    # ── Date slider marks ───────────────────────────────────────────────────
    @app.callback(
        Output("date-slider", "max"),
        Output("date-slider", "value"),
        Output("date-slider", "marks"),
        Output("current-date-label", "children"),
        Input("store-date-list", "data"),
        Input("date-slider", "value"),
    )
    def update_date_slider(date_list: list[str], slider_val: int):
        if not date_list:
            raise PreventUpdate
        n = len(date_list)
        last_idx = n - 1
        marks = {}
        # Show ~6 evenly-spaced marks
        step = max(1, n // 6)
        for i in range(0, n, step):
            marks[i] = date_list[i][:10]
        marks[last_idx] = date_list[last_idx][:10]

        cur_val = min(slider_val if slider_val is not None else last_idx, last_idx)
        label   = f"Date: {date_list[cur_val][:10]}"
        return last_idx, cur_val, marks, label


    # ── RRG chart + symbol table ────────────────────────────────────────────
    @app.callback(
        Output("rrg-graph",         "figure"),
        Output("rrg-symbol-table",  "children"),
        Input("store-rs-ratio",    "data"),
        Input("store-rs-momentum", "data"),
        Input("store-quadrants",   "data"),
        Input("date-slider",       "value"),
        Input("trail-slider",      "value"),
        Input("animate-toggle",    "value"),
    )
    def update_rrg(ratio_json, mom_json, quad_json, date_idx, trail_bars, animate_val):
        if not ratio_json or ratio_json == "{}":
            raise PreventUpdate
        rs_ratio    = pd.read_json(ratio_json)
        rs_momentum = pd.read_json(mom_json)
        quadrants   = pd.read_json(quad_json)

        rs_ratio.index    = pd.to_datetime(rs_ratio.index)
        rs_momentum.index = pd.to_datetime(rs_momentum.index)
        quadrants.index   = pd.to_datetime(quadrants.index)

        if rs_ratio.empty:
            raise PreventUpdate

        animate = bool(animate_val)
        date    = rs_ratio.index[min(date_idx or len(rs_ratio) - 1, len(rs_ratio) - 1)]
        trail   = int(trail_bars or 10)

        fig   = build_rrg_figure(rs_ratio, rs_momentum, quadrants,
                                  date=date, trail_bars=trail, animate=animate)
        table = build_symbol_table(rs_ratio, rs_momentum, quadrants, date=date)
        return fig, table


    # ── Equity comparison chart ─────────────────────────────────────────────
    @app.callback(
        Output("equity-graph", "figure"),
        Output("stats-cards-container", "children"),
        Output("comparison-table-container", "children"),
        Input("store-study-results", "data"),
        Input("store-benchmark",     "data"),
        Input("tf-selector",         "value"),
    )
    def update_backtest(study_serial, bm_json, timeframe):
        if not study_serial or not bm_json or bm_json == "{}":
            raise PreventUpdate

        benchmark = pd.read_json(bm_json, typ="series")
        benchmark.index = pd.to_datetime(benchmark.index)
        benchmark = benchmark.sort_index()

        # Reconstruct study dict for equity panel
        study_results: dict = {}
        for key_str, val in study_serial.items():
            tf, label = key_str.split("|")
            equity = pd.Series(
                val["equity_vals"],
                index=pd.to_datetime(val["equity_dates"]),
                name="equity",
            )
            study_results[(tf, label)] = {
                "equity":  equity,
                "summary": pd.Series(val["summary"]),
            }

        if not any(tf == timeframe for tf, _ in study_results):
            raise PreventUpdate

        fig   = build_equity_figure(study_results, benchmark, timeframe)
        cards = build_stats_row(study_results, timeframe)
        table = build_comparison_table(study_results, timeframe)
        return fig, cards, table


    # ── Holding time heatmap ────────────────────────────────────────────────
    @app.callback(
        Output("holding-heatmap",    "figure"),
        Output("holding-bar-chart",  "figure"),
        Input("store-streaks",       "data"),
        Input("holding-stat-selector","value"),
        Input("tf-selector",         "value"),
    )
    def update_holding(streaks_records, stat, timeframe):
        if not streaks_records:
            raise PreventUpdate

        raw = pd.DataFrame(streaks_records)
        if raw.empty:
            raise PreventUpdate

        # Rebuild proper dtypes
        streaks = raw.copy()
        streaks["bars"] = pd.to_numeric(streaks["bars"], errors="coerce")

        # For the heatmap we only have the current timeframe's streaks in the store
        streaks_by_tf = {timeframe: streaks}

        heatmap = build_holding_heatmap(streaks_by_tf, stat=stat)
        bar     = build_holding_bar_chart(streaks, timeframe)
        return heatmap, bar
