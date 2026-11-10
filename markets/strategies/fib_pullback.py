"""Fibonacci pullback, long only, daily bars.

Rules (keep in sync with README and the project instructions):
1. Universe: price > $10, 50-day average volume > 1M shares.
2. Uptrend: 50-day SMA rising (vs 10 bars ago) and above the 200-day SMA;
   price no more than 3% below the 50-day.
3. Swing: highest high 3-60 bars back; swing low = lowest low in the 80 bars
   before it; move >= 10%. Fibonacci levels run from that low to that high.
4. Zone: price 30-70% retraced, and the pullback never traded below 78.6%.
5. Entry: close above the prior bar's high.
6. Stop: 0.5% below the next Fibonacci level beneath the pullback low.
7. Targets: T1 = swing high, T2 = 127.2% extension.
8. Qualifies only if reward/risk to T2 >= 2.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .base import Setup, Strategy

RETRACEMENTS = [0.236, 0.382, 0.5, 0.618, 0.786]


@dataclass
class FibParams:
    min_price: float = 10.0
    min_avg_volume: float = 1_000_000
    max_below_ma50: float = 0.03
    ma_slope_lookback: int = 10
    high_min_age: int = 3
    high_max_age: int = 60
    low_lookback: int = 80
    min_move: float = 0.10
    zone_min: float = 0.30
    zone_max: float = 0.70
    max_retrace: float = 0.786
    stop_buffer: float = 0.005
    extension: float = 1.272
    min_rr: float = 2.0


class FibPullback(Strategy):
    name = "fib_pullback"
    min_bars = 220

    def __init__(self, params: FibParams | None = None):
        self.p = params or FibParams()

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ma50"] = df["close"].rolling(50).mean()
        df["ma200"] = df["close"].rolling(200).mean()
        df["vol50"] = df["volume"].rolling(50).mean()
        return df

    def setup(self, ticker: str, df: pd.DataFrame, i: int) -> Setup | None:
        p = self.p
        if i < max(self.min_bars, p.high_max_age + p.low_lookback):
            return None
        o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
        ma50, ma200, vol50 = df["ma50"].iat[i], df["ma200"].iat[i], df["vol50"].iat[i]
        px = c[i]

        # 1-2: universe and trend
        if px < p.min_price or vol50 < p.min_avg_volume:
            return None
        if not (ma50 > ma200 and ma50 > df["ma50"].iat[i - p.ma_slope_lookback]
                and px >= ma50 * (1 - p.max_below_ma50)):
            return None

        # 3: swing
        hi_start, hi_end = i - p.high_max_age, i - p.high_min_age
        hi_idx = hi_start + int(h[hi_start:hi_end + 1].argmax())
        lo_start = max(0, hi_idx - p.low_lookback)
        lo_idx = lo_start + int(l[lo_start:hi_idx].argmin())
        swing_high, swing_low = h[hi_idx], l[lo_idx]
        rng = swing_high - swing_low
        if rng <= 0 or swing_high / swing_low - 1 < p.min_move:
            return None

        # 4: zone
        depth = (swing_high - px) / rng
        pull_low = l[hi_idx + 1:i + 1].min()
        max_depth = (swing_high - pull_low) / rng
        if not (p.zone_min <= depth <= p.zone_max) or max_depth >= p.max_retrace:
            return None

        level = lambda r: swing_high - r * rng
        deeper = next((r for r in RETRACEMENTS if r > max_depth + 0.005), RETRACEMENTS[-1])
        stop = level(deeper) * (1 - p.stop_buffer)
        trigger = h[i - 1]
        triggered = px > trigger
        entry = px if triggered else trigger
        t1, t2 = swing_high, swing_low + p.extension * rng

        s = Setup(
            ticker=ticker, date=df.index[i], triggered=triggered, qualifies=False,
            entry=float(entry), trigger=float(trigger), stop=float(stop),
            targets=[float(t1), float(t2)],
            levels={"swing_low": float(swing_low), "swing_high": float(swing_high),
                    **{f"fib_{r:.3f}": float(level(r)) for r in RETRACEMENTS},
                    "ma50": float(ma50), "depth": float(depth), "max_depth": float(max_depth)},
            notes=f"swing {df.index[lo_idx].date()} -> {df.index[hi_idx].date()}, "
                  f"pullback low {max_depth:.0%}, stop under {deeper:.1%}",
        )
        s.qualifies = s.risk > 0 and s.rr(1) >= p.min_rr
        return s
