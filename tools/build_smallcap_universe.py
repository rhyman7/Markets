"""Write universe_smallcap.txt: S&P SmallCap 600 members per Wikipedia, minus any ticker
already in universe.txt or universe_midcap.txt, so the holdout uses stocks never tested.

    python -m tools.build_smallcap_universe     (needs lxml; run by the "Build universe" workflow)
"""
from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from markets.data.loader import load_universe

ROOT = Path(__file__).resolve().parents[1]
URL = "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"


def main() -> None:
    html = requests.get(URL, timeout=30, headers={"User-Agent": "Markets research script"}).text
    table = next(t for t in pd.read_html(io.StringIO(html)) if "Symbol" in t.columns)
    tickers = sorted({str(s).strip().upper().replace(".", "-") for s in table["Symbol"].dropna()})
    used = set(load_universe(ROOT / "universe.txt")) | set(load_universe(ROOT / "universe_midcap.txt"))
    fresh = [t for t in tickers if t not in used]
    header = (f"# S&P SmallCap 600 constituents per Wikipedia, fetched {date.today().isoformat()}. Holdout\n"
              f"# universe for the FibAlgo library screen: {len(tickers)} listed, {len(tickers) - len(fresh)} dropped as\n"
              f"# already in universe.txt / universe_midcap.txt. Today's list used for all history (survivorship bias).\n")
    lines = [" ".join(fresh[i:i + 20]) for i in range(0, len(fresh), 20)]
    (ROOT / "universe_smallcap.txt").write_text(header + "\n".join(lines) + "\n")
    print(f"universe_smallcap.txt: {len(fresh)} tickers ({len(tickers)} listed)")


if __name__ == "__main__":
    main()
