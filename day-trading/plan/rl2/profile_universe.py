"""RL-SERIES v2 (2026-09-16): the universe measured with NO policy at all.

Buy one ticket at every tradeable (name, decision minute) and hold H
minutes, same costs, same fills, same size cap. Split by session so the
50 bps extended haircut is visible rather than averaged away. This is the
number every approach has to beat: if the eligible set has negative net
expectancy at every horizon, a long-only policy must either abstain or
find that much selection alpha just to break even.

Also reports the per-day universe size and the turnover of its membership,
because a universe whose size drifts is a universe whose results drift.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import features as FT                                         # noqa: E402

FEAT = HERE / "out" / "feat"
OUT = HERE / "out"

SPLITS = [("train", "2024-10-22", "2025-06-01"),
          ("val", "2025-06-01", "2025-08-01"),
          ("test", "2025-08-01", "2026-08-07")]
TICKET = 15000.0


def main():
    files = sorted(FEAT.glob("*.npz"))
    isext = (FT.STEPS < FT.RTH_LO) | (FT.STEPS >= FT.RTH_HI)
    acc = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
    sizes, members = {}, defaultdict(set)
    for p in files:
        d = p.stem
        sp = next((s for s, a, b in SPLITS if a <= d < b), None)
        z = np.load(p, allow_pickle=False)
        prn, tgt, ok = z["printed"], z["tgt"], z["tgt_ok"]
        sizes[d] = int(len(z["syms"]))
        for s in z["syms"]:
            members[d[:7]].add(str(s))
        if sp is None:
            continue
        for hi, H in enumerate(FT.HORIZONS):
            for tag, mask in (("all", np.ones_like(isext)),
                              ("rth", ~isext), ("ext", isext)):
                m = prn & ok[:, :, hi] & mask[:, None]
                if m.any():
                    a = acc[sp][(H, tag)]
                    a[0] += float(tgt[:, :, hi][m].sum()) * TICKET
                    a[1] += int(m.sum())
    tbl = {}
    for sp in acc:
        tbl[sp] = {f"{H}_{tag}": {"per_ticket": round(v[0] / v[1], 2),
                                  "n": v[1]}
                   for (H, tag), v in acc[sp].items()}
    months = sorted(members)
    churn = []
    for i in range(1, len(months)):
        a, b = members[months[i - 1]], members[months[i]]
        churn.append({"month": months[i], "n": len(b),
                      "new": len(b - a), "gone": len(a - b)})
    res = {"per_ticket_by_horizon_and_session": tbl,
           "universe_size": {"min": min(sizes.values()),
                             "max": max(sizes.values()),
                             "mean": round(float(np.mean(list(sizes.values()))), 1),
                             "by_month": {m: round(float(np.mean(
                                 [v for k, v in sizes.items() if k[:7] == m])), 1)
                                 for m in months}},
           "membership_churn": churn,
           "distinct_symbols": len(set().union(*members.values()))}
    (OUT / "profile_universe.json").write_text(json.dumps(res, indent=1))
    for sp in ("train", "val", "test"):
        if sp not in tbl:
            continue
        print(f"\n{sp}:")
        for H in FT.HORIZONS:
            r = [tbl[sp].get(f"{H}_{t}") for t in ("all", "rth", "ext")]
            print(f"  H={H:<8} all {r[0]['per_ticket']:>9.2f} "
                  f"({r[0]['n']:>7,})   rth {r[1]['per_ticket']:>9.2f} "
                  f"({r[1]['n']:>7,})   ext {r[2]['per_ticket']:>9.2f} "
                  f"({r[2]['n']:>7,})")
    print("\nuniverse:", json.dumps(res["universe_size"]["by_month"]))
    print("distinct symbols:", res["distinct_symbols"])


if __name__ == "__main__":
    main()
