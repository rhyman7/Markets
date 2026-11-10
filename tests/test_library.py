import numpy as np
import pandas as pd
import pytest

from markets.backtest import simulate_ticker
from markets.strategies import breakout as brk
from markets.strategies import library as lib
from markets.strategies.base import Setup, Strategy


def walk(seed, n=700, steps=8, sd=2.0, start=200.0, gap_sd=0.6):
    """Arithmetic random walk built from intrabar steps, with small overnight gaps."""
    r = np.random.default_rng(seed)
    p = start + np.cumsum(r.normal(0, sd / np.sqrt(steps), n * steps)).reshape(n, steps)
    gaps = np.cumsum(r.normal(0, gap_sd, n))
    p = p + gaps[:, None]
    o = np.r_[start, p[:-1, -1]] + r.normal(0, gap_sd, n)
    h, l = np.maximum(p.max(1), o), np.minimum(p.min(1), o)
    v = 2e6 * np.exp(r.normal(0, 0.6, n))
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": p[:, -1], "volume": v},
                        index=pd.bdate_range("2018-01-01", periods=n))


def make(tool, bench):
    st = tool()
    if tool is lib.ComparativeStrength:
        st.benchmark = bench
    if getattr(tool, "needs_ranks", False):
        st.rank = pd.Series(np.random.default_rng(7).random(len(bench)), index=bench.index)
    return st


@pytest.mark.parametrize("tool", lib.ALL_TOOLS + brk.BREAKOUT_TOOLS, ids=lambda t: t.name)
def test_no_lookahead(tool):
    """Signals and orders up to bar k must not change when later bars are added."""
    bench = walk(99)["close"]
    for seed in (1, 2):
        df = walk(seed)
        full = make(tool, bench)
        full.prepare(df)
        for k in (260, 333, 420, 517, 650):
            part = make(tool, bench)
            part.prepare(df.iloc[:k])
            for attr in ("event", "ev_stop", "ev_t1", "lim", "lim_stop"):
                np.testing.assert_array_equal(getattr(part, attr), getattr(full, attr)[:k], err_msg=f"{attr} at k={k}")


def test_every_tool_produces_signals_on_random_data():
    bench = walk(99, n=1500)["close"]
    rare = {"wyckoff_accumulation", "wyckoff_selling_climax", "wyckoff_reaccumulation", "ict_market_maker_buy"}
    for tool in lib.ALL_TOOLS + brk.BREAKOUT_TOOLS:
        hits = 0
        for seed in range(4):
            st = make(tool, bench)
            st.prepare(walk(seed, n=1500))
            hits += st.event.sum() + np.isfinite(st.lim).sum()
        assert hits > 0 or tool.name in rare, tool.name


def bars(rows):
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], dtype=float)
    df["volume"] = 2_000_000.0
    df.index = pd.bdate_range("2020-01-01", periods=len(df))
    return df


def test_fvg_zone_and_limit_order():
    flat = [[100, 101, 99, 100]] * 30
    df = bars(flat + [[100, 102, 99.5, 101.5], [101.5, 108, 101.4, 107.5], [107.5, 110, 104, 109],
                      [109, 110, 106, 107], [107, 108, 102.5, 103]])
    st = lib.FairValueGap()
    st.prepare(df)
    i = 32                                    # gap: low[32]=104 > high[30]=102
    ce = (104 + 102) / 2
    assert st.lim[i] == pytest.approx(ce) and st.lim_stop[i] == pytest.approx(102)
    assert st.lim[i + 1] == pytest.approx(ce)
    assert np.isnan(st.lim[i + 2])            # bar 34's low (102.5) touched the CE: zone used up
    assert np.isnan(st.lim[i - 1])


def test_key_level_sweep_fires_once_per_week():
    rows = [[100, 101, 99, 100]] * 5 + [[100, 100.5, 98, 99.5], [99.5, 100, 97, 99.2], [99, 99.5, 98.5, 99]]
    df = bars(rows)                            # 2020-01-01 is a Wednesday: first 3 bars are week 1
    st = lib.KeyLevelSweep()
    st.prepare(df)
    weekly_hits = [i for i in np.flatnonzero(st.event)]
    assert weekly_hits, "a low below last week's low that closes back above it should fire"
    weeks = df.index[weekly_hits].to_period("W")
    assert len(set(zip(weeks, ["W"] * len(weeks)))) == len(weeks)


class _Fixed(Strategy):
    """One limit order on a chosen bar, for engine tests."""
    min_bars = 0

    def __init__(self, at, limit, stop, target, max_hold=None):
        self.at, self.limit, self.stop, self.target = at, limit, stop, target
        if max_hold:
            self.max_hold = max_hold

    def setup(self, ticker, df, i):
        if i != self.at:
            return None
        e = self.limit if self.limit is not None else df["close"].iat[i]
        return Setup(ticker, df.index[i], True, True, e, e, self.stop, [self.target, self.target], limit=self.limit)


def test_limit_fill_bar_high_does_not_count_for_target():
    # Bar 1 opens at 105, runs to 112 (before the fill), drops to 99.5 and fills the 100 limit,
    # closes at 101. The 110 target must NOT count on that bar.
    df = bars([[104, 105, 103, 104], [105, 112, 99.5, 101], [101, 102, 100.5, 101.5], [101.5, 102, 101, 101.8]])
    tr = simulate_ticker(_Fixed(0, 100.0, 95.0, 110.0), "T", df)
    assert tr and tr[0].exit_reason != "target 2" and tr[0].entry == 100.0
    # Same bar but closing above the target: the path after the fill reached it.
    df2 = bars([[104, 105, 103, 104], [105, 112, 99.5, 111], [111, 112, 110.5, 111]])
    tr2 = simulate_ticker(_Fixed(0, 100.0, 95.0, 110.0), "T", df2)
    assert tr2[0].exit_reason == "target 2" and tr2[0].r == pytest.approx(2.0)


def test_strategy_max_hold_is_used():
    df = bars([[100, 100.5, 99.5, 100]] * 40)
    tr = simulate_ticker(_Fixed(0, None, 95.0, 110.0, max_hold=5), "T", df)
    assert tr[0].exit_reason == "time" and tr[0].bars_held == 5


def test_shared_template_stop_floor_and_target():
    df = walk(3, n=600)
    st = lib.VSAStoppingVolume()
    st.prepare(df)
    for i in np.flatnonzero(st.event):
        if i < st.min_bars:
            continue
        s = st.setup("T", df, i)
        if s is None:
            continue
        a = st.atr[i]
        assert s.entry - s.stop >= lib.MIN_RISK * a - 1e-9
        assert s.entry - s.stop <= lib.MAX_RISK * a + 1e-9
        assert s.targets[-1] == pytest.approx(s.entry + 2 * (s.entry - s.stop))


def test_matched_control_copies_mechanics():
    class T:
        def __init__(self, risk, gap):
            self.risk_atr, self.limit_gap_atr = risk, gap
    ctl = lib.matched_control(lib.FairValueGap, [T(0.6, 0.5), T(0.7, 0.4), T(0.9, 0.6)])
    assert ctl.context == "up" and ctl.limit_atr == 0.5 and ctl.stop_atr == 0.75
    ctl2 = lib.matched_control(lib.SellingClimax, [T(2.1, np.nan), T(1.9, np.nan)])
    assert ctl2.context == "any" and ctl2.limit_atr is None and ctl2.stop_atr == 2.0


def test_costs_come_out_of_r():
    # Buy at 100 (next open), stop 95 (risk 5), time exit at 101 after 3 bars.
    df = bars([[100, 100.5, 99.5, 100]] * 3 + [[101, 101.2, 100.8, 101]] * 5)
    free = simulate_ticker(_Fixed(0, None, 95.0, 120.0, max_hold=3), "T", df, cost=0.0)[0]
    paid = simulate_ticker(_Fixed(0, None, 95.0, 120.0, max_hold=3), "T", df, cost=0.001)[0]
    assert free.exit_reason == "time"
    assert free.r - paid.r == pytest.approx(0.001 * (free.entry + df["close"].iat[3]) / 5)


def test_momentum_ranks_use_same_day_closes_only():
    data = {f"T{k}": walk(k, n=400) for k in range(25)}
    full = brk.momentum_ranks(data)
    part = brk.momentum_ranks({t: df.iloc[:300] for t, df in data.items()})
    for t in data:
        pd.testing.assert_series_equal(part[t], full[t].iloc[:300], check_names=False)
    vals = pd.concat(full.values()).dropna()
    assert vals.between(0, 1).all() and len(vals) > 0
