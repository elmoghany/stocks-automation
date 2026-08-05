"""AX20 backfill: fetch 1-min bars + warm point-in-time halal caches for
the widened gappers2 candidate set. Per day: top-12 by gain_pct PLUS any
>$75 candidate outside the top-12 (capped at +8/day). Resumable --
skips existing m1 files (EMPTY sentinel on no-data) and cached halal
lookups. Run after penny_ax20_discover.py.
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
from shared import massive

M1 = ROOT / "data" / "massive" / "m1"
TOP = 12
BIG_EXTRA = 8

_spec = importlib.util.spec_from_file_location(
    "axb", ROOT / "plan" / "penny_ax11b_massive.py")
axb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(axb)


def fetch_m1(sym, date):
    f = M1 / f"{sym}_{date}.csv"
    if f.exists():
        return False
    df = massive.minute_bars(sym, date)
    if df is None or df.empty:
        f.write_text("EMPTY")
        return True
    out = df.reset_index()
    out["begins_at"] = out["begins_at"].dt.tz_convert("UTC")
    out.to_csv(f, index=False)
    return True


def wanted(label):
    gap = json.loads(
        (ROOT / f"data/massive/gappers2_{label}.json").read_text())
    by_day = {}
    for c in gap:
        by_day.setdefault(c["date"], []).append(c)
    out = []
    for date, cs in sorted(by_day.items()):
        ranked = sorted(cs, key=lambda x: -x["gain_pct"])
        keep = ranked[:TOP]
        big = [c for c in ranked[TOP:]
               if c["prev_close"] > 75 or c["close"] > 75][:BIG_EXTRA]
        out.extend(keep + big)
    return out


def main():
    from concurrent.futures import ThreadPoolExecutor
    for label in ("year", "y2025"):
        cands = wanted(label)
        print(f"{label}: {len(cands)} candidate-days to ensure", flush=True)
        fetched = 0
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(fetch_m1, c["symbol"], c["date"])
                    for c in cands]
            for n, fu in enumerate(futs):
                if fu.result():
                    fetched += 1
                if n % 200 == 0:
                    print(f"  {label} m1 {n}/{len(cands)} "
                          f"({fetched} new)", flush=True)
        print(f"{label}: m1 done, {fetched} new fetches", flush=True)
        ok = bad = 0
        for n, c in enumerate(cands):
            if axb.halal_pt(c["symbol"], c["date"], c["prev_close"]):
                ok += 1
            else:
                bad += 1
            if n % 300 == 0:
                print(f"  {label} halal {n}/{len(cands)}", flush=True)
        print(f"{label}: halal warm done ({ok} pass / {bad} fail)",
              flush=True)


if __name__ == "__main__":
    main()
