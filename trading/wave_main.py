"""Entry point: 60-minute polling loop for the Never Lose wave trading system."""

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
    WAVE_EXTENDED_CLOSE_HOUR,
    WAVE_EXTENDED_OPEN_HOUR,
    WAVE_INITIAL_CASH,
    WAVE_POLL_INTERVAL_SECONDS,
    WAVE_TRADES_FILE,
    TOKEN_RENEW_MINUTES,
)
from trading.api_wrapper import ETradeSession
from trading.data_pipeline import fetch_all_historical, fetch_live_quotes
from trading.risk_manager import WashSaleTracker
from trading.wave_config import WAVE_SYMBOLS, WAVE_TOP6
from trading.wave_sectors import compute_sector_momentum, format_sector_dashboard
from trading.wave_trader import WaveTrader

ET = pytz.timezone("US/Eastern")


def setup_logging():
    logger = logging.getLogger("wave")
    logger.setLevel(logging.DEBUG)
    os.makedirs(DATA_DIR, exist_ok=True)
    fh = RotatingFileHandler(
        os.path.join(DATA_DIR, "wave_trading.log"),
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


def get_market_session() -> tuple[bool, str]:
    """Determine if we're in trading hours and which session.

    Returns (is_open, session_type):
      4:00-9:30 AM ET  -> (True, "EXTENDED")   pre-market
      9:30-4:00 PM ET  -> (True, "REGULAR")    regular
      4:00-8:00 PM ET  -> (True, "EXTENDED")   post-market
      Otherwise        -> (False, "CLOSED")
    """
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False, "CLOSED"

    hour, minute = now.hour, now.minute
    t = hour * 60 + minute

    if t < WAVE_EXTENDED_OPEN_HOUR * 60:       # before 4 AM
        return False, "CLOSED"
    if t < 9 * 60 + 30:                        # 4:00-9:30
        return True, "EXTENDED"
    if t < 16 * 60:                            # 9:30-4:00
        return True, "REGULAR"
    if t < WAVE_EXTENDED_CLOSE_HOUR * 60:      # 4:00-8:00 PM
        return True, "EXTENDED"
    return False, "CLOSED"


def select_account(etrade: ETradeSession, account_index: int = None) -> dict:
    accounts = etrade.get_account_list()
    if not accounts:
        print("No accounts found.")
        sys.exit(1)
    if account_index is not None:
        if account_index >= len(accounts):
            print(f"Account index {account_index} out of range.")
            sys.exit(1)
        acct = accounts[account_index]
        print(f"Using account: {acct.get('accountId')} - {acct.get('accountDesc', '')}")
        return acct
    print("\nAvailable accounts:")
    for i, acct in enumerate(accounts, 1):
        print(f"  {i}) {acct.get('accountId', '?')} - {acct.get('accountDesc', '')}")
    while True:
        choice = input("Select account number: ")
        if choice.isdigit() and 1 <= int(choice) <= len(accounts):
            return accounts[int(choice) - 1]


def print_status(trader: WaveTrader, live_prices: dict, session: str,
                 cycle: int, historical: dict):
    """Print formatted status table with sector momentum."""
    now_et = datetime.now(ET).strftime("%H:%M ET")
    perf = trader.get_performance()

    print(f"\n{'=' * 100}")
    print(f"  Wave Trader Cycle {cycle} at {now_et} ({session} session)")
    print(f"  Active: {len(trader.trades)} | Completed: {perf['total_trades']} "
          f"| Win rate: {perf['win_rate']}% | Total P&L: ${perf['total_pnl']:.2f}")
    print(f"{'=' * 100}")

    # Sector momentum dashboard
    sector_mom = compute_sector_momentum(historical)
    print(f"\n  SECTOR MOMENTUM:")
    print(format_sector_dashboard(sector_mom))
    print()
    print(f"  {'Stock':<6} {'Price':>8} {'State':<14} {'BuyAt':>8} {'SellAt':>8} "
          f"{'P&L':>10} {'Gain%':>7} {'Days':>5} {'Tier':<4}")
    print(f"  {'-' * 90}")

    rows = trader.get_status_table(live_prices)
    for r in rows:
        price_s = f"${r['price']:.2f}" if r['price'] else "N/A"
        state_s = r['state']
        buy_s = f"${r['buy_price']:.2f}" if r['buy_price'] else "--"
        sell_s = f"${r['sell_target']:.2f}" if r['sell_target'] else "--"
        pnl_s = f"${r['unrealized_pnl']:.2f}" if r['unrealized_pnl'] is not None else "--"
        gain_s = f"{r['gain_pct']:+.1f}%" if r['gain_pct'] is not None else "--"
        days_s = str(r['days_held']) if r['days_held'] is not None else "--"

        # Highlight active trades
        prefix = "  "
        if state_s == "ACTIVE":
            prefix = "> "
        elif state_s == "SELL_PENDING":
            prefix = "$ "

        print(f"{prefix}{r['symbol']:<6} {price_s:>8} {state_s:<14} {buy_s:>8} {sell_s:>8} "
              f"{pnl_s:>10} {gain_s:>7} {days_s:>5} {r['tier']:<4}")

    # Unrealized total
    total_unrealized = sum(
        t.unrealized_pnl for t in trader.trades.values() if t.unrealized_pnl
    )
    print(f"\n  Unrealized P&L: ${total_unrealized:.2f} | "
          f"Realized P&L: ${perf['total_pnl']:.2f}")
    print()


def run(mode: str, sandbox: bool, account_index: int = None,
        ignore_hours: bool = False):
    logger = setup_logging()
    logger.info("Starting wave trader: mode=%s, sandbox=%s", mode, sandbox)

    os.makedirs(DATA_DIR, exist_ok=True)

    # Authenticate (skip for pure SIM)
    etrade = None
    account = None
    if mode in ("SANDBOX", "REAL"):
        etrade = ETradeSession(sandbox=sandbox)
        etrade.authenticate()
        account = select_account(etrade, account_index)
        logger.info("Using account: %s", account.get("accountId"))

    last_renew = time.time()

    # Initialize wave trader + wash sale tracker
    # Top 6 mode: $100K split into 6 buckets, each compounds independently
    trader = WaveTrader(initial_cash=WAVE_INITIAL_CASH, num_stocks=len(WAVE_TOP6))
    wash_tracker = WashSaleTracker()

    # Portfolio value tracking (simple for SIM)
    portfolio_value = WAVE_INITIAL_CASH

    # Use top 6 stocks for trading, all 21 for sector momentum
    trade_symbols = WAVE_TOP6
    logger.info("Trading %d stocks: %s", len(trade_symbols), trade_symbols)
    logger.info("Fetching historical data for %d wave symbols...", len(WAVE_SYMBOLS))
    historical = fetch_all_historical(WAVE_SYMBOLS)
    logger.info("Historical data loaded.")

    # Graceful shutdown
    running = True

    def shutdown(signum, frame):
        nonlocal running
        logger.info("Shutdown signal received...")
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Polling loop
    cycle = 0
    while running:
        cycle += 1
        is_open, session = get_market_session()
        now_et = datetime.now(ET)
        logger.info("=== Wave Cycle %d at %s (%s) ===", cycle, now_et.strftime("%H:%M"), session)

        # Token renewal
        if etrade:
            elapsed_min = (time.time() - last_renew) / 60
            if elapsed_min >= TOKEN_RENEW_MINUTES:
                if etrade.renew_token():
                    last_renew = time.time()

        # Market hours check
        if not ignore_hours and not is_open:
            logger.info("Market closed. Sleeping until next cycle.")
            # Expire any pending sells at end of day
            trader.expire_pending_sells()
            trader.save()
            _sleep(WAVE_POLL_INTERVAL_SECONDS, lambda: running)
            continue

        try:
            # Fetch live prices
            if etrade:
                etrade_quotes = fetch_live_quotes(etrade, WAVE_SYMBOLS)
                live_prices = {
                    sym: q.get("last_price")
                    for sym, q in etrade_quotes.items()
                    if q.get("last_price") is not None
                }
            else:
                # SIM mode: use latest historical close as proxy
                live_prices = {}
                for sym in WAVE_SYMBOLS:
                    df = historical.get(sym)
                    if df is not None and len(df) > 0:
                        live_prices[sym] = float(df["Close"].iloc[-1])

            # Get wash sale blocked symbols
            wash_blocked = set(wash_tracker.get_blocked_symbols())

            # Scan for new buy opportunities (top 6, sector-aware, wash-sale-safe)
            new_buys = trader.scan_for_entries(
                trade_symbols, historical, live_prices, portfolio_value,
                wash_blocked=wash_blocked,
            )
            # Portfolio value = sum of all stock buckets + held positions
            portfolio_value = sum(trader.stock_cash.values())
            for t in trader.trades.values():
                p = live_prices.get(t.symbol, t.buy_price)
                portfolio_value += t.quantity * p

            # Check for sell signals
            exits = trader.check_exits(live_prices, session)

            # Process pending sells (realistic same-day fill)
            filled = trader.process_pending_sells(live_prices)

            # Print status with sector dashboard
            print_status(trader, live_prices, session, cycle, historical)

            # Save state
            trader.save()

            logger.info(
                "Cycle %d done: %d active, %d completed, portfolio $%.2f",
                cycle, len(trader.trades),
                len(trader.completed), portfolio_value,
            )

        except Exception:
            logger.exception("Error in wave cycle %d", cycle)

        _sleep(WAVE_POLL_INTERVAL_SECONDS, lambda: running)

    # End of day cleanup
    trader.expire_pending_sells()
    trader.save()
    logger.info("Wave trader shut down.")


def _sleep(seconds: float, check_running):
    end = time.time() + seconds
    while time.time() < end and check_running():
        time.sleep(min(5, end - time.time()))


def main():
    parser = argparse.ArgumentParser(description="Wave Trader (Never Lose strategy)")
    parser.add_argument(
        "--mode", choices=["SIM", "SANDBOX", "REAL"], default="SIM",
        help="SIM = paper trade, SANDBOX = E*TRADE sandbox, REAL = live",
    )
    parser.add_argument("--account", type=int, default=None)
    parser.add_argument("--ignore-hours", action="store_true", default=False)
    args = parser.parse_args()

    sandbox = args.mode == "SANDBOX"
    run(args.mode, sandbox, args.account, args.ignore_hours)


if __name__ == "__main__":
    main()
