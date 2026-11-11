import json
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from markets.backtest import simulate_ticker
from markets.dashboard import MODELS, PRIMARY, build, split_unfinished, track_signal, write_site
from markets.strategies import STRATEGIES
from markets.strategies.base import Setup, Strategy

ET = ZoneInfo("America/New_York")
LAST = "2026-11-11"


def walk(seed, n=420, steps=8, end=LAST):
    """Random walk with a mild upward drift, so uptrend filters let some stocks through."""
    r = np.random.default_rng(seed)
    start = float(r.uniform(40, 300))
    sd, drift = start * 0.02, start * r.uniform(0.0, 0.002)
    p = np.maximum(start + np.cumsum(r.normal(drift / steps, sd / np.sqrt(steps), n * steps)).reshape(n, steps), 5)
    o = np.r_[start, p[:-1, -1]] + r.normal(0, sd * 0.2, n)
    h, l = np.maximum(p.max(1), o), np.minimum(p.min(1), o)
    v = 2e6 * np.exp(r.normal(0, 0.6, n))
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": p[:, -1], "volume": v},
                        index=pd.bdate_range(end=end, periods=n))


def at(hhmm):
    return datetime.fromisoformat(f"{LAST}T{hhmm}:00").replace(tzinfo=ET)


def test_every_registered_strategy_has_evidence():
    keys = {m.key for m in MODELS}
    assert set(STRATEGIES) - {"trend_baseline"} <= keys
    assert [m.key for m in MODELS if m.verdict == "passed"] == [PRIMARY]
    for m in MODELS:
        if m.key != PRIMARY:
            assert m.verdict in ("no edge", "worse than random")
            assert m.gap < 0.10      # nothing else reached the screen's +0.10R bar
    assert sum(m.verdict == "worse than random" for m in MODELS) == 5


def test_split_unfinished():
    df = walk(1, n=30)
    done, dropped = split_unfinished(df, at("14:00"))
    assert dropped and len(done) == len(df) - 1
    done, dropped = split_unfinished(df, at("16:20"))
    assert not dropped and len(done) == len(df)
    done, dropped = split_unfinished(df.iloc[:-1], at("10:00"))   # today's bar not in the data yet
    assert not dropped and len(done) == len(df) - 1


class OneShot(Strategy):
    """Fires once, at bar `k`, with fixed stop and targets."""
    name, min_bars = "one_shot", 5

    def __init__(self, k, stop, t1, t2):
        self.k, self.stop, self.t1, self.t2 = k, stop, t1, t2

    def setup(self, ticker, df, i):
        if i != self.k:
            return None
        c = float(df["close"].iat[i])
        return Setup(ticker, df.index[i], True, True, c, c, self.stop, [self.t1, self.t2])


def test_tracker_matches_backtester():
    checked = 0
    for seed in range(40):
        df = walk(seed, n=160)
        k = 60
        c = float(df["close"].iat[k])
        stop, t1, t2 = c * 0.93, c * 1.05, c * 1.12
        trades = simulate_ticker(OneShot(k, stop, t1, t2), "X", df, cost=0.0)
        got = track_signal(df, df.index[k], stop, t1, t2)
        if not trades:
            assert got["state"] == "skipped"
            continue
        t = trades[0]
        assert got["entry"] == round(t.entry, 2)
        if t.exit_reason.startswith("open"):
            assert got["state"] == "open"
        else:
            assert got["state"] == "closed" and got["exit_reason"] == t.exit_reason
            assert got["exit_date"] == str(t.exit_date.date())
        assert abs(got["r"] - t.r) < 0.006
        checked += 1
    assert checked > 30


def test_tracker_pending_and_unfinished_bar():
    df = walk(3, n=100)
    assert track_signal(df, df.index[-1], 1.0, 1e9, 2e9)["state"] == "pending"
    # 40 bars in, last bar unfinished: the time exit must wait for a completed bar
    k = len(df) - 41
    open_ = track_signal(df, df.index[k], 0.01, 1e9, 2e9, n_done=len(df) - 1)
    assert open_["state"] == "open" and open_["bars_left"] == 1
    assert track_signal(df, df.index[k], 0.01, 1e9, 2e9)["exit_reason"] == "time"


def _universes(n=25):
    return {"universe": {f"L{i}": walk(i) for i in range(n)}, "universe_midcap": {f"M{i}": walk(500 + i) for i in range(n)}}


def test_rules_never_see_the_unfinished_bar():
    uni = _universes()
    intraday = build(uni, now=at("13:00"), benchmark=walk(999)["close"])
    assert intraday["session_unfinished"] and intraday["data_through"] == "2026-11-10"
    # Same data with today's bar removed: every confirmed row must be identical apart from `live`.
    cut = {tag: {t: df.iloc[:-1] for t, df in d.items()} for tag, d in uni.items()}
    prior = build(cut, now=at("13:00"), benchmark=walk(999)["close"].iloc[:-1])
    strip = lambda rows: [{k: v for k, v in r.items() if k != "live"} for r in rows if r["status"] != "forming"]
    assert strip(intraday["rows"]) == strip(prior["rows"])
    assert not [r for r in prior["rows"] if r["status"] == "forming"]
    after = build(uni, now=at("16:30"))
    assert not after["session_unfinished"] and after["data_through"] == LAST


def test_rows_and_site(tmp_path):
    uni = _universes(40)
    sig = pd.DataFrame([{"date": "2026-11-03", "ticker": "L1", "strategy": PRIMARY, "universe": "universe",
                         "status": "TRIGGERED", "close": "100", "entry": "100", "stop": "1", "t1": "100000",
                         "t2": "200000", "risk_pct": "5", "notes": "", "taken": np.nan}])
    p = build(uni, signals=sig, now=at("16:30"), benchmark=walk(999)["close"], provider="alpaca")
    assert p["rows"], "synthetic data should produce some setups"
    keys = {m["key"] for m in p["models"]}
    for r in p["rows"]:
        assert r["model"] in keys and r["status"] in ("signal", "limit", "watch", "forming")
        assert r["stop"] < r["entry"] <= r["t1"] <= r["t2"]
        if r["universe"] != "universe":            # library rules were only tested on large caps
            assert r["model"].startswith("fib_")
        if r["model"] == PRIMARY and r["status"] == "watch":
            assert r["zone_bot"] <= r["close"] <= r["zone_top"] and r["checks"]["reversal_candle"] is False
    assert p["tracker"][0]["state"] == "open" and p["tracker"][0]["taken"] is None
    index = write_site(p, tmp_path)
    assert json.loads((tmp_path / "data.json").read_text())["rows"] == p["rows"]
    html = index.read_text()
    assert "/*__DATA__*/" not in html and '"generated_at"' in html
