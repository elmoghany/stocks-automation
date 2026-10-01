"""LEGACY-7 (anatomy of losers -> vetoes): entry-time feature table for
every honest leg of CHAMPION-REPLAY R4 (plan/pa_out/cp_r4_legs.json) and
C37F-hf3 (data/massive/rotation_trades_C37F_hf3.json).

CAUSALITY: every feature is read at the last 5-minute grid point STRICTLY
BEFORE the fill minute (cp_feat grid values use bars <= that grid minute),
or from prior sessions / premarket; spread/Amihud use bars < fill minute;
catalyst counts use events with timestamp <= the minute before the fill;
the day-so-far P&L uses only legs that EXITED before this entry.
PnL is normalised to a $10,000 ticket (gross; costs applied in lm7_veto).

    python plan/lm7_feat.py   -> scratch pickle (path printed)
"""
import json
import pickle
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import cp_lib as L                                          # noqa: E402
import cp_feat as F                                         # noqa: E402
import cp_cost as CC                                        # noqa: E402
import cat_events as E                                      # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:/Users/MYPC~1/AppData/Local/Temp/claude/C--cornell-stocks-automation/20a29bc8-aa0d-497e-a600-4db3499b8240/scratchpad/lm7_table.pkl")
OUT.parent.mkdir(exist_ok=True)
GKEYS = ["gain_now", "coil", "hi_gain", "dvol_now", "vwap_dist", "pressure30",
         "pressure10", "orb_dist", "dens", "sigma1", "rvol_now", "vol5"]
SKEYS = ["pc", "pm_dvol", "pm_high_gain", "gap_open", "gap7", "pm_bars",
         "dvol60", "prior_range", "nhist", "prevrange", "ret5", "shares"]
FN = E.feature_names()


def legs():
    out = []
    r4 = json.loads((HERE / "pa_out" / "cp_r4_legs.json").read_text())["legs"]["R4"]
    for x in r4:
        out.append(dict(strat="R4", date=x["date"], sym=x["sym"], em=int(x["entry_min"]),
                        xm=int(x["exit_min"]), entry=x["entry"], shares=x["shares"],
                        gross=x["gross"], reason=x["reason"]))
    c = json.loads((ROOT / "data/massive/rotation_trades_C37F_hf3.json").read_text())
    for x in c:
        def mm(s):
            hh, mi = int(s[11:13]), int(s[14:16])
            return L.mgrid(hh, mi)
        out.append(dict(strat="C37F", date=x["date"], sym=x["symbol"], em=mm(x["entry_time"]),
                        xm=mm(x["exit_time"]), entry=x["entry"], shares=x["shares"],
                        gross=x["pnl"], reason=x["reason"].split()[0], lab=x["label"]))
    for r in out:
        r["notional"] = r["entry"] * r["shares"]
        r["g10k"] = r["gross"] * 10_000.0 / r["notional"]
        r["ret_bps"] = r["g10k"]  # $ per $10k == bps
        r["y"] = 1 if r["date"] < "2025-08-01" else 2
        if r["strat"] == "C37F":
            r["y"] = 1 if r.get("lab") == "y2025" else 2
    return out


def amihud(day, i, m, win=30):
    a = max(0, m - win)
    sel = day.printed[i, a:m]
    c = np.where(sel, day.c[i, a:m], np.nan)
    v = day.v[i, a:m]
    ok = np.isfinite(c)
    if ok.sum() < 4:
        return np.nan
    cc = c[ok]
    vv = v[ok][1:] * cc[1:]
    r = np.abs(np.diff(np.log(cc)))
    good = vv > 0
    if good.sum() < 3:
        return np.nan
    return float(np.mean(r[good] / vv[good]) * 1e10)   # bps per $1M


def main():
    t0 = time.time()
    rows = legs()
    by = {}
    for k, r in enumerate(rows):
        by.setdefault(r["date"], []).append(k)
    tc = CC.TapeCost(coef=0.0, floor=0.0)
    G = np.array(F.GRID)
    miss = 0
    for n, (date, ks) in enumerate(sorted(by.items())):
        Fd = F.load(date)
        day = L.load_day(date)
        if Fd is None or day is None:
            miss += len(ks)
            continue
        sidx = {s: j for j, s in enumerate(Fd["syms"])}
        didx = {s: j for j, s in enumerate(day.syms)}
        for k in ks:
            r = rows[k]
            j = sidx.get(r["sym"])
            r["ok"] = j is not None
            if j is None:
                miss += 1
                continue
            for s in SKEYS:
                r[s] = float(Fd[s][j])
            gi = int(np.searchsorted(G, r["em"], side="left")) - 1   # GRID[gi] < em
            r["gi"] = gi
            if gi >= 0:
                for s in GKEYS:
                    r[s] = float(Fd[s][j, gi])
                el = Fd["elig_high"][j, :gi + 1]
                r["min_since_cross"] = float(G[gi] - G[int(np.argmax(el))]) if el.any() else np.nan
                r["breadth"] = float(Fd["elig_last"][:, gi].sum())
                # cross-sectional rank of the leg's gain among eligible names
                e = Fd["elig_last"][:, gi]
                gn = Fd["gain_now"][e, gi]
                r["gain_rank"] = float((gn > Fd["gain_now"][j, gi]).sum()) if e.any() else np.nan
            else:
                for s in GKEYS + ["min_since_cross", "breadth", "gain_rank"]:
                    r[s] = np.nan
            i = didx.get(r["sym"])
            if i is not None:
                tc.hist.clear(); tc.parts.clear()
                r["half_spread"] = float(tc.bps(day, i, r["em"], 10_000.0))
                r["amihud"] = amihud(day, i, r["em"])
                # entry fill vs prior bar close (gap-through / chase at fill)
                pcl = day.c[i, r["em"] - 1] if day.printed[i, r["em"] - 1] else np.nan
                r["fill_vs_prev"] = float(r["entry"] / pcl - 1.0) if np.isfinite(pcl) else np.nan
            else:
                r["half_spread"] = r["amihud"] = r["fill_vs_prev"] = np.nan
            r["min_of_day"] = r["em"] - L.M_OPEN
            hh, mi = divmod(r["em"] - 1 + L.GRID_START, 60)
            y, mo, d = (int(x) for x in date.split("-"))
            ts = datetime(y, mo, d, hh, mi, tzinfo=ET).timestamp()
            X = E.features_for(r["sym"], np.array([ts]))[0]
            for nm, v in zip(FN, X):
                r["cat_" + nm] = float(v)
        # same-day sequence (only legs that exited before this entry)
        for strat in ("R4", "C37F"):
            kk = sorted((k for k in ks if rows[k]["strat"] == strat), key=lambda k: rows[k]["em"])
            for q, k in enumerate(kk):
                prev = [rows[p] for p in kk[:q] if rows[p]["xm"] < rows[k]["em"]]
                rows[k]["seq"] = q
                rows[k]["day_pnl_before"] = float(sum(p["g10k"] for p in prev))
                rows[k]["prev_loss"] = float(prev[-1]["g10k"] < 0) if prev else 0.0
                rows[k]["same_sym_before"] = float(any(p["sym"] == rows[k]["sym"] for p in prev))
        if n % 50 == 0:
            print(n, date, round(time.time() - t0), flush=True)
    with open(OUT, "wb") as f:
        pickle.dump(rows, f)
    print("done", len(rows), "missing", miss, round(time.time() - t0), OUT)


if __name__ == "__main__":
    main()
