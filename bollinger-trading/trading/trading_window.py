"""10% price window calculator using median-based centre."""

import logging

import numpy as np
import pandas as pd

from trading.config import (
    WINDOW_LOOKBACK_DAYS,
    WINDOW_HALF_WIDTH,
    STRONG_BUY_THRESHOLD,
    BUY_THRESHOLD,
    SELL_THRESHOLD,
    STRONG_SELL_THRESHOLD,
)

logger = logging.getLogger("trading")


class WindowResult:
    """Container for trading window calculation output."""

    __slots__ = (
        "symbol", "center", "upper", "lower",
        "current_price", "position", "z_score", "volatility",
    )

    def __init__(self, symbol, center, upper, lower, current_price,
                 position, z_score, volatility):
        self.symbol = symbol
        self.center = center
        self.upper = upper
        self.lower = lower
        self.current_price = current_price
        self.position = position
        self.z_score = z_score
        self.volatility = volatility

    def to_dict(self):
        return {s: getattr(self, s) for s in self.__slots__}


def compute_trading_window(
    symbol: str,
    historical_df: pd.DataFrame,
    current_price: float = None,
    lookback: int = WINDOW_LOOKBACK_DAYS,
) -> WindowResult | None:
    """Compute the trading window for a symbol.

    Uses the median of the last *lookback* closing prices as the centre,
    then +/- WINDOW_HALF_WIDTH (5%) to form a 10% window.

    Returns WindowResult or None if insufficient data.
    """
    if historical_df is None or len(historical_df) < 10:
        return None

    closes = historical_df["Close"].iloc[-lookback:]
    if len(closes) < 10:
        return None

    center = float(np.median(closes))
    upper = center * (1 + WINDOW_HALF_WIDTH)
    lower = center * (1 - WINDOW_HALF_WIDTH)

    if current_price is None:
        current_price = float(closes.iloc[-1])

    # Position within window: 0.0 = at lower bound, 1.0 = at upper bound
    window_width = upper - lower
    if window_width > 0:
        position = (current_price - lower) / window_width
    else:
        position = 0.5

    # Z-score relative to lookback distribution
    std = float(np.std(closes))
    mean = float(np.mean(closes))
    z_score = (current_price - mean) / std if std > 0 else 0.0

    # Annualised volatility
    returns = closes.pct_change().dropna()
    volatility = float(np.std(returns) * np.sqrt(252)) if len(returns) > 1 else 0.0

    return WindowResult(
        symbol=symbol,
        center=round(center, 2),
        upper=round(upper, 2),
        lower=round(lower, 2),
        current_price=round(current_price, 2),
        position=round(position, 4),
        z_score=round(z_score, 4),
        volatility=round(volatility, 4),
    )


# ---------------------------------------------------------------------------
# Window signal interpretation
# ---------------------------------------------------------------------------
STRONG_BUY = "STRONG_BUY"
BUY = "BUY"
HOLD = "HOLD"
SELL = "SELL"
STRONG_SELL = "STRONG_SELL"


def get_window_signal(window: WindowResult) -> str:
    """Translate window position into a signal string."""
    if window is None:
        return HOLD
    p = window.position
    if p < STRONG_BUY_THRESHOLD:
        return STRONG_BUY
    if p < BUY_THRESHOLD:
        return BUY
    if p > STRONG_SELL_THRESHOLD:
        return STRONG_SELL
    if p > SELL_THRESHOLD:
        return SELL
    return HOLD


def compute_all_windows(
    symbols: list,
    historical: dict,
    live_prices: dict,
) -> dict:
    """Compute windows for all symbols.

    Args:
        symbols: list of tickers
        historical: {symbol: DataFrame}
        live_prices: {symbol: float} current prices

    Returns:
        {symbol: WindowResult}
    """
    windows = {}
    for sym in symbols:
        df = historical.get(sym)
        price = live_prices.get(sym)
        windows[sym] = compute_trading_window(sym, df, price)
    return windows
