# Research log

Newest first. Record every experiment, including the ones that didn't work.

## 2026-11-10 — FibAlgo library screen: plan (written before any run on real data)

Request: test every tool on the 28 FibAlgo ICT/Wyckoff library pages. Reviewed all 28.
**None of them gives entry, stop or target rules or any backtest evidence**; each says the
indicator "does not generate buy/sell signals". So this tests my mechanical reading of each
concept with one shared trade template, not FibAlgo's indicators themselves.

**Not testable on daily stock bars (6):** killzones, silver bullet, macro times, power of 3,
midnight open (all need intraday bars), SMT divergence (needs a correlated pair like ES/NQ).
Revisit only if minute data is added.

**Tested (22 pages → 25 rules, long side only; the backtester can't short):** order blocks,
FVG, volume imbalance, displacement, unicorn, premium/discount OTE, dealing range, IPDA range,
market structure (CHoCH and BOS as two rules), liquidity sweep, key-level sweep (prior
week/month low), NWOG, market maker buy model, standard deviation (2R exit and SD-target exit
as two rules), Wyckoff accumulation (SC → spring → SOS), spring + test, VSA (stopping volume
and no supply as two rules), price cycle (markup + pullback to 50 EMA), selling climax + AR,
SOS → LPS, comparative strength (bullish divergence vs SPY), re-accumulation breakout.
Exact rules: `markets/strategies/library.py` docstrings.

**Shared template (no per-tool tuning):** close ≥ $10, 50-day volume ≥ 1M. Zone tools: buy
limit at the zone's 50% level for 20 bars, one attempt per zone. Event tools: buy the next
open. Stop = the tool's structure level − 0.1 ATR, risk floored at 0.5 ATR, skip if > 5 ATR.
Exit all at +2R, the stop, or after 20 bars. "Up" tools also need the control's uptrend
filter; reversal/range tools don't.

**Control (new, per tool):** random entries with the same filter, context and exits, and the
tool's median risk in ATR. For zone tools, the control also uses a one-bar buy limit at the
tool's median distance below the close. This matters: with tight stops on daily bars the
engine's conservative rules (stop before target on the same bar) cost limit entries about
0.1–0.15R on driftless data. A matched control cancels that. Check on driftless synthetic
data (120 tickers × 10 years): tool − control within ±2.2 SE for all 25; 0 of 25 passed.

**Engine fix found while building this:** on the bar where a buy limit filled below the open,
the backtester counted the bar's high toward the target, though that high may have come
before the fill. Now the target only counts on that bar if the close reached it. This
affects only limit-entry variants (fib_textbook G and J from earlier today), which were
slightly flattered. Variant I uses market entries and is unaffected.

**Pass rules, screen on large caps (universe.txt):** ≥ 100 trades, gap vs its control
≥ +0.10R overall with z ≥ 2.0, and gap > 0 both before and after 2021.
With 25 rules tested, expect about 0–1 to pass by luck alone (one-sided p ≈ 0.02 each).
**Holdout:** every passing rule, unchanged, on S&P SmallCap 600 stocks not in either existing
universe (universe_smallcap.txt). Confirmed only with ≥ 100 trades, gap > 0 in both periods,
and z ≥ 1.5 overall. Nothing gets paper traded unless it is confirmed on the holdout.

Known biases as before: survivorship (today's lists for all history), no costs or slippage
(hurts tight-stop tools most, since costs are a bigger share of a small R).

## 2026-11-10 — Variant I on mid-caps with Alpaca data (data-source check)

Purpose: before switching from Yahoo to Alpaca, confirm the mid-cap result doesn't depend
on the data source. Same rules, same universe. Alpaca free plan, SIP (all-exchange) feed.
A separate check (run 42871829490) found Alpaca's adjusted closes match Yahoo to a median
0.002% on 5 tickers since 2016; its volume runs ~6% higher (likely includes extended hours),
so slightly more stocks pass the volume filter. MOG-A failed (symbol format, now fixed).
Run: https://github.com/rhyman7/Markets/actions/runs/42872327399

| Variant | Trades | Exp. R | 2016–20 (trades) | 2021–26 (trades) | Profit factor | Max DD |
|---|---|---|---|---|---|---|
| I (Alpaca) | 427 | +0.189 | +0.317 (103) | +0.148 (324) | 1.47 | 20R |
| F control (Alpaca) | 4,203 | +0.026 | +0.164 (1,132) | −0.025 (3,071) | 1.05 | 135R |
| I (Yahoo, earlier today) | 396 | +0.219 | +0.396 (90) | +0.167 (306) | 1.57 | 19R |
| F control (Yahoo) | 3,934 | +0.029 | +0.162 (1,013) | −0.017 (2,921) | 1.06 | 100R |

By year (I vs control, Alpaca): 2017 +1.28/+0.48, 2018 +0.04/−0.05, 2019 +0.40/+0.22,
2020 +0.31/+0.19, 2021 +0.29/−0.03, 2022 +0.05/−0.18, 2023 +0.10/+0.02,
2024 +0.47/+0.09, 2025 +0.05/−0.02, 2026 −0.12/−0.10.

Findings:
- **Same conclusion on both sources.** I beats the control in both periods; gap +0.16R
  overall (Yahoo: +0.19R). I is ahead in 9 of 10 years; 2026 is a near tie, slightly behind.
- The gap is a little smaller on Alpaca. The difference between sources (~0.03R) is well
  inside the noise, but it's a reminder that the exact figures aren't precise.

Decision: Alpaca is now the default data source on GitHub (sturdier than Yahoo, full volume).

## 2026-11-10 — Variant I vs control by year (mid-caps)

Rerun of fib_midcap with a by-year table for both variants and today's unfinished bar
dropped (the previous run, at 12:35 ET, had included it). WCC failed to download this time,
so 397 tickers. Totals barely changed: I 396 trades, +0.219R (+0.396 pre, +0.167 post);
control +0.029R.
Run: https://github.com/rhyman7/Markets/actions/runs/42866934330

| Year | I trades | I exp. R | Control trades | Control exp. R | Gap |
|---|---|---|---|---|---|
| 2017 | 10 | +1.279 | 107 | +0.522 | +0.76 |
| 2018 | 38 | +0.191 | 271 | −0.079 | +0.27 |
| 2019 | 24 | +0.405 | 284 | +0.237 | +0.17 |
| 2020 | 18 | +0.329 | 351 | +0.177 | +0.15 |
| 2021 | 45 | +0.371 | 551 | −0.004 | +0.38 |
| 2022 | 33 | +0.131 | 244 | −0.161 | +0.29 |
| 2023 | 49 | +0.119 | 378 | +0.015 | +0.10 |
| 2024 | 62 | +0.458 | 625 | +0.087 | +0.37 |
| 2025 | 62 | +0.010 | 528 | −0.033 | +0.04 |
| 2026 | 55 | −0.086 | 595 | −0.087 | +0.00 |

Findings:
- **I was ahead of the control in 9 of 10 years and level in 2026.** The edge is spread
  across years, not carried by one good stretch.
- **But the gap has shrunk to about zero in 2025–26.** Combined: I −0.035R on 117 trades,
  control −0.062R. With ~0.11R standard error on I there, that says nothing either way.
- **Both lost money in 2025–26 on mid-caps.** I's flat recent result reflects a bad market
  for buying mid-caps in uptrends, not I alone falling apart.
- No single year has enough I trades (10–62) to mean anything on its own.

Conclusion: unchanged. I is a live hypothesis with real support; the recent fade is the
main open question, and only forward data can answer it. Next: paper trade I forward
against the scanner, logging every signal including the ones not taken.

## 2026-11-10 — Variant I on fresh stocks (S&P MidCap 400)

Written down before running: variant I's rules unchanged, on 400 mid-caps that share no
ticker with universe.txt. I counts as confirmed only if it beats the control (F) in both
periods. Expected ~1,000 trades; got far fewer.

Data: universe_midcap.txt (398 of 400 tickers had enough history), 10 years of Yahoo daily
bars pulled 2026-11-10 ~12:35 ET, split 2021-01-01. No costs or slippage. Today's index
membership used for all history.
Run: https://github.com/rhyman7/Markets/actions/runs/42865573963

| Variant | Trades | Exp. R | 2016–20 (trades) | 2021–26 (trades) | Profit factor | Max DD |
|---|---|---|---|---|---|---|
| I. Reversal candle + RSI < 40 turning up | 392 | +0.215 | +0.386 (89) | +0.164 (303) | 1.55 | 18R |
| F. Random entries in uptrends (control) | 3,935 | +0.029 | +0.160 (1,014) | −0.017 (2,921) | 1.06 | 98R |

Findings:
- **I passed the test set in advance.** It beat the control in both periods. The gap is
  about +0.19R overall and +0.18R since 2021, roughly 3 and 2.6 standard errors (I's
  standard error is about ±0.06R overall, ±0.07R since 2021, assuming ~1.2R spread per trade).
- **I's own result barely moved between universes** (+0.177R large caps, +0.215R mid-caps).
  The gap opened mostly because the control fell from +0.132R to +0.029R on mid-caps.
- **The pre-2021 half is noise**: 89 trades.
- **The last two years are flat**: 2025 +0.017R (62 trades), 2026 −0.084R (55 trades).
  The control's by-year numbers weren't printed, so it's unknown whether I still beat it there.
- I by year: 2017 +1.28 (10), 2018 +0.16 (37), 2019 +0.41 (24), 2020 +0.33 (18),
  2021 +0.34 (45), 2022 +0.17 (31), 2023 +0.09 (48), 2024 +0.46 (62).
- Deeper pullbacks did better (50–61.8%: +0.46R, 139 trades; 38.2–50%: +0.08R, 253 trades).
  Noted only. Not to be tuned on.

Reasons the result is weaker than it looks:
- Survivorship may favour I over the control, not just flatter both: stocks in today's
  index are the ones whose sharp dips recovered, and I buys sharp dips.
- I's trades cluster in market sell-offs, so they aren't independent and the true
  standard error is larger than the figures above.
- No costs; mid-cap spreads are wider than large-cap.

Conclusion: first real evidence for I, from a test fixed in advance on unseen stocks.
Not proof, and not tradable on this alone. Next: print the control by year to check
2025–26, then paper trade I forward.

## 2026-11-10 — Textbook 4-step Fibonacci (variants fixed before running)

Same data and caveats as the entry below. Run: https://github.com/rhyman7/Markets/actions/runs/42863792799

| Variant | Trades | Exp. R | 2016–20 | 2021–26 | Profit factor |
|---|---|---|---|---|---|
| A. fib_pullback (reference) | 1,146 | +0.075 | +0.354 | −0.039 | 1.13 |
| G. Limit buy at 0.559, stop < 78.6% | 1,340 | +0.082 | +0.019 | +0.118 | 1.13 |
| H. Reversal candle in 38.2–61.8% zone | 587 | +0.165 | +0.341 | +0.091 | 1.42 |
| I. H + RSI < 40 and turning up | 358 | +0.177 | +0.303 | +0.114 | 1.46 |
| J. G + 50-day SMA in zone | 637 | +0.060 | +0.083 | +0.047 | 1.09 |
| F. Random entries in uptrends (control) | 3,862 | +0.132 | +0.185 | +0.104 | 1.30 |

Findings:
- **Candle confirmation is the only thing that helped.** H and I are the best Fib variants
  so far and the only ones above the control overall.
- **But the gap is within noise.** With ~1.2R spread per trade, I's standard error is about
  ±0.06R overall and ±0.08R since 2021. I vs control: +0.18 vs +0.13 overall and +0.11 vs
  +0.10 since 2021. Nine variants have now been tested, so one landing a bit above the
  control is expected by chance alone.
- **The plain limit order (G) did not help**, and had by far the worst drawdown (120R).
- **50-day confluence (J) made things worse.**

Conclusion: no Fib version shows a clear edge over random entries in uptrends.
I (reversal candle + RSI) is the only candidate worth following, and only as a hypothesis.

To confirm or reject I without more tuning: test it unchanged on stocks it hasn't been
tested on (e.g. a mid-cap universe), and/or paper trade it forward.

## 2026-11-10 — Why does fib_pullback trail random entries?

Data: 142 tickers in universe.txt, 10 years of Yahoo daily bars, split 2021-01-01.
No costs or slippage. Survivorship bias flatters every variant, including the control.
Run: https://github.com/rhyman7/Markets/actions/runs/42862030240

| Variant | Trades | Exp. R | 2016–20 | 2021–26 |
|---|---|---|---|---|
| A. Fib rules as written | 1,144 | +0.075 | +0.354 | −0.039 |
| B. Fib entries, 5% stop, Fib targets | 1,349 | +0.022 | +0.207 | −0.053 |
| C. Fib entries, baseline stop/targets | 1,388 | +0.033 | +0.156 | −0.022 |
| D. Like C, no close-above-high trigger | 3,559 | +0.071 | +0.091 | +0.062 |
| E. Fib rules, no 2:1 filter | 1,447 | +0.063 | +0.252 | −0.019 |
| F. Random entries in uptrends (control) | 3,862 | +0.132 | +0.185 | +0.104 |

Findings:
- **The entries are the problem.** With identical trade management, Fib-selected entries
  (C, +0.03R) did worse than random entries in the same uptrends (F, +0.13R).
- **The Fib stop isn't the problem.** Swapping it for a fixed 5% stop made results worse (B vs A).
- **The confirmation trigger hurts.** Entering anywhere in the zone beat waiting for a close
  above the prior high (D vs C).
- **The 2:1 filter barely matters** (E vs A).
- **No sign that the Fib levels themselves matter.** Shallow pullbacks (<38.2%) did best,
  38.2–50% worst, 50–61.8% in between, which doesn't fit the theory.
- The pre-2021 strength leans on 2017 (36 trades, +1.5R). Since 2021 the rules lose money.

Conclusion: in this sample, buying weakness (pullbacks) inside uptrends did worse than
buying at random inside uptrends. Not tradable as written.

Next hypothesis: if pullback entries pick weaker moments, strength-based entries
(e.g. breakouts to new highs inside uptrends) may beat the control. Test against F.
