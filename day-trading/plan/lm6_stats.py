"""LEGACY-6 stats over plan/lm6_out/legs_feat.json (see lm6_anatomy.py)."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\cornell\stocks-automation\day-trading")
R = json.loads((ROOT / "plan/lm6_out/legs_feat.json").read_text())
Y2 = "2025-08-01"
COST = 15.0                       # bps/side, gapper central
for r in R:
    r["y"] = 2 if r["date"] >= Y2 else 1
    r["n10"] = 1e4 * r["ret"] - 2 * COST          # $ net at a $10k ticket
    r["pm_rel"] = r["pm_dvol"] / r["dvol60"] if r["dvol60"] > 0 else np.nan
    r["mcap"] = r["shares"] * r["pc"] if r["shares"] > 0 else np.nan
    r["tod"] = r["g"] - 330
    r["fade_from_hi"] = (1 + r["gain_now"]) / (1 + r["hi_gain"]) - 1
    r["gain_vs_pmh"] = (1 + r["gain_now"]) / (1 + r["pm_high_gain"]) - 1
    r["gap_hold"] = (1 + r["gain_now"]) / (1 + r["gap_open"]) - 1
    r["vwap_dist"] = r["vwap_dist"]

FEATS = ["last", "gap_open", "gap7", "pm_high_gain", "pm_dvol", "pm_rel",
         "pm_bars", "dvol60", "shares", "mcap", "nhist", "prior_range", "ret5",
         "gain_now", "hi_gain", "coil", "fade_from_hi", "gain_vs_pmh",
         "gap_hold", "vwap_dist", "pressure30", "pressure10", "orb_dist",
         "dens", "sigma1", "rvol_now", "dvol_now", "tod", "since_cross",
         "n_elig", "n_gap10", "lead_rank", "mkt_gain_med",
         "any_catalyst_18h", "n_news_all_18h", "n_pr_18h", "n_offering_18h",
         "n_fda_18h", "n_contract_18h", "n_earnings_18h", "n_424b_10d",
         "n_s3_10d", "dilution_30d", "hrs_since_news", "hrs_since_fil"]


def arr(rs, k):
    return np.array([r.get(k, np.nan) for r in rs], float)


def auc(x, lab):
    ok = np.isfinite(x)
    x, lab = x[ok], lab[ok]
    p, n = lab.sum(), (~lab).sum()
    if p < 3 or n < 3:
        return np.nan
    rk = np.argsort(np.argsort(x, kind="mergesort")).astype(float)
    # average ranks for ties
    from scipy.stats import rankdata
    rk = rankdata(x)
    return (rk[lab].sum() - p * (p + 1) / 2) / (p * n)


def p(*a):
    print(*a)
    sys.stdout.flush()


def describe(src):
    rs = [r for r in R if r["src"] == src]
    ret = arr(rs, "ret")
    usd = arr(rs, "usd")
    n = len(rs)
    q95r = np.quantile(ret, 0.95)
    q95u = np.quantile(usd, 0.95)
    top_r = ret >= q95r
    top_u = usd >= q95u
    ndays = len({r["date"] for r in rs})
    p(f"\n=== {src}: n={n} days={ndays} Y1={sum(r['y']==1 for r in rs)} Y2={sum(r['y']==2 for r in rs)}")
    p(f" ret pct 5/25/50/75/95/99: " + " ".join(f"{100*v:+.1f}" for v in np.quantile(ret, [.05, .25, .5, .75, .95, .99])))
    p(f" top5% by ret: thr {100*q95r:+.1f}% n={top_r.sum()} (Y1 {sum(top_r & (arr(rs,'y')==1))}, Y2 {sum(top_r & (arr(rs,'y')==2))});"
      f" top5% by $: thr ${q95u:,.0f} n={top_u.sum()}; overlap {np.sum(top_r & top_u)}")
    g10 = 1e4 * ret
    p(f" $10k gross total {g10.sum():,.0f}  top5%(ret) contributes {g10[top_r].sum():,.0f}; rest {g10[~top_r].sum():,.0f}"
      f"  -> rest per trade gross {g10[~top_r].mean():+.1f}, net15 {g10[~top_r].mean()-30:+.1f}")
    p(f" mean $10k gross {g10.mean():+.1f} net15 {g10.mean()-30:+.1f};  Y1 {g10[arr(rs,'y')==1].mean():+.1f}  Y2 {g10[arr(rs,'y')==2].mean():+.1f}")
    # exit reasons of winners
    from collections import Counter
    p(" winners' exit:", dict(Counter(r["reason"] for r, t in zip(rs, top_r) if t)),
      " all:", dict(Counter(r["reason"] for r in rs)))
    ho = arr(rs, "xm") - arr(rs, "em")
    p(f" hold min median winners {np.median(ho[top_r]):.0f} vs all {np.median(ho):.0f}")
    return rs, top_r


def medtable(rs, top):
    ret = arr(rs, "ret")
    q = np.argsort(np.argsort(ret)) / len(ret)
    mid = (q >= 0.40) & (q <= 0.60)
    bot = q <= 0.05
    y = arr(rs, "y")
    p(f" {'feature':18s} {'top5':>9s} {'mid':>9s} {'bot5':>9s} {'all':>9s} | AUC(top vs rest) all / Y1 / Y2")
    res = {}
    for k in FEATS:
        x = arr(rs, k)
        a = auc(x, top)
        a1 = auc(x[y == 1], top[y == 1])
        a2 = auc(x[y == 2], top[y == 2])
        res[k] = (a, a1, a2)
        def m(mask):
            v = x[mask & np.isfinite(x)]
            return np.median(v) if v.size else np.nan
        p(f" {k:18s} {m(top):9.3g} {m(mid):9.3g} {m(bot):9.3g} {m(np.ones_like(top)):9.3g} | {a:.3f} / {a1:.3f} / {a2:.3f}")
    return res


def quint(rs, k, edges=None):
    x = arr(rs, k)
    n10 = arr(rs, "n10")
    y = arr(rs, "y")
    ok = np.isfinite(x)
    if edges is None:
        edges = np.unique(np.quantile(x[ok], [0.2, 0.4, 0.6, 0.8]))
    b = np.digitize(x, edges)
    out = []
    for j in range(len(edges) + 1):
        m = ok & (b == j)
        row = [j, int(m.sum())]
        for yy in (1, 2):
            mm = m & (y == yy)
            row += [n10[mm].mean() if mm.any() else np.nan, int(mm.sum())]
        out.append(row)
    return edges, out


if __name__ == "__main__":
    allres = {}
    for src in ("R4", "HF3", "RND"):
        rs, top = describe(src)
        allres[src] = medtable(rs, top)
    # consistency: features whose AUC is on the same side of .5 by >=.05 in all 6 (3 srcs x 2 yrs)
    p("\n=== AUC consistency (top5 vs rest), Y1/Y2 per source")
    for k in FEATS:
        v = [allres[s][k][1:] for s in ("R4", "HF3", "RND")]
        flat = [a for t in v for a in t]
        tag = ""
        if all(np.isfinite(flat)):
            if all(a >= 0.55 for a in flat):
                tag = "  <== HIGH in all 6"
            elif all(a <= 0.45 for a in flat):
                tag = "  <== LOW in all 6"
            elif all(a > 0.5 for a in flat) or all(a < 0.5 for a in flat):
                tag = "  (same side, all 6)"
        p(f" {k:18s} " + "  ".join(f"{s}:{allres[s][k][1]:.2f}/{allres[s][k][2]:.2f}" for s in ("R4", "HF3", "RND")) + tag)
    # quintile $/trade (net15 at $10k) on RND with fixed edges, then same edges on R4 / HF3
    p("\n=== quintiles: mean net $/trade at $10k (15 bps/side), Y1 | Y2  [n]")
    rnd = [r for r in R if r["src"] == "RND"]
    for k in FEATS:
        edges, o = quint(rnd, k)
        line = f" {k:16s} edges " + ",".join(f"{e:.3g}" for e in edges)
        p(line)
        for s in ("RND", "R4", "HF3"):
            rs = [r for r in R if r["src"] == s]
            _, oo = quint(rs, k, edges)
            p(f"   {s:4s} " + " | ".join(f"Q{j}:{a:+6.0f}/{c:+6.0f} [{na}/{nc}]" for j, _n, a, na, c, nc in oo))
