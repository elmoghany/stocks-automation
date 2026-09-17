"""CHAMPION-REPLAY part 2: a CAUSAL detector of the kind of day the
champions actually profited from.

THE TARGET. The champions' P&L is made of names that ran +50-300% in a
session. "Ran" is not a decision-time fact, so the causal restatement
is: at the decision minute t, will this name's high reach +30% ABOVE
ITS PRICE AT t before 15:00? That is a label, it is measured strictly
after t, and it is never an input.

THE INPUTS are the pre-open and session-so-far block in cp_feat:
premarket dollar volume and how it compares with the name's OWN prior
60 sessions, the gap, the 07:00 gap, tape density and bar count,
realised 1-minute vol, distance from VWAP and from the opening range,
coil, signed-volume pressure, prior-session range, listing age, shares
outstanding and the implied market cap / turnover. Nothing in the block
can see a bar after t.

WALK-FORWARD. Dates are ordered; the model is refit at the start of
each fold on every row strictly BEFORE that fold and scores only the
rows inside it. No row is ever scored by a model that saw its own date.

CONTROLS, all run: shuffled target (labels permuted inside the training
block only), a random score, the inverted score, and -- the one that
matters most -- the base rate, because a rare positive class makes a
useless model look accurate.

    "C:\\cornell\\venvs\\rl\\Scripts\\python.exe" plan/cp_detect.py --fit
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_scan                                              # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/massive/cp"

TARGET = "up30"
RET = "mfe1500"
DROP = {"up30", "up50", "up100", "mfe1500", "mae1500", "r30", "r60",
        "r120", "r1500", "gain_full_HINDSIGHT", "last", "pc"}
MIN_TRAIN_DAYS = 120
NFOLD = 6


def feature_cols(cols):
    return [c for c in cols if c not in DROP]


def walk_forward(T, times=(935, 1000), seeds=(0, 1), shuffle=False,
                 verbose=True):
    import lightgbm as lgb
    X, cols, ci = T["X"], T["cols"], T["ci"]
    keep = np.isin(T["tt"], list(times))
    X, date, sym, tt = X[keep], T["date"][keep], T["sym"][keep], T["tt"][keep]
    fc = feature_cols(cols)
    fi = [ci[c] for c in fc]
    Xf = X[:, fi].astype(np.float64)
    y = X[:, ci[TARGET]].astype(np.float64)
    r = X[:, ci[RET]].astype(np.float64)
    ndates = int(date.max()) + 1
    bounds = np.linspace(MIN_TRAIN_DAYS, ndates, NFOLD + 1).astype(int)
    scores = np.full((len(seeds), len(y)), np.nan)
    for s_i, seed in enumerate(seeds):
        rng = np.random.default_rng(seed)
        for k in range(NFOLD):
            lo, hi = bounds[k], bounds[k + 1]
            if hi <= lo:
                continue
            tr = date < lo
            te = (date >= lo) & (date < hi)
            if tr.sum() < 500 or te.sum() == 0:
                continue
            ytr = y[tr].copy()
            if shuffle:
                ytr = rng.permutation(ytr)
            print(f"    fold {k} train={int(tr.sum())} test={int(te.sum())}",
                  flush=True)
            m = lgb.train(
                dict(objective="binary", learning_rate=0.08,
                     num_leaves=15, min_data_in_leaf=120, max_bin=63,
                     feature_fraction=0.8, bagging_fraction=0.8,
                     bagging_freq=1, verbose=-1, seed=int(seed),
                     num_threads=2),
                lgb.Dataset(Xf[tr], label=ytr), num_boost_round=150)
            scores[s_i, te] = m.predict(Xf[te])
        if verbose:
            print(f"  seed {seed} done", flush=True)
    return dict(scores=scores, y=y, r=r, date=date, sym=sym, tt=tt,
                feats=fc, Xf=Xf)


def _spear(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if len(a) < 5:
        return np.nan
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    d = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return float((ra * rb).sum() / d) if d else np.nan


def _auc(y, s):
    ok = np.isfinite(s)
    y, s = y[ok], s[ok]
    if y.sum() == 0 or y.sum() == len(y):
        return np.nan
    o = np.argsort(s)
    rk = np.empty(len(s))
    rk[o] = np.arange(1, len(s) + 1)
    n1 = y.sum()
    n0 = len(y) - n1
    return float((rk[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def evaluate(res, label=""):
    sc = np.nanmean(res["scores"], axis=0)
    y, r, date = res["y"], res["r"], res["date"]
    ok = np.isfinite(sc)
    base = float(y[ok].mean())
    out = dict(label=label, n=int(ok.sum()), base_rate=base,
               auc=_auc(y[ok], sc[ok]),
               ic_mfe=_spear(sc[ok], r[ok]))
    # per-cross-section top decile / top-1 precision
    prec10, prec1, lift = [], [], []
    for d in np.unique(date[ok]):
        m = ok & (date == d)
        if m.sum() < 10:
            continue
        s = sc[m]
        yy = y[m]
        k = max(1, int(round(0.10 * len(s))))
        top = np.argsort(-s)[:k]
        prec10.append(yy[top].mean())
        prec1.append(yy[np.argmax(s)])
    out["prec_top10pct"] = float(np.mean(prec10)) if prec10 else np.nan
    out["prec_top1"] = float(np.mean(prec1)) if prec1 else np.nan
    out["lift_top10pct"] = (out["prec_top10pct"] / base) if base else np.nan
    out["lift_top1"] = (out["prec_top1"] / base) if base else np.nan
    # per-day IC, averaged (the cross-sectional IC the repo reports)
    ics = []
    for d in np.unique(date[ok]):
        m = ok & (date == d)
        if m.sum() >= 8:
            ics.append(_spear(sc[m], r[m]))
    ics = [x for x in ics if np.isfinite(x)]
    out["ic_xs_mean"] = float(np.mean(ics)) if ics else np.nan
    out["ic_xs_t"] = (float(np.mean(ics) / (np.std(ics, ddof=1)
                                            / np.sqrt(len(ics))))
                      if len(ics) > 3 else np.nan)
    return out


def save_scores(res, path=None):
    sc = np.nanmean(res["scores"], axis=0)
    np.savez_compressed(path or (OUT / "scores.npz"), score=sc,
                        date=res["date"], sym=res["sym"], tt=res["tt"])


def main():
    a = sys.argv[1:]
    T = cp_scan.load()
    print(f"table: {T['X'].shape[0]} rows, {len(T['dates'])} dates")
    rows = []
    res = walk_forward(T)
    rows.append(evaluate(res, "walk-forward LightGBM (2 seeds), 09:35+10:00"))
    save_scores(res)
    for t in (935, 1000):
        m = res["tt"] == t
        sub = {k: (v[:, m] if k == "scores" else
                   (v[m] if isinstance(v, np.ndarray) else v))
               for k, v in res.items()}
        rows.append(evaluate(sub, f"  ... restricted to {t//100:02d}:"
                                  f"{t%100:02d}"))
    # the aug-2026 out-of-sample block, scored by folds that ended
    # before it (the walk-forward never trains on a row's own date)
    names = [str(x) for x in T["dates"]]
    oos_i = [i for i, d in enumerate(names) if d >= "2026-08-01"]
    if oos_i:
        lo = min(oos_i)
        m = res["date"] >= lo
        if m.sum() > 50:
            sub = {k: (v[:, m] if k == "scores" else
                       (v[m] if isinstance(v, np.ndarray) else v))
                   for k, v in res.items()}
            rows.append(evaluate(sub, "  ... aug-2026 block only (OOS)"))
    resh = walk_forward(T, shuffle=True, seeds=(0,))
    rows.append(evaluate(resh, "CONTROL shuffled target"))
    rnd = dict(res)
    rng = np.random.default_rng(7)
    rnd["scores"] = rng.random(res["scores"].shape)
    rows.append(evaluate(rnd, "CONTROL random score"))
    inv = dict(res)
    inv["scores"] = -res["scores"]
    rows.append(evaluate(inv, "CONTROL inverted score"))
    print("\n| model | n | base rate | AUC | IC vs MFE | xs-IC | t | "
          "prec top-10% | lift | prec top-1 | lift |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for o in rows:
        print(f"| {o['label']} | {o['n']:,} | {o['base_rate']*100:.2f}% | "
              f"{o['auc']:.3f} | {o['ic_mfe']:+.4f} | "
              f"{o['ic_xs_mean']:+.4f} | {o['ic_xs_t']:+.1f} | "
              f"{o['prec_top10pct']*100:.2f}% | {o['lift_top10pct']:.2f}x | "
              f"{o['prec_top1']*100:.2f}% | {o['lift_top1']:.2f}x |")
    (OUT / "detect.json").write_text(json.dumps(rows, indent=1,
                                                default=float))
    # feature importance, refit once on the first 70% for readability
    if "--imp" in a:
        import lightgbm as lgb
        X, ci = T["X"], T["ci"]
        keep = np.isin(T["tt"], [935, 1000])
        fc = feature_cols(T["cols"])
        Xf = X[keep][:, [ci[c] for c in fc]].astype(np.float64)
        y = X[keep][:, ci[TARGET]].astype(np.float64)
        d = T["date"][keep]
        cut = int(np.percentile(d, 70))
        m = lgb.train(dict(objective="binary", learning_rate=0.08,
                           num_leaves=15, min_data_in_leaf=120,
                           max_bin=63, verbose=-1, seed=0, num_threads=2),
                      lgb.Dataset(Xf[d < cut], label=y[d < cut]),
                      num_boost_round=150)
        imp = sorted(zip(fc, m.feature_importance("gain")),
                     key=lambda x: -x[1])
        print("\ntop features by gain (fit on the first 70% of dates):")
        for k, v in imp[:14]:
            print(f"  {k:16s} {v:12.0f}")


if __name__ == "__main__":
    main()
