"""RL-SERIES (2026-09-16): train one RL agent on the intraday ticket env.

  python plan/rl/train.py --algo ppo --seed 0 --steps 400000 --variant real

VARIANTS
  real     the actual panel.
  shuffle  SHUFFLED-LABELS CONTROL. Train AND test on a panel whose
           per-symbol intraday log-return sequence is permuted. A positive
           test result here is proof of leakage, not of skill.
  leak     POSITIVE CONTROL. The next step's open-to-open return for each
           candidate slot is appended to the observation. The agent SHOULD
           print a large positive number; if it does not, the harness has no
           statistical power and the null results mean nothing.

PROTOCOL
  * Splits are date-strict and come from different pool files:
      train  y2025   2024-10-22 .. 2025-05-30
      val    y2025   2025-06-02 .. 2025-07-31   (model selection ONLY)
      test   year    2025-08-01 .. 2026-07-31   (touched once, at the end)
      extra  aug2026 2026-08-01 ..
  * The feature normalizer is fitted on TRAIN ONLY and handed to val/test/
    extra unchanged.
  * Checkpoint selection is by VALIDATION total P&L. The number of
    checkpoints inspected is recorded (`n_checkpoints`) because it is part
    of the multiple-testing count that any Sharpe here must be deflated by.
  * Nothing about the test window influences training, early stopping or
    hyper-parameters.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import env as E                                             # noqa: E402

RES = E.OUT / "results"


# ------------------------------------------------------------------ policies
def model_policy(model, masked=False):
    def pol(obs, env):
        if masked:
            a, _ = model.predict(obs, deterministic=True,
                                 action_masks=env.action_masks())
        else:
            a, _ = model.predict(obs, deterministic=True)
        return int(np.asarray(a).reshape(-1)[0]) if np.ndim(a) else int(a)
    return pol


def cont_model_policy(model):
    """SAC/TD3 emit a score vector; take the argmax over LEGAL actions."""
    def pol(obs, env):
        a, _ = model.predict(obs, deterministic=True)
        s = np.asarray(a, float).reshape(-1)
        m = env.action_masks()
        s = np.where(m, s, -np.inf)
        return int(np.argmax(s))
    return pol


class ContinuousWrap(E.TicketEnv):
    """Box(n_actions) score vector -> masked argmax. Lets the continuous-only
    SB3 algorithms (SAC/TD3) drive the same discrete ticket env, which is the
    'discretized wrapper' the brief asks for."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        from gymnasium import spaces
        self.action_space = spaces.Box(-1.0, 1.0, (self.n_actions,), np.float32)

    def step(self, action):
        s = np.asarray(action, float).reshape(-1)
        m = self.action_masks()
        s = np.where(m, s, -np.inf)
        return super().step(int(np.argmax(s)))


# ------------------------------------------------------------------ datasets
def load_splits(variant, seed, max_days=None):
    sp = E.split_files()
    if max_days:
        sp = {k: v[:max_days] for k, v in sp.items()}
    tf = "shuffle" if variant == "shuffle" else None
    out = {}
    for k, files in sp.items():
        out[k] = E.Dataset(files, transform=tf,
                           seed=seed * 1000 + hash(k) % 997, label=k)
    norm = out["train"].fit_norm()
    for k in out:
        out[k].set_norm(norm)
    return out, norm, {k: len(v) for k, v in sp.items()}


# ------------------------------------------------------------------ training
def build_model(algo, env, seed, device="cpu"):
    from stable_baselines3 import A2C, DQN, PPO, SAC
    common = dict(seed=seed, verbose=0, device=device)
    if algo == "eiieppo":
        from eiie import EIIE_KW
        return PPO("MlpPolicy", env, n_steps=1260, batch_size=252, n_epochs=8,
                   learning_rate=3e-4, gamma=0.999, gae_lambda=0.95,
                   ent_coef=0.01, clip_range=0.2,
                   policy_kwargs=dict(EIIE_KW), **common)
    if algo == "eiiemask":
        from eiie import EIIE_KW
        from sb3_contrib import MaskablePPO
        return MaskablePPO("MlpPolicy", env, n_steps=1260, batch_size=252,
                           n_epochs=8, learning_rate=3e-4, gamma=0.999,
                           gae_lambda=0.95, ent_coef=0.01, clip_range=0.2,
                           policy_kwargs=dict(EIIE_KW), **common)
    if algo == "ppo":
        return PPO("MlpPolicy", env, n_steps=1260, batch_size=252, n_epochs=8,
                   learning_rate=3e-4, gamma=0.999, gae_lambda=0.95,
                   ent_coef=0.01, clip_range=0.2,
                   policy_kwargs=dict(net_arch=[128, 128]), **common)
    if algo == "maskppo":
        from sb3_contrib import MaskablePPO
        return MaskablePPO("MlpPolicy", env, n_steps=1260, batch_size=252,
                           n_epochs=8, learning_rate=3e-4, gamma=0.999,
                           gae_lambda=0.95, ent_coef=0.01, clip_range=0.2,
                           policy_kwargs=dict(net_arch=[128, 128]), **common)
    if algo == "a2c":
        return A2C("MlpPolicy", env, n_steps=63, learning_rate=7e-4,
                   gamma=0.999, ent_coef=0.01,
                   policy_kwargs=dict(net_arch=[128, 128]), **common)
    if algo == "dqn":
        return DQN("MlpPolicy", env, learning_rate=1e-4, buffer_size=200_000,
                   learning_starts=10_000, batch_size=256, gamma=0.999,
                   train_freq=4, target_update_interval=2000,
                   exploration_fraction=0.30, exploration_final_eps=0.05,
                   policy_kwargs=dict(net_arch=[128, 128]), **common)
    if algo == "sac":
        return SAC("MlpPolicy", env, learning_rate=3e-4, buffer_size=200_000,
                   learning_starts=10_000, batch_size=256, gamma=0.999,
                   train_freq=4, policy_kwargs=dict(net_arch=[128, 128]),
                   **common)
    raise SystemExit(f"unknown algo {algo}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--algo", default="ppo",
                    choices=["ppo", "maskppo", "eiieppo", "eiiemask", "dqn", "a2c", "sac"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--steps", type=int, default=400_000)
    ap.add_argument("--variant", default="real",
                    choices=["real", "shuffle", "leak"])
    ap.add_argument("--evals", type=int, default=10)
    ap.add_argument("--max-days", type=int, default=0)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()

    t0 = time.time()
    ds, norm, counts = load_splits(a.variant, a.seed,
                                   a.max_days or None)
    leak = a.variant == "leak"
    cont = a.algo == "sac"
    cls = ContinuousWrap if cont else E.TicketEnv
    kw = dict(norm=norm, leak=leak, seed=a.seed)
    train_env = cls(ds["train"], shuffle_days=True, **kw)
    if a.algo in ("maskppo", "eiiemask"):
        from sb3_contrib.common.wrappers import ActionMasker
        train_env = ActionMasker(train_env, lambda e: e.action_masks())
    model = build_model(a.algo, train_env, a.seed, a.device)

    def eval_on(split, m, record=False):
        e = cls(ds[split], shuffle_days=False, **kw)
        pol = cont_model_policy(m) if cont else \
            model_policy(m, masked=(a.algo in ("maskppo", "eiiemask")))
        return E.run_epoch(e, pol, record=record)

    chunk = max(a.steps // a.evals, 1)
    best = (-1e18, None, 0)
    hist = []
    for it in range(a.evals):
        model.learn(total_timesteps=chunk, reset_num_timesteps=(it == 0),
                    progress_bar=False)
        v = eval_on("val", model)
        hist.append({"step": (it + 1) * chunk, "val_pnl": v["total_pnl"],
                     "val_tickets": v["tickets"]})
        print(f"[{a.algo} s{a.seed} {a.variant}] {(it+1)*chunk} "
              f"val {v['total_pnl']:.0f} ({v['tickets']} tk) "
              f"{time.time()-t0:.0f}s", flush=True)
        if v["total_pnl"] > best[0]:
            import io
            buf = io.BytesIO()
            model.save(buf)
            best = (v["total_pnl"], buf, (it + 1) * chunk)

    if best[1] is not None:
        best[1].seek(0)
        model = type(model).load(best[1], device=a.device)
    out = {
        "algo": a.algo, "seed": a.seed, "variant": a.variant,
        "steps": a.steps, "n_checkpoints": a.evals,
        "best_val_pnl": best[0], "best_step": best[2],
        "split_days": counts, "history": hist,
        "wall_s": round(time.time() - t0, 1),
        "env": dict(fee_bps=E.FEE_BPS, ext_bps=E.EXT_BPS,
                    vol_cap=E.VOL_CAP_FRAC, step_min=E.STEP,
                    k_slots=E.K_SLOTS, tickets=E.TICKET_NOTIONALS),
    }
    for split in ("train", "val", "test", "extra"):
        if counts.get(split):
            out[split] = eval_on(split, model, record=True)
    RES.mkdir(parents=True, exist_ok=True)
    tag = f"{a.algo}_{a.variant}_s{a.seed}" + (f"_{a.tag}" if a.tag else "")
    p = RES / f"{tag}.json"
    p.write_text(json.dumps(out, indent=1))
    print("wrote", p, json.dumps({k: out[k]["total_pnl"]
                                  for k in ("train", "val", "test", "extra")
                                  if k in out}), flush=True)


if __name__ == "__main__":
    main()
