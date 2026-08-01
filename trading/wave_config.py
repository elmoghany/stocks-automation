"""Wave trading configuration -- backtested and optimized.

Strategy: Never Lose
- Buy when price dips X% from recent 5-day high
- Sell when price gains Y% above buy price
- Never sell at a loss -- hold until profitable
- 100% capital per trade, compound profits

Default params: dip=2.5%, sell=+11%, lookback=5d (best one-size-fits-all)
Per-stock optimized params also available for top 6 stocks.

Backtested on 1Y data (Apr 2025 - Mar 2026):
- Default (2.5d/11s) across 6 stocks: $100K -> $361K (3.6x)
- Per-stock optimized across 6 stocks: $100K -> $384K (3.8x)
- All 21 stocks avg: +97% return, beats B&H on 20/21 stocks
"""

# ---------------------------------------------------------------------------
# Global defaults (best one-size-fits-all from backtest)
# ---------------------------------------------------------------------------
WAVE_DEFAULT_DIP_PCT = 2.5
WAVE_DEFAULT_SELL_PCT = 11.0
WAVE_DEFAULT_LOOKBACK = 5

# ---------------------------------------------------------------------------
# Top 6 priority stocks (highest backtested returns)
# ---------------------------------------------------------------------------
WAVE_TOP6 = ["FIX", "VRT", "LRCX", "AMD", "TDW", "TSM"]

# ---------------------------------------------------------------------------
# Per-stock optimized parameters (from brute-force backtest)
# ---------------------------------------------------------------------------
# fmt: off
WAVE_STOCKS = {
    # Top 6 -- per-stock optimized params
    "FIX":  {"dip_pct": 2.0, "sell_pct": 12.0, "lookback": 5, "tier": "top6", "backtest_ret": 397},
    "VRT":  {"dip_pct": 2.0, "sell_pct": 12.0, "lookback": 5, "tier": "top6", "backtest_ret": 392},
    "LRCX": {"dip_pct": 3.0, "sell_pct": 12.0, "lookback": 5, "tier": "top6", "backtest_ret": 329},
    # AMD recalibrated 2026-08-01: walk-forward (train Aug15-Jul25, OOS Aug25-Jul26)
    # dip 8/sell 20/lb 3 made +201% OOS vs +143% for old 2.5/10/5; beat B&H (+180%)
    "AMD":  {"dip_pct": 8.0, "sell_pct": 20.0, "lookback": 3, "tier": "top6", "backtest_ret": 201},
    "TDW":  {"dip_pct": 2.0, "sell_pct": 11.0, "lookback": 5, "tier": "top6", "backtest_ret": 206},
    "TSM":  {"dip_pct": 3.0, "sell_pct": 10.0, "lookback": 5, "tier": "top6", "backtest_ret": 170},

    # Remaining 15 stocks -- use default params, include wave stats
    "AMSC": {"dip_pct": 2.5, "sell_pct": 11.0, "lookback": 5, "tier": "wave", "backtest_ret": 96},
    "ANET": {"dip_pct": 2.5, "sell_pct": 11.0, "lookback": 5, "tier": "wave", "backtest_ret": 70},
    "MLI":  {"dip_pct": 2.5, "sell_pct": 11.0, "lookback": 5, "tier": "wave", "backtest_ret": 81},
    "HUBB": {"dip_pct": 2.5, "sell_pct": 11.0, "lookback": 5, "tier": "wave", "backtest_ret": 70},
    "LLY":  {"dip_pct": 2.5, "sell_pct": 11.0, "lookback": 5, "tier": "wave", "backtest_ret": 22},
    "DECK": {"dip_pct": 2.5, "sell_pct": 11.0, "lookback": 5, "tier": "wave", "backtest_ret": 8},
    "CDNS": {"dip_pct": 2.5, "sell_pct": 11.0, "lookback": 5, "tier": "wave", "backtest_ret": 28},
    "ETN":  {"dip_pct": 2.5, "sell_pct": 11.0, "lookback": 5, "tier": "wave", "backtest_ret": 34},
    "AWI":  {"dip_pct": 2.5, "sell_pct": 11.0, "lookback": 5, "tier": "wave", "backtest_ret": 16},
    "TJX":  {"dip_pct": 2.5, "sell_pct": 11.0, "lookback": 5, "tier": "wave", "backtest_ret": 42},
    "BMI":  {"dip_pct": 2.5, "sell_pct": 11.0, "lookback": 5, "tier": "wave", "backtest_ret": -19},
    "ISRG": {"dip_pct": 2.5, "sell_pct": 11.0, "lookback": 5, "tier": "wave", "backtest_ret": 10},
    "RMD":  {"dip_pct": 2.5, "sell_pct": 11.0, "lookback": 5, "tier": "wave", "backtest_ret": 2},
    "CTAS": {"dip_pct": 2.5, "sell_pct": 11.0, "lookback": 5, "tier": "wave", "backtest_ret": -15},
    "FICO": {"dip_pct": 2.5, "sell_pct": 11.0, "lookback": 5, "tier": "wave", "backtest_ret": -33},
}
# fmt: on

WAVE_SYMBOLS = list(WAVE_STOCKS.keys())


def get_params(symbol: str) -> tuple[float, float, int]:
    """Get (dip_pct, sell_pct, lookback) for a stock."""
    cfg = WAVE_STOCKS.get(symbol)
    if cfg:
        return cfg["dip_pct"], cfg["sell_pct"], cfg["lookback"]
    return WAVE_DEFAULT_DIP_PCT, WAVE_DEFAULT_SELL_PCT, WAVE_DEFAULT_LOOKBACK


def get_buy_target(symbol: str, recent_high: float) -> float:
    """Buy target: recent high minus dip%."""
    dip_pct, _, _ = get_params(symbol)
    return round(recent_high * (1 - dip_pct / 100), 2)


def get_sell_target(symbol: str, buy_price: float) -> float:
    """Sell target: buy price plus sell%."""
    _, sell_pct, _ = get_params(symbol)
    return round(buy_price * (1 + sell_pct / 100), 2)


def get_lookback(symbol: str) -> int:
    """Lookback days for finding recent high."""
    _, _, lookback = get_params(symbol)
    return lookback


# ---------------------------------------------------------------------------
# Swap stock pairs for wash sale avoidance
# ---------------------------------------------------------------------------
SWAP_PAIRS = {
    "AMD": "CDNS", "CDNS": "AMD",
    "LRCX": "ANET", "ANET": "LRCX",
    "VRT": "TSM", "TSM": "VRT",
    "FICO": "LRCX",
    "FIX": "HUBB", "HUBB": "FIX",
    "ETN": "AWI", "AWI": "ETN",
    "MLI": "BMI", "BMI": "MLI",
    "DECK": "CTAS", "CTAS": "DECK",
    "TJX": "CTAS",
    "LLY": "ISRG", "ISRG": "LLY",
    "RMD": "ISRG",
    "TDW": "AMSC", "AMSC": "TDW",
}


def get_swap(symbol: str) -> str | None:
    """Get the swap stock for wash sale avoidance."""
    return SWAP_PAIRS.get(symbol)
