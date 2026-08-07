"""W-pool discovery: same rules as gappers2, WITHOUT the volume filter.

WHY (2026-08-07, user): "we want to test multiple strategies, to see if
ignoring the volume somehow increase the profit. or when checking the
volume in a specific way different than 5x". And: "when paper trading,
you do not [know] the volume of the whole day!" -- the old pool's
"full-day volume >= 5x the 50-day average" filter is not knowable at
decision time, so live paper trading can never reproduce it. TWLO
(2026-08-06, +$1,266.58) reached the live session at a true 2.05x --
a name this filter would have hidden.

Identical to penny_ax20_discover.py in every rule EXCEPT:
  * NO rvol filter (that is the point);
  * rvol still RECORDED, both 50d (schema parity) and 30d (the live
    scanner's lookback), so W-experiments can re-gate on either;
  * zero API calls -- reads the local data/massive/gd cache only.

Output: data/massive/gappers_novol_{label}.json, same schema as
gappers2 plus "rvol30". The old pool is a strict subset of this one
(same rules, one filter dropped); the sanity check asserts that.

The 1-minute bars for NEW names still have to be backfilled (Massive,
5 req/min) before W-experiments can simulate them.
"""

import gzip
import importlib.util
import json
from datetime import date as ddate, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "ax20d", ROOT / "plan" / "penny_ax20_discover.py")
ax20d = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ax20d)          # reuse clean_ticker + gd_cached

MCACHE = ROOT / "data" / "massive"
MIN_GAIN = 10.0


def discover(label, year_start, year_end):
    out_f = MCACHE / f"gappers_novol_{label}.json"
    if out_f.exists():
        print(f"{label}: exists, skipping", flush=True)
        return
    warmup = (ddate.fromisoformat(year_start) - timedelta(days=78)).isoformat()
    hist = {}
    found = []
    d = ddate.fromisoformat(warmup)
    end = ddate.fromisoformat(year_end)
    while d <= end:
        if d.weekday() < 5:
            for r in ax20d.gd_cached(d.isoformat()):
                sym = r.get("T") or ""
                if not ax20d.clean_ticker(sym):
                    continue
                c = r.get("c") or 0
                if c <= 0.2:
                    continue
                h = hist.setdefault(sym, [])
                hi, lo, vol = r.get("h") or 0, r.get("l") or 0, r.get("v") or 0
                if len(h) >= 10 and d.isoformat() >= year_start:
                    prev = h[-1][3]
                    if prev > 0 and (hi / prev - 1) * 100 >= MIN_GAIN \
                            and hi >= 2.0:
                        base = h[-50:]
                        av = sum(x[4] for x in base) / len(base)
                        b30 = h[-30:]
                        av30 = sum(x[4] for x in b30) / len(b30)
                        if av > 0:            # need a baseline to RECORD rvol
                            found.append({
                                "symbol": sym, "date": d.isoformat(),
                                "gain_pct": round((hi / prev - 1) * 100, 1),
                                "prev_close": round(float(prev), 4),
                                "rvol": round(float(vol / av), 1),
                                "rvol30": round(float(vol / av30), 1)
                                if av30 > 0 else 0.0,
                                "band": bool(lo <= 16.0),
                                "open": round(float(r.get("o") or 0), 4),
                                "high": round(float(hi), 4),
                                "close": round(float(c), 4),
                                "volume": int(vol),
                                "hist_n": len(h)})
                h.append((d.isoformat(), hi, lo, c, vol))
                if len(h) > 60:
                    del h[0]
        d += timedelta(days=1)
    out_f.write_text(json.dumps(found))
    print(f"{label}: {len(found):,} hits -> {out_f.name}", flush=True)


def sanity(label):
    """The old pool must be a subset of the new one (same rules minus
    one filter). Loud failure otherwise -- it would mean the re-scan
    does not reproduce the original and nothing downstream is valid."""
    old = json.loads((MCACHE / f"gappers2_{label}.json").read_text())
    new = json.loads((MCACHE / f"gappers_novol_{label}.json").read_text())
    nk = {(c["symbol"], c["date"]) for c in new}
    missing = [(c["symbol"], c["date"]) for c in old
               if (c["symbol"], c["date"]) not in nk]
    low = sum(1 for c in new if c["rvol"] < 5)
    print(f"{label}: old {len(old):,} -> novol {len(new):,} "
          f"({low:,} have rvol<5, the names the old scan never showed)")
    if missing:
        print(f"ERROR: {len(missing)} old-pool days MISSING from the "
              f"re-scan -- first: {missing[:5]}. The re-scan does not "
              f"reproduce discovery; do not use it.")
    return not missing


if __name__ == "__main__":
    ok = True
    for label, ys, ye in (("year", "2025-08-01", "2026-08-01"),
                          ("y2025", "2024-10-22", "2025-08-01")):
        discover(label, ys, ye)
        ok = sanity(label) and ok
    if not ok:
        raise SystemExit(1)
