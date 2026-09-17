"""CATALYST-MINER (2026-09-16): the poison test, on BOTH information
sources and at the level of the PICKS.

For a sampled day and a cut minute m (one of the six decision times):

  BARS    every 1-minute bar strictly after m becomes uniform garbage and
          the price block is rebuilt through plan/rl2/features.compute_day
          + plan/wn_table.day_block (the functions that built the table),
  EVENTS  every news article / filing / earnings report / Form 4 / sentiment
          record with a public timestamp AFTER the decision instant is
          deleted and replaced by garbage events (random classes, random
          times inside the next 60 days), and the catalyst block is rebuilt
          through plan/cat_events.features_for,

and the test asserts that at every decision time <= m

  1. all price-block columns and the causal gate are bit-identical,
  2. all catalyst columns are bit-identical,
  3. the top-1 AND top-7 names chosen by a fitted base+cat LightGBM
     ranker are the same tickers,

while at decision times > m the catalyst block MUST differ (the garbage
must be visible where it is allowed to be, or the mutation had no
teeth) and the label MUST move (it prices minute m+1 onward).

Usage: python plan/cat_poison.py [--days 12]
"""
import copy
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import features as FT                                         # noqa: E402
import wn_table as WT                                         # noqa: E402
import cat_lib as C                                           # noqa: E402
import cat_events as E                                        # noqa: E402
import cat_model as M                                         # noqa: E402
import cat_table as CT                                        # noqa: E402

DAYS = HERE / "rl2" / "out" / "days"


def poison_corpus(corp, syms, cut, rng):
    """Copy of the corpus for `syms` with every event after `cut` replaced
    by garbage.  Returns (poisoned dict, n_events_removed, n_added)."""
    out = {}
    removed = added = 0
    for s in syms:
        ev = corp.get(s)
        if ev is None:
            continue
        new = {}
        for k, arr in ev.items():
            if k.startswith("_"):
                keep = arr[arr[:, 0] <= cut] if arr.shape[0] else arr
                removed += int(arr.shape[0] - keep.shape[0])
                n_add = int(rng.integers(0, 4))
                g = np.column_stack([cut + rng.uniform(1, 60 * 86400, n_add)]
                                    + [rng.uniform(-100, 100, n_add)
                                       for _ in range(arr.shape[1] - 1)])
                new[k] = np.vstack([keep, g]) if n_add else keep
                new[k] = new[k][np.argsort(new[k][:, 0])] if new[k].shape[0] else new[k]
                added += n_add
            else:
                keep = arr[arr <= cut]
                removed += int(arr.size - keep.size)
                n_add = int(rng.integers(0, 6))
                g = cut + rng.uniform(1, 60 * 86400, n_add)
                new[k] = np.sort(np.concatenate([keep, g]))
                added += n_add
        out[s] = new
    return out, removed, added


def main(ndays=12, seed=11):
    t = M.load("wide")
    # one fitted ranker (train split only) for the pick-identity check
    idx = M.feat_idx(t, "base+cat")
    rows = np.flatnonzero(t.mask(split=0, h="h60"))
    bst = M.fit(t, rows, "h60", idx, 0, nround=120)

    CT.W.DEC_ET = CT.DEC_ET
    CT.W.DEC_T = np.array([WT.et_to_step(x) for x in CT.DEC_ET], np.int32)
    CT.W.NT = len(CT.W.DEC_T)
    prof = FT.fit_profile()
    daily = FT.Daily()
    sic2, earn, cal = WT.load_sic2(), WT.load_earn(), WT.load_earn_rh()
    files = sorted(DAYS.glob("*.npz"))
    all_dates = [p.stem for p in sorted(CT.FEAT.glob("*.npz"))]
    prevmap = {d: (all_dates[i - 1] if i else None) for i, d in enumerate(all_dates)}
    rng = np.random.default_rng(seed)
    pick = [files[i] for i in rng.choice(len(files), min(ndays, len(files)), replace=False)]
    corp = E.corpus()
    cuts = list(range(len(CT.DEC_ET)))
    st = {"array_checks": 0, "array_mism": 0, "cat_checks": 0, "cat_mism": 0,
          "pick_checks": 0, "pick_mism": 0, "label_moved": 0, "label_of": 0,
          "cat_future_moved": 0, "cat_future_of": 0, "events_removed": 0,
          "events_added": 0}
    detail = []
    for p in pick:
        date = p.stem
        syms, pc, bars = FT.load_raw(p)
        clean = WT.day_block(date, FT.compute_day(date, syms, pc, bars, prof, daily),
                             sic2, earn, cal, prevmap.get(date))
        ts = np.array([C.decision_ts(date, x).timestamp() for x in CT.DEC_ET])
        cat_clean = np.stack([E.features_for(s, ts) for s in syms], axis=1)   # [NT,S,NF]
        for ci in cuts:
            m = int(WT.STEPS[CT.W.DEC_T[ci]])
            cut = ts[ci]
            # ---- bars
            o, h, lo, c, v = (a.copy() for a in bars)
            sl = slice(m + 1, None)
            shp = o[:, sl].shape
            g = rng.uniform(0.5, 500.0, size=shp)
            o[:, sl] = g
            h[:, sl] = g * rng.uniform(1.0, 1.5, size=shp)
            lo[:, sl] = g * rng.uniform(0.5, 1.0, size=shp)
            c[:, sl] = g * rng.uniform(0.7, 1.3, size=shp)
            v[:, sl] = rng.integers(1, 10 ** 7, size=shp)
            bad = WT.day_block(date, FT.compute_day(date, syms, pc, (o, h, lo, c, v),
                                                    prof, daily), sic2, earn, cal,
                               prevmap.get(date))
            keep = WT.STEPS[CT.W.DEC_T] <= m
            for k in ("F", "printed_m"):
                a = np.nan_to_num(clean[k][keep], nan=-9e9)
                b = np.nan_to_num(bad[k][keep], nan=-9e9)
                st["array_checks"] += 1
                if not np.array_equal(a, b):
                    st["array_mism"] += 1
                    detail.append({"date": date, "cut": CT.DEC_ET[ci], "array": k,
                                   "n_diff": int((a != b).sum())})
            st["label_of"] += 1
            if not np.array_equal(np.nan_to_num(clean["pnl"][ci]), np.nan_to_num(bad["pnl"][ci])):
                st["label_moved"] += 1
            # ---- events
            pc_corp, rem, add = poison_corpus(corp, syms, cut, rng)
            st["events_removed"] += rem
            st["events_added"] += add
            E._CORPUS = pc_corp
            cat_bad = np.stack([E.features_for(s, ts) for s in syms], axis=1)
            E._CORPUS = corp
            st["cat_checks"] += 1
            if not np.array_equal(cat_clean[keep], cat_bad[keep]):
                st["cat_mism"] += 1
                d = np.flatnonzero((cat_clean[keep] != cat_bad[keep]).any(axis=(0, 1)))
                detail.append({"date": date, "cut": CT.DEC_ET[ci], "array": "cat",
                               "cols": [E.feature_names()[i] for i in d[:8]]})
            if (~keep).any() and add > 0:
                st["cat_future_of"] += 1
                if not np.array_equal(cat_clean[~keep], cat_bad[~keep]):
                    st["cat_future_moved"] += 1
            # ---- picks (top-1 / top-7 under the fitted ranker) at every dec <= m
            for ti in np.flatnonzero(keep):
                Fa = np.concatenate([clean["F"][ti], cat_clean[ti]], axis=1)[:, idx]
                Fb = np.concatenate([bad["F"][ti], cat_bad[ti]], axis=1)[:, idx]
                la, lb = clean["printed_m"][ti], bad["printed_m"][ti]
                sa = np.where(la, bst.predict(Fa), -np.inf)
                sb = np.where(lb, bst.predict(Fb), -np.inf)
                if not la.any():
                    continue
                for k in (1, 7):
                    st["pick_checks"] += 1
                    ta = [syms[i] for i in np.argsort(-sa)[:k] if np.isfinite(sa[i])]
                    tb = [syms[i] for i in np.argsort(-sb)[:k] if np.isfinite(sb[i])]
                    if ta != tb:
                        st["pick_mism"] += 1
                        detail.append({"date": date, "cut": CT.DEC_ET[ci],
                                       "dec": CT.DEC_ET[ti], "k": k, "clean": ta, "bad": tb})
        print(f"  {date}: arrays {st['array_checks']}/{st['array_mism']} "
              f"cat {st['cat_checks']}/{st['cat_mism']} picks {st['pick_checks']}/{st['pick_mism']} "
              f"future-moved {st['cat_future_moved']}/{st['cat_future_of']}", flush=True)
    st["days"] = len(pick)
    st["cuts"] = CT.DEC_ET
    st["PASS"] = bool(st["array_mism"] == 0 and st["cat_mism"] == 0 and st["pick_mism"] == 0
                      and st["label_moved"] == st["label_of"]
                      and st["cat_future_moved"] == st["cat_future_of"])
    st["detail"] = detail[:20]
    C.write_json(C.OUT / "poison.json", st)
    print(json.dumps({k: v for k, v in st.items() if k != "detail"}, indent=1))


if __name__ == "__main__":
    a = sys.argv
    main(int(a[a.index("--days") + 1]) if "--days" in a else 12)
