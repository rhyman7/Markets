"""Run several strategy variants over the same data and compare them side by side.

    python experiment.py fib_diagnostics

Experiments are defined in EXPERIMENTS below. Each loads data once, so it's much
faster than separate backtest runs. Decide what a variant is meant to show
BEFORE running it, and keep failed variants in the list so the record is honest.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from markets.backtest import simulate_ticker, summarize, trades_frame
from markets.data.loader import load_bars, load_universe
from scan import drop_unfinished_bar
from markets.strategies import FibParams, FibPullback, FibTextbook, FibTextbookI, TextbookParams, TrendBaseline
from markets.strategies import library as lib

EXPERIMENTS = {
    # 2026-11-10: why does fib_pullback trail random entries in uptrends?
    "fib_diagnostics": {
        "A. fib rules (as written)": lambda: FibPullback(),
        "B. fib entries + 5% stop, fib targets": lambda: FibPullback(FibParams(stop_mode="pct")),
        "C. fib entries + baseline stop/targets": lambda: FibPullback(FibParams(stop_mode="pct", target_mode="pct")),
        "D. C without the close-above-high trigger": lambda: FibPullback(FibParams(stop_mode="pct", target_mode="pct", require_trigger=False)),
        "E. fib rules, no 2:1 filter": lambda: FibPullback(FibParams(min_rr=0)),
        "F. random entries in uptrends (control)": lambda: TrendBaseline(),
    },
    # 2026-11-10: the textbook 4-step version (fixed before seeing results).
    "fib_textbook": {
        "A. fib_pullback as written (reference)": lambda: FibPullback(),
        "G. limit buy at 0.559, stop < 78.6%": lambda: FibTextbook(TextbookParams(mode="limit")),
        "H. reversal candle in 38.2-61.8% zone": lambda: FibTextbook(TextbookParams(mode="pattern")),
        "I. H + RSI < 40 and turning up": lambda: FibTextbook(TextbookParams(mode="pattern", require_rsi=True)),
        "J. G + 50-day SMA in the zone": lambda: FibTextbook(TextbookParams(mode="limit", require_ma=True)),
        "F. random entries in uptrends (control)": lambda: TrendBaseline(),
    },
    # 2026-11-10: out-of-sample check of variant I. Rules unchanged; run with
    # --universe universe_midcap.txt. Written down before running: I counts as
    # confirmed only if it beats F in BOTH periods here too.
    "fib_midcap": {
        "I. reversal candle + RSI < 40 turning up": lambda: FibTextbookI(),
        "F. random entries in uptrends (control)": lambda: TrendBaseline(),
    },
}


# 2026-11-10: FibAlgo library screen. Every daily-testable ICT/Wyckoff tool with the shared
# template in markets/strategies/library.py, each against its own matched random control.
# Pass rules were written in research/log.md BEFORE the first run.
LIBRARY_EXPERIMENTS = {
    "fibalgo_screen": [t.name for t in lib.ALL_TOOLS],
    # Filled in from the screen's passes, rules unchanged, run with --universe universe_smallcap.txt.
    "fibalgo_holdout": [],
}
SCREEN_PASS = dict(min_trades=100, min_gap=0.10, min_z=2.0)      # plus gap > 0 in both periods
HOLDOUT_PASS = dict(min_trades=100, min_gap=0.0, min_z=1.5)      # plus gap > 0 in both periods


def _r(trades):
    return np.array([t.r for t in trades if not t.exit_reason.startswith("open")])


def _mean_se(r):
    return (float(r.mean()), float(r.std(ddof=1) / np.sqrt(len(r)))) if len(r) > 1 else (np.nan, np.nan)


def run_library(name, data, split, benchmark):
    rules = HOLDOUT_PASS if name == "fibalgo_holdout" else SCREEN_PASS
    tools = [t for t in lib.ALL_TOOLS if t.name in LIBRARY_EXPERIMENTS[name]]
    if not tools:
        print("No tools listed for this experiment yet.")
        return
    cut = pd.Timestamp(split)
    rows, years = [], {}

    def make(tool):
        st = tool()
        if tool is lib.ComparativeStrength:
            st.benchmark = benchmark
        return st

    for tool in tools:
        trades = []
        for t, df in data.items():
            trades += simulate_ticker(make(tool), t, df)
        ctl_proto = lib.matched_control(tool, trades)
        ctl = []
        for t, df in data.items():
            ctl += simulate_ticker(lib.matched_control(tool, trades), t, df)
        out = {"tool": tool.name, "ctx": tool.context}
        for label, f in (("all", lambda x: True), ("pre", lambda x: x.entry_date < cut), ("post", lambda x: x.entry_date >= cut)):
            r, rc = _r([x for x in trades if f(x)]), _r([x for x in ctl if f(x)])
            m, se = _mean_se(r)
            mc, sec = _mean_se(rc)
            out[f"{label}_n"] = len(r)
            out[f"{label}_expR"] = round(m, 3)
            out[f"{label}_ctl"] = round(mc, 3)
            out[f"{label}_gap"] = round(m - mc, 3)
            if label == "all":
                out["ctl_n"] = len(rc)
                out["z"] = round((m - mc) / np.sqrt(se ** 2 + sec ** 2), 2) if len(r) > 1 else np.nan
        out["risk_atr"] = ctl_proto.stop_atr
        out["limit_atr"] = ctl_proto.limit_atr
        out["PASS"] = bool(out["all_n"] >= rules["min_trades"] and out["all_gap"] >= rules["min_gap"]
                           and out["z"] >= rules["min_z"] and out["pre_gap"] > 0 and out["post_gap"] > 0)
        rows.append(out)
        for part, label in ((trades, "tool"), (ctl, "ctl")):
            df = trades_frame([x for x in part if not x.exit_reason.startswith("open")])
            if not df.empty:
                years[(tool.name, label)] = df.groupby(pd.to_datetime(df["entry_date"]).dt.year)["r"].mean()
        print(f"  done {tool.name}: {out['all_n']} trades", flush=True)

    tab = pd.DataFrame(rows)
    by_year = pd.DataFrame({k[0]: years[(k[0], "tool")] - years.get((k[0], "ctl"), np.nan)
                            for k in years if k[1] == "tool"}).T.round(2)
    with pd.option_context("display.width", 300, "display.max_columns", None, "display.max_rows", None):
        print(f"\nPass rules: {rules} and gap > 0 in both periods. gap = tool expR - matched control expR.")
        print(tab.to_string(index=False))
        print("\nGap vs control by entry year (R):\n" + by_year.to_string())
    print(f"\nPASSED: {', '.join(tab.loc[tab.PASS, 'tool']) or 'none'}  ({int(tab.PASS.sum())} of {len(tab)} tested)")


def row(name, trades, split):
    cut = pd.Timestamp(split)
    out = {"variant": name}
    for label, part in (("all", trades), ("pre", [t for t in trades if t.entry_date < cut]),
                        ("post", [t for t in trades if t.entry_date >= cut])):
        s = summarize(part)
        out[f"{label}_n"] = s.get("trades", 0)
        out[f"{label}_expR"] = s.get("expectancy_R", np.nan)
        if label == "all":
            out["win"] = s.get("win_rate", np.nan)
            out["pf"] = s.get("profit_factor", np.nan)
            out["maxDD_R"] = s.get("max_drawdown_R", np.nan)
    return out


def by_year(results):
    """Trades and expectancy per entry year, every variant side by side."""
    cols = {}
    for name, trades in results:
        df = trades_frame([t for t in trades if not t.exit_reason.startswith("open")])
        if df.empty:
            continue
        g = df.groupby(pd.to_datetime(df["entry_date"]).dt.year)["r"]
        key = name.split(".")[0]
        cols[(key, "n")] = g.count()
        cols[(key, "expR")] = g.mean().round(3)
    if cols:
        print("\nBy entry year (closed trades):\n" + pd.DataFrame(cols).to_string())


def breakdown(trades):
    df = trades_frame([t for t in trades if not t.exit_reason.startswith("open")])
    if df.empty:
        return
    df["year"] = pd.to_datetime(df["entry_date"]).dt.year
    df["risk_bucket"] = pd.cut(df["risk_pct"] * 100, [0, 3, 5, 7, 10, 100])
    df["depth_bucket"] = pd.cut(df["depth"], [0, .382, .5, .618, 1])
    for col in ("year", "exit_reason", "risk_bucket", "depth_bucket"):
        g = df.groupby(col, observed=True)["r"].agg(trades="count", expR="mean", win=lambda r: (r > 0).mean())
        print(f"\n  by {col}:\n" + g.round(3).to_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", choices=list(EXPERIMENTS) + list(LIBRARY_EXPERIMENTS))
    ap.add_argument("--years", type=float, default=10)
    ap.add_argument("--split", default="2021-01-01")
    ap.add_argument("--tickers", nargs="*")
    ap.add_argument("--universe", help="ticker file (default universe.txt)")
    args = ap.parse_args()

    tickers = [t.upper() for t in args.tickers] if args.tickers else load_universe(args.universe or None)
    data = {}
    for t in tickers:
        try:
            df = drop_unfinished_bar(load_bars(t, years=args.years))
            if len(df) > 250:
                data[t] = df
        except Exception as e:
            print(f"skip {t}: {type(e).__name__}")
    print(f"{args.name}: {len(data)} tickers, {args.years:g} years, split {args.split}\n")

    if args.name in LIBRARY_EXPERIMENTS:
        bench = drop_unfinished_bar(load_bars("SPY", years=args.years))["close"]
        print(f"Data through {max(df.index[-1] for df in data.values()).date()}; SPY benchmark through {bench.index[-1].date()}")
        run_library(args.name, data, args.split, bench)
        return

    rows, first, results = [], None, []
    for name, make in EXPERIMENTS[args.name].items():
        trades = []
        for t, df in data.items():
            trades += simulate_ticker(make(), t, df)
        rows.append(row(name, trades, args.split))
        results.append((name, trades))
        first = first or trades
    with pd.option_context("display.width", 250, "display.max_columns", None):
        print(pd.DataFrame(rows).to_string(index=False))
        by_year(results)
    print("\nBreakdown of the first variant:")
    breakdown(first)


if __name__ == "__main__":
    main()
