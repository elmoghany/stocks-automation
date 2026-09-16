"""RL-SERIES (2026-09-16): non-learned baselines + the full honesty battery.

Every baseline runs through the SAME env, the SAME leak-safe eligibility,
the SAME causal slotting, the SAME next-bar-open fills and the SAME cost
ladder as the agents. That is the whole point: the only thing that differs
between a row here and an RL row is the policy.

  HOLD          never trades (must be exactly $0)
  BUYFIRST      buy the top-liquidity slot as soon as it is legal, hold to
                the forced flatten. Measures what the eligible set does on
                its own, net of costs.
  CHURN         buy, sell one step later, repeat. Measures the cost ladder.
  RANDOM x30    uniform over the legal actions with a 10% trade rate.
  RANDOM-EAGER  uniform with a 35% trade rate (fills the ticket budget early)

  python plan/rl/baselines.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import env as E                                             # noqa: E402
import honesty as H                                         # noqa: E402

SPLITS = ("train", "val", "test", "extra")
N_RANDOM = 30


def churn_policy(obs, env):
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


def main():
    t0 = time.time()
    sp = E.split_files()
    ds = {k: E.Dataset(v, label=k) for k, v in sp.items() if v}
    norm = ds["train"].fit_norm()
    for k in ds:
        ds[k].set_norm(norm)
    print({k: len(v.days) for k, v in ds.items()},
          f"loaded {time.time()-t0:.0f}s", flush=True)

    out = {"norm_mu": norm[0].tolist(), "norm_sd": norm[1].tolist(),
           "split_days": {k: len(v.days) for k, v in ds.items()},
           "env": dict(fee_bps=E.FEE_BPS, ext_bps=E.EXT_BPS,
                       vol_cap=E.VOL_CAP_FRAC, step_min=E.STEP,
                       k_slots=E.K_SLOTS, p_slots=E.P_SLOTS,
                       tickets=E.TICKET_NOTIONALS, n_feat=E.NF,
                       n_steps_per_day=E.NSTEP,
                       first_decision_min=int(E.STEP_MINS[0]),
                       last_decision_min=int(E.STEP_MINS[-1]))}

    print("honesty: poison test on train + test ...", flush=True)
    out["poison_train"] = H.poison_test(sp["train"], norm, n_days=16)
    out["poison_test"] = H.poison_test(sp["test"], norm, n_days=16, seed=3)
    print(json.dumps(out["poison_train"]), json.dumps(out["poison_test"]),
          flush=True)

    for name, pol in (("HOLD", E.hold_policy), ("BUYFIRST", E.buy_first_policy),
                      ("CHURN", churn_policy)):
        out[name] = {}
        for s in SPLITS:
            if s in ds:
                out[name][s] = E.run_epoch(
                    E.TicketEnv(ds[s], norm=norm, shuffle_days=False),
                    pol, record=True)
        print(name, {s: round(out[name][s]["total_pnl"]) for s in out[name]},
              flush=True)

    for tag, pt in (("RANDOM", 0.10), ("RANDOM_EAGER", 0.35)):
        rows = {s: [] for s in SPLITS if s in ds}
        for seed in range(N_RANDOM):
            for s in rows:
                rows[s].append(E.run_epoch(
                    E.TicketEnv(ds[s], norm=norm, shuffle_days=False, seed=seed),
                    E.random_policy(seed=seed, p_trade=pt), record=True))
            if seed % 10 == 0:
                print(f"  {tag} seed {seed} {time.time()-t0:.0f}s", flush=True)
        out[tag] = {s: H.agg(v) for s, v in rows.items()}
        out[tag + "_raw"] = {s: [{k: v2[k] for k in
                                  ("total_pnl", "tickets", "pnl_per_ticket",
                                   "sharpe_daily_ann", "max_dd", "exit_ext_n",
                                   "exit_ext_pnl", "exit_rth_n", "exit_rth_pnl",
                                   "cap_blocked", "noprint_blocked",
                                   "forced_flatten", "stale_forced")}
                                 for v2 in v] for s, v in rows.items()}
        print(tag, {s: round(out[tag][s]["total_pnl"]["mean"]) for s in rows},
              flush=True)

    out["cost_sanity"] = H.cost_sanity(ds["val"], norm)
    out["wall_s"] = round(time.time() - t0, 1)
    E.OUT.mkdir(exist_ok=True)
    p = E.OUT / "baselines.json"
    p.write_text(json.dumps(out, indent=1))
    print("wrote", p, flush=True)


if __name__ == "__main__":
    main()
