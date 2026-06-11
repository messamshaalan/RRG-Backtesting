#!/usr/bin/env python3
"""
RRG Sector Dashboard — desktop GUI.

Based on RRGPy (github.com/An0n1mity/RRGPy) chart approach.
Uses the correct JdK WMA formula instead of z-score normalisation.
Adds Backtest and Holding Time tabs on top of the RRG chart.

Run:
    python rrg_dashboard.py
"""
from __future__ import annotations

import os
import sys
import threading
import warnings
warnings.filterwarnings("ignore")

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)

import tkinter as tk
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import pandas as pd

try:
    from scipy import interpolate
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

import config
from data.fetcher import load_all
from rrg.calculator import compute_rrg
from rrg.quadrant import classify_frame, Quadrant
from backtest.quadrant_study import run_study
from analysis.holding_time import compute_streaks, overall_summary, streak_summary

# ── Dark theme ────────────────────────────────────────────────────────────────
_BG       = "#0d0f14"
_SURFACE  = "#151820"
_ELEVATED = "#1c2030"
_BORDER   = "#2a2f45"
_ACCENT   = "#4f8ef7"
_TEXT     = "#e8eaf0"
_MUTED    = "#8b92a8"
_C_LEAD   = "#2ecc71"
_C_IMPR   = "#3498db"
_C_WEAK   = "#f39c12"
_C_LAGG   = "#e74c3c"

QUAD_COLORS = {
    Quadrant.LEADING:   _C_LEAD,
    Quadrant.IMPROVING: _C_IMPR,
    Quadrant.WEAKENING: _C_WEAK,
    Quadrant.LAGGING:   _C_LAGG,
}
QUAD_ROW_BG = {
    Quadrant.LEADING:   "#152b1e",
    Quadrant.IMPROVING: "#152130",
    Quadrant.WEAKENING: "#2d2210",
    Quadrant.LAGGING:   "#2d1515",
}
STRATEGY_COLORS = {
    "Leading":   _C_LEAD,
    "Improving": _C_IMPR,
    "Weakening": _C_WEAK,
    "Lagging":   _C_LAGG,
}

plt.rcParams.update({
    "figure.facecolor":  _BG,
    "axes.facecolor":    _SURFACE,
    "axes.edgecolor":    _BORDER,
    "axes.labelcolor":   _MUTED,
    "axes.titlecolor":   _TEXT,
    "xtick.color":       _MUTED,
    "ytick.color":       _MUTED,
    "grid.color":        _BORDER,
    "grid.alpha":        0.5,
    "text.color":        _TEXT,
    "legend.facecolor":  _ELEVATED,
    "legend.edgecolor":  _BORDER,
    "font.family":       "sans-serif",
    "axes.titlesize":    11,
    "axes.labelsize":    9,
})

# ── Constants (match RRGPy defaults) ─────────────────────────────────────────
_TAIL_INIT      = 5
_DOT_TRAIL      = 10    # small trail dot size (s= for scatter)
_DOT_CURRENT    = 60    # large current-position dot


class RRGDashboard:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("RRG Sector Dashboard")
        self.root.geometry("1350x860")
        self.root.configure(bg=_BG)
        self.root.resizable(True, True)

        # ── Runtime state ─────────────────────────────────────────────────────
        self._tf_var      = tk.StringVar(value=config.DEFAULT_TIMEFRAME)
        self._is_playing  = False
        self._tail        = _TAIL_INIT
        self._slider_val  = 0
        self._anim_job: str | None = None

        # ── Data ─────────────────────────────────────────────────────────────
        self.universe:  pd.DataFrame | None = None
        self.benchmark: pd.Series    | None = None
        self.rsr:       pd.DataFrame | None = None   # RS-Ratio
        self.rsm:       pd.DataFrame | None = None   # RS-Momentum
        self.quadrants: pd.DataFrame | None = None
        self.study:     dict         | None = None
        self.streaks:   pd.DataFrame | None = None

        self._build_ui()
        self._load_data()

    # ─────────────────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Top toolbar
        bar = tk.Frame(self.root, bg=_ELEVATED, pady=7, padx=14)
        bar.pack(fill="x", side="top")

        tk.Label(bar, text="RRG Sector Dashboard", bg=_ELEVATED, fg=_TEXT,
                 font=("sans-serif", 13, "bold")).pack(side="left")

        tk.Label(bar, text="  Timeframe:", bg=_ELEVATED, fg=_MUTED,
                 font=("sans-serif", 9)).pack(side="left")
        for tf in config.TIMEFRAMES:
            lbl = config.TIMEFRAMES[tf]["label"]
            tk.Radiobutton(bar, text=lbl, variable=self._tf_var, value=tf,
                           bg=_ELEVATED, fg=_MUTED, selectcolor=_BG,
                           activebackground=_ELEVATED, activeforeground=_TEXT,
                           command=self._on_tf_change).pack(side="left", padx=5)

        self._status_lbl = tk.Label(bar, text="Starting…", bg=_ELEVATED, fg=_MUTED,
                                    font=("sans-serif", 9))
        self._status_lbl.pack(side="right")

        # ttk.Notebook
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook",     background=_BG,      tabmargins=[2, 2, 2, 0])
        style.configure("TNotebook.Tab", background=_ELEVATED, foreground=_MUTED,
                        padding=[14, 6])
        style.map("TNotebook.Tab",
                  background=[("selected", _BG)],
                  foreground=[("selected", _TEXT)])
        style.configure("TFrame", background=_BG)

        self._nb = ttk.Notebook(self.root)
        self._nb.pack(fill="both", expand=True, padx=4, pady=4)

        self._build_rrg_tab()
        self._build_backtest_tab()
        self._build_holding_tab()

    # ── Tab 1: RRG Chart ──────────────────────────────────────────────────────

    def _build_rrg_tab(self) -> None:
        frame = tk.Frame(self._nb, bg=_BG)
        self._nb.add(frame, text="  RRG Chart  ")

        # Matplotlib figure (RRG scatter)
        self._rrg_fig, self._rrg_ax = plt.subplots(figsize=(10, 6))
        self._rrg_fig.subplots_adjust(left=0.07, right=0.97, top=0.93, bottom=0.07)

        self._rrg_canvas = FigureCanvasTkAgg(self._rrg_fig, master=frame)
        self._rrg_canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=(6, 2))

        # Controls row (Play/Pause, Date slider, Tail slider)
        ctrl = tk.Frame(frame, bg=_ELEVATED, pady=6, padx=12)
        ctrl.pack(fill="x", padx=6, pady=(0, 2))

        self._play_btn = tk.Button(ctrl, text="▶  Play", bg=_ACCENT, fg="white",
                                   activebackground="#3a7ae0", activeforeground="white",
                                   relief="flat", padx=14, pady=5, cursor="hand2",
                                   command=self._toggle_play)
        self._play_btn.pack(side="left", padx=(0, 16))

        tk.Label(ctrl, text="Date:", bg=_ELEVATED, fg=_MUTED,
                 font=("sans-serif", 9)).pack(side="left")
        self._date_var = tk.IntVar(value=0)
        self._date_slider = tk.Scale(
            ctrl, variable=self._date_var, from_=0, to=1,
            orient="horizontal", bg=_ELEVATED, fg=_MUTED,
            troughcolor=_BORDER, highlightthickness=0, bd=0,
            length=320, showvalue=False,
            command=self._on_date_slider,
        )
        self._date_slider.pack(side="left", padx=4)

        self._date_lbl = tk.Label(ctrl, text="—", bg=_ELEVATED, fg=_TEXT,
                                  font=("Courier", 10, "bold"), width=12)
        self._date_lbl.pack(side="left", padx=10)

        tk.Label(ctrl, text="Trail:", bg=_ELEVATED, fg=_MUTED,
                 font=("sans-serif", 9)).pack(side="left", padx=(16, 0))
        self._tail_var = tk.IntVar(value=_TAIL_INIT)
        tk.Scale(ctrl, variable=self._tail_var, from_=2, to=20,
                 orient="horizontal", bg=_ELEVATED, fg=_MUTED,
                 troughcolor=_BORDER, highlightthickness=0, bd=0,
                 length=140, showvalue=True,
                 command=self._on_tail_change).pack(side="left", padx=4)

        # Symbol status table (like RRGPy's table, coloured rows by quadrant)
        self._build_status_table(frame)

    def _build_status_table(self, parent: tk.Frame) -> None:
        tbl = tk.Frame(parent, bg=_ELEVATED)
        tbl.pack(fill="x", padx=6, pady=(2, 6))

        cols   = ["Symbol", "Sector", "Quadrant", "RS-Ratio", "RS-Mom", "Trend"]
        widths = [8, 22, 12, 10, 10, 7]
        for j, (h, w) in enumerate(zip(cols, widths)):
            tk.Label(tbl, text=h, bg=_BORDER, fg=_MUTED,
                     font=("Courier", 9, "bold"), width=w, anchor="w",
                     relief="flat", padx=5, pady=3).grid(
                row=0, column=j, padx=1, pady=1, sticky="ew")

        self._tbl_rows: list[list[tk.Label]] = []
        for i, sym in enumerate(config.SYMBOLS):
            row: list[tk.Label] = []
            for j, w in enumerate(widths):
                lbl = tk.Label(tbl, text="—", bg=_ELEVATED, fg=_MUTED,
                               font=("Courier", 9), width=w, anchor="w",
                               relief="flat", padx=5, pady=2)
                lbl.grid(row=i + 1, column=j, padx=1, pady=0, sticky="ew")
                row.append(lbl)
            self._tbl_rows.append(row)

    # ── Tab 2: Backtest ───────────────────────────────────────────────────────

    def _build_backtest_tab(self) -> None:
        frame = tk.Frame(self._nb, bg=_BG)
        self._nb.add(frame, text="  Backtest  ")

        self._bt_fig, axes = plt.subplots(
            2, 1, figsize=(11, 5.8),
            gridspec_kw={"height_ratios": [3, 1]}, sharex=True,
        )
        self._bt_fig.subplots_adjust(left=0.08, right=0.97, top=0.93, bottom=0.08, hspace=0.05)
        self._bt_ax_eq, self._bt_ax_dd = axes

        self._bt_canvas = FigureCanvasTkAgg(self._bt_fig, master=frame)
        self._bt_canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)

        # Metrics table
        self._bt_tbl = tk.Frame(frame, bg=_ELEVATED)
        self._bt_tbl.pack(fill="x", padx=6, pady=(0, 6))

    # ── Tab 3: Holding Time ───────────────────────────────────────────────────

    def _build_holding_tab(self) -> None:
        frame = tk.Frame(self._nb, bg=_BG)
        self._nb.add(frame, text="  Holding Time  ")

        self._ht_fig, (self._ht_ax_heat, self._ht_ax_bar) = plt.subplots(
            1, 2, figsize=(12, 5.5)
        )
        self._ht_fig.subplots_adjust(left=0.09, right=0.97, top=0.90, bottom=0.14, wspace=0.4)

        self._ht_canvas = FigureCanvasTkAgg(self._ht_fig, master=frame)
        self._ht_canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)

    # ─────────────────────────────────────────────────────────────────────────
    # Data loading
    # ─────────────────────────────────────────────────────────────────────────

    def _load_data(self) -> None:
        """Download + compute in a background thread so the UI stays responsive."""
        def _worker() -> None:
            tf = self._tf_var.get()
            self._set_status("Downloading prices…")
            try:
                universe, benchmark = load_all(interval=tf)

                self._set_status("Computing RRG (JdK WMA)…")
                rs_ratio, rs_momentum = compute_rrg(universe, benchmark, timeframe=tf)
                quadrants = classify_frame(rs_ratio, rs_momentum)

                self._set_status("Running backtests (4 strategies)…")
                precomp = {tf: (universe, benchmark, rs_ratio, rs_momentum, quadrants)}
                study = run_study(timeframes=[tf], force_refresh=False, precomputed=precomp)

                self._set_status("Computing holding time…")
                streaks = compute_streaks(quadrants)

                # Store all results
                self.universe  = universe
                self.benchmark = benchmark
                self.rsr       = rs_ratio
                self.rsm       = rs_momentum
                self.quadrants = quadrants
                self.study     = study
                self.streaks   = streaks

                self.root.after(0, self._on_data_ready)

            except Exception as exc:
                import traceback
                traceback.print_exc()
                self.root.after(0, lambda: self._set_status(f"Error: {exc}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_data_ready(self) -> None:
        n = len(self.rsr)
        self._date_slider.config(from_=self._tail, to=n - 1)
        self._date_var.set(n - 1)
        self._slider_val = n - 1

        tf = self._tf_var.get()
        tf_lbl = config.TIMEFRAMES[tf]["label"]
        span   = f"{self.rsr.index[0].date()}  to  {self.rsr.index[-1].date()}"
        self._set_status(f"{tf_lbl}  |  {n} bars  |  {span}")

        self._draw_rrg()
        self._draw_backtest()
        self._draw_holding()

    def _set_status(self, msg: str) -> None:
        self.root.after(0, lambda: self._status_lbl.config(text=msg))

    # ─────────────────────────────────────────────────────────────────────────
    # Control handlers
    # ─────────────────────────────────────────────────────────────────────────

    def _on_tf_change(self) -> None:
        if self._anim_job:
            self.root.after_cancel(self._anim_job)
            self._anim_job = None
        self._is_playing = False
        self._play_btn.config(text="▶  Play")
        self.rsr = None
        self._set_status("Loading…")
        self._load_data()

    def _on_date_slider(self, val: str) -> None:
        self._slider_val = int(val)
        if self.rsr is not None:
            self._draw_rrg()

    def _on_tail_change(self, val: str) -> None:
        self._tail = int(val)
        if self.rsr is not None:
            self._draw_rrg()

    def _toggle_play(self) -> None:
        self._is_playing = not self._is_playing
        if self._is_playing:
            self._play_btn.config(text="⏸  Pause")
            self._step()
        else:
            self._play_btn.config(text="▶  Play")
            if self._anim_job:
                self.root.after_cancel(self._anim_job)
                self._anim_job = None

    def _step(self) -> None:
        if not self._is_playing or self.rsr is None:
            return
        n = len(self.rsr)
        nxt = self._slider_val + 1
        if nxt >= n:
            nxt = self._tail
        self._slider_val = nxt
        self._date_var.set(nxt)
        self._draw_rrg()
        self._anim_job = self.root.after(280, self._step)

    # ─────────────────────────────────────────────────────────────────────────
    # RRG chart drawing  (Tab 1) — closely modelled on RRGPy's animate()
    # ─────────────────────────────────────────────────────────────────────────

    def _draw_rrg(self) -> None:
        if self.rsr is None:
            return

        ax = self._rrg_ax
        ax.cla()

        end_i   = min(self._slider_val, len(self.rsr) - 1)
        start_i = max(0, end_i - self._tail + 1)
        date    = self.rsr.index[end_i]

        # Dynamic axis range centred on 100
        win_x = self.rsr.iloc[start_i: end_i + 1].values.flatten()
        win_y = self.rsm.iloc[start_i: end_i + 1].values.flatten()
        margin = max(np.nanmax(np.abs(np.concatenate([win_x - 100, win_y - 100]))), 5) * 1.25
        lo, hi = 100 - margin, 100 + margin

        # Static chart elements
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        ax.set_xlabel("JdK RS-Ratio")
        ax.set_ylabel("JdK RS-Momentum")
        ax.set_title(f"Relative Rotation Graph — {date.strftime('%Y-%m-%d')}",
                     color=_TEXT, fontsize=12)
        ax.axhline(y=100, color=_BORDER, linestyle="--", linewidth=1, alpha=0.9)
        ax.axvline(x=100, color=_BORDER, linestyle="--", linewidth=1, alpha=0.9)
        ax.grid(True, alpha=0.25)

        # Quadrant background fills (like RRGPy — same alpha 0.12)
        ax.fill_between([100, hi], [100, 100], [hi, hi],  color=_C_LEAD, alpha=0.12)
        ax.fill_between([lo, 100], [100, 100], [hi, hi],  color=_C_IMPR, alpha=0.12)
        ax.fill_between([lo, 100], [lo, lo],   [100, 100],color=_C_LAGG, alpha=0.12)
        ax.fill_between([100, hi], [lo, lo],   [100, 100],color=_C_WEAK, alpha=0.12)

        # Quadrant labels
        span = hi - lo
        ax.text(lo + 0.74*span, lo + 0.92*span, "Leading",   color=_C_LEAD, fontsize=11, fontweight="bold", alpha=0.85)
        ax.text(lo + 0.02*span, lo + 0.92*span, "Improving", color=_C_IMPR, fontsize=11, fontweight="bold", alpha=0.85)
        ax.text(lo + 0.02*span, lo + 0.03*span, "Lagging",   color=_C_LAGG, fontsize=11, fontweight="bold", alpha=0.85)
        ax.text(lo + 0.72*span, lo + 0.03*span, "Weakening", color=_C_WEAK, fontsize=11, fontweight="bold", alpha=0.85)

        # Draw each symbol (RRGPy style: spline trail + small dots + big current dot)
        for sym in self.rsr.columns:
            x_trail = self.rsr.iloc[start_i: end_i + 1][sym].values.astype(float)
            y_trail = self.rsm.iloc[start_i: end_i + 1][sym].values.astype(float)

            valid = ~(np.isnan(x_trail) | np.isnan(y_trail))
            if valid.sum() < 2:
                continue
            xv, yv = x_trail[valid], y_trail[valid]
            n_pts  = len(xv)

            quad  = self.quadrants.iloc[end_i][sym]
            color = QUAD_COLORS.get(quad, "#888888")

            # Spline trail (RRGPy uses scipy splprep)
            if _HAS_SCIPY and n_pts >= 4:
                try:
                    tck, _ = interpolate.splprep([xv, yv], s=0, k=min(3, n_pts - 1))
                    xi, yi = interpolate.splev(np.linspace(0, 1, 120), tck)
                    ax.plot(xi, yi, color=color, alpha=0.35, linewidth=1.8)
                except Exception:
                    ax.plot(xv, yv, color=color, alpha=0.35, linewidth=1.8)
            else:
                ax.plot(xv, yv, color=color, alpha=0.35, linewidth=1.8)

            # Trail dots: small for older positions, bigger toward current (RRGPy style)
            sizes = np.linspace(_DOT_TRAIL * 0.4, _DOT_TRAIL, n_pts)
            ax.scatter(xv, yv, s=sizes, color=color, alpha=0.55, zorder=3)

            # Current position: large dot with white edge (RRGPy style)
            ax.scatter(xv[-1], yv[-1], s=_DOT_CURRENT, color=color,
                       edgecolors="white", linewidths=1.5, zorder=5)
            ax.annotate(sym, (xv[-1], yv[-1]),
                        xytext=(5, 6), textcoords="offset points",
                        color=color, fontsize=9, fontweight="bold", zorder=6)

            # Update status table row
            self._update_status_row(sym, quad, xv[-1], yv[-1])

        self._date_lbl.config(text=str(date.date()))
        self._rrg_canvas.draw_idle()

    def _update_status_row(self, sym: str, quad: str, rr: float, rm: float) -> None:
        try:
            i = config.SYMBOLS.index(sym)
        except ValueError:
            return
        if i >= len(self._tbl_rows):
            return

        row    = self._tbl_rows[i]
        bg     = QUAD_ROW_BG.get(quad, _ELEVATED)
        qcolor = QUAD_COLORS.get(quad, _MUTED)
        trend  = "▲" if rm >= 100 else "▼"
        tc     = _C_LEAD if rm >= 100 else _C_LAGG

        vals   = [sym, config.SECTOR_NAMES.get(sym, sym), quad,
                  f"{rr:.2f}", f"{rm:.2f}", trend]
        fgs    = [_TEXT, _MUTED, qcolor, _TEXT, _TEXT, tc]

        for lbl, val, fg in zip(row, vals, fgs):
            lbl.config(text=val, bg=bg, fg=fg)

    # ─────────────────────────────────────────────────────────────────────────
    # Backtest chart (Tab 2)
    # ─────────────────────────────────────────────────────────────────────────

    def _draw_backtest(self) -> None:
        if not self.study:
            return

        tf     = self._tf_var.get()
        ax_eq  = self._bt_ax_eq
        ax_dd  = self._bt_ax_dd
        ax_eq.cla()
        ax_dd.cla()

        ax_eq.set_title("Equity Curves — Entry Quadrant Comparison")
        ax_eq.set_ylabel("Portfolio Value ($)")
        ax_dd.set_ylabel("Drawdown")
        ax_dd.set_xlabel("Date")
        for ax in (ax_eq, ax_dd):
            ax.grid(True, alpha=0.25)

        # SPY benchmark (normalised to initial capital)
        first_equity = next(
            (r["equity"] for (t, _), r in self.study.items() if t == tf), None
        )
        if first_equity is not None:
            bm = self.benchmark.reindex(first_equity.index).ffill()
            bm_norm = bm / bm.iloc[0] * config.INITIAL_CAPITAL
            ax_eq.plot(bm_norm.index, bm_norm.values,
                       color="#777777", linewidth=1.5, linestyle="--",
                       label="SPY (buy & hold)", alpha=0.75)

        for (stf, label), res in self.study.items():
            if stf != tf:
                continue
            eq    = res["equity"]
            dd    = eq / eq.cummax() - 1
            color = STRATEGY_COLORS.get(label, _ACCENT)
            ax_eq.plot(eq.index, eq.values, color=color, linewidth=2.2, label=label)
            ax_dd.fill_between(dd.index, dd.values, 0, color=color, alpha=0.28)

        ax_eq.legend(loc="upper left", fontsize=9, framealpha=0.7)
        self._bt_canvas.draw_idle()

        # Rebuild metrics table
        for w in self._bt_tbl.winfo_children():
            w.destroy()

        headers = ["Strategy", "CAGR", "Sharpe", "Max DD", "Volatility", "Trades"]
        widths  = [14, 10, 10, 10, 12, 8]
        for j, (h, w) in enumerate(zip(headers, widths)):
            tk.Label(self._bt_tbl, text=h, bg=_BORDER, fg=_MUTED,
                     font=("Courier", 9, "bold"), width=w, anchor="w",
                     relief="flat", padx=5, pady=3).grid(
                row=0, column=j, padx=1, pady=1, sticky="ew")

        for i, label in enumerate(STRATEGY_COLORS):
            key = (tf, label)
            if key not in self.study:
                continue
            s  = self.study[key]["summary"]
            sc = STRATEGY_COLORS[label]

            def _v(key: str) -> str:
                return str(s[key]) if key in s.index else "—"

            vals = [label, _v("CAGR"), _v("Sharpe Ratio"),
                    _v("Max Drawdown"), _v("Ann. Volatility"), _v("Num Trades")]
            fgs = [sc] + [_TEXT] * (len(vals) - 1)
            for j, (v, fg, w) in enumerate(zip(vals, fgs, widths)):
                tk.Label(self._bt_tbl, text=v, bg=_ELEVATED, fg=fg,
                         font=("Courier", 9), width=w, anchor="w",
                         relief="flat", padx=5, pady=2).grid(
                    row=i + 1, column=j, padx=1, pady=0, sticky="ew")

    # ─────────────────────────────────────────────────────────────────────────
    # Holding time chart (Tab 3)
    # ─────────────────────────────────────────────────────────────────────────

    def _draw_holding(self) -> None:
        if self.streaks is None or self.streaks.empty:
            return

        ax_h = self._ht_ax_heat
        ax_b = self._ht_ax_bar
        ax_h.cla()
        ax_b.cla()

        quads  = [Quadrant.LEADING, Quadrant.IMPROVING, Quadrant.WEAKENING, Quadrant.LAGGING]
        qcols  = [_C_LEAD, _C_IMPR, _C_WEAK, _C_LAGG]

        # ── Left: grouped bar chart per symbol ──────────────────────────────
        summ = streak_summary(self.streaks).reset_index()
        if not summ.empty:
            pivot = (summ.pivot(index="symbol", columns="quadrant", values="mean_bars")
                     .reindex(columns=quads).fillna(0))
            syms  = list(pivot.index)
            n_sym = len(syms)
            x     = np.arange(len(quads))
            bar_w = 0.7 / max(n_sym, 1)

            for i, sym in enumerate(syms):
                offset = (i - n_sym / 2 + 0.5) * bar_w
                ax_h.bar(x + offset, pivot.loc[sym].values, bar_w,
                         color=_ACCENT, alpha=0.55, label=sym if i < 6 else None)

            ax_h.set_xticks(x)
            ax_h.set_xticklabels(quads, rotation=12, color=_MUTED, fontsize=8)
            ax_h.set_ylabel("Avg Bars", fontsize=8)
            ax_h.set_title("Avg Bars Per Symbol in Each Quadrant", fontsize=10)
            ax_h.legend(fontsize=7, ncol=2, loc="upper right", framealpha=0.5)
            ax_h.grid(True, alpha=0.2, axis="y")

        # ── Right: overall summary per quadrant ─────────────────────────────
        overall = overall_summary(self.streaks)
        if not overall.empty:
            tf_lbl = config.TIMEFRAMES[self._tf_var.get()]["label"]
            vals   = [overall.loc[q, "mean_bars"] if q in overall.index else 0 for q in quads]
            medians= [overall.loc[q, "median_bars"] if q in overall.index else 0 for q in quads]
            maxs   = [overall.loc[q, "max_bars"] if q in overall.index else 0 for q in quads]

            bx = np.arange(len(quads))
            ax_b.bar(bx - 0.25, vals,     0.25, label="Mean",   color=qcols, alpha=0.80)
            ax_b.bar(bx,        medians,   0.25, label="Median", color=qcols, alpha=0.55)
            ax_b.bar(bx + 0.25, maxs,      0.25, label="Max",    color=qcols, alpha=0.35)

            ax_b.set_xticks(bx)
            ax_b.set_xticklabels(quads, rotation=12, color=_MUTED, fontsize=8)
            ax_b.set_ylabel("Bars", fontsize=8)
            ax_b.set_title(f"Hold Duration Distribution  ({tf_lbl})", fontsize=10)
            ax_b.legend(fontsize=8, framealpha=0.5)
            ax_b.grid(True, alpha=0.2, axis="y")

        self._ht_canvas.draw_idle()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    root = tk.Tk()
    RRGDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
