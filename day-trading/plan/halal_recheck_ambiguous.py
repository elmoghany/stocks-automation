"""Re-screen names removed by the (now withdrawn) free-text ambiguous tier.

User ruling 2026-08-14: only a PURE defense company is haram -- AMD,
which merely sells into defense/aerospace markets, is halal. Matching
those terms in free text removed 132+ names whose summaries name their
CUSTOMERS. HARAM_AMBIGUOUS_ANY is now empty, so those verdicts are stale.

Writes data/halal_recheck.json (separate file so it can run alongside
the builder without both writing halal_universe.json). Merge afterwards.
"""
import importlib.util, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("dtm", ROOT / "day-trading.py")
dt = importlib.util.module_from_spec(spec); spec.loader.exec_module(dt)

uni = json.loads((ROOT / "data/halal_universe.json").read_text())
old = set(json.loads((ROOT / "data/halal_list.pre-2026-08-13.json").read_text())["symbols"])
new = set(json.loads((ROOT / "data/halal_list.json").read_text())["symbols"])

TERMS = ("defense", "aerospace", "gaming", "entertainment", "theater",
         "theatre", "cinema", "movie")
todo = []
for s in sorted(old - new):
    fr = str(uni.get(s, {}).get("fail_reason", ""))
    if "CANNOT-VERIFY" in fr and any(t in fr.lower() for t in TERMS):
        todo.append(s)
print(f"{len(todo)} names removed by the ambiguous tier -- re-screening",
      flush=True)

out = {}
outf = ROOT / "data/halal_recheck.json"
for n, s in enumerate(todo, 1):
    try:
        r = dt.halal_check(s)
        out[s] = {k: r.get(k) for k in
                  ("halal", "verdict", "source", "loan_pct", "cash_pct",
                   "combined", "haram_pct", "fail_reason")}
    except Exception as e:
        out[s] = {"halal": False, "source": "error",
                  "fail_reason": f"ERROR: {type(e).__name__}: {e}"}
    if n % 25 == 0:
        outf.write_text(json.dumps(out, indent=1))
        print(f"  [{n}/{len(todo)}] restored so far: "
              f"{sum(1 for v in out.values() if v.get('halal'))}", flush=True)
    time.sleep(0.4)
outf.write_text(json.dumps(out, indent=1))
ok = sum(1 for v in out.values() if v.get("halal"))
print(f"done: {ok}/{len(todo)} now PASS and should be restored to the list",
      flush=True)
