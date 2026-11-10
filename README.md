# Markets

Rule-based stock strategy research: scan for setups, backtest the rules, journal real trades.

Education and research only, not financial advice.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest            # sanity check
```

Data comes from Yahoo Finance via `yfinance` by default, cached in `cache/` for the day.
yfinance is free but breaks now and then. For something sturdier, get free API keys
from [Alpaca](https://alpaca.markets) (a paper account is enough), then
`cp .env.example .env` and fill in the keys.

## Daily use

```bash
python scan.py                       # today's setups across universe.txt
python scan.py --tickers UNH CI EOG  # specific stocks
```

Run it **after the 4 PM ET close**. An unfinished intraday bar is dropped automatically,
because the entry rule depends on the daily close. Status meanings:

- `TRIGGERED`: closed above the trigger and passes the reward/risk filter. Candidate to enter next session.
- `setting up`: in the zone and passes the filter, waiting for a close above the trigger.
- `pass (R:R)`: in the zone, but the reward isn't worth the risk.

Results print and are saved to `output/scan_<strategy>_<date>.csv`.

## Backtesting

```bash
python backtest.py                           # fib_pullback, 10 years, full universe
python backtest.py --strategy trend_baseline # the control
python backtest.py --split 2021-01-01        # does it hold up in both halves?
```

Results are in **R**: 1R = the amount risked on a trade. At 1% risk per trade,
+0.2R expectancy means about +0.2% of the account per trade on average, before costs.

How to read a result honestly:

1. **Compare against `trend_baseline`.** Buying stocks in uptrends during a rising
   market looks profitable with no skill. The Fibonacci rules only add value if they beat
   random entries in the same uptrends. (The test suite checks that both come out at
   about 0R on driftless random data, so the engine itself has no built-in bias.)
2. **Check both halves with `--split`.** An edge that only appears in one period is fragile.
3. **Few trades means noise.** Under ~100 trades, treat any number as a guess.
4. **Don't tune to the past.** Every parameter you tweak to improve the backtest makes
   it look better than the future will be. Change rules for a reason, then re-test.
5. **Known gaps:** no commissions or slippage; no earnings-date filter; today's
   `universe.txt` is used for all history (survivorship bias: stocks that failed
   aren't on the list, which flatters results); positions are not capped at 5.

The exact trade-management rules are documented at the top of `markets/backtest.py`.

## Layout

```
scan.py, backtest.py        command-line tools
universe.txt                tickers to scan
markets/data/loader.py      price data + cache (yfinance or Alpaca)
markets/strategies/         one file per strategy, registered in __init__.py
markets/backtest.py         trade simulation and stats
journal/trades.csv          your real and paper trades
tests/                      pytest
```

## Adding a strategy

1. Copy `markets/strategies/fib_pullback.py` as a starting point.
2. Implement `prepare()` (indicators) and `setup()` (returns a `Setup` for bar `i`, using only data up to `i`).
3. Register it in `markets/strategies/__init__.py`.
4. Backtest it against `trend_baseline` before using it.

## Strategy: `fib_pullback`

Long only, daily bars. The rules are listed at the top of `markets/strategies/fib_pullback.py`.
In short: in an established uptrend, after a swing of 10%+, buy a 30–70% Fibonacci
retracement once a daily close clears the prior day's high. Stop goes under the next
Fib level below the pullback low. Take half at the swing high, run the rest to the
127.2% extension, and take only setups with at least 2:1 reward/risk.
