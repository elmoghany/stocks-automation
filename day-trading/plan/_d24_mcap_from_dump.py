"""Day-24: load Robinhood market caps for named tickers straight out of a saved
run_scan dump into the fundamentals cache halal_check reads.

Beats hand-transcribing the "Market cap" column (that is where a typo would
silently change a halal denominator). Refuses a ticker whose row carries no
market cap rather than inventing one -- a missing denominator is a FAIL.

Usage:  python plan/_d24_mcap_from_dump.py <dump.json> SYM [SYM ...]
"""
import json
import subprocess
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent

dump = Path(sys.argv[1])
want = {s.upper() for s in sys.argv[2:]}

raw = json.loads(dump.read_text(encoding="utf-8-sig"))
data = raw.get("data", raw)
res = data.get("result", data)
rows = res.get("results") or []

found, missing = {}, set(want)
for r in rows:
    tk = (r.get("ticker") or "").upper()
    if tk in want:
        mc = (r.get("columns") or {}).get("Market cap")
        if mc not in (None, ""):
            found[tk] = float(mc)
            missing.discard(tk)

for sym, mcap in sorted(found.items()):
    out = subprocess.run(
        [sys.executable, str(DIR / "update_rh_fundamentals.py"), sym, repr(mcap)],
        capture_output=True, text=True)
    print(f"{sym:6} {out.stdout.strip() or out.stderr.strip()}")

if missing:
    print(f"NO MARKET CAP IN DUMP (left uncached, will read "
          f"REFUSE-TO-EVALUATE): {sorted(missing)}")
