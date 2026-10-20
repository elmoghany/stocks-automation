"""PAPER-VS-BT: per-day R4 candidate lists.
  gd pool  = Polygon grouped-daily: high >= 1.10 x prev close, high >= $2,
             clean ticker (the cp_panel pool rule; superset of the R4
             universe, which needs an RTH close >= 1.10 x pc and last >= $2)
  scan     = every name the live "P3 R4 gapper coil" scan returned that day
             (data/paper/r4/snaps_{D}.jsonl)
Writes data/pvb/r4_universe.json {date: {sym: {pc, src}}}. 2026-10-19 has no
grouped-daily yet (403 for the current day): scan names only, pc = 10-16
gd close.
"""
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GD = ROOT / "data/massive/gd"
DAYS = ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09",
        "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16",
        "2026-10-19"]
PREV = {"2026-10-05": "2026-10-02"}


def ld(d):
    f = GD / f"{d}.json.gz"
    if not f.exists():
        return None
    return {r["T"]: r for r in json.load(gzip.open(f, "rt"))}


def clean(s):
    return s.isalpha() and s.isupper() and len(s) <= 5 and not (
        len(s) == 5 and s[-1] in "WUR")


def snaps(d):
    f = ROOT / f"data/paper/r4/snaps_{d}.jsonl"
    out = {}
    if f.exists():
        for x in f.read_text().splitlines():
            if x.strip():
                for s, r in json.loads(x)["rows"].items():
                    out.setdefault(s, r.get("pc"))
    return out


def main():
    res = {}
    allg = sorted(p.name[:10] for p in GD.glob("*.json.gz"))
    for d in DAYS:
        prevd = max(x for x in allg if x < d)
        prev, cur = ld(prevd), ld(d)
        u = {}
        if cur:
            for s, r in cur.items():
                p = prev.get(s)
                if p and clean(s) and r["h"] >= 1.10 * p["c"] and r["h"] >= 2:
                    u[s] = dict(pc=p["c"], src="gd")
        for s, pc in snaps(d).items():
            if s in u:
                u[s]["src"] = "gd+scan"
            else:
                pcg = prev.get(s, {}).get("c") if prev else None
                u[s] = dict(pc=pcg or pc, pc_scan=pc, src="scan")
        res[d] = u
        n = {k: sum(1 for v in u.values() if v["src"] == k)
             for k in ("gd", "gd+scan", "scan")}
        print(d, len(u), n)
    (ROOT / "data/pvb/r4_universe.json").write_text(json.dumps(res))


if __name__ == "__main__":
    main()
