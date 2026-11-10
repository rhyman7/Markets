# Research log

Newest first. Record every experiment, including the ones that didn't work.

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
