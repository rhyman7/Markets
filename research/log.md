# Research log

Newest first. Record every experiment, including the ones that didn't work.

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
