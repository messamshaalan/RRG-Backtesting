"""
RRG scatter chart with animated trails — inspired by RRGPy (An0n1mity/RRGPy).

UI features incorporated from RRGPy:
- Spline-smoothed trail curves (Plotly native line_shape='spline')
- Progressive dot sizes along trail: small (old) → large (current)
- Arrow head at the current position to show rotation direction
- Increased quadrant background opacity for clearer quadrant separation

Color model:
- Each symbol gets a unique fixed color from SYMBOL_PALETTE (not quadrant-based)
  so multiple symbols in the same quadrant remain visually distinct.
- Quadrant colors (QUAD_COLORS) are used ONLY for backgrounds, labels, and the
  current-dot border ring — so you can see both identity and quadrant at a glance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

import config
from rrg.quadrant import Quadrant

# ── Per-quadrant colours (backgrounds, labels, dot border rings) ──────────────
QUAD_COLORS = {
    Quadrant.LEADING:   "#2ecc71",
    Quadrant.IMPROVING: "#3498db",
    Quadrant.WEAKENING: "#f39c12",
    Quadrant.LAGGING:   "#e74c3c",
}
QUAD_BG = {
    Quadrant.LEADING:   "rgba(46,  204, 113, 0.15)",
    Quadrant.IMPROVING: "rgba(52,  152, 219, 0.15)",
    Quadrant.WEAKENING: "rgba(243, 156,  18, 0.15)",
    Quadrant.LAGGING:   "rgba(231,  76,  60, 0.15)",
}
QUAD_LABEL_POS = {
    Quadrant.LEADING:   (0.73, 0.93),
    Quadrant.WEAKENING: (0.73, 0.07),
    Quadrant.LAGGING:   (0.03, 0.07),
    Quadrant.IMPROVING: (0.03, 0.93),
}

# ── Per-symbol colour palette (vibrant, dark-theme optimised) ─────────────────
SYMBOL_PALETTE = [
    "#00d4ff",  # cyan
    "#ffd93d",  # gold
    "#ff6b6b",  # coral
    "#6bcb77",  # mint green
    "#a855f7",  # violet
    "#ff9f43",  # orange
    "#54a0ff",  # royal blue
    "#1dd1a1",  # teal
    "#fd79a8",  # pink
    "#fdcb6e",  # peach
    "#6c5ce7",  # indigo
    "#ff6348",  # tomato
]

C = config.CENTER  # 100.0


def _symbol_color_map(symbols: list[str]) -> dict[str, str]:
    return {sym: SYMBOL_PALETTE[i % len(SYMBOL_PALETTE)] for i, sym in enumerate(symbols)}


def _axis_range(rs_ratio: pd.DataFrame, rs_momentum: pd.DataFrame) -> tuple[list, list]:
    all_x = rs_ratio.values.flatten()
    all_y = rs_momentum.values.flatten()
    x_span = max(abs(np.nanmax(all_x) - C), abs(np.nanmin(all_x) - C), 5) * 1.3
    y_span = max(abs(np.nanmax(all_y) - C), abs(np.nanmin(all_y) - C), 5) * 1.3
    span   = max(x_span, y_span)
    return [C - span, C + span], [C - span, C + span]


def _quadrant_shapes(x_range: list, y_range: list) -> list[dict]:
    regions = [
        (Quadrant.LEADING,   C, x_range[1], C, y_range[1]),
        (Quadrant.WEAKENING, C, x_range[1], y_range[0], C),
        (Quadrant.LAGGING,   x_range[0], C, y_range[0], C),
        (Quadrant.IMPROVING, x_range[0], C, C, y_range[1]),
    ]
    return [
        dict(type="rect", xref="x", yref="y",
             x0=x0, x1=x1, y0=y0, y1=y1,
             fillcolor=QUAD_BG[quad], line=dict(width=0), layer="below")
        for quad, x0, x1, y0, y1 in regions
    ]


def _quadrant_annotations(x_range: list, y_range: list) -> list[dict]:
    x_lo, x_hi = x_range
    y_lo, y_hi = y_range
    x_span, y_span = x_hi - x_lo, y_hi - y_lo
    return [
        dict(
            x=x_lo + xf * x_span,
            y=y_lo + yf * y_span,
            text=f"<b>{quad}</b>",
            showarrow=False,
            font=dict(size=14, color=QUAD_COLORS[quad]),
            opacity=0.85,
            xref="x", yref="y",
        )
        for quad, (xf, yf) in QUAD_LABEL_POS.items()
    ]


def _symbol_traces(
    rs_ratio: pd.DataFrame,
    rs_momentum: pd.DataFrame,
    quadrants: pd.DataFrame,
    date: pd.Timestamp,
    trail_bars: int,
) -> list[go.BaseTraceType]:
    """
    Build traces per symbol:
      1. Spline trail line (smooth curve, symbol colour, faded)
      2. Progressive dots along trail (small → bigger toward current end)
      3. Current-position dot (large, symbol fill + quadrant border ring)
      4. Ticker label at current position
    """
    traces: list[go.BaseTraceType] = []
    sym_colors = _symbol_color_map(list(rs_ratio.columns))

    idx       = rs_ratio.index.get_loc(date)
    t_start   = max(0, idx - trail_bars + 1)
    trail_idx = rs_ratio.index[t_start: idx + 1]
    n         = len(trail_idx)

    for sym in rs_ratio.columns:
        sym_color  = sym_colors[sym]
        quad       = quadrants.loc[date, sym]
        quad_color = QUAD_COLORS.get(quad, "#888888")

        x_trail = rs_ratio.loc[trail_idx, sym].values.astype(float)
        y_trail = rs_momentum.loc[trail_idx, sym].values.astype(float)

        # ── 1. Spline trail line ──────────────────────────────────────────────
        traces.append(go.Scatter(
            x=x_trail, y=y_trail,
            mode="lines",
            line=dict(color=sym_color, width=2, shape="spline", smoothing=1.2),
            opacity=0.40,
            showlegend=False,
            hoverinfo="skip",
            name=sym,
        ))

        # ── 2. Progressive trail dots (skip the very last — drawn separately) ─
        if n > 1:
            trail_sizes = np.linspace(4, 8, n - 1).tolist()
            traces.append(go.Scatter(
                x=x_trail[:-1], y=y_trail[:-1],
                mode="markers",
                marker=dict(color=sym_color, size=trail_sizes, opacity=0.45),
                showlegend=False,
                hoverinfo="skip",
                name=sym,
            ))

        # ── 3 & 4. Large current dot + label ─────────────────────────────────
        cur_x, cur_y = float(x_trail[-1]), float(y_trail[-1])
        traces.append(go.Scatter(
            x=[cur_x], y=[cur_y],
            mode="markers+text",
            marker=dict(
                color=sym_color,
                size=16,
                line=dict(color=quad_color, width=2.5),
                symbol="circle",
            ),
            text=[sym],
            textposition="top center",
            textfont=dict(size=11, color=sym_color, family="Inter, sans-serif"),
            name=sym,
            legendgroup=sym,
            showlegend=True,
            hovertemplate=(
                f"<b>{sym}</b> — {config.SECTOR_NAMES.get(sym, sym)}<br>"
                f"RS-Ratio: %{{x:.2f}}<br>"
                f"RS-Mom:   %{{y:.2f}}<br>"
                f"Quadrant: <b>{quad}</b><extra></extra>"
            ),
        ))

    return traces


def build_rrg_figure(
    rs_ratio: pd.DataFrame,
    rs_momentum: pd.DataFrame,
    quadrants: pd.DataFrame,
    date: pd.Timestamp | None = None,
    trail_bars: int = 10,
    animate: bool = False,
    height: int = 650,
) -> go.Figure:
    """
    Build the full RRG Plotly figure for a given date (or the latest date).

    animate: if True, generate Plotly frames for the full playback slider.
             Expensive for large datasets — use False for live callback updates.
    """
    if date is None:
        date = rs_ratio.index[-1]

    x_range, y_range = _axis_range(rs_ratio, rs_momentum)
    shapes      = _quadrant_shapes(x_range, y_range)
    annotations = _quadrant_annotations(x_range, y_range)

    # Crosshair at (100, 100)
    shapes += [
        dict(type="line", xref="x", yref="y",
             x0=x_range[0], x1=x_range[1], y0=C, y1=C,
             line=dict(color="rgba(255,255,255,0.18)", width=1, dash="dot")),
        dict(type="line", xref="x", yref="y",
             x0=C, x1=C, y0=y_range[0], y1=y_range[1],
             line=dict(color="rgba(255,255,255,0.18)", width=1, dash="dot")),
    ]

    traces = _symbol_traces(rs_ratio, rs_momentum, quadrants, date, trail_bars)

    layout = go.Layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(21,24,32,1)",
        font=dict(family="Inter, sans-serif", color="#8b92a8"),
        height=height,
        margin=dict(l=55, r=35, t=55, b=55),
        xaxis=dict(
            title="RS-Ratio",
            range=x_range,
            gridcolor="rgba(42,47,69,0.5)",
            zeroline=False,
            tickfont=dict(size=10),
        ),
        yaxis=dict(
            title="RS-Momentum",
            range=y_range,
            gridcolor="rgba(42,47,69,0.5)",
            zeroline=False,
            tickfont=dict(size=10),
        ),
        title=dict(
            text=f"Relative Rotation Graph — {date.strftime('%Y-%m-%d')}",
            font=dict(size=15, color="#e8eaf0"),
            x=0.01, xanchor="left",
        ),
        legend=dict(
            bgcolor="rgba(21,24,32,0.85)",
            bordercolor="rgba(42,47,69,0.8)",
            borderwidth=1,
            font=dict(size=10),
            orientation="v",
            x=1.01, y=1, xanchor="left",
        ),
        shapes=shapes,
        annotations=annotations,
        hovermode="closest",
    )

    fig = go.Figure(data=traces, layout=layout)

    if animate:
        frames = []
        for d in rs_ratio.index:
            frame_traces = _symbol_traces(rs_ratio, rs_momentum, quadrants, d, trail_bars)
            frames.append(go.Frame(
                data=frame_traces,
                name=str(d.date()),
                layout=go.Layout(
                    title_text=f"Relative Rotation Graph — {d.strftime('%Y-%m-%d')}"
                ),
            ))

        fig.frames = frames
        steps = [dict(
            args=[[f.name], dict(frame=dict(duration=150, redraw=True),
                                 mode="immediate", transition=dict(duration=0))],
            label=f.name, method="animate",
        ) for f in frames]

        fig.update_layout(
            updatemenus=[dict(
                type="buttons", showactive=False,
                x=0, y=-0.12, xanchor="left", yanchor="top",
                buttons=[
                    dict(label="Play",  method="animate",
                         args=[None, dict(frame=dict(duration=200, redraw=True),
                                          fromcurrent=True, mode="immediate")]),
                    dict(label="Pause", method="animate",
                         args=[[None], dict(frame=dict(duration=0, redraw=False),
                                            mode="immediate")]),
                ],
                bgcolor="#1c2030", font=dict(color="#e8eaf0"),
            )],
            sliders=[dict(
                currentvalue=dict(prefix="Date: ", font=dict(size=11, color="#8b92a8")),
                pad=dict(t=60),
                steps=steps,
                bgcolor="#1c2030",
                bordercolor="#2a2f45",
                tickcolor="#2a2f45",
                font=dict(color="#8b92a8"),
            )],
        )

    return fig


def build_symbol_table(
    rs_ratio: pd.DataFrame,
    rs_momentum: pd.DataFrame,
    quadrants: pd.DataFrame,
    date: pd.Timestamp | None = None,
) -> list:
    """
    Build an HTML status table (rows per symbol) styled like RRGPy's status panel.
    Returns a list of dash html elements to render below the RRG chart.
    Quadrant background colour applied per row.
    """
    from dash import html

    if date is None:
        date = rs_ratio.index[-1]

    sym_colors = _symbol_color_map(list(rs_ratio.columns))

    # Row background colours (soft, dark-theme variant of quadrant colours)
    _ROW_BG = {
        Quadrant.LEADING:   "rgba(46, 204, 113, 0.12)",
        Quadrant.IMPROVING: "rgba(52, 152, 219, 0.12)",
        Quadrant.WEAKENING: "rgba(243,156,  18, 0.12)",
        Quadrant.LAGGING:   "rgba(231, 76,  60, 0.12)",
    }

    header = html.Tr([
        html.Th(col, style={"padding": "6px 10px", "color": "#8b92a8",
                            "fontSize": "0.75rem", "fontWeight": "600",
                            "borderBottom": "1px solid rgba(42,47,69,0.8)",
                            "textAlign": "left"})
        for col in ["Symbol", "Sector", "Quadrant", "RS-Ratio", "RS-Mom"]
    ])

    rows = []
    for sym in rs_ratio.columns:
        rr  = rs_ratio.loc[date, sym]
        rm  = rs_momentum.loc[date, sym]
        qd  = quadrants.loc[date, sym]
        sc  = sym_colors[sym]
        qc  = QUAD_COLORS.get(qd, "#888")
        bg  = _ROW_BG.get(qd, "transparent")
        sector = config.SECTOR_NAMES.get(sym, sym)

        arrow = "▲" if rm >= C else "▼"
        arrow_color = "#2ecc71" if rm >= C else "#e74c3c"

        rows.append(html.Tr(
            style={"background": bg, "borderBottom": "1px solid rgba(42,47,69,0.4)"},
            children=[
                html.Td(html.Span(sym, style={"color": sc, "fontWeight": "700",
                                              "fontSize": "0.82rem"}),
                        style={"padding": "6px 10px"}),
                html.Td(sector, style={"padding": "6px 10px", "color": "#8b92a8",
                                       "fontSize": "0.78rem"}),
                html.Td(
                    html.Span(qd, style={
                        "background": qc, "color": "#fff",
                        "padding": "2px 8px", "borderRadius": "10px",
                        "fontSize": "0.72rem", "fontWeight": "600",
                    }),
                    style={"padding": "4px 10px"}
                ),
                html.Td(f"{rr:.2f}", style={"padding": "6px 10px",
                                             "color": "#e8eaf0", "fontSize": "0.82rem",
                                             "textAlign": "right", "fontFamily": "monospace"}),
                html.Td(
                    html.Span(f"{arrow} {rm:.2f}",
                              style={"color": arrow_color, "fontSize": "0.82rem",
                                     "fontFamily": "monospace"}),
                    style={"padding": "6px 10px", "textAlign": "right"}
                ),
            ]
        ))

    table = html.Table(
        [html.Thead(header), html.Tbody(rows)],
        style={
            "width": "100%", "borderCollapse": "collapse",
            "fontSize": "0.82rem",
        },
    )

    return html.Div(
        table,
        style={
            "background": "rgba(21,24,32,0.7)",
            "border": "1px solid rgba(42,47,69,0.6)",
            "borderRadius": "8px",
            "overflowX": "auto",
            "marginTop": "8px",
        },
    )
