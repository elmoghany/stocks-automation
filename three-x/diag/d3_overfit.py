"""Item 3: overfitting audit.

Part A: for each search already run, how well do settings that win on one part do on the other part (rank correlation across all settings, picked-on-A scored on B,
        number beating held in both parts versus the number expected if the two parts were unrelated).
Part B: random in/out schedules with the same number of trades, the same lengths of each stay in AMD, and so the same time in market, placed at random in the same window.
        Where does each tried rule sit in that distribution, and what does the best of N random schedules reach (N = 10 ... 17,280, the sizes of our searches)?
Part C: do the rules that did best in 2023-26 also do best in 2013-2023?  Rank correlation across the 13 rules re-created from code.
All of this is measurement of selection, not a new strategy.
"""
import numpy as np
import pandas as pd
import rules as R
from common import *

f = load_amd()
o, c, idx = f.open.values, f.close.values, f.index
n = len(c)
W = windows(idx)


def spearman(a, b):
    a, b = pd.Series(a), pd.Series(b)
    return float(a.rank().corr(b.rank()))


def held_between(lo, hi):
    return float(c[hi - 1] / c[lo])


# ---------------- Part A
def part_a():
    rows = []
    i_early, i_recent = int(idx.searchsorted("2013-01-01")), int(idx.searchsorted("2023-08-01"))
    i_cut = int(idx.searchsorted("2026-11-06"))
    split = int(idx.searchsorted("2025-05-01"))
    held = {"surge": (held_between(i_early, i_recent), held_between(i_recent, i_cut)),
            "zone": (held_between(i_recent, split), held_between(split, i_cut)),
            "buy": (held_between(i_recent, split), held_between(split, i_cut))}
    S = pd.read_csv(RES / "amd_surge_search.csv")
    Z = pd.read_csv(RES / "amd_zone_search.csv")
    B = pd.read_csv(RES / "amd_buy_search.csv")
    specs = [("Surge search (3,900 rules); parts: 2013-Jul 2023 vs Aug 2023-Nov 5 2026", S, "early_mult", "recent_mult", held["surge"], "2013-23", "2023-26"),
             ("Zone search (17,280 rules); parts: Aug 2023-Apr 2025 vs May 2025-Nov 2026", Z, "first_mult", "last_mult", held["zone"], "to Apr 2025", "May 2025 on"),
             ("Buy-signal search (1,142 rules); same parts as zone", B, "first_mult", "last_mult", held["buy"], "to Apr 2025", "May 2025 on")]
    for title, t, a, b, (ha, hb), la, lb in specs:
        t = t.dropna(subset=[a, b])
        ra, rb = t[a] / ha, t[b] / hb                    # result divided by held in each part
        rho = spearman(ra, rb)
        bestA = t.loc[t[a].idxmax()]
        bestB = t.loc[t[b].idxmax()]
        top50A = t.sort_values(a, ascending=False).head(50)
        top50B = t.sort_values(b, ascending=False).head(50)
        beatA, beatB = (ra > 1), (rb > 1)
        both = int((beatA & beatB).sum())
        expected_both = float(beatA.mean() * beatB.mean() * len(t))
        rows.append({"search": title, "settings": len(t), "held_A": ha, "held_B": hb,
                     "best_on_A": bestA[a], "best_on_A_scored_on_B": bestA[b], "bestA_B_over_held": bestA[b] / hb,
                     "best_on_B": bestB[b], "best_on_B_scored_on_A": bestB[a], "bestB_A_over_held": bestB[a] / ha,
                     "median_all_A_over_held": float(ra.median()), "median_all_B_over_held": float(rb.median()),
                     "median_top50A_on_B_over_held": float((top50A[b] / hb).median()), "median_top50B_on_A_over_held": float((top50B[a] / ha).median()),
                     "rank_corr_A_B": rho, "beat_held_A": int(beatA.sum()), "beat_held_B": int(beatB.sum()), "beat_both": both, "expected_both_if_unrelated": expected_both,
                     "label_A": la, "label_B": lb})
    # wide grid / time grid / quarters: first and last parts available as columns
    TG = pd.read_csv(RES / "amd_time_grid.csv")
    rows.append({"search": "Buy-day / sell-days-before grid (121); parts: first 8 quarters vs last 4 (compared to each other)", "settings": len(TG),
                 "rank_corr_A_B": spearman(TG["first8"], TG["last4"]), "label_A": "first 8 qtrs", "label_B": "last 4 qtrs",
                 "best_on_A": TG["first8"].max(), "best_on_A_scored_on_B": TG.loc[TG["first8"].idxmax(), "last4"], "median_all_A_over_held": TG["first8"].median(), "median_all_B_over_held": TG["last4"].median()})
    Q = pd.read_csv(RES / "amd_quarters.csv").dropna(subset=["first8", "last4"])
    rows.append({"search": "Earnings-timing rules (204); parts: first 8 quarters vs last 4", "settings": len(Q), "rank_corr_A_B": spearman(Q["first8"], Q["last4"]), "label_A": "first 8 qtrs", "label_B": "last 4 qtrs",
                 "best_on_A": Q["first8"].max(), "best_on_A_scored_on_B": Q.loc[Q["first8"].idxmax(), "last4"], "median_all_A_over_held": Q["first8"].median(), "median_all_B_over_held": Q["last4"].median()})
    return pd.DataFrame(rows)


# ---------------- Part B
def schedule_stats(pos, lo, hi):
    """Durations (in fill-to-fill sessions) of each stay in AMD, and the trades' log return list, on the open-fill grid P[0..N], P[i]=open[lo+i], P[N]=last close."""
    N = hi - lo
    tr = trades_from_pos(pos, lo, hi)
    D = []
    for b, s in tr:
        a = max(b + 1 - lo, 0)
        e = N if s is None else min(s + 1 - lo, N)
        D.append(e - a)
    return np.array(D, dtype=int)


def random_multiples(D, lo, hi, m, rng):
    """m random schedules with stays of lengths D (shuffled) at random non-overlapping places in the window; returns multiples vs the same cost model."""
    N = hi - lo
    P = np.r_[o[lo:hi], c[hi - 1]]
    LP = np.log(P)
    k = len(D)
    T = int(D.sum())
    F = N - T
    if k == 0 or F < 0:
        return np.ones(m)
    # random order of stays
    order = np.argsort(rng.random((m, k)), axis=1)
    Dm = D[order]
    cuts = np.sort(rng.integers(0, F + 1, (m, k)), axis=1)
    gaps = np.diff(np.concatenate([np.zeros((m, 1), dtype=int), cuts], axis=1), axis=1)   # k gaps before each stay; the remainder is the final gap
    starts = np.cumsum(gaps, axis=1) + np.cumsum(Dm, axis=1) - Dm
    ends = starts + Dm
    ends = np.minimum(ends, N)
    log = (LP[ends] - LP[starts]).sum(axis=1) + 2 * k * np.log(1 - COST)
    return np.exp(log)


def part_b(nsim=200_000):
    rng = np.random.default_rng(2024)
    rows = []
    best_rows = []
    for w in ("recent", "early"):
        lo, hi = W[w]
        H = hold_mult(o, c, lo, hi)
        P = R.positions(w)
        for key, nm in R.NAMES.items():
            pos = P[key]
            D = schedule_stats(pos, lo, hi)
            actual = mult(pos, o, c, lo, hi)
            sim = random_multiples(D, lo, hi, nsim, rng)
            pct = float((sim < actual).mean())
            row = {"window": w, "rule": nm, "key": key, "trades": len(D), "in_market_share": D.sum() / (hi - lo), "held_x": H, "actual_x": actual, "actual_over_held": actual / H,
                   "random_median_x": float(np.median(sim)), "random_p95_x": float(np.quantile(sim, 0.95)), "random_p99_x": float(np.quantile(sim, 0.99)), "random_max_x": float(sim.max()),
                   "actual_percentile_in_random": pct, "share_random_beating_held": float((sim > H).mean()), "random_share_at_least_actual": float((sim >= actual).mean()),
                   "equivalent_N_for_best_of_random": float(np.log(2) / max((sim >= actual).mean(), 1.0 / (10 * len(sim)))), "share_random_reaching_2x_held": float((sim > 2 * H).mean())}
            # best of N random schedules
            for N_ in (10, 100, 1000, 17280):
                usable = (len(sim) // N_) * N_
                arr = sim[:usable].reshape(-1, N_).max(axis=1)
                row[f"best_of_{N_}_random_median_x"] = float(np.median(arr))
            rows.append(row)
    return pd.DataFrame(rows)


# ---------------- Part C
def part_c():
    A = pd.read_csv(OUT / "d2_decompose.csv")
    r = A.pivot(index="rule", columns="window", values="rule_over_held")
    rho = spearman(r["recent"], r["early"])
    return r.sort_values("recent", ascending=False), rho


def main():
    pd.set_option("display.width", 250, "display.max_columns", 50, "display.max_rows", 200, "display.max_colwidth", 90)
    A = part_a()
    A.to_csv(OUT / "d3_search_splits.csv", index=False)
    print("PART A: do winners on one part win on the other?")
    for _, r in A.iterrows():
        print("\n" + r["search"])
        for k, v in r.items():
            if k in ("search",) or pd.isna(v):
                continue
            print(f"   {k:<34} {v:,.3f}" if isinstance(v, (float, np.floating)) else f"   {k:<34} {v}")
    Bt = part_b()
    Bt.to_csv(OUT / "d3_random_schedules.csv", index=False)
    print("\nPART B: matched random schedules (200,000 draws per rule): rule vs random with same trade count and same stay lengths")
    cols = ["window", "rule", "trades", "in_market_share", "held_x", "actual_x", "random_median_x", "random_p95_x", "random_p99_x", "actual_percentile_in_random", "equivalent_N_for_best_of_random", "share_random_beating_held", "share_random_reaching_2x_held", "best_of_100_random_median_x", "best_of_1000_random_median_x", "best_of_17280_random_median_x"]
    print(Bt[cols].to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    r, rho = part_c()
    print("\nPART C: rule result divided by held, in each window (the 13 rules re-created from code)")
    print(r.to_string(float_format=lambda v: f"{v:.2f}"))
    print(f"rank correlation between windows: {rho:.2f}")


if __name__ == "__main__":
    main()
