"""CLOSE-MOMENTUM (2026-09-16), hypothesis 1(a): the published market
intraday momentum effect on the HALAL INDEX ETFs.

Gao, Han, Li, Zhou (2018, JFE) report that the market's FIRST half-hour
return (09:30-10:00) and its SECOND-TO-LAST half-hour return (15:00-15:30)
both predict the LAST half-hour return (15:30-16:00), most strongly on
high-volatility / high-volume days. The halal-compatible instruments for
an index-level version are the Sharia index ETFs.

This is the cleanest available test of the published claim: one series,
no cross-sectional selection, no universe construction, nothing fitted.
If the effect is not here, the single-name versions in plan/cm_single.py
are not a replication of anything -- they are a fresh search.

MEASURES (grid index k = ET minute - 240)
  r_first  = c[359] / o[330] - 1          09:30 open -> 10:00
  r_2last  = c[689] / c[659] - 1          14:59 close -> 15:29 close
  r_last   = c[719] / c[689] - 1          15:29 close -> 15:59 close
  traded   = c[X]   / o[690] - 1          15:30 OPEN -> exit bar X's close
             with X in {710 (15:50), 715 (15:55), 719 (15:59)}

The decision is taken at minute 689 and reads nothing after it; the fill
is the 15:30 bar's open. SPY is fetched and reported as the replication
reference only -- it is NOT halal and is never part of a tradeable row.

Usage:  python plan/cm_etf_study.py
Writes: data/massive/cm/etf_study.json
"""
import gzip
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import cm_lib as L                                            # noqa: E402

HALAL = ["SPUS", "HLAL", "SPSK", "SPRE", "UMMA", "SPWO"]
REF = ["SPY"]
ALL = HALAL + REF
EXITS = {"15:50": L.idx("15:50"), "15:55": L.idx("15:55"),
         "15:59": L.idx("15:59")}
K_OPEN = L.idx("09:30")          # 330
K_10 = L.idx("10:00") - 1        # 359
K_1500 = L.idx("15:00") - 1      # 659
K_1530 = L.idx("15:30") - 1      # 689
K_FILL = L.idx("15:30")          # 690


def load_series():
    """{sym: {date: dict of measures}} from data/massive/m1etf."""
    dates = L.study_dates()
    prev = {}
    out = {s: {} for s in ALL}
    pc = {}
    for d in dates:
        r = json.loads(gzip.open(L.GD / f"{d}.json.gz", "rt").read())
        m = {x["T"]: x for x in r}
        pc[d] = {s: (m[s]["c"] if s in m else np.nan) for s in ALL}
    prevmap = {}
    for i, d in enumerate(dates):
        prevmap[d] = pc[dates[i - 1]] if i else {s: np.nan for s in ALL}
    for d in dates:
        for s in ALL:
            f = L.M1ETF / f"{s}_{d}.csv"
            if not f.exists():
                continue
            b = L._read_csv_grid(f, d)
            if b is None:
                continue
            o, h, lo, c, v = b
            cf = L._ffill(c[None, :])[0]
            if not (np.isfinite(o[K_OPEN]) and np.isfinite(cf[K_10])
                    and np.isfinite(cf[K_1500]) and np.isfinite(cf[K_1530])
                    and np.isfinite(cf[L.idx("15:59")])):
                continue
            row = {
                "r_first": c if False else float(cf[K_10] / o[K_OPEN] - 1.0),
                "r_2last": float(cf[K_1530] / cf[K_1500] - 1.0),
                "r_last": float(cf[L.idx("15:59")] / cf[K_1530] - 1.0),
                "fill_open": float(o[K_FILL]) if np.isfinite(o[K_FILL])
                else float(cf[K_FILL]),
                "gap": float(o[K_OPEN] / prevmap[d][s] - 1.0)
                if np.isfinite(prevmap[d].get(s, np.nan)) else 0.0,
                "dayvol": float(np.nansum(v[K_OPEN:L.RTH_HI])),
                "sigma_day": float(np.nanstd(np.diff(np.log(
                    np.maximum(cf[K_OPEN:K_1530 + 1], 1e-9))))),
                "px1530": float(cf[K_1530]),
            }
            for lab, x in EXITS.items():
                row["exit_" + lab] = float(cf[x]) if np.isfinite(cf[x]) else \
                    float(cf[K_1530])
            out[s][d] = row
    return dates, out


# --------------------------------------------------------------- stats
def ols_t(x, y):
    """slope, Newey-West(5) t-stat, R^2, n."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    k = np.isfinite(x) & np.isfinite(y)
    x, y = x[k], y[k]
    n = x.size
    if n < 30:
        return dict(n=n, slope=np.nan, t=np.nan, r2=np.nan)
    X = np.c_[np.ones(n), x]
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    XtXi = np.linalg.inv(X.T @ X)
    # Newey-West with 5 lags
    S = (X * e[:, None]).T @ (X * e[:, None])
    for lag in range(1, 6):
        w = 1.0 - lag / 6.0
        A = (X[lag:] * e[lag:, None]).T @ (X[:-lag] * e[:-lag, None])
        S += w * (A + A.T)
    V = XtXi @ S @ XtXi
    t = b[1] / np.sqrt(max(V[1, 1], 1e-30))
    ss = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - float(np.sum(e ** 2)) / ss if ss > 0 else np.nan
    return dict(n=int(n), slope=round(float(b[1]), 4), t=round(float(t), 2),
                r2=round(float(r2), 5))


def trade_rows(sym, ser, dates, signal_fn, label, exit_lab="15:59",
               tickets=15000.0):
    """One $15k ticket a day when `signal_fn(row) > 0`; entry at the 15:30
    bar's open + 10 bps, exit at the stated bar's close - 10 bps."""
    trades = []
    for d in dates:
        row = ser.get(d)
        if row is None:
            continue
        s = signal_fn(row)
        if not np.isfinite(s) or s <= 0:
            continue
        px_in = row["fill_open"]
        px_out = row["exit_" + exit_lab]
        if not (px_in > 0 and px_out > 0):
            continue
        sh = tickets / px_in
        c_in = L.cost_frac(L.K_FILL if False else K_FILL)
        c_out = L.cost_frac(EXITS[exit_lab])
        cost = sh * px_in * (1 + c_in)
        pnl = sh * px_out * (1 - c_out) - cost
        trades.append({"date": d, "sym": sym, "pnl": pnl,
                       "gross": sh * (px_out - px_in), "notional": cost,
                       "m_in": K_FILL, "m_out": EXITS[exit_lab],
                       "px_in": px_in, "px_out": px_out, "sh": sh,
                       "hold": EXITS[exit_lab] - K_FILL, "i": 0,
                       "m_dec": K_1530})
    return L.split_rows(trades, dates, label)


def main():
    dates, ser = load_series()
    res = {"dates": len(dates), "coverage": {s: len(ser[s]) for s in ALL}}
    print("coverage:", res["coverage"], flush=True)

    # ---- 1. the published predictive regressions, per symbol
    reg = {}
    for s in ALL:
        d = sorted(ser[s])
        if len(d) < 60:
            continue
        rf = np.array([ser[s][x]["r_first"] for x in d])
        r2 = np.array([ser[s][x]["r_2last"] for x in d])
        rl = np.array([ser[s][x]["r_last"] for x in d])
        sig = np.array([ser[s][x]["sigma_day"] for x in d])
        hi = sig >= np.median(sig)
        reg[s] = {
            "r_last ~ r_first": ols_t(rf, rl),
            "r_last ~ r_2last": ols_t(r2, rl),
            "r_last ~ r_first (high-vol half)": ols_t(rf[hi], rl[hi]),
            "r_last ~ r_2last (high-vol half)": ols_t(r2[hi], rl[hi]),
            "mean_r_last_bps": round(float(rl.mean() * 1e4), 2),
            "mean_r_last_bps | r_first>0": round(
                float(rl[rf > 0].mean() * 1e4), 2) if (rf > 0).any() else None,
            "mean_r_last_bps | r_first<0": round(
                float(rl[rf < 0].mean() * 1e4), 2) if (rf < 0).any() else None,
            "mean_r_last_bps | r_2last>0": round(
                float(rl[r2 > 0].mean() * 1e4), 2) if (r2 > 0).any() else None,
            "mean_r_last_bps | r_2last<0": round(
                float(rl[r2 < 0].mean() * 1e4), 2) if (r2 < 0).any() else None,
            "sign_match_first": round(float(np.mean(
                np.sign(rf) == np.sign(rl))), 4),
            "sign_match_2last": round(float(np.mean(
                np.sign(r2) == np.sign(rl))), 4),
        }
        # split-sample: is the sign the same in Y1 and Y2?
        for lab, keep in (("y1", [L.split_of(x) == 0 for x in d]),
                          ("y2", [L.split_of(x) == 1 for x in d])):
            k = np.array(keep)
            if k.sum() >= 60:
                reg[s][f"r_last ~ r_first [{lab}]"] = ols_t(rf[k], rl[k])
                reg[s][f"r_last ~ r_2last [{lab}]"] = ols_t(r2[k], rl[k])
    res["regressions"] = reg

    # ---- 2. the tradeable versions
    sigs = {
        "always": lambda r: 1.0,
        "first>0": lambda r: r["r_first"],
        "2last>0": lambda r: r["r_2last"],
        "both>0": lambda r: min(r["r_first"], r["r_2last"]),
        "sum>0": lambda r: r["r_first"] + r["r_2last"],
        "first<0 (inverted)": lambda r: -r["r_first"],
        "2last<0 (inverted)": lambda r: -r["r_2last"],
    }
    rows = {}
    for s in ALL:
        if len(ser[s]) < 60:
            continue
        for lab, fn in sigs.items():
            for ex in EXITS:
                rows[f"{s}|{lab}|{ex}"] = trade_rows(
                    s, ser[s], dates, fn, f"{s}|{lab}|{ex}", exit_lab=ex)
    res["trade_rows"] = rows

    # ---- 3. market-timing variant: gate SPUS/HLAL on the SPUS signal
    gate = {}
    for s in ("SPUS", "HLAL"):
        for gsym in ("SPUS", "HLAL"):
            def fn(r, d=None, gs=gsym):
                return np.nan
        for lab in ("gate_SPUS_first", "gate_SPUS_2last"):
            key = "r_first" if lab.endswith("first") else "r_2last"
            tr = []
            for d in dates:
                g = ser["SPUS"].get(d)
                row = ser[s].get(d)
                if g is None or row is None or g[key] <= 0:
                    continue
                sh = 15000.0 / row["fill_open"]
                cost = sh * row["fill_open"] * (1 + L.cost_frac(K_FILL))
                pnl = sh * row["exit_15:59"] * (1 - L.cost_frac(EXITS["15:59"])) - cost
                tr.append({"date": d, "sym": s, "pnl": pnl,
                           "gross": sh * (row["exit_15:59"] - row["fill_open"]),
                           "notional": cost, "m_in": K_FILL,
                           "m_out": EXITS["15:59"], "px_in": row["fill_open"],
                           "px_out": row["exit_15:59"], "sh": sh,
                           "hold": EXITS["15:59"] - K_FILL, "i": 0,
                           "m_dec": K_1530})
            gate[f"{s}|{lab}|15:59"] = L.split_rows(tr, dates,
                                                    f"{s}|{lab}|15:59")
    res["gated_rows"] = gate

    L.write_json("etf_study.json", res)
    # ---- console digest
    print("\n== predictive regressions (r_last on the two signals) ==")
    for s in ALL:
        if s not in reg:
            continue
        a = reg[s]["r_last ~ r_first"]
        b = reg[s]["r_last ~ r_2last"]
        print(f"{s:5s} n={a['n']:3d}  first: b={a['slope']:+.4f} t={a['t']:+.2f} "
              f"R2={a['r2']:.5f}   2last: b={b['slope']:+.4f} t={b['t']:+.2f} "
              f"R2={b['r2']:.5f}   mean r_last={reg[s]['mean_r_last_bps']:+.2f}bp")
    print("\n== tradeable rows, exit 15:59 ==")
    for k, v in rows.items():
        if not k.endswith("15:59"):
            continue
        a = v["all"]
        print(f"{k:32s} n={a['tickets']:4d} ${a['per_ticket']:+8.2f}/tkt "
              f"${a['per_month']:+9.2f}/mo  y1 ${v['y1']['per_ticket']:+7.2f} "
              f"y2 ${v['y2']['per_ticket']:+7.2f}")
    print("\nwrote", L.OUT / "etf_study.json", flush=True)


if __name__ == "__main__":
    main()
