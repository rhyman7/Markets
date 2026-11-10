"""One-off check of Alpaca data against Yahoo. Run from Actions -> Data check.

Answers: do the keys work; does the free plan return full-market (SIP) history or only
IEX; do Alpaca's adjusted daily bars match Yahoo; how far back do hourly bars go; and
does asking for the latest 15 minutes of SIP data fail (it should on the free plan).
Never prints the keys.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from markets.data.loader import _fetch_yfinance

URL = "https://data.alpaca.markets/v2/stocks/{t}/bars"
HEAD = {"APCA-API-KEY-ID": os.environ.get("ALPACA_API_KEY", ""),
        "APCA-API-SECRET-KEY": os.environ.get("ALPACA_API_SECRET", "")}
TICKERS = ["AAPL", "JPM", "SHOP", "DINO", "SAIA"]


def bars(t, feed, timeframe="1Day", start="2016-01-01", end=None):
    params = {"timeframe": timeframe, "start": start, "adjustment": "all", "feed": feed, "limit": 10000}
    if end:
        params["end"] = end
    rows, token = [], None
    while True:
        if token:
            params["page_token"] = token
        r = requests.get(URL.format(t=t), params=params, headers=HEAD, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        body = r.json()
        rows += body.get("bars") or []
        token = body.get("next_page_token")
        if not token:
            break
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df["t"])
    return df.rename(columns={"c": "close", "v": "volume"})


def main():
    print(f"Keys present: {bool(HEAD['APCA-API-KEY-ID'])}, key ID starts with "
          f"{HEAD['APCA-API-KEY-ID'][:2] or '-'} (PK = paper)\n")
    safe_end = (datetime.now(timezone.utc) - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")

    print("1. Daily bars since 2016 vs Yahoo (adjusted closes, matched days)")
    out = []
    for t in TICKERS:
        y = _fetch_yfinance(t, datetime(2016, 1, 1).date())
        y.index = y.index.normalize()
        for feed in ("iex", "sip"):
            try:
                a = bars(t, feed, end=safe_end)
            except Exception as e:
                out.append({"ticker": t, "feed": feed, "error": str(e)[:80]})
                continue
            a.index = a.index.tz_convert("America/New_York").tz_localize(None).normalize()
            j = a[["close", "volume"]].join(y[["close", "volume"]], rsuffix="_y", how="inner")
            diff = (j["close"] / j["close_y"] - 1).abs() * 100
            out.append({"ticker": t, "feed": feed, "first": a.index[0].date(), "rows": len(a),
                        "yahoo_rows": len(y), "matched": len(j),
                        "median_close_diff_%": round(diff.median(), 3),
                        "p99_close_diff_%": round(diff.quantile(.99), 3),
                        "volume_vs_yahoo": round((j["volume"] / j["volume_y"]).median(), 3)})
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print(pd.DataFrame(out).to_string(index=False))

    print("\n2. Hourly SIP bars: earliest available and a recent day")
    for start, end in (("2016-01-04", "2016-01-06"), ("2021-01-04", "2021-01-06")):
        try:
            h = bars("AAPL", "sip", "1Hour", start, end)
            print(f"  AAPL 1Hour {start}..{end}: {len(h)} bars")
        except Exception as e:
            print(f"  AAPL 1Hour {start}..{end}: {e}")

    print("\n3. SIP request including the latest 15 minutes (expected to fail on free plan)")
    try:
        r = bars("AAPL", "sip", "1Min", (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        print(f"  returned {len(r)} bars (no error)")
    except Exception as e:
        print(f"  {e}")


if __name__ == "__main__":
    main()
