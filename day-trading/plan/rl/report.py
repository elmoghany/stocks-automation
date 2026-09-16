"""RL-SERIES (2026-09-16): assemble the results table from the run JSONs.

  python plan/rl/report.py           # prints markdown, writes out/report.json

Reads plan/rl/out/results/*.json (one per algo x variant x seed) and
plan/rl/out/baselines.json. Reports, per (algo, variant) and per split, the
seed mean / std / min / max of every headline metric, plus:

  * the two-sided Welch t statistic of the agent's per-seed test P&L against
    the 30 random seeds, and
  * the SEED-OVERLAP number: what fraction of random seeds beat the agent's
    BEST seed. This is the honest question -- if a third of the random seeds
    beat the best agent, the agent is a draw from the same distribution.

No p-value is presented as a discovery. With 4 algorithms x 5 seeds x 10
checkpoints inspected on validation, the multiple-testing count behind any
single "winning" row is >= 200, and Bailey/Lopez de Prado's result is that
strategies selected by such a search have NEGATIVE expected out-of-sample
return, not zero.
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = HERE / "out"
RES = OUT / "results"
SPLITS = ("train", "val", "test", "extra")
KEYS = ("total_pnl", "pnl_per_ticket", "tickets_per_day", "sharpe_daily_ann",
        "max_dd", "win_days_pct")


def welch(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 2 or len(b) < 2:
        return 0.0, 0.0
    va, vb = a.var(ddof=1), b.var(ddof=1)
    se = math.sqrt(va / len(a) + vb / len(b))
    if se == 0:
        return 0.0, 0.0
    t = (a.mean() - b.mean()) / se
    df = se ** 4 / ((va / len(a)) ** 2 / (len(a) - 1) +
                    (vb / len(b)) ** 2 / (len(b) - 1))
    return float(t), float(df)


def fmt(x, n=0):
    if x is None:
        return "-"
    if abs(x) >= 1000 or n == 0:
        return f"{x:,.0f}"
    return f"{x:.{n}f}"


def main():
    runs = defaultdict(list)
    for f in sorted(RES.glob("*.json")):
        d = json.loads(f.read_text())
        runs[(d["algo"], d["variant"])].append(d)
    base = {}
    bp = OUT / "baselines.json"
    if bp.exists():
        base = json.loads(bp.read_text())

    rand_test = []
    if base:
        rand_test = [r["total_pnl"] for r in
                     base.get("RANDOM_raw", {}).get("test", [])]

    table = {}
    for (algo, var), ds in sorted(runs.items()):
        row = {"n_seeds": len(ds), "seeds": sorted(d["seed"] for d in ds),
               "steps": ds[0]["steps"], "wall_s_mean":
               float(np.mean([d["wall_s"] for d in ds]))}
        for sp in SPLITS:
            got = [d[sp] for d in ds if sp in d]
            if not got:
                continue
            row[sp] = {}
            for k in KEYS:
                v = np.array([g[k] for g in got], float)
                row[sp][k] = dict(mean=float(v.mean()), std=float(v.std()),
                                  min=float(v.min()), max=float(v.max()))
            for k in ("tickets", "exit_ext_n", "exit_ext_pnl", "exit_rth_n",
                      "exit_rth_pnl", "cap_blocked", "noprint_blocked",
                      "forced_flatten", "stale_forced", "invalid_actions",
                      "mean_hold_min"):
                v = [g.get(k, 0) for g in got]
                row[sp][k + "_mean"] = float(np.mean(v))
        if rand_test and "test" in row:
            per = [d["test"]["total_pnl"] for d in ds]
            t, df = welch(per, rand_test)
            row["vs_random_test"] = {
                "welch_t": round(t, 2), "df": round(df, 1),
                "agent_mean": float(np.mean(per)),
                "random_mean": float(np.mean(rand_test)),
                "frac_random_beating_best_agent":
                    float(np.mean(np.array(rand_test) > max(per))),
                "frac_random_beating_agent_mean":
                    float(np.mean(np.array(rand_test) > np.mean(per))),
            }
        table[f"{algo}|{var}"] = row

    out = {"runs": table, "baselines_present": bool(base)}
    (OUT / "report.json").write_text(json.dumps(out, indent=1))

    # ---- markdown ----
    L = []
    L.append("| policy | variant | seeds | split | total P&L | per-ticket | "
             "tickets/day | Sharpe(d,ann) | max DD | seed spread (min..max) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")

    def brow(name, split, m):
        L.append(f"| {name} | - | 1 | {split} | {fmt(m['total_pnl'])} | "
                 f"{fmt(m['pnl_per_ticket'], 1)} | {fmt(m['tickets_per_day'],2)} | "
                 f"{fmt(m['sharpe_daily_ann'],2)} | {fmt(m['max_dd'])} | - |")

    for nm in ("HOLD", "BUYFIRST", "CHURN"):
        if nm in base:
            for sp in SPLITS:
                if sp in base[nm]:
                    brow(nm, sp, base[nm][sp])
    for nm in ("RANDOM", "RANDOM_EAGER"):
        if nm in base:
            for sp in SPLITS:
                if sp not in base[nm]:
                    continue
                a = base[nm][sp]
                L.append(
                    f"| {nm} | - | {a['n']} | {sp} | "
                    f"{fmt(a['total_pnl']['mean'])} | "
                    f"{fmt(a['pnl_per_ticket']['mean'],1)} | "
                    f"{fmt(a['tickets_per_day']['mean'],2)} | "
                    f"{fmt(a['sharpe_daily_ann']['mean'],2)} | "
                    f"{fmt(a['max_dd']['mean'])} | "
                    f"{fmt(a['total_pnl']['min'])} .. {fmt(a['total_pnl']['max'])} |")
    for key, row in table.items():
        algo, var = key.split("|")
        for sp in SPLITS:
            if sp not in row:
                continue
            m = row[sp]
            L.append(
                f"| {algo.upper()} | {var} | {row['n_seeds']} | {sp} | "
                f"{fmt(m['total_pnl']['mean'])} | "
                f"{fmt(m['pnl_per_ticket']['mean'],1)} | "
                f"{fmt(m['tickets_per_day']['mean'],2)} | "
                f"{fmt(m['sharpe_daily_ann']['mean'],2)} | "
                f"{fmt(m['max_dd']['mean'])} | "
                f"{fmt(m['total_pnl']['min'])} .. {fmt(m['total_pnl']['max'])} |")
    md = "\n".join(L)
    print(md)
    (OUT / "report.md").write_text(md)

    print("\n\n### vs random (test split)")
    for key, row in table.items():
        if "vs_random_test" in row:
            v = row["vs_random_test"]
            print(f"{key}: agent mean {v['agent_mean']:,.0f} vs random "
                  f"{v['random_mean']:,.0f}, Welch t={v['welch_t']} "
                  f"(df {v['df']}), random seeds beating the BEST agent seed: "
                  f"{v['frac_random_beating_best_agent']*100:.0f}%")
    if base:
        print("\n### honesty")
        for k in ("poison_train", "poison_test", "cost_sanity"):
            if k in base:
                print(k, json.dumps(base[k]))
        if "HOLD" in base:
            print("hold_is_zero:", {s: base["HOLD"][s]["total_pnl"]
                                    for s in base["HOLD"]})


if __name__ == "__main__":
    main()
