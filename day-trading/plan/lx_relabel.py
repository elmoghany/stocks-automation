"""LIMIT-EXEC stage 2b: RANK FOR THE END-TO-END FILL.

UNIVERSE-QUOTES showed that a ranker fitted on market-fill P&L loses its
edge under a conditional execution, and that refitting the SAME model on
the limit ticket's own realized P&L ($0 when unfilled) restores it.  Its
label was the ENTRY-side limit (10 bps / 1 minute, market exit).  This
module builds the label of the END-TO-END passive ticket -- bid-rest3-
cancel / ask-rest3 (both legs resting, unfilled = $0) -- for every
causally eligible wn row, and refits plan/wn_model.fit on it exactly as
plan/uq_relabel.py does (same 32 features, same params, same early
stopping, monthly walk-forward; train months 2025-01..07 fitted on train
rows before each; OOS months 2025-08..2026-07 fitted on every row before
each).  The label is future information and is never a feature.

Usage:
  python plan/lx_relabel.py --stage label  [--workers 1]
  python plan/lx_relabel.py --stage scores
"""
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lx_engine as X                                         # noqa: E402
import lx_frame as F                                          # noqa: E402
import lx_tables as T                                         # noqa: E402
import uq_econ as UE                                          # noqa: E402
import uq_fills as UF                                         # noqa: E402
from wn_lib import Table, TAB                                 # noqa: E402

LABEL = X.OUT / "lx_label_h30.npz"
ENTRY, EXIT = F.E("rest", 3), F.Xs("rest", 3)


def _worker(args):
    date, rows_sym_dec = args
    import lx_engine as XX
    try:
        day = XX.Day(date)
    except Exception as e:
        return date, None, str(e)
    f = np.load(UF.FEAT / f"{date}.npz", allow_pickle=False)
    vc = f["volcap"].astype(float)
    fsyms = {str(s): i for i, s in enumerate(f["syms"])}
    out = []
    for r, sym, ti, m_dec in rows_sym_dec:
        si = day.sidx.get(sym)
        if si is None or not day.has_tape(si):
            out.append((r, np.nan, np.nan, 0))
            continue
        cap = float(vc[ti, fsyms[sym]]) if sym in fsyms else np.nan
        rec = XX.ticket(day, si, m_dec, 30, ENTRY, EXIT, int(day.flat_min[si]),
                        cap_shares=cap, exit_conv="open_next")
        if rec is None:
            out.append((r, 0.0, 0.0, 0))
        else:
            out.append((r, rec["pnl"]["flat"], rec["pnl"]["meas"], 1))
    return date, out, None


def stage_label(workers=1):
    t = Table()
    prov = T.WnProvider(t)
    days = UE.cached_days(t, None)
    di = {d: i for i, d in enumerate(t.dates)}
    n = len(t.date_i)
    y = np.zeros(n, np.float32)
    ym = np.zeros(n, np.float32)
    filled = np.zeros(n, bool)
    have = np.zeros(n, bool)
    args = []
    for d in days:
        rows = np.flatnonzero((t.date_i == di[d]) & t.printed_m
                              & np.isin(t.dec_i, prov.dec_i))
        lst = [(int(r), t.syms[t.sym_i[r]], prov.ti_of_ci[int(t.dec_i[r])],
                prov.m_of_ci[int(t.dec_i[r])]) for r in rows]
        args.append((d, lst))
    print(f"label: {len(days)} tape-complete days, "
          f"{sum(len(a[1]) for a in args):,} rows", flush=True)
    t0 = time.monotonic()
    it = Pool(workers).imap_unordered(_worker, args, chunksize=2) \
        if workers > 1 else map(_worker, args)
    done = 0
    for date, out, err in it:
        done += 1
        if err:
            print(f"  !! {date}: {err}", flush=True)
            continue
        for r, a, b, fl in out:
            if np.isfinite(a):
                y[r], ym[r], filled[r], have[r] = a, b, bool(fl), True
        if done % 50 == 0 or done == len(args):
            print(f"  ..{done}/{len(args)} days {(time.monotonic()-t0)/60:.1f} min, "
                  f"{int(have.sum()):,} rows, fill {float(filled[have].mean()):.3f}",
                  flush=True)
    np.savez_compressed(LABEL, y=y, y_meas=ym, filled=filled, have=have)
    print(f"saved {LABEL.name}: {int(have.sum()):,} rows, fill "
          f"{float(filled[have].mean()):.4f}, ${float(y[have].mean()):.2f}/attempt, "
          f"${float(y[have & filled].mean()):.2f}/filled (flat); "
          f"${float(ym[have & filled].mean()):.2f}/filled (measured)")


def stage_scores(seed=0, key="y"):
    import wn_model
    z = np.load(LABEL)
    t = Table()
    t.pnl["lx"] = z[key].astype(np.float32)
    have = z["have"]
    m = t.mask(split=None, dec=UF.RTH_DEC, h="h30") & have
    rows = np.flatnonzero(m)
    print(f"refit: {len(rows):,} labelled eligible rows", flush=True)
    for split, months in ((0, [f"2025-0{i}" for i in range(1, 8)]),
                          (1, sorted({x for x in t.month[rows] if x >= "2025-08"}))):
        score = np.full(len(t.date_i), np.nan)
        pool = rows[t.split[rows] == 0] if split == 0 else rows
        for mo in months:
            te = pool[t.month[pool] == mo]
            tr = pool[t.month[pool] < mo]
            if len(tr) < 5000 or len(te) == 0:
                continue
            dd = t.date_i[tr]
            cut = np.quantile(np.unique(dd), 0.9)
            bst = wn_model.fit(t, tr[dd < cut], "lx", seed, valid_rows=tr[dd >= cut])
            score[te] = bst.predict(t.F[te])
            print(f"  [{split}] {mo} train={len(tr):,} test={len(te):,} "
                  f"iters={bst.best_iteration}", flush=True)
        f = X.OUT / f"lx_relabel_scores_s{split}.npy"
        np.save(f, score.astype(np.float32))
        print(f"  -> {f.name}: {int(np.isfinite(score).sum()):,} scored rows", flush=True)


if __name__ == "__main__":
    a = sys.argv
    g = lambda f, d: (type(d)(a[a.index(f) + 1]) if f in a else d)  # noqa: E731
    st = g("--stage", "label")
    if st == "label":
        stage_label(g("--workers", 1))
    else:
        stage_scores(g("--seed", 0))
