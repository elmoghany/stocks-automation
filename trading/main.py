"""Entry point: 10-minute polling loop for the value trading system."""

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

import pytz

from trading.config import (
    DATA_DIR,
    POLL_INTERVAL_SECONDS,
    TOKEN_RENEW_MINUTES,
    MARKET_OPEN_HOUR,
    MARKET_OPEN_MINUTE,
    MARKET_CLOSE_HOUR,
    MARKET_CLOSE_MINUTE,
    TRADES_FILE,
    WASH_SALE_LOSS_THRESHOLD,
)
from trading.universe import ALL_SYMBOLS, SECTORS, SYMBOL_TO_SECTOR
from trading.api_wrapper import ETradeSession
from trading.data_pipeline import (
    fetch_all_historical,
    fetch_all_fundamentals,
    fetch_live_quotes,
    merge_fundamentals,
)
from trading.value_scorer import score_all
from trading.trading_window import compute_all_windows
from trading.sector_rotation import (
    compute_sector_performance,
    compute_sector_allocations,
)
from trading.signal_generator import (
    generate_all_signals,
    ACTION_BUY,
    ACTION_STRONG_BUY,
    ACTION_SELL,
)
from trading.order_executor import SimExecutor, RealExecutor, compute_position_size
from trading.risk_manager import WashSaleTracker, SettlementTracker, get_risk_flags
from trading.portfolio_tracker import PortfolioTracker

ET = pytz.timezone("US/Eastern")

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
def setup_logging():
    logger = logging.getLogger("trading")
    logger.setLevel(logging.DEBUG)

    os.makedirs(DATA_DIR, exist_ok=True)
    fh = RotatingFileHandler(
        os.path.join(DATA_DIR, "trading.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
    )
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# ---------------------------------------------------------------------------
# Market hours check
# ---------------------------------------------------------------------------
def is_market_open() -> bool:
    """Return True if current time is within regular market hours (ET)."""
    now = datetime.now(ET)
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    market_open = now.replace(
        hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0, microsecond=0
    )
    market_close = now.replace(
        hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0, microsecond=0
    )
    return market_open <= now <= market_close


# ---------------------------------------------------------------------------
# Account selection
# ---------------------------------------------------------------------------
def select_account(etrade: ETradeSession) -> dict:
    """Let user pick an account from their E*TRADE account list."""
    accounts = etrade.get_account_list()
    if not accounts:
        print("No accounts found. Exiting.")
        sys.exit(1)

    print("\nAvailable accounts:")
    for i, acct in enumerate(accounts, 1):
        desc = acct.get("accountDesc", "").strip()
        inst = acct.get("institutionType", "")
        print(f"  {i}) {acct.get('accountId', '?')} - {desc} ({inst})")

    while True:
        choice = input("Select account number: ")
        if choice.isdigit() and 1 <= int(choice) <= len(accounts):
            return accounts[int(choice) - 1]
        print("Invalid selection, try again.")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def run(mode: str, sandbox: bool):
    logger = setup_logging()
    logger.info("Starting trading system: mode=%s, sandbox=%s", mode, sandbox)

    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # --- Authenticate ---
    etrade = ETradeSession(sandbox=sandbox)
    etrade.authenticate()
    account = select_account(etrade)
    logger.info("Using account: %s", account.get("accountId"))

    last_renew = time.time()

    # --- Initialize components ---
    wash_tracker = WashSaleTracker()
    settlement = SettlementTracker()
    portfolio = PortfolioTracker()

    if mode == "SIM":
        executor = SimExecutor()
        portfolio.sync_from_sim(TRADES_FILE)
    else:
        executor = RealExecutor(etrade, account)
        portfolio.sync_from_api(etrade, account)

    # --- Fetch historical data once at startup ---
    logger.info("Fetching historical data for %d symbols...", len(ALL_SYMBOLS))
    historical = fetch_all_historical(ALL_SYMBOLS)
    logger.info("Historical data loaded.")

    # --- Fetch yfinance fundamentals once at startup ---
    logger.info("Fetching yfinance fundamentals...")
    yf_fundamentals = fetch_all_fundamentals(ALL_SYMBOLS)
    logger.info("Fundamentals loaded.")

    # --- Graceful shutdown ---
    running = True

    def shutdown(signum, frame):
        nonlocal running
        logger.info("Shutdown signal received, finishing current cycle...")
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # --- Polling loop ---
    cycle = 0
    while running:
        cycle += 1
        now_et = datetime.now(ET)
        logger.info("=== Cycle %d at %s ET ===", cycle, now_et.strftime("%H:%M:%S"))

        # 1. Token renewal
        elapsed_min = (time.time() - last_renew) / 60
        if elapsed_min >= TOKEN_RENEW_MINUTES:
            if etrade.renew_token():
                last_renew = time.time()
            else:
                logger.warning("Token renewal failed, may need re-auth at midnight")

        # 2. Market hours check
        if not is_market_open():
            logger.info("Market closed. Sleeping until next cycle.")
            _sleep(POLL_INTERVAL_SECONDS, lambda: running)
            continue

        try:
            # 3. Fetch live quotes
            logger.info("Fetching live quotes...")
            etrade_quotes = fetch_live_quotes(etrade, ALL_SYMBOLS)
            live_prices = {
                sym: q.get("last_price")
                for sym, q in etrade_quotes.items()
                if q.get("last_price") is not None
            }

            # 4. Merge fundamentals with live data
            fundamentals = merge_fundamentals(yf_fundamentals, etrade_quotes)

            # 5. Score all stocks
            value_scores = score_all(fundamentals)
            logger.info(
                "Value scores: top 5 = %s",
                sorted(value_scores.items(), key=lambda x: x[1], reverse=True)[:5],
            )

            # 6. Compute trading windows
            windows = compute_all_windows(ALL_SYMBOLS, historical, live_prices)

            # 7. Compute sector allocations
            perf = compute_sector_performance(historical)
            allocations = compute_sector_allocations(perf)
            logger.info("Sector allocations: %s", allocations)

            # 8. Update portfolio with live prices
            portfolio.update_market_values(live_prices)

            # 9. Build risk flags
            held = portfolio.get_held_symbols()
            risk_flags = {}
            for sym in ALL_SYMBOLS:
                risk_flags[sym] = get_risk_flags(
                    sym, portfolio.num_positions(), wash_tracker
                )

            # 10. Generate signals
            signals = generate_all_signals(
                value_scores, windows, allocations, held, risk_flags
            )
            logger.info("Signals generated: %d actionable", len(signals))
            for sig in signals[:10]:
                logger.info(
                    "  %s %s: %s (priority=%.1f)",
                    sig.action, sig.symbol, sig.reason, sig.priority,
                )

            # 11. Execute orders
            for sig in signals:
                if not running:
                    break

                price = live_prices.get(sig.symbol)
                if price is None:
                    continue

                if sig.action in (ACTION_BUY, ACTION_STRONG_BUY):
                    sector = SYMBOL_TO_SECTOR.get(sig.symbol, "Tech")
                    num_in_sector = len(SECTORS.get(sector, []))
                    alloc = allocations.get(sector, 0.33)
                    qty = compute_position_size(
                        sig.symbol, price, portfolio.total_value, alloc, num_in_sector
                    )
                    if qty > 0:
                        # Check cash availability
                        cost = qty * price
                        avail = portfolio.cash - settlement.get_unavailable_cash()
                        if cost > avail:
                            qty = int(avail // price)
                        if qty > 0:
                            executor.execute_buy(sig.symbol, qty, price, sig.reason)

                elif sig.action == ACTION_SELL:
                    pos = portfolio.get_position(sig.symbol)
                    if pos and pos["qty"] > 0:
                        qty = pos["qty"]
                        executor.execute_sell(sig.symbol, qty, price, sig.reason)
                        # Track wash sale
                        loss = (pos.get("avg_cost", price) - price) * qty
                        if loss >= WASH_SALE_LOSS_THRESHOLD:
                            wash_tracker.record_sale(sig.symbol, loss)
                        # Track settlement
                        settlement.record_sale_proceeds(qty * price)

            # 12. Sync portfolio state
            if mode == "SIM":
                portfolio.sync_from_sim(TRADES_FILE)
            else:
                portfolio.sync_from_api(etrade, account)

            logger.info(
                "Cycle %d complete: %d positions, cash=$%.2f, total=$%.2f",
                cycle, portfolio.num_positions(), portfolio.cash, portfolio.total_value,
            )

        except Exception:
            logger.exception("Error in cycle %d", cycle)

        # Sleep until next cycle
        _sleep(POLL_INTERVAL_SECONDS, lambda: running)

    logger.info("Trading system shut down gracefully.")


def _sleep(seconds: float, check_running):
    """Sleep in small increments to allow graceful shutdown."""
    end = time.time() + seconds
    while time.time() < end and check_running():
        time.sleep(min(5, end - time.time()))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Value-based stock trading system")
    parser.add_argument(
        "--mode",
        choices=["SIM", "REAL"],
        default="SIM",
        help="SIM = paper trading (JSON log), REAL = live orders",
    )
    parser.add_argument(
        "--sandbox",
        action="store_true",
        default=False,
        help="Use E*TRADE sandbox environment",
    )
    args = parser.parse_args()
    run(args.mode, args.sandbox)


if __name__ == "__main__":
    main()
