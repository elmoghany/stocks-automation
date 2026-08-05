"""Signal generator: combines value scores, trading windows, sector
allocations, and risk flags into actionable buy/sell decisions."""

import logging

from trading.config import (
    BUY_SCORE_THRESHOLD,
    STRONG_BUY_SCORE_THRESHOLD,
    SELL_SCORE_THRESHOLD,
    COLLAPSE_SCORE_THRESHOLD,
)
from trading.trading_window import (
    WindowResult,
    get_window_signal,
    STRONG_BUY,
    BUY,
    SELL,
    STRONG_SELL,
)
from trading.risk_manager import RiskFlags
from trading.value_scorer import passes_fundamental_gate
from trading.universe import ALL_SYMBOLS, SYMBOL_TO_SECTOR

logger = logging.getLogger("trading")

# Actions returned by the signal generator
ACTION_BUY = "BUY"
ACTION_STRONG_BUY = "STRONG_BUY"
ACTION_SELL = "SELL"
ACTION_HOLD = "HOLD"


class Signal:
    """A single trading signal."""
    __slots__ = ("symbol", "action", "reason", "priority", "value_score",
                 "window_signal", "sector")

    def __init__(self, symbol, action, reason, priority, value_score,
                 window_signal, sector):
        self.symbol = symbol
        self.action = action
        self.reason = reason
        self.priority = priority
        self.value_score = value_score
        self.window_signal = window_signal
        self.sector = sector

    def to_dict(self):
        return {s: getattr(self, s) for s in self.__slots__}


def generate_signal(
    symbol: str,
    value_score: float,
    window: WindowResult | None,
    sector_allocation: float,
    is_held: bool,
    risk_flags: RiskFlags,
) -> Signal:
    """Generate a single signal for one symbol.

    Decision rules:
        1. Fundamental gate: score < 40 = never buy
        2. Wash sale blocked = no buy
        3. Max positions reached = no buy
        4. BUY: value >= 60 AND window in buy zone
        5. STRONG_BUY: value >= 70 AND window in strong buy zone
        6. SELL: window in sell zone AND value < 50, OR fundamentals < 30
    """
    sector = SYMBOL_TO_SECTOR.get(symbol, "Unknown")
    w_signal = get_window_signal(window)

    # --- SELL signals (check first for held positions) ---
    if is_held:
        # Fundamentals collapsed -- sell regardless of window
        if value_score < COLLAPSE_SCORE_THRESHOLD:
            return Signal(
                symbol, ACTION_SELL,
                f"Fundamentals collapsed (score={value_score})",
                priority=90, value_score=value_score,
                window_signal=w_signal, sector=sector,
            )

        # Sell zone + weakening value
        if w_signal in (SELL, STRONG_SELL) and value_score < SELL_SCORE_THRESHOLD:
            return Signal(
                symbol, ACTION_SELL,
                f"Sell zone + weak value (score={value_score}, window={w_signal})",
                priority=80, value_score=value_score,
                window_signal=w_signal, sector=sector,
            )

        # Strong sell zone alone
        if w_signal == STRONG_SELL:
            return Signal(
                symbol, ACTION_SELL,
                f"Strong sell zone (window={w_signal}, score={value_score})",
                priority=70, value_score=value_score,
                window_signal=w_signal, sector=sector,
            )

    # --- BUY signals (only if not already held) ---
    if not is_held:
        # Gate checks
        if not passes_fundamental_gate(value_score):
            return Signal(
                symbol, ACTION_HOLD,
                f"Below fundamental gate (score={value_score})",
                priority=0, value_score=value_score,
                window_signal=w_signal, sector=sector,
            )
        if risk_flags.wash_sale_blocked:
            return Signal(
                symbol, ACTION_HOLD,
                "Wash sale blocked",
                priority=0, value_score=value_score,
                window_signal=w_signal, sector=sector,
            )
        if risk_flags.max_positions_reached:
            return Signal(
                symbol, ACTION_HOLD,
                "Max positions reached",
                priority=0, value_score=value_score,
                window_signal=w_signal, sector=sector,
            )

        # STRONG BUY
        if value_score >= STRONG_BUY_SCORE_THRESHOLD and w_signal == STRONG_BUY:
            return Signal(
                symbol, ACTION_STRONG_BUY,
                f"Strong buy: high value ({value_score}) + strong buy zone",
                priority=100, value_score=value_score,
                window_signal=w_signal, sector=sector,
            )

        # BUY
        if value_score >= BUY_SCORE_THRESHOLD and w_signal in (BUY, STRONG_BUY):
            return Signal(
                symbol, ACTION_BUY,
                f"Buy: good value ({value_score}) + buy zone ({w_signal})",
                priority=60 + value_score / 10,
                value_score=value_score,
                window_signal=w_signal, sector=sector,
            )

    # Default HOLD
    return Signal(
        symbol, ACTION_HOLD,
        f"Hold (score={value_score}, window={w_signal})",
        priority=0, value_score=value_score,
        window_signal=w_signal, sector=sector,
    )


def generate_all_signals(
    value_scores: dict,
    windows: dict,
    sector_allocations: dict,
    held_symbols: set,
    risk_flags_by_symbol: dict,
) -> list:
    """Generate signals for all symbols, sorted by priority (highest first).

    Returns list of Signal objects with action != HOLD.
    """
    signals = []
    for sym in ALL_SYMBOLS:
        score = value_scores.get(sym, 50.0)
        window = windows.get(sym)
        sector = SYMBOL_TO_SECTOR.get(sym, "Unknown")
        alloc = sector_allocations.get(sector, 0.33)
        is_held = sym in held_symbols
        flags = risk_flags_by_symbol.get(
            sym, RiskFlags(wash_sale_blocked=False, max_positions_reached=False)
        )

        signal = generate_signal(sym, score, window, alloc, is_held, flags)
        if signal.action != ACTION_HOLD:
            signals.append(signal)

    signals.sort(key=lambda s: s.priority, reverse=True)
    return signals
