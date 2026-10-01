"""PESSIMISM-AUDIT check 2 -- is the minute-open / minute-close fill biased?

Engines fill entries at the NEXT 1-minute bar's OPEN and exits at a bar's
CLOSE. On the 1-second tape (wide universe, cost1 sample) compare:
  entry: minute open  vs VWAP of that minute's first 10 seconds
  exit : minute close vs VWAP of that minute's last 10 seconds
signed so POSITIVE = the convention is OPTIMISTIC for us (we bought
cheaper / sold dearer than the 10-second VWAP), NEGATIVE = pessimistic.
Conditioned on the signal: prior minute up / prior 5 minutes in the top
decile (momentum entries), prior minute down (reversal entries).
Bid-ask bounce: P(open > prev close), P(open < prev close) by signal.

python plan/pa_fillbias.py [--n 300]
"""
import sys, json, gzip, argparse
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cr_cost as CC

ET = ZoneInfo("America/New_York")
OUT = HERE / "pa_out"
OUT.mkdir(exist_ok=True)


def open_ms(date):
    return int(datetime.combine(datetime.strptime(date, "%Y-%m-%d").date(),
                                dtime(9, 30), ET).timestamp() * 1000)


def one(tf, date):
    rows = json.load(gzip.open(tf))["rows"]
    if len(rows) < 2000:
        return None
    a = np.array(rows, dtype=float)
    sec = ((a[:, 0] - open_ms(date)) // 1000).astype(np.int64)
    k = (sec >= 0) & (sec < 390 * 60)
    a, sec = a[k], sec[k]
    mn = sec // 60
    so = sec % 60
    tp = (a[:, 2] + a[:, 3] + a[:, 4]) / 3.0
    v = a[:, 5]
    out = []
    # per-minute aggregates
    first = np.full(390, -1)
    last = np.full(390, -1)
    for j in range(len(a)):
        m = mn[j]
        if first[m] < 0:
            first[m] = j
        last[m] = j
    mo = np.where(first >= 0, a[np.maximum(first, 0), 1], np.nan)
    mc = np.where(last >= 0, a[np.maximum(last, 0), 4], np.nan)
    pv_f = np.zeros(390); v_f = np.zeros(390)
    pv_l = np.zeros(390); v_l = np.zeros(390)
    e = so < 10
    np.add.at(pv_f, mn[e], tp[e] * v[e]); np.add.at(v_f, mn[e], v[e])
    e = so >= 50
    np.add.at(pv_l, mn[e], tp[e] * v[e]); np.add.at(v_l, mn[e], v[e])
    with np.errstate(invalid="ignore", divide="ignore"):
        vwf = pv_f / v_f
        vwl = pv_l / v_l
    for m in range(6, 389):
        if not (np.isfinite(mo[m]) and np.isfinite(vwf[m]) and
                np.isfinite(mc[m - 1]) and np.isfinite(mc[m - 2]) and
                np.isfinite(mc[m - 6])):
            continue
        r1 = mc[m - 1] / mc[m - 2] - 1
        r5 = mc[m - 1] / mc[m - 6] - 1
        ent = 1e4 * (vwf[m] - mo[m]) / mo[m]        # + = buy optimistic
        ex = 1e4 * (mc[m] - vwl[m]) / vwl[m] if np.isfinite(vwl[m]) \
            else np.nan                               # + = sell optimistic
        bounce = np.sign(mo[m] - mc[m - 1])
        out.append((m, r1, r5, ent, ex, bounce))
    return out


def summ(x):
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return None
    return dict(n=int(len(x)), median=round(float(np.median(x)), 3),
                mean=round(float(x.mean()), 3),
                trim_mean=round(float(np.mean(np.clip(
                    x, *np.percentile(x, [1, 99])))), 3),
                se=round(float(x.std(ddof=1) / np.sqrt(len(x))), 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    a = ap.parse_args()
    fs = sorted(CC.CDIR.glob("*.npz"))
    sel = fs[::max(1, len(fs) // a.n)][:a.n]
    rec = []
    for f in sel:
        s, d = f.name[:-4].split("_", 1)
        tf = CC.XDIR / f"{s}_{d}.json.gz"
        if tf.exists():
            r = one(tf, d)
            if r:
                rec += r
    A = np.array(rec, dtype=float)
    M, R1, R5, EN, EX, BO = A.T
    q90 = np.nanpercentile(R5, 90)
    res = dict(n_minutes=int(len(A)), symdays=len(sel))
    conds = {"all": np.ones(len(A), bool), "prior_min_up": R1 > 0,
             "prior_min_down": R1 < 0, "prior5_top_decile": R5 >= q90,
             "open_0931_1030": M < 60,
             "open_0931_1030_prior5_top": (M < 60) & (R5 >= q90)}
    for nm, k in conds.items():
        res[nm] = dict(
            entry_buy_open_vs_vwap10=summ(EN[k]),
            exit_sell_close_vs_vwap_last10=summ(EX[k]),
            p_open_uptick=round(float((BO[k] > 0).mean()), 4),
            p_open_downtick=round(float((BO[k] < 0).mean()), 4))
    print(json.dumps(res, indent=1))
    json.dump(res, open(OUT / "fillbias.json", "w"), indent=1)


if __name__ == "__main__":
    main()
