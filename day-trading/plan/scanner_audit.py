"""SCANNER AUDIT (user 2026-08-06: "audit the scanner now"): would the
BACKTEST's discovery have produced candidates on the paper days that
the live Robinhood scanner never surfaced?

Backtest discovery (AX20 pipeline): full-market Massive grouped-daily,
clean ticker, prev_close >= $2, day high >= prev_close x 1.10, volume
>= 5x trailing-50-session average (our rvol, >= 50 sessions history),
rank by gain, top 8. Rebuilt here for 2026-08-04/05 (and -06 when the
session's grouped data is final) from the gd cache + fresh fetches.
Diffed against every symbol the live scanner surfaced those days.
"""

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
from shared import massive

GD = ROOT / "data/massive/gd"
WARRANT_SUFFIX = ("W", "U", "R")

SEEN = {  # every symbol the live scanner surfaced, from the day logs
    "2026-08-04": {"AMIX", "NUWE", "XGN", "ATPC", "ACCL", "RACC",
                   "AIQU", "FNG", "KEYG"},
    "2026-08-05": {"GTE", "DBGI", "JLHL", "SHPH", "UPSC", "BEEP",
                   "PCLA", "INLF", "OESX", "JDZG", "ZYBT", "SAIH"},
    "2026-08-06": {"WYHG", "PAVS", "MSIX", "CLRO", "SPHL", "AZI",
                   "HNST"},
}


def clean_ticker(sym):
    if not sym or not sym.isalpha() or not sym.isupper():
        return False
    if len(sym) == 5 and sym.endswith(WARRANT_SUFFIX):
        return False
    return len(sym) <= 5


def gd(date):
    f = GD / f"{date}.json.gz"
    if f.exists():
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    try:
        rows = massive.grouped_daily(date)
    except Exception as e:
        print(f"  !! gd {date}: {e}", flush=True)
        return None
    slim = [{k: r.get(k) for k in ("T", "o", "h", "l", "c", "v")}
            for r in (rows or [])]
    if slim:
        with gzip.open(f, "wt", encoding="utf-8") as fh:
            json.dump(slim, fh)
    return slim or None


def main():
    # session list: cached dates + the August additions
    dates = sorted(p.name[:10] for p in GD.glob("*.json.gz"))
    for d in ("2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06"):
        if d not in dates:
            if gd(d):
                dates.append(d)
    dates = sorted(set(dates))
    # rolling 50-session volume history
    hist = defaultdict(list)          # sym -> [(date, v, c)]
    audit_days = [d for d in ("2026-08-04", "2026-08-05", "2026-08-06")
                  if d in dates]
    pools = {}
    for k, d in enumerate(dates):
        rows = gd(d)
        if rows is None:
            continue
        if d in audit_days:
            prev_i = k - 1
            prev_rows = gd(dates[prev_i])
            prev_close = {r["T"]: r["c"] for r in prev_rows
                          if r.get("T") and r.get("c")}
            cands = []
            for r in rows:
                sym = r.get("T")
                if not clean_ticker(sym):
                    continue
                pc = prev_close.get(sym)
                h_, v = r.get("h"), r.get("v")
                if not pc or pc < 2 or not h_ or not v:
                    continue
                gain = (h_ / pc - 1) * 100
                if gain < 10:
                    continue
                hs = hist.get(sym, [])
                if len(hs) < 50:
                    continue
                avg = sum(x[1] for x in hs[-50:]) / 50
                if avg <= 0 or v < 5 * avg:
                    continue
                cands.append(dict(sym=sym, gain=round(gain, 1),
                                  rvol=round(v / avg, 1),
                                  pc=pc, high=h_, close=r.get("c"),
                                  vol=int(v)))
            cands.sort(key=lambda c: -c["gain"])
            pools[d] = cands
        for r in rows:
            sym = r.get("T")
            if sym and r.get("v"):
                hist[sym].append((d, r["v"], r.get("c")))
    for d in audit_days:
        pool = pools.get(d, [])
        seen = SEEN.get(d, set())
        print(f"\n=== {d}: backtest pool = {len(pool)} candidates "
              f"(top 8 tradeable) ===")
        for i, c in enumerate(pool[:12]):
            mark = "SEEN" if c["sym"] in seen else ">>> MISSED BY SCANNER"
            print(f"  #{i}: {c['sym']:<6} gain {c['gain']:>6.1f}% "
                  f"rvol {c['rvol']:>6.1f} pc {c['pc']:>8.2f} "
                  f"vol {c['vol']:>12,}  {mark}")
        missed = [c["sym"] for c in pool[:8] if c["sym"] not in seen]
        print(f"  top-8 missed by the live scanner: "
              f"{missed if missed else 'NONE'}")
    (ROOT / "data/massive/scanner_audit.json").write_text(
        json.dumps(pools))


if __name__ == "__main__":
    main()
