"""Live halal screen for a scan hit missing from halal_universe.json.

Usage:  python plan/live_halal.py SYM [SYM ...]

This is QUESTION 1 ONLY -- the financing test (loans/mcap, deposits/mcap,
combined, plus the interest-income keyword screen), run by calling
day-trading.halal_check verbatim with the Robinhood market cap from
data/rh_fundamentals.json. A missing market cap is a REFUSAL TO EVALUATE,
not a pass: fetch it with update_rh_fundamentals.py first.

QUESTION 2 -- does the company EARN permissibly (the binary 5% rule) -- is
NOT mechanised and is NOT answered here. halal_check's revenue term is
interest-income only and is structurally blind to alcohol, pork, gambling
and entertainment revenue. A PASS printed below means "the financing test
passed"; the business-line judgement is still owed before arming, and
only a name that passes BOTH questions is armable.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import importlib.util

DIR = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("dt", DIR / "day-trading.py")
dt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dt)

RH_F = DIR / "data" / "rh_fundamentals.json"
FIELDS = ("halal", "verdict", "loan_pct", "cash_pct", "combined",
          "haram_pct", "fail_reason", "source", "mcap")


def main():
    syms = [s.upper() for s in sys.argv[1:]]
    rh = json.loads(RH_F.read_text()) if RH_F.exists() else {}
    for sym in syms:
        mcap = (rh.get(sym) or {}).get("market_cap")
        if not mcap:
            print(f"{sym:<7} REFUSE-TO-EVALUATE: no RH market cap cached. "
                  f"Run update_rh_fundamentals.py {sym} MCAP SECTOR INDUSTRY")
            continue
        # DOT-CLASS TICKERS (2026-09-01, Day 20). Robinhood says "HVT.A";
        # yfinance 404s on that and wants "HVT-A". Left unhandled the name
        # reads NO FUNDAMENTALS DATA -- a refusal to evaluate that looks
        # exactly like a compliance failure in the ledger. Try the dash
        # form, then the bare root ticker. The root is the SAME ISSUER with
        # ONE consolidated balance sheet, which is the right input for the
        # ratio test, but it is a substitution and is logged as one.
        attempts = [sym]
        if "." in sym:
            attempts.append(sym.replace(".", "-"))
            attempts.append(sym.split(".")[0])
        r, used = None, None
        for cand in attempts:
            try:
                rr = dt.halal_check(cand, mcap=float(mcap))
            except Exception as e:
                print(f"{sym:<7} ERROR on {cand}: {type(e).__name__}: {e}")
                continue
            if "NO FUNDAMENTALS DATA" not in (rr.get("fail_reason") or ""):
                r, used = rr, cand
                break
            r, used = r or rr, used or cand
        if r is None:
            continue
        if used != sym:
            print(f"{sym:<7} NOTE: yfinance could not resolve '{sym}'; "
                  f"statements taken from '{used}' (same issuer, one "
                  f"consolidated balance sheet). SUBSTITUTION -- record it.")
        got = {k: r.get(k) for k in FIELDS}
        pct = lambda k: ("n/a" if got.get(k) is None
                         else f"{float(got[k]):.2f}")
        print(f"{sym:<7} q1={got.get('verdict') or ('PASS' if got.get('halal') else 'FAIL')}"
              f"  loan={pct('loan_pct')}%  cash={pct('cash_pct')}%"
              f"  comb={pct('combined')}%  haram={pct('haram_pct')}%"
              f"  src={got.get('source')}"
              f"  mcap=${float(mcap):,.0f}")
        if got.get("fail_reason"):
            print(f"        reason: {got['fail_reason']}")
        print(f"        NOTE: question 2 (business line / 5% rule) NOT "
              f"answered by this tool -- judge it before arming.")


if __name__ == "__main__":
    main()
