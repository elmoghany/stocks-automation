"""OVERNIGHT research: point-in-time universe + causal features on the gd panel.

Decision at day D's close (MOC entry at the official close c_D), exit at the
next session's official open o_{D+1} (gd `o` == 09:30 minute-bar open, see
harness-diagnostic.md section 0).

Universe U(D) (nothing about D's own outcome enters):
  CS/ADRC type (incl. delisted), prior close c_{D-1} >= $5,
  median dollar volume over the 20 sessions BEFORE D >= $20M (>=15 obs),
  printed on D.
Feature classes:
  PRE  -- known by D's 09:30 open (history through D-1 + D's opening gap).
          Fully causal for an MOC order at any time on D.
  CLS  -- uses D's close/high/low/volume (gd day bar). The close is the entry
          price itself, so these are NOT causal at 15:55 (5-min look-ahead);
          they are screened here and must be re-validated with <=15:55 bars.
Target: on1 = o_{D+1}/c_D - 1 (next printed session within 5 sessions),
        plus h-day variants ohk = o_{D+k}/c_D - 1, k=2..5.
Split guard: a c_D -> o_{D+1} ratio within 3% of a common split ratio and
|move| > 40% is treated as an unadjusted split and dropped (counted).
"""
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/research_oct"
GD = ROOT / "data/massive/gd"

MIN_MDV = 20e6
MIN_PX = 5.0
ETFS = ("SPY", "QQQ", "IWM", "VXX", "UVXY", "VIXY", "SPUS", "HLAL")


def etf_panel():
    f = OUT / "on_etf_panel.parquet"
    if f.exists():
        return pd.read_parquet(f)
    rows = []
    for p in sorted(GD.glob("*.json.gz")):
        for r in json.load(gzip.open(p)):
            if r.get("T") in ETFS:
                rows.append((p.name[:10], r["T"], r["o"], r["h"], r["l"], r["c"], r["v"]))
    e = pd.DataFrame(rows, columns="date sym o h l c v".split())
    e["date"] = pd.to_datetime(e["date"])
    e.to_parquet(f)
    return e


def split_like(r):
    rat = np.array([2, 3, 4, 5, 8, 10, 15, 20, 25, 30, 40, 50, 100], float)
    cand = np.concatenate([rat, 1 / rat])
    x = np.asarray(r, float)
    near = np.zeros(len(x), bool)
    for c in cand:
        near |= np.abs(x / c - 1) < 0.03
    return near & (np.abs(x - 1) > 0.4)


def main():
    df = pd.read_parquet(OUT / "on_gd_panel.parquet")
    df = df.dropna(subset=["o", "c", "h", "l", "v"]).sort_values(["sym", "date"])
    dates = np.array(sorted(df.date.unique()))
    di = {d: i for i, d in enumerate(dates)}
    df["di"] = df.date.map(di).astype(int)
    df["dv"] = df.vw.fillna(df.c) * df.v
    g = df.groupby("sym", sort=False)
    df["pc"] = g.c.shift(1)
    df["pdi"] = g.di.shift(1)
    df["mdv20"] = g.dv.transform(lambda s: s.shift(1).rolling(20, min_periods=15).median())
    df["adv20"] = g.v.transform(lambda s: s.shift(1).rolling(20, min_periods=15).mean())
    # overnight / intraday legs of each session (session-aligned to D)
    df["gap"] = df.o / df.pc - 1                     # c_{D-1} -> o_D  (PRE)
    df.loc[df.di - df.pdi > 5, "gap"] = np.nan
    df["intra"] = df.c / df.o - 1                    # o_D -> c_D      (CLS)
    df.loc[split_like(1 + df.gap.fillna(0)), "gap"] = np.nan
    g = df.groupby("sym", sort=False)
    # ---- PRE features (history through D-1 plus D's open)
    df["on_mom5"] = g.gap.transform(lambda s: s.rolling(5, min_periods=4).mean())
    df["on_mom20"] = g.gap.transform(lambda s: s.rolling(20, min_periods=15).mean())
    df["on_mom60"] = g.gap.transform(lambda s: s.rolling(60, min_periods=45).mean())
    df["id_mom20"] = g.intra.transform(lambda s: s.shift(1).rolling(20, min_periods=15).mean())
    df["on_pos20"] = g.gap.transform(lambda s: (s > 0).astype(float).rolling(20, min_periods=15).mean())
    df["tug20"] = df.on_mom20 - df.id_mom20          # Lou-Polk-Skouras tug of war
    df["rev5"] = df.pc / g.c.shift(6) - 1            # c_{D-6} -> c_{D-1}
    df["rev20"] = df.pc / g.c.shift(21) - 1
    r1 = g.c.pct_change()
    df["vol20"] = r1.groupby(df.sym).transform(lambda s: s.shift(1).rolling(20, min_periods=15).std())
    df["pgap"] = g.gap.shift(1)                      # prior-day gap
    df["pintra"] = g.intra.shift(1)
    df["lmdv"] = np.log(df.mdv20)
    df["dow"] = df.date.dt.dayofweek
    # ---- CLS features (use D's close -- screening only)
    rng = (df.h - df.l).replace(0, np.nan)
    df["cloc"] = (df.c - df.l) / rng
    df["dret"] = df.c / df.pc - 1
    df["rvol"] = df.v / df.adv20
    # ---- targets
    for k in range(1, 6):
        no = g.o.shift(-k)
        ndi = g.di.shift(-k)
        t = no / df.c - 1
        t[(ndi - df.di) > k + 4] = np.nan
        if k == 1:
            bad = split_like(no / df.c)
            print("split-guard drops", int(np.nansum(bad)))
            t[bad] = np.nan
            df["n_ndi"] = ndi
        else:
            t[split_like(no / df.c)] = np.nan
        df[f"oh{k}"] = t
    df["cc1"] = g.c.shift(-1) / df.c - 1
    # ---- universe
    U = (df.pc >= MIN_PX) & (df.mdv20 >= MIN_MDV) & (df.date >= "2024-10-01")
    u = df[U].copy()
    print("universe rows", len(u), "names/day median", u.groupby("date").size().median(),
          "missing next open", int(u.oh1.isna().sum()))
    # ---- earnings (known calendar): report after close D or before open D+1
    ey = json.loads((ROOT / "data/earnings_yf.json").read_text())
    nxt = {dates[i]: dates[i + 1] for i in range(len(dates) - 1)}
    flag = set()
    for s, lst in ey.items():
        for e in lst:
            ts = pd.Timestamp(e["ts"])
            d0 = ts.normalize()
            if ts.hour >= 16 or (ts.hour == 0):     # AMC on d0
                flag.add((s, d0))
            elif ts.hour < 10:                       # BMO on d0 -> held from prior session
                prev = dates[dates < np.datetime64(d0)]
                if len(prev):
                    flag.add((s, pd.Timestamp(prev[-1])))
    u["earn_cov"] = u.sym.isin(set(ey))
    u["earn_on"] = [(s, d) in flag for s, d in zip(u.sym, u.date)]
    print("earnings-overnight rows", int(u.earn_on.sum()), "coverage", round(u.earn_cov.mean(), 3))
    # ---- market regime from ETFs (D-1 info + D's open for SPY gap)
    e = etf_panel().pivot(index="date", columns="sym", values="c")
    eo = etf_panel().pivot(index="date", columns="sym", values="o")
    spy = e["SPY"]
    reg = pd.DataFrame(index=e.index)
    reg["spy_ma50"] = (spy.shift(1) > spy.shift(1).rolling(50).mean()).astype(float)
    reg["spy_r5"] = spy.shift(1) / spy.shift(6) - 1
    reg["spy_vol20"] = spy.pct_change().shift(1).rolling(20).std()
    reg["vxx_r5"] = e["VXX"].shift(1) / e["VXX"].shift(6) - 1 if "VXX" in e else np.nan
    reg["spy_gap"] = eo["SPY"] / spy.shift(1) - 1
    reg["spy_on1"] = eo["SPY"].shift(-1) / spy - 1
    reg["spy_intra_cls"] = spy / eo["SPY"] - 1        # CLS
    u = u.merge(reg, left_on="date", right_index=True, how="left")
    keep = ["date", "sym", "di", "c", "o", "h", "l", "v", "pc", "mdv20", "gap", "intra",
            "on_mom5", "on_mom20", "on_mom60", "id_mom20", "on_pos20", "tug20", "rev5", "rev20",
            "vol20", "pgap", "pintra", "lmdv", "dow", "cloc", "dret", "rvol", "earn_cov", "earn_on",
            "oh1", "oh2", "oh3", "oh4", "oh5", "cc1"] + list(reg.columns)
    u[keep].to_parquet(OUT / "on_feat.parquet")
    print(u[keep].describe().T[["count", "mean", "50%"]].to_string())


if __name__ == "__main__":
    main()
