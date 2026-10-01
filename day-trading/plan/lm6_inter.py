"""LEGACY-6: interactions + robustness on the joined legs (lm6_anatomy)."""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\cornell\stocks-automation\day-trading")
R = json.loads((ROOT / "plan/lm6_out/legs_feat.json").read_text())
Y2 = "2025-08-01"
for r in R:
    r["y"] = 2 if r["date"] >= Y2 else 1
    r["g10"] = 1e4 * r["ret"]
    r["pm_rel"] = r["pm_dvol"] / r["dvol60"] if r["dvol60"] > 0 else float("nan")
    r["tod"] = r["g"] - 330


def stat(rs, label, cost=15.0):
    if not rs:
        print(f"  {label:44s} n=0")
        return
    g = np.array([r["g10"] for r in rs])
    y = np.array([r["y"] for r in rs])
    days = len({r["date"] for r in rs})
    srt = np.sort(g)
    ex5 = srt[:-5].mean() if len(g) > 10 else np.nan
    s = f"  {label:44s} n={len(g):5d} d={days:4d} gross {g.mean():+7.1f} net{cost:.0f} {g.mean()-2*cost:+7.1f}"
    for yy in (1, 2):
        gg = g[y == yy]
        s += f" | Y{yy} n={len(gg):4d} {gg.mean()-2*cost:+7.1f}" if len(gg) else f" | Y{yy} n=0"
    s += f" | med {np.median(g):+5.0f} win {100*(g>2*cost).mean():3.0f}% ex-top5 {ex5-2*cost:+6.1f}"
    print(s)


def main():
    # catalyst coverage
    for src in ("R4", "HF3", "RND"):
        rs = [r for r in R if r["src"] == src]
        cov = np.mean([r.get("cat_cov", False) for r in rs])
        anyc = np.mean([r["any_catalyst_18h"] > 0 for r in rs])
        news = np.mean([r["n_news_all_18h"] > 0 for r in rs])
        print(f"{src}: corpus-covered {100*cov:.0f}%  any_catalyst_18h>0 {100*anyc:.1f}%  news18h>0 {100*news:.1f}%")
    rnd = [r for r in R if r["src"] == "RND"]
    r4 = [r for r in R if r["src"] == "R4"]
    hf = [r for r in R if r["src"] == "HF3"]
    print("\n== catalyst yes/no (net15 $/trade at $10k)")
    for nm, rs in (("RND", rnd), ("R4", r4), ("HF3", hf)):
        stat([r for r in rs if r["n_news_all_18h"] > 0], f"{nm} news in last 18h")
        stat([r for r in rs if r["n_news_all_18h"] == 0], f"{nm} no news 18h")
    print("\n== RND: coil bucket x sigma1 bucket")
    for clo, chi in ((0, 0.95), (0.95, 0.99), (0.99, 1.01)):
        for slo, shi in ((0, 0.009), (0.009, 0.0135), (0.0135, 0.0215), (0.0215, 9)):
            stat([r for r in rnd if clo <= r["coil"] < chi and slo <= r["sigma1"] < shi],
                 f"coil[{clo},{chi}) sig[{slo},{shi})")
    print("\n== R4 (all coil~1): sigma1 buckets")
    for slo, shi in ((0, 0.009), (0.009, 0.0135), (0.0135, 0.0215), (0.0215, 9)):
        stat([r for r in r4 if slo <= r["sigma1"] < shi], f"R4 sig[{slo},{shi})")
    print("\n== HF3: coil x sigma1")
    for clo, chi in ((0, 0.99), (0.99, 1.01)):
        for slo, shi in ((0, 0.0135), (0.0135, 9)):
            stat([r for r in hf if clo <= r["coil"] < chi and slo <= r["sigma1"] < shi],
                 f"HF3 coil[{clo},{chi}) sig[{slo},{shi})")
    print("\n== RND at-high (coil>=0.99): other features split at RND median within that subset")
    sub = [r for r in rnd if r["coil"] >= 0.99]
    for k in ("sigma1", "dvol60", "prior_range", "gain_now", "hi_gain", "vwap_dist",
              "pm_rel", "rvol_now", "tod", "lead_rank", "mkt_gain_med", "n_elig",
              "pressure30", "last", "dvol_now", "since_cross", "gap_open"):
        x = np.array([r[k] for r in sub], float)
        med = np.nanmedian(x)
        stat([r for r, v in zip(sub, x) if v >= med], f"{k} >= {med:.3g}")
        stat([r for r, v in zip(sub, x) if v < med], f"{k} <  {med:.3g}")
    # the winners themselves: the R4 top-5% by $ (actual) listed
    print("\n== R4 top 49 legs by ret: date sym ret% sigma1 coil hi_gain dvol60 tod since_cross lead_rank news18h")
    for r in sorted(r4, key=lambda r: -r["ret"])[:49]:
        print(f"  {r['date']} {r['sym']:6s} {100*r['ret']:+6.1f} sig {r['sigma1']:.4f} coil {r['coil']:.3f} "
              f"hig {r['hi_gain']:.2f} dv60 {r['dvol60']/1e6:7.2f}M px {r['last']:6.2f} tod {r['tod'] if 'tod' in r else r['g']-330:4.0f} "
              f"sc {r['since_cross']:4.0f} lr {r['lead_rank']:3d} news {r['n_news_all_18h']:.0f} ex {r['reason']}")


if __name__ == "__main__":
    main()
