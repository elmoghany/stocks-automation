"""RL-SERIES v2, APPROACH 2 (2026-09-16): offline RL on logged trajectories.

Behaviour data comes from two loggers on TRAIN DAYS ONLY:
  * a uniform-random legal policy (exploration), and
  * an epsilon-greedy policy driven by the APPROACH-1 bandit model, itself
    trained on train days only (exploitation).
Both run in the same env as approach 3, so the logged (obs, action,
reward, terminal) tuples are exactly the MDP the online agents see.

d3rlpy 2.8.1 has no DISCRETE IQL (IQLConfig is continuous-action only), so
the offline pair reported is DiscreteCQL and DiscreteBCQ -- the two
discrete conservative/constrained learners it does ship. That substitution
is a limitation of the library, recorded here rather than papered over.

  python plan/rl2/offline.py --algo cql --seed 0 [--steps 100000]
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rlenv as E                                             # noqa: E402

RES = HERE / "results"
EXIT_H = 30                    # the bandit logger's fixed holding horizon


def random_policy(obs, env):
    m = env.action_masks()
    legal = np.flatnonzero(m)
    return int(env._rng.choice(legal))


def make_bandit_policy(eps, rng):
    def pol(obs, env):
        d, i = env.d, env.i
        m = env.action_masks()
        # exits first: anything held past EXIT_H minutes
        for p in range(E.P_SLOTS):
            s = int(env.pos_sym[p])
            if s >= 0 and E.STEPS[i] >= env.pos_min[p] + EXIT_H \
                    and m[1 + E.K_SLOTS + p]:
                return 1 + E.K_SLOTS + p
        if rng.random() < eps:
            return int(rng.choice(np.flatnonzero(m)))
        best, bk = 0.0, -1
        for k in range(E.K_SLOTS):
            if not m[1 + k]:
                continue
            s = int(d.slots[i, k])
            pr = float(d.pred[i, s])
            if pr > best:
                best, bk = pr, k
        return 0 if bk < 0 else 1 + bk
    return pol


def log_episodes(env, policy, n_days):
    obs_l, act_l, rew_l, term_l = [], [], [], []
    env.shuffle_days = False
    env._order = np.arange(len(env.ds.days))
    env._ptr = 0
    for _ in range(n_days):
        o, _ = env.reset()
        done = False
        while not done:
            a = policy(o, env)
            obs_l.append(o)
            act_l.append(a)
            o, r, done, _, _ = env.step(a)
            rew_l.append(r)
            term_l.append(1.0 if done else 0.0)
    return (np.asarray(obs_l, np.float32), np.asarray(act_l, np.int64),
            np.asarray(rew_l, np.float32), np.asarray(term_l, np.float32))


def attach_bandit_preds(days, booster):
    for d in days:
        p = np.zeros(d.feat.shape[:2], np.float32)
        t_i, s_i = np.nonzero(d.printed)
        if len(t_i):
            p[t_i, s_i] = booster.predict(d.feat[t_i, s_i])
        d.pred = p


def main():
    a = sys.argv[1:]
    algo = a[a.index("--algo") + 1] if "--algo" in a else "cql"
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 0
    steps = int(a[a.index("--steps") + 1]) if "--steps" in a else 60_000
    RES.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    import lightgbm as lgb
    import dataset as DS
    import bandit as BD
    R = DS.Rows()
    sp = E.splits()
    hi = BD.FT.HORIZONS.index(EXIT_H)
    tr = (R.date_of_row < E.TRAIN_END) & R.OKY[:, hi]
    p = dict(BD.PARAMS)
    p["seed"] = seed
    booster = lgb.train(p, lgb.Dataset(R.X[tr], label=R.Y[tr, hi]),
                        num_boost_round=BD.NROUND)
    print(f"behaviour bandit trained on {tr.sum():,} train rows "
          f"({time.time()-t0:.0f}s)", flush=True)

    tr_env, norm = None, None
    ds_tr = E.Dataset(sp["train"])
    norm = ds_tr.fit_norm()
    tr_env = E.TicketEnv(ds_tr, norm=norm, seed=seed)
    E.DayData.pred = None
    attach_bandit_preds(ds_tr.days, booster)

    rng = np.random.default_rng(seed)
    o1, a1, r1, t1 = log_episodes(tr_env, random_policy, len(ds_tr.days))
    o2, a2, r2, t2 = log_episodes(tr_env, make_bandit_policy(0.1, rng),
                                  len(ds_tr.days))
    obs = np.concatenate([o1, o2])
    act = np.concatenate([a1, a2])
    rew = np.concatenate([r1, r2])
    term = np.concatenate([t1, t2])
    print(f"logged {len(obs):,} transitions "
          f"({int(t1.sum())+int(t2.sum())} episodes)", flush=True)

    import d3rlpy
    from d3rlpy.dataset import MDPDataset
    d3rlpy.seed(seed)
    mdp = MDPDataset(observations=obs, actions=act.reshape(-1, 1),
                     rewards=rew.reshape(-1, 1), terminals=term)
    if algo == "cql":
        cfg = d3rlpy.algos.DiscreteCQLConfig(batch_size=256,
                                             learning_rate=3e-4)
    elif algo == "bcq":
        cfg = d3rlpy.algos.DiscreteBCQConfig(batch_size=256,
                                             learning_rate=3e-4)
    elif algo == "bc":
        cfg = d3rlpy.algos.DiscreteBCConfig(batch_size=256,
                                            learning_rate=3e-4)
    else:
        raise SystemExit(f"unknown algo {algo}")
    algo_o = cfg.create(device="cpu")
    algo_o.fit(mdp, n_steps=steps, n_steps_per_epoch=max(steps // 5, 1),
               show_progress=False)
    print(f"offline fit done {(time.time()-t0)/60:.1f}m", flush=True)

    class Wrap:
        def __init__(self, m):
            self.m = m

        def predict(self, obs, deterministic=True):
            return int(self.m.predict(obs[None].astype(np.float32))[0]), None

    out = {"algo": f"offline-{algo}", "seed": seed, "steps": steps,
           "transitions": int(len(obs))}
    for name in ("train", "val", "test"):
        ds = ds_tr if name == "train" else E.Dataset(sp[name]).set_norm(norm)
        env = tr_env if name == "train" else E.TicketEnv(ds, norm=norm,
                                                         seed=seed)
        out[name] = E.run_epoch(env, Wrap(algo_o))
        out[name]["label"] = f"offline-{algo}-s{seed}-{name}"
        print(f"  {name}: {json.dumps(out[name])}", flush=True)
    out["wall_s"] = round(time.time() - t0, 1)
    f = RES / f"offline_{algo}_s{seed}.json"
    f.write_text(json.dumps(out, indent=1))
    print("wrote", f, flush=True)


if __name__ == "__main__":
    main()
