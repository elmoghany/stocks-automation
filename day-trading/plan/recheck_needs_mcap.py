"""Re-screen needs_mcap.json symbols that NOW have a Robinhood market cap.

Runs day-trading.py::halal_check VERBATIM (the same function the live
gate and plan/build_halal_universe.py call) with the RH market cap
passed explicitly, so the mcap==0 refusal no longer masks the real
verdict. Writes to data/halal_mcap_recheck.json -- a SEPARATE file; the
merge into halal_universe.json / halal_list.json happens in the main
session where the list format is controlled. This script never touches
the list files.

Verdict semantics preserved from the builder: PASS / FAIL /
CANNOT-VERIFY, plus NO-DATA when yfinance still has no statements even
with an mcap in hand (refused, stays unverifiable -- typical for very
recent IPOs and SPACs yfinance has not populated yet).

Usage:  python plan/recheck_needs_mcap.py
Resumable: skips symbols already in the output file; delete the file
for a clean pass.
"""

import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
_spec = importlib.util.spec_from_file_location("dt", ROOT / "day-trading.py")
dt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dt)

NEED_F = ROOT / "data" / "needs_mcap.json"
RH_F = ROOT / "data" / "rh_fundamentals.json"
OUT_F = ROOT / "data" / "halal_mcap_recheck.json"
PACE_SEC = 0.7          # same courtesy pacing as the universe builder
FIELDS = ("halal", "verdict", "source", "loan_pct", "cash_pct",
          "combined", "haram_pct", "fail_reason")


def verdict_bucket(r):
    v = r.get("verdict")
    if v in ("PASS", "FAIL", "CANNOT-VERIFY"):
        return v
    if "NO FUNDAMENTALS DATA" in (r.get("fail_reason") or ""):
        return "NO-DATA"
    return "ERROR"


def main():
    need = set(json.loads(NEED_F.read_text()))
    rh = json.loads(RH_F.read_text())
    todo = sorted(s for s in need
                  if (rh.get(s) or {}).get("market_cap"))
    out = json.loads(OUT_F.read_text()) if OUT_F.exists() else {}
    queue = [s for s in todo if s not in out]
    print(f"{len(todo)} needs_mcap symbols have an RH market cap; "
          f"{len(out)} already rechecked, {len(queue)} to do", flush=True)

    for n, sym in enumerate(queue, 1):
        time.sleep(PACE_SEC)
        mcap = float(rh[sym]["market_cap"])
        try:
            r = dt.halal_check(sym, mcap=mcap)
        except Exception as e:
            # loud, never swallowed -- and cached as ERROR so a re-run
            # retries it (delete the entry or the file to force).
            print(f"  !! ERROR {sym}: {type(e).__name__}: {e}", flush=True)
            r = {"halal": False, "source": "error",
                 "fail_reason": f"ERROR: {type(e).__name__}: {e}"}
        rec = {"mcap": mcap, "rechecked": time.strftime("%Y-%m-%d")}
        rec.update({k: r.get(k) for k in FIELDS})
        out[sym] = rec
        OUT_F.write_text(json.dumps(out, indent=1))
        print(f"  [{n}/{len(queue)}] {sym:<6} mcap ${mcap:>14,.0f}  "
              f"{verdict_bucket(rec):<13} {(rec.get('fail_reason') or '')[:60]}",
              flush=True)

    counts = {}
    for r in out.values():
        b = verdict_bucket(r)
        counts[b] = counts.get(b, 0) + 1
    print(f"\nRECHECK SUMMARY ({len(out)} symbols): "
          + "  ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    passing = sorted(s for s, r in out.items() if r.get("halal"))
    print(f"newly PASSING: {passing if passing else 'none'}")
    print(f"-> {OUT_F.relative_to(ROOT)} (merge into the universe happens "
          f"in the main session, NOT here)")


if __name__ == "__main__":
    main()
