"""LEGACY-5 part 3: threshold sensitivity + tail-robust $/month for the
'skip fresh crossers' shadow rule; random-control on GROSS per ticket."""
import json, sys
from pathlib import Path
import numpy as np

ROOT = Path(r"C:\cornell\stocks-automation\day-trading")
sys.path.insert(0, str(ROOT / "plan"))
from lm5_seq import annotate  # noqa: E402
from lm5_seq2 import attach  # noqa: E402


def mo(xs, nd, c=15, drop_top=0):
    p = np.sort(np.array([x["p"] for x in xs]))
    if drop_top:
        p = p[:-drop_top]
    return (p - 2 * c).sum() / nd * 21, p.mean() if len(p) else np.nan


for fname, key in (("plan/pa_out/cp_r4_legs.json", "R4"), ("plan/crs_cp_r5_legs.json", "R5")):
    d = json.loads((ROOT / fname).read_text())
    nd = d["ndays"]
    m = annotate(d["legs"][key])
    rnd = {k: annotate(v) for k, v in d["legs"].items() if k.startswith("RND")}
    attach(m + [x for v in rnd.values() for x in v])
    yrs = sorted({x["date"][:4] for x in m})
    print(f"\n## {key}: skip legs with since_cross <= T (shadow)\n")
    print("| T (min) | n | gross $/10k | net@15 $/mo | ex-top-5 net@15 $/mo | ex-top-10 | " + " | ".join(f"{y} net@15 $/10k" for y in yrs)
          + " | RND gross $/10k rule - all (mean, seeds>0) | dropped-leg gross $/10k |")
    print("|---:|---:|---:|---:|---:|---:|" + "---:|" * len(yrs) + "---|---:|")
    for T in (-1, 0, 5, 10, 15, 20, 30, 45, 60):
        f = lambda x: x.get("since", 999) > T
        xs = [x for x in m if f(x)]
        dr = [x for x in m if not f(x)]
        a, g = mo(xs, nd)
        b, _ = mo(xs, nd, drop_top=5)
        b10, _ = mo(xs, nd, drop_top=10)
        ys = [np.mean([x["p"] - 30 for x in xs if x["date"][:4] == y] or [np.nan]) for y in yrs]
        diffs = []
        for v in rnd.values():
            k = [x["p"] for x in v if f(x)]
            diffs.append((np.mean(k) if k else np.nan) - np.mean([x["p"] for x in v]))
        diffs = np.array(diffs)
        print(f"| {T} | {len(xs)} | {g:+.1f} | {a:+,.0f} | {b:+,.0f} | {b10:+,.0f} | " + " | ".join(f"{y:+.0f}" for y in ys)
              + f" | {np.nanmean(diffs):+.1f} ({(diffs>0).sum()}/{len(diffs)}) | {np.mean([x['p'] for x in dr]) if dr else float('nan'):+.1f} |")
    # tail check of ALL
    a, g = mo(m, nd); b, _ = mo(m, nd, drop_top=5)
    print(f"\n{key} ALL: net@15 {a:+,.0f}/mo, ex-top-5 {b:+,.0f}/mo")
    # top-5 legs of R4
    top = sorted(m, key=lambda x: -x["p"])[:5]
    print("top-5 legs:", [(x["date"], x["sym"], x["ord"], x.get("since"), round(x["p"])) for x in top])
