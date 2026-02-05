"""Order execution: SIM (JSON log) and REAL (E*TRADE API) modes."""

import json
import logging
import os
from datetime import datetime

from trading.config import (
    DATA_DIR,
    TRADES_FILE,
    MAX_POSITION_PCT,
)
from trading.universe import SYMBOL_TO_SECTOR

logger = logging.getLogger("trading")


def compute_position_size(
    symbol: str,
    price: float,
    portfolio_value: float,
    sector_allocation: float,
    num_sector_stocks: int,
) -> int:
    """Determine how many shares to buy.

    Budget = portfolio_value * sector_allocation / num_sector_stocks
    Capped at MAX_POSITION_PCT of portfolio.
    Returns integer quantity (0 if price too high).
    """
    if price <= 0 or portfolio_value <= 0:
        return 0

    sector_budget = portfolio_value * sector_allocation
    per_stock_budget = sector_budget / max(num_sector_stocks, 1)

    # Cap at 5% of portfolio
    max_budget = portfolio_value * MAX_POSITION_PCT
    budget = min(per_stock_budget, max_budget)

    qty = int(budget // price)
    return max(qty, 0)


class SimExecutor:
    """Paper trading executor -- logs trades to JSON."""

    def __init__(self):
        self.trades: list = []
        self._load()

    def _load(self):
        if os.path.exists(TRADES_FILE):
            try:
                with open(TRADES_FILE, "r") as f:
                    self.trades = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.trades = []

    def _save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(TRADES_FILE, "w") as f:
            json.dump(self.trades, f, indent=2)

    def execute_buy(
        self, symbol: str, quantity: int, price: float, reason: str
    ) -> dict:
        """Log a simulated buy."""
        trade = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": "BUY",
            "symbol": symbol,
            "quantity": quantity,
            "price": round(price, 2),
            "total": round(quantity * price, 2),
            "reason": reason,
            "sector": SYMBOL_TO_SECTOR.get(symbol, "Unknown"),
        }
        self.trades.append(trade)
        self._save()
        logger.info("SIM BUY: %d x %s @ $%.2f (%s)", quantity, symbol, price, reason)
        return trade

    def execute_sell(
        self, symbol: str, quantity: int, price: float, reason: str
    ) -> dict:
        """Log a simulated sell."""
        trade = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": "SELL",
            "symbol": symbol,
            "quantity": quantity,
            "price": round(price, 2),
            "total": round(quantity * price, 2),
            "reason": reason,
            "sector": SYMBOL_TO_SECTOR.get(symbol, "Unknown"),
        }
        self.trades.append(trade)
        self._save()
        logger.info("SIM SELL: %d x %s @ $%.2f (%s)", quantity, symbol, price, reason)
        return trade


class RealExecutor:
    """Live trading executor -- preview then place via E*TRADE API.

    LIMIT orders only.
    """

    def __init__(self, etrade_session, account: dict):
        self.session = etrade_session
        self.account = account

    def execute_buy(
        self, symbol: str, quantity: int, price: float, reason: str
    ) -> dict:
        """Preview + place a LIMIT BUY order."""
        return self._execute("BUY", symbol, quantity, price, reason)

    def execute_sell(
        self, symbol: str, quantity: int, price: float, reason: str
    ) -> dict:
        """Preview + place a LIMIT SELL order."""
        return self._execute("SELL", symbol, quantity, price, reason)

    def _execute(
        self, action: str, symbol: str, quantity: int, price: float, reason: str
    ) -> dict:
        logger.info(
            "REAL %s: previewing %d x %s @ $%.2f (%s)",
            action, quantity, symbol, price, reason,
        )

        # Step 1: Preview
        preview = self.session.preview_order(
            account=self.account,
            symbol=symbol,
            action=action,
            quantity=quantity,
            limit_price=round(price, 2),
        )
        if not preview:
            logger.error("Preview failed for %s %s", action, symbol)
            return {"error": "preview_failed"}

        preview_ids = preview.get("PreviewIds", [])
        if not preview_ids:
            logger.error("No preview IDs for %s %s", action, symbol)
            return {"error": "no_preview_ids"}

        logger.info(
            "Preview OK for %s %s: previewId=%s",
            action, symbol, preview_ids[0].get("previewId"),
        )

        # Step 2: Place
        result = self.session.place_order(
            account=self.account,
            preview_response=preview,
            symbol=symbol,
            action=action,
            quantity=quantity,
            limit_price=round(price, 2),
        )
        if not result:
            logger.error("Place order failed for %s %s", action, symbol)
            return {"error": "place_failed"}

        order_id = result.get("OrderIds", [{}])
        logger.info("REAL %s placed: %s %s, orderId=%s", action, symbol, reason, order_id)
        return {
            "action": action,
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "reason": reason,
            "order_response": result,
        }
