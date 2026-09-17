"""HALAL-GATE-REVIEW (2026-09-17) -- re-screen a named subset and refresh
the parked armable list.

Used after `plan/hgr_rulings.py --write` adds Class-B rulings: only the
ruled names can have moved, so re-running the whole 2,439-name rescreen
to pick them up would cost 80 minutes to change a few dozen verdicts.
Same cache keys, same list writer, same park rule (NEVER touches
data/halal_list.json -- a live session reads it every scan cycle).

Usage: python plan/hgr_apply.py SYM [SYM ...]
       python plan/hgr_apply.py --ruled        (every ruling dated today)
"""
import importlib.util
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
_spec = importlib.util.spec_from_file_location("dt", ROOT / "day-trading.py")
dt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dt)

UNI_F = ROOT / "data/halal_universe.json"
LIST_F = ROOT / "data/halal_list.NEW.json"
CACHED_KEYS = ("halal", "verdict", "source", "loan_pct", "cash_pct",
               "combined", "haram_pct", "haram_src", "interest_flags",
               "last_available", "fail_reason")


def one(sym):
    import yfinance as yf
    time.sleep(0.7)
    try:
        t = yf.Ticker(sym)
        r = dt.halal_check(sym, t)
        rec = {k: r.get(k) for k in CACHED_KEYS}
        mc = (dt.load_rh_fundamentals().get(sym.upper()) or {}).get(
            "market_cap")
        if not mc:
            try:
                mc = (t.info or {}).get("marketCap")
            except Exception:
                mc = None
        rec["mcap"] = float(mc or 0) or None
        return sym, rec
    except Exception as e:
        return sym, {"halal": False, "source": "error",
                     "fail_reason": f"ERROR: {type(e).__name__}: {e}"}


def main():
    done = json.loads(UNI_F.read_text())
    if "--ruled" in sys.argv:
        rul = json.loads((ROOT / "data/halal_rulings.json").read_text())
        today = time.strftime("%Y-%m-%d")
        syms = sorted(s for s, v in rul.items()
                      if not s.startswith("_") and isinstance(v, dict)
                      and v.get("date") == today)
    else:
        syms = [s.upper() for s in sys.argv[1:] if not s.startswith("--")]
    syms = [s for s in syms if s in done]
    print(f"re-screening {len(syms):,} names", flush=True)
    before = {s: bool(done[s].get("halal")) for s in syms}
    flips = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        for n, (sym, rec) in enumerate(ex.map(one, syms), 1):
            done[sym] = rec
            if bool(rec.get("halal")) != before[sym]:
                flips.append((sym, before[sym], bool(rec.get("halal")),
                              rec.get("source"), rec.get("fail_reason")))
            if n % 25 == 0:
                UNI_F.write_text(json.dumps(done))
                print(f"  {n:,}/{len(syms):,}", flush=True)
    UNI_F.write_text(json.dumps(done))
    for s, was, now, src, fr in flips:
        print(f"  {s:<6} {'PASS' if was else 'FAIL'} -> "
              f"{'PASS' if now else 'FAIL'}  src={src}  {(fr or '')[:60]}")
    halal = sorted(s for s, r in done.items() if r.get("halal"))
    LIST_F.write_text(json.dumps(
        {"updated": time.strftime("%Y-%m-%d"), "n": len(halal),
         "symbols": halal}))
    print(f"\nARMABLE {len(halal):,} -> {LIST_F.name} "
          f"(data/halal_list.json untouched)")


if __name__ == "__main__":
    main()
