"""Wave Trader: Never Lose strategy -- buy dips, sell recoveries, never sell at a loss.

Buy: price dips X% from recent N-day high (per-stock calibrated)
Sell: price gains Y% above buy price (per-stock calibrated)
Never sell at a loss. 100% capital. Compound profits.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime

from trading.config import (
    DATA_DIR,
    WAVE_MAX_CONCURRENT_TRADES,
    WAVE_MAX_HOLD_DAYS,
    WAVE_MAX_POSITION_PCT,
    WAVE_ORDERS_FILE,
    WAVE_TRADES_FILE,
)
from trading.wave_config import (
    WAVE_STOCKS,
    get_lookback,
    get_params,
    get_sell_target,
    get_swap,
)
from trading.wave_sectors import compute_sector_momentum, get_sector, get_stock_priority

logger = logging.getLogger("wave")


class WaveState:
    SCANNING = "SCANNING"
    ACTIVE = "ACTIVE"
    SELL_PENDING = "SELL_PENDING"
    COMPLETED = "COMPLETED"


@dataclass
class WaveTrade:
    symbol: str
    state: str = WaveState.SCANNING
    # Entry
    buy_price: float = 0.0
    quantity: int = 0
    buy_time: str = ""
    # Params used
    dip_pct: float = 0.0
    sell_pct: float = 0.0
    lookback: int = 5
    # Exit
    sell_target: float = 0.0
    sell_price: float = 0.0
    sell_time: str = ""
    # Tracking
    intended_buy_price: float = 0.0
    intended_sell_price: float = 0.0
    # P&L
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    gain_pct: float = 0.0
    # Sector
    sector: str = ""
    # Metadata
    days_held: int = 0
    tier: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class WaveOrder:
    symbol: str
    action: str
    intended_price: float
    fill_price: float | None = None
    status: str = "PENDING"
    timestamp: str = ""
    market_session: str = "REGULAR"


class WaveTrader:
    """Manages wave trades using the Never Lose strategy.

    Each stock gets its own cash bucket that compounds independently.
    When a trade completes, profits stay in that stock's bucket for the next trade.
    """

    def __init__(self, initial_cash: float = 100_000, num_stocks: int = 6):
        self.trades: dict[str, WaveTrade] = {}
        self.completed: list[dict] = []
        self.orders: list[dict] = []
        self.sector_momentum: dict = {}
        # Per-stock cash buckets for independent compounding
        self.stock_cash: dict[str, float] = {}
        self._initial_per_stock = initial_cash / num_stocks
        self._load()

    def _load(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(WAVE_TRADES_FILE):
            try:
                with open(WAVE_TRADES_FILE, "r") as f:
                    data = json.load(f)
                for t in data.get("active", []):
                    self.trades[t["symbol"]] = WaveTrade(**t)
                self.completed = data.get("completed", [])
                self.stock_cash = data.get("stock_cash", {})
            except (json.JSONDecodeError, IOError):
                pass
        if os.path.exists(WAVE_ORDERS_FILE):
            try:
                with open(WAVE_ORDERS_FILE, "r") as f:
                    self.orders = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

    def save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(WAVE_TRADES_FILE, "w") as f:
            json.dump({
                "active": [asdict(t) for t in self.trades.values()],
                "completed": self.completed,
                "stock_cash": self.stock_cash,
            }, f, indent=2)
        with open(WAVE_ORDERS_FILE, "w") as f:
            json.dump(self.orders, f, indent=2)

    def get_stock_cash(self, symbol: str) -> float:
        """Get available cash for a stock's bucket."""
        if symbol not in self.stock_cash:
            self.stock_cash[symbol] = self._initial_per_stock
        return self.stock_cash[symbol]

    def scan_for_entries(self, symbols: list, historical: dict,
                        live_prices: dict, portfolio_value: float,
                        wash_blocked: set = None) -> list[WaveTrade]:
        """Scan for buy signals using per-stock calibrated params.

        Buy when: price dips X% from recent N-day high.
        Sector-aware: prioritize oversold sectors.
        Wash sale: skip blocked stocks, offer swap.
        """
        new_trades = []
        now = datetime.utcnow().isoformat()
        wash_blocked = wash_blocked or set()

        if len(self.trades) >= WAVE_MAX_CONCURRENT_TRADES:
            return []

        self.sector_momentum = compute_sector_momentum(historical)
        prioritized = get_stock_priority(symbols, self.sector_momentum, "buy")

        for sym in prioritized:
            if sym in self.trades:
                continue
            if sym not in WAVE_STOCKS:
                continue
            if len(self.trades) >= WAVE_MAX_CONCURRENT_TRADES:
                break

            # Wash sale check
            if sym in wash_blocked:
                swap = get_swap(sym)
                if swap and swap not in self.trades and swap not in wash_blocked:
                    logger.info("WAVE SWAP: %s blocked, trying %s", sym, swap)
                    sym = swap
                else:
                    continue

            price = live_prices.get(sym)
            if price is None:
                continue

            # Get per-stock params
            dip_pct, sell_pct, lookback = get_params(sym)

            # Check dip from recent high
            df = historical.get(sym)
            if df is None or len(df) < lookback:
                continue

            recent_high = float(df["High"].iloc[-lookback:].max())
            current_dip = (recent_high - price) / recent_high * 100

            if current_dip < dip_pct:
                continue

            # Position sizing: use this stock's cash bucket (100% of bucket)
            stock_cash = self.get_stock_cash(sym)
            qty = int(stock_cash // price)
            if qty <= 0:
                continue

            sell_target = get_sell_target(sym, price)
            cfg = WAVE_STOCKS[sym]

            trade = WaveTrade(
                symbol=sym,
                state=WaveState.ACTIVE,
                buy_price=price,
                quantity=qty,
                buy_time=now,
                dip_pct=dip_pct,
                sell_pct=sell_pct,
                lookback=lookback,
                sell_target=sell_target,
                intended_buy_price=price,
                intended_sell_price=sell_target,
                sector=get_sector(sym),
                tier=cfg.get("tier", ""),
                created_at=now,
                updated_at=now,
            )
            # Deduct from stock's cash bucket
            self.stock_cash[sym] = stock_cash - (qty * price)

            self.trades[sym] = trade
            new_trades.append(trade)

            self.orders.append(asdict(WaveOrder(
                symbol=sym, action="BUY",
                intended_price=price, fill_price=price,
                status="FILLED", timestamp=now,
            )))

            logger.info(
                "WAVE BUY: %d x %s @ $%.2f (dip=%.1f%%, target $%.2f +%.0f%%, lookback=%dd)",
                qty, sym, price, current_dip, sell_target, sell_pct, lookback,
            )

        return new_trades

    def check_exits(self, live_prices: dict, market_session: str) -> list[WaveTrade]:
        """Check active trades for sell signals. Only sell at profit (Never Lose)."""
        exits = []
        now = datetime.utcnow().isoformat()

        sorted_trades = sorted(
            self.trades.items(),
            key=lambda x: -self.sector_momentum.get(
                get_sector(x[0]), {}
            ).get("avg_rsi", 50) if self.sector_momentum else 0,
        )

        for sym, trade in sorted_trades:
            if trade.state != WaveState.ACTIVE:
                continue

            price = live_prices.get(sym)
            if price is None:
                continue

            trade.unrealized_pnl = round((price - trade.buy_price) * trade.quantity, 2)
            trade.gain_pct = round((price - trade.buy_price) / trade.buy_price * 100, 2)

            try:
                buy_dt = datetime.fromisoformat(trade.buy_time)
                trade.days_held = (datetime.utcnow() - buy_dt).days
            except (ValueError, TypeError):
                pass

            if trade.days_held > WAVE_MAX_HOLD_DAYS:
                logger.warning(
                    "WAVE HOLD WARNING: %s held %d days, unrealized %.2f%%",
                    sym, trade.days_held, trade.gain_pct,
                )

            # SELL: price >= sell target (Never Lose)
            if price >= trade.sell_target:
                trade.state = WaveState.SELL_PENDING
                trade.intended_sell_price = trade.sell_target
                trade.updated_at = now

                self.orders.append(asdict(WaveOrder(
                    symbol=sym, action="SELL",
                    intended_price=trade.sell_target,
                    status="PENDING", timestamp=now,
                    market_session=market_session,
                )))
                exits.append(trade)
                logger.info(
                    "WAVE SELL PENDING: %s @ $%.2f (bought $%.2f, +%.1f%%, %dd)",
                    sym, price, trade.buy_price, trade.gain_pct, trade.days_held,
                )

            trade.updated_at = now

        return exits

    def process_pending_sells(self, live_prices: dict) -> list[WaveTrade]:
        """Fill pending sells if price still at target."""
        filled = []
        now = datetime.utcnow().isoformat()

        for sym, trade in list(self.trades.items()):
            if trade.state != WaveState.SELL_PENDING:
                continue

            price = live_prices.get(sym)
            if price is None:
                continue

            if price >= trade.sell_target:
                trade.sell_price = price
                trade.sell_time = now
                trade.realized_pnl = round((price - trade.buy_price) * trade.quantity, 2)
                trade.gain_pct = round((price - trade.buy_price) / trade.buy_price * 100, 2)
                trade.state = WaveState.COMPLETED
                trade.updated_at = now

                for order in reversed(self.orders):
                    if order["symbol"] == sym and order["action"] == "SELL" and order["status"] == "PENDING":
                        order["fill_price"] = price
                        order["status"] = "FILLED"
                        break

                # Add proceeds back to stock's cash bucket (compounds for next trade)
                self.stock_cash[sym] = self.stock_cash.get(sym, 0) + price * trade.quantity

                self.completed.append(asdict(trade))
                del self.trades[sym]
                filled.append(trade)

                logger.info(
                    "WAVE SOLD: %s %d shares @ $%.2f, P&L $%.2f (+%.1f%%), held %dd, bucket $%.0f",
                    sym, trade.quantity, price, trade.realized_pnl,
                    trade.gain_pct, trade.days_held, self.stock_cash[sym],
                )

        return filled

    def expire_pending_sells(self):
        """End of day: revert unfilled sells back to ACTIVE."""
        now = datetime.utcnow().isoformat()
        for sym, trade in self.trades.items():
            if trade.state == WaveState.SELL_PENDING:
                trade.state = WaveState.ACTIVE
                trade.updated_at = now
                for order in reversed(self.orders):
                    if order["symbol"] == sym and order["action"] == "SELL" and order["status"] == "PENDING":
                        order["status"] = "EXPIRED"
                        break
                logger.info("WAVE SELL EXPIRED: %s back to ACTIVE", sym)

    def get_status_table(self, live_prices: dict) -> list[dict]:
        rows = []
        for sym in WAVE_STOCKS:
            price = live_prices.get(sym)
            trade = self.trades.get(sym)
            dip_pct, sell_pct, lookback = get_params(sym)
            rows.append({
                "symbol": sym,
                "price": price,
                "state": trade.state if trade else WaveState.SCANNING,
                "buy_price": trade.buy_price if trade else None,
                "sell_target": trade.sell_target if trade else None,
                "unrealized_pnl": trade.unrealized_pnl if trade else None,
                "gain_pct": trade.gain_pct if trade else None,
                "days_held": trade.days_held if trade else None,
                "tier": WAVE_STOCKS[sym].get("tier", ""),
                "dip_pct": dip_pct,
                "sell_pct": sell_pct,
            })
        return rows

    def get_performance(self) -> dict:
        if not self.completed:
            return {"total_trades": 0, "wins": 0, "losses": 0,
                    "win_rate": 0, "total_pnl": 0, "avg_gain_pct": 0}
        wins = sum(1 for t in self.completed if t["realized_pnl"] > 0)
        total_pnl = sum(t["realized_pnl"] for t in self.completed)
        gain_pcts = [t["gain_pct"] for t in self.completed]
        return {
            "total_trades": len(self.completed),
            "wins": wins,
            "losses": len(self.completed) - wins,
            "win_rate": round(wins / len(self.completed) * 100, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_gain_pct": round(sum(gain_pcts) / len(gain_pcts), 2),
            "avg_hold_days": round(
                sum(t["days_held"] for t in self.completed) / len(self.completed), 1
            ),
        }
