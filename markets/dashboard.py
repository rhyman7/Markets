"""Builds the data behind the setups dashboard (site/index.html, served by GitHub Pages).

One pass over the universes, every rule in the repo, completed daily bars only:

- signal:  the rule fired on the last completed bar. "Buy at the next session's open."
- limit:   the rule has a resting buy limit for the next session.
- watch:   in the rule's buying zone, entry condition not met yet.
- forming: variant I would fire if today's unfinished bar closed where it is now. Not a
           signal. Never act on an unfinished daily candle.

Every row carries the rule's own entry, stop and targets, and the page shows each rule's
backtest result against its random control next to it (EVIDENCE below, copied from
research/log.md). Only variant I has beaten its control on fresh stocks; everything else
is shown for research and is labelled as failed.

The tracker replays journal/signals.csv with the backtester's trade management, so the
forward test can be read at a glance. No rule is changed or tuned here.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .strategies import FibPullback, FibTextbook, FibTextbookI, TextbookParams
from .strategies import breakout as brk
from .strategies import library as lib
from .strategies.base import Setup, Strategy

ET = ZoneInfo("America/New_York")
TEMPLATE = Path(__file__).with_name("dashboard_template.html")
FIB_EXIT = "Half off at T1 (swing high), stop to breakeven; rest at T2 (127.2% extension), the stop, or after 40 bars."
LIB_EXIT = "Whole position at +2R, the stop, or the close of the 20th bar."


@dataclass
class Model:
    key: str                      # strategy name, or a dashboard-only key for unregistered variants
    label: str
    family: str                   # "fib", "ict", "wyckoff", "breakout"
    factory: Callable[[], Strategy]
    verdict: str                  # "passed", "no edge", "worse than random"
    trades: int                   # backtest trades behind the numbers below
    exp_r: float                  # expectancy per trade, R
    ctl_r: float                  # matched random control, R
    z: float | None
    tested_on: str
    note: str = ""
    exit: str = LIB_EXIT
    all_universes: bool = False   # False: scanned on the large-cap list only (where it was tested)

    @property
    def gap(self) -> float:
        return round(self.exp_r - self.ctl_r, 3)


def _fib(key, label, factory, verdict, trades, exp_r, ctl_r, tested_on, note):
    return Model(key, label, "fib", factory, verdict, trades, exp_r, ctl_r, None, tested_on, note,
                 exit=FIB_EXIT, all_universes=True)


# Numbers are copied from research/log.md. Update them there first, then here.
LARGE = "142 large caps, 2016-2026, no costs"
FIB_MODELS = [
    _fib("fib_textbook_i", "Variant I: reversal candle in the 38.2-61.8% zone + RSI < 40 turning up",
         FibTextbookI, "passed", 427, 0.177, 0.002, "S&P MidCap 400, 2016-2026, 5 bps/side costs",
         "Ahead of the control in 9 of 10 years, but the gap is about zero in 2025-26 and both lost "
         "money in 2026 (I -0.127R on 57 trades). On large caps the gap (+0.045R) was within noise. "
         "The only rule of 34 tried that passed, so some of this may be luck."),
    _fib("fib_textbook_h", "Variant H: reversal candle in the 38.2-61.8% zone",
         lambda: FibTextbook(TextbookParams(mode="pattern")), "no edge", 587, 0.165, 0.132, LARGE,
         "Slightly ahead of the control, within noise. Never tested on fresh stocks."),
    _fib("fib_textbook", "Variant G: buy limit at the 55.9% level",
         FibTextbook, "no edge", 1340, 0.082, 0.132, LARGE, "Behind random entries in the same uptrends."),
    _fib("fib_textbook_j", "Variant J: buy limit + 50-day SMA in the zone",
         lambda: FibTextbook(TextbookParams(mode="limit", require_ma=True)), "no edge", 637, 0.060, 0.132, LARGE,
         "Behind random entries in the same uptrends."),
    _fib("fib_pullback", "Original fib pullback (close above prior high in the 30-70% zone)",
         FibPullback, "no edge", 1146, 0.075, 0.132, LARGE,
         "Behind random entries, and lost money after 2021 (-0.039R)."),
]

# name: (label, trades, tool R, control R, z). Large caps, matched random control.
_LIB = {
    "ict_displacement": ("ICT displacement (FVG retest)", 843, 0.022, -0.033, 0.8),
    "wyckoff_sos_lps": ("Wyckoff SOS -> LPS", 1001, 0.181, 0.136, 1.0),
    "ict_nwog": ("ICT NWOG retest", 2057, 0.016, -0.015, 0.8),
    "ict_order_block": ("ICT order block", 722, 0.081, 0.062, 0.2),
    "ict_fvg": ("ICT fair value gap", 8366, 0.004, -0.015, 0.7),
    "ict_ipda_range": ("ICT IPDA range", 2948, 0.155, 0.148, 0.3),
    "ict_key_level_sweep": ("ICT key-level sweep", 16797, 0.090, 0.083, 0.3),
    "wyckoff_spring_test": ("Wyckoff spring + test", 2580, 0.140, 0.142, -0.1),
    "wyckoff_vsa_no_supply": ("Wyckoff VSA no supply", 4484, 0.016, 0.019, -0.1),
    "ict_sd_breakout_2R": ("ICT SD breakout (2R)", 3843, 0.124, 0.132, -0.4),
    "ict_sd_targets": ("ICT SD breakout (SD targets)", 3835, 0.121, 0.132, -0.5),
    "ict_structure_bos": ("ICT break of structure", 2431, 0.094, 0.109, -0.6),
    "ict_structure_choch": ("ICT CHoCH / MSS", 2990, 0.105, 0.122, -0.8),
    "ict_volume_imbalance": ("ICT volume imbalance", 13728, -0.014, 0.004, -0.7),
    "wyckoff_reaccumulation": ("Wyckoff re-accumulation", 1369, 0.061, 0.111, -1.9),
    "ict_market_maker_buy": ("ICT market maker buy model", 323, 0.049, 0.103, -1.2),
    "ict_liquidity_sweep": ("ICT liquidity sweep", 2555, 0.024, 0.083, -1.7),
    "ict_premium_discount_ote": ("ICT premium/discount OTE", 1378, 0.018, 0.090, -1.3),
    "ict_dealing_range": ("ICT dealing range", 4018, 0.084, 0.157, -2.6),
    "wyckoff_vsa_stopping_volume": ("Wyckoff VSA stopping volume", 3323, 0.062, 0.136, -2.2),
    "wyckoff_price_cycle_pullback": ("Wyckoff price cycle pullback", 2665, -0.006, 0.083, -1.9),
    "ict_unicorn": ("ICT unicorn", 140, -0.093, 0.003, -0.7),
    "wyckoff_comparative_strength": ("Wyckoff comparative strength", 2551, 0.021, 0.151, -4.4),
    "wyckoff_selling_climax": ("Wyckoff selling climax + AR", 250, -0.071, 0.145, -2.9),
    "wyckoff_accumulation": ("Wyckoff accumulation (SC -> spring -> SOS)", 11, -0.139, 0.122, -1.3),
    "breakout_52w_high": ("52-week-high breakout", 3353, 0.067, 0.087, -0.8),
    "breakout_squeeze": ("Tight-range breakout", 1980, 0.064, 0.080, -0.7),
    "momentum_top_decile": ("Top-decile 6-month momentum entry", 1097, 0.005, 0.108, -2.5),
}


def _library_models() -> list[Model]:
    out = []
    for tool in lib.ALL_TOOLS + brk.BREAKOUT_TOOLS:
        label, n, r, ctl, z = _LIB[tool.name]
        family = "breakout" if tool in brk.BREAKOUT_TOOLS else tool.name.split("_")[0]
        note = "Fewer than 100 trades: too few to say anything." if n < 100 else ""
        out.append(Model(tool.name, label, family, tool, "worse than random" if z <= -2 else "no edge",
                         n, r, ctl, z, "142 large caps, 2016-2026, +2R / 20-bar exit", note,
                         exit="Tool's standard-deviation targets, the stop, or the close of the 20th bar."
                         if tool.name == "ict_sd_targets" else LIB_EXIT))
    return sorted(out, key=lambda m: -m.gap)


MODELS: list[Model] = FIB_MODELS + _library_models()
PRIMARY = "fib_textbook_i"


# ----------------------------------------------------------------------------- helpers
def split_unfinished(df: pd.DataFrame, now: datetime) -> tuple[pd.DataFrame, bool]:
    """(completed bars, whether a bar from today's unfinished session was dropped).
    Same cutoff as scan.drop_unfinished_bar: the session counts as done from 4:15 PM ET."""
    now = now.astimezone(ET)
    done = now.hour > 16 or (now.hour == 16 and now.minute >= 15)
    if len(df) and df.index[-1].date() == now.date() and not done:
        return df.iloc[:-1], True
    return df, False


def _num(x, nd=2):
    x = float(x)
    return round(x, nd) if math.isfinite(x) else None


def _row(model: Model, universe: str, s: Setup, close: float, live: float, status: str, **extra) -> dict:
    entry, risk = s.entry, s.entry - s.stop
    row = {
        "model": model.key, "ticker": s.ticker, "universe": universe, "status": status,
        "bar": str(s.date.date()), "close": _num(close), "live": _num(live),
        "entry": _num(entry), "stop": _num(s.stop), "t1": _num(s.targets[0]), "t2": _num(s.targets[-1]),
        "risk_pct": _num(100 * risk / entry, 1) if entry > 0 else None,
        "rr1": _num(s.rr(0)), "rr2": _num(s.rr(len(s.targets) - 1)),
        "notes": s.notes if model.family == "fib" else "",
    }
    row.update(extra)
    return row


def _zone(s: Setup) -> dict:
    lv = s.levels
    return {"zone_top": _num(lv["fib_0.382"]), "zone_bot": _num(lv["fib_0.618"]),
            "depth_pct": _num(100 * lv["depth"], 1)}


def _make(model: Model, ticker: str, benchmark, ranks) -> Strategy:
    st = model.factory()
    if isinstance(st, lib.ComparativeStrength):
        st.benchmark = benchmark
    if getattr(st, "needs_ranks", False):
        st.rank = (ranks or {}).get(ticker)
    return st


def _last_setup(st: Strategy, ticker: str, df: pd.DataFrame) -> Setup | None:
    if len(df) < max(st.min_bars + 1, 260):
        return None
    return st.setup(ticker, st.prepare(df), len(df) - 1)


def scan_ticker(ticker: str, universe: str, full: pd.DataFrame, now: datetime, models: list[Model],
                benchmark=None, ranks=None) -> list[dict]:
    """Every row this ticker contributes. Rules only ever see completed bars; the unfinished
    bar supplies the live price and the 'forming' check for variant I."""
    done, unfinished = split_unfinished(full, now)
    if done.empty:
        return []
    close, live = float(done["close"].iat[-1]), float(full["close"].iat[-1])
    rows: list[dict] = []
    fired_i = False
    for m in models:
        try:
            s = _last_setup(_make(m, ticker, benchmark, ranks), ticker, done)
        except Exception:       # one rule failing on one ticker must not blank the board
            continue
        if s is None:
            continue
        if s.limit is not None:
            extra = _zone(s) if m.family == "fib" else {}
            rows.append(_row(m, universe, s, close, live, "limit", limit=_num(s.limit), **extra))
        elif s.triggered and s.qualifies:
            fired_i = fired_i or m.key == PRIMARY
            extra = _zone(s) if "fib_0.382" in s.levels else {}
            rows.append(_row(m, universe, s, close, live, "signal", **extra))
        elif s.qualifies:       # fib_pullback: in its zone, waiting for a close above the trigger
            rows.append(_row(m, universe, s, close, live, "watch", trigger=_num(s.trigger),
                             waiting=f"a daily close above {s.trigger:.2f}"))

    primary = next((m for m in models if m.key == PRIMARY), None)
    if primary is None:
        return rows
    if not fired_i:
        # Variant I's buying zone: same trend, swing and 78.6% rules (the limit variant returns
        # them for any valid pullback), price inside 38.2-61.8%, confirmation still missing.
        g = _last_setup(FibTextbook(), ticker, done)
        if g is not None and g.levels["fib_0.618"] <= close <= g.levels["fib_0.382"]:
            lv = g.levels
            entry_ref = Setup(ticker, g.date, False, True, close, close, g.stop, g.targets, lv, g.notes.split(",")[0])
            rows.append(_row(primary, universe, entry_ref, close, live, "watch", **_zone(g),
                             rsi=_num(lv["rsi"], 1), rsi_min=_num(lv["rsi_min"], 1),
                             checks={"rsi_below_40_in_pullback": lv["rsi_min"] < 40,
                                     "rsi_rising": bool(lv["rsi_rising"]), "reversal_candle": False},
                             waiting="a bullish engulfing or pin bar closing inside the zone"))
    if unfinished:
        try:
            f = _last_setup(FibTextbookI(), ticker, full)
        except Exception:
            f = None
        if f is not None:
            rows.append(_row(primary, universe, f, close, live, "forming", **_zone(f)))
    return rows


# ----------------------------------------------------------------------------- forward-test tracker
def track_signal(df: pd.DataFrame, signal_date, stop: float, t1: float, t2: float, n_done: int | None = None,
                 max_hold: int = 40) -> dict:
    """Replay one logged signal with the backtester's management (markets/backtest.py): enter at
    the next open, half off at T1 and stop to breakeven, rest at T2, the stop, or after
    `max_hold` bars. No costs. `n_done` = number of completed bars; an unfinished last bar
    can hit the stop or a target but can't close the trade on time."""
    n = len(df)
    n_done = n if n_done is None else n_done
    o, h, l, c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    after = np.flatnonzero(df.index > pd.Timestamp(signal_date))
    if not len(after):
        return {"state": "pending", "text": "Enter at the next session's open"}
    e = int(after[0])
    entry = float(o[e])
    if entry <= stop:
        return {"state": "skipped", "text": "Opened at or below the stop; no trade", "entry": _num(entry)}
    risk = entry - stop
    cur_stop, half, realized = stop, False, 0.0
    out = {"entry": _num(entry), "entry_date": str(df.index[e].date())}
    for j in range(e, n):
        px = why = None
        if o[j] <= cur_stop and j > e:
            px, why = o[j], "stop (gap)"
        elif l[j] <= cur_stop:
            px, why = cur_stop, "breakeven" if half else "stop"
        if px is None and not half and h[j] >= t1:
            realized += 0.5 * (t1 - entry) / risk
            half, cur_stop = True, max(cur_stop, entry)
        if px is None and half and h[j] >= t2:
            px, why = t2, "target 2"
        if px is None and j - e + 1 >= max_hold and j < n_done:
            px, why = c[j], "time"
        if px is not None:
            r = realized + (0.5 if half else 1.0) * (px - entry) / risk
            return {**out, "state": "closed", "exit": _num(px), "exit_date": str(df.index[j].date()),
                    "exit_reason": why, "r": _num(r), "t1_hit": half,
                    "text": f"Closed: {why}" + (" (today, unfinished bar)" if j >= n_done else "")}
    r = realized + (0.5 if half else 1.0) * (c[-1] - entry) / risk
    return {**out, "state": "open", "stop_now": _num(cur_stop), "t1_hit": half, "r": _num(r),
            "bars": n - e, "bars_left": max(0, max_hold - (n_done - e)),
            "text": "T1 hit: half off, stop at breakeven" if half else "Open: stop unchanged"}


def track_signals(signals: pd.DataFrame, data: dict[str, pd.DataFrame], now: datetime) -> list[dict]:
    rows = []
    for rec in signals.to_dict("records"):
        t = str(rec.get("ticker", "")).upper()
        row = {k: (None if pd.isna(rec.get(k)) else rec.get(k)) for k in
               ("date", "ticker", "strategy", "universe", "close", "stop", "t1", "t2", "taken")}
        df = data.get(t)
        try:
            stop, t1, t2 = float(rec["stop"]), float(rec["t1"]), float(rec["t2"])
            for k, v in (("close", float(rec["close"])), ("stop", stop), ("t1", t1), ("t2", t2)):
                row[k] = _num(v)
            if df is None or df.empty:
                row.update(state="no data", text="No price data in this build")
            else:
                done, _ = split_unfinished(df, now)
                row.update(track_signal(df, rec["date"], stop, t1, t2, n_done=len(done)))
                row["live"] = _num(df["close"].iat[-1])
        except (KeyError, TypeError, ValueError):
            row.update(state="no data", text="Could not read this row")
        rows.append(row)
    return sorted(rows, key=lambda r: str(r.get("date")), reverse=True)


# ----------------------------------------------------------------------------- build
def build(universes: dict[str, dict[str, pd.DataFrame]], signals: pd.DataFrame | None = None,
          now: datetime | None = None, benchmark: pd.Series | None = None, provider: str = "",
          failed: list[str] | None = None, library_universes: tuple[str, ...] = ("universe",),
          extra_data: dict[str, pd.DataFrame] | None = None) -> dict:
    """`universes` maps a universe tag (file stem) to {ticker: daily bars}. Bars may end with
    today's unfinished bar; rules never see it."""
    now = (now or datetime.now(ET)).astimezone(ET)
    rows: list[dict] = []
    all_data: dict[str, pd.DataFrame] = dict(extra_data or {})   # tracker-only tickers
    last_done, live_dates, any_unfinished = [], [], False
    for tag, data in universes.items():
        models = [m for m in MODELS if m.all_universes or tag in library_universes]
        done_only = {t: split_unfinished(df, now)[0] for t, df in data.items()}
        ranks = brk.momentum_ranks({t: d for t, d in done_only.items() if len(d)}) \
            if any(getattr(m.factory, "needs_ranks", False) for m in models) and done_only else {}
        bench_done = None if benchmark is None else split_unfinished(benchmark.to_frame("close"), now)[0]["close"]
        for t, df in data.items():
            if df is None or df.empty:
                continue
            all_data[t] = df
            done, unfinished = split_unfinished(df, now)
            any_unfinished = any_unfinished or unfinished
            if len(done):
                last_done.append(done.index[-1])
            live_dates.append(df.index[-1])
            rows += scan_ticker(t, tag, df, now, models, bench_done, ranks)

    order = {"signal": 0, "limit": 1, "forming": 2, "watch": 3}
    rows.sort(key=lambda r: (order[r["status"]], -(r["rr2"] or 0), r["ticker"]))
    data_through = max(last_done).date() if last_done else None
    stale = []
    for t, df in all_data.items():
        done = split_unfinished(df, now)[0]
        if data_through and len(done) and done.index[-1].date() < data_through:
            stale.append(t)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "data_through": str(data_through) if data_through else None,
        "live_date": str(max(live_dates).date()) if live_dates else None,
        "session_unfinished": any_unfinished,
        "provider": provider,
        "price_delay": "about 15 minutes behind (Alpaca free plan)" if provider == "alpaca" else "delayed",
        "scanned": {tag: len(d) for tag, d in universes.items()},
        "failed": sorted(failed or []),
        "stale": sorted(stale),
        "primary": PRIMARY,
        "rules_tried": 34,
        "models": [{"key": m.key, "label": m.label, "family": m.family, "verdict": m.verdict,
                    "trades": m.trades, "exp_r": m.exp_r, "ctl_r": m.ctl_r, "gap": m.gap, "z": m.z,
                    "tested_on": m.tested_on, "note": m.note, "exit": m.exit,
                    "scanned_on": "large caps + mid-caps" if m.all_universes else "large caps"}
                   for m in MODELS],
        "rows": rows,
        "tracker": track_signals(signals, all_data, now) if signals is not None and len(signals) else [],
    }


def write_site(payload: dict, out_dir: str | Path) -> Path:
    """Write data.json and a self-contained index.html (the data is inlined, so the page also
    opens from disk; when served it re-reads data.json every few minutes)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, allow_nan=False, separators=(",", ":"))
    (out / "data.json").write_text(text)
    html = TEMPLATE.read_text().replace("/*__DATA__*/null", text.replace("</", "<\\/"))
    (out / "index.html").write_text(html)
    (out / ".nojekyll").write_text("")
    return out / "index.html"
