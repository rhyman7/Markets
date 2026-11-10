"""Baseline: random entries in the same uptrends, with fixed stop/targets.

Use it as a control. A strategy only has a real edge if it beats this baseline
over the same tickers and years, because simply buying stocks in uptrends during
a rising market looks profitable without any skill.

Entries are pseudo-random but deterministic (same result every run).
"""
from __future__ import annotations

import zlib

import pandas as pd

from .base import Setup, Strategy


class TrendBaseline(Strategy):
    name = "trend_baseline"
    min_bars = 220

    def __init__(self, entry_rate: float = 0.05, stop_pct: float = 0.05,
                 t1_pct: float = 0.05, t2_pct: float = 0.10):
        self.entry_rate, self.stop_pct, self.t1_pct, self.t2_pct = entry_rate, stop_pct, t1_pct, t2_pct

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ma50"] = df["close"].rolling(50).mean()
        df["ma200"] = df["close"].rolling(200).mean()
        df["vol50"] = df["volume"].rolling(50).mean()
        return df

    def setup(self, ticker: str, df: pd.DataFrame, i: int) -> Setup | None:
        if i < self.min_bars:
            return None
        px, ma50, ma200 = df["close"].iat[i], df["ma50"].iat[i], df["ma200"].iat[i]
        if px < 10 or df["vol50"].iat[i] < 1_000_000:
            return None
        if not (ma50 > ma200 and ma50 > df["ma50"].iat[i - 10] and px >= ma50 * 0.97):
            return None
        if zlib.crc32(f"{ticker}{i}".encode()) % 10_000 >= self.entry_rate * 10_000:
            return None
        return Setup(ticker, df.index[i], triggered=True, qualifies=True, entry=float(px),
                     trigger=float(px), stop=float(px * (1 - self.stop_pct)),
                     targets=[float(px * (1 + self.t1_pct)), float(px * (1 + self.t2_pct))],
                     notes="random entry in uptrend (control)")
