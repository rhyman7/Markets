from .base import Setup, Strategy
from .fib_pullback import FibParams, FibPullback
from .fib_textbook import FibTextbook, FibTextbookI, TextbookParams
from .trend_baseline import TrendBaseline
from . import breakout, library

# Register new strategies here so scan.py and backtest.py can find them by name.
STRATEGIES: dict[str, type[Strategy]] = {
    FibPullback.name: FibPullback,
    FibTextbook.name: FibTextbook,
    FibTextbookI.name: FibTextbookI,
    TrendBaseline.name: TrendBaseline,
}
# FibAlgo library tools (shared template; see library.py). wyckoff_comparative_strength needs a
# benchmark series, which only experiment.py supplies, so it finds nothing via backtest.py.
STRATEGIES.update({t.name: t for t in library.ALL_TOOLS + breakout.BREAKOUT_TOOLS})

__all__ = ["Setup", "Strategy", "FibPullback", "FibParams", "FibTextbook", "FibTextbookI", "TextbookParams", "TrendBaseline", "STRATEGIES"]
