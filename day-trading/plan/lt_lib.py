"""LEADS-TEST shared helpers: TC regime label (LEGACY-10, frozen), splits,
summaries with ex-top-5 and random-control percentiles."""
import gzip
import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
GD = ROOT / "data/massive/gd"
OUT = ROOT / "data/research_oct"


def split_of(d):
    if d < "2025-08-01":
        return "Y1"
    if d < "2026-08-01":
        return "Y2"
    return "OOS"


def tc_labels():
    """LEGACY-10 TC, pre-registered and NOT re-tuned:
    TC(D) = SPY_ma20 > 0 & QQQ_ma20 > 0 & SPY_volratio < 1, where for ETF e
    using closes through D-1 (lm10_feat.etf_feats verbatim):
      ma20 = cl[-1] / mean(cl[-20:]) - 1
      volratio = std(r[-5:]) / std(r[-20:]),  r = diff(log cl)
    (lm10_feat requires >= 51 prior closes; same here)."""
    files = sorted(f for f in os.listdir(GD) if f.endswith(".json.gz"))
    dates = [f[:10] for f in files]
    ser = {"SPY": {}, "QQQ": {}}
    for f, d in zip(files, dates):
        with gzip.open(GD / f, "rt", encoding="utf-8") as fh:
            for r in json.load(fh):
                t = r.get("T")
                if t in ser and r.get("c"):
                    ser[t][d] = r["c"]
    out = {}
    for i, d in enumerate(dates):
        if i < 51:
            continue
        f = {}
        for e in ("SPY", "QQQ"):
            cl = np.array([ser[e][x] for x in dates[:i] if x in ser[e]])
            if len(cl) < 51:
                break
            r = np.diff(np.log(cl))
            f[e + "_ma20"] = cl[-1] / cl[-20:].mean() - 1
            f[e + "_vr"] = r[-5:].std() / max(r[-20:].std(), 1e-9)
        else:
            out[d] = bool(f["SPY_ma20"] > 0 and f["QQQ_ma20"] > 0
                          and f["SPY_vr"] < 1)
    return out


def summ(legs, ndays_by_split, key="n_c"):
    """Per split: n, $/trade (gross, central, flat12), trades/month,
    $/month central, ex-top-5 $/month, months positive."""
    res = {}
    for sp in ("Y1", "Y2", "OOS", "ALL"):
        L = [x for x in legs if sp == "ALL" or split_of(x["date"]) == sp]
        nd = ndays_by_split[sp]
        months = max(nd, 1) / 21.0
        if not L:
            res[sp] = dict(n=0)
            continue
        g = np.array([x["g"] for x in L])
        c = np.array([x["n_c"] for x in L])
        f = np.array([x["n_12"] for x in L])
        srt = np.sort(c)
        ex5 = srt[:-5].sum() if len(srt) > 5 else 0.0
        mon = {}
        for x in L:
            mon[x["date"][:7]] = mon.get(x["date"][:7], 0) + x["n_c"]
        res[sp] = dict(n=len(L), g=g.mean(), c=c.mean(), f12=f.mean(),
                       tpm=len(L) / months, pm=c.sum() / months,
                       pm12=f.sum() / months, ex5pm=ex5 / months,
                       mpos=f"{sum(v > 0 for v in mon.values())}/{len(mon)}",
                       win=float((g > 0).mean()))
    return res


def fmt_row(name, s, sp):
    x = s[sp]
    if not x.get("n"):
        return f"| {name} | {sp} | 0 | | | | | | | |"
    return (f"| {name} | {sp} | {x['n']} | {x['g']:+.1f} | {x['c']:+.1f} | "
            f"{x['f12']:+.1f} | {x['tpm']:.1f} | {x['pm']:+,.0f} | "
            f"{x['pm12']:+,.0f} | {x['ex5pm']:+,.0f} |")
