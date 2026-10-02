"""SWING-REVERSION main study.

python plan/sr_run.py gd     -> point-in-time grouped-daily panel 2024-10..2026-09
python plan/sr_run.py long   -> yfinance S&P-500 point-in-time members 2005..2024-09
Writes data/research_oct/sr_results_<ds>.json and prints tables.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sr_lib import features, random_control, simulate, stats  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research_oct"
DS = sys.argv[1] if len(sys.argv) > 1 else "gd"
ONLY = sys.argv[2].split(",") if len(sys.argv) > 2 else None
SEEDS = 30
C6, C12 = 0.0006, 0.0012

if DS == "gd":
    blob = pd.read_pickle(OUT / "sr_panel.pkl")
    P = blob["P"]
    ref = json.load(open(OUT / "tickers_ref.json"))
    okt = np.array([any(v[0] in ("CS", "ADRC") for v in ref.get(t, [])) for t in P["C"].columns])
    SPLITS = {"Y1": ("2024-10-01", "2025-07-31", 10), "Y2": ("2025-08-01", "2026-07-31", 12),
              "OOS": ("2026-08-01", "2026-09-30", 2)}
    START, END = "2024-10-01", "2026-09-30"
    split_dates = blob["split_dates"]
else:
    yfd = pd.read_pickle(OUT / "long" / "yf_daily.pkl")
    P = {k[0]: v.sort_index() for k, v in yfd.items()}
    P = {k: v.loc[:, P["C"].columns] for k, v in P.items()}
    okt = np.ones(P["C"].shape[1], bool)
    SPLITS = {"L05-09": ("2005-01-01", "2009-12-31", 60), "L10-14": ("2010-01-01", "2014-12-31", 60),
              "L15-19": ("2015-01-01", "2019-12-31", 60), "L20-24": ("2020-01-01", "2024-09-30", 57)}
    START, END = "2005-01-01", "2024-09-30"
    split_dates = {}

F = features(P)
C = P["C"]
cols = C.columns
okt_df = pd.DataFrame(np.broadcast_to(okt, C.shape), index=C.index, columns=cols)
hist = C.notna().rolling(60, min_periods=1).sum() >= 55
if DS == "gd":
    U = okt_df & (F["dv20"] >= 25e6) & (C >= 10) & hist
else:
    mem = pd.read_csv(OUT / "long" / "sp500_ticker_start_end.csv").fillna({"end_date": "2099-01-01"})
    M = pd.DataFrame(False, index=C.index, columns=cols)
    for t, a, b in mem.itertuples(index=False):
        if t in M.columns:
            M.loc[(M.index >= a) & (M.index <= b), t] = True
    U = M & (C >= 5) & hist & (F["dv20"] >= 1e6)
if "SPY" in cols:
    U["SPY"] = False
# belt and braces: no signals within [E-25, E+5] sessions of any split date
for t, ds in split_dates.items():
    if t in cols:
        for E in ds:
            k = int(np.searchsorted(C.index, pd.Timestamp(E)))
            U.iloc[max(0, k - 5):k + 26, cols.get_loc(t)] = False
rk = F["dv20"].where(U).rank(axis=1, ascending=False)
UL = U & (rk <= 500)
halal = set(json.load(open(ROOT / "data" / "halal_list.json"))["symbols"])
HAL = pd.Series([t in halal for t in cols], index=cols)
week_end = pd.Series(C.index.isocalendar().week.values, index=C.index)
week_end = (week_end != week_end.shift(-1)).values  # last session of ISO week
print("universe size median", int(U.sum(axis=1).median()), "large", int(UL.sum(axis=1).median()),
      "| residual huge gaps inside U:", int((((P["O"] / C.shift(1)) > 2.5) | ((P["O"] / C.shift(1)) < 0.35)).shift(-1).where(U).fillna(False).astype(bool).values.sum()))


def S_(mask, score):
    return score.where(mask)


r2, r3 = F["rsi2"], F["rsi3"]
up200, up100, up50 = C > F["ma200"], C > F["ma100"], C > F["ma50"]
x_ma5 = C > F["ma5"]
x_rsi70 = r2 > 70
volr = P["V"] / F["vol20"]
wk = pd.DataFrame(np.broadcast_to(week_end[:, None], C.shape), index=C.index, columns=cols)
p05 = F["ret5"].where(UL).quantile(0.05, axis=1)

STRATS = {
    # ---- family 1: short-term mean reversion (pullback in uptrend)
    "MR-rsi2<5|ma200|x>ma5|H10": (S_(U & up200 & (r2 < 5), r2), x_ma5, 10, U),
    "MR-rsi2<5|ma100|x>ma5|H10": (S_(U & up100 & (r2 < 5), r2), x_ma5, 10, U),
    "MR-rsi2<5|ma50|x>ma5|H10": (S_(U & up50 & (r2 < 5), r2), x_ma5, 10, U),
    "MR-rsi2<10|ma100|x>rsi70|H5": (S_(U & up100 & (r2 < 10), r2), x_rsi70, 5, U),
    "MR-rsi3<15|ma100|x>ma5|H10": (S_(U & up100 & (r3 < 15), r3), x_ma5, 10, U),
    "MR-down3|ma100|x>ma5|H10": (S_(U & up100 & (F["downrun"] >= 3), r2), x_ma5, 10, U),
    "MR-bbl|ma100|x>ma5|H10": (S_(U & up100 & (C < F["bbl"]), r2), x_ma5, 10, U),
    "MR-low10|ma100|x>ma5|H10": (S_(U & up100 & (C <= F["low10"]), r2), x_ma5, 10, U),
    "MR-rsi2<5|notrend|x>ma5|H10": (S_(U & (r2 < 5), r2), x_ma5, 10, U),
    "MR-rsi2<5|ma100|large|x>ma5|H10": (S_(UL & up100 & (r2 < 5), r2), x_ma5, 10, UL),
    # ---- family 2: 1-week reversal among large/liquid names
    "WR-weekly-losers|large|H5": (S_(UL & wk, F["ret5"]), None, 5, UL),
    "WR-daily-ret5<p5|large|H5": (S_(UL & F["ret5"].le(p05, axis=0), F["ret5"]), None, 5, UL),
    # ---- family 3: momentum / breakout continuation (contrast)
    "MO-52wHigh+vol1.5|H10": (S_(U & (C >= F["hh252"]) & (volr >= 1.5), -volr), None, 10, U),
    "MO-120dHigh+vol1.5|H10": (S_(U & (C >= F["hh120"]) & (volr >= 1.5), -volr), None, 10, U),
    "MO-gap4hold+vol2|H3": (S_(U & (F["gap"] >= 0.04) & (C >= P["O"]) & (volr >= 2), -F["gap"]), None, 3, U),
    "MO-gap4hold+vol2|H10": (S_(U & (F["gap"] >= 0.04) & (C >= P["O"]) & (volr >= 2), -F["gap"]), None, 10, U),
}
if DS == "long":  # 52w high needs 252 sessions; the long panel has them everywhere
    STRATS.pop("MO-120dHigh+vol1.5|H10")


def run_one(name, S, X, H, Uc, n, mode="open", halal_only=False):
    size = 100_000 / n
    if halal_only:
        S = S.where(pd.DataFrame(np.broadcast_to(HAL.values, S.shape), index=S.index, columns=cols))
        Uc = Uc & pd.DataFrame(np.broadcast_to(HAL.values, S.shape), index=S.index, columns=cols)
    tr, curve = simulate(P, S, X, H, n, size, C6, mode=mode, start=START, end=END)
    res = {}
    rc = random_control(P, Uc, tr, size, C6, SEEDS, mode) if len(tr) else np.zeros((SEEDS, 0))
    for sp, (a, b, mo) in SPLITS.items():
        r = {}
        for lab, c in (("c6", C6), ("c12", C12)):
            r[lab] = stats(tr, curve, a, b, mo, size,
                           cost_adj=lambda t, c=c: size * t.g - c * size * (2 + t.g))
        m = ((tr.ent_date >= pd.Timestamp(a)) & (tr.ent_date <= pd.Timestamp(b))).values
        ctl = rc[:, m].sum(axis=1) / mo
        r["ctl_mo_mean"] = float(ctl.mean()) if len(ctl) else 0.0
        r["ctl_pct"] = float((ctl < r["c6"]["mo"]).mean() * 100)
        res[sp] = r
    m_all = np.ones(len(tr), bool)
    ctl_all = rc[:, m_all].sum(axis=1)
    res["ALL_ctl_pct"] = float((ctl_all < tr.pnl.sum()).mean() * 100) if len(tr) else 0.0
    res["ALL_mo"] = float(tr.pnl.sum()) / sum(v[2] for v in SPLITS.values())
    res["ALL_ex5_mo"] = float(tr.pnl.sum() - tr.pnl.nlargest(5).sum()) / sum(v[2] for v in SPLITS.values())
    return res, tr


def spy_bh():
    out = {}
    if "SPY" not in cols:
        return out
    s = C["SPY"].dropna()
    for sp, (a, b, mo) in SPLITS.items():
        w = s[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]
        prev = s[s.index < pd.Timestamp(a)]
        base = prev.iloc[-1] if len(prev) else w.iloc[0]
        eq = 100_000 * (w / base - 1)
        out[sp] = dict(mo=float(eq.iloc[-1]) / mo, maxdd=float((eq - eq.cummax()).min()))
    return out


def main():
    results = {"spy": spy_bh(), "strats": {}}
    print("SPY B&H $/mo:", {k: round(v["mo"]) for k, v in results["spy"].items()})
    trades_keep = {}
    for name, (S, X, H, Uc) in STRATS.items():
        if ONLY and not any(o in name for o in ONLY):
            continue
        for n in (5, 10):
            for mode in (("open", "close") if name.startswith("MR") else ("open",)):
                key = f"{name}|N{n}|{mode}"
                res, tr = run_one(name, S, X, H, Uc, n, mode)
                results["strats"][key] = res
                trades_keep[key] = tr
                line = " ".join(f"{sp}:{res[sp]['c6']['mo']:+7.0f}({res[sp]['c12']['mo']:+6.0f})"
                                f"n{res[sp]['c6']['n']:4d} ${res[sp]['c6']['per_tr']:+5.0f} w{res[sp]['c6']['win']:.2f}"
                                f" dd{res[sp]['c6']['maxdd']:+6.0f} p{res[sp]['ctl_pct']:3.0f}"
                                for sp in SPLITS)
                print(f"{key:45s} {line} | ALL {res['ALL_mo']:+6.0f} ex5 {res['ALL_ex5_mo']:+6.0f} pct {res['ALL_ctl_pct']:.0f}", flush=True)
            if n == 10 and name.startswith(("MR", "WR")):
                key = f"{name}|N{n}|open|HALAL-present-day"
                res, tr = run_one(name, S, X, H, Uc, n, "open", halal_only=True)
                results["strats"][key] = res
                print(f"{key:45s} " + " ".join(f"{sp}:{res[sp]['c6']['mo']:+7.0f} n{res[sp]['c6']['n']}" for sp in SPLITS), flush=True)
    (OUT / f"sr_results_{DS}{'_' + '_'.join(ONLY) if ONLY else ''}.json").write_text(json.dumps(results, indent=1))
    pd.to_pickle(trades_keep, OUT / f"sr_trades_{DS}{'_' + '_'.join(ONLY) if ONLY else ''}.pkl")
    print("DONE")


if __name__ == "__main__":
    main()
