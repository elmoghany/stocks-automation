"""PESSIMISM-AUDIT check 1 -- is the square-root impact term too big?

Part A: recompute impact on the SAME sample cr_out/_decomp.py used
(cost1 symbol-days, fixed minutes, $15k), with the textbook inputs:
    impact_daily = Y * sigma_d * sqrt(N / ADV20)
    ADV20   = mean prior-20-session dollar volume (v * c, gd grouped daily)
    sigma_d = stdev of prior-20-session close-to-close log returns
strictly before the trade date (causal). Same Y = 1.0.
Also the variance ratio sigma_1min*sqrt(390) / sigma_d (microstructure
noise inflating the intraday sigma the window model uses).

Part B: empirical upper bound from the 1-second tape. For seconds whose
dollar volume >= $15k vs seconds < $15k (and > 0) in the SAME symbol and
minute: signed move from the pre-bar price (last close before the bar)
to the price k seconds after the bar, sign = tick rule of the bar vs the
pre-bar price. big-minus-small (paired by name/minute) = extra move that
comes with a >= $15k print; an UPPER bound on what our order causes (big
prints also carry information).

python plan/pa_impact.py [--n 1200]
"""
import sys, json, gzip, math, argparse, collections
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cr_cost as CC

ET = ZoneInfo("America/New_York")
GD = CC.ROOT / "data" / "massive" / "gd"
OUT = HERE / "pa_out"
OUT.mkdir(exist_ok=True)
N = 15000.0
MINS = [5, 10, 20, 35, 60, 90, 120, 180, 240, 300, 350]


def load_gd(dates_needed, syms):
    """sym -> {date: (c, dv)} for the given symbols over all gd files."""
    out = collections.defaultdict(dict)
    files = sorted(GD.glob("*.json.gz"))
    for f in files:
        d = f.name[:10]
        try:
            rows = json.load(gzip.open(f))
        except Exception:
            continue
        for r in rows:
            s = r.get("T")
            if s in syms and r.get("c") and r.get("v"):
                out[s][d] = (float(r["c"]), float(r["v"]) * float(r["c"]))
    return out


def daily_inputs(g, sym, date, look=20):
    ser = g.get(sym, {})
    ds = sorted(x for x in ser if x < date)[-(look + 1):]
    if len(ds) < look + 1:
        return None, None
    c = np.array([ser[x][0] for x in ds])
    dv = np.array([ser[x][1] for x in ds[1:]])
    r = np.diff(np.log(c))
    return float(dv.mean()), float(np.std(r, ddof=1))


def part_a(sel, g):
    cm = CC.CostModel()
    rec = []
    vr = []
    for f in sel:
        s, d = f.name[:-4].split("_", 1)
        adv, sd = daily_inputs(g, s, d)
        dd = cm._day(s, d)
        if dd is not None and sd:
            c = dd.c[dd.c > 0]
            if len(c) > 100:
                r1 = np.diff(np.log(c))
                vr.append(float(np.std(r1, ddof=1)) * math.sqrt(390) / sd)
        for m in MINS:
            t = dtime((CC.MIN_M + m) // 60, (CC.MIN_M + m) % 60)
            h, i, tier = cm.parts(s, d, t, N)
            idaily = (1e4 * sd * math.sqrt(N / adv)) if adv else np.nan
            part10 = (N / dd.dv_win[CC.mkey(t)]) if (
                dd is not None and dd.dv_win[CC.mkey(t)] > 0) else np.nan
            rec.append((m, h, i, idaily, N / adv if adv else np.nan,
                        part10))
    a = np.array(rec, dtype=float)
    ok = np.isfinite(a[:, 3])
    a = a[ok]
    M, H, I, D, P, P10 = a.T

    def st(x):
        x = x[np.isfinite(x)]
        return dict(median=round(float(np.median(x)), 3),
                    mean=round(float(x.mean()), 3),
                    p75=round(float(np.percentile(x, 75)), 3),
                    p90=round(float(np.percentile(x, 90)), 3))
    out = dict(n=int(len(a)), symdays=len(sel),
               half_spread=st(H), impact_window=st(I),
               impact_daily=st(D),
               participation_daily=st(P), participation_10min=st(P10),
               frac_impact_daily_gt5=round(float((D > 5).mean()), 4),
               frac_impact_window_gt5=round(float((I > 5).mean()), 4),
               total_window=st(H + I), total_daily=st(H + D),
               frac_total_daily_gt10=round(float(((H + D) > 10).mean()), 4),
               frac_total_window_gt10=round(float(((H + I) > 10).mean()), 4),
               variance_ratio_sig1m_sqrt390_over_sigd=st(np.array(vr)))
    bt = {}
    for lo, hi, nm in ((0, 16, "09:30-09:45"), (16, 61, "09:46-10:30"),
                       (61, 181, "10:31-12:30"), (181, 400, "12:31-16:00")):
        k = (M >= lo) & (M < hi)
        bt[nm] = dict(n=int(k.sum()), half=round(float(np.median(H[k])), 2),
                      imp_window=round(float(np.median(I[k])), 2),
                      imp_daily=round(float(np.median(D[k])), 2),
                      total_daily=round(float(np.median((H + D)[k])), 2))
    out["by_time"] = bt
    for y in (0.3, 0.5, 1.0):
        t_ = H + y * D
        out[f"total_daily_Y{y}"] = dict(
            median=round(float(np.median(t_)), 3),
            mean=round(float(t_.mean()), 3))
    return out


def open_ms(date):
    return int(datetime.combine(datetime.strptime(date, "%Y-%m-%d").date(),
                                dtime(9, 30), ET).timestamp() * 1000)


def part_b(sel, ks=(1, 5, 10, 30), maxn=None):
    """paired big-vs-small signed moves, by name/minute."""
    diffs = {k: [] for k in ks}
    absd = {k: [] for k in ks}
    bigm = {k: [] for k in ks}
    smlm = {k: [] for k in ks}
    nbig = 0
    mins = []
    for f in sel:
        s, d = f.name[:-4].split("_", 1)
        tf = CC.XDIR / f"{s}_{d}.json.gz"
        if not tf.exists():
            continue
        try:
            rows = json.load(gzip.open(tf))["rows"]
        except Exception:
            continue
        if len(rows) < 500:
            continue
        a = np.array(rows, dtype=float)
        t0 = open_ms(d)
        sec = ((a[:, 0] - t0) // 1000).astype(np.int64)
        k_ = (sec >= 0) & (sec < 390 * 60)
        a, sec = a[k_], sec[k_]
        if len(a) < 500:
            continue
        # dense per-second last-price series (forward filled)
        px = np.full(390 * 60, np.nan)
        px[sec] = a[:, 4]
        idx = np.where(np.isfinite(px), np.arange(len(px)), 0)
        np.maximum.accumulate(idx, out=idx)
        pxf = px[idx]
        dv = a[:, 5] * (a[:, 1] + a[:, 2] + a[:, 3] + a[:, 4]) / 4.0
        # pre-bar price = previous printed second's close
        pre = np.concatenate([[np.nan], a[:-1, 4]])
        sgn = np.sign(a[:, 4] - pre)
        z = sgn == 0
        sgn[z] = np.sign(a[z, 4] - a[z, 1])
        good = np.isfinite(pre) & (sgn != 0) & (sec > 60) & \
            (sec < 390 * 60 - 31)
        minute = sec // 60
        bucket = collections.defaultdict(lambda: ([], []))
        fut = {}
        for k in ks:
            fut[k] = pxf[np.minimum(sec + k, len(pxf) - 1)]
        for j in np.where(good)[0]:
            b = bucket[minute[j]]
            if dv[j] >= N:
                if maxn is None or a[j, 6] <= maxn:
                    b[0].append(j)
            else:
                b[1].append(j)
        for mnt, (bj, sj) in bucket.items():
            if not bj or not sj:
                continue
            nbig += len(bj)
            mins.append(int(mnt))
            bj = np.array(bj)
            sj = np.array(sj)
            for k in ks:
                mb = 1e4 * sgn[bj] * (fut[k][bj] - pre[bj]) / pre[bj]
                ms = 1e4 * sgn[sj] * (fut[k][sj] - pre[sj]) / pre[sj]
                diffs[k].append(float(mb.mean() - ms.mean()))
                bigm[k].append(float(mb.mean()))
                smlm[k].append(float(ms.mean()))
                ab = 1e4 * np.abs(fut[k][bj] - pre[bj]) / pre[bj]
                as_ = 1e4 * np.abs(fut[k][sj] - pre[sj]) / pre[sj]
                absd[k].append(float(ab.mean() - as_.mean()))
    res = dict(n_minutes_paired=len(diffs[ks[0]]), n_big_seconds=nbig)
    for k in ks:
        x = np.array(diffs[k])
        res[f"k{k}s"] = dict(
            signed_big_minus_small_median=round(float(np.median(x)), 3),
            signed_big_minus_small_mean=round(float(x.mean()), 3),
            se=round(float(x.std(ddof=1) / math.sqrt(len(x))), 3),
            signed_big_median=round(float(np.median(bigm[k])), 3),
            signed_small_median=round(float(np.median(smlm[k])), 3),
            signed_big_mean=round(float(np.mean(bigm[k])), 3),
            signed_small_mean=round(float(np.mean(smlm[k])), 3),
            signed_big_mean_0930_1030=round(float(np.mean(
                np.array(bigm[k])[np.array(mins) < 60])), 3),
            big_minus_small_mean_0930_1030=round(float(np.mean(
                x[np.array(mins) < 60])), 3),
            abs_big_minus_small_median=round(float(np.median(absd[k])), 3))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1200)
    ap.add_argument("--nb", type=int, default=300)
    ap.add_argument("--only-b", action="store_true")
    a = ap.parse_args()
    fs = sorted(CC.CDIR.glob("*.npz"))
    step = max(1, len(fs) // a.n)
    sel = fs[::step][:a.n]
    syms = {f.name[:-4].split("_", 1)[0] for f in sel}
    if a.only_b:
        prev = json.load(open(OUT / "impact.json"))
        ra = prev["part_a"]
    else:
        g = load_gd(None, syms)
        ra = part_a(sel, g)
    print(json.dumps(ra, indent=1), flush=True)
    selb = sel[::max(1, len(sel) // a.nb)][:a.nb]
    rb = part_b(selb)
    print(json.dumps(rb, indent=1))
    rb["few_prints_n_le_3"] = part_b(selb, maxn=3)
    print(json.dumps(rb["few_prints_n_le_3"], indent=1))
    json.dump(dict(part_a=ra, part_b=rb), open(OUT / "impact.json", "w"),
              indent=1)


if __name__ == "__main__":
    main()
