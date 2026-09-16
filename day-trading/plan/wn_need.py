"""WIDE-NET (2026-09-16): what would it actually take?

Everything in this study fails the $7,500/month bar, so the most useful
number left is the SIZE OF THE GAP -- expressed not in dollars but in the
only currency a ranker can pay: predictive skill.

METHOD (no model, no fitting, pure measurement).  For a given decision
time and horizon, take the REAL cross-section of $15,000-ticket P&L on
each OOS day.  Build a synthetic score

    score = rho * z(pnl) + sqrt(1 - rho^2) * noise

whose Spearman correlation with the true outcome is a controlled rho.
Buy the top-k names by that score, exactly as plan/wn_oos.py does.  Sweep
rho from 0 (a coin flip) to 1 (perfect foresight) and read off the rho at
which $/month crosses $7,500.

Then locate the strategies this study actually built on the same axis, by
inverting their measured $/ticket through the same curve.  That converts
"we missed" into "we missed by a factor of N in information coefficient",
which is the only form of the answer that tells the next attempt what to
aim at.

Usage: python plan/wn_need.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wn_lib import Table, write_json                      # noqa: E402

RTH = ["09:35", "09:45", "10:00", "10:30", "11:00", "12:00", "13:00",
       "14:00", "15:00"]
RHOS = [0.0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.70, 1.0]
TARGET = 7500.0
NSEED = 12


def curve(t, dec, h, ks=(1, 3, 7), split=1, seeds=NSEED):
    m = t.mask(split=split, dec=dec, h=h)
    idx = np.flatnonzero(m)
    d = t.date_i[idx]
    p = t.pnl[h][idx]
    order = np.argsort(d, kind="stable")
    idx, d, p = idx[order], d[order], p[order]
    st = np.flatnonzero(np.r_[True, d[1:] != d[:-1]])
    en = np.r_[st[1:], len(d)]
    nd = t.ndays(split)
    nmonth = nd / 21.0
    out = {}
    for k in ks:
        rows = []
        for rho in RHOS:
            tot = []
            for s in range(seeds if rho not in (0.0, 1.0) else max(seeds, 20)):
                rng = np.random.default_rng(777 + s)
                acc = 0.0
                ntk = 0
                for a, b in zip(st, en):
                    q = p[a:b]
                    n = b - a
                    if n == 0:
                        continue
                    if rho >= 1.0:
                        sc = q
                    elif rho <= 0.0:
                        sc = rng.standard_normal(n)
                    else:
                        z = (q - q.mean()) / (q.std() or 1.0)
                        sc = rho * z + np.sqrt(1 - rho ** 2) * \
                            rng.standard_normal(n)
                    take = np.argsort(-sc)[:k]
                    acc += float(q[take].sum())
                    ntk += len(take)
                tot.append((acc, ntk))
            a = np.array([x[0] for x in tot])
            nt = np.mean([x[1] for x in tot])
            rows.append({"rho": rho,
                         "per_month": round(float(a.mean() / nmonth), 0),
                         "per_month_sd": round(float(a.std(ddof=1) / nmonth), 0)
                         if len(a) > 1 else 0.0,
                         "per_ticket": round(float(a.mean() / max(nt, 1)), 2),
                         "tickets": int(nt)})
        out[k] = rows
    return out


def needed_rho(rows, target=TARGET):
    xs = [r["rho"] for r in rows]
    ys = [r["per_month"] for r in rows]
    for i in range(1, len(xs)):
        if ys[i] >= target >= ys[i - 1]:
            f = (target - ys[i - 1]) / max(ys[i] - ys[i - 1], 1e-9)
            return round(xs[i - 1] + f * (xs[i] - xs[i - 1]), 3)
    return None if max(ys) < target else round(xs[0], 3)


def rho_of(rows, per_ticket):
    xs = [r["rho"] for r in rows]
    ys = [r["per_ticket"] for r in rows]
    for i in range(1, len(xs)):
        if ys[i] >= per_ticket >= ys[i - 1]:
            f = (per_ticket - ys[i - 1]) / max(ys[i] - ys[i - 1], 1e-9)
            return round(xs[i - 1] + f * (xs[i] - xs[i - 1]), 3)
    return None


def main():
    t = Table()
    rep = {}
    for lab, dec, h in (("09:35 only, 30-min hold", ["09:35"], "h30"),
                        ("09:35 only, 120-min hold", ["09:35"], "h120"),
                        ("all 9 RTH times, 30-min hold", RTH, "h30")):
        c = curve(t, dec, h)
        rep[lab] = c
        print(f"\n=== {lab}  (OOS {t.ndays(1)} days) ===")
        print(f"{'rho':>6} " + "".join(
            f"{('k=%d $/mo' % k):>14}{'  $/tkt':>9}" for k in c))
        for i, rho in enumerate(RHOS):
            line = f"{rho:>6.2f} "
            for k in c:
                r = c[k][i]
                line += f"{r['per_month']:>14,.0f}{r['per_ticket']:>9.1f}"
            print(line)
        for k in c:
            nr = needed_rho(c[k])
            ceil = max(r["per_month"] for r in c[k])
            txt = (f"{nr}" if nr is not None
                   else f"UNREACHABLE (perfect-foresight ceiling "
                        f"${ceil:,.0f}/mo)")
            print(f"  k={k}: rho needed for ${TARGET:,.0f}/month = {txt}")

    # where this study's own strategies sit on the k=1 curve at 09:35/h30
    base = rep["09:35 only, 30-min hold"]
    print("\n=== where the measured strategies sit (k=1, 09:35, h30) ===")
    for nm, pt in (("random single pick", base[1][0]["per_ticket"]),
                   ("walk-forward LightGBM single pick", -3.35),
                   ("best OOS rule, one ticket a day", 121.21)):
        r = rho_of(base[1], pt)
        print(f"  {nm:<38} ${pt:>8.2f}/tkt -> implied rho "
              f"{r if r is not None else 'n/a'}")
    write_json("need_report.json",
               {"target_per_month": TARGET,
                "curves": {k: v for k, v in rep.items()},
                "needed_rho": {k: {kk: needed_rho(vv) for kk, vv in v.items()}
                               for k, v in rep.items()}})


if __name__ == "__main__":
    main()
