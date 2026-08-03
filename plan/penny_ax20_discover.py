"""AX20 discovery: widened universe re-scan (both year labels).

Changes vs stage1_discover (plan/penny_year_backtest.py):
  - NO $75 close cap (user approved any price >= $2)
  - universe.json membership check DROPPED (it embeds the old cap);
    replaced with ticker hygiene: pure uppercase alpha, no 5-letter
    warrant/unit/rights suffixes (ETFs/funds die later at halal gate)
  - qualifies at hist >= 10 sessions and RECORDS hist_n so consumers
    can filter >= 50 (baseline parity) or relax to >= 10 (AX20i)
    without re-scanning; rvol uses up to trailing 50 sessions
  - raw grouped-daily responses cached to data/massive/gd/{date}.json.gz
    so every future filter change costs zero API calls
  - extra fields per record: open/high/close/volume/hist_n

Output: data/massive/gappers2_{label}.json (originals never touched).
Parity note: symbols whose close crossed $75 accumulate history on
those days here but not in the old scan, so a handful of rvol values
can differ for crossers -- the sanity diff tolerates only those.
"""

import gzip
import json
import sys
from datetime import date as ddate, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from trading import massive

MCACHE = ROOT / "data" / "massive"
GD = MCACHE / "gd"
GD.mkdir(exist_ok=True)

MIN_GAIN = 10.0
MIN_RVOL = 5.0
WARRANT_SUFFIX = ("W", "U", "R")


def clean_ticker(sym):
    if not sym or not sym.isalpha() or not sym.isupper():
        return False           # dots, dashes, lowercase (preferred shares)
    if len(sym) == 5 and sym.endswith(WARRANT_SUFFIX):
        return False           # warrants / units / rights
    return len(sym) <= 5


def gd_cached(date):
    f = GD / f"{date}.json.gz"
    if f.exists():
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    try:
        rows = massive.grouped_daily(date)
    except Exception as e:
        print(f"  !! gd {date}: {e}", flush=True)
        rows = []
    slim = [{k: r.get(k) for k in ("T", "o", "h", "l", "c", "v")}
            for r in (rows or [])]
    with gzip.open(f, "wt", encoding="utf-8") as fh:
        json.dump(slim, fh)
    return slim


def discover(label, year_start, year_end):
    out_f = MCACHE / f"gappers2_{label}.json"
    if out_f.exists():
        print(f"{label}: gappers2 exists, skipping", flush=True)
        return
    warmup = (ddate.fromisoformat(year_start) - timedelta(days=78)).isoformat()
    hist = {}    # sym -> list of (date, high, low, close, volume)
    found = []
    d = ddate.fromisoformat(warmup)
    end = ddate.fromisoformat(year_end)
    n_days = 0
    while d <= end:
        if d.weekday() < 5:
            rows = gd_cached(d.isoformat())
            n_days += 1
            if n_days % 20 == 0:
                print(f"  {label} {d} ({n_days} sessions, "
                      f"{len(found)} hits)", flush=True)
            for r in rows:
                sym = r.get("T") or ""
                if not clean_ticker(sym):
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
                        if av > 0 and vol >= MIN_RVOL * av:
                            found.append({
                                "symbol": sym, "date": d.isoformat(),
                                "gain_pct": round((hi / prev - 1) * 100, 1),
                                "prev_close": round(float(prev), 4),
                                "rvol": round(float(vol / av), 1),
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
    print(f"{label}: {len(found)} hits -> {out_f.name}", flush=True)


if __name__ == "__main__":
    for label, ys, ye in (("year", "2025-08-01", "2026-08-01"),
                          ("y2025", "2024-10-22", "2025-08-01")):
        discover(label, ys, ye)
