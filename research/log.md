# Research log

Newest first. Record every experiment, including the ones that didn't work.

## 2026-11-12 — Results: variant I on Robinhood's crypto list

Plan and pass rules: next entry down (written before these runs). Coinbase daily bars (UTC
days) through 2026-11-11, split 2023-01-01. 77 of 89 coins had enough data. Left out: not on
Coinbase in USD (CC, CASHCAT, MEW, GRAM, LIT, MNT, XDC) or under 251 bars (BILL, MEGA, RE,
CHIP, VIRTUAL).
Runs: https://github.com/rhyman7/Markets/actions/runs/43220486270 (95 bps),
https://github.com/rhyman7/Markets/actions/runs/43220502873 (5 bps).

| Costs/side | Variant | Trades | Exp R | Before 2023 | 2023–26 | PF | Max DD |
|---|---|---|---|---|---|---|---|
| 95 bps | I | 132 | −0.180 | −0.017 (26) | −0.220 (106) | 0.69 | 37R |
| 95 bps | M matched control (22.5% stop) | 452 | −0.167 | +0.081 | −0.278 | 0.69 | 100R |
| 95 bps | F stock control (5% stop) | 697 | −0.450 | −0.392 | −0.475 | 0.40 | 314R |
| 5 bps | I | 132 | −0.091 | +0.066 | −0.129 | 0.83 | 31R |
| 5 bps | M | 452 | −0.087 | +0.163 | −0.200 | 0.83 | 83R |
| 5 bps | F | 697 | −0.090 | −0.032 | −0.116 | 0.84 | 76R |

Gap I − M: **−0.013R, z −0.1** at 95 bps (before 2023 −0.098R, after +0.058R); −0.003R at 5 bps.
**RESULT: FAIL.** The claim that Fibonacci works better on crypto than on stocks is not supported.

- Variant I lost money on these coins and so did random entries in the same uptrends, by the
  same amount. The Fibonacci entry added nothing. On mid-cap stocks the gap was +0.175R.
- It lost even before realistic costs (−0.09R at 5 bps). Robinhood-level costs took another
  0.09R per trade off I, and 0.36R off the 5%-stop control.
- Win rate 37%; 59 of 132 trades hit the full stop. I by year at 95 bps: 2021 +0.48 (11 trades),
  2023 −0.05 (18), 2024 −0.02 (51), 2025 −0.50 (29), 2026 −0.88 (8). No year with 20+ trades
  was positive.
- Only 132 trades over 50 coins, 26 of them before 2023, so the split comparison is noise.
  The estimate is loose (standard error of the gap about 0.11R): a small real edge can't be
  ruled out, but an edge bigger than the mid-cap one is unlikely, and survivorship bias
  pushes these numbers up, not down.
- Even "buy coins in uptrends at random" lost since 2023 on this list, despite the list being
  made of today's survivors. A long-only daily pullback approach on these coins has had no
  tailwind to lean on.

Decision, per the plan: crypto does not go on the paper-trading list, and no other Fibonacci
variants get tried on crypto to find one that works. The Coinbase loader, universe and
`fib_crypto` experiment stay in the repo for any future, different idea.

Rule/universe count on this repo: 35 tried, 1 confirmed on fresh stocks (variant I, mid-caps).

## 2026-11-12 — Variant I on Robinhood's crypto list: plan (written before running)

Results: entry above. This plan was committed (10ec68b) before any real crypto prices were loaded.

**Claim under test (Ryan's):** Fibonacci entries should work better on crypto than on stocks.
**What the run can show:** whether variant I beats random entries in the same crypto uptrends,
and whether that gap is larger than the +0.175R it had on mid-caps.

**Universe:** `universe_crypto.txt`, the 91 assets on Robinhood's US availability page
(read 2026-11-12) minus the two dollar stablecoins (USDC, USDG) = 89 coins.
**Data:** Coinbase Exchange public daily candles, USD pairs, UTC days, up to 10 years. Coins
Coinbase doesn't list, or with 250 bars or fewer, are left out and named in the output.
(Alpaca's crypto feed covers far fewer coins; Yahoo's crypto tickers are ambiguous.)

**Rules:** variant I exactly as frozen. Two forced changes, both liquidity filters that make
no sense for coins: no $10 minimum price, and "50-day average volume >= 1M shares" becomes
"50-day average dollar volume >= $1M on Coinbase". Nothing else changes: same uptrend filter
(50-day > 200-day and rising), same zone, candle, RSI, stop and targets, 40-bar time stop.
Bars are calendar days, so "200-day" is 200 calendar days, about 6.5 months instead of 9.5.
Signal on a UTC daily close, buy at the next UTC open (7 PM or 8 PM Eastern).

**Control (primary):** M, random entries (5% of days) under the same filters, stop = the
median stop distance of I's own trades, half off at +1R, rest at +2R, same 40-bar limit. The
stock control F (5% stop, +5%/+10%) is also printed for reference only: a 5% stop is inside
one day's normal range for most coins, so it isn't a fair comparison here.

**Costs:** 95 bps per side (Robinhood's entry-tier taker fee, and about what it keeps from the
spread on market-maker routing). A second run at 5 bps is for comparison with the stock runs.

**Split:** 2023-01-01, not 2021: most of these coins have little or no history before 2021.

**Pass rules (same as the screens):** >= 100 trades, gap vs M >= +0.10R with z >= 2.0, and
gap > 0 both before and after the split. "Better than stocks" additionally needs the gap to
be above +0.175R; with a few hundred trades that comparison will be loose either way.

**Known problems, set down beforehand:**
- Survivorship is much worse than for stocks. Robinhood lists coins after they've become
  popular, and dead coins are gone. This inflates every number, the control's included.
- Many coins were listed in 2023-26 and have little history. Trades will be concentrated in
  a couple of dozen older coins, and coins move together, so the trades are less independent
  than the count suggests and z is overstated.
- This is rule/universe try number 35. A pass here would need a fresh confirmation (other
  coins, or forward signals) before it means anything.
- If it fails, it doesn't go on the paper-trading list, and other Fibonacci variants are not
  to be tried on crypto afterwards to find one that works.

Sanity check done: on 40 synthetic random-walk "coins" with upward drift, I and M both made
about +0.23R and the gap was +0.002R, so the comparison itself isn't biased toward I.

## 2026-11-11 — Dashboard added (no experiment, no rule changes)

`dashboard.py` + the Dashboard workflow publish a page of current setups for the 33 rules that
can be scanned as written (5 Fibonacci, 25 FibAlgo, 3 breakout/momentum; variants H and J are
built from `TextbookParams`).
Variant I is shown first; the rest are labelled with their backtest gap vs control from the
entries below. No rule or parameter changed. `fib_textbook` now also reports the pullback's
RSI readings in `Setup.levels` (used for the watch list, not by any rule); all tests pass,
including a new one that the dashboard's signal replay matches the backtester trade for trade
and that no row changes when today's unfinished bar is added.
Not tested on real data from Claude's sandbox (market data is unreachable there): the first
workflow run is the check.

## 2026-11-10 — Results: variant I with costs, breakout/momentum screen

Both at 5 bps per side, Alpaca data through 2026-11-09, split 2021-01-01.

**Variant I on mid-caps with costs** (run https://github.com/rhyman7/Markets/actions/runs/42880007829):
I +0.177R on 427 trades (2016–20 +0.305 on 103, 2021–26 +0.137 on 324), PF 1.43, max DD 21R.
Control F +0.002R on 4,203 (2016–20 +0.144, 2021–26 −0.050). Gap +0.175R, vs +0.163R
without costs. **Costs cost I only ~0.01R and the control ~0.02R** (I's stops are wider
than F's 5%). 2026 is still a loss for both (I −0.127 on 57 trades, F −0.142). Conclusion
unchanged: I is still a live hypothesis; the recent fade is still the open question.

**Breakout/momentum screen on large caps** (run https://github.com/rhyman7/Markets/actions/runs/42880020909):

| Rule | Trades | Tool R | Control R | Gap | z | Gap 2016–20 | Gap 2021–26 |
|---|---|---|---|---|---|---|---|
| breakout_52w_high | 3,353 | +0.067 | +0.087 | −0.019 | −0.8 | −0.050 | −0.002 |
| breakout_squeeze | 1,980 | +0.064 | +0.080 | −0.016 | −0.7 | −0.068 | +0.013 |
| momentum_top_decile | 1,097 | +0.005 | +0.108 | −0.103 | −2.5 | −0.197 | −0.051 |

**Passed: none (0 of 3).** Buying a 52-week high or a tight-range breakout made money, but no
more than random entries in the same uptrends. Buying stocks as they entered the top decile
of 6-month returns was clearly worse than random (z −2.5), worst before 2021. With a +2R /
20-bar exit, buying after a strong run tends to buy short-term exhaustion. This doesn't test
momentum held for months (see the caveat in the plan). Nothing goes to the holdout.

Rule count on this repo: 34 tried, 1 confirmed on fresh stocks (variant I).

## 2026-11-10 — Costs added; breakout/momentum screen: plan (written before running)

**Costs.** The backtester now charges commission + slippage per side as a fraction of
price, taken out of R (`--cost-bps`, default 5 bps = 0.05% per side, about 0.1% round trip).
That's realistic-to-optimistic for liquid large caps on market orders. All results from
here on include it unless they say otherwise. Results logged before this entry have no costs.
First check: rerun fib_midcap (variant I vs control) at 5 bps to see what's left of the
+0.16R gap. Expected: both drop. Variant I has a tighter typical stop, so it drops a bit more.

**Breakout/momentum screen.** The last open item on the list, and a different family from
everything tested so far (all pullbacks or reversals). 3 rules only, to keep luck down. Same
template and matched control as the FibAlgo screen, "up" context, so the control is random
entries in the same uptrends:
- breakout_52w_high: close above the prior 252 bars' highest close; stop below the 10-bar low.
- breakout_squeeze: prior 20 bars spanned <= 4 ATR, close above their high; stop below their low.
- momentum_top_decile: 126-bar return enters the universe's top 10% that day; stop below the
  10-bar low.
Caveat set beforehand: the template exits at +2R or 20 bars. Momentum's edge in the
literature comes from holding winners for months, so this tests breakout TIMING only, not
momentum as a holding strategy. If all three fail, that's the claim that fails.

Pass rules unchanged: >= 100 trades, gap >= +0.10R with z >= 2.0, gap > 0 in both halves.
Holdout for passes: universe_smallcap.txt, rules unchanged, at 10 bps per side (small caps
cost more to trade); confirmed with >= 100 trades, gap > 0 in both halves, z >= 1.5.
Rule count on this repo so far: 6 fib variants + 25 FibAlgo rules + these 3 = 34.

## 2026-11-10 — FibAlgo library screen: results (large caps)

Plan and pass rules: next entry down (written before this run). 142 tickers (universe.txt),
Alpaca SIP data through 2026-11-09 (no unfinished bar), split 2021-01-01, no costs.
Run: https://github.com/rhyman7/Markets/actions/runs/42878359718

**Passed: none (0 of 25).** No rule reached even half the +0.10R bar. So nothing goes to the
SmallCap 600 holdout. universe_smallcap.txt (600 fresh tickers) is built and kept for later tests.

Gap = tool expectancy − its matched random control (R). z = gap / combined standard error.

| Rule | Trades | Tool R | Control R | Gap | z | Gap 2016–20 | Gap 2021–26 |
|---|---|---|---|---|---|---|---|
| ICT displacement (FVG retest) | 843 | +0.022 | −0.033 | +0.055 | 0.8 | +0.219 | −0.026 |
| Wyckoff SOS → LPS | 1,001 | +0.181 | +0.136 | +0.045 | 1.0 | +0.052 | +0.050 |
| ICT NWOG retest | 2,057 | +0.016 | −0.015 | +0.031 | 0.8 | −0.008 | +0.053 |
| ICT order block | 722 | +0.081 | +0.062 | +0.019 | 0.2 | +0.088 | −0.021 |
| ICT FVG | 8,366 | +0.004 | −0.015 | +0.019 | 0.7 | +0.014 | +0.021 |
| ICT IPDA range | 2,948 | +0.155 | +0.148 | +0.007 | 0.3 | −0.046 | +0.035 |
| ICT key-level sweep | 16,797 | +0.090 | +0.083 | +0.007 | 0.3 | −0.007 | +0.018 |
| Wyckoff spring + test | 2,580 | +0.140 | +0.142 | −0.002 | −0.1 | +0.054 | −0.018 |
| Wyckoff VSA no supply | 4,484 | +0.016 | +0.019 | −0.003 | −0.1 | +0.049 | −0.039 |
| ICT SD breakout (2R) | 3,843 | +0.124 | +0.132 | −0.007 | −0.4 | −0.023 | −0.000 |
| ICT SD breakout (SD targets) | 3,835 | +0.121 | +0.132 | −0.011 | −0.5 | −0.028 | −0.003 |
| ICT BOS | 2,431 | +0.094 | +0.109 | −0.015 | −0.6 | +0.024 | −0.044 |
| ICT CHoCH/MSS | 2,990 | +0.105 | +0.122 | −0.017 | −0.8 | −0.090 | +0.019 |
| ICT volume imbalance | 13,728 | −0.014 | +0.004 | −0.018 | −0.7 | +0.001 | −0.033 |
| Wyckoff re-accumulation | 1,369 | +0.061 | +0.111 | −0.050 | −1.9 | −0.131 | −0.001 |
| ICT market maker buy | 323 | +0.049 | +0.103 | −0.054 | −1.2 | −0.241 | +0.018 |
| ICT liquidity sweep | 2,555 | +0.024 | +0.083 | −0.059 | −1.7 | −0.170 | −0.005 |
| ICT premium/discount OTE | 1,378 | +0.018 | +0.090 | −0.072 | −1.3 | −0.116 | −0.046 |
| ICT dealing range | 4,018 | +0.084 | +0.157 | −0.073 | −2.6 | +0.007 | −0.107 |
| Wyckoff VSA stopping volume | 3,323 | +0.062 | +0.136 | −0.074 | −2.2 | −0.222 | −0.006 |
| Wyckoff price cycle pullback | 2,665 | −0.006 | +0.083 | −0.089 | −1.9 | −0.179 | −0.045 |
| ICT unicorn | 140 | −0.093 | +0.003 | −0.095 | −0.7 | −0.198 | −0.052 |
| Wyckoff comparative strength | 2,551 | +0.021 | +0.151 | −0.130 | −4.4 | −0.186 | −0.101 |
| Wyckoff selling climax + AR | 250 | −0.071 | +0.145 | −0.216 | −2.9 | −0.746 | +0.122 |
| Wyckoff accumulation (SC→spring→SOS) | 11 | −0.139 | +0.122 | −0.261 | −1.3 | — | — |

Findings:
- **No ICT or Wyckoff rule beat random entries with the same stops and exits.** The 25 gaps
  sit around zero (median about −0.02R), close to what pure noise would give.
- **Several do worse than random.** Comparative strength (z −4.4), selling climax (−2.9),
  dealing range (−2.6) and stopping volume (−2.2) are significantly below their controls.
  These are long-only "bounce" or "relative strength" entries. Buying them was worse than
  buying at random. That's a reason to avoid them, not a short signal (shorts weren't tested).
- Positive raw R (SOS/LPS +0.18, spring test +0.14, IPDA +0.16) comes from buying stocks in
  a rising market. Their controls earned about the same.
- The best gaps (displacement +0.06, SOS/LPS +0.05) are about 1 SE and would be expected
  from 25 tries anyway. Running them on the holdout now would be a forking-path test.
- Caveat: this tests ONE mechanical reading of each concept with ONE exit template. A
  different reading could do differently, but each new variant adds to the count of tries.
  Accumulation fired only 11 times, so it is untested in practice.

Conclusion: FibAlgo's ICT/Wyckoff tools give no measurable edge on daily large-cap bars in
this form. Variant I remains the only live hypothesis. Tries so far on this repo: 25 here,
plus the 6 fib variants earlier.

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
