"""LEGACY-2: why coil works as an ORDER. Reads plan/lm2_out/panel.npz.

All statistics are day-clustered: a number is averaged inside a session
first, then across sessions, and t = mean / (sd / sqrt(n_days)).
Returns are fractions of the deferred fill (next printed bar's OPEN after
the decision minute). $ figures are per $10,000 ticket, gross, and net of
a round-trip cost of 2 x COST_BPS (default 15 bps/side for +10% gappers).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

P = Path(__file__).resolve().parent / "lm2_out"
COST_BPS = 15.0
Y1_END = "2025-08-01"
OOS = "2026-08-01"


def load():
    z = np.load(P / "panel.npz")
    dates = z["dates"]
    d = pd.DataFrame({k: z[k] for k in z.files if k != "dates"})
    d["date"] = dates[d["di"].astype(int)]
    d["yr"] = np.where(d["date"] < Y1_END, "Y1",
                       np.where(d["date"] < OOS, "Y2", "OOS"))
    d["ret15b"] = (1 + d["gain_now"]) / (1 + d["gain_m15"]) - 1
    d["hm"] = (d["t"] + 240).astype(int)          # minutes after 00:00 ET
    d["tb"] = pd.cut(d["hm"], [0, 590, 600, 630, 720, 900],
                     labels=["0935-0950", "0955-1000", "1005-1030",
                             "1035-1200", "1205-1430"])
    # clip absurd outcomes (bad prints) -- symmetric, reported
    for c in ["r15", "r30", "r60", "r1500", "r4"]:
        d[c] = d[c].clip(-0.6, 1.5)
    return d


def dmean(df, col):
    """day-clustered mean, t, n_days, n_rows"""
    g = df.dropna(subset=[col]).groupby("date")[col].mean()
    if len(g) < 3:
        return np.nan, np.nan, len(g), len(df)
    return g.mean(), g.mean() / (g.std(ddof=1) / np.sqrt(len(g))), len(g), len(df)


def fmt(m, t, nd, n, cost=True):
    if not np.isfinite(m):
        return f"n={n} --"
    net = m * 1e4 - 2 * COST_BPS
    return (f"{m*1e4:+7.1f}bps (t{t:+5.1f}) net${net:+6.1f}/tkt "
            f"nd={nd} n={n}")


COILB = [-1, 0.80, 0.90, 0.95, 0.98, 0.995, 1.01]
COILL = ["<.80", ".80-.90", ".90-.95", ".95-.98", ".98-.995", ">=.995"]


def bucket_table(d, col, title, by=None):
    print(f"\n### {title}  [outcome={col}]")
    d = d.copy()
    d["cb"] = pd.cut(d["coil"], COILB, labels=COILL, right=False)
    groups = [("ALL", d)] if by is None else list(d.groupby(by, observed=True))
    for gname, gd in groups:
        print(f"-- {by}={gname}" if by else "")
        for yr in ["Y1", "Y2", "OOS"]:
            yd = gd[gd["yr"] == yr]
            parts = []
            for cl in COILL:
                m, t, nd, n = dmean(yd[yd["cb"] == cl], col)
                parts.append(f"{cl}:{m*1e4:+6.0f}({t:+4.1f},{n})"
                             if np.isfinite(m) else f"{cl}: --")
            print(f"  {yr}: " + " | ".join(parts))


def xs_ic(d, col, feat="coil", min_n=2):
    """mean per-(date,t) Spearman IC, day-clustered t."""
    x = d.dropna(subset=[col, feat])
    x = x[x.groupby(["date", "t"])[feat].transform("size") >= min_n]
    x = x[x.groupby(["date", "t"])[feat].transform("size") >= 3]
    k = ["date", "t"]
    rf = x.groupby(k)[feat].rank(pct=True)
    ro = x.groupby(k)[col].rank(pct=True)
    a = rf - rf.groupby([x["date"], x["t"]]).transform("mean")
    b = ro - ro.groupby([x["date"], x["t"]]).transform("mean")
    y = pd.DataFrame({"date": x["date"], "t": x["t"], "ab": a * b,
                      "aa": a * a, "bb": b * b}).groupby(k).sum()
    ic = (y["ab"] / np.sqrt(y["aa"] * y["bb"])).replace([np.inf, -np.inf], np.nan)
    ic = ic.dropna().groupby(level=0).mean()
    return ic.mean(), ic.mean() / (ic.std(ddof=1) / np.sqrt(len(ic))), len(ic)


def pick_value(d, col, key="coil", asc=False):
    """top-by-key minus group mean, groups with >=2 candidates."""
    x = d.dropna(subset=[col, key])
    x = x[x.groupby(["date", "t"])[key].transform("size") >= 2]
    x = x.sort_values(["date", "t", key], ascending=[True, True, asc])
    top = x.groupby(["date", "t"]).head(1).set_index(["date", "t"])[col]
    mean = x.groupby(["date", "t"])[col].mean()
    diff = (top - mean).groupby(level=0).mean()
    return diff.mean(), diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))), len(diff)


def main():
    d = load()
    print("rows", len(d), "days", d["date"].nunique(),
          d.groupby("yr")["date"].nunique().to_dict())
    print("cands per (date,t): median",
          d.groupby(["date", "t"]).size().median(),
          " share of decision groups with 1 cand:",
          round((d.groupby(["date", "t"]).size() == 1).mean(), 3))
    print("coil quantiles", d["coil"].quantile([.1, .25, .5, .75, .9]).round(3).to_dict())

    # 1. absolute level of forward return by coil bucket
    for col in ["r30", "r60", "r1500", "r4"]:
        bucket_table(d, col, "coil bucket -> forward return (bps), (t, n)")
    # 2. by decision time
    bucket_table(d, "r1500", "by decision time", by="tb")
    bucket_table(d[d["r4"].notna()], "r4", "R4-exit by decision time", by="tb")
    # 3. by gain so far, price, dollar volume
    d["gb"] = pd.cut(d["gain_now"], [0, .2, .4, .8, 99],
                     labels=["10-20%", "20-40%", "40-80%", "80%+"])
    d["pb"] = pd.cut(d["last"], [0, 5, 20, 1e9], labels=["$2-5", "$5-20", "$20+"])
    d["vb"] = pd.qcut(d["dvol_now"].rank(method="first"), 3,
                      labels=["dvol-lo", "dvol-mid", "dvol-hi"])
    for by in ["gb", "pb", "vb"]:
        bucket_table(d, "r1500", f"by {by}", by=by)

    # 4. cross-sectional IC and pick value vs other keys
    print("\n### cross-sectional IC (per date,t Spearman, day-clustered)")
    for col in ["r30", "r60", "r1500", "r4"]:
        for feat in ["coil", "gain_now", "hi_gain", "ret15b", "vwap_dist",
                     "pressure30", "rvol_now", "orb_dist"]:
            for yr in ["Y1", "Y2"]:
                m, t, n = xs_ic(d[d["yr"] == yr], col, feat)
                print(f"  {col:6s} {feat:11s} {yr}: IC {m:+.4f} t{t:+5.1f} nd={n}")

    print("\n### pick value: top-coil minus group mean (groups >=2), $/10k gross")
    for col in ["r60", "r1500", "r4"]:
        for yr in ["Y1", "Y2", "OOS"]:
            for tb in [None, "0935-0950", "0955-1000", "1005-1030",
                       "1035-1200", "1205-1430"]:
                x = d[d["yr"] == yr]
                if tb:
                    x = x[x["tb"] == tb]
                m, t, n = pick_value(x, col)
                print(f"  {col:6s} {yr} {tb or 'all':10s}: {m*1e4:+7.1f}bps t{t:+5.1f} nd={n}")

    # 5. is it momentum? partial out within (date,t): regress demeaned
    print("\n### within-(date,t) OLS of r1500 / r60 on standardized ranks")
    for col in ["r60", "r1500"]:
        for yr in ["Y1", "Y2"]:
            x = d[(d["yr"] == yr)].dropna(subset=[col, "coil", "gain_now",
                                                  "ret15b", "hi_gain", "vwap_dist"])
            x = x[x.groupby(["date", "t"])["coil"].transform("size") >= 3]
            feats = ["coil", "gain_now", "ret15b", "vwap_dist", "dvol_now"]
            X = np.column_stack([
                x.groupby(["date", "t"])[f].rank(pct=True) - 0.5 for f in feats])
            y = (x[col] - x.groupby(["date", "t"])[col].transform("mean")).values
            # day-clustered SE via per-day coefficient estimates (Fama-MacBeth)
            coefs = []
            for _, idx in x.groupby("date").indices.items():
                if len(idx) < 15:
                    continue
                b, *_ = np.linalg.lstsq(X[idx], y[idx], rcond=None)
                coefs.append(b)
            C = np.array(coefs)
            mu, se = C.mean(0), C.std(0, ddof=1) / np.sqrt(len(C))
            print(f"  {col} {yr} FM n_days={len(C)}: " + "  ".join(
                f"{f}:{m*1e4:+.0f}bps(t{m/s:+.1f})" for f, m, s in zip(feats, mu, se)))

    # 6. filter thresholds: absolute return of coil >= x, by year and time
    print("\n### FILTER coil >= x (absolute, all candidates) -- r4 / r1500")
    for col in ["r4", "r1500", "r60"]:
        for th in [0.0, 0.90, 0.95, 0.97, 0.98, 0.99, 0.995]:
            s = []
            for yr in ["Y1", "Y2", "OOS"]:
                m, t, nd, n = dmean(d[(d["yr"] == yr) & (d["coil"] >= th)], col)
                s.append(f"{yr} {m*1e4:+6.0f}(t{t:+4.1f},n{n})")
            print(f"  {col} coil>={th:.3f}: " + " | ".join(s))


if __name__ == "__main__":
    main()
