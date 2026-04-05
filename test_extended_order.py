"""
Test: Place a REAL BUY limit order for AMD at current price - $4.00
      (1 share, GOOD_FOR_DAY)

Interactive usage (run in your own terminal):
    python test_extended_order.py [--session REGULAR|EXTENDED]

Two-phase usage (for automated runs):
    python test_extended_order.py --auth
    python test_extended_order.py --verifier CODE [--session REGULAR|EXTENDED] [--account 0] [--confirm]
"""

import sys
import json
import pickle
import configparser
import webbrowser
from pathlib import Path
from rauth import OAuth1Service
from trading.config import (
    CONFIG_INI_PATH,
    ETRADE_AUTH_BASE,
    ETRADE_AUTHORIZE_URL,
    PROD_BASE_URL,
)
from trading.api_wrapper import ETradeSession

SYMBOL = "AMD"
QUANTITY = 1
PRICE_OFFSET = 5.00
TOKEN_FILE = Path("data/.etrade_tokens.pkl")


def load_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_INI_PATH)
    return config["DEFAULT"]["CONSUMER_KEY"], config["DEFAULT"]["CONSUMER_SECRET"]


def make_service(consumer_key, consumer_secret):
    return OAuth1Service(
        name="etrade",
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        request_token_url=f"{ETRADE_AUTH_BASE}/oauth/request_token",
        access_token_url=f"{ETRADE_AUTH_BASE}/oauth/access_token",
        authorize_url=ETRADE_AUTHORIZE_URL,
        base_url=ETRADE_AUTH_BASE,
    )


def run_order(etrade, session_type, account_index, auto_confirm):
    """Fetch quote, preview, and place order."""
    # Quote
    print(f"\nFetching quote for {SYMBOL}...")
    quotes = etrade.get_quotes([SYMBOL])
    if SYMBOL not in quotes:
        print(f"ERROR: Could not retrieve quote for {SYMBOL}")
        sys.exit(1)

    all_data = quotes[SYMBOL].get("All", {})
    last_price = all_data.get("lastTrade") or all_data.get("ask") or all_data.get("bid")
    if last_price is None:
        print(f"ERROR: No price in quote:\n{json.dumps(quotes[SYMBOL], indent=2)}")
        sys.exit(1)

    last_price = float(last_price)
    limit_price = round(last_price - PRICE_OFFSET, 2)
    print(f"  Last price : ${last_price:.2f}")
    print(f"  Limit price: ${limit_price:.2f}  (last - ${PRICE_OFFSET:.2f})")
    print(f"  Session    : {session_type}")

    # Account
    accounts = etrade.get_account_list()
    if not accounts:
        print("ERROR: No accounts returned.")
        sys.exit(1)

    print("\nAvailable accounts:")
    for i, a in enumerate(accounts):
        print(f"  [{i}] {a.get('accountDesc', '')}  ({a.get('accountId', '')})")

    if account_index is None:
        choice = input("\nSelect account number [0]: ").strip()
        account_index = int(choice) if choice else 0

    account = accounts[account_index]
    print(f"Using: {account.get('accountDesc')} ({account.get('accountId')})")

    # Preview
    print(f"\nPreviewing {session_type} BUY: {QUANTITY} x {SYMBOL} @ ${limit_price:.2f}...")
    preview = etrade.preview_order(
        account=account,
        symbol=SYMBOL,
        action="BUY",
        quantity=QUANTITY,
        limit_price=limit_price,
        order_term="GOOD_FOR_DAY",
        market_session=session_type,
    )

    if not preview:
        print("ERROR: Preview failed. Check above for E*TRADE error message.")
        sys.exit(1)

    print("Preview response:")
    print(json.dumps(preview, indent=2))

    for order in preview.get("Order", []):
        for m in order.get("messages", {}).get("Message", []):
            print(f"  [{m.get('type')}] {m.get('description')}")

    # Confirm
    if not auto_confirm:
        ans = input(f"\nPlace REAL order? BUY {QUANTITY} {SYMBOL} @ ${limit_price:.2f} {session_type} (yes/no): ").strip().lower()
        if ans != "yes":
            print("Cancelled.")
            sys.exit(0)

    # Place
    print("\nPlacing order...")
    result = etrade.place_order(
        account=account,
        preview_response=preview,
        symbol=SYMBOL,
        action="BUY",
        quantity=QUANTITY,
        limit_price=limit_price,
        order_term="GOOD_FOR_DAY",
        market_session=session_type,
    )

    if not result:
        print("ERROR: Order placement failed.")
        sys.exit(1)

    print("\nOrder placed successfully!")
    print(json.dumps(result, indent=2))
    order_id = result.get("OrderIds", [{}])[0].get("orderId", "N/A")
    print(f"\nOrder ID : {order_id}")
    print(f"Symbol   : {SYMBOL}")
    print(f"Action   : BUY")
    print(f"Qty      : {QUANTITY}")
    print(f"Limit    : ${limit_price:.2f}")
    print(f"Session  : {session_type}")
    print(f"Term     : GOOD_FOR_DAY")
    TOKEN_FILE.unlink(missing_ok=True)


def main():
    args = sys.argv[1:]

    # Parse --session
    session_type = "EXTENDED"
    if "--session" in args:
        i = args.index("--session")
        session_type = args[i + 1].upper()

    # Parse --account
    account_index = None
    if "--account" in args:
        i = args.index("--account")
        account_index = int(args[i + 1])

    auto_confirm = "--confirm" in args

    # ---- Two-phase: --auth ----
    if "--auth" in args:
        consumer_key, consumer_secret = load_config()
        service = make_service(consumer_key, consumer_secret)
        request_token, request_token_secret = service.get_request_token(
            params={"oauth_callback": "oob", "format": "json"}
        )
        TOKEN_FILE.parent.mkdir(exist_ok=True)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump({
                "request_token": request_token,
                "request_token_secret": request_token_secret,
                "consumer_key": consumer_key,
                "consumer_secret": consumer_secret,
            }, f)
        auth_url = service.authorize_url.format(consumer_key, request_token)
        print(f"\nOpening browser for E*TRADE authorization...")
        print(f"URL: {auth_url}\n")
        webbrowser.open(auth_url)
        print("After authorizing, give me the code and I will run:")
        print(f"  python test_extended_order.py --verifier YOUR_CODE --session {session_type} --account 0 --confirm")
        return

    # ---- Two-phase: --verifier ----
    if "--verifier" in args:
        i = args.index("--verifier")
        verifier = args[i + 1]

        if not TOKEN_FILE.exists():
            print("ERROR: Run --auth first.")
            sys.exit(1)

        with open(TOKEN_FILE, "rb") as f:
            saved = pickle.load(f)

        service = make_service(saved["consumer_key"], saved["consumer_secret"])
        session = service.get_auth_session(
            saved["request_token"],
            saved["request_token_secret"],
            params={"oauth_verifier": verifier},
        )
        print("Authentication successful.")

        etrade = ETradeSession.__new__(ETradeSession)
        etrade.session = session
        etrade.consumer_key = saved["consumer_key"]
        etrade.base_url = PROD_BASE_URL
        etrade._save_token()  # persist so future runs skip browser login

        run_order(etrade, session_type, account_index, auto_confirm)
        return

    # ---- Use saved access token if available (no browser needed) ----
    etrade = ETradeSession(sandbox=False)
    if etrade._load_saved_token():
        print("Reusing saved session — no login needed.")
        run_order(etrade, session_type, account_index if account_index is not None else 0, auto_confirm)
        return

    # ---- Interactive (single-phase, browser login) ----
    print("Connecting to E*TRADE PRODUCTION...")
    etrade.authenticate()
    run_order(etrade, session_type, account_index, auto_confirm)


if __name__ == "__main__":
    main()
