"""Fundamental value scoring: produces a 0-100 score per stock."""

import logging

from trading.config import (
    SCORE_WEIGHT_PE,
    SCORE_WEIGHT_EPS_GROWTH,
    SCORE_WEIGHT_REVENUE_GROWTH,
    SCORE_WEIGHT_PROFIT_MARGIN,
    SCORE_WEIGHT_DEBT_EQUITY,
    SCORE_WEIGHT_FAIR_VALUE_GAP,
    FUNDAMENTAL_GATE_THRESHOLD,
)

logger = logging.getLogger("trading")

NEUTRAL = 50.0  # default when data is missing


def _score_pe(pe) -> float:
    """Lower PE is better. Bracket scoring 0-100."""
    if pe is None or pe <= 0:
        return NEUTRAL
    if pe < 10:
        return 100
    if pe < 15:
        return 85
    if pe < 20:
        return 70
    if pe < 25:
        return 55
    if pe < 30:
        return 40
    if pe < 40:
        return 25
    return 10


def _score_eps_growth(growth) -> float:
    """Higher EPS growth is better. yfinance returns as decimal (0.15 = 15%)."""
    if growth is None:
        return NEUTRAL
    pct = growth * 100  # convert to percentage
    if pct > 30:
        return 100
    if pct > 20:
        return 85
    if pct > 10:
        return 70
    if pct > 5:
        return 60
    if pct > 0:
        return 45
    if pct > -10:
        return 30
    return 10


def _score_revenue_growth(growth) -> float:
    """Higher revenue growth is better. Decimal input."""
    if growth is None:
        return NEUTRAL
    pct = growth * 100
    if pct > 25:
        return 100
    if pct > 15:
        return 85
    if pct > 10:
        return 70
    if pct > 5:
        return 55
    if pct > 0:
        return 40
    if pct > -5:
        return 25
    return 10


def _score_profit_margin(margin) -> float:
    """Higher margin is better. Decimal input."""
    if margin is None:
        return NEUTRAL
    pct = margin * 100
    if pct > 30:
        return 100
    if pct > 20:
        return 85
    if pct > 15:
        return 70
    if pct > 10:
        return 55
    if pct > 5:
        return 40
    if pct > 0:
        return 25
    return 10


def _score_debt_equity(de) -> float:
    """Lower debt/equity is better. yfinance returns as percentage (e.g. 50 = 50%)."""
    if de is None:
        return NEUTRAL
    if de < 20:
        return 100
    if de < 50:
        return 85
    if de < 80:
        return 70
    if de < 120:
        return 55
    if de < 180:
        return 40
    if de < 250:
        return 25
    return 10


def _score_fair_value_gap(current_price, analyst_target) -> float:
    """How far below analyst target. Bigger gap = more upside = higher score."""
    if current_price is None or analyst_target is None or analyst_target <= 0:
        return NEUTRAL
    gap_pct = (analyst_target - current_price) / analyst_target * 100
    if gap_pct > 30:
        return 100
    if gap_pct > 20:
        return 85
    if gap_pct > 10:
        return 70
    if gap_pct > 5:
        return 55
    if gap_pct > 0:
        return 40
    if gap_pct > -10:
        return 25
    return 10


def compute_value_score(fundamentals: dict) -> float:
    """Compute a 0-100 value score from fundamental data.

    Args:
        fundamentals: dict with keys pe, eps_growth, revenue_growth,
            profit_margin, debt_equity, analyst_target, current_price

    Returns:
        float 0-100
    """
    pe_score = _score_pe(fundamentals.get("pe"))
    eps_score = _score_eps_growth(fundamentals.get("eps_growth"))
    rev_score = _score_revenue_growth(fundamentals.get("revenue_growth"))
    margin_score = _score_profit_margin(fundamentals.get("profit_margin"))
    de_score = _score_debt_equity(fundamentals.get("debt_equity"))
    fv_score = _score_fair_value_gap(
        fundamentals.get("current_price"),
        fundamentals.get("analyst_target"),
    )

    weighted = (
        SCORE_WEIGHT_PE * pe_score
        + SCORE_WEIGHT_EPS_GROWTH * eps_score
        + SCORE_WEIGHT_REVENUE_GROWTH * rev_score
        + SCORE_WEIGHT_PROFIT_MARGIN * margin_score
        + SCORE_WEIGHT_DEBT_EQUITY * de_score
        + SCORE_WEIGHT_FAIR_VALUE_GAP * fv_score
    )

    return round(min(100.0, max(0.0, weighted)), 2)


def passes_fundamental_gate(score: float) -> bool:
    """Must meet minimum score to be eligible for purchase."""
    return score >= FUNDAMENTAL_GATE_THRESHOLD


def score_all(fundamentals_by_symbol: dict) -> dict:
    """Score every symbol. Returns {symbol: score}."""
    scores = {}
    for sym, data in fundamentals_by_symbol.items():
        scores[sym] = compute_value_score(data)
    return scores
