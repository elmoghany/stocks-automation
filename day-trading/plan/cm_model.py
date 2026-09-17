"""CLOSE-MOMENTUM (2026-09-16): the information content of the late
session, and the strongest fitted arm the mandate allows.

Two questions single-feature rankings cannot answer:

  1. HOW MUCH information is in the causal state at 12:00 / 15:00 / 15:30
     about the return to the close? Reported as the rank IC of every
     feature, per split, and as the break-even IC the pass bar implies.
  2. Does a FITTED combination beat its own controls? LightGBM trained on
     Y1 rows only (target = the realized net return of the very ticket the
     decision opens), predicted on Y2 and on the aug-2026 stub. The same
     model is refitted on a SHUFFLED target as the control that isolates
     information from policy shape -- rl2 §3.8(b) showed the percentile
     leg alone cannot tell them apart.

Break-even arithmetic for the last half hour, so the gap is a number and
not an impression: the unconditional gross drift 15:30 -> 15:59 on this
universe is +3.41 bps (t = 5.0), the round trip costs 20 bps, and the bar
needs +$51 net on a $15,000 ticket at 7 tickets/day = +34 bps net = +54
bps gross. Selection has to multiply the drift by ~16.

Usage:  python plan/cm_model.py [--universe wide]
Writes: data/massive/cm/model_{universe}.json
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import cm_lib as L                                            # noqa: E402
import cm_single as S                                         # noqa: E402

PAIRS = [("15:30", "15:59"), ("15:30", "15:55"), ("15:00", "15:59"),
         ("12:00", "15:59"), ("12:00", "14:00"), ("13:00", "15:59")]


def net_ret(t, dec, exit_lab):
    """The net return per $1 of the ticket a decision at `dec` opens,
    exited at `exit_lab`. This is the LABEL; it never enters a feature."""
    xi = t.xidx[exit_lab]
    c_in = L.cost_frac(L.idx(dec))
    c_out = L.cost_frac(L.idx(exit_lab))
    with np.errstate(all="ignore"):
        return (t.px_out[:, xi] * (1 - c_out)) / np.maximum(
            t.px_in * (1 + c_in), 1e-9) - 1.0


def eligible(t, dec, exit_lab):
    j = t.didx[dec]
    xi = t.xidx[exit_lab]
    return ((t.dec_i == j) & t.printed_m & np.isfinite(t.px_in)
            & (t.px_in > 0) & np.isfinite(t.px_out[:, xi])
            & (t.px_out[:, xi] > 0))


def spearman(x, y):
    k = np.isfinite(x) & np.isfinite(y)
    if k.sum() < 50:
        return np.nan
    a = np.argsort(np.argsort(x[k])).astype(float)
    b = np.argsort(np.argsort(y[k])).astype(float)
    a -= a.mean(); b -= b.mean()
    d = a.std() * b.std()
    return float((a * b).mean() / d) if d > 0 else np.nan


def stage_ic(t):
    out = {}
    for dec, ex in PAIRS:
        m = eligible(t, dec, ex)
        y = net_ret(t, dec, ex)
        row = {}
        for f in t.feat:
            x = t.f(f)
            row[f] = {
                "all": round(spearman(x[m], y[m]), 4),
                "y1": round(spearman(x[m & (t.split == 0)],
                                     y[m & (t.split == 0)]), 4),
                "y2": round(spearman(x[m & (t.split == 1)],
                                     y[m & (t.split == 1)]), 4)}
        row["_n"] = int(m.sum())
        out[f"{dec}->{ex}"] = row
    return out


def stage_model(t, dec, exit_lab, seeds=(0, 1, 2)):
    """LightGBM fitted on Y1 rows only, scored on Y2 and aug2026."""
    import lightgbm as lgb
    m = eligible(t, dec, exit_lab)
    y = net_ret(t, dec, exit_lab)
    tr = m & (t.split == 0)
    X = t.F
    res = {"train_rows": int(tr.sum()), "test_rows": int((m & (t.split == 1)).sum())}
    for tag, target in (("real", y), ("shuffled", None)):
        rows = []
        for sd in seeds:
            yy = target
            if yy is None:
                rng = np.random.default_rng(4000 + sd)
                yy = y.copy()
                for dnum in range(len(t.dates)):
                    k = np.flatnonzero((t.date_i == dnum) & m)
                    if k.size > 1:
                        yy[k] = y[k][rng.permutation(k.size)]
            mdl = lgb.LGBMRegressor(
                n_estimators=300, learning_rate=0.05, num_leaves=31,
                min_child_samples=100, subsample=0.8, subsample_freq=1,
                colsample_bytree=0.8, random_state=sd, verbose=-1)
            mdl.fit(X[tr], yy[tr])
            sc = np.full(len(t.px_in), -np.inf)
            pred = mdl.predict(X[m])
            sc[m] = pred
            for k in (1, 3, 7):
                trd = S.run(t, sc, exit_lab, [dec], topk=k)
                keep = [x for x in trd if L.split_of(x["date"]) == 1]
                rows.append({"seed": sd, "topk": k,
                             "y2": L.summarize(keep, t.ndays(1),
                                               f"{tag}-s{sd}-k{k}"),
                             "all": L.summarize(trd, len(t.dates),
                                                f"{tag}-s{sd}-k{k}-all"),
                             "ic_y2": round(spearman(
                                 pred[(t.split[m] == 1)],
                                 y[m][(t.split[m] == 1)]), 4)})
        res[tag] = rows
    return res


def main():
    uni = sys.argv[sys.argv.index("--universe") + 1] \
        if "--universe" in sys.argv else "wide"
    t = S.Table(uni)
    res = {}
    print("== rank IC of every causal feature vs the ticket's net return ==")
    ic = stage_ic(t)
    res["ic"] = ic
    for pair, row in ic.items():
        best = sorted(((abs(v["all"]), f, v) for f, v in row.items()
                       if f != "_n"), reverse=True)[:6]
        print(f"\n{pair}  n={row['_n']:,}")
        for _, f, v in best:
            print(f"   {f:16s} all {v['all']:+7.4f}  y1 {v['y1']:+7.4f}  "
                  f"y2 {v['y2']:+7.4f}")
    print("\n== fitted arm: LightGBM on Y1 -> Y2 ==", flush=True)
    for dec, ex in (("15:30", "15:59"), ("15:00", "15:59"), ("12:00", "15:59")):
        r = stage_model(t, dec, ex)
        res[f"model|{dec}->{ex}"] = r
        for tag in ("real", "shuffled"):
            for row in r[tag]:
                a = row["y2"]
                print(f"  {dec}->{ex} {tag:9s} s{row['seed']} k{row['topk']} "
                      f"n={a['tickets']:5d} ${a['per_ticket']:+8.2f}/tkt "
                      f"${a['per_month']:+9.1f}/mo  IC(y2)={row['ic_y2']:+.4f}",
                      flush=True)
    L.write_json(f"model_{uni}.json", res)
    print("wrote", L.OUT / f"model_{uni}.json", flush=True)


if __name__ == "__main__":
    main()
