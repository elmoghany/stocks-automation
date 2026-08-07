"""CAUSAL VOLUME MEASURES: can we reproduce the backtest's rvol gate
using only information available at decision time?

THE PROBLEM (found by the 2026-08-07 audit): the backtest's gate is
  full-day volume / 50-day average >= 5
but full-day volume is unknowable at 7AM. Live has been dividing
partial-day volume by a full-day average, which under-reports rvol all
morning and rejected a winner (PN, 2026-08-06, real rvol 16.1, live
computed 0.9).

THE IDEA: volume accumulates along a predictable intraday profile. If
we know what fraction of a typical day's volume has printed by time T,
we can PROJECT the full day from the part we can see:
  projected_full = cumulative_by_T / profile_fraction(T)
  projected_rvol = projected_full / 50-day average
This is fully causal.

This script (a) builds the intraday volume profile empirically from the
cached 1-minute bars, then (b) measures, over the real candidate pool,
how well projected rvol at 07:00 / 08:00 / 09:45 / 10:30 reproduces the
full-day rvol >= 5 selection -- recall, precision, and the rank
correlation. Output: data/massive/rvol_causal.json
"""

import json
import math
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
M1 = ROOT / "data/massive/m1"
CHECKPOINTS = ["07:00", "08:00", "09:45", "10:30"]
GATE = 5.0


def load_pool():
    """Candidates with full-day volume and the gate's rvol."""
    out = {}
    for lab in ("year", "y2025"):
        f = ROOT / f"data/massive/gappers2_{lab}.json"
        if not f.exists():
            continue
        for c in json.loads(f.read_text()):
            if c.get("hist_n", 0) >= 50 and c.get("rvol") and c.get("volume"):
                out[(c["symbol"], c["date"])] = c
    return out


def cum_by(df, hhmm):
    """Cumulative volume from the session start through hh:mm ET."""
    h, m = int(hhmm[:2]), int(hhmm[3:])
    idx = df.index
    mask = (idx.hour * 60 + idx.minute) <= (h * 60 + m)
    return float(df.loc[mask, "Volume"].sum())


def main():
    pool = load_pool()
    print(f"pool candidates with hist>=50: {len(pool):,}")

    # ---- (a) build the intraday volume profile -------------------------
    # fraction of the FULL day's volume printed by each checkpoint,
    # averaged across every cached symbol-day (market-wide profile)
    fracs = defaultdict(list)
    used = 0
    for f in M1.glob("*.csv"):
        try:
            df = pd.read_csv(f, index_col=0, parse_dates=True)
        except Exception:
            continue
        if len(df) < 60 or "Volume" not in df:
            continue
        idx = df.index
        if idx.tz is None:
            continue
        df.index = idx.tz_convert("America/New_York")
        tot = float(df["Volume"].sum())
        if tot <= 0:
            continue
        used += 1
        for cp in CHECKPOINTS:
            fracs[cp].append(cum_by(df, cp) / tot)
    profile = {cp: (sum(v) / len(v)) for cp, v in fracs.items() if v}
    print(f"\nINTRADAY VOLUME PROFILE (from {used:,} cached symbol-days)")
    for cp in CHECKPOINTS:
        p = profile.get(cp)
        if p:
            med = sorted(fracs[cp])[len(fracs[cp]) // 2]
            print(f"  by {cp}: mean {100*p:5.1f}% of the day's volume "
                  f"printed (median {100*med:5.1f}%)")

    # ---- (b) score causal proxies against the real gate -----------------
    rows = []
    for f in M1.glob("*.csv"):
        sym, date = f.stem.rsplit("_", 1)
        c = pool.get((sym, date))
        if not c:
            continue
        try:
            df = pd.read_csv(f, index_col=0, parse_dates=True)
        except Exception:
            continue
        if len(df) < 60 or df.index.tz is None:
            continue
        df.index = df.index.tz_convert("America/New_York")
        avg50 = c["volume"] / c["rvol"] if c["rvol"] else None
        if not avg50 or avg50 <= 0:
            continue
        r = dict(sym=sym, date=date, true_rvol=c["rvol"],
                 gain=c.get("gain_pct"))
        for cp in CHECKPOINTS:
            frac = profile.get(cp) or 0.0
            cum = cum_by(df, cp)
            r[f"cum_{cp}"] = cum
            r[f"naive_{cp}"] = cum / avg50                  # the BUG
            r[f"proj_{cp}"] = (cum / frac / avg50) if frac > 0 else None
        rows.append(r)
    print(f"\nscored {len(rows):,} candidate-days that have minute bars")

    def spearman(a, b):
        def rank(x):
            order = sorted(range(len(x)), key=lambda i: x[i])
            rk = [0] * len(x)
            for pos, i in enumerate(order):
                rk[i] = pos
            return rk
        ra, rb = rank(a), rank(b)
        n = len(a)
        ma, mb = sum(ra) / n, sum(rb) / n
        num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
        den = math.sqrt(sum((x - ma) ** 2 for x in ra)
                        * sum((y - mb) ** 2 for y in rb))
        return num / den if den else float("nan")

    truth = [r["true_rvol"] >= GATE for r in rows]
    n_true = sum(truth)
    print(f"names the REAL gate admits (full-day rvol >= {GATE}): "
          f"{n_true:,} of {len(rows):,}")
    print(f"\n{'measure':<16}{'admits':>8}{'recall':>8}{'precis':>8}"
          f"{'spearman':>10}")
    out = {"profile": profile, "checkpoints": {}}
    for cp in CHECKPOINTS:
        for kind in ("naive", "proj"):
            vals = [r[f"{kind}_{cp}"] for r in rows]
            if any(v is None for v in vals):
                continue
            pred = [v >= GATE for v in vals]
            tp = sum(1 for p, t in zip(pred, truth) if p and t)
            fp = sum(1 for p, t in zip(pred, truth) if p and not t)
            rec = tp / n_true if n_true else 0
            pre = tp / (tp + fp) if (tp + fp) else 0
            rho = spearman(vals, [r["true_rvol"] for r in rows])
            print(f"{kind}@{cp:<10}{tp+fp:>8,}{100*rec:>7.0f}%"
                  f"{100*pre:>7.0f}%{rho:>10.3f}")
            out["checkpoints"][f"{kind}@{cp}"] = dict(
                admits=tp + fp, recall=rec, precision=pre, spearman=rho)
    (ROOT / "data/massive/rvol_causal.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
