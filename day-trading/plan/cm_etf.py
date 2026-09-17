"""CLOSE-MOMENTUM (2026-09-16): 1-minute bars for the halal ETFs.

The published market-intraday-momentum effect (Gao, Han, Li, Zhou 2018,
JFE) is an INDEX-level effect: the first half-hour return and the
second-to-last half-hour return of the market predict the last half-hour
return. The cleanest halal-compatible instruments for it are the Sharia
index ETFs, which the wide causal universe deliberately excludes (it is a
common-stock universe built from a halal screen on issuers).

This module fetches their minute bars into a SEPARATE cache,
data/massive/m1etf, so the m1w manifest's coverage accounting for the
RL-SERIES v2 universe stays exactly what it says it is.

  SPUS  SP Funds S&P 500 Sharia                ~$18.3M/day median $vol
  HLAL  Wahed FTSE USA Shariah                 ~$3.6M/day
  SPSK  SP Funds Dow Jones Global Sukuk        ~$2.7M/day   (bond-like)
  SPRE  SP Funds S&P Global REIT Sharia        ~$1.1M/day
  UMMA  Wahed Dow Jones Islamic World ex-US    ~$0.9M/day
  SPWO  SP Funds S&P World ex-US Sharia        ~$0.44M/day
  SPY   NOT halal -- fetched only as the replication reference, so a null
        on SPUS/HLAL can be told apart from "the published effect is gone
        in this window". SPY is never traded in any reported config.

Dates are exactly the 448 study dates of plan/rl2 (2024-10-22..2026-08-06,
holidays already dropped by rl2.universe.gd_dates).

Usage:  python plan/cm_etf.py [--workers 16] [--limit N]
"""
import os
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(HERE / "rl2"))
from shared import massive                                    # noqa: E402

massive._TH_INTERVAL = float(os.environ.get("MASSIVE_TH_INTERVAL", "0.0"))

M1E = ROOT / "data" / "massive" / "m1etf"
SYMS = ["SPUS", "HLAL", "SPSK", "SPRE", "UMMA", "SPWO", "SPY"]
RETRIES = 3

_lock = threading.Lock()
_stats = {"got": 0, "empty": 0, "fail": 0}


def study_dates():
    import universe as UV
    return [d for d in UV.gd_dates() if UV.START <= d <= UV.END]


def fetch_one(sym, date):
    f = M1E / f"{sym}_{date}.csv"
    for attempt in range(RETRIES):
        try:
            df = massive.minute_bars(sym, date)
            if df is None or df.empty:
                f.write_text("EMPTY")
                return "empty"
            out = df.reset_index()
            out["begins_at"] = out["begins_at"].dt.tz_convert("UTC")
            tmp = f.parent / f"{f.name}.{os.getpid()}.{threading.get_ident()}.part"
            out.to_csv(tmp, index=False)
            os.replace(tmp, f)
            return "got"
        except Exception as e:
            if getattr(e, "code", None) in (401, 403):
                break
            time.sleep(2 * (attempt + 1))
    return "fail"


def main():
    workers = 16
    limit = None
    if "--workers" in sys.argv:
        workers = int(sys.argv[sys.argv.index("--workers") + 1])
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    M1E.mkdir(parents=True, exist_ok=True)
    for p in M1E.glob("*.part"):
        p.unlink()
    dates = study_dates()
    todo = [(s, d) for d in dates for s in SYMS
            if not ((M1E / f"{s}_{d}.csv").exists()
                    and (M1E / f"{s}_{d}.csv").stat().st_size > 0)]
    print(f"etf cache: {len(SYMS)} symbols x {len(dates)} dates = "
          f"{len(SYMS)*len(dates):,}; to fetch {len(todo):,}", flush=True)
    if limit:
        todo = todo[:limit]
    from concurrent.futures import ThreadPoolExecutor, as_completed
    t0 = time.monotonic()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fetch_one, s, d) for s, d in todo]
        for fu in as_completed(futs):
            r = fu.result()
            with _lock:
                _stats[r] += 1
                done += 1
                snap = dict(_stats)
            if done % 250 == 0 or done == len(todo):
                el = time.monotonic() - t0
                rate = done / el if el else 0
                print(f"  [{done:,}/{len(todo):,}] {snap} {rate:.1f}/s "
                      f"eta {(len(todo)-done)/rate/60 if rate else 0:.1f}m",
                      flush=True)
    print(f"DONE {(time.monotonic()-t0)/60:.1f}m {_stats}", flush=True)


if __name__ == "__main__":
    main()
