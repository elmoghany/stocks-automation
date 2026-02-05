"""Data pipeline: yfinance historical/fundamentals + E*TRADE live quotes."""

import logging

import pandas as pd
import yfinance as yf

from trading.config import HISTORICAL_PERIOD, QUOTE_BATCH_SIZE

logger = logging.getLogger("trading")


# ---------------------------------------------------------------------------
# yfinance: historical prices
# ---------------------------------------------------------------------------
def fetch_historical(symbol: str, period: str = HISTORICAL_PERIOD) -> pd.DataFrame:
    """Download 1-year daily OHLCV from yfinance. Returns DataFrame or empty."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)
        if df.empty:
            logger.warning("No historical data for %s", symbol)
        return df
    except Exception:
        logger.exception("fetch_historical failed for %s", symbol)
        return pd.DataFrame()


def fetch_all_historical(symbols: list) -> dict:
    """Fetch historical data for all symbols. Returns {symbol: DataFrame}."""
    result = {}
    for sym in symbols:
        result[sym] = fetch_historical(sym)
    return result


# ---------------------------------------------------------------------------
# yfinance: fundamentals
# ---------------------------------------------------------------------------
def fetch_fundamentals_yf(symbol: str) -> dict:
    """Pull fundamental metrics from yfinance for a single symbol.

    Returns dict with keys: pe, eps_growth, revenue_growth, profit_margin,
    debt_equity, analyst_target, price_to_book, current_price.
    Missing values are None.
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return {
            "symbol": symbol,
            "pe": info.get("trailingPE") or info.get("forwardPE"),
            "forward_pe": info.get("forwardPE"),
            "eps_growth": info.get("earningsGrowth"),
            "revenue_growth": info.get("revenueGrowth"),
            "profit_margin": info.get("profitMargins"),
            "debt_equity": info.get("debtToEquity"),
            "analyst_target": info.get("targetMeanPrice"),
            "price_to_book": info.get("priceToBook"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
        }
    except Exception:
        logger.exception("fetch_fundamentals_yf failed for %s", symbol)
        return {"symbol": symbol}


def fetch_all_fundamentals(symbols: list) -> dict:
    """Fetch fundamentals for all symbols. Returns {symbol: fundamentals_dict}."""
    result = {}
    for sym in symbols:
        result[sym] = fetch_fundamentals_yf(sym)
    return result


# ---------------------------------------------------------------------------
# E*TRADE live quotes
# ---------------------------------------------------------------------------
def parse_etrade_quote(quote_data: dict) -> dict:
    """Extract useful fields from a single E*TRADE QuoteData response."""
    all_data = quote_data.get("All", {})
    product = quote_data.get("Product", {})
    return {
        "symbol": product.get("symbol"),
        "last_price": all_data.get("lastTrade"),
        "bid": all_data.get("bid"),
        "ask": all_data.get("ask"),
        "bid_size": all_data.get("bidSize"),
        "ask_size": all_data.get("askSize"),
        "volume": all_data.get("totalVolume"),
        "high": all_data.get("high"),
        "low": all_data.get("low"),
        "open": all_data.get("open"),
        "previous_close": all_data.get("previousClose"),
        "change_close": all_data.get("changeClose"),
        "change_pct": all_data.get("changeClosePercentage"),
        "pe": all_data.get("pe"),
        "eps": all_data.get("eps"),
        "beta": all_data.get("beta"),
        "market_cap": all_data.get("marketCap"),
        "high52": all_data.get("week52HiPrice"),
        "low52": all_data.get("week52LowPrice"),
    }


def fetch_live_quotes(etrade_session, symbols: list) -> dict:
    """Fetch live quotes via E*TRADE API, batched.

    Args:
        etrade_session: authenticated ETradeSession instance
        symbols: list of ticker symbols

    Returns:
        dict keyed by symbol with parsed quote data
    """
    raw = etrade_session.get_quotes(symbols)
    result = {}
    for sym, qd in raw.items():
        result[sym] = parse_etrade_quote(qd)
    return result


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------
def merge_fundamentals(yf_data: dict, etrade_data: dict) -> dict:
    """Combine yfinance fundamentals with E*TRADE live quotes.

    yf_data and etrade_data are both keyed by symbol.
    E*TRADE live price takes precedence over yfinance current_price.
    """
    merged = {}
    all_symbols = set(list(yf_data.keys()) + list(etrade_data.keys()))
    for sym in all_symbols:
        yf_info = yf_data.get(sym, {})
        et_info = etrade_data.get(sym, {})
        entry = dict(yf_info)
        # Override price with live E*TRADE data
        if et_info.get("last_price") is not None:
            entry["current_price"] = et_info["last_price"]
        entry["bid"] = et_info.get("bid")
        entry["ask"] = et_info.get("ask")
        entry["volume"] = et_info.get("volume")
        entry["high52"] = et_info.get("high52") or entry.get("high52")
        entry["low52"] = et_info.get("low52") or entry.get("low52")
        merged[sym] = entry
    return merged
