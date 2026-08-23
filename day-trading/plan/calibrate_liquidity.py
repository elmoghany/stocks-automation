"""Calibrate the bar-only liquidity estimators against REAL books.

Reads data/liquidity_truth.json (the book observations live sessions
actually logged -- built by plan/extract_liquidity_truth.py) and, for
each observation, computes every estimator in
plan/liquidity_estimators.py from the bars STRICTLY BEFORE the book
read (decision ts floored to the minute, so only completed bars are
seen -- exactly what live knew).

Reports, per phase (premarket / post-open):
  1. Spearman rank correlation of each estimator vs the observed
     inside spread, with n -- including the INCUMBENT bar-range proxy
     (rotation_sim.spread_proxy's statistic) as the baseline to beat;
  2. a head-to-head on the common subset where every estimator is
     defined, with a paired bootstrap on (winner - incumbent);
  3. a cluster-collapsed check (median per symbol-day) because serial
     reads of the same book inflate raw n;
  4. the mapping of the live 0.5% cap into winner-estimator units:
     the threshold that best separates observed<=0.5% books from
     observed>0.5% books, with a bootstrap CI;
  5. depth-side: Spearman of Amihud / no-trade-share vs the logged
     displayed-depth shares (heterogeneous definitions -- reported
     with that caveat).

Idempotent: pure function of the truth file and the bar files.
`python plan/calibrate_liquidity.py` prints the tables and rewrites
data/liquidity_calibration.json. No sim files are touched.
"""

import json
import math
import os
import random
import sys

import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import liquidity_estimators as le  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
TRUTH = os.path.join(ROOT, "data", "liquidity_truth.json")
OUT = os.path.join(ROOT, "data", "liquidity_calibration.json")

ET = "America/New_York"
CAP = 0.5          # the live inside-spread veto cap, percent
LOOKBACK = 30      # bars, CS/AR/Roll/Amihud default
RANGE_LB = 10      # bars, incumbent bar-range proxy (live parity)
BOOT = 2000
SEED = 20260822

# Everything tested against the OBSERVED SPREAD. amihud (x1e6 units)
# and no_trade_share (0..1) are not percent -- ordinal comparisons and
# unit-specific cuts only. They were built as tape-sparseness/depth
# measures and turned out to be premarket's best spread predictors.
SPREAD_COLS = ["bar_range", "corwin_schultz", "abdi_ranaldo", "roll",
               "max_cs_range", "max_ar_range", "amihud",
               "no_trade_share"]


def load_bars(rel):
    """Either bar format (rh_bars lowercase / massive m1 capitalized)
    -> tz-aware ET frame with Open/High/Low/Close/Volume."""
    df = pd.read_csv(os.path.join(ROOT, rel))
    cols = {c.lower(): c for c in df.columns}
    df.index = pd.to_datetime(df[cols["begins_at"]], utc=True,
                              format="mixed").dt.tz_convert(ET)
    out = pd.DataFrame({
        "Open": df[cols["open"]].astype(float).values,
        "High": df[cols["high"]].astype(float).values,
        "Low": df[cols["low"]].astype(float).values,
        "Close": df[cols["close"]].astype(float).values,
        "Volume": df[cols["volume"]].astype(float).values,
    }, index=df.index)
    return out.sort_index()


def decision_ts(date, time_et):
    """Floor the book-read wall clock to the minute: the estimator may
    only see COMPLETED bars, and the bar containing the read was still
    forming when live read the book."""
    hh, mm = time_et[:2], time_et[3:5]
    return pd.Timestamp(f"{date} {hh}:{mm}:00", tz=ET)


def build_samples():
    truth = json.load(open(TRUTH))
    bars_cache = {}
    samples = []
    for r in truth["observations"]:
        if r["requote"] or not r["bars_source"]:
            continue
        src = r["bars_source"]
        if src not in bars_cache:
            bars_cache[src] = load_bars(src)
        df = bars_cache[src]
        ts = decision_ts(r["date"], r["time_et"])
        est = le.estimate_all(df, ts, lookback=LOOKBACK,
                              range_lookback=RANGE_LB)
        # combinations: max() falls back to the defined member
        for combo, a, b in (("max_cs_range", "corwin_schultz",
                             "bar_range"),
                            ("max_ar_range", "abdi_ranaldo",
                             "bar_range")):
            va, vb = est[a], est[b]
            est[combo] = (None if va is None and vb is None
                          else max(x for x in (va, vb) if x is not None))
        samples.append({**r, "ts": str(ts), **est})
    return truth, samples


def rho_n(pairs):
    if len(pairs) < 5:
        return None, None, len(pairs)
    x, y = zip(*pairs)
    rho, p = spearmanr(x, y)
    return float(rho), float(p), len(pairs)


def table_spearman(samples, phase=None, cols=SPREAD_COLS):
    rows = {}
    sub = [s for s in samples
           if (phase is None or s["phase"] == phase)
           and s["spread_pct"] is not None]
    for c in cols:
        pairs = [(s[c], s["spread_pct"]) for s in sub
                 if s[c] is not None]
        rows[c] = rho_n(pairs)
    return rows


def head_to_head(samples, phase, cols, rng):
    """Same-rows comparison + paired bootstrap of (col - bar_range)."""
    sub = [s for s in samples
           if s["phase"] == phase and s["spread_pct"] is not None
           and all(s[c] is not None for c in cols)]
    if len(sub) < 8:
        return None
    out = {"n": len(sub), "rho": {}, "delta_vs_bar_range": {}}
    for c in cols:
        rho, _, _ = rho_n([(s[c], s["spread_pct"]) for s in sub])
        out["rho"][c] = rho
    for c in cols:
        if c == "bar_range":
            continue
        deltas = []
        for _ in range(BOOT):
            bs = [sub[rng.randrange(len(sub))] for _ in range(len(sub))]
            try:
                r1 = spearmanr([s[c] for s in bs],
                               [s["spread_pct"] for s in bs])[0]
                r0 = spearmanr([s["bar_range"] for s in bs],
                               [s["spread_pct"] for s in bs])[0]
            except Exception:
                continue
            if not (math.isnan(r1) or math.isnan(r0)):
                deltas.append(r1 - r0)
        deltas.sort()
        if deltas:
            out["delta_vs_bar_range"][c] = {
                "mean": sum(deltas) / len(deltas),
                "ci90": [deltas[int(0.05 * len(deltas))],
                         deltas[int(0.95 * len(deltas)) - 1]],
                "frac_gt0": sum(d > 0 for d in deltas) / len(deltas),
            }
    return out


def cluster_collapsed(samples, col):
    """Median estimator + median observed spread per (date, symbol,
    phase) -> Spearman. Kills serial-correlation inflation."""
    groups = {}
    for s in samples:
        if s["spread_pct"] is None or s[col] is None:
            continue
        groups.setdefault((s["date"], s["symbol"], s["phase"]),
                          []).append((s[col], s["spread_pct"]))
    pairs = []
    for vals in groups.values():
        xs = sorted(v[0] for v in vals)
        ys = sorted(v[1] for v in vals)
        pairs.append((xs[len(xs) // 2], ys[len(ys) // 2]))
    return rho_n(pairs)


def threshold_map(samples, col, phase=None, rng=None):
    """Map the live 0.5% cap into estimator units: the cut on `col`
    that best separates books observed <=0.5% from >0.5% (balanced
    accuracy), bootstrap CI for the cut."""
    sub = [(s[col], s["spread_pct"] <= CAP) for s in samples
           if (phase is None or s["phase"] == phase)
           and s["spread_pct"] is not None and s[col] is not None]
    n_pass = sum(1 for _, ok in sub if ok)
    if len(sub) < 10 or n_pass < 3 or n_pass > len(sub) - 3:
        return None

    def best_cut(data):
        vals = sorted({v for v, _ in data})
        cuts = [(vals[i] + vals[i + 1]) / 2
                for i in range(len(vals) - 1)] or vals
        best, bacc = None, -1.0
        for c in cuts:
            tp = sum(1 for v, ok in data if ok and v <= c)
            tn = sum(1 for v, ok in data if not ok and v > c)
            npos = sum(1 for _, ok in data if ok)
            nneg = len(data) - npos
            if npos == 0 or nneg == 0:
                continue
            ba = 0.5 * (tp / npos + tn / nneg)
            if ba > bacc:
                bacc, best = ba, c
        return best, bacc

    cut, bacc = best_cut(sub)
    cuts = []
    for _ in range(BOOT):
        bs = [sub[rng.randrange(len(sub))] for _ in range(len(sub))]
        c, _ = best_cut(bs)
        if c is not None:
            cuts.append(c)
    cuts.sort()
    ci = ([cuts[int(0.05 * len(cuts))],
           cuts[int(0.95 * len(cuts)) - 1]] if cuts else None)
    return {"n": len(sub), "n_pass_true": n_pass, "cut": cut,
            "balanced_acc": bacc, "cut_ci90": ci}


def depth_side(samples):
    """Amihud / no-trade-share vs logged displayed depth (shares).
    CAVEAT: depth_kind mixes 'shares to the limit cap' with 'inside
    displayed' -- ordinal at best."""
    out = {}
    sub = [s for s in samples if s["depth_shares"] not in (None, 0)
           and s["depth_kind"] in ("ask_to_cap", "ask_inside")]
    for col, sign in (("amihud", -1), ("no_trade_share", -1)):
        pairs = [(s[col], math.log(s["depth_shares"])) for s in sub
                 if s[col] is not None]
        rho, p, n = rho_n(pairs)
        out[col] = {"rho_vs_log_depth": rho, "p": p, "n": n,
                    "expected_sign": sign}
    return out


def fmt(v):
    return " --- " if v is None else f"{v:+.3f}"


def main():
    rng = random.Random(SEED)
    truth, samples = build_samples()
    n_all = len(samples)
    res = {"config": {"lookback_bars": LOOKBACK,
                      "range_lookback": RANGE_LB, "cap_pct": CAP,
                      "bootstrap": BOOT, "seed": SEED},
           "n_samples": n_all}

    print(f"\n=== liquidity calibration: {n_all} primary observations "
          f"with bars ===")
    for phase in ("premarket", "postopen", None):
        label = phase or "pooled"
        tab = table_spearman(samples, phase)
        res.setdefault("spearman", {})[label] = tab
        print(f"\nSpearman vs observed spread -- {label}")
        print(f"{'estimator':16s} {'rho':>8s} {'p':>10s} {'n':>4s}")
        for c in SPREAD_COLS:
            rho, p, n = tab[c]
            mark = " <- incumbent" if c == "bar_range" else ""
            print(f"{c:16s} {fmt(rho):>8s} "
                  f"{('---' if p is None else f'{p:.2g}'):>10s} "
                  f"{n:4d}{mark}")

    # head-to-head, common rows only
    res["head_to_head"] = {}
    for phase in ("premarket", "postopen"):
        hh = head_to_head(samples, phase, SPREAD_COLS, rng)
        res["head_to_head"][phase] = hh
        if hh:
            print(f"\nHead-to-head ({phase}, common n={hh['n']}):")
            for c in SPREAD_COLS:
                print(f"  {c:16s} rho {fmt(hh['rho'][c])}")
            for c, d in hh["delta_vs_bar_range"].items():
                print(f"  {c:16s} delta vs incumbent "
                      f"{d['mean']:+.3f} ci90 "
                      f"[{d['ci90'][0]:+.3f},{d['ci90'][1]:+.3f}] "
                      f"P(delta>0)={d['frac_gt0']:.2f}")

    # cluster-collapsed (anti serial-correlation)
    print("\nCluster-collapsed (median per symbol-day-phase):")
    res["cluster_collapsed"] = {}
    for c in SPREAD_COLS:
        rho, p, n = cluster_collapsed(samples, c)
        res["cluster_collapsed"][c] = {"rho": rho, "p": p, "n": n}
        print(f"  {c:16s} rho {fmt(rho)} "
              f"(p {'---' if p is None else f'{p:.2g}'}, n={n})")

    # lookback sensitivity
    print("\nLookback sensitivity (premarket rho):")
    res["lookback_sensitivity"] = {}
    base = json.load(open(TRUTH))
    for lb in (15, 30, 60):
        cache = {}
        subs = []
        for r in base["observations"]:
            if r["requote"] or not r["bars_source"] or \
                    r["spread_pct"] is None or r["phase"] != "premarket":
                continue
            if r["bars_source"] not in cache:
                cache[r["bars_source"]] = load_bars(r["bars_source"])
            ts = decision_ts(r["date"], r["time_et"])
            row = {"spread_pct": r["spread_pct"]}
            df = cache[r["bars_source"]]
            row["corwin_schultz"] = le.corwin_schultz(df, ts, lb)
            row["abdi_ranaldo"] = le.abdi_ranaldo(df, ts, lb)
            row["roll"] = le.roll(df, ts, lb)
            subs.append(row)
        entry = {}
        for c in ("corwin_schultz", "abdi_ranaldo", "roll"):
            rho, p, n = rho_n([(s[c], s["spread_pct"]) for s in subs
                               if s[c] is not None])
            entry[c] = {"rho": rho, "n": n}
            print(f"  lb={lb:3d} {c:16s} rho {fmt(rho)} (n={n})")
        res["lookback_sensitivity"][lb] = entry

    # cap mapping
    print(f"\nMapping the live {CAP}% cap into estimator units "
          f"(balanced-accuracy cut, bootstrap ci90):")
    res["cap_mapping"] = {}
    for phase in ("premarket", None):
        label = phase or "pooled"
        res["cap_mapping"][label] = {}
        for c in SPREAD_COLS:
            tm = threshold_map(samples, c, phase, rng)
            res["cap_mapping"][label][c] = tm
            if tm:
                print(f"  {label:9s} {c:16s} cut {tm['cut']:7.3f} "
                      f"ci90 [{tm['cut_ci90'][0]:.3f},"
                      f"{tm['cut_ci90'][1]:.3f}] "
                      f"bacc {tm['balanced_acc']:.2f} "
                      f"(n={tm['n']}, true-pass={tm['n_pass_true']})")

    # ensemble diagnostic (NOT deployable -- ranks are computed within
    # this sample; reported only to show how much a combination could
    # add over the single best estimator)
    pre = [s for s in samples if s["phase"] == "premarket"
           and s["spread_pct"] is not None
           and all(s[c] is not None
                   for c in ("abdi_ranaldo", "amihud",
                             "no_trade_share"))]
    if len(pre) >= 10:
        def ranks(vals):
            order = sorted(range(len(vals)), key=lambda i: vals[i])
            rk = [0.0] * len(vals)
            for pos, i in enumerate(order):
                rk[i] = pos
            return rk
        cols3 = ("abdi_ranaldo", "amihud", "no_trade_share")
        rks = [ranks([s[c] for s in pre]) for c in cols3]
        score = [sum(r[i] for r in rks) / 3 for i in range(len(pre))]
        rho, p, n = rho_n(list(zip(score,
                                   [s["spread_pct"] for s in pre])))
        res["ensemble_rank_mean_premarket"] = {"rho": rho, "p": p,
                                               "n": n, "cols": cols3}
        print(f"\nEnsemble diagnostic (mean rank of AR+amihud+"
              f"no_trade, premarket): rho {fmt(rho)} (n={n}) -- "
              f"within-sample, not deployable")

    # depth side
    res["depth_side"] = depth_side(samples)
    print("\nDepth side (vs log displayed shares, mixed definitions):")
    for c, d in res["depth_side"].items():
        print(f"  {c:16s} rho {fmt(d['rho_vs_log_depth'])} "
              f"(p {'---' if d['p'] is None else f'{d['p']:.2g}'}, "
              f"n={d['n']}, expected sign {d['expected_sign']})")

    with open(OUT, "w") as f:
        json.dump(res, f, indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
