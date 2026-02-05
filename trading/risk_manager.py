"""Risk management: wash-sale tracking and T+1 settlement."""

import json
import logging
import os
from datetime import datetime, timedelta

from trading.config import (
    DATA_DIR,
    WASH_SALE_FILE,
    WASH_SALE_LOSS_THRESHOLD,
    WASH_SALE_BLOCK_DAYS,
    MAX_POSITIONS,
)

logger = logging.getLogger("trading")


class WashSaleTracker:
    """Track symbols blocked from repurchase due to wash-sale rule.

    If a stock is sold at a loss >= WASH_SALE_LOSS_THRESHOLD, the symbol
    is blocked for WASH_SALE_BLOCK_DAYS.
    """

    def __init__(self):
        self.blocked: dict = {}  # {symbol: expiry_iso_string}
        self._load()

    def _load(self):
        if os.path.exists(WASH_SALE_FILE):
            try:
                with open(WASH_SALE_FILE, "r") as f:
                    self.blocked = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.blocked = {}

    def _save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(WASH_SALE_FILE, "w") as f:
            json.dump(self.blocked, f, indent=2)

    def record_sale(self, symbol: str, loss: float) -> None:
        """Record a sale. If loss >= threshold, block the symbol."""
        if loss >= WASH_SALE_LOSS_THRESHOLD:
            expiry = datetime.utcnow() + timedelta(days=WASH_SALE_BLOCK_DAYS)
            self.blocked[symbol] = expiry.isoformat()
            logger.info(
                "Wash sale block: %s blocked until %s (loss=$%.2f)",
                symbol, expiry.date(), loss,
            )
            self._save()

    def is_blocked(self, symbol: str) -> bool:
        """Check if a symbol is currently blocked."""
        self._purge_expired()
        return symbol in self.blocked

    def _purge_expired(self):
        now = datetime.utcnow()
        expired = [
            s for s, exp in self.blocked.items()
            if datetime.fromisoformat(exp) <= now
        ]
        for s in expired:
            del self.blocked[s]
        if expired:
            self._save()

    def get_blocked_symbols(self) -> list:
        self._purge_expired()
        return list(self.blocked.keys())


class SettlementTracker:
    """Track T+1 settlement: cash from sales isn't available until next day."""

    def __init__(self):
        # {date_iso: amount_pending}
        self.pending: dict = {}

    def record_sale_proceeds(self, amount: float) -> None:
        """Record proceeds from a sale, available next business day."""
        settle_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        self.pending[settle_date] = self.pending.get(settle_date, 0.0) + amount
        logger.info("Settlement pending: $%.2f available on %s", amount, settle_date)

    def get_unavailable_cash(self) -> float:
        """Return total cash that is pending settlement (not yet available)."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        total = 0.0
        expired = []
        for date_str, amount in self.pending.items():
            if date_str > today:
                total += amount
            else:
                expired.append(date_str)
        # Clean up settled entries
        for d in expired:
            del self.pending[d]
        return total


class RiskFlags:
    """Container for risk check results."""
    __slots__ = ("wash_sale_blocked", "max_positions_reached")

    def __init__(self, wash_sale_blocked: bool, max_positions_reached: bool):
        self.wash_sale_blocked = wash_sale_blocked
        self.max_positions_reached = max_positions_reached


def get_risk_flags(
    symbol: str,
    num_positions: int,
    wash_tracker: WashSaleTracker,
) -> RiskFlags:
    """Evaluate risk constraints for a potential buy."""
    return RiskFlags(
        wash_sale_blocked=wash_tracker.is_blocked(symbol),
        max_positions_reached=num_positions >= MAX_POSITIONS,
    )
