"""Crypto data path: Coinbase candles -> the same bar frame the stock strategies use."""
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

import experiment
from markets.data import loader
from markets.strategies import TrendBaseline


class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body

    def raise_for_status(self):
        assert self.status_code == 200


def test_coinbase_candles_parse_page_and_drop_today(monkeypatch):
    today = datetime.utcnow().date()
    first = today - timedelta(days=450)            # the coin's first trading day
    calls = []

    def fake_get(url, params, headers, timeout):
        calls.append(params)
        lo, hi = (date.fromisoformat(params[k][:10]) for k in ("start", "end"))
        assert (hi - lo).days <= 299 and hi < today
        days = [lo + timedelta(days=k) for k in range((hi - lo).days + 1) if lo + timedelta(days=k) >= first]
        # Coinbase order: [time, low, high, open, close, volume], newest first
        return FakeResponse(200, [[int(pd.Timestamp(d).timestamp()), 9.0, 12.0, 10.0, 11.0, 100.0] for d in reversed(days)])

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr(loader.time, "sleep", lambda s: None)
    df = loader._fetch_coinbase("TEST-USD", today - timedelta(days=3660))
    assert list(df.columns) == loader.COLUMNS
    assert len(df) == 450 and df.index.is_monotonic_increasing and not df.index.duplicated().any()
    assert df.index[0].date() == first and df.index[-1].date() == today - timedelta(days=1)
    assert (df["low"] == 9).all() and (df["high"] == 12).all() and (df["open"] == 10).all()
    assert (df["volume"] == 1100).all()            # 100 coins x $11 close = dollar volume
    assert len(calls) == 3                         # two pages with data, then an empty one stops it


def test_coinbase_unlisted_pair_is_empty(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResponse(404, {"message": "NotFound"}))
    assert loader._fetch_coinbase("NOPE-USD", date(2020, 1, 1)).empty


def test_crypto_tickers_route_to_coinbase():
    assert loader.is_crypto("btc-usd") and not loader.is_crypto("BRK-B") and not loader.is_crypto("USD")


def _coin(seed, n=1500, price=0.0001):
    rng = np.random.default_rng(seed)
    c = price * np.exp(np.cumsum(rng.normal(0.001, 0.04, n)))
    o = np.r_[c[0], c[:-1]]
    df = pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.02, "low": np.minimum(o, c) * 0.98,
                       "close": c}, index=pd.date_range("2021-01-01", periods=n))
    df["volume"] = 5e6
    return df


def test_baseline_filters_are_parameters():
    df = _coin(1)
    from markets.backtest import simulate_ticker
    assert simulate_ticker(TrendBaseline(), "X-USD", df) == []                       # sub-$10 coin: stock filter blocks it
    assert simulate_ticker(TrendBaseline(**experiment.CRYPTO_FILTERS), "X-USD", df)  # crypto filter lets it trade


def test_fib_crypto_runs_end_to_end(capsys):
    experiment.run_crypto({f"C{k}-USD": _coin(k) for k in range(12)}, "2023-01-01")
    out = capsys.readouterr().out
    assert "matched control" in out and "RESULT:" in out
