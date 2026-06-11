"""
Entry point — run a full RRG backtest and save results.

Usage:
    python main.py
    python main.py --strategy momentum
    python main.py --strategy leading --refresh
"""
import argparse
import os
import sys

import pandas as pd

import config
from data.fetcher import load_all
from backtest.engine import run, performance_summary
from strategy.examples import LeadingOnlyStrategy, MomentumRotationStrategy, CustomStrategy
from visualize.plots import equity_curve, rrg_chart


STRATEGIES = {
    "leading":  LeadingOnlyStrategy,
    "momentum": MomentumRotationStrategy,
    "custom":   CustomStrategy,
}


def parse_args():
    p = argparse.ArgumentParser(description="RRG Strategy Backtester")
    p.add_argument("--strategy", default="leading", choices=STRATEGIES.keys(),
                   help="Which strategy to run (default: leading)")
    p.add_argument("--refresh", action="store_true",
                   help="Force re-download of price data")
    p.add_argument("--no-plots", action="store_true",
                   help="Skip saving plot files")
    return p.parse_args()


def main():
    args = parse_args()

    print(f"\n{'='*55}")
    print(f"  RRG Strategy Backtest  |  strategy={args.strategy}")
    print(f"  Universe : {', '.join(config.SYMBOLS)}")
    print(f"  Benchmark: {config.BENCHMARK}")
    print(f"  Period   : {config.START_DATE} → {config.END_DATE}")
    print(f"{'='*55}\n")

    # ── Load data ─────────────────────────────────────────────────────────────
    universe, benchmark = load_all(force_refresh=args.refresh)
    print(f"Loaded {len(universe.columns)} symbols × {len(universe)} weeks\n")

    # ── Run backtest ──────────────────────────────────────────────────────────
    strategy = STRATEGIES[args.strategy]()
    results  = run(universe, benchmark, strategy)

    equity   = results["equity"]
    trades   = results["trades"]

    # ── Performance ───────────────────────────────────────────────────────────
    summary = performance_summary(equity)
    summary["Num Trades"] = len(trades)
    print("Performance Summary")
    print("-" * 30)
    for k, v in summary.items():
        print(f"  {k:<20} {v}")
    print()

    # ── Save outputs ──────────────────────────────────────────────────────────
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    equity.to_csv(os.path.join(config.OUTPUT_DIR, "equity.csv"))
    if not trades.empty:
        trades.to_csv(os.path.join(config.OUTPUT_DIR, "trades.csv"), index=False)
    results["positions"].to_csv(os.path.join(config.OUTPUT_DIR, "positions.csv"), index=False)

    if not args.no_plots:
        # benchmark equity for comparison
        bm_aligned = benchmark.reindex(equity.index).ffill()

        fig1 = equity_curve(
            equity, bm_aligned,
            save_path=os.path.join(config.OUTPUT_DIR, "equity_curve.png"),
        )
        fig2 = rrg_chart(
            results["rs_ratio"], results["rs_momentum"], results["quadrants"],
            save_path=os.path.join(config.OUTPUT_DIR, "rrg_latest.png"),
        )
        print(f"Plots saved to '{config.OUTPUT_DIR}/'")

    print(f"\nDone. CSV outputs in '{config.OUTPUT_DIR}/'")


if __name__ == "__main__":
    main()
