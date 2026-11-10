"""Scan the universe for today's setups.

    python scan.py                       # fib_pullback on universe.txt
    python scan.py --tickers UNH CI EOG  # specific tickers
    python scan.py --include-today       # use today's unfinished bar (intraday)

By default an unfinished bar from today's session is dropped, so every result is
based on completed daily candles. Results print as a table and save to output/.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from markets.data.loader import load_bars, load_universe
from markets.strategies import STRATEGIES


def drop_unfinished_bar(df: pd.DataFrame) -> pd.DataFrame:
    now = datetime.now(ZoneInfo("America/New_York"))
    session_done = now.hour > 16 or (now.hour == 16 and now.minute >= 15)
    if len(df) and df.index[-1].date() == now.date() and not session_done:
        return df.iloc[:-1]
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default="fib_pullback", choices=STRATEGIES)
    ap.add_argument("--tickers", nargs="*")
    ap.add_argument("--include-today", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="ignore today's cache")
    args = ap.parse_args()

    strategy = STRATEGIES[args.strategy]()
    tickers = [t.upper() for t in args.tickers] if args.tickers else load_universe()
    rows, failed = [], []
    for t in tickers:
        try:
            df = load_bars(t, years=2, refresh=args.refresh)
        except Exception as e:  # network, bad ticker, provider outage
            failed.append(f"{t} ({type(e).__name__})")
            continue
        if not args.include_today:
            df = drop_unfinished_bar(df)
        if len(df) < strategy.min_bars:
            continue
        df = strategy.prepare(df)
        s = strategy.setup(t, df, len(df) - 1)
        if s is None:
            continue
        status = "TRIGGERED" if s.triggered and s.qualifies else "setting up" if s.qualifies else "pass (R:R)"
        rows.append({"ticker": t, "status": status, "date": s.date.date(),
                     "close": round(df["close"].iat[-1], 2), "trigger": round(s.trigger, 2),
                     "entry": round(s.entry, 2), "stop": round(s.stop, 2),
                     "t1": round(s.targets[0], 2), "t2": round(s.targets[-1], 2),
                     "rr_t1": round(s.rr(0), 2), "rr_t2": round(s.rr(1), 2),
                     "risk_pct": round(100 * s.risk / s.entry, 1), "notes": s.notes})

    order = {"TRIGGERED": 0, "setting up": 1, "pass (R:R)": 2}
    out = pd.DataFrame(rows)
    if out.empty:
        print(f"No setups across {len(tickers)} tickers.")
    else:
        out = out.sort_values(["status", "rr_t2"], key=lambda s: s.map(order) if s.name == "status" else -s)
        with pd.option_context("display.width", 200, "display.max_columns", None):
            print(out.drop(columns="notes").to_string(index=False))
        Path("output").mkdir(exist_ok=True)
        path = Path("output") / f"scan_{args.strategy}_{out['date'].max()}.csv"
        out.to_csv(path, index=False)
        print(f"\nSaved {path}")
    if failed:
        print(f"\nCould not load {len(failed)}: {', '.join(failed)}")


if __name__ == "__main__":
    main()
