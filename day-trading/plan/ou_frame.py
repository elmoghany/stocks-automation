"""OPEN-UNIVERSE (2026-09-17) TEST 1: frame ablation on the open universe.

THE QUESTION the mandate puts first: "the zero-cost ceiling and the random
baseline on 1,500+ names vs the 64/283 measured before -- does BREADTH change
the ceiling?"

THE INSTRUMENT is HARNESS-DIAGNOSTIC's (plan/hd_frame.py), reused unchanged so
the two studies are comparable line for line: the Polygon grouped-daily tape,
whose `o` matches the 09:30 minute-bar open to 0.0000% median on 789 sampled
symbol-days, buy at O[t] and flatten at C[t], twenty deliberately tiny
policies -- rank the day's eligible names on ONE feature built only from
sessions strictly before t, both signs, ten features -- take the top 7 at
$15,000 each.  `gap` is excluded by construction: a policy that buys at the
open cannot have observed the open.  The best-of-twenty is an IN-SAMPLE
maximum and is labelled as one; the matched random control under the identical
setting is printed beside it, so the search premium is always visible.

WHAT IS NEW HERE
  * the universe is the OPEN one -- 2,532 operating companies a day of every
    sector, against halal_strict's 64 and halal_wide's 283;
  * a fourth cost column, `measured`, from plan/ou_cost.DailyCost: the same
    max(Corwin-Schultz, Abdi-Ranaldo) spread and the same Y = 1.0 square-root
    impact term COST-REBASE charges, but computed per (name, date) for all
    2,532 names instead of assumed;
  * a large-cap slice and a sector-neutral variant (the mandate's Test 4),
    because the whole point of breadth is that the books are cheaper.

CONTROLS on every row: 30-seed random picking with identical eligibility and
identical fills; the inverted policy (it is one of the twenty by
construction); and the percentile of the best policy against the 30 seeds.

Usage:  python plan/ou_frame.py [--seeds 30]
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ou_lib as L                                            # noqa: E402
import ou_cost as OC                                          # noqa: E402

NTICK = 7
LOOK = 25
MAXR = 0.5
SEEDS = 30

FEATURES = ["r1", "r5", "r20", "oc_prev", "ovn_prev", "lpx", "ldv", "vol20",
            "rng_prev", "dist_hi60"]


def build_features(A):
    """F[name] -> (D, S); every entry a function of rows < t only.

    Byte-for-byte the feature block of plan/hd_frame.build_features.
    """
    O, HI, LO, C, V = A["o"], A["h"], A["l"], A["c"], A["v"]
    D, S = C.shape
    with np.errstate(all="ignore"):
        ret = np.full((D, S), np.nan)
        ret[1:] = C[1:] / C[:-1] - 1.0
        F = {}
        F["r1"] = np.roll(ret, 1, axis=0)
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


class Pre:
    """Per-(universe, exit_mode) precomputation.

    The gd cross-section is the same for every one of the 20 policies and
    every one of the 30 random seeds, so the eligible index vector, the two
    legs, the return and the per-name measured cost are built ONCE per
    (universe, exit_mode, cost) and only the SCORE changes between runs.
    Nothing here depends on the score, so no ordering decision can leak into
    the eligibility -- which is exactly the "identical eligibility and fills"
    the control protocol requires.
    """

    def __init__(self, dates, A, sidx, mem, exit_mode, dc, syms, groups=None):
        O, C = A["o"], A["c"]
        D = len(dates)
        hi = D - (1 if exit_mode == "next_open" else 0)
        self.rows = []
        for t in range(LOOK, hi):
            names = mem.get(dates[t])
            if not names:
                continue
            j = np.fromiter((sidx[s] for s in names if s in sidx), int)
            if j.size < NTICK:
                continue
            px_in = O[t, j]
            px_out = C[t, j] if exit_mode == "close" else O[t + 1, j]
            with np.errstate(all="ignore"):
                ok = (np.isfinite(px_in) & np.isfinite(px_out) & (px_in > 0)
                      & (px_out > 0)
                      & (np.abs(px_out / px_in - 1.0) < MAXR))
            if ok.sum() < NTICK:
                continue
            j = j[ok]
            with np.errstate(all="ignore"):
                r = px_out[ok] / px_in[ok] - 1.0
            g = groups[t, j] if groups is not None else None
            self.rows.append((t, dates[t], j, r, g))
        self.cost = {}
        self.dc = dc
        self.syms = syms

    def cf(self, cost, k):
        """Per-name cost fraction for row k under `cost`."""
        t, date, j, r, g = self.rows[k]
        if cost == "zero":
            return 0.0
        if cost == "flat10":
            return L.FEE_BPS / 1e4
        if cost != "measured":
            return float(cost) / 1e4
        c = self.cost.get(k)
        if c is None:
            c = self.dc.row(date, [self.syms[x] for x in j]) / 1e4
            self.cost[k] = c
        return c


def run_pre(pre, score, sign, side, cost, ntick=NTICK, rng=None,
            neutral=False, cap=True):
    """(day $ P&L, per-ticket $, dates used) for one policy over a Pre.

    `cap=True` charges the account's real ladder (6 x $15,000 + 1 x $10,000
    at k = 7, so the day never exceeds the $100,000 same-day cap).
    `cap=False` reproduces HARNESS-DIAGNOSTIC's 7 x $15,000 = $105,000, which
    is what every hd_frame number in the index was computed with; both are
    reported so the two studies stay comparable.
    """
    sizes = L.ticket_sizes(ntick) if cap else np.full(ntick, L.TICKET)
    day_pnl, tk, used = [], [], []
    for k, (t, date, j, r, g) in enumerate(pre.rows):
        s = score[t, j] if score is not None else rng.random(j.size)
        sv = np.where(np.isfinite(s), s * sign, -np.inf)
        if not neutral:
            if np.isfinite(sv).sum() < ntick:
                continue
            top = np.argpartition(-sv, ntick - 1)[:ntick]
            top = top[np.argsort(-sv[top])]
        else:
            order = np.argsort(-sv)
            seen, tl = set(), []
            for q in order:
                if not np.isfinite(sv[q]):
                    break
                if g[q] in seen:
                    continue
                seen.add(g[q])
                tl.append(q)
                if len(tl) == ntick:
                    break
            if len(tl) < ntick:
                continue
            top = np.array(tl, int)
        rr = r[top]
        cf = pre.cf(cost, k)
        cf = cf[top] if isinstance(cf, np.ndarray) else cf
        pnl = sizes[:len(top)] * (side * rr - cf * (2.0 + rr))
        day_pnl.append(float(pnl.sum()))
        tk.extend(float(x) for x in pnl)
        used.append(date)
    return np.array(day_pnl), np.array(tk), used


def search(pre, F, setting, seeds=SEEDS, neutral=False):
    sides = [1] if setting.get("long_only", True) else [1, -1]
    cap = bool(setting.get("cap", False))
    rows = []
    for name in FEATURES:
        arr = F[name]
        for sign in (1, -1):
            for side in sides:
                dp, tk, used = run_pre(pre, arr, sign, side, setting["cost"],
                                       neutral=neutral, cap=cap)
                if tk.size == 0:
                    continue
                lab = f"{name}{'+' if sign > 0 else '-'}" \
                      f"{'L' if side > 0 else 'S'}"
                rows.append(L.summarise(dp, used, tk, lab))
    rows.sort(key=lambda r: -r["per_month"])
    rnd = []
    for k in range(seeds):
        rng = np.random.default_rng(700 + k)
        dp, tk, used = run_pre(pre, None, 1, sides[0], setting["cost"],
                               rng=rng, neutral=neutral, cap=cap)
        rnd.append(L.summarise(dp, used, tk, f"rand{k}"))
    rm = np.array([r["per_month"] for r in rnd])
    rt = np.array([r["per_ticket"] for r in rnd if r["per_ticket"]])
    best = rows[0] if rows else None
    return {
        "best": best,
        "pct_vs_random": L.percentile_of(best["per_month"], rm) if best
        else None,
        "median_policy_per_month": round(float(np.median(
            [r["per_month"] for r in rows])), 2) if rows else None,
        "random_per_month_mean": round(float(rm.mean()), 2),
        "random_per_month_sd": round(float(rm.std(ddof=1)), 2),
        "random_per_ticket_mean": round(float(rt.mean()), 2) if rt.size else None,
        "edge_per_ticket": round(best["per_ticket"] - float(rt.mean()), 2)
        if best and rt.size else None,
        "n_policies": len(rows),
        "top5": rows[:5],
        "worst": rows[-1] if rows else None,
    }


def minute_close_matrix(dates, sidx, nsym):
    """(D, S) matrix of the 15:59 minute CLOSE and the 09:30 minute OPEN for
    the m1o subset, plus the coverage mask.

    HARNESS-DIAGNOSTIC validated that gd `o` IS the 09:30 minute-bar open to
    0.0000% median, but gd `c` is the CLOSING AUCTION print and sits 4.83 bps
    (median) from the last regular-session minute close.  4.83 bps on a
    $15,000 ticket is $7.25 -- a quarter of the whole round-trip toll -- so
    the mandate's "flatten at 15:59" is NOT the same trade as "sell at the gd
    close", and this line reports both rather than assuming they agree.
    """
    import ou_table as OTB
    D = len(dates)
    di = {d: i for i, d in enumerate(dates)}
    C59 = np.full((D, nsym), np.nan)
    O30 = np.full((D, nsym), np.nan)
    uni = L.universe()
    need = sorted({r[0] for d in dates for r in uni.get(d, [])[:L.MINUTE_TOP]})
    k1559 = L.idx("15:59")
    k0930 = L.idx("09:30")
    got = 0
    for sym in need:
        j = sidx.get(sym)
        if j is None:
            continue
        rec = OTB.load_symbol(sym)
        if rec is None:
            continue
        ds, o, h, l, c, v = rec
        rows = np.array([di[d] for d in ds if d in di])
        src = np.array([i for i, d in enumerate(ds) if d in di])
        if not rows.size:
            continue
        C59[rows, j] = c[src, k1559]
        O30[rows, j] = o[src, k0930]
        got += 1
    print(f"[frame] 15:59 matrix: {got:,}/{len(need):,} symbols, "
          f"{int(np.isfinite(C59).sum()):,} symbol-days", flush=True)
    return O30, C59


def stage_close1559(seeds=SEEDS):
    """The mandate's own exit -- flatten at 15:59 -- against the gd close."""
    dates = L.study_dates()
    syms, sidx, A = L.gd_matrices(dates)
    F = build_features(A)
    dc = OC.DailyCost()
    O30, C59 = minute_close_matrix(dates, sidx, len(syms))
    uni = L.universe()
    MC = L.mcap_matrix(dates, syms, sidx)
    MEM = {"open_top600": {d: {r[0] for r in uni[d][:L.MINUTE_TOP]}
                           for d in dates}}
    for nm, lo_, hi_ in (("open_mcap10b", 10e9, np.inf),
                         ("open_mcap2_10b", 2e9, 10e9)):
        MEM[nm] = {d: {r[0] for r in uni[d][:L.MINUTE_TOP]
                       if r[0] in sidx and lo_ <= MC[i, sidx[r[0]]] < hi_}
                   for i, d in enumerate(dates)}
    out = {}
    for uk, mem in MEM.items():
        for exit_label, Aa in (("gdclose", A),
                               ("m1559", {"o": A["o"], "c": C59}),
                               ("m1559_m0930", {"o": O30, "c": C59})):
            for cost in ("flat10", "zero", "measured"):
                pre = Pre(dates, {"o": Aa["o"], "c": Aa["c"]}, sidx, mem,
                          "close", dc, syms)
                r = search(pre, F, {"cost": cost, "exit_mode": "close",
                                    "long_only": True, "universe": uk},
                           seeds=seeds)
                lab = f"{uk}|{exit_label}|{cost}"
                out[lab] = r
                b = r["best"]
                print(f"[1559] {lab:34s} best ${b['per_month']:+9,.0f}/mo "
                      f"({b['label']:>12s}, ${b['per_ticket']:+7.2f}/tkt) "
                      f"random ${r['random_per_month_mean']:+9,.0f} "
                      f"edge/tkt ${r['edge_per_ticket'] or 0:+6.2f} "
                      f"pct {r['pct_vs_random']}", flush=True)
    L.write("frame_1559.json", out)


def main():
    seeds = SEEDS
    if "--seeds" in sys.argv:
        seeds = int(sys.argv[sys.argv.index("--seeds") + 1])
    if "--stage" in sys.argv and \
            sys.argv[sys.argv.index("--stage") + 1] == "close1559":
        return stage_close1559(seeds)
    dates = L.study_dates()
    syms, sidx, A = L.gd_matrices(dates)
    print(f"[frame] {len(dates)} dates x {len(syms):,} gd symbols", flush=True)
    F = build_features(A)
    dc = OC.DailyCost()

    # ---------------- universes ----------------
    uni = L.universe()
    MEM = {}
    MEM["open"] = {d: {r[0] for r in uni[d]} for d in dates}
    MEM["open_top600"] = {d: {r[0] for r in uni[d][:L.MINUTE_TOP]}
                          for d in dates}
    # the liquidity screen WITHOUT the operating-company type gate: the
    # nearest thing to HARNESS-DIAGNOSTIC's `liquid` universe
    import gzip
    sc = json.loads(gzip.open(Path(__file__).resolve().parent / "rl2" / "out"
                              / "screen.json.gz", "rt").read())
    MEM["rl2_liquid"] = {d: {r[0] for r in sc.get(d, [])} for d in dates}
    for kind, src in (("halal_strict", "rl2/out/universe"),
                      ("halal_wide", "uq_out/universe")):
        base = Path(__file__).resolve().parent / src
        m = {}
        for d in dates:
            f = base / f"{d}.json"
            m[d] = ({r["symbol"] if isinstance(r, dict) else r
                     for r in json.loads(f.read_text())} if f.exists()
                    else set())
        MEM[kind] = m
    # large-cap slice of the open universe (mandate Test 4).  Market cap is
    # CAUSAL: present-day share count x the PREVIOUS session's close, so
    # membership cannot be conditioned on the name having gone up.
    MC = L.mcap_matrix(dates, syms, sidx)
    for nm, lo_, hi_ in (("open_mcap10b", 10e9, np.inf),
                         ("open_mcap2_10b", 2e9, 10e9),
                         ("open_mcap_lt2b", 0.0, 2e9)):
        m = {}
        for i, d in enumerate(dates):
            m[d] = {r[0] for r in uni[d]
                    if r[0] in sidx and lo_ <= MC[i, sidx[r[0]]] < hi_}
        MEM[nm] = m
    # the LIQUIDITY LADDER -- the mandate's breadth question asked as a
    # gradient rather than as one contrast.  Rank k by prior-60-day median
    # dollar volume, which is the same quantity the universe is screened on.
    for lo_, hi_ in ((0, 100), (0, 300), (0, 600), (0, 1200), (600, 99999),
                     (1200, 99999)):
        MEM[f"open_rank{lo_}_{hi_}"] = {
            d: {r[0] for r in uni[d][lo_:hi_]} for d in dates}
    for k, m in MEM.items():
        n = np.array([len(v) for v in m.values()])
        print(f"[frame] {k:16s} names/day {n.min():5d}..{n.max():5d} "
              f"(mean {n.mean():7.0f})", flush=True)

    # sector groups for the neutral variant
    g2 = {}
    grp = np.zeros((len(dates), len(syms)), np.int32)
    for i, s in enumerate(syms):
        k = L.sic2(s)
        grp[:, i] = g2.setdefault(k, len(g2))

    out = {}
    PRE = {}

    def run(label, universe_key, cost, exit_mode="close", long_only=True,
            groups=None, cap=False):
        st = {"cost": cost, "exit_mode": exit_mode, "long_only": long_only,
              "universe": universe_key, "cap": cap}
        key = (universe_key, exit_mode, groups is not None)
        if key not in PRE:
            PRE[key] = Pre(dates, A, sidx, MEM[universe_key], exit_mode, dc,
                           syms, groups=groups)
        r = search(PRE[key], F, st, seeds=seeds, neutral=groups is not None)
        out[label] = {"setting": st, **r}
        b = r["best"]
        print(f"[frame] {label:46s} best ${b['per_month']:+10,.0f}/mo "
              f"({b['label']:>12s}, ${b['per_ticket']:+7.2f}/tkt)  "
              f"median ${r['median_policy_per_month']:+9,.0f}  random "
              f"${r['random_per_month_mean']:+9,.0f}+/-"
              f"{r['random_per_month_sd']:,.0f}  edge/tkt "
              f"${r['edge_per_ticket'] or 0:+6.2f}  pct {r['pct_vs_random']}",
              flush=True)
        return r

    # ---- the breadth question: same 20 policies, every universe ----
    for u in ("halal_strict", "halal_wide", "rl2_liquid", "open",
              "open_top600", "open_mcap10b", "open_mcap2_10b",
              "open_mcap_lt2b", "open_rank0_100", "open_rank0_300",
              "open_rank0_1200", "open_rank600_99999",
              "open_rank1200_99999"):
        run(f"U:{u} flat10", u, "flat10")
        run(f"U:{u} ZERO-COST", u, "zero")
        run(f"U:{u} MEASURED", u, "measured")
    # ---- the ablation table, now anchored on the OPEN universe ----
    run("BASE open/flat10", "open", "flat10")
    run("same-day OFF (hold overnight)", "open", "flat10",
        exit_mode="next_open")
    run("long-only OFF (short allowed)", "open", "flat10", long_only=False)
    run("costs OFF (0 bps/side)", "open", "zero")
    run("market-order OFF (2.77 bps half-spread)", "open", 2.77)
    run("MEASURED cost (CS/AR + sqrt impact, per name)", "open", "measured")
    run("MEASURED cost, top-600 only", "open_top600", "measured")
    run("MEASURED cost, mcap>$10B only", "open_mcap10b", "measured")
    run("sector-neutral (one per 2-digit SIC)", "open", "flat10", groups=grp)
    run("sector-neutral MEASURED", "open", "measured", groups=grp)
    run("sector-neutral ZERO-COST", "open", "zero", groups=grp)

    # ---- the ACCOUNT-LEGAL ladder: 6 x $15,000 + 1 x $10,000 = $100,000/day
    # ---- (every row above, like every hd_frame row in the index, charges
    # ---- 7 x $15,000 = $105,000, which the cash account cannot do)
    for u in ("open_top600", "open_mcap10b", "open_mcap2_10b",
              "open_rank0_300", "halal_strict"):
        for c in ("flat10", "measured", "zero"):
            run(f"CAP100k {u} {c}", u, c, cap=True)

    L.write("frame.json", out)
    print("[frame] wrote plan/ou_out/frame.json", flush=True)


if __name__ == "__main__":
    main()
