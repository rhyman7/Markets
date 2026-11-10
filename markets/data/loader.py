"""Daily price data with a local CSV cache.

Every strategy and tool gets bars through `load_bars`, so the data source can be
swapped in one place. Returned frames are indexed by date with columns:
open, high, low, close, volume (split/dividend adjusted).
"""
from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parents[2] / "cache"
COLUMNS = ["open", "high", "low", "close", "volume"]


def _load_env() -> None:
    env = Path(__file__).resolve().parents[2] / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def load_universe(path: str | Path | None = None) -> list[str]:
    path = Path(path) if path else Path(__file__).resolve().parents[2] / "universe.txt"
    tickers: list[str] = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0]
        tickers += [t.strip().upper() for t in line.split() if t.strip()]
    return list(dict.fromkeys(tickers))


def _fetch_yfinance(ticker: str, start: date) -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(ticker, start=start.isoformat(), auto_adjust=True, progress=False)
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[COLUMNS]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df


def _fetch_alpaca(ticker: str, start: date) -> pd.DataFrame:
    import requests

    key, secret = os.environ["ALPACA_API_KEY"], os.environ["ALPACA_API_SECRET"]
    url = f"https://data.alpaca.markets/v2/stocks/{ticker.replace('-', '.')}/bars"
    # SIP = all US exchanges. The free plan serves full SIP history but refuses the most
    # recent 15 minutes, so stop the request 16 minutes ago. (IEX alone is ~2-8% of
    # volume and only goes back to mid-2020; checked 2026-11-10.)
    end = (datetime.utcnow() - timedelta(minutes=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {"timeframe": "1Day", "start": start.isoformat(), "end": end, "adjustment": "all",
              "feed": os.environ.get("ALPACA_FEED", "sip"), "limit": 10000}
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    rows, token = [], None
    while True:
        if token:
            params["page_token"] = token
        for attempt in range(5):  # free plan: 200 calls/min, so back off on 429
            r = requests.get(url, params=params, headers=headers, timeout=30)
            if r.status_code != 429:
                break
            time.sleep(int(r.headers.get("Retry-After", 0) or 0) or 5 * (attempt + 1))
        r.raise_for_status()
        body = r.json()
        rows += body.get("bars") or []
        token = body.get("next_page_token")
        if not token:
            break
    if not rows:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(rows).rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    df.index = pd.to_datetime(df["t"]).dt.tz_localize(None).dt.normalize()
    return df[COLUMNS]


def load_bars(ticker: str, years: float = 3, refresh: bool = False) -> pd.DataFrame:
    """Daily bars for `ticker`, using the cache when it was refreshed today."""
    _load_env()
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{ticker.upper()}.csv"
    if path.exists() and not refresh:
        modified = datetime.fromtimestamp(path.stat().st_mtime).date()
        if modified == date.today():
            return pd.read_csv(path, index_col=0, parse_dates=True)
    start = date.today() - timedelta(days=int(365 * years) + 10)
    provider = (os.environ.get("DATA_PROVIDER") or "yfinance").lower()
    fetch = _fetch_alpaca if provider == "alpaca" else _fetch_yfinance
    df = fetch(ticker.upper(), start).dropna()
    if not df.empty:
        df.to_csv(path)
    return df
