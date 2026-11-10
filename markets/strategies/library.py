"""FibAlgo library tools (ICT and Wyckoff) turned into testable long-only daily rules.

None of the FibAlgo pages give entry, stop or target rules ("does not generate buy/sell
signals"), so every tool here uses ONE shared trade template, fixed before any test was
run (see research/log.md, 2026-11-10 "FibAlgo library screen"):

- Daily bars, long only. Same liquidity filter as the control: close >= $10 and
  50-day average volume >= 1M.
- Context: "up" tools also need the control's uptrend (50 > 200 SMA, 50 SMA rising over
  10 bars, close >= 97% of the 50 SMA). "any" tools (reversal / range concepts) don't.
- Zone tools: when the zone is confirmed on a bar's close, place a buy limit at the
  zone's entry level (its CE / 50% midpoint unless stated) for the next 20 bars. One
  attempt per zone; the zone is used up at the first touch or when a close goes below it.
- Event tools: the signal is on a bar's close; buy the next open.
- Stop: the tool's structure level (zone bottom, sweep low, ...) minus 0.1 x ATR(14).
  Risk is floored at 0.5 x ATR (stop moved down) and trades risking > 5 x ATR are skipped.
- Exit: the whole position at +2R, the stop, or the close of the 20th bar.
  (Exception: SDTargets uses the tool's own standard-deviation levels as targets.)
- Bearish versions (upthrust, SOW, distribution, bearish OBs...) are not tested:
  the backtester is long only.

Each tool is compared to RandomControl: random entries with the same filter and context,
the same exits, and a stop distance equal to the tool's median risk in ATR.

Every detector only uses bars up to i to decide what happens at bar i (tests check this
by truncating the data).
"""
from __future__ import annotations

import zlib

import numpy as np
import pandas as pd

from .base import Setup, Strategy

ZONE_BARS = 20       # a zone accepts a limit order for this many bars after it's confirmed
STOP_BUFFER = 0.1    # x ATR below the structure level
MIN_RISK = 0.5       # x ATR
MAX_RISK = 5.0       # x ATR
TARGET_R = 2.0


# ----------------------------------------------------------------------------- helpers
def atr(df: pd.DataFrame, n: int = 14) -> np.ndarray:
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean().to_numpy()


def lagged_mean(s: pd.Series, n: int) -> np.ndarray:
    """Mean of the n bars BEFORE each bar (the bar itself excluded)."""
    return s.rolling(n).mean().shift(1).to_numpy()


def linreg_slope(c: np.ndarray, n: int = 20) -> np.ndarray:
    x = np.arange(n) - (n - 1) / 2
    out = np.full(len(c), np.nan)
    for i in range(n - 1, len(c)):
        out[i] = (x * c[i - n + 1:i + 1]).sum() / (x * x).sum()
    return out


def adx(df: pd.DataFrame, n: int = 14) -> np.ndarray:
    h, l, c = df["high"], df["low"], df["close"]
    up, dn = h.diff(), -l.diff()
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    a = 1 / n
    atr_w = tr.ewm(alpha=a, adjust=False).mean()
    pdi = 100 * pd.Series(plus, index=df.index).ewm(alpha=a, adjust=False).mean() / atr_w
    mdi = 100 * pd.Series(minus, index=df.index).ewm(alpha=a, adjust=False).mean() / atr_w
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=a, adjust=False).mean().to_numpy()


def pivots(h: np.ndarray, l: np.ndarray, length: int):
    """Confirmed pivots as (bar, confirmed_at, price). A pivot high at k is the highest
    high of k-length..k+length and is only known at bar k+length."""
    ph, pl = [], []
    for k in range(length, len(h) - length):
        win_h, win_l = h[k - length:k + length + 1], l[k - length:k + length + 1]
        if h[k] == win_h.max() and np.argmax(win_h) == length:
            ph.append((k, k + length, h[k]))
        if l[k] == win_l.min() and np.argmin(win_l) == length:
            pl.append((k, k + length, l[k]))
    return ph, pl


def close_pos(o, h, l, c):
    rng = h - l
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(rng > 0, (c - l) / rng, 0.5)


# ----------------------------------------------------------------------------- base class
class LibraryTool(Strategy):
    """Shared template. Subclasses implement detect(df) and fill self.events / self.zones."""

    name = "library_base"
    context = "any"          # "up" or "any"
    min_bars = 220
    max_hold = 20
    page = ""                # FibAlgo URL slug

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        n = len(df)
        self.o, self.h, self.l, self.c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
        self.v = df["volume"].to_numpy(dtype=float)
        self.atr = atr(df)
        ma50 = df["close"].rolling(50).mean().to_numpy()
        ma200 = df["close"].rolling(200).mean().to_numpy()
        vol50 = df["volume"].rolling(50).mean().to_numpy()
        ma50_10 = np.r_[np.full(10, np.nan), ma50[:-10]] if n > 10 else np.full(n, np.nan)
        self.ok = (self.c >= 10) & (vol50 >= 1_000_000)
        self.up = (ma50 > ma200) & (ma50 > ma50_10) & (self.c >= ma50 * 0.97)
        # event[i] -> buy next open, stop level ev_stop[i]
        self.event = np.zeros(n, dtype=bool)
        self.ev_stop = np.full(n, np.nan)
        self.ev_t1 = np.full(n, np.nan)
        self.ev_t2 = np.full(n, np.nan)
        # limit orders: lim[i] = buy limit for bar i+1, lim_stop[i] = its stop level
        self.lim = np.full(n, np.nan)
        self.lim_stop = np.full(n, np.nan)
        self._lim_formed = np.full(n, -1)
        self.detect(df)
        return df

    def detect(self, df: pd.DataFrame) -> None:
        raise NotImplementedError

    # --- helpers for subclasses
    def add_event(self, i: int, stop_level: float, t1: float = np.nan, t2: float = np.nan) -> None:
        self.event[i] = True
        self.ev_stop[i] = stop_level
        self.ev_t1[i], self.ev_t2[i] = t1, t2

    def add_zone(self, formed: int, entry: float, stop_level: float, watch_from: int | None = None,
                 cancel_above: float | None = None) -> None:
        """Buy limit at `entry` on bars formed+1 .. formed+ZONE_BARS until the first touch.
        Skipped if price already touched entry between watch_from and formed."""
        h, l, c, n = self.h, self.l, self.c, len(self.c)
        if not (entry > stop_level) or formed >= n:
            return
        start = formed + 1 if watch_from is None else watch_from
        if start <= formed and l[start:formed + 1].min() <= entry:
            return
        if c[formed] <= entry:
            return
        for i in range(formed, min(formed + ZONE_BARS, n)):
            if i > formed:
                if l[i] <= entry or c[i] < stop_level:        # used up (the fill happens on this bar)
                    break
                if cancel_above is not None and c[i] > cancel_above:
                    break
            if self._lim_formed[i] <= formed:                 # newest zone wins
                self.lim[i], self.lim_stop[i], self._lim_formed[i] = entry, stop_level, formed

    def setup(self, ticker: str, df: pd.DataFrame, i: int) -> Setup | None:
        if i < self.min_bars or not self.ok[i] or not np.isfinite(self.atr[i]):
            return None
        if self.context == "up" and not self.up[i]:
            return None
        a = self.atr[i]
        if self.event[i]:
            entry, lvl, limit = self.c[i], self.ev_stop[i], None
        elif np.isfinite(self.lim[i]):
            entry, lvl, limit = self.lim[i], self.lim_stop[i], self.lim[i]
        else:
            return None
        stop = min(lvl - STOP_BUFFER * a, entry - MIN_RISK * a)
        if entry - stop > MAX_RISK * a:
            return None
        risk = entry - stop
        t1 = self.ev_t1[i] if self.event[i] and np.isfinite(self.ev_t1[i]) else entry + TARGET_R * risk
        t2 = self.ev_t2[i] if self.event[i] and np.isfinite(self.ev_t2[i]) else t1
        return Setup(ticker, df.index[i], triggered=True, qualifies=True, entry=float(entry),
                     trigger=float(entry), stop=float(stop), targets=[float(t1), float(t2)],
                     levels={"risk_atr": float(risk / a),
                             "limit_gap_atr": float((self.c[i] - limit) / a) if limit is not None else float("nan")},
                     notes=self.name, limit=limit)


class RandomControl(Strategy):
    """Control for one tool: random bars (same hash as trend_baseline), the same filter, context
    and exits, and the tool's typical stop distance. For zone tools it also uses the same entry
    mechanics: a one-bar buy limit `limit_atr` x ATR below the close."""

    name = "random_control"
    min_bars = 220
    max_hold = 20

    def __init__(self, context: str = "up", stop_atr: float = 1.5, limit_atr: float | None = None,
                 entry_rate: float = 0.05):
        self.context, self.stop_atr, self.limit_atr, self.entry_rate = context, stop_atr, limit_atr, entry_rate
        self._tool = LibraryTool()
        self._tool.detect = lambda d: None

    def prepare(self, df):
        return self._tool.prepare(df)

    def setup(self, ticker, df, i):
        t = self._tool
        if i < self.min_bars or not t.ok[i] or not np.isfinite(t.atr[i]):
            return None
        if self.context == "up" and not t.up[i]:
            return None
        if zlib.crc32(f"{ticker}{i}".encode()) % 10_000 >= self.entry_rate * 10_000:
            return None
        a = t.atr[i]
        limit = None if self.limit_atr is None else float(t.c[i] - self.limit_atr * a)
        entry = t.c[i] if limit is None else limit
        stop = entry - self.stop_atr * a
        tgt = entry + TARGET_R * (entry - stop)
        return Setup(ticker, df.index[i], True, True, float(entry), float(entry), float(stop), [float(tgt), float(tgt)],
                     levels={"risk_atr": float(self.stop_atr)}, notes="random control", limit=limit)


def matched_control(tool_cls: type[LibraryTool], trades: list, entry_rate: float = 0.05) -> RandomControl:
    """Control matched to a tool's actual trades: median risk (and limit gap) in ATR, rounded."""
    risk = np.nanmedian([t.risk_atr for t in trades]) if trades else 1.0
    gaps = [t.limit_gap_atr for t in trades if np.isfinite(t.limit_gap_atr)]
    limit_atr = round(float(np.median(gaps)) * 4) / 4 if len(gaps) > len(trades) / 2 else None
    rate = entry_rate if limit_atr is None else min(1.0, entry_rate * 4)   # limits fill less often
    return RandomControl(tool_cls.context, max(MIN_RISK, round(float(risk) * 4) / 4), limit_atr, rate)


# ============================================================================= ICT tools
class OrderBlock(LibraryTool):
    """Bullish OB: last bearish candle within 10 bars before a bullish displacement
    (body > 1.5 x prior ATR) that closes above the OB high. Zone = OB high-low range."""
    name, context, page = "ict_order_block", "up", "ict-order-blocks"

    def detect(self, df):
        o, h, l, c, a = self.o, self.h, self.l, self.c, self.atr
        used = set()
        for i in range(11, len(c)):
            if not (c[i] > o[i] and c[i] - o[i] > 1.5 * a[i - 1]):
                continue
            for k in range(i - 1, i - 11, -1):
                if c[k] < o[k]:
                    if k not in used and c[i] > h[k]:
                        used.add(k)
                        self.add_zone(i, (h[k] + l[k]) / 2, l[k])
                    break


class FairValueGap(LibraryTool):
    """Bullish FVG: low[i] > high[i-2], gap >= 0.25 x ATR. Entry at the CE."""
    name, context, page = "ict_fvg", "up", "ict-fair-value-gaps"

    def detect(self, df):
        h, l, a = self.h, self.l, self.atr
        for i in range(2, len(h)):
            if l[i] > h[i - 2] and l[i] - h[i - 2] >= 0.25 * a[i]:
                self.add_zone(i, (l[i] + h[i - 2]) / 2, h[i - 2])


class VolumeImbalance(LibraryTool):
    """Bullish VI: body bottom > previous body top while wicks overlap; gap >= 0.05 ATR."""
    name, context, page = "ict_volume_imbalance", "up", "ict-volume-imbalance"

    def detect(self, df):
        o, h, l, c, a = self.o, self.h, self.l, self.c, self.atr
        bt, bb = np.maximum(o, c), np.minimum(o, c)
        for i in range(1, len(c)):
            if bb[i] > bt[i - 1] and l[i] <= h[i - 1] and bb[i] - bt[i - 1] >= 0.05 * a[i]:
                self.add_zone(i, (bb[i] + bt[i - 1]) / 2, bt[i - 1])


class Displacement(LibraryTool):
    """Bullish displacement candle (body > 1.5 x ATR, body >= 65% of range) that leaves an
    FVG (next bar's low > high before the displacement). Entry at that FVG's CE."""
    name, context, page = "ict_displacement", "up", "ict-displacement"

    def detect(self, df):
        o, h, l, c, a = self.o, self.h, self.l, self.c, self.atr
        for i in range(3, len(c)):
            d = i - 1
            body, rng = c[d] - o[d], h[d] - l[d]
            if body > 1.5 * a[d - 1] and rng > 0 and body / rng >= 0.65 and l[i] > h[i - 2]:
                self.add_zone(i, (l[i] + h[i - 2]) / 2, h[i - 2])


class Unicorn(LibraryTool):
    """Bullish breaker (a bearish OB closed through by a bullish displacement within 60 bars)
    overlapping a bullish FVG that completes within 5 bars. Entry at the overlap's CE."""
    name, context, page = "ict_unicorn", "any", "ict-unicorn-model"

    def detect(self, df):
        o, h, l, c, a = self.o, self.h, self.l, self.c, self.atr
        n = len(c)
        bear_obs = []   # (formed, top, bottom)
        for i in range(11, n):
            body = c[i] - o[i]
            if body < 0 and -body > 1.5 * a[i - 1]:
                for k in range(i - 1, i - 11, -1):
                    if c[k] > o[k]:
                        if c[i] < l[k]:
                            bear_obs.append((i, h[k], l[k]))
                        break
            if body > 1.5 * a[i - 1]:
                for ob in [z for z in bear_obs if i - 60 <= z[0] < i and c[i] > z[1]]:
                    bear_obs.remove(ob)
                    top, bot = ob[1], ob[2]
                    for f in range(i, min(i + 6, n)):
                        if f >= 2 and l[f] > h[f - 2]:
                            o_top, o_bot = min(top, l[f]), max(bot, h[f - 2])
                            if o_top > o_bot:
                                self.add_zone(f, (o_top + o_bot) / 2, o_bot)
                            break
            bear_obs = [z for z in bear_obs if z[0] >= i - 60]


class PremiumDiscountOTE(LibraryTool):
    """After an up leg that breaks the prior pivot high (BOS; pivots of 5 bars), buy the OTE
    at the 70.5% retracement of the leg, stop below the leg's low."""
    name, context, page = "ict_premium_discount_ote", "up", "ict-premium-discount"

    def detect(self, df):
        ph, pl = pivots(self.h, self.l, 5)
        for j, (kh, conf, H) in enumerate(ph):
            if j == 0:
                continue
            lows = [p for p in pl if p[0] < kh and p[1] <= conf]
            if not lows or H <= ph[j - 1][2]:
                continue
            kl, _, L = lows[-1]
            if kl <= ph[j - 1][0]:          # leg must start after the previous high
                continue
            self.add_zone(conf, H - 0.705 * (H - L), L, watch_from=kh + 1)


class DealingRange(LibraryTool):
    """Range from the latest confirmed pivot high and low (10 bars), >= 2 x ATR and unbroken.
    Buy at 30% of the range (buy OTE, 21.4-38.2%), stop below the range low."""
    name, context, page = "ict_dealing_range", "any", "ict-dealing-range"

    def detect(self, df):
        h, l, c, a = self.h, self.l, self.c, self.atr
        ph, pl = pivots(h, l, 10)
        events = sorted([(p[1], "h", p) for p in ph] + [(p[1], "l", p) for p in pl], key=lambda x: x[0])
        last_h = last_l = None
        for conf, kind, p in events:
            if kind == "h":
                last_h = p
            else:
                last_l = p
            if last_h is None or last_l is None:
                continue
            H, L = last_h[2], last_l[2]
            start = max(last_h[0], last_l[0]) + 1
            if H - L < 2 * a[conf] or (conf >= start and (c[start:conf + 1].max() > H or c[start:conf + 1].min() < L)):
                continue
            self.add_zone(conf, L + 0.298 * (H - L), L, cancel_above=H)


class IPDARange(LibraryTool):
    """Close crosses above the 20-day equilibrium while price sits in the discount (< 48%)
    of both the 40- and 60-day ranges (completed bars). Stop below the 20-day low."""
    name, context, page = "ict_ipda_range", "any", "ict-ipda-data-range"

    def detect(self, df):
        hi = {n: df["high"].rolling(n).max().shift(1).to_numpy() for n in (20, 40, 60)}
        lo = {n: df["low"].rolling(n).min().shift(1).to_numpy() for n in (20, 40, 60)}
        c = self.c
        eq20 = (hi[20] + lo[20]) / 2
        with np.errstate(invalid="ignore", divide="ignore"):
            pos = {n: (c - lo[n]) / (hi[n] - lo[n]) for n in (40, 60)}
        for i in range(61, len(c)):
            if c[i - 1] <= eq20[i - 1] and c[i] > eq20[i] and pos[40][i] < 0.48 and pos[60][i] < 0.48:
                self.add_event(i, lo[20][i])


class _Structure(LibraryTool):
    """Swing structure with 5-bar pivots. A close above the last pivot high is a BOS if the
    trend was up, a CHoCH/MSS if it was down. Stop below the lowest low since that pivot."""
    want = "choch"

    def detect(self, df):
        h, l, c = self.h, self.l, self.c
        ph, pl = pivots(h, l, 5)
        ph_by_conf = {p[1]: p for p in ph}
        pl_by_conf = {p[1]: p for p in pl}
        last_h = last_l = None
        trend = 0
        for i in range(len(c)):
            if i in ph_by_conf:
                last_h = ph_by_conf[i]
            if i in pl_by_conf:
                last_l = pl_by_conf[i]
            if last_h is not None and c[i] > last_h[2]:
                kind = "choch" if trend == -1 else ("bos" if trend == 1 else None)
                if kind == self.want:
                    self.add_event(i, l[last_h[0]:i + 1].min())
                trend, last_h = 1, None
            elif last_l is not None and c[i] < last_l[2]:
                trend, last_l = -1, None


class MarketStructureCHoCH(_Structure):
    name, context, page, want = "ict_structure_choch", "any", "ict-market-structure", "choch"


class MarketStructureBOS(_Structure):
    name, context, page, want = "ict_structure_bos", "up", "ict-market-structure", "bos"


class LiquiditySweep(LibraryTool):
    """SSL sweep: a bar's low goes below a confirmed 10-bar swing low (still unbroken, < 250
    bars old) but it closes at or above it. Each level fires once. Stop below the bar's low."""
    name, context, page = "ict_liquidity_sweep", "any", "ict-liquidity-levels"

    def detect(self, df):
        l, c = self.l, self.c
        _, pl = pivots(self.h, l, 10)
        by_conf = {}
        for p in pl:
            by_conf.setdefault(p[1], []).append(p[2])
        active = []   # (level, confirmed_at)
        for i in range(len(c)):
            active = [z for z in active if i - z[1] < 250]
            hit = False
            for z in list(active):
                if l[i] < z[0]:
                    if c[i] >= z[0]:
                        hit = True
                    active.remove(z)          # fires once / broken
            if hit:
                self.add_event(i, l[i])
            for lvl in by_conf.get(i, []):
                active.append((lvl, i))


class KeyLevelSweep(LibraryTool):
    """Sweep of the prior week's or prior month's low: low below it, close back above it.
    First sweep per period only. Stop below the bar's low."""
    name, context, page = "ict_key_level_sweep", "any", "ict-key-levels"

    def detect(self, df):
        l, c = self.l, self.c
        for freq in ("W", "M"):
            per = df.index.to_period(freq)
            lows = df["low"].groupby(per).min()
            prev = pd.Series(lows.shift(1).reindex(per).to_numpy(), index=df.index).to_numpy()
            fired = set()
            for i in range(len(c)):
                if np.isfinite(prev[i]) and per[i] not in fired and l[i] < prev[i] <= c[i]:
                    fired.add(per[i])
                    if not self.event[i] or l[i] < self.ev_stop[i]:
                        self.add_event(i, l[i])


class NWOG(LibraryTool):
    """New Week Opening Gap up: the week's first open is above the previous week's last close
    by >= 0.1 x ATR. Buy a retest of the gap's CE; stop below the Friday close."""
    name, context, page = "ict_nwog", "up", "ict-opening-gaps"

    def detect(self, df):
        o, c, a = self.o, self.c, self.atr
        wk = df.index.to_period("W")
        for i in range(1, len(c)):
            if wk[i] != wk[i - 1] and o[i] - c[i - 1] >= 0.1 * a[i - 1]:
                self.add_zone(i, (o[i] + c[i - 1]) / 2, c[i - 1], watch_from=i)


class MarketMakerBuyModel(LibraryTool):
    """Accumulation (20-bar range <= 3.5 x ATR) -> sweep below it by >= 0.3 x ATR within 60
    bars -> bullish displacement (body >= 65% of range, range >= 0.8 x ATR) closing above the
    range high within 60 bars. Invalid if price first runs 2 x ATR above the range.
    Stop below the sweep low."""
    name, context, page = "ict_market_maker_buy", "any", "ict-market-maker-model"

    def detect(self, df):
        o, h, l, c, a = self.o, self.h, self.l, self.c, self.atr
        n, i = len(c), 20
        while i < n:
            hi, lo = h[i - 19:i + 1].max(), l[i - 19:i + 1].min()
            if not (np.isfinite(a[i]) and hi - lo <= 3.5 * a[i]):
                i += 1
                continue
            j, sweep, swept_at, done = i + 1, None, None, i + 1
            while j < n:
                if sweep is None:
                    if j - i > 60 or c[j] > hi + 2 * a[i]:
                        break
                    if l[j] < lo - 0.3 * a[i]:
                        sweep, swept_at = l[j], j
                else:
                    if j - swept_at > 60:
                        break
                    sweep = min(sweep, l[j])
                    rng = h[j] - l[j]
                    if c[j] > o[j] and rng >= 0.8 * a[j - 1] and (c[j] - o[j]) / rng >= 0.65 and c[j] > hi:
                        self.add_event(j, sweep)
                        break
                j += 1
            i = max(j, done) + 1


class _SDRange(LibraryTool):
    """Range from the latest confirmed 10-bar pivot high and low (>= 2 x ATR). Event: the first
    close above the range high within 60 bars of the range being set. Stop below the range CE."""
    sd_targets = False

    def detect(self, df):
        h, l, c, a = self.h, self.l, self.c, self.atr
        ph, pl = pivots(h, l, 10)
        events = sorted([(p[1], "h", p) for p in ph] + [(p[1], "l", p) for p in pl], key=lambda x: x[0])
        last_h = last_l = None
        for conf, kind, p in events:
            if kind == "h":
                last_h = p
            else:
                last_l = p
            if last_h is None or last_l is None:
                continue
            H, L = last_h[2], last_l[2]
            size = H - L
            if size < 2 * a[conf] or c[max(last_h[0], last_l[0]):conf + 1].max() > H:
                continue
            for i in range(conf + 1, min(conf + 61, len(c))):
                if c[i] > H:
                    if self.sd_targets:
                        self.add_event(i, (H + L) / 2, H + 1.0 * size, H + 2.0 * size)
                    else:
                        self.add_event(i, (H + L) / 2)
                    break


class SDBreakout(_SDRange):
    name, context, page = "ict_sd_breakout_2R", "any", "ict-standard-deviation"


class SDTargets(_SDRange):
    """Same entries as SDBreakout, but exits at the 1.0 SD (half) and 2.0 SD projections."""
    name, context, page, sd_targets = "ict_sd_targets", "any", "ict-standard-deviation", True


# ============================================================================= Wyckoff tools
def _selling_climax(t: LibraryTool, df: pd.DataFrame) -> np.ndarray:
    """SC per the climax page: falling 20-bar regression slope, lowest low of 20 bars, volume >
    2 x prior 20-bar average, range > 1.5 x prior ATR, close in upper half or lower wick > 50%."""
    o, h, l, c = t.o, t.h, t.l, t.c
    slope = linreg_slope(c, 20)
    vma = lagged_mean(df["volume"], 20)
    atr_prev = np.r_[np.nan, t.atr[:-1]]
    low20 = df["low"].rolling(20).min().to_numpy()
    rng = h - l
    cp = close_pos(o, h, l, c)
    wick = np.minimum(o, c) - l
    with np.errstate(invalid="ignore", divide="ignore"):
        return ((slope < 0) & (l <= low20) & (t.v > 2 * vma) & (rng > 1.5 * atr_prev)
                & ((cp > 0.5) | (wick > 0.5 * rng)))


class SellingClimax(LibraryTool):
    """SC, then an automatic rally within 10 bars (up bar closing in its upper half, range >=
    1 x ATR, volume >= 0.8 x average); cancelled by a close below the SC low. Buy after the AR.
    Stop below the SC low."""
    name, context, page = "wyckoff_selling_climax", "any", "wyckoff-selling-buying-climax"

    def detect(self, df):
        o, h, l, c, a = self.o, self.h, self.l, self.c, self.atr
        sc = _selling_climax(self, df)
        vma = lagged_mean(df["volume"], 20)
        cp = close_pos(o, h, l, c)
        for s in np.flatnonzero(sc):
            for j in range(s + 1, min(s + 11, len(c))):
                if c[j] < l[s]:
                    break
                if c[j] > o[j] and cp[j] > 0.5 and h[j] - l[j] >= a[j - 1] and self.v[j] >= 0.8 * vma[j]:
                    self.add_event(j, l[s])
                    break


class WyckoffAccumulation(LibraryTool):
    """Simplified schematic: SC -> trading range (SC low to the AR high of the next 10 bars) ->
    spring (low below the SC low, close back above it within 3 bars) within 80 bars -> SOS
    (up bar, range > 1.3 x ATR, close in top 30%, volume > 1.5 x average, close above mid-range)
    within 30 bars of the spring. Buy after the SOS; stop below the spring low."""
    name, context, page = "wyckoff_accumulation", "any", "wyckoff-accumulation-distribution"

    def detect(self, df):
        o, h, l, c, a = self.o, self.h, self.l, self.c, self.atr
        n = len(c)
        sc = _selling_climax(self, df)
        vma = lagged_mean(df["volume"], 20)
        cp = close_pos(o, h, l, c)
        last_used = -1
        for s in np.flatnonzero(sc):
            if s <= last_used or s + 11 >= n:
                continue
            sup, res = l[s], h[s + 1:s + 11].max()
            mid = (sup + res) / 2
            j = s + 11
            while j < min(s + 91, n):
                if c[j] > res:                       # left the range upward without a spring
                    break
                if l[j] < sup:
                    back = next((k for k in range(j, min(j + 4, n)) if c[k] >= sup), None)
                    if back is None:
                        break
                    spring_low = l[j:back + 1].min()
                    for k in range(back + 1, min(back + 31, n)):
                        if c[k] < spring_low:
                            break
                        if (c[k] > o[k] and h[k] - l[k] > 1.3 * a[k - 1] and cp[k] > 0.7
                                and self.v[k] > 1.5 * vma[k] and c[k] > mid):
                            self.add_event(k, spring_low)
                            last_used = k
                            break
                    break
                j += 1


class SpringTest(LibraryTool):
    """Trading range = the prior 40 bars' high/low, no wider than 8 x ATR. Spring: a low below
    support and a close back above it within 3 bars. Entry on the TEST (the page's "wait for
    Test"): within 20 bars, after price has risen > 0.5 x ATR above the spring low, a bar that
    holds above the spring low, comes within 1 x ATR of it, on lower volume and a narrower range
    than the break bar. Cancelled by a close > 0.5 x ATR below support. Stop below the spring low."""
    name, context, page = "wyckoff_spring_test", "any", "wyckoff-spring-upthrust"

    def detect(self, df):
        h, l, c, a, v = self.h, self.l, self.c, self.atr, self.v
        n = len(c)
        sup = df["low"].rolling(40).min().shift(1).to_numpy()
        res = df["high"].rolling(40).max().shift(1).to_numpy()
        b = 41
        while b < n:
            if not (np.isfinite(a[b - 1]) and res[b] - sup[b] <= 8 * a[b - 1] and l[b] < sup[b]):
                b += 1
                continue
            S, A = sup[b], a[b - 1]
            back = next((k for k in range(b, min(b + 4, n)) if c[k] >= S), None)
            if back is None:
                b += 1
                continue
            spring_low = l[b:back + 1].min()
            hi_since, nxt = h[back], back + 1
            for t in range(back + 1, min(back + 21, n)):
                nxt = t + 1
                if c[t] < S - 0.5 * A or l[t] < spring_low:
                    break
                if (hi_since > spring_low + 0.5 * A and l[t] <= spring_low + A
                        and v[t] < v[b] and h[t] - l[t] < h[b] - l[b]):
                    self.add_event(t, spring_low)
                    break
                hi_since = max(hi_since, h[t])
            b = nxt


class VSAStoppingVolume(LibraryTool):
    """Stopping volume in a downtrend: falling 20-bar regression slope, volume > 1.5 x average,
    close in the top 30% of the bar. Stop below the bar's low."""
    name, context, page = "wyckoff_vsa_stopping_volume", "any", "wyckoff-vsa"

    def detect(self, df):
        slope = linreg_slope(self.c, 20)
        vma = lagged_mean(df["volume"], 20)
        cp = close_pos(self.o, self.h, self.l, self.c)
        with np.errstate(invalid="ignore"):
            hit = (slope < 0) & (self.v > 1.5 * vma) & (cp > 0.7)
        for i in np.flatnonzero(hit):
            self.add_event(i, self.l[i])


class VSANoSupply(LibraryTool):
    """No supply in an uptrend: down bar, range < 0.7 x 20-bar average range, volume < 0.7 x
    average. Stop below the bar's low."""
    name, context, page = "wyckoff_vsa_no_supply", "up", "wyckoff-vsa"

    def detect(self, df):
        rng = pd.Series(self.h - self.l, index=df.index)
        rma = lagged_mean(rng, 20)
        vma = lagged_mean(df["volume"], 20)
        with np.errstate(invalid="ignore"):
            hit = (self.c < self.o) & (rng.to_numpy() < 0.7 * rma) & (self.v < 0.7 * vma)
        for i in np.flatnonzero(hit):
            self.add_event(i, self.l[i])


class PriceCycleMarkupPullback(LibraryTool):
    """Markup phase (ADX > 20 and 20 EMA > 50 EMA for 3 straight bars), then a bar that dips to
    the 50 EMA and closes above it (the page's 'pullback toward the slow EMA'). Stop below the
    bar's low."""
    name, context, page = "wyckoff_price_cycle_pullback", "any", "wyckoff-price-cycle"

    def detect(self, df):
        e20 = df["close"].ewm(span=20, adjust=False).mean().to_numpy()
        e50 = df["close"].ewm(span=50, adjust=False).mean().to_numpy()
        markup = (adx(df) > 20) & (e20 > e50)
        m3 = markup & np.r_[False, markup[:-1]] & np.r_[False, False, markup[:-2]]
        for i in range(60, len(e50)):
            if m3[i] and self.l[i] <= e50[i] < self.c[i]:
                self.add_event(i, self.l[i])


class SOSLastPoint(LibraryTool):
    """SOS bar (up bar, range > 1.3 x prior ATR, close in top 30%, volume > 1.5 x average), then
    the first LPS within 12 bars (range < 0.8 x ATR, volume < 0.7 x average, low above the SOS
    low, close below the SOS high). Buy after the LPS; stop below the SOS low."""
    name, context, page = "wyckoff_sos_lps", "any", "wyckoff-sos-sow"

    def detect(self, df):
        o, h, l, c, a, v = self.o, self.h, self.l, self.c, self.atr, self.v
        vma = lagged_mean(df["volume"], 20)
        cp = close_pos(o, h, l, c)
        for s in range(15, len(c)):
            if not (c[s] > o[s] and h[s] - l[s] > 1.3 * a[s - 1] and cp[s] > 0.7 and v[s] > 1.5 * vma[s]):
                continue
            for k in range(s + 1, min(s + 13, len(c))):
                if l[k] <= l[s]:
                    break
                if h[k] - l[k] < 0.8 * a[k - 1] and v[k] < 0.7 * vma[k] and c[k] < h[s]:
                    self.add_event(k, l[s])
                    break


class ComparativeStrength(LibraryTool):
    """Bullish divergence vs SPY over two adjacent 20-bar windows: the stock makes a higher low
    while SPY makes a lower low. Fires on the first bar it's true, 10-bar cooldown. Stop below
    the stock's low of the recent window. Needs a benchmark close series (set_benchmark)."""
    name, context, page = "wyckoff_comparative_strength", "any", "wyckoff-comparative-strength"
    benchmark: pd.Series | None = None

    def detect(self, df):
        if self.benchmark is None:
            return
        b = self.benchmark.reindex(df.index).ffill()
        s_low = df["low"].rolling(20).min()
        b_low = b.rolling(20).min()
        s_now, s_prev = s_low.to_numpy(), s_low.shift(20).to_numpy()
        b_now, b_prev = b_low.to_numpy(), b_low.shift(20).to_numpy()
        with np.errstate(invalid="ignore"):
            div = (s_now > s_prev) & (b_now < b_prev)
        last = -99
        for i in range(41, len(div)):
            if div[i] and not div[i - 1] and i - last >= 10:
                self.add_event(i, s_now[i])
                last = i


class Reaccumulation(LibraryTool):
    """Uptrend (20 EMA > 50 EMA) when a 15-bar range first tightens to <= 6% of its midpoint.
    The zone grows with new highs/lows; invalid past 9% or after 120 bars. Buy after a close above
    the zone high (re-accumulation). Stop below the zone low."""
    name, context, page = "wyckoff_reaccumulation", "any", "wyckoff-reaccumulation-redistribution"

    def detect(self, df):
        h, l, c = self.h, self.l, self.c
        e20 = df["close"].ewm(span=20, adjust=False).mean().to_numpy()
        e50 = df["close"].ewm(span=50, adjust=False).mean().to_numpy()
        hi = df["high"].rolling(15).max().to_numpy()
        lo = df["low"].rolling(15).min().to_numpy()
        pct = (hi - lo) / ((hi + lo) / 2)
        i, n = 15, len(c)
        while i < n:
            if not (pct[i] <= 0.06 and pct[i - 1] > 0.06):
                i += 1
                continue
            up, H, L = e20[i] > e50[i], hi[i], lo[i]
            j = i + 1
            while j < n and j - i <= 120:
                if c[j] > H:
                    if up:
                        self.add_event(j, L)
                    break
                if c[j] < L:
                    break
                H, L = max(H, h[j]), min(L, l[j])
                if (H - L) / ((H + L) / 2) > 0.09:
                    break
                j += 1
            i = max(i + 15, j + 1)     # cooldown


ICT_TOOLS = [OrderBlock, FairValueGap, VolumeImbalance, Displacement, Unicorn, PremiumDiscountOTE,
             DealingRange, IPDARange, MarketStructureCHoCH, MarketStructureBOS, LiquiditySweep,
             KeyLevelSweep, NWOG, MarketMakerBuyModel, SDBreakout, SDTargets]
WYCKOFF_TOOLS = [WyckoffAccumulation, SpringTest, VSAStoppingVolume, VSANoSupply,
                 PriceCycleMarkupPullback, SellingClimax, SOSLastPoint, ComparativeStrength,
                 Reaccumulation]
ALL_TOOLS = ICT_TOOLS + WYCKOFF_TOOLS

# Pages with no daily-bar test (intraday time windows, or a second instrument).
NOT_TESTED = {
    "ict-killzones-sessions": "intraday session windows; draws nothing on daily charts",
    "ict-silver-bullet": "needs 1m-15m bars inside 1-hour New York windows",
    "ict-macro-times": "20-30 minute windows; needs 1m-5m bars",
    "ict-power-of-3": "Asia/London/NY session phases; page says US stocks form no cycles",
    "ict-midnight-open": "midnight ET open needs intraday bars (daily proxy is just the open)",
    "ict-smt-divergence": "needs a correlated pair (ES/NQ etc.), not single stocks",
}
