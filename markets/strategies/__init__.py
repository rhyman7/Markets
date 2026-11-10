from .base import Setup, Strategy
from .fib_pullback import FibParams, FibPullback
from .trend_baseline import TrendBaseline

# Register new strategies here so scan.py and backtest.py can find them by name.
STRATEGIES: dict[str, type[Strategy]] = {
    FibPullback.name: FibPullback,
    TrendBaseline.name: TrendBaseline,
}

__all__ = ["Setup", "Strategy", "FibPullback", "FibParams", "TrendBaseline", "STRATEGIES"]
