"""RL-SERIES v2 (2026-09-16): write data/massive/MANIFEST_m1w.json.

Describes what is in the wide minute cache and, critically, the CAUSAL
MEMBERSHIP RULE that decided what is in it -- so a later reader can tell
whether a symbol-day is there because of something knowable before the
day opened (it is) or because of what the day did (it is not).
"""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
M1W = ROOT / "data" / "massive" / "m1w"
UNI = HERE / "out" / "universe"
OUT = ROOT / "data" / "massive" / "MANIFEST_m1w.json"


def main():
    sys.path.insert(0, str(HERE))
    import universe as UV
    files = sorted(UNI.glob("*.json"))
    by_date, syms = {}, set()
    for f in files:
        rows = json.loads(f.read_text())
        by_date[f.stem] = len(rows)
        syms.update(r["symbol"] for r in rows)
    csvs = list(M1W.glob("*.csv"))
    nb = sum(p.stat().st_size for p in csvs)
    empty = sum(1 for p in csvs if p.stat().st_size <= 8)
    per_month = defaultdict(list)
    for d, n in by_date.items():
        per_month[d[:7]].append(n)
    stats = json.loads((HERE / "out" / "universe_stats.json").read_text())
    errs = json.loads((HERE / "out" / "m1w_errors.json").read_text())
    man = {
        "written": "2026-09-16",
        "written_by": "plan/rl2/manifest.py (RL-SERIES v2)",
        "what": ("1-minute bars 04:00-20:00 ET for the CAUSAL WIDE INTRADAY "
                 "UNIVERSE of RL-SERIES v2. Format is byte-compatible with "
                 "data/massive/m1: UTC begins_at index column, columns "
                 "Open,High,Low,Close,Volume; a day with no prints would be "
                 "the 5-byte EMPTY sentinel."),
        "membership_rule": {
            "summary": ("On trading date D a symbol is eligible iff it was "
                        "halal-PASS point-in-time at D, its median dollar "
                        "volume over the PRIOR 60 trading days was >= $2M and "
                        "its median close >= $3, and it printed a bar on D. "
                        "NOTHING about day D's own outcome enters membership "
                        "-- this cache is deliberately NOT the +10% gapper "
                        "pool, whose membership is conditioned on the day's "
                        "own regular-session high (NOTES 'MX-SERIES "
                        "RETRACTION #2')."),
            "halal": ("plan/penny_ax11b_massive.halal_pt under "
                      "HALAL_STRICT=1 PT_FILED=1, network removed; shares "
                      "as-of a date <= D from plan/rl2/cache/shares (monthly "
                      "anchor grid, de-campaigned) then data/pt_shares; "
                      "quarterly statements selected by FILED date <= D"),
            "liquidity": stats["rule"],
            "prev_close": "grouped-daily close of the previous TRADING day",
            "builder": "plan/rl2/universe.py --stage screen|halal",
        },
        "coverage": {
            "dates": len(by_date),
            "first_date": min(by_date), "last_date": max(by_date),
            "symbol_days": sum(by_date.values()),
            "distinct_symbols": len(syms),
            "files": len(csvs), "bytes": nb,
            "empty_sentinels": empty,
            "permanent_failures": len(errs),
            "per_day_min": min(by_date.values()),
            "per_day_max": max(by_date.values()),
            "per_day_mean": round(sum(by_date.values()) / len(by_date), 1),
            "per_month_mean": {m: round(sum(v) / len(v), 1)
                               for m, v in sorted(per_month.items())},
        },
        "caveats": [
            ("Universe SIZE drifts up over the sample (44 names/day in "
             "2024-10 to 87 in 2026-07) because data/pt_halal quarterly "
             "coverage grew as earlier campaigns ran. Membership at D uses "
             "only <= D information, but WHICH names have a cached statement "
             "file at all is uneven across time."),
            ("industry_clean and sector_clean read PRESENT-DAY sector / "
             "industry / SIC labels. A symbol with no label is REFUSED, so "
             "label coverage (728 of 4,575 liquid names/day) bounds the "
             "universe."),
            ("Grouped-daily closes are split-ADJUSTED to the present while "
             "the point-in-time share count is not, so mcap = shares x "
             "prev_close is wrong across a split. Same convention as every "
             "engine backtest in this repo."),
        ],
    }
    OUT.write_text(json.dumps(man, indent=1))
    print(json.dumps(man["coverage"], indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
