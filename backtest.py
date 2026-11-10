"""Backtest a strategy over the universe's history.

    python backtest.py                    # fib_pullback, 10 years, universe.txt
    python backtest.py --years 5 --tickers AAPL MSFT
    python backtest.py --split 2021-01-01 # report before/after a date separately

Results are in R (multiples of the initial risk per trade). See markets/backtest.py
for exactly how trades are managed and what the backtest does not model.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from markets.backtest import simulate_ticker, summarize, trades_frame
from markets.data.loader import load_bars, load_universe
from markets.strategies import STRATEGIES


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default="fib_pullback", choices=STRATEGIES)
    ap.add_argument("--tickers", nargs="*")
    ap.add_argument("--years", type=float, default=10)
    ap.add_argument("--max-hold", type=int, default=40)
    ap.add_argument("--split", help="YYYY-MM-DD: also summarize trades before/after this date")
    args = ap.parse_args()

    strategy = STRATEGIES[args.strategy]()
    tickers = [t.upper() for t in args.tickers] if args.tickers else load_universe()
    trades = []
    for t in tickers:
        try:
            df = load_bars(t, years=args.years)
        except Exception as e:
            print(f"skip {t}: {type(e).__name__}")
            continue
        if len(df) > strategy.min_bars:
            trades += simulate_ticker(strategy, t, df, max_hold=args.max_hold)

    print(f"{args.strategy}: {len(tickers)} tickers, {args.years:g} years")
    for k, v in summarize(trades).items():
        print(f"  {k:>15}: {v}")
    if args.split and trades:
        cut = pd.Timestamp(args.split)
        for label, part in (("before", [t for t in trades if t.entry_date < cut]),
                            ("after", [t for t in trades if t.entry_date >= cut])):
            print(f"\n  {label} {args.split}: {summarize(part)}")
    if trades:
        Path("output").mkdir(exist_ok=True)
        path = Path("output") / f"backtest_{args.strategy}.csv"
        trades_frame(trades).to_csv(path, index=False)
        print(f"\nTrades saved to {path}")


if __name__ == "__main__":
    main()
