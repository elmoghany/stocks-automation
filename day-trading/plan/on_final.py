"""OVERNIGHT research step 4: full report tables for the shortlisted selectors.

For each selector x N: per split (Y1/Y2/OOS/ALL) at 6 and 12 bps/side:
$/night, $/month (loose $100k nightly, strict settled-cash = $50k nightly),
win rate, max drawdown, t, ex-top-5-nights, and percentile vs two 30-seed
controls: random-N from the universe, and VOL-MATCHED random-N (random names
from the top vol20 quintile -- losers are high-vol, so this asks whether the
selector beats its own risk bucket). Also a HALAL-PASS-only line (present-day
data/halal_list.json, 2026-09-17 -- a look-ahead list, labelled as such).
Writes data/research_oct/on_final.csv + picks for the chosen rule.
"""
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from on_lib import OUT, ROOT, SPLITS, by_split, load, nightly, pick_top, split_of  # noqa: E402
from on_port import selectors, zs  # noqa: E402

SHORT = ["rev5_lo", "gap_lo", "vol+tug", "vol+tug+rev5lo", "vol20_hi", "CLS:dret_lo"]


def ctrl(u, n, mask=None, seeds=30):
    out = []
    for s in range(seeds):
        rng = np.random.default_rng(5000 + s)
        idx = pick_top(u, pd.Series(rng.random(len(u)), index=u.index), n, seed=s, mask=mask)
        out.append(nightly(u, idx))
    return out


def pct(r, sims, k):
    sp = split_of(pd.Series(r.index, index=r.index))
    m = (sp == k) if k != "ALL" else (sp != "")
    g = r[m].mean()
    vals = []
    for s in sims:
        ss = split_of(pd.Series(s.index, index=s.index))
        vals.append(s[(ss == k) if k != "ALL" else (ss != "")].mean())
    return float(np.mean([g > v for v in vals]))


def main():
    u = load()
    hal = set(json.loads((ROOT / "data/halal_list.json").read_text())["symbols"])
    u["halal"] = u.sym.isin(hal)
    u["volq"] = u.groupby("date").vol20.rank(pct=True)
    S = selectors(u)
    rows = []
    for n in (5, 10, 20):
        rc = ctrl(u, n)
        vc = ctrl(u, n, mask=(u.volq >= 0.8))
        for name in SHORT:
            for hal_only in (False, True):
                mask = u.halal if hal_only else None
                idx = pick_top(u, S[name], n, seed=11, mask=mask)
                r = nightly(u, idx)
                for b in (6, 12):
                    for mode, cap in (("loose", 1e5), ("strict", 5e4)):
                        st = by_split(r, b, cap=cap)
                        for k, v in st.items():
                            rows.append({"sel": name, "N": n, "halal_only": hal_only, "bps": b,
                                         "mode": mode, "split": k, **v,
                                         "pct_rand": pct(r, rc, k), "pct_volmatch": pct(r, vc, k)})
                if name == "rev5_lo" and n == 20 and not hal_only:
                    u.loc[idx, ["sym", "date"]].to_csv(OUT / "on_picks_rev5lo_n20.csv", index=False)
                if name == "vol+tug+rev5lo" and n == 20 and not hal_only:
                    u.loc[idx, ["sym", "date"]].to_csv(OUT / "on_picks_vtr_n20.csv", index=False)
        # control rows themselves (mean over seeds) for reference
        for lab, sims in (("CTRL_random", rc), ("CTRL_volmatched", vc)):
            g = pd.concat(sims, axis=1).mean(axis=1)
            for b in (6, 12):
                for k, v in by_split(g, b).items():
                    rows.append({"sel": lab, "N": n, "halal_only": False, "bps": b, "mode": "loose",
                                 "split": k, **v})
        print("done N", n, flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "on_final.csv", index=False)
    v = df[(df["mode"] == "loose") & (df.bps == 6) & (~df.halal_only)]
    print(v.pivot_table(index=["sel", "N"], columns="split",
                        values=["gross_bp", "usd_month", "pct_volmatch"]).round(1).to_string())


if __name__ == "__main__":
    main()
