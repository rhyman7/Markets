from .base import Setup, Strategy
from .fib_pullback import FibParams, FibPullback
from .fib_textbook import FibTextbook, TextbookParams
from .trend_baseline import TrendBaseline

# Register new strategies here so scan.py and backtest.py can find them by name.
STRATEGIES: dict[str, type[Strategy]] = {
    FibPullback.name: FibPullback,
    FibTextbook.name: FibTextbook,
    TrendBaseline.name: TrendBaseline,
}

__all__ = ["Setup", "Strategy", "FibPullback", "FibParams", "FibTextbook", "TextbookParams", "TrendBaseline", "STRATEGIES"]
