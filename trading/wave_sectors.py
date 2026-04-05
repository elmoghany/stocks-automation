"""Sector momentum tracking for wave trading rotation.

When one sector is overbought (momentum high), prioritize selling.
When another sector is oversold (momentum low), prioritize buying.
Rotate capital from hot sectors into cold sectors.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

logger = logging.getLogger("wave")

# Sector assignments for wave trading stocks
SECTOR_MAP = {
    # Tech
    "LRCX": "Tech", "VRT": "Tech", "AMD": "Tech", "ANET": "Tech",
    "CDNS": "Tech", "FICO": "Tech", "TSM": "Tech",
    # Industrials
    "FIX": "Industrials", "TJX": "Industrials", "MLI": "Industrials",
    "HUBB": "Industrials", "ETN": "Industrials", "DECK": "Industrials",
    "AWI": "Industrials", "CTAS": "Industrials", "BMI": "Industrials",
    # Healthcare
    "LLY": "Healthcare", "RMD": "Healthcare", "ISRG": "Healthcare",
    # Energy
    "TDW": "Energy", "AMSC": "Energy",
}

SECTORS = ["Tech", "Industrials", "Healthcare", "Energy"]


def get_sector(symbol: str) -> str:
    return SECTOR_MAP.get(symbol, "Unknown")


def compute_sector_momentum(historical: dict) -> dict:
    """Compute momentum score per sector from historical price data.

    For each sector, averages the momentum of its constituent stocks.

    Returns dict per sector:
        {
            "Tech": {
                "momentum_5d": +2.3%,    # avg 5-day return
                "momentum_20d": -5.1%,   # avg 20-day return
                "avg_rsi": 42.3,         # avg RSI across stocks
                "signal": "OVERSOLD",    # OVERBOUGHT / NEUTRAL / OVERSOLD
                "rank": 1,               # 1 = most oversold (best to buy)
                "stocks_in_buy_zone": 3, # how many are near lower BB
            }
        }
    """
    from trading.wave_indicators import rsi as calc_rsi

    sector_data = {s: {"returns_5d": [], "returns_20d": [], "rsis": [],
                        "bb_positions": []} for s in SECTORS}

    for sym, sector in SECTOR_MAP.items():
        df = historical.get(sym)
        if df is None or len(df) < 30:
            continue

        closes = df["Close"]
        current = float(closes.iloc[-1])

        # 5-day return
        if len(closes) >= 5:
            price_5d = float(closes.iloc[-5])
            ret_5d = (current - price_5d) / price_5d * 100
            sector_data[sector]["returns_5d"].append(ret_5d)

        # 20-day return
        if len(closes) >= 20:
            price_20d = float(closes.iloc[-20])
            ret_20d = (current - price_20d) / price_20d * 100
            sector_data[sector]["returns_20d"].append(ret_20d)

        # RSI
        rsi_series = calc_rsi(closes, 14)
        if not rsi_series.empty and not pd.isna(rsi_series.iloc[-1]):
            sector_data[sector]["rsis"].append(float(rsi_series.iloc[-1]))

        # BB position
        sma_20 = closes.rolling(20).mean()
        std_20 = closes.rolling(20).std()
        if not pd.isna(sma_20.iloc[-1]) and not pd.isna(std_20.iloc[-1]):
            upper = float(sma_20.iloc[-1] + 2 * std_20.iloc[-1])
            lower = float(sma_20.iloc[-1] - 2 * std_20.iloc[-1])
            width = upper - lower
            if width > 0:
                bb_pos = (current - lower) / width
                sector_data[sector]["bb_positions"].append(bb_pos)

    # Build results
    results = {}
    for sector in SECTORS:
        sd = sector_data[sector]
        mom_5d = np.mean(sd["returns_5d"]) if sd["returns_5d"] else 0
        mom_20d = np.mean(sd["returns_20d"]) if sd["returns_20d"] else 0
        avg_rsi = np.mean(sd["rsis"]) if sd["rsis"] else 50
        in_buy_zone = sum(1 for bp in sd["bb_positions"] if bp < 0.2)

        # Signal based on RSI + momentum
        if avg_rsi > 65 and mom_5d > 2:
            signal = "OVERBOUGHT"
        elif avg_rsi < 35 and mom_5d < -2:
            signal = "OVERSOLD"
        elif avg_rsi > 55:
            signal = "WARMING"
        elif avg_rsi < 45:
            signal = "COOLING"
        else:
            signal = "NEUTRAL"

        results[sector] = {
            "momentum_5d": round(mom_5d, 2),
            "momentum_20d": round(mom_20d, 2),
            "avg_rsi": round(avg_rsi, 1),
            "signal": signal,
            "stocks_in_buy_zone": in_buy_zone,
            "stock_count": len(sd["rsis"]),
        }

    # Rank sectors: lowest RSI = rank 1 (best to buy)
    ranked = sorted(results.items(), key=lambda x: x[1]["avg_rsi"])
    for rank, (sector, data) in enumerate(ranked, 1):
        data["rank"] = rank

    return results


def get_buy_priority(sector_momentum: dict) -> list[str]:
    """Return sectors ordered by buy priority (most oversold first)."""
    return [s for s, _ in sorted(
        sector_momentum.items(),
        key=lambda x: x[1]["avg_rsi"]
    )]


def get_sell_priority(sector_momentum: dict) -> list[str]:
    """Return sectors ordered by sell priority (most overbought first)."""
    return [s for s, _ in sorted(
        sector_momentum.items(),
        key=lambda x: -x[1]["avg_rsi"]
    )]


def get_stock_priority(symbols: list, sector_momentum: dict,
                       priority_type: str = "buy") -> list[str]:
    """Sort stocks by sector momentum priority.

    For buying: stocks in oversold sectors come first.
    For selling: stocks in overbought sectors come first.
    """
    if priority_type == "buy":
        sector_order = get_buy_priority(sector_momentum)
    else:
        sector_order = get_sell_priority(sector_momentum)

    sector_rank = {s: i for i, s in enumerate(sector_order)}

    return sorted(symbols, key=lambda sym: sector_rank.get(
        SECTOR_MAP.get(sym, "Unknown"), 99
    ))


def format_sector_dashboard(sector_momentum: dict) -> str:
    """Format sector momentum as a printable dashboard."""
    lines = [
        f"  {'Sector':<14} {'5d':>6} {'20d':>6} {'RSI':>5} {'Signal':<12} {'BuyZone':>8} {'Rank':>5}",
        f"  {'-' * 60}",
    ]
    for sector in sorted(sector_momentum, key=lambda s: sector_momentum[s]["rank"]):
        d = sector_momentum[sector]
        lines.append(
            f"  {sector:<14} {d['momentum_5d']:>+5.1f}% {d['momentum_20d']:>+5.1f}% "
            f"{d['avg_rsi']:>5.1f} {d['signal']:<12} {d['stocks_in_buy_zone']:>5}/{d['stock_count']:<2} "
            f"{'#' + str(d['rank']):>5}"
        )
    return "\n".join(lines)
