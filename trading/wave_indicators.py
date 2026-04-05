"""Technical indicators for wave trading: SMA, Bollinger Bands, RSI, ATR."""

import numpy as np
import pandas as pd


def sma(closes: pd.Series, period: int = 20) -> pd.Series:
    """Simple Moving Average."""
    return closes.rolling(window=period).mean()


def bollinger_bands(closes: pd.Series, period: int = 20, num_std: float = 2.0
                    ) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands: (middle, upper, lower)."""
    middle = sma(closes, period)
    std = closes.rolling(window=period).std()
    return middle, middle + num_std * std, middle - num_std * std


def rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing)."""
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(high: pd.Series, low: pd.Series, close: pd.Series,
        period: int = 14) -> pd.Series:
    """Average True Range (Wilder's smoothing)."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def compute_all_indicators(df: pd.DataFrame, bb_period: int = 20,
                           bb_std: float = 2.0, rsi_period: int = 14,
                           atr_period: int = 14) -> dict | None:
    """Compute all indicators for a stock's historical DataFrame.

    Args:
        df: DataFrame with columns Open, High, Low, Close, Volume

    Returns dict with latest scalar values and full series, or None if
    insufficient data.
    """
    if df is None or len(df) < max(bb_period, rsi_period, atr_period) + 10:
        return None

    closes = df["Close"]
    highs = df["High"]
    lows = df["Low"]
    volumes = df["Volume"]

    sma_20 = sma(closes, bb_period)
    bb_mid, bb_upper, bb_lower = bollinger_bands(closes, bb_period, bb_std)
    rsi_14 = rsi(closes, rsi_period)
    atr_14 = atr(highs, lows, closes, atr_period)
    avg_vol = volumes.rolling(20).mean()

    current_price = float(closes.iloc[-1])
    upper = float(bb_upper.iloc[-1])
    lower = float(bb_lower.iloc[-1])
    width = upper - lower
    bb_pos = (current_price - lower) / width if width > 0 else 0.5

    return {
        "current_price": current_price,
        "sma_20": float(sma_20.iloc[-1]),
        "bb_upper": upper,
        "bb_lower": lower,
        "bb_middle": float(bb_mid.iloc[-1]),
        "bb_position": round(max(0, min(1, bb_pos)), 4),
        "rsi": round(float(rsi_14.iloc[-1]), 2),
        "atr": round(float(atr_14.iloc[-1]), 4),
        "atr_pct": round(float(atr_14.iloc[-1]) / current_price * 100, 2),
        "avg_volume": int(avg_vol.iloc[-1]) if not pd.isna(avg_vol.iloc[-1]) else 0,
        "current_volume": int(volumes.iloc[-1]),
        "volume_ratio": round(float(volumes.iloc[-1] / avg_vol.iloc[-1]), 2)
        if avg_vol.iloc[-1] > 0 else 0,
        # Full series for trend analysis
        "_sma_20": sma_20,
        "_bb_upper": bb_upper,
        "_bb_lower": bb_lower,
        "_rsi": rsi_14,
        "_atr": atr_14,
    }
