"""Textbook Fibonacci retracement, long only, daily bars.

Follows the common 4-step description (identify trend, wait for the 38.2-61.8%
"golden zone", confirm, stop behind 78.6%, target the swing high / extensions).
Variants were fixed on 2026-11-10 before any results were seen:

- mode="limit"   (G): resting buy limit at the 0.5/0.618 midpoint (0.559 level).
- mode="pattern" (H): buy next open after a bullish engulfing or pin bar closes
                      inside the 38.2-61.8% zone.
- require_rsi    (I): also needs 14-day RSI < 40 at some point in the pullback and
                      RSI rising on the signal bar.
- require_ma     (J): also needs the 50-day SMA inside the 38.2-61.8% zone.

Shared rules: same universe and uptrend filters as fib_pullback; swing = highest
high 3-60 bars back with no higher high since, swing low = lowest low in the 80
bars before it, move >= 10%; pullback never below 78.6%. Stop 0.5% below the
78.6% level. T1 = swing high (half off, stop to breakeven), T2 = 127.2% extension.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .base import Setup, Strategy


@dataclass
class TextbookParams:
    mode: str = "limit"            # "limit" or "pattern"
    require_rsi: bool = False
    require_ma: bool = False
    limit_level: float = 0.559
    zone: tuple[float, float] = (0.382, 0.618)
    rsi_oversold: float = 40.0
    min_price: float = 10.0
    min_avg_volume: float = 1_000_000
    min_move: float = 0.10
    stop_level: float = 0.786
    stop_buffer: float = 0.005
    extension: float = 1.272


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def bullish_reversal(o, h, l, c, i) -> bool:
    body = abs(c[i] - o[i])
    rng = h[i] - l[i]
    engulfing = c[i - 1] < o[i - 1] and c[i] > o[i] and o[i] <= c[i - 1] and c[i] >= o[i - 1]
    lower_wick = min(o[i], c[i]) - l[i]
    upper_wick = h[i] - max(o[i], c[i])
    pin = rng > 0 and lower_wick >= 2 * body and upper_wick <= body and c[i] >= l[i] + 0.66 * rng
    return engulfing or pin


class FibTextbook(Strategy):
    name = "fib_textbook"
    min_bars = 220

    def __init__(self, params: TextbookParams | None = None):
        self.p = params or TextbookParams()

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ma50"] = df["close"].rolling(50).mean()
        df["ma200"] = df["close"].rolling(200).mean()
        df["vol50"] = df["volume"].rolling(50).mean()
        df["rsi14"] = rsi(df["close"])
        return df

    def setup(self, ticker: str, df: pd.DataFrame, i: int) -> Setup | None:
        p = self.p
        if i < self.min_bars:
            return None
        o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
        ma50, ma200 = df["ma50"].iat[i], df["ma200"].iat[i]
        px = c[i]
        if px < p.min_price or df["vol50"].iat[i] < p.min_avg_volume:
            return None
        if not (ma50 > ma200 and ma50 > df["ma50"].iat[i - 10]):
            return None

        hi_idx = (i - 60) + int(h[i - 60:i - 2].argmax())
        swing_high = h[hi_idx]
        if h[hi_idx + 1:i + 1].max() > swing_high:
            return None
        lo_start = max(0, hi_idx - 80)
        lo_idx = lo_start + int(l[lo_start:hi_idx].argmin())
        swing_low = l[lo_idx]
        rng = swing_high - swing_low
        if rng <= 0 or swing_high / swing_low - 1 < p.min_move:
            return None
        level = lambda r: swing_high - r * rng
        max_depth = (swing_high - l[hi_idx + 1:i + 1].min()) / rng
        if max_depth >= p.stop_level:
            return None

        zone_top, zone_bot = level(p.zone[0]), level(p.zone[1])
        if p.require_ma and not (zone_bot <= ma50 <= zone_top):
            return None
        if p.require_rsi:
            r = df["rsi14"].to_numpy()
            if np.nanmin(r[hi_idx + 1:i + 1]) >= p.rsi_oversold or not r[i] > r[i - 1]:
                return None

        limit = None
        if p.mode == "limit":
            limit = level(p.limit_level)
            entry = min(px, limit)
        else:
            if not (zone_bot <= px <= zone_top and bullish_reversal(o, h, l, c, i)):
                return None
            entry = px

        stop = level(p.stop_level) * (1 - p.stop_buffer)
        t1, t2 = swing_high, swing_low + p.extension * rng
        return Setup(
            ticker=ticker, date=df.index[i], triggered=True, qualifies=True,
            entry=float(entry), trigger=float(limit if limit else px), stop=float(stop),
            targets=[float(t1), float(t2)], limit=None if limit is None else float(limit),
            levels={"swing_low": float(swing_low), "swing_high": float(swing_high),
                    "fib_0.382": float(zone_top), "fib_0.618": float(zone_bot),
                    "fib_0.786": float(level(0.786)), "ma50": float(ma50),
                    "depth": float((swing_high - px) / rng)},
            notes=f"swing {df.index[lo_idx].date()} -> {df.index[hi_idx].date()}, "
                  + (f"buy limit {limit:.2f}" if limit else "reversal candle in zone"),
        )


class FibTextbookI(FibTextbook):
    """Variant I under its own name so the scanner can run it: reversal candle in the
    38.2-61.8% zone plus RSI < 40 during the pullback and rising on the signal bar.
    Rules frozen 2026-11-10 after it beat the control out of sample (mid-caps).
    Do not change these settings; test a new variant instead."""
    name = "fib_textbook_i"

    def __init__(self, params: TextbookParams | None = None):
        super().__init__(params or TextbookParams(mode="pattern", require_rsi=True))
