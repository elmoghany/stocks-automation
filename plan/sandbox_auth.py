"""Two-phase sandbox auth + smoke test (keys come from Windows Credential Manager).

Phase 1:  python plan/sandbox_auth.py --auth
          -> opens browser, prints authorize URL, saves request token
Phase 2:  python plan/sandbox_auth.py --verifier CODE
          -> exchanges for access token, saves it, runs smoke test
Later:    python plan/sandbox_auth.py --smoke
          -> reuses saved token (renews it), runs smoke test only
"""

import argparse
import pickle
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trading.api_wrapper import ETradeSession

REQ_TOKEN_FILE = Path("data/.etrade_sandbox_request_token.pkl")


def phase_auth() -> None:
    sess = ETradeSession(sandbox=True)
    service = sess._make_service()
    rt, rts = service.get_request_token(
        params={"oauth_callback": "oob", "format": "json"})
    REQ_TOKEN_FILE.parent.mkdir(exist_ok=True)
    with open(REQ_TOKEN_FILE, "wb") as f:
        pickle.dump({"rt": rt, "rts": rts}, f)
    url = service.authorize_url.format(service.consumer_key, rt)
    webbrowser.open(url)
    print("Browser opened. If not, open this URL:")
    print(url)
    print("\nLog in, accept, then run:")
    print("  python plan/sandbox_auth.py --verifier CODE")


def phase_verifier(code: str) -> None:
    sess = ETradeSession(sandbox=True)
    service = sess._make_service()
    with open(REQ_TOKEN_FILE, "rb") as f:
        saved = pickle.load(f)
    sess.session = service.get_auth_session(
        saved["rt"], saved["rts"], params={"oauth_verifier": code})
    sess._save_token()
    REQ_TOKEN_FILE.unlink(missing_ok=True)
    print("Sandbox access token saved.")
    smoke(sess)


def phase_smoke() -> None:
    sess = ETradeSession(sandbox=True)
    if not sess._load_saved_token():
        print("No valid saved sandbox token. Run: python plan/sandbox_auth.py --auth")
        sys.exit(1)
    smoke(sess)


def smoke(sess: ETradeSession) -> None:
    print("\n--- SANDBOX SMOKE TEST ---")
    accounts = sess.get_account_list()
    print(f"accounts: {len(accounts)}")
    for a in accounts:
        print(f"  {a.get('accountId')}  {a.get('accountDesc')}  "
              f"{a.get('institutionType')}  {a.get('accountStatus')}")
    quotes = sess.get_quotes(["AMD"])
    q = quotes.get("AMD", {}).get("All", {})
    print(f"AMD quote: last={q.get('lastTrade')}  bid={q.get('bid')}  "
          f"ask={q.get('ask')}  (sandbox data is fake/stale by design)")
    if accounts:
        bal = sess.get_balance(accounts[0])
        computed = bal.get("Computed", {})
        print(f"balance acct[0]: cash available = "
              f"{computed.get('cashAvailableForInvestment')}")
    print("--- SMOKE TEST DONE ---")


def main() -> None:
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--auth", action="store_true")
    g.add_argument("--verifier", metavar="CODE")
    g.add_argument("--smoke", action="store_true")
    args = p.parse_args()
    if args.auth:
        phase_auth()
    elif args.verifier:
        phase_verifier(args.verifier)
    else:
        phase_smoke()


if __name__ == "__main__":
    main()
