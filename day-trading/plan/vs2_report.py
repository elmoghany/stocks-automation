"""VS2 RESULT TABLE (2026-09-16).

Reads the VS2 shard files and prints the pre-registered verdict columns
for every config: total, per year, tickets, $/ticket, $/month, negative
months, maxDD, best day, total ex-best, and -- where the controls have
been run -- the config's percentile against its 30 random replicates on
total and on total ex-best.

  python plan/vs2_report.py               # gapper pool (rotation shards)
  python plan/vs2_report.py --wide        # m1w wide universe
  python plan/vs2_report.py --wide --shards wa,wb

The pass bar (pre-registered): BOTH years positive, >= $7,500/month
averaged over the window, >= the 90th percentile of the 30-replicate
random control on total AND ex-best, inverted/shuffled control fails,
aug2026 sign-consistent.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data/massive"


def load(paths):
    res = {}
    for p in paths:
        if p.exists():
            res.update(json.loads(p.read_text()))
        else:
            print(f"  (missing {p.name})")
    return res


def months_of(row, labels):
    n = 0
    for lab in labels:
        if lab in row and isinstance(row[lab], dict):
            n += row[lab].get("nmonths") or 0
    return n


def agg(row, labels):
    tot = tk = days = negm = nm = exb = 0
    best = 0
    dd = 0
    per_year = {}
    for lab in labels:
        r = row.get(lab)
        if not isinstance(r, dict):
            continue
        tot += r["total"]
        tk += r.get("tickets") or 0
        days += r.get("days") or 0
        negm += r.get("negm") or 0
        nm += r.get("nmonths") or 0
        exb += r.get("total_ex_best") or 0
        best = max(best, r.get("best_day") or 0)
        dd = max(dd, r.get("max_dd") or 0)
        per_year[lab] = r["total"]
    return dict(total=tot, tickets=tk, days=days, negm=negm, nmonths=nm,
                ex_best=exb, best=best, dd=dd, years=per_year)


def pct_rank(value, sample):
    if not sample:
        return None
    return round(100.0 * sum(1 for s in sample if value > s) / len(sample))


def main(wide, shards):
    if wide:
        paths = [D / f"vs2wide_results_{s}.json" for s in shards]
        labels = ["wy1", "wy2"]
    else:
        paths = [D / f"rotation_results_{s}.json" for s in shards]
        labels = ["year", "y2025"]
    res = load(paths)
    ranked = sorted(k for k in res if "#r" not in k
                    and not k.endswith("-I")
                    and not k.endswith("-R")
                    and "-E" not in k)
    print(f"{'config':<12} {'total':>10} {'Y1':>9} {'Y2':>9} {'tkts':>6} "
          f"{'$/tkt':>7} {'$/mo':>8} {'negm':>6} {'maxDD':>9} "
          f"{'best':>8} {'ex_best':>10} {'t/day':>6} {'ctrl%':>6}")
    print("-" * 122)
    for cid in ranked:
        a = agg(res[cid], labels)
        if not a["nmonths"]:
            continue
        ys = list(a["years"].values())
        reps = [agg(res[k], labels) for k in res
                if k.startswith(cid + "#r")]
        ctrl = pct_rank(a["total"], [r["total"] for r in reps]) if reps \
            else None
        rctrl = [k for k in res if k.startswith(cid + "-R#r")]
        if rctrl and not reps:
            reps = [agg(res[k], labels) for k in rctrl]
            ctrl = pct_rank(a["total"], [r["total"] for r in reps])
        print(f"{cid:<12} {a['total']:>+10,.0f} "
              f"{(ys[0] if len(ys) > 0 else 0):>+9,.0f} "
              f"{(ys[1] if len(ys) > 1 else 0):>+9,.0f} "
              f"{a['tickets']:>6} "
              f"{(a['total'] / a['tickets'] if a['tickets'] else 0):>7.0f} "
              f"{a['total'] / a['nmonths']:>8,.0f} "
              f"{a['negm']:>3}/{a['nmonths']:<2} "
              f"{a['dd']:>9,.0f} {a['best']:>+8,.0f} "
              f"{a['ex_best']:>+10,.0f} "
              f"{(a['tickets'] / a['days'] if a['days'] else 0):>6.2f} "
              f"{('' if ctrl is None else str(ctrl)):>6}")
        for suf, tag in (("-I", "inv"), ("-R", "rand")):
            k = cid + suf
            if k in res:
                b = agg(res[k], labels)
                if b["nmonths"]:
                    print(f"  {tag:<9} {b['total']:>+10,.0f} "
                          f"{'':>9} {'':>9} {b['tickets']:>6} "
                          f"{(b['total'] / b['tickets'] if b['tickets'] else 0):>7.0f}")
    print()
    print("PASS BAR: both years positive, >= $7,500/month, >= 90th "
          "percentile of the 30-rep random control on total AND ex_best,"
          "\n          inverted/shuffled control fails, aug2026 "
          "sign-consistent.")


if __name__ == "__main__":
    argv = sys.argv[1:]
    wide = "--wide" in argv
    sh = ["wa", "wb"] if wide else ["vs2_a", "vs2_b"]
    if "--shards" in argv:
        sh = argv[argv.index("--shards") + 1].split(",")
    main(wide, sh)
