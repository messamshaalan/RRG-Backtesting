"""
RRG Sector Dashboard entry point.

Run:
    python dashboard/app.py
    python dashboard/app.py --port 8051 --no-debug
"""
from __future__ import annotations

import argparse
import io
import os
import sys

# Force UTF-8 on Windows where the default console encoding (cp1252) rejects
# characters like the em-dash, arrows, and box-drawing chars used in output.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure project root is on the path when running from any directory
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import dash
import dash_bootstrap_components as dbc

import config
from dashboard.layout import build_layout
from dashboard.callbacks import register_callbacks


def create_app() -> dash.Dash:
    app = dash.Dash(
        __name__,
        external_stylesheets=[
            dbc.themes.SLATE,                    # dark Bootstrap base
            dbc.icons.BOOTSTRAP,
        ],
        suppress_callback_exceptions=True,
        title="RRG Sector Dashboard",
        update_title=None,
        assets_folder=os.path.join(_ROOT, "assets"),
    )
    app.layout = build_layout()
    register_callbacks(app)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="RRG Sector Dashboard")
    parser.add_argument("--port",     type=int,  default=config.DASH_PORT)
    parser.add_argument("--no-debug", action="store_true")
    args = parser.parse_args()

    app = create_app()
    print(f"\n  RRG Dashboard running at  http://127.0.0.1:{args.port}/\n")
    app.run(
        debug=not args.no_debug,
        port=args.port,
        host="127.0.0.1",
    )


if __name__ == "__main__":
    main()
