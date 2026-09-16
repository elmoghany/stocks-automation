"""WIDE-NET (2026-09-16) step 2c: interpretable conjunctive rule search.

A rule is 2-3 conditions of the form `feature <= v` / `feature > v` (plus,
optionally, `decision time == HH:MM`), thresholds drawn from TRAIN-window
quantiles only.  Objective: maximise mean net $ per $15,000 ticket subject
to at least MIN_N train tickets.  The search is a beam search -- every
single-condition atom is scored exhaustively, the best BEAM survive, each
is extended by every atom, and so on to depth 3.

WHY A BEAM AND NOT A RANDOM SEARCH.  plan/rl2/rules.py already ran a
random + elitist-mutation search of essentially this shape and found that
selection-on-train transfers about +$46/ticket out of sample from a -$59
base.  A beam is the *strongest* possible train-fitter of this family, so
if the beam's held-out result is still negative the family is exhausted,
not merely under-searched.  The price of a stronger fitter is a bigger
selection bias, which is why the unsearched null (`--stage null`) is run
with exactly the same atom generator and compared on the SAME held-out
window.

Nothing in this file ever reads a row with date >= 2025-08-01.

Usage: python plan/wn_rules.py --stage search [--seeds 5]
       python plan/wn_rules.py --stage null [--n 2000]
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wn_lib import HNAMES, Table, write_json          # noqa: E402

RTH = ["09:35", "09:45", "10:00", "10:30", "11:00", "12:00", "13:00",
       "14:00", "15:00"]
MIN_N = 150
BEAM = 120
DEPTH = 3
NQ = 9                       # interior quantiles per feature
SKIP = {"is_ext", "earn_prox", "sic2"}   # constant / non-ordinal here


def atoms(t, rows):
    """(list of (name, bool mask over `rows`)) -- the search alphabet."""
    A = []
    for f in t.feat:
        if f in SKIP:
            continue
        x = t.F[rows, t.fidx[f]].astype(np.float64)
        qs = np.unique(np.quantile(x, np.linspace(0.1, 0.9, NQ)))
        for q in qs:
            le = x <= q
            n = int(le.sum())
            if MIN_N <= n <= len(rows) - MIN_N:
                A.append((f"{f}<={q:.5g}", le))
                A.append((f"{f}>{q:.5g}", ~le))
    for d in RTH:
        m = t.dec_i[rows] == t.dec.index(d)
        if m.sum() >= MIN_N:
            A.append((f"dec=={d}", m))
    # sector atoms: one-vs-rest on the 2-digit SIC groups that are big
    s2 = t.F[rows, t.fidx["sic2"]].astype(int)
    for v in np.unique(s2):
        m = s2 == v
        if m.sum() >= 2 * MIN_N:
            A.append((f"sic2=={v}", m))
    return A


def beam_search(t, rows, h, A, sub=None, verbose=True):
    """Best-on-train conjunctions up to DEPTH conditions."""
    p = t.pnl[h][rows]
    if sub is not None:
        p = np.where(sub, p, np.nan)
    ok = np.isfinite(p)
    base = np.full(len(rows), True)
    cur = [((), base)]
    best_all = []
    for d in range(DEPTH):
        cand = []
        for names, msk in cur:
            start = 0 if not names else \
                max(i for i, a in enumerate(A) if a[0] == names[-1]) + 1
            for i in range(start, len(A)):
                an, am = A[i]
                if an.split("<=")[0].split(">")[0] in \
                        [x.split("<=")[0].split(">")[0] for x in names]:
                    continue
                m = msk & am & ok
                n = int(m.sum())
                if n < MIN_N:
                    continue
                cand.append((float(p[m].mean()), names + (an,), m, n))
        if not cand:
            break
        cand.sort(key=lambda r: -r[0])
        cur = [(c[1], c[2]) for c in cand[:BEAM]]
        best_all += [{"depth": d + 1, "mean": round(c[0], 2), "n": c[3],
                      "rule": list(c[1]),
                      "win": round(float((p[c[2]] > 0).mean()), 4)}
                     for c in cand[:20]]
        if verbose:
            c = cand[0]
            print(f"   depth {d+1}: best ${c[0]:+.2f}/tkt n={c[3]} "
                  f"{' AND '.join(c[1])}", flush=True)
    best_all.sort(key=lambda r: -r["mean"])
    return best_all


def apply_rule(t, rule, h, split=None):
    """Boolean mask over the WHOLE table for a rule's conjunction."""
    m = t.ok[h].copy()
    if split is not None:
        m &= np.isin(t.split, np.atleast_1d(split))
    m &= np.isin(t.dec_i, [t.dec.index(d) for d in RTH])
    for cond in rule:
        if cond.startswith("dec=="):
            m &= t.dec_i == t.dec.index(cond[5:])
        elif cond.startswith("sic2=="):
            m &= t.F[:, t.fidx["sic2"]].astype(int) == int(cond[6:])
        elif "<=" in cond:
            f, v = cond.split("<=")
            m &= t.F[:, t.fidx[f]] <= float(v)
        else:
            f, v = cond.split(">")
            m &= t.F[:, t.fidx[f]] > float(v)
    return m


# ------------------------------------------------------------------ main
def stage_search(nseeds=5):
    t = Table()
    out = []
    for h in HNAMES:
        rows = np.flatnonzero(t.mask(split=0, dec=RTH, h=h))
        A = atoms(t, rows)
        print(f"\n=== horizon {h}: {len(rows):,} train tickets, "
              f"{len(A)} atoms ===", flush=True)
        for seed in range(nseeds):
            # seed 0 = the full train window; seeds 1.. = day-level
            # bootstrap resamples, so the five rules are genuinely
            # different fits of the same family rather than one answer.
            if seed == 0:
                sub = None
            else:
                rng = np.random.default_rng(1000 + seed)
                d = np.unique(t.date_i[rows])
                keep = set(rng.choice(d, int(0.7 * len(d)), replace=False)
                           .tolist())
                sub = np.isin(t.date_i[rows], list(keep))
            res = beam_search(t, rows, h, A, sub, verbose=(seed == 0))
            if not res:
                continue
            top = res[0]
            out.append({"h": h, "seed": seed, "train_mean": top["mean"],
                        "train_n": top["n"], "train_win": top["win"],
                        "rule": top["rule"],
                        "runners_up": res[1:6]})
            print(f"  seed {seed}: ${top['mean']:+.2f}/tkt n={top['n']} "
                  f"| {' AND '.join(top['rule'])}", flush=True)
    write_json("rules_search.json", out)
    out.sort(key=lambda r: -r["train_mean"])
    print("\n=== best-on-train rules, all horizons ===")
    for r in out[:12]:
        print(f"  {r['h']:>5} s{r['seed']} ${r['train_mean']:+8.2f}/tkt "
              f"n={r['train_n']:>5} | {' AND '.join(r['rule'])}")


def stage_null(n=2000, h="h30", seed=0):
    """UNSEARCHED null: rules drawn from the same generator with the same
    TRAIN quantiles, never fitted, evaluated once on the held-out year."""
    t = Table()
    rows = np.flatnonzero(t.mask(split=0, dec=RTH, h=h))
    A = atoms(t, rows)
    rng = np.random.default_rng(seed)
    res = []
    for _ in range(n):
        k = rng.integers(2, DEPTH + 1)
        idx = rng.choice(len(A), k, replace=False)
        rule = [A[i][0] for i in idx]
        fams = [c.split("<=")[0].split(">")[0] for c in rule]
        if len(set(fams)) != len(fams):
            continue
        mtr = apply_rule(t, rule, h, split=0)
        if mtr.sum() < MIN_N:
            continue
        mo = apply_rule(t, rule, h, split=1)
        if mo.sum() < 60:
            continue
        p = t.pnl[h][mo]
        res.append({"rule": rule, "train_n": int(mtr.sum()),
                    "train_mean": round(float(t.pnl[h][mtr].mean()), 2),
                    "oos_n": int(mo.sum()),
                    "oos_mean": round(float(p.mean()), 2)})
    v = np.array([r["oos_mean"] for r in res])
    stats = {"h": h, "drawn": n, "kept": len(res),
             "mean": round(float(v.mean()), 2), "sd": round(float(v.std()), 2),
             "median": round(float(np.median(v)), 2),
             "p90": round(float(np.percentile(v, 90)), 2),
             "p95": round(float(np.percentile(v, 95)), 2),
             "p99": round(float(np.percentile(v, 99)), 2),
             "max": round(float(v.max()), 2),
             "frac_positive": round(float((v > 0).mean()), 4)}
    write_json(f"rules_null_{h}.json", {"stats": stats, "rules": res})
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    a = sys.argv
    st = a[a.index("--stage") + 1] if "--stage" in a else "search"
    if st == "search":
        stage_search(int(a[a.index("--seeds") + 1]) if "--seeds" in a else 5)
    else:
        stage_null(int(a[a.index("--n") + 1]) if "--n" in a else 2000,
                   a[a.index("--h") + 1] if "--h" in a else "h30")
