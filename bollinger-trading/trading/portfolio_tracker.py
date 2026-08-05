"""Portfolio state tracker with JSON persistence."""

import json
import logging
import os

from trading.config import DATA_DIR, PORTFOLIO_STATE_FILE

logger = logging.getLogger("trading")


class PortfolioTracker:
    """Track holdings, cash, and total value across cycles.

    In REAL mode, syncs from E*TRADE API.
    In SIM mode, builds state from the trade log.
    """

    def __init__(self):
        self.holdings: dict = {}  # {symbol: {"qty": int, "avg_cost": float}}
        self.cash: float = 0.0
        self.total_value: float = 0.0
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self):
        if os.path.exists(PORTFOLIO_STATE_FILE):
            try:
                with open(PORTFOLIO_STATE_FILE, "r") as f:
                    state = json.load(f)
                self.holdings = state.get("holdings", {})
                self.cash = state.get("cash", 0.0)
                self.total_value = state.get("total_value", 0.0)
            except (json.JSONDecodeError, IOError):
                logger.warning("Could not load portfolio state, starting fresh")

    def save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        state = {
            "holdings": self.holdings,
            "cash": self.cash,
            "total_value": self.total_value,
        }
        with open(PORTFOLIO_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    # ------------------------------------------------------------------
    # Sync from E*TRADE API (REAL mode)
    # ------------------------------------------------------------------
    def sync_from_api(self, etrade_session, account: dict) -> None:
        """Pull real positions and balance from E*TRADE."""
        # Balance
        balance = etrade_session.get_balance(account)
        computed = balance.get("Computed", {})
        rtv = computed.get("RealTimeValues", {})
        self.cash = computed.get("cashBuyingPower", 0.0)
        self.total_value = rtv.get("totalAccountValue", 0.0)

        # Positions
        positions = etrade_session.get_portfolio(account)
        self.holdings = {}
        for pos in positions:
            product = pos.get("Product", {})
            sym = product.get("symbol") if product else pos.get("symbolDescription", "")
            if not sym:
                continue
            self.holdings[sym] = {
                "qty": pos.get("quantity", 0),
                "avg_cost": pos.get("pricePaid", 0.0),
                "market_value": pos.get("marketValue", 0.0),
                "total_gain": pos.get("totalGain", 0.0),
            }

        self.save()
        logger.info(
            "Portfolio synced from API: %d positions, cash=$%.2f, total=$%.2f",
            len(self.holdings), self.cash, self.total_value,
        )

    # ------------------------------------------------------------------
    # Sync from trade log (SIM mode)
    # ------------------------------------------------------------------
    def sync_from_sim(self, trades_file: str, initial_cash: float = 100_000.0) -> None:
        """Rebuild portfolio state from the JSON trade log."""
        self.holdings = {}
        self.cash = initial_cash

        if not os.path.exists(trades_file):
            self.total_value = self.cash
            self.save()
            return

        try:
            with open(trades_file, "r") as f:
                trades = json.load(f)
        except (json.JSONDecodeError, IOError):
            trades = []

        for trade in trades:
            sym = trade["symbol"]
            qty = trade["quantity"]
            price = trade["price"]
            action = trade["action"]

            if action == "BUY":
                cost = qty * price
                self.cash -= cost
                if sym in self.holdings:
                    old = self.holdings[sym]
                    total_qty = old["qty"] + qty
                    total_cost = old["avg_cost"] * old["qty"] + cost
                    self.holdings[sym] = {
                        "qty": total_qty,
                        "avg_cost": total_cost / total_qty if total_qty else 0,
                    }
                else:
                    self.holdings[sym] = {"qty": qty, "avg_cost": price}

            elif action == "SELL":
                proceeds = qty * price
                self.cash += proceeds
                if sym in self.holdings:
                    self.holdings[sym]["qty"] -= qty
                    if self.holdings[sym]["qty"] <= 0:
                        del self.holdings[sym]

        # Total value = cash + sum of holdings at avg cost (approximate)
        holdings_value = sum(
            h["qty"] * h["avg_cost"] for h in self.holdings.values()
        )
        self.total_value = self.cash + holdings_value
        self.save()
        logger.info(
            "Portfolio synced from sim: %d positions, cash=$%.2f, total=$%.2f",
            len(self.holdings), self.cash, self.total_value,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def update_market_values(self, live_prices: dict) -> None:
        """Update total_value using current market prices."""
        holdings_value = 0.0
        for sym, holding in self.holdings.items():
            price = live_prices.get(sym)
            if price is not None:
                holdings_value += holding["qty"] * price
            else:
                holdings_value += holding["qty"] * holding.get("avg_cost", 0)
        self.total_value = self.cash + holdings_value

    def get_held_symbols(self) -> set:
        return set(self.holdings.keys())

    def num_positions(self) -> int:
        return len(self.holdings)

    def get_position(self, symbol: str) -> dict | None:
        return self.holdings.get(symbol)
