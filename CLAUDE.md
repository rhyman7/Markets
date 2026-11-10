# Notes for Claude

Ryan's trading research repo. Read README.md first.

- Strategy rules live in code (`markets/strategies/`). When a rule changes, update the
  module docstring and README, add or adjust a test, and backtest before and after.
- Strategies may only use data up to bar `i` in `setup()`. No lookahead.
- Compare any strategy's backtest to `trend_baseline` on the same tickers and years.
- Run `python -m pytest` before committing.
- Never present scan or backtest output as a recommendation to trade. State the data
  date, and say when a daily bar was unfinished.
- Market data sites may be unreachable from Claude's sandbox. If so, say so, and either
  test with synthetic data or ask Ryan to run the command locally and share the output.
