import numpy as np
import pandas as pd

from markets.backtest import simulate_ticker, summarize
from markets.strategies import FibPullback


def make_bars(closes, volume=2_000_000):
    closes = np.asarray(closes, dtype=float)
    idx = pd.bdate_range("2020-01-01", periods=len(closes))
    opens = np.r_[closes[0], closes[:-1]]
    return pd.DataFrame({"open": opens, "high": np.maximum(opens, closes) * 1.005,
                         "low": np.minimum(opens, closes) * 0.995, "close": closes,
                         "volume": volume}, index=idx)


def uptrend_with_pullback():
    base = list(np.linspace(50, 80, 230))       # long uptrend: MAs aligned and rising
    dip = list(np.linspace(80, 75, 10))         # swing low ~75
    rally = list(np.linspace(75, 100, 20))      # swing up to ~100
    pull = list(np.linspace(100, 87, 8))        # ~50% retrace
    bounce = [90.0]                             # close above prior high -> trigger
    return make_bars(base + dip + rally + pull + bounce)


def test_detects_triggered_setup():
    s = FibPullback()
    df = s.prepare(uptrend_with_pullback())
    setup = s.setup("TEST", df, len(df) - 1)
    assert setup is not None
    assert setup.triggered
    lv = setup.levels
    assert lv["swing_high"] > lv["fib_0.382"] > lv["fib_0.500"] > lv["fib_0.618"] > lv["swing_low"]
    assert setup.stop < lv["fib_0.500"] and setup.stop < setup.entry
    assert setup.targets[0] == lv["swing_high"] and setup.targets[1] > setup.targets[0]


def test_no_setup_in_downtrend():
    s = FibPullback()
    df = s.prepare(make_bars(np.linspace(100, 40, 300)))
    assert s.setup("DOWN", df, len(df) - 1) is None


def test_low_volume_filtered():
    s = FibPullback()
    df = uptrend_with_pullback()
    df["volume"] = 10_000
    df = s.prepare(df)
    assert s.setup("THIN", df, len(df) - 1) is None


def test_backtest_target_and_stop_paths():
    s = FibPullback()
    winner = uptrend_with_pullback()
    extra = make_bars(list(np.linspace(90, 125, 25)))  # rallies through T1 and T2
    extra.index = pd.bdate_range(winner.index[-1] + pd.offsets.BDay(), periods=len(extra))
    trades = simulate_ticker(s, "WIN", pd.concat([winner, extra]))
    assert trades and trades[-1].exit_reason == "target 2" and trades[-1].r > 1

    loser = uptrend_with_pullback()
    extra = make_bars(list(np.linspace(89, 65, 15)))     # collapses through the stop
    extra.index = pd.bdate_range(loser.index[-1] + pd.offsets.BDay(), periods=len(extra))
    trades = simulate_ticker(s, "LOSE", pd.concat([loser, extra]))
    last = trades[-1]
    assert last.exit_reason.startswith("stop") and last.r <= -0.99

    stats = summarize([last])
    assert stats["trades"] == 1 and stats["win_rate"] == 0


def test_no_edge_on_driftless_random_walks():
    """On prices with no drift and no memory, no strategy should make money.
    Guards against lookahead or fill bugs in the backtester."""
    from markets.strategies import TrendBaseline

    rng = np.random.default_rng(3)
    series = []
    while len(series) < 150:
        c = 200 + np.cumsum(rng.normal(0, 2.0, 1000))
        if c.min() > 20:
            series.append(make_bars(c))
    for strat in (FibPullback(), TrendBaseline(entry_rate=0.10)):
        trades = []
        for k, df in enumerate(series):
            trades += simulate_ticker(strat, f"R{k}", df)
        stats = summarize(trades)
        assert stats["trades"] > 150, (strat.name, stats)
        assert abs(stats["expectancy_R"]) < 0.15, (strat.name, stats)
