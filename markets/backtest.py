"""Bar-by-bar backtest for any Strategy, reported in R (multiples of initial risk).

Trade management (shared by all strategies unless they override it later):
- Signal on bar i's close -> enter at bar i+1's open. Skip if it opens at/below the stop.
- Limit orders (Setup.limit): fill on bar i+1 only if its low reaches the limit, at the
  lower of the open and the limit. Unfilled orders are re-evaluated on the next bar.
  If the fill is below the open, that bar's high may predate the fill, so on that bar a
  target only counts if the close reaches it.
- R = entry - stop, using the actual entry price.
- Half the position exits at the first target; the stop then moves to breakeven.
- The rest exits at the last target, the stop, or the close after `max_hold` bars
  (40 by default; a strategy can set its own `max_hold` attribute).
- A gap through the stop exits at the open (can lose more than 1R).
- If a bar touches both the stop and a target, assume the stop hit first (conservative).
- Costs: COST_PER_SIDE (a fraction of price, e.g. 0.0005 = 0.05%) is charged on the entry
  and on every exit, and taken out of R. It covers commission and slippage together.
  Default 0 here; experiment.py and backtest.py set it from --cost-bps (default 5 bps).
- One position per ticker at a time. Positions across tickers are independent:
  this measures the edge of the rules, not portfolio constraints like max positions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .strategies.base import Strategy

COST_PER_SIDE = 0.0   # commission + slippage per side as a fraction of price (set by the CLIs)


@dataclass
class Trade:
    ticker: str
    signal_date: pd.Timestamp
    entry_date: pd.Timestamp
    entry: float
    stop: float
    t1: float
    t2: float
    exit_date: pd.Timestamp | None = None
    exit_reason: str = ""
    r: float = 0.0
    bars_held: int = 0
    risk_pct: float = 0.0      # (entry - stop) / entry
    depth: float = float("nan")  # retracement depth at the signal, if the strategy reports it
    risk_atr: float = float("nan")  # planned risk in ATR units, if the strategy reports it
    limit_gap_atr: float = float("nan")  # (signal close - limit) / ATR for limit entries


def simulate_ticker(strategy: Strategy, ticker: str, df: pd.DataFrame, max_hold: int = 40,
                    cost: float | None = None) -> list[Trade]:
    cost = COST_PER_SIDE if cost is None else cost
    max_hold = getattr(strategy, "max_hold", None) or max_hold   # a strategy may set its own
    df = strategy.prepare(df)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    trades: list[Trade] = []
    i = strategy.min_bars
    n = len(df)
    while i < n - 1:
        s = strategy.setup(ticker, df, i)
        if not (s and s.triggered and s.qualifies):
            i += 1
            continue
        if s.limit is not None:
            if l[i + 1] > s.limit:
                i += 1
                continue
            entry = min(o[i + 1], s.limit)
        else:
            entry = o[i + 1]
        if entry <= s.stop:
            i += 1
            continue
        risk = entry - s.stop
        t1, t2 = s.targets[0], s.targets[-1]
        tr = Trade(ticker, df.index[i], df.index[i + 1], float(entry), s.stop, t1, t2,
                   risk_pct=float(risk / entry), depth=float(s.levels.get("depth", float("nan"))),
                   risk_atr=float(s.levels.get("risk_atr", float("nan"))),
                   limit_gap_atr=float(s.levels.get("limit_gap_atr", float("nan"))))
        stop, half_done, realized = s.stop, False, 0.0
        # A limit filled below the open: the bar's high may have come before the fill. After
        # the fill the path ends at the close, so on that bar a target only counts if the close
        # reached it (fixed 2026-11-10; before, any high counted, which flattered limit entries).
        fill_bar = i + 1 if (s.limit is not None and entry < o[i + 1]) else -1
        j = i + 1
        while True:
            if o[j] <= stop and j > i + 1:            # gap through stop
                px, why = o[j], "stop (gap)"
            elif l[j] <= stop:
                px, why = stop, "stop" if not half_done else "breakeven"
            else:
                px = None
            if px is None and not half_done and (h[j] if j != fill_bar else c[j]) >= t1:
                realized += 0.5 * (t1 - entry) / risk
                half_done, stop = True, max(stop, entry)
            if px is None and half_done and (h[j] if j != fill_bar else c[j]) >= t2:
                px, why = t2, "target 2"
            if px is None and j - (i + 1) + 1 >= max_hold:
                px, why = c[j], "time"
            if px is None and j == n - 1:
                px, why = c[j], "open (end of data)"
            if px is not None:
                frac = 0.5 if half_done else 1.0
                traded = entry + frac * px + (0.5 * t1 if half_done else 0.0)   # value bought + sold
                tr.r = realized + frac * (px - entry) / risk - cost * traded / risk
                tr.exit_date, tr.exit_reason, tr.bars_held = df.index[j], why, j - i
                trades.append(tr)
                break
            j += 1
        i = j + 1
    return trades


def summarize(trades: list[Trade]) -> dict:
    closed = [t for t in trades if not t.exit_reason.startswith("open")]
    if not closed:
        return {"trades": 0}
    r = np.array([t.r for t in sorted(closed, key=lambda t: t.exit_date)])
    wins, losses = r[r > 0], r[r <= 0]
    equity = r.cumsum()
    drawdown = (np.maximum.accumulate(np.concatenate([[0], equity]))[1:] - equity).max()
    return {
        "trades": len(r),
        "win_rate": round(len(wins) / len(r), 3),
        "avg_win_R": round(float(wins.mean()), 2) if len(wins) else 0.0,
        "avg_loss_R": round(float(losses.mean()), 2) if len(losses) else 0.0,
        "expectancy_R": round(float(r.mean()), 3),
        "total_R": round(float(r.sum()), 1),
        "profit_factor": round(float(wins.sum() / -losses.sum()), 2) if losses.sum() < 0 else float("inf"),
        "max_drawdown_R": round(float(drawdown), 1),
        "avg_bars_held": round(float(np.mean([t.bars_held for t in closed])), 1),
    }


def trades_frame(trades: list[Trade]) -> pd.DataFrame:
    return pd.DataFrame([asdict(t) for t in trades])
