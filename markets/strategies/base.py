"""Common interface every strategy implements.

A strategy looks at completed daily bars up to index `i` and returns a `Setup`
(or None). The scanner and backtester only talk to this interface, so adding a
strategy means writing one class and registering it in strategies/__init__.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Setup:
    ticker: str
    date: pd.Timestamp
    triggered: bool            # entry condition met on this bar's close
    qualifies: bool            # passes the strategy's reward/risk filter
    entry: float               # expected entry (this close if triggered, else the trigger)
    trigger: float             # price the close must exceed
    stop: float
    targets: list[float]       # in order; first is a partial-profit target
    levels: dict[str, float] = field(default_factory=dict)  # for charts/notes
    notes: str = ""
    limit: float | None = None  # if set: a buy limit for the next bar instead of buying at the open

    @property
    def risk(self) -> float:
        return self.entry - self.stop

    def rr(self, target_index: int) -> float:
        return (self.targets[target_index] - self.entry) / self.risk if self.risk > 0 else 0.0


class Strategy:
    name = "base"
    min_bars = 250

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add indicator columns once per ticker. Override as needed."""
        return df

    def setup(self, ticker: str, df: pd.DataFrame, i: int) -> Setup | None:
        raise NotImplementedError
