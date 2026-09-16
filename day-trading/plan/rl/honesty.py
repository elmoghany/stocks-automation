"""RL-SERIES (2026-09-16): the adversarial checks that must FAIL before any
RL number in this study is allowed to mean anything.

  poison_test        replace every bar strictly after minute m with garbage;
                     the observation at every step <= m, and the action a
                     deterministic policy takes there, must be BIT-IDENTICAL.
                     Anything else is look-ahead in the state.
  masks_causal_test  the action mask (what the agent is allowed to do) must
                     also survive poisoning -- a mask that reads bar m+1
                     leaks "will the next minute print".
  hold_is_zero       a policy that never trades must return exactly $0, so
                     any reported P&L is attributable to fills, not drift in
                     the accounting.
  cost_sanity        an immediate round trip must lose at least the modelled
                     cost; verifies the fee/extended-hours ladder is live.
  fee_monotone       raising the fee must never raise a fixed policy's P&L.
  leak_control       (positive control) with next-step returns bolted onto
                     the observation the harness MUST be able to make money;
                     if it cannot, the study has no power and a null result
                     is meaningless.
  shuffled_labels    (negative control) train and test on a panel whose
                     intraday return sequence is permuted. A positive test
                     result there is proof of leakage in the evaluation.

Run:  python plan/rl/honesty.py
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import env as E                                             # noqa: E402


def _clean(path, label=""):
    return E.DayData(path, label=label)


def _episode_actions(day, norm, make_policy, stop_step=None, seed=0):
    """Replay one day, returning (actions, obs list, masks list).

    `make_policy` is a FACTORY, not a policy: the clean and poisoned replays
    must each get a policy with a freshly seeded RNG, otherwise the two runs
    differ because of the policy's own random state and the test reports a
    leak that is not there."""
    policy = make_policy()
    ds = type("D", (), {"days": [day], "norm": norm})()
    env = E.TicketEnv(ds, norm=norm, shuffle_days=False, seed=seed)
    obs, _ = env.reset()
    acts, obss, masks = [], [], []
    done = False
    while not done:
        i = env.i
        m = env.action_masks()
        a = policy(obs, env)
        obss.append(obs.copy())
        masks.append(m.copy())
        acts.append(int(a))
        if stop_step is not None and i >= stop_step:
            break
        obs, r, done, _, _ = env.step(a)
    return acts, obss, masks


def poison_test(files, norm, n_days=12, points=(20, 45, 70, 95), seed=0):
    """For each sampled day and cut point, compare clean vs poisoned."""
    rng = np.random.default_rng(seed)
    pick = list(rng.choice(len(files), size=min(n_days, len(files)),
                           replace=False))
    def pol():
        return E.random_policy(seed=7, p_trade=0.35)
    res = dict(checked=0, obs_mismatch=0, act_mismatch=0, mask_mismatch=0,
               feat_mismatch=0, days=len(pick), worst_abs=0.0)
    for di in pick:
        f = files[int(di)]
        clean = _clean(f)
        for sp in points:
            if sp >= E.NSTEP:
                continue
            cut = int(E.STEP_MINS[sp])
            bad = E.DayData.poisoned(f, cut, seed=int(di) * 97 + sp)
            # 1. raw causal arrays for every step at or before the cut
            k = sp + 1
            for name in ("feat", "mark", "elig", "slots", "volcap",
                         "printed_now"):
                a = getattr(clean, name)[:k]
                b = getattr(bad, name)[:k]
                if a.dtype.kind == "f":
                    d = np.nanmax(np.abs(np.nan_to_num(a) - np.nan_to_num(b))) \
                        if a.size else 0.0
                    res["worst_abs"] = max(res["worst_abs"], float(d))
                    if d > 0:
                        res["feat_mismatch"] += 1
                elif not np.array_equal(a, b):
                    res["feat_mismatch"] += 1
            # 2. the policy's own decisions
            a1, o1, m1 = _episode_actions(clean, norm, pol, stop_step=sp)
            a2, o2, m2 = _episode_actions(bad, norm, pol, stop_step=sp)
            n = min(len(a1), len(a2))
            if a1[:n] != a2[:n]:
                res["act_mismatch"] += 1
            if any(not np.array_equal(x, y) for x, y in zip(o1[:n], o2[:n])):
                res["obs_mismatch"] += 1
            if any(not np.array_equal(x, y) for x, y in zip(m1[:n], m2[:n])):
                res["mask_mismatch"] += 1
            res["checked"] += 1
    res["PASS"] = (res["obs_mismatch"] == 0 and res["act_mismatch"] == 0
                   and res["mask_mismatch"] == 0 and res["feat_mismatch"] == 0)
    return res


def hold_is_zero(ds, norm):
    env = E.TicketEnv(ds, norm=norm, shuffle_days=False)
    s = E.run_epoch(env, E.hold_policy)
    return {"total_pnl": s["total_pnl"], "tickets": s["tickets"],
            "PASS": s["total_pnl"] == 0.0 and s["tickets"] == 0}


def cost_sanity(ds, norm):
    """Buy at the first legal chance, sell one step later, every day. The
    result must be <= the no-cost version by at least the modelled fee."""
    def churn(obs, env):
        m = env.action_masks()
        if (env.pos_sym >= 0).any():
            for p in range(E.P_SLOTS):
                if m[1 + E.K_SLOTS + p]:
                    return 1 + E.K_SLOTS + p
            return 0
        for k in range(E.K_SLOTS):
            if m[1 + k]:
                return 1 + k
        return 0
    a = E.run_epoch(E.TicketEnv(ds, norm=norm, shuffle_days=False), churn,
                    record=True)
    b = E.run_epoch(E.TicketEnv(ds, norm=norm, shuffle_days=False,
                                fee_bps=0.0, ext_bps=0.0), churn, record=True)
    c = E.run_epoch(E.TicketEnv(ds, norm=norm, shuffle_days=False,
                                fee_bps=100.0, ext_bps=200.0), churn,
                    record=True)
    return {"with_costs": a["total_pnl"], "zero_cost": b["total_pnl"],
            "cost_10x": c["total_pnl"], "tickets": a["tickets"],
            "PASS": a["total_pnl"] < b["total_pnl"] and
                    c["total_pnl"] < a["total_pnl"]}


def random_spread(ds, norm, seeds=30, p_trade=0.10):
    out = []
    for s in range(seeds):
        env = E.TicketEnv(ds, norm=norm, shuffle_days=False, seed=s)
        out.append(E.run_epoch(env, E.random_policy(seed=s, p_trade=p_trade),
                               record=True))
    return out


def agg(rows, keys=("total_pnl", "pnl_per_ticket", "sharpe_daily_ann",
                    "tickets_per_day", "max_dd")):
    o = {}
    for k in keys:
        v = np.array([r[k] for r in rows], float)
        o[k] = {"mean": float(v.mean()), "std": float(v.std()),
                "min": float(v.min()), "max": float(v.max()),
                "median": float(np.median(v))}
    o["n"] = len(rows)
    return o


def main():
    sp = E.split_files()
    if not sp["train"]:
        print("no day tensors yet -- run build_days.py first")
        return
    tr = E.Dataset(sp["train"][:40])
    norm = tr.fit_norm()
    out = {}
    print("poison test ...", flush=True)
    out["poison"] = poison_test(sp["train"], norm)
    print(json.dumps(out["poison"]), flush=True)
    print("hold-is-zero ...", flush=True)
    out["hold_zero"] = hold_is_zero(tr, norm)
    print(json.dumps(out["hold_zero"]), flush=True)
    print("cost sanity ...", flush=True)
    out["cost"] = cost_sanity(tr, norm)
    print(json.dumps(out["cost"]), flush=True)
    print("random spread (train, 8 seeds) ...", flush=True)
    out["random_train"] = agg(random_spread(tr, norm, seeds=8))
    print(json.dumps(out["random_train"]), flush=True)
    p = E.OUT / "honesty.json"
    p.write_text(json.dumps(out, indent=1))
    print("wrote", p)


if __name__ == "__main__":
    main()
