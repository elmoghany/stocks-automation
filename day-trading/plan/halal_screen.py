"""Run day-trading.py's halal_check on symbols and print the fields the paper
ledger records. Written 2026-08-31 (Day 19).

The `screen` subcommand is the legacy 6-rule penny screener and its halal column
reads "-"; `livescreen` needs E*TRADE. Neither answers the compliance question.
This calls halal_check directly so the ledger's numbers come from the same code
path the offline universe build uses.

QUESTION 2 IS NOT ANSWERED HERE. halal_check runs a keyword industry screen that
is known-blind to intoxicants (ZSTK, 2026-08-28), gambling (AIFA) and mislabelled
sectors (AIIR tobacco read as Industrial Conglomerates). A PASS here means
"question 1 clean and no keyword hit" -- the business must still be read by hand
before arming.

Usage:
    python plan/halal_screen.py SYM [SYM ...]
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import importlib.util

spec = importlib.util.spec_from_file_location(
    "dt", Path(__file__).resolve().parent.parent / "day-trading.py")
dt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dt)


def main():
    out = {}
    for sym in (s.upper() for s in sys.argv[1:]):
        try:
            r = dt.halal_check(sym)
        except Exception as e:
            r = {"verdict": "ERROR", "fail_reason": f"{type(e).__name__}: {e}"}
        out[sym] = r
        print(f"{sym:<7} {r.get('verdict','?'):<5} "
              f"loan {r.get('loan_pct','?'):>8}  cash {r.get('cash_pct','?'):>8}  "
              f"comb {r.get('combined','?'):>8}  haram {r.get('haram_pct','?'):>7}  "
              f"src={r.get('source','?'):<9} {r.get('fail_reason','')}")
        if r.get("ruling"):
            print(f"        ruling attached: {json.dumps(r['ruling'])[:300]}")
    print("\nREMINDER: verdict PASS here answers QUESTION 1 only. Read the "
          "business description and answer QUESTION 2 by hand before arming.")


if __name__ == "__main__":
    main()
