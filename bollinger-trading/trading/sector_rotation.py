"""Inverse sector allocation: worst-performing sector gets highest weight."""

import logging

import numpy as np
import pandas as pd

from trading.config import (
    SECTOR_PERF_PERIOD_DAYS,
    SECTOR_MIN_ALLOCATION,
    SECTOR_MAX_ALLOCATION,
)
from trading.universe import SECTORS, SYMBOL_TO_SECTOR, SECTOR_NAMES

logger = logging.getLogger("trading")


def compute_sector_performance(
    historical: dict,
    period: int = SECTOR_PERF_PERIOD_DAYS,
) -> dict:
    """Compute average return per sector over the lookback period.

    Args:
        historical: {symbol: DataFrame} with 'Close' column
        period: number of trading days to measure

    Returns:
        {sector_name: average_return_pct}
    """
    sector_returns = {s: [] for s in SECTOR_NAMES}

    for sym, df in historical.items():
        if df is None or len(df) < 2:
            continue
        sector = SYMBOL_TO_SECTOR.get(sym)
        if sector is None:
            continue

        closes = df["Close"].iloc[-period:]
        if len(closes) < 2:
            continue

        ret = (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0]
        sector_returns[sector].append(float(ret))

    performances = {}
    for sector, returns in sector_returns.items():
        if returns:
            performances[sector] = np.mean(returns)
        else:
            performances[sector] = 0.0

    return performances


def compute_sector_allocations(performances: dict) -> dict:
    """Inverse-weight sectors: worst performer gets highest allocation.

    Steps:
        1. Invert returns (negate)
        2. Shift so all values are positive
        3. Normalise to sum to 1.0
        4. Clamp to [SECTOR_MIN_ALLOCATION, SECTOR_MAX_ALLOCATION]
        5. Re-normalise after clamping

    Returns:
        {sector_name: allocation_fraction} summing to 1.0
    """
    if not performances:
        # Equal weight fallback
        n = len(SECTOR_NAMES)
        return {s: 1.0 / n for s in SECTOR_NAMES}

    # Step 1: negate so worst performer has highest value
    inverted = {s: -r for s, r in performances.items()}

    # Step 2: shift to positive
    min_val = min(inverted.values())
    shifted = {s: v - min_val + 0.01 for s, v in inverted.items()}

    # Step 3: normalise
    total = sum(shifted.values())
    alloc = {s: v / total for s, v in shifted.items()}

    # Step 4: clamp
    for s in alloc:
        alloc[s] = max(SECTOR_MIN_ALLOCATION, min(SECTOR_MAX_ALLOCATION, alloc[s]))

    # Step 5: re-normalise after clamping
    total = sum(alloc.values())
    alloc = {s: v / total for s, v in alloc.items()}

    return alloc
