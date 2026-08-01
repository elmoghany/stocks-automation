"""Place a test LIMIT order in the E*TRADE SANDBOX (paper environment).

Usage: python plan/sandbox_place_test.py [SYMBOL] [QTY] [LIMIT_PRICE]
Defaults: AMD, 1 share, limit $100.00 (sandbox ignores real market prices).
Requires a valid sandbox token (plan/sandbox_auth.py --auth / --verifier).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trading.api_wrapper import ETradeSession

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "AMD"
QTY = int(sys.argv[2]) if len(sys.argv) > 2 else 1
LIMIT = float(sys.argv[3]) if len(sys.argv) > 3 else 100.00


def main() -> None:
    sess = ETradeSession(sandbox=True)
    if not sess._load_saved_token():
        print("No valid sandbox token. Run: python plan/sandbox_auth.py --auth")
        sys.exit(1)

    accounts = sess.get_account_list()
    if not accounts:
        print("No sandbox accounts returned.")
        sys.exit(1)
    acct = accounts[0]
    print(f"Using sandbox account: {acct.get('accountId')} "
          f"({acct.get('accountDesc')}, {acct.get('institutionType')})")

    print(f"\nPreviewing LIMIT BUY {QTY} x {SYMBOL} @ ${LIMIT:.2f} ...")
    preview = sess.preview_order(acct, SYMBOL, "BUY", QTY, LIMIT)
    if not preview:
        print("Preview FAILED (see log above).")
        sys.exit(1)
    est = preview.get("Order", [{}])[0].get("estimatedTotalAmount")
    pid = preview.get("PreviewIds", [{}])[0].get("previewId")
    print(f"Preview OK: previewId={pid}, estimated total=${est}")

    print("\nPlacing order ...")
    placed = sess.place_order(acct, preview, SYMBOL, "BUY", QTY, LIMIT)
    if not placed:
        print("Place FAILED (see log above).")
        sys.exit(1)
    oids = placed.get("OrderIds", [{}])
    oid = oids[0].get("orderId") if oids else None
    msgs = placed.get("Order", [{}])[0].get("messages", {}).get("Message", [])
    print(f"ORDER PLACED: orderId={oid}")
    for m in msgs:
        print(f"  message: {m.get('description')}")
    print("\nSandbox order test PASSED.")


if __name__ == "__main__":
    main()
