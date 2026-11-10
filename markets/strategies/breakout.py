"""Breakout / momentum entries, tested with the same shared template as the FibAlgo screen
(see library.py: stop at a structure level - 0.1 ATR, risk 0.5-5 ATR, exit at +2R, the stop,
or after 20 bars) and the same matched random control. All need the control's uptrend
filter ("up" context), so the control is random entries in the same uptrends.

Rules fixed before running (research/log.md, 2026-11-10 "Breakout/momentum screen"):
- new_52w_high: close above the highest close of the prior 252 bars. Stop below the 10-bar low.
- squeeze_breakout: the prior 20 bars spanned <= 4 x ATR (a tight range), and today closes
  above their high. Stop below their low.
- momentum_top_decile: the stock's 126-bar return enters the top 10% of the universe that day
  (cross-sectional rank, set by experiment.py). Stop below the 10-bar low.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .library import LibraryTool


class New52WeekHigh(LibraryTool):
    name, context, page = "breakout_52w_high", "up", ""
    min_bars = 260

    def detect(self, df):
        c = df["close"]
        prior_max = c.rolling(252).max().shift(1).to_numpy()
        low10 = df["low"].rolling(10).min().to_numpy()
        with np.errstate(invalid="ignore"):
            hit = self.c > prior_max
        for i in np.flatnonzero(hit):
            self.add_event(i, low10[i])


class SqueezeBreakout(LibraryTool):
    name, context, page = "breakout_squeeze", "up", ""

    def detect(self, df):
        hi = df["high"].rolling(20).max().shift(1).to_numpy()
        lo = df["low"].rolling(20).min().shift(1).to_numpy()
        atr_prev = np.r_[np.nan, self.atr[:-1]]
        with np.errstate(invalid="ignore"):
            hit = (hi - lo <= 4 * atr_prev) & (self.c > hi)
        for i in np.flatnonzero(hit):
            self.add_event(i, lo[i])


class MomentumTopDecile(LibraryTool):
    """Needs `rank`: a Series of the stock's cross-sectional percentile (0-1) of 126-bar return."""
    name, context, page = "momentum_top_decile", "up", ""
    needs_ranks = True
    rank: pd.Series | None = None

    def detect(self, df):
        if self.rank is None:
            return
        r = self.rank.reindex(df.index).to_numpy()
        low10 = df["low"].rolling(10).min().to_numpy()
        with np.errstate(invalid="ignore"):
            enter = (r >= 0.9) & ~(np.r_[np.nan, r[:-1]] >= 0.9)
        for i in np.flatnonzero(enter & np.isfinite(r)):
            self.add_event(i, low10[i])


def momentum_ranks(data: dict[str, pd.DataFrame], lookback: int = 126, min_names: int = 20) -> dict[str, pd.Series]:
    """Each day, every stock's percentile rank of its `lookback`-bar return among the stocks
    with data that day. Uses closes up to that day only."""
    rets = pd.DataFrame({t: df["close"].pct_change(lookback) for t, df in data.items()})
    ranks = rets.rank(axis=1, pct=True)
    ranks[rets.notna().sum(axis=1) < min_names] = np.nan
    return {t: ranks[t] for t in data}


BREAKOUT_TOOLS = [New52WeekHigh, SqueezeBreakout, MomentumTopDecile]
