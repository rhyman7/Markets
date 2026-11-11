"""Build the setups dashboard: every rule's current setups with entry, stop and targets.

    python dashboard.py                 # scan universe.txt + universe_midcap.txt -> site/
    python dashboard.py --out site --universes universe.txt

Writes site/index.html and site/data.json. On GitHub the "Dashboard" workflow runs this
every 30 minutes during the session and after the close, and publishes site/ with Pages.
Rules only use completed daily bars; an unfinished bar only supplies the latest price.
See markets/dashboard.py for what each status means.
"""
from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from markets.dashboard import build, write_site
from markets.data.loader import load_bars, load_universe


def load_all(tickers: list[str], workers: int = 4) -> tuple[dict[str, pd.DataFrame], list[str]]:
    def one(t):
        try:
            return t, load_bars(t, years=2, refresh=True), None
        except Exception as e:  # network, bad ticker, provider outage
            return t, None, f"{t} ({type(e).__name__})"
    data, failed = {}, []
    with ThreadPoolExecutor(workers) as pool:
        for t, df, err in pool.map(one, tickers):
            if err or df is None or df.empty:
                failed.append(err or f"{t} (no data)")
            else:
                data[t] = df
    return data, failed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universes", nargs="*", default=["universe.txt", "universe_midcap.txt"])
    ap.add_argument("--signals", default="journal/signals.csv")
    ap.add_argument("--out", default="site")
    args = ap.parse_args()

    lists = {Path(u).stem: load_universe(u) for u in args.universes}
    sig_path = Path(args.signals)
    signals = pd.read_csv(sig_path, dtype=str) if sig_path.exists() else None
    extra = [] if signals is None else [t.upper() for t in signals["ticker"].dropna()]
    wanted = list(dict.fromkeys([t for ts in lists.values() for t in ts] + extra + ["SPY"]))
    data, failed = load_all(wanted)
    if not data:
        raise SystemExit(f"No data loaded for any of {len(wanted)} tickers; keeping the last published page.")

    universes = {tag: {t: data[t] for t in ts if t in data} for tag, ts in lists.items()}
    payload = build(universes, signals=signals, benchmark=data["SPY"]["close"] if "SPY" in data else None,
                    provider=(os.environ.get("DATA_PROVIDER") or "yfinance").lower(), failed=failed,
                    extra_data={t: data[t] for t in extra if t in data})
    path = write_site(payload, args.out)
    n = {s: sum(r["status"] == s for r in payload["rows"]) for s in ("signal", "limit", "forming", "watch")}
    print(f"Data through {payload['data_through']} (session unfinished: {payload['session_unfinished']}). "
          f"{n['signal']} signals, {n['limit']} limits, {n['forming']} forming, {n['watch']} watching. Wrote {path}")
    if failed:
        print(f"Could not load {len(failed)}: {', '.join(failed)}")


if __name__ == "__main__":
    main()
