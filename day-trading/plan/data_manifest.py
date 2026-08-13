"""Data manifest -- make the bundle describe its own coverage.

WHY: zipline's bundles are versioned, immutable and self-describing. Our
data is an ad-hoc pile (gappers_*.json + data/massive/m1/*.csv) with no
manifest, which is why "minute bars exist for only ~17 of ~213 daily
candidates, and that depth was itself chosen by full-day gain" went
unnoticed until it was dug out by hand -- after it had already inflated
the champion's reported edge by 14%.

A coverage bias you can read off a file is a disclosed limitation. The
same bias buried in a fetch script is a future leak.

    python plan/data_manifest.py            # write + print
    python plan/data_manifest.py --check    # non-zero exit if it drifted

Writes data/massive/MANIFEST.json.
"""

import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
M1 = ROOT / "data/massive/m1"
OUT = ROOT / "data/massive/MANIFEST.json"


def build():
    man = {
        "generated_by": "plan/data_manifest.py",
        "purpose": "Self-describing coverage for the backtest bundle. "
                   "Read this BEFORE trusting any headline number.",
        "pools": {},
        "minute_bars": {},
        "known_biases": [],
        "causal_rvol": {},
    }

    bar_files = list(M1.glob("*.csv"))
    by_date = Counter()
    syms = set()
    for f in bar_files:
        stem = f.stem
        if "_" not in stem:
            continue
        sym, date = stem.rsplit("_", 1)
        by_date[date] += 1
        syms.add(sym)
    counts = sorted(by_date.values())
    man["minute_bars"] = {
        "files": len(bar_files),
        "distinct_symbols": len(syms),
        "distinct_dates": len(by_date),
        "bars_per_date_median": st.median(counts) if counts else 0,
        "bars_per_date_min": counts[0] if counts else 0,
        "bars_per_date_max": counts[-1] if counts else 0,
        "total_bytes": sum(f.stat().st_size for f in bar_files),
    }

    for pool_file in sorted((ROOT / "data/massive").glob("gappers*.json")):
        try:
            g = json.loads(pool_file.read_text())
        except Exception as e:
            man["pools"][pool_file.name] = {"ERROR": str(e)}
            continue
        byday = {}
        for c in g:
            if c.get("hist_n", 99) < 50:
                continue
            byday.setdefault(c["date"], []).append(c)
        per_day = sorted(len(v) for v in byday.values())
        covered = []
        for date, cs in byday.items():
            have = sum(1 for c in cs
                       if (M1 / f"{c['symbol']}_{date}.csv").exists())
            covered.append((have, len(cs)))
        tot_have = sum(h for h, _ in covered)
        tot_all = sum(n for _, n in covered)
        man["pools"][pool_file.name] = {
            "rows": len(g),
            "dates": len(byday),
            "candidates_per_day_median": (st.median(per_day)
                                          if per_day else 0),
            "candidates_per_day_max": per_day[-1] if per_day else 0,
            "candidates_with_bars_per_day_median": (
                st.median([h for h, _ in covered]) if covered else 0),
            "bar_coverage_pct": round(100 * tot_have / tot_all, 2)
            if tot_all else 0,
        }

    cr = ROOT / "data/massive/causal_rvol.json"
    if cr.exists():
        try:
            d = json.loads(cr.read_text())
            man["causal_rvol"] = {
                "entries": len(d),
                "note": "Built only for previously-selected names, so it "
                        "inherits the same coverage bias. Filtering on it "
                        "COMPOUNDS the bias -- do not use it as a gate "
                        "without saying so.",
            }
        except Exception as e:
            man["causal_rvol"] = {"ERROR": str(e)}

    man["known_biases"] = [
        {
            "id": "bar-coverage-by-full-day-gain",
            "severity": "OPEN -- bounds every backtest number we publish",
            "what": "Minute bars were only ever FETCHED to full-day-gain "
                    "depth (~17 of ~213 candidates/day). The universe a "
                    "simulation can choose from is therefore selected "
                    "with hindsight.",
            "impact": "C37 on a causal pool is $665,667; the same config "
                      "on the old hindsight-cut pool read $774,534. The "
                      "remaining coverage bias means $665,667 is an "
                      "UPPER BOUND, not a point estimate.",
            "fix": "Fetch minute bars for the full candidate set (~92k "
                   "symbol-days, ~3 GB) and rebuild. Needs an unlimited "
                   "call plan; the free tier's 5 req/min makes it "
                   "impossible.",
        },
        {
            "id": "pool-cut-by-day-high-gain",
            "severity": "FIXED 2026-08-13",
            "what": "day_candidates cut the pool with sorted(-gain_pct)"
                    "[:16] where gain_pct is the DAY-HIGH gain.",
            "impact": "-$108,867 (14%) of the champion's reported edge.",
            "fix": "Causal pool is now the default; biased_pool=True "
                   "reproduces the old behaviour for comparison only.",
        },
        {
            "id": "no-l2-history",
            "severity": "OPEN -- blocks a live rule",
            "what": "No historical order-book data, so the live 0.5% "
                    "spread veto cannot be replayed exactly; the "
                    "V-series used median bar range as a proxy.",
            "impact": "We can state the optimum as a veto RATE "
                      "(~50-65% of would-be entries) but not as an "
                      "implementable spread threshold.",
            "fix": "An MBP-10 style historical book feed.",
        },
    ]
    return man


def main():
    man = build()
    check = "--check" in sys.argv
    if check and OUT.exists():
        old = json.loads(OUT.read_text())
        drift = {k: (old.get(k), man.get(k))
                 for k in ("pools", "minute_bars")
                 if old.get(k) != man.get(k)}
        if drift:
            print("MANIFEST DRIFT -- the bundle changed since the last "
                  "write. Re-read the biases before trusting results.")
            for k in drift:
                print(f"  section changed: {k}")
            OUT.write_text(json.dumps(man, indent=1))
            sys.exit(1)
        print("manifest unchanged")
        return
    OUT.write_text(json.dumps(man, indent=1))
    mb = man["minute_bars"]
    print(f"MANIFEST -> {OUT}")
    print(f"  minute bars: {mb['files']:,} files, {mb['distinct_symbols']:,} "
          f"symbols, {mb['distinct_dates']:,} dates, "
          f"{mb['total_bytes']/1e6:.0f} MB")
    for name, p in man["pools"].items():
        if "ERROR" in p:
            print(f"  {name}: ERROR {p['ERROR']}")
            continue
        print(f"  {name}: {p['dates']} dates, median "
              f"{p['candidates_per_day_median']:.0f} candidates/day, "
              f"median {p['candidates_with_bars_per_day_median']:.0f} with "
              f"bars -> {p['bar_coverage_pct']}% coverage")
    print(f"  known biases: {len(man['known_biases'])} "
          f"({sum(1 for b in man['known_biases'] if b['severity'].startswith('OPEN'))} OPEN)")


if __name__ == "__main__":
    main()
