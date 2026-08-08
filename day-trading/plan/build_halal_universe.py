"""ONE-TIME (then monthly) HALAL UNIVERSE PRE-SCREEN.

USER (2026-08-08): "analyze which stocks are halal based on recent
quarterly earnings, if not exist, use half year earning, if not exist,
use annual earnings. and save those stocks, so when we scan stocks, we
only scan the halal stocks, instead of wasting time search for so many
stocks... the halal skill should update stocks every first of each
month."

Universe: every clean ticker with close >= $2 in the most recent
grouped-daily file (data/massive/gd) -- the same universe the scanner
can ever surface.

Verdict: day-trading.py::halal_check VERBATIM -- the same function the
live session calls, so the pre-screen and the live gate cannot
disagree. Its source chain is already quarterly -> annual -> info;
half-year filers (foreign 6-K reporters) appear in yfinance's quarterly
table with 6-month period ends, so the user's quarterly -> half-year ->
annual chain is what this yields in practice. `source` records which
tier answered.

Market cap: names where yfinance has no mcap AND no shares outstanding
cannot be ratio-screened (the SSP bug class). They are NOT marked
haram -- they land in needs_mcap.json for the agent to backfill via
Robinhood (update_rh_fundamentals.py) and re-run; halal_check picks the
RH cap up automatically through load_rh_fundamentals.

Output (data/):
  halal_universe.json  full verdicts {sym: {halal, source, ratios...}}
  halal_list.json      just the PASSING symbols (what the scanner uses)
  needs_mcap.json      unverifiable pending an RH market cap

Resumable: flushes every 50 symbols, skips already-done on re-run.
Refresh monthly (1st): delete halal_universe.json first for a clean
pass, or pass --refresh.
"""

import gzip
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

GD = ROOT / "data/massive/gd"
UNI_F = ROOT / "data/halal_universe.json"
LIST_F = ROOT / "data/halal_list.json"
NEED_F = ROOT / "data/needs_mcap.json"
MIN_PRICE = 2.0
THREADS = 2          # v1 with 6 threads: yfinance rate-limited after ~900
                     # symbols and returned empty statements for the next
                     # 9,800 -- the no-data guard refused them all (105
                     # halal of 10,761, 97% "NO FUNDAMENTALS DATA").
                     # Slow and steady is the only way through 10k names.
PACE_SEC = 0.7       # per-request pause
BREAKER = 30         # consecutive no-data results -> assume rate-limited
BREAKER_SLEEP = 600  # and stand down for 10 minutes


def clean_ticker(sym):
    if not sym or not sym.isalpha() or not sym.isupper():
        return False
    if len(sym) == 5 and sym.endswith(("W", "U", "R")):
        return False
    return len(sym) <= 5


def universe():
    latest = sorted(GD.glob("*.json.gz"))[-1]
    with gzip.open(latest, "rt", encoding="utf-8") as f:
        rows = json.load(f)
    syms = sorted(r["T"] for r in rows
                  if clean_ticker(r.get("T") or "")
                  and (r.get("c") or 0) >= MIN_PRICE)
    print(f"universe from {latest.name}: {len(syms):,} symbols "
          f"(clean ticker, close >= ${MIN_PRICE:.0f})", flush=True)
    return syms


def _retryable(res):
    """A verdict that only says 'no data' is a FAILED FETCH, not a
    verdict -- must be retried on the next pass, never cached as done."""
    return (res.get("source") in ("none", "error")
            or "NO FUNDAMENTALS DATA" in (res.get("fail_reason") or ""))


def screen_one(sym):
    time.sleep(PACE_SEC)
    try:
        r = dt.halal_check(sym)
        return sym, {k: r.get(k) for k in
                     ("halal", "source", "loan_pct", "cash_pct",
                      "combined_pct", "haram_rev_pct", "fail_reason")}
    except Exception as e:
        return sym, {"halal": False, "source": "error",
                     "fail_reason": f"ERROR: {type(e).__name__}: {e}"}


def main():
    if "--refresh" in sys.argv and UNI_F.exists():
        UNI_F.unlink()
    done = json.loads(UNI_F.read_text()) if UNI_F.exists() else {}
    # drop failed fetches so they are re-tried, keep real verdicts
    retry = [s for s, r in done.items() if _retryable(r)]
    for s_ in retry:
        del done[s_]
    if retry:
        print(f"{len(retry):,} previous no-data results queued for retry",
              flush=True)
    syms = [s for s in universe() if s not in done]
    print(f"{len(done):,} already screened, {len(syms):,} to do", flush=True)

    t0 = time.time()
    streak = [0]
    with ThreadPoolExecutor(max_workers=THREADS) as ex:
        for n, (sym, res) in enumerate(ex.map(screen_one, syms), 1):
            done[sym] = res
            streak[0] = streak[0] + 1 if _retryable(res) else 0
            if streak[0] >= BREAKER:
                print(f"  RATE-LIMITED ({BREAKER} consecutive no-data) -- "
                      f"sleeping {BREAKER_SLEEP//60} min", flush=True)
                UNI_F.write_text(json.dumps(done))
                time.sleep(BREAKER_SLEEP)
                streak[0] = 0
            if n % 50 == 0 or n == len(syms):
                UNI_F.write_text(json.dumps(done))
                el = time.time() - t0
                eta = el / n * (len(syms) - n) / 60
                h = sum(1 for r in done.values() if r.get("halal"))
                print(f"  [{n:,}/{len(syms):,}] halal so far: {h:,} "
                      f"(eta {eta:.0f} min)", flush=True)
    UNI_F.write_text(json.dumps(done))

    halal = sorted(s for s, r in done.items() if r.get("halal"))
    needs = sorted(s for s, r in done.items()
                   if not r.get("halal")
                   and "NO FUNDAMENTALS DATA" in (r.get("fail_reason") or ""))
    LIST_F.write_text(json.dumps(
        {"updated": time.strftime("%Y-%m-%d"), "n": len(halal),
         "symbols": halal}))
    NEED_F.write_text(json.dumps(needs))
    by_src = {}
    for r in done.values():
        if r.get("halal"):
            by_src[r.get("source")] = by_src.get(r.get("source"), 0) + 1
    print(f"\nHALAL: {len(halal):,} of {len(done):,} "
          f"({100*len(halal)/max(len(done),1):.1f}%)  by source: {by_src}")
    print(f"UNVERIFIABLE (need RH mcap backfill): {len(needs):,} "
          f"-> data/needs_mcap.json")
    print(f"scanner list -> {LIST_F.name}", flush=True)


if __name__ == "__main__":
    main()
