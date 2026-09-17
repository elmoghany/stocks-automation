"""CATALYST-MINER (2026-09-16): the labelled $15,000-ticket table with
the catalyst block appended.

One row per (date, symbol, decision time) on the causal wide universe
(plan/rl2/out/feat/*.npz, 448 dates, 191 names).  The PRICE block, the
fills, the size cap, the cost ladder and the labels are exactly
plan/wn_table.day_block -- nothing is re-derived -- with the decision
grid replaced by the mandate's six times (09:35 10:00 10:30 11:00 13:00
15:30).  The CATALYST block (plan/cat_events.features_for) is evaluated
at the decision minute's wall-clock instant, so an event published at
09:34:59 is visible at 09:35 and one published at 09:35:01 is not.

Output data/massive/cat/table.npz is byte-compatible with
plan/wn_lib.Table (same keys), so every wide-net summariser and control
runs on it unchanged.  `features` = the 32 wide-net columns followed by
the NF catalyst columns; `n_base` records the split point.

Also writes data/massive/cat/table_gap.npz for the +10% gapper pool
under RS_CROSS (plan/cm_rows.py rows_gap.npz): the CM row's 17 causal
features + the catalyst block, with the ticket priced from px_in /
px_out at 10 bps a side exactly as plan/cm_lib.trade_day does.  Pool
MEMBERSHIP there is still outcome-conditioned; it is reported as the
mandate asked, labelled as an upper bound.

Usage:  python plan/cat_table.py [--smoke 20] [--universe wide|gap|both]
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cat_lib as C                                           # noqa: E402
import cat_events as E                                        # noqa: E402
import wn_table as W                                          # noqa: E402

DEC_ET = ["09:35", "10:00", "10:30", "11:00", "13:00", "15:30"]
FEAT = HERE / "rl2" / "out" / "feat"


def build_wide(smoke=0):
    # re-point wn_table's decision grid (module globals read by day_block)
    W.DEC_ET = DEC_ET
    W.DEC_T = np.array([W.et_to_step(x) for x in DEC_ET], np.int32)
    W.NT = len(W.DEC_T)
    sic2 = W.load_sic2()
    earn = W.load_earn()
    cal = W.load_earn_rh()
    files = sorted(FEAT.glob("*.npz"))
    all_dates = [p.stem for p in files]
    prevmap = {d: (all_dates[i - 1] if i else None) for i, d in enumerate(all_dates)}
    if smoke:
        files = files[:smoke]
    cols = {k: [] for k in ("date_i", "sym_i", "dec_i", "notional", "printed",
                            "printed_m", "fill_px")}
    for h in W.HNAMES:
        cols["pnl_" + h] = []
        cols["ok_" + h] = []
    Fl, dates, syms_all, sidx = [], [], [], {}
    t0 = time.time()
    dec_secs = {d: [C.decision_ts(d, x).timestamp() for x in DEC_ET] for d in all_dates}
    for di, p in enumerate(files):
        date = p.stem
        z = np.load(p, allow_pickle=False)
        b = W.day_block(date, z, sic2, earn, cal, prevmap.get(date))
        ss = b["syms"]
        S = len(ss)
        for s in ss:
            if s not in sidx:
                sidx[s] = len(syms_all)
                syms_all.append(s)
        si = np.array([sidx[s] for s in ss], np.int32)
        NT = len(DEC_ET)
        nt, ns = np.mgrid[0:NT, 0:S]
        # catalyst block: [NT, S, NF]
        ts = np.array(dec_secs[date], np.float64)
        cat = np.zeros((NT, S, E.NF), np.float32)
        for j, s in enumerate(ss):
            cat[:, j, :] = E.features_for(s, ts)
        Fl.append(np.concatenate([b["F"], cat], axis=2).reshape(NT * S, -1))
        cols["date_i"].append(np.full(NT * S, di, np.int32))
        cols["sym_i"].append(np.tile(si, NT))
        cols["dec_i"].append(nt.reshape(-1).astype(np.int8))
        cols["notional"].append(b["notional"].reshape(-1))
        cols["printed"].append(b["printed"].reshape(-1))
        cols["printed_m"].append(b["printed_m"].reshape(-1))
        cols["fill_px"].append(b["fill_px"].reshape(-1))
        for hi, hn in enumerate(W.HNAMES):
            cols["pnl_" + hn].append(b["pnl"][:, :, hi].reshape(-1))
            cols["ok_" + hn].append(b["ok"][:, :, hi].reshape(-1))
        dates.append(date)
        if (di + 1) % 100 == 0:
            print(f"  [{di+1}/{len(files)}] {date} {time.time()-t0:.0f}s", flush=True)
    out = {k: np.concatenate(v) for k, v in cols.items()}
    out["F"] = np.concatenate(Fl).astype(np.float32)
    out["dates"] = np.array(dates)
    out["syms"] = np.array(syms_all)
    out["features"] = np.array(list(W.FEATURES) + E.feature_names())
    out["n_base"] = np.array([len(W.FEATURES)])
    out["dec_et"] = np.array(DEC_ET)
    out["horizons"] = np.array(W.HNAMES)
    f = C.OUT / ("table_smoke.npz" if smoke else "table.npz")
    np.savez_compressed(f, **out)
    print(json.dumps({"file": str(f), "rows": int(len(out["date_i"])),
                      "dates": len(dates), "symbols": len(syms_all),
                      "eligible": int(out["printed_m"].sum()),
                      "features": len(out["features"]), "n_base": len(W.FEATURES),
                      "secs": round(time.time() - t0, 1)}, indent=1), flush=True)


# ------------------------------------------------------------ gapper pool
GAP_DEC = ["10:00", "11:00", "13:00", "15:30"]
GAP_EXIT = {"10:00": ["12:00", "13:00"], "11:00": ["13:00", "14:00"],
            "13:00": ["15:00", "15:30"], "15:30": ["15:59"]}
FEE = 10.0 / 1e4


def build_gap():
    z = np.load(C.ROOT / "data" / "massive" / "cm" / "rows_gap.npz", allow_pickle=False)
    dates = [str(x) for x in z["dates"]]
    syms = [str(x) for x in z["syms"]]
    dec = [str(x) for x in z["dec"]]
    exits = [str(x) for x in z["exits"]]
    keep = np.isin(z["dec_i"], [dec.index(d) for d in GAP_DEC])
    idx = np.flatnonzero(keep)
    date_i = z["date_i"][idx]
    sym_i = z["sym_i"][idx]
    dec_i = z["dec_i"][idx]
    F = z["F"][idx]
    px_in = z["px_in"][idx].astype(np.float64)
    volcap = z["volcap"][idx].astype(np.float64)
    printed_m = z["printed_m"][idx]
    px_out = z["px_out"][idx].astype(np.float64)
    # ticket economics, identical to cm_lib.trade_day: notional = min(15k, volcap*px_in)
    with np.errstate(all="ignore"):
        notion = np.where(np.isfinite(px_in) & (px_in > 0),
                          np.minimum(15000.0, volcap * px_in), np.nan)
    live = printed_m & np.isfinite(notion) & (notion >= 500.0)
    # decision instant = fill label minus one minute (cm convention)
    t0 = time.time()
    cat = np.zeros((len(idx), E.NF), np.float32)
    dsec = {}
    for r in range(len(idx)):
        d, lab = dates[date_i[r]], dec[dec_i[r]]
        k = (d, lab)
        if k not in dsec:
            h, m = (int(x) for x in lab.split(":"))
            dsec[k] = C.decision_ts(d, f"{h:02d}:{m:02d}").timestamp() - 60.0
    # group by symbol for speed
    order = np.argsort(sym_i, kind="stable")
    st = 0
    while st < len(order):
        s = sym_i[order[st]]
        en = st
        while en < len(order) and sym_i[order[en]] == s:
            en += 1
        rows = order[st:en]
        ts = np.array([dsec[(dates[date_i[r]], dec[dec_i[r]])] for r in rows])
        cat[rows] = E.features_for(syms[s], ts)
        st = en
    pnl = {}
    ok = {}
    for lab in GAP_DEC:
        for ex in GAP_EXIT[lab]:
            key = f"{lab}->{ex}"
            po = px_out[:, exits.index(ex)]
            with np.errstate(all="ignore"):
                ret = (po * (1 - FEE)) / (px_in * (1 + FEE)) - 1.0
            sel = (dec_i == dec.index(lab)) & live & np.isfinite(po) & (po > 0)
            pnl[key] = np.where(sel, np.nan_to_num(notion) * ret, 0.0).astype(np.float32)
            ok[key] = sel
    out = dict(date_i=date_i, sym_i=sym_i, dec_i=dec_i.astype(np.int8),
               F=np.concatenate([F, cat], axis=1).astype(np.float32),
               notional=np.nan_to_num(notion), printed=live, printed_m=printed_m,
               fill_px=np.nan_to_num(px_in), dates=np.array(dates), syms=np.array(syms),
               features=np.array([str(x) for x in z["features"]] + E.feature_names()),
               n_base=np.array([len(z["features"])]), dec_et=np.array(dec),
               exit_keys=np.array(list(pnl)))
    for k in pnl:
        out["pnl_" + k] = pnl[k]
        out["ok_" + k] = ok[k]
    f = C.OUT / "table_gap.npz"
    np.savez_compressed(f, **out)
    print(json.dumps({"file": str(f), "rows": int(len(idx)), "live": int(live.sum()),
                      "secs": round(time.time() - t0, 1)}), flush=True)


if __name__ == "__main__":
    a = sys.argv
    sm = int(a[a.index("--smoke") + 1]) if "--smoke" in a else 0
    uni = a[a.index("--universe") + 1] if "--universe" in a else "both"
    if uni in ("wide", "both"):
        build_wide(sm)
    if uni in ("gap", "both") and not sm:
        build_gap()
