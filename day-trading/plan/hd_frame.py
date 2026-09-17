"""HARNESS-DIAGNOSTIC control 5: frame ablation -- relax ONE constraint at a
time on exactly the same data, and see which constraint the money is behind.

THE GRID.  Every constraint in the user's frame can be tested on the Polygon
grouped-daily tape, because gd carries the REGULAR-SESSION open and close for
every US ticker (validated in plan/hd_lib: gd `o` matches the 09:30 minute-bar
open to 0.0000% on 789 sampled symbol-days).  So one instrument answers all
five rows:

    buy at O[t], sell at C[t]        = the same-day frame
    buy at O[t], sell at O[t+1]      = the same-day constraint relaxed
    short instead of long            = the long-only constraint relaxed
    0 bps instead of 10 bps a side   = the cost constraint relaxed
    liquid universe instead of halal = the halal constraint relaxed
    2.77 bps (measured half-spread)  = the market-order constraint relaxed

and it does so on 4,000+ names a day, which no minute-bar cache in this repo
covers for the non-halal arm.

THE POLICY FAMILY.  Deliberately tiny and entirely pre-open: rank the day's
eligible names on ONE feature built only from sessions strictly before t,
take the top 7 at $15,000 each -- the account's own ticket ladder -- and
flatten at the stated exit.  Ten features, both signs, twenty policies.  The
SAME twenty are searched under every setting, so the CONTRAST between the two
columns is what is being reported, not the level.  The best-of-twenty is an
in-sample maximum and is stated as such; the random-pick control under the
same setting is printed beside it so the search premium is visible.

`gap` is deliberately NOT a feature: a policy that buys at the open cannot
have observed the open.

Usage:  python plan/hd_frame.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_lib as H                                            # noqa: E402

NTICK = 7
LOOK = 25                     # sessions of history a feature may need
UNIVERSES = ["halal_strict", "halal_wide", "liquid"]
MAXR = 0.5


def gd_full(dates):
    per = [H.gd_day(d) for d in dates]
    syms = sorted(set().union(*[set(p) for p in per]))
    sidx = {s: i for i, s in enumerate(syms)}
    D, S = len(dates), len(syms)
    A = {k: np.full((D, S), np.nan) for k in "ohlcv"}
    for i, p in enumerate(per):
        for s, x in p.items():
            j = sidx[s]
            for k in "ohlcv":
                val = x.get(k)
                if val is not None:
                    A[k][i, j] = val
    return syms, sidx, A


def build_features(A):
    """F[name] -> (D, S) array, every entry computed from rows < t."""
    O, HI, LO, C, V = A["o"], A["h"], A["l"], A["c"], A["v"]
    D, S = C.shape
    with np.errstate(all="ignore"):
        ret = np.full((D, S), np.nan)
        ret[1:] = C[1:] / C[:-1] - 1.0
        F = {}
        F["r1"] = np.roll(ret, 1, axis=0)                       # C[t-1]/C[t-2]
        r5 = np.full((D, S), np.nan)
        r5[6:] = C[5:-1] / C[:-6] - 1.0
        F["r5"] = r5
        r20 = np.full((D, S), np.nan)
        r20[21:] = C[20:-1] / C[:-21] - 1.0
        F["r20"] = r20
        oc = C / O - 1.0
        F["oc_prev"] = np.roll(oc, 1, axis=0)
        ovn = np.full((D, S), np.nan)
        ovn[1:] = O[1:] / C[:-1] - 1.0
        F["ovn_prev"] = np.roll(ovn, 1, axis=0)
        F["lpx"] = np.log(np.maximum(np.roll(C, 1, axis=0), 1e-9))
        dv = C * V
        ldv = np.full((D, S), np.nan)
        for t in range(21, D):
            ldv[t] = np.nanmedian(dv[t - 20:t], axis=0)
        F["ldv"] = np.log1p(ldv)
        vol20 = np.full((D, S), np.nan)
        for t in range(22, D):
            vol20[t] = np.nanstd(ret[t - 20:t], axis=0)
        F["vol20"] = vol20
        rng1 = (HI - LO) / np.maximum(C, 1e-9)
        F["rng_prev"] = np.roll(rng1, 1, axis=0)
        d60 = np.full((D, S), np.nan)
        for t in range(21, D):
            d60[t] = C[t - 1] / np.nanmax(C[max(t - 60, 0):t], axis=0) - 1.0
        F["dist_hi60"] = d60
        for k in F:
            F[k][:LOOK] = np.nan
    return F


def run_policy(dates, A, sidx, mem, score, sign, side, exit_mode, cost_bps,
               ntick=NTICK, rng=None):
    """Return (per-day $ P&L list, per-ticket $ list).

    side      +1 long, -1 short
    exit_mode 'close'  sell at C[t]   |  'next_open'  sell at O[t+1]
    """
    O, C = A["o"], A["c"]
    D = len(dates)
    day_pnl, tk = [], []
    cf = cost_bps / 1e4
    hi = D - (1 if exit_mode == "next_open" else 0)
    for t in range(LOOK, hi):
        names = mem.get(dates[t], set())
        if not names:
            continue
        j = np.array([sidx[s] for s in names if s in sidx], int)
        if j.size < ntick:
            continue
        px_in = O[t, j]
        px_out = C[t, j] if exit_mode == "close" else O[t + 1, j]
        s = score[t, j] if score is not None else rng.random(j.size)
        ok = (np.isfinite(px_in) & np.isfinite(px_out) & (px_in > 0)
              & (px_out > 0) & np.isfinite(s)
              & (np.abs(px_out / px_in - 1.0) < MAXR))
        if ok.sum() < ntick:
            continue
        s = np.where(ok, s * sign, -np.inf)
        top = np.argsort(-s)[:ntick]
        r = px_out[top] / px_in[top] - 1.0
        # toll is charged on the entry notional N and on the exit notional
        # N(1+r), whichever side we are; the P&L itself flips with `side`
        pnl = H.TICKET * (side * r - cf * (2.0 + r))
        day_pnl.append(float(pnl.sum()))
        tk.extend([float(x) for x in pnl])
    return np.array(day_pnl), np.array(tk)


def summ(day_pnl, tk, dates_used, label):
    if tk.size == 0:
        return {"label": label, "tickets": 0, "per_month": 0.0}
    nmon = len(day_pnl) / H.DAYS_PER_MONTH
    eq = np.cumsum(day_pnl)
    return {"label": label, "days": int(day_pnl.size), "tickets": int(tk.size),
            "per_ticket": round(float(tk.mean()), 2),
            "per_day": round(float(day_pnl.mean()), 2),
            "per_month": round(float(day_pnl.sum()) / nmon, 2),
            "total": round(float(day_pnl.sum()), 2),
            "max_dd": round(float(np.min(eq - np.maximum.accumulate(eq))), 2),
            "ex_best": round(float(tk.sum() - tk.max()), 2),
            "win_rate": round(float((tk > 0).mean()), 4)}


def best_policy(dates, A, sidx, mem, F, setting, seeds=12):
    """Search the 20 (feature, sign) policies -- and both sides when the
    long-only constraint is off -- under one setting."""
    sides = [1] if setting["long_only"] else [1, -1]
    rows = []
    for name, arr in F.items():
        for sign in (1, -1):
            for side in sides:
                dp, tk = run_policy(dates, A, sidx, mem, arr, sign, side,
                                    setting["exit_mode"], setting["cost_bps"])
                if tk.size == 0:
                    continue
                s = summ(dp, tk, dates, f"{name}{'+' if sign>0 else '-'}"
                         f"{'L' if side>0 else 'S'}")
                rows.append(s)
    rows.sort(key=lambda r: -r["per_month"])
    rnd = []
    for k in range(seeds):
        rng = np.random.default_rng(700 + k)
        dp, tk = run_policy(dates, A, sidx, mem, None, 1, sides[0],
                            setting["exit_mode"], setting["cost_bps"], rng=rng)
        rnd.append(summ(dp, tk, dates, f"rand{k}")["per_month"])
    return {"best": rows[0] if rows else None,
            "median_policy_per_month": (round(float(np.median(
                [r["per_month"] for r in rows])), 2) if rows else None),
            "random_per_month_mean": round(float(np.mean(rnd)), 2),
            "random_per_month_sd": round(float(np.std(rnd, ddof=1)), 2),
            "n_policies": len(rows),
            "top5": rows[:5]}


def main():
    dates = H.study_dates()
    print(f"[frame] {len(dates)} dates", flush=True)
    syms, sidx, A = gd_full(dates)
    print(f"[frame] gd {A['c'].shape}", flush=True)
    F = build_features(A)
    print(f"[frame] {len(F)} features: {sorted(F)}", flush=True)
    MEM = {k: H.members(k, dates) for k in UNIVERSES}

    BASE = {"exit_mode": "close", "long_only": True,
            "cost_bps": H.FEE_BPS, "universe": "halal_strict"}

    def setting(**kw):
        s = dict(BASE)
        s.update(kw)
        return s

    rows = []
    cases = [
        ("BASE (all constraints on)", setting(), "halal_strict"),
        ("same-day OFF (hold overnight)", setting(exit_mode="next_open"),
         "halal_strict"),
        ("long-only OFF (short allowed)", setting(long_only=False),
         "halal_strict"),
        ("costs OFF (0 bps/side)", setting(cost_bps=0.0), "halal_strict"),
        ("market-order OFF (2.77 bps = measured half-spread)",
         setting(cost_bps=2.77), "halal_strict"),
        ("halal OFF (all liquid names)", setting(universe="liquid"),
         "liquid"),
        ("halal PARTIAL (wide halal universe)",
         setting(universe="halal_wide"), "halal_wide"),
    ]
    out = {}
    for label, st, uni in cases:
        r = best_policy(dates, A, sidx, MEM[uni], F, st)
        out[label] = {"setting": st, **r}
        b = r["best"]
        print(f"[frame] {label:52s} best ${b['per_month']:+10,.0f}/mo "
              f"({b['label']:>10s}, ${b['per_ticket']:+7.2f}/tkt)  "
              f"median ${r['median_policy_per_month']:+10,.0f}  "
              f"random ${r['random_per_month_mean']:+10,.0f}"
              f" +/- {r['random_per_month_sd']:,.0f}", flush=True)
        rows.append((label, b["per_month"], r["random_per_month_mean"]))

    # the 2x5 table the mandate asked for: constraint ON vs OFF
    base = out["BASE (all constraints on)"]
    table = []
    for cname, off_key in (
            ("same-day only", "same-day OFF (hold overnight)"),
            ("long-only (halal)", "long-only OFF (short allowed)"),
            ("costs charged", "costs OFF (0 bps/side)"),
            ("market orders (10 bps)",
             "market-order OFF (2.77 bps = measured half-spread)"),
            ("halal screen", "halal OFF (all liquid names)")):
        table.append({
            "constraint": cname,
            "on_per_month": base["best"]["per_month"],
            "off_per_month": out[off_key]["best"]["per_month"],
            "delta": round(out[off_key]["best"]["per_month"]
                           - base["best"]["per_month"], 2),
            "on_random": base["random_per_month_mean"],
            "off_random": out[off_key]["random_per_month_mean"],
            "delta_random": round(out[off_key]["random_per_month_mean"]
                                  - base["random_per_month_mean"], 2)})
    print("\n[frame] ABLATION TABLE ($/month, best of the same 20 simple "
          "policies; random control in brackets)", flush=True)
    for r in table:
        print(f"  {r['constraint']:24s} ON ${r['on_per_month']:+10,.0f} "
              f"[{r['on_random']:+9,.0f}]   OFF ${r['off_per_month']:+10,.0f} "
              f"[{r['off_random']:+9,.0f}]   delta ${r['delta']:+10,.0f} "
              f"[{r['delta_random']:+9,.0f}]", flush=True)

    H.write("frame.json", {"cases": out, "table": table})
    print("[frame] wrote frame.json", flush=True)


if __name__ == "__main__":
    main()
