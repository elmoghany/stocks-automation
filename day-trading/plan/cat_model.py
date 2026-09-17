"""CATALYST-MINER (2026-09-16): the walk-forward LightGBM ranker WITH and
WITHOUT the catalyst block, and every control the index header demands.

The whole question of this line is a DELTA: does adding causal catalyst
information to the WIDE-NET feature block move the out-of-sample rank IC
and the $/ticket of the chosen name?  So the model, the parameters, the
refit schedule and the label are plan/wn_model.py's, unchanged; the only
thing that varies between rows is the column set:

    base      the 32 wide-net columns (price / volume / calendar)
    cat       the NF catalyst columns only
    base+cat  both

Walk-forward: refit once per test month M on every eligible row with
date < M (early-stopping on the last 10% of train days), score month M.
Scoring starts at 2025-02 so that both halves of the sample get an
out-of-sample reading (Y1 = 2025-02..2025-07 OOS months, Y2 = 2025-08..
2026-07, aug26 = the 4-day stub).

Every dollar is counted by plan/wn_lib.single_pick + summarize on the
same table, so a config and its controls cannot disagree on fills, costs
or eligibility.  Controls per row: 30-seed random on the same slots,
inverted score, corrected shuffled labels (permuted WITHIN each train
day), foresight (score = the ticket's own realised net P&L).

Usage:  python plan/cat_model.py [--h h60] [--seeds 0,1,2] [--sets base,base+cat,cat]
        python plan/cat_model.py --gap        (the gapper-pool arm)
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cat_lib as C                                           # noqa: E402
import wn_lib as L                                            # noqa: E402

PARAMS = dict(objective="regression", learning_rate=0.04, num_leaves=63,
              min_data_in_leaf=400, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0,
              verbose=-1, num_threads=8)
NROUND = 600
START_MONTH = "2025-02"
Y1_END = "2025-08"          # months < Y1_END are "Y1", < OOS_END "Y2"


def load(which="wide"):
    p = C.OUT / ("table.npz" if which == "wide" else "table_gap.npz")
    t = L.Table(p)
    z = np.load(p, allow_pickle=False)
    t.n_base = int(z["n_base"][0])
    return t


def feat_idx(t, which):
    nb = t.n_base
    if which == "base":
        return list(range(nb))
    if which == "cat":
        return list(range(nb, len(t.feat)))
    return list(range(len(t.feat)))


def _cat_cols(t, idx):
    out = []
    for name in ("sic2", "dow"):
        if name in t.fidx and t.fidx[name] in idx:
            out.append(idx.index(t.fidx[name]))
    return out


def fit(t, rows, h, idx, seed, valid_rows=None, nround=NROUND, label=None):
    import lightgbm as lgb
    p = dict(PARAMS, seed=seed, bagging_seed=seed, feature_fraction_seed=seed)
    y = t.pnl[h] if label is None else label
    ds = lgb.Dataset(t.F[rows][:, idx], label=y[rows],
                     feature_name=[t.feat[i] for i in idx],
                     categorical_feature=_cat_cols(t, idx), free_raw_data=False)
    if valid_rows is not None and len(valid_rows):
        va = lgb.Dataset(t.F[valid_rows][:, idx], label=y[valid_rows], reference=ds)
        return lgb.train(p, ds, nround, valid_sets=[va],
                         callbacks=[lgb.early_stopping(50, verbose=False)])
    return lgb.train(p, ds, nround)


def walk_forward(t, h, which, seed=0, shuffle=False, tag=""):
    idx = feat_idx(t, which)
    m = t.mask(split=None, h=h)
    rows = np.flatnonzero(m)
    months = sorted({x for x in t.month[rows] if x >= START_MONTH})
    score = np.full(len(t.date_i), np.nan, np.float32)
    rng = np.random.default_rng(seed)
    info = []
    gain_acc = np.zeros(len(idx))
    for mo in months:
        te = rows[t.month[rows] == mo]
        tr = rows[t.month[rows] < mo]
        if len(tr) < 5000 or len(te) == 0:
            continue
        if shuffle:
            lab = t.pnl[h].copy()
            d = t.date_i[tr]
            o = np.argsort(d, kind="stable")
            ds = d[o]
            st = np.flatnonzero(np.r_[True, ds[1:] != ds[:-1]])
            en = np.r_[st[1:], len(o)]
            for a, b in zip(st, en):
                sel = tr[o[a:b]]
                lab[sel] = lab[sel][rng.permutation(b - a)]
            bst = fit(t, tr, h, idx, seed, nround=300, label=lab)
        else:
            dd = t.date_i[tr]
            cut = np.quantile(np.unique(dd), 0.9)
            bst = fit(t, tr[dd < cut], h, idx, seed, valid_rows=tr[dd >= cut])
        score[te] = bst.predict(t.F[te][:, idx])
        gain_acc += bst.feature_importance("gain")
        info.append({"month": mo, "train": int(len(tr)), "test": int(len(te)),
                     "iters": int(bst.best_iteration or (300 if shuffle else NROUND))})
    nm = f"scores_{h}_{which}_s{seed}{'_shuf' if shuffle else ''}{tag}.npy"
    np.save(C.OUT / nm, score)
    gain = sorted(zip([t.feat[i] for i in idx], gain_acc), key=lambda kv: -kv[1])
    return score, info, [(k, round(float(v), 1)) for k, v in gain[:25]]


# ------------------------------------------------------------ evaluation
def rank_ic(t, score, h, mask, min_n=10):
    """Mean cross-sectional Spearman IC over (date, dec) groups."""
    idx = np.flatnonzero(mask & np.isfinite(score))
    if idx.size == 0:
        return {"ic": 0.0, "t": 0.0, "n": 0}
    key = t.date_i[idx].astype(np.int64) * 64 + t.dec_i[idx]
    order = np.argsort(key, kind="stable")
    idx, key = idx[order], key[order]
    st = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
    en = np.r_[st[1:], len(idx)]
    ics, ys = [], []
    for a, b in zip(st, en):
        if b - a < min_n:
            continue
        s = score[idx[a:b]]
        y = t.pnl[h][idx[a:b]]
        rs = np.argsort(np.argsort(s)).astype(float)
        ry = np.argsort(np.argsort(y)).astype(float)
        if rs.std() == 0 or ry.std() == 0:
            continue
        ics.append(float(np.corrcoef(rs, ry)[0, 1]))
        ys.append(t.date_s[idx[a]][:7])
    ics = np.array(ics)
    ys = np.array(ys)
    out = {"ic": round(float(ics.mean()), 4) if ics.size else 0.0,
           "t": round(float(ics.mean() / ics.std() * np.sqrt(ics.size)), 2)
           if ics.size > 2 and ics.std() > 0 else 0.0, "n": int(ics.size)}
    for lab, sel in (("y1", ys < Y1_END), ("y2", (ys >= Y1_END) & (ys < "2026-08"))):
        v = ics[sel]
        out["ic_" + lab] = round(float(v.mean()), 4) if v.size else None
        out["n_" + lab] = int(v.size)
    return out


def _years(pnl, dates):
    m = np.array([d[:7] for d in dates])
    y1 = pnl[m < Y1_END]
    y2 = pnl[(m >= Y1_END) & (m < "2026-08")]
    a = pnl[m >= "2026-08"]
    return {"y1_total": round(float(y1.sum()), 2), "y1_n": int(y1.size),
            "y1_per_tkt": round(float(y1.mean()), 2) if y1.size else None,
            "y2_total": round(float(y2.sum()), 2), "y2_n": int(y2.size),
            "y2_per_tkt": round(float(y2.mean()), 2) if y2.size else None,
            "aug26_total": round(float(a.sum()), 2), "aug26_n": int(a.size)}


def pick_eval(t, score, h, dec=None, topk=1, label="", ndays=None):
    m = t.mask(dec=dec, h=h) & np.isfinite(score)
    pnl, dates, take = L.single_pick(t, score, m, h, topk)
    if ndays is None:
        ndays = len({d for d in t.date_s[np.flatnonzero(np.isfinite(score))]})
    s = L.summarize(pnl, dates, ndays, label)
    s.update(_years(pnl, dates))
    s["take"] = take
    return s


def controls(t, score, h, dec, topk, real, nseed=30, seed0=1000):
    """random (same slots), inverted, foresight -> dict."""
    m = t.mask(dec=dec, h=h) & np.isfinite(score)
    nd = real["days"]
    tots, exb, per = [], [], []
    for s in range(nseed):
        rng = np.random.default_rng(seed0 + s)
        r = rng.random(len(score)).astype(np.float32)
        pnl, dates, _ = L.single_pick(t, r, m, h, topk)
        tots.append(float(pnl.sum()))
        exb.append(float(pnl.sum() - pnl.max()) if pnl.size else 0.0)
        per.append(float(pnl.mean()) if pnl.size else 0.0)
    tots, exb, per = np.array(tots), np.array(exb), np.array(per)
    inv = pick_eval(t, -score, h, dec, topk, "inverted", nd)
    fs = np.where(np.isfinite(score), t.pnl[h], np.nan).astype(np.float32)
    fore = pick_eval(t, fs, h, dec, topk, "foresight", nd)
    return {"random_per_tkt_mean": round(float(per.mean()), 2),
            "random_per_tkt_sd": round(float(per.std()), 2),
            "random_per_month_mean": round(float(tots.mean()) / max(nd / 21.0, 1e-9), 2),
            "pct_total": round(float((tots < real["total"]).mean() * 100), 1),
            "pct_ex_best": round(float((exb < real["ex_best_total"]).mean() * 100), 1),
            "inverted_per_tkt": inv["per_ticket"], "inverted_total": inv["total"],
            "foresight_per_tkt": fore["per_ticket"], "foresight_per_month": fore["per_month"]}


def evaluate(t, score, h, name, with_controls=True):
    out = {"name": name, "h": h}
    out["ic_all"] = rank_ic(t, score, h, t.mask(h=h))
    out["ic_by_dec"] = {d: rank_ic(t, score, h, t.mask(dec=d, h=h)) for d in t.dec}
    ndays = len({d for d in t.date_s[np.flatnonzero(np.isfinite(score))]})
    rows = {}
    cfgs = [("1/day@09:35", "09:35", 1), ("7/day@09:35", "09:35", 7),
            ("1/day@10:00", "10:00", 1), ("1/day@10:30", "10:30", 1),
            ("1/day@11:00", "11:00", 1), ("1/day@13:00", "13:00", 1),
            ("1/day@15:30", "15:30", 1), ("1/slot all decs", None, 1)]
    for lab, dec, k in cfgs:
        r = pick_eval(t, score, h, dec, k, lab, ndays)
        r.pop("take", None)
        if with_controls:
            r["controls"] = controls(t, score, h, dec, k, r)
        rows[lab] = r
    out["picks"] = rows
    return out


def run_wide(hs, seeds, sets, shuffle_sets=("base+cat",)):
    t = load("wide")
    res = {"table": "wide", "rows": int(len(t.date_i)), "eligible": int(t.printed_m.sum()),
           "n_base": t.n_base, "n_feat": len(t.feat), "runs": []}
    t0 = time.time()
    for h in hs:
        for which in sets:
            for seed in seeds:
                sc, info, gain = walk_forward(t, h, which, seed)
                ev = evaluate(t, sc, h, f"{which}|{h}|s{seed}")
                ev["folds"] = info
                ev["gain_top"] = gain
                res["runs"].append(ev)
                p = ev["picks"]["1/day@09:35"]
                print(f"  {which:9s} {h} s{seed} IC={ev['ic_all']['ic']:+.4f} "
                      f"(y1 {ev['ic_all']['ic_y1']} y2 {ev['ic_all']['ic_y2']}) "
                      f"1/day@09:35 ${p['per_ticket']:+.2f}/tkt ${p['per_month']:+.0f}/mo "
                      f"pct {p['controls']['pct_total']} | 7/day "
                      f"${ev['picks']['7/day@09:35']['per_ticket']:+.2f} "
                      f"{time.time()-t0:.0f}s", flush=True)
                C.write_json(C.OUT / "model_results.json", res)
            if which in shuffle_sets and seeds:
                sc, info, _ = walk_forward(t, h, which, seeds[0], shuffle=True)
                ev = evaluate(t, sc, h, f"{which}|{h}|s{seeds[0]}|SHUFFLED", with_controls=True)
                res["runs"].append(ev)
                p = ev["picks"]["1/day@09:35"]
                print(f"  SHUFFLED {which} {h}: IC={ev['ic_all']['ic']:+.4f} "
                      f"1/day ${p['per_ticket']:+.2f} pct {p['controls']['pct_total']}",
                      flush=True)
                C.write_json(C.OUT / "model_results.json", res)
    C.write_json(C.OUT / "model_results.json", res)
    return res


# ------------------------------------------------------------ gapper arm
def run_gap(seeds=(0,)):
    """Same protocol on table_gap.npz; horizons are the CM exit keys."""
    p = C.OUT / "table_gap.npz"
    z = np.load(p, allow_pickle=False)
    keys = [str(k) for k in z["exit_keys"]]

    class G(L.Table):
        def __init__(self):
            self.dates = [str(x) for x in z["dates"]]
            self.syms = [str(x) for x in z["syms"]]
            self.feat = [str(x) for x in z["features"]]
            self.dec = [str(x) for x in z["dec_et"]]
            self.date_i = z["date_i"]; self.sym_i = z["sym_i"]
            self.dec_i = z["dec_i"].astype(np.int32)
            self.F = z["F"]; self.notional = z["notional"]
            self.printed = z["printed"]; self.printed_m = z["printed_m"]
            self.fill_px = z["fill_px"]
            self.pnl = {k: z["pnl_" + k] for k in keys}
            self.ok = {k: z["ok_" + k] for k in keys}
            self.fidx = {f: i for i, f in enumerate(self.feat)}
            da = np.array(self.dates)
            self.split = np.where(da < L.TRAIN_END, 0,
                                  np.where(da < L.OOS_END, 1, 2))[self.date_i]
            self.date_s = da[self.date_i]
            self.month = np.array([d[:7] for d in self.dates])[self.date_i]
            self.n_base = int(z["n_base"][0])

        def mask(self, split=None, dec=None, h=None):
            m = self.printed_m.copy()
            if h is not None:
                m &= self.ok[h]
            if split is not None:
                m &= np.isin(self.split, np.atleast_1d(split))
            if dec is not None:
                di = [self.dec.index(d) for d in np.atleast_1d(dec)]
                m &= np.isin(self.dec_i, di)
            return m

    t = G()
    res = {"table": "gap", "rows": int(len(t.date_i)), "runs": []}
    for k in keys:
        dec = k.split("->")[0]
        for which in ("base", "base+cat", "cat"):
            for seed in seeds:
                sc, info, gain = walk_forward(t, k, which, seed, tag="_gap")
                ev = {"name": f"{which}|{k}|s{seed}", "h": k,
                      "ic": rank_ic(t, sc, k, t.mask(dec=dec, h=k))}
                ndays = len({d for d in t.date_s[np.flatnonzero(np.isfinite(sc))]})
                for lab, kk in (("1/day", 1), ("7/day", 7)):
                    r = pick_eval(t, sc, k, dec, kk, lab, ndays)
                    r.pop("take", None)
                    r["controls"] = controls(t, sc, k, dec, kk, r)
                    ev[lab] = r
                ev["gain_top"] = gain[:12]
                res["runs"].append(ev)
                print(f"  GAP {which:9s} {k} IC={ev['ic']['ic']:+.4f} 1/day "
                      f"${ev['1/day']['per_ticket']:+.2f} pct {ev['1/day']['controls']['pct_total']} "
                      f"7/day ${ev['7/day']['per_ticket']:+.2f} rand "
                      f"{ev['7/day']['controls']['random_per_tkt_mean']}", flush=True)
                C.write_json(C.OUT / "model_results_gap.json", res)
    return res


if __name__ == "__main__":
    a = sys.argv
    if "--gap" in a:
        run_gap()
    else:
        hs = (a[a.index("--h") + 1].split(",") if "--h" in a else ["h30", "h60", "h120"])
        seeds = [int(x) for x in (a[a.index("--seeds") + 1].split(",") if "--seeds" in a else ["0"])]
        sets = (a[a.index("--sets") + 1].split(",") if "--sets" in a
                else ["base", "base+cat", "cat"])
        run_wide(hs, seeds, sets)
