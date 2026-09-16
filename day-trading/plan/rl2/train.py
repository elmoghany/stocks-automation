"""RL-SERIES v2, APPROACH 3 (2026-09-16): online PPO / MaskablePPO on the
wide-universe env.

v1's harness generalized: same algorithms, same seeds discipline, new
universe. The normalizer is fitted on TRAIN days only and handed to
val/test unchanged. Validation is used ONLY to record whether it predicts
test (in v1 it did not: corr = -0.126); the reported test row is the final
checkpoint, so no selection is performed on a short noisy statistic.

  python plan/rl2/train.py --algo maskppo --seed 0 --steps 300000
  python plan/rl2/train.py --algo ppo --variant leak30 --seed 0
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


def make(dates, norm=None, leak=False, seed=0, leak_k=6):
    ds = E.Dataset(dates)
    if norm is None:
        norm = ds.fit_norm()
    else:
        ds.set_norm(norm)
    return E.TicketEnv(ds, norm=norm, leak=leak, leak_k=leak_k, seed=seed), norm


def main():
    a = sys.argv[1:]
    algo = a[a.index("--algo") + 1] if "--algo" in a else "maskppo"
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 0
    steps = int(a[a.index("--steps") + 1]) if "--steps" in a else 300_000
    variant = a[a.index("--variant") + 1] if "--variant" in a else "real"
    leak = variant.startswith("leak")
    leak_k = 6 if variant == "leak30" else 1
    RES.mkdir(parents=True, exist_ok=True)

    sp = E.splits()
    t0 = time.time()
    tr_env, norm = make(sp["train"], leak=leak, seed=seed, leak_k=leak_k)
    va_env, _ = make(sp["val"], norm, leak, seed, leak_k)
    te_env, _ = make(sp["test"], norm, leak, seed, leak_k)
    print(f"days train/val/test = {len(sp['train'])}/{len(sp['val'])}/"
          f"{len(sp['test'])}  obs_dim={tr_env.obs_dim}  "
          f"load {time.time()-t0:.0f}s", flush=True)

    if algo == "maskppo":
        from sb3_contrib import MaskablePPO
        from sb3_contrib.common.wrappers import ActionMasker
        wrapped = ActionMasker(tr_env, lambda e: e.action_masks())
        model = MaskablePPO("MlpPolicy", wrapped, seed=seed, verbose=0,
                            n_steps=2048, batch_size=256, learning_rate=3e-4,
                            device="cpu")
    elif algo == "ppo":
        from stable_baselines3 import PPO
        model = PPO("MlpPolicy", tr_env, seed=seed, verbose=0, n_steps=2048,
                    batch_size=256, learning_rate=3e-4, device="cpu")
    elif algo == "dqn":
        from stable_baselines3 import DQN
        model = DQN("MlpPolicy", tr_env, seed=seed, verbose=0,
                    buffer_size=200_000, learning_starts=10_000,
                    device="cpu")
    else:
        raise SystemExit(f"unknown algo {algo}")
    model.learn(total_timesteps=steps, progress_bar=False)
    print(f"trained {steps:,} steps in {(time.time()-t0)/60:.1f}m", flush=True)

    out = {"algo": algo, "seed": seed, "steps": steps, "variant": variant}
    for name, env in (("train", tr_env), ("val", va_env), ("test", te_env)):
        out[name] = E.run_epoch(env, model, record=(name == "test"))
        out[name]["label"] = f"{algo}-{variant}-s{seed}-{name}"
        print(f"  {name}: {json.dumps(out[name])}", flush=True)
    out["wall_s"] = round(time.time() - t0, 1)
    f = RES / f"rl_{algo}_{variant}_s{seed}.json"
    f.write_text(json.dumps(out, indent=1))
    mdir = HERE / "out" / "models"
    mdir.mkdir(parents=True, exist_ok=True)
    model.save(str(mdir / f"{algo}_{variant}_s{seed}"))
    np.save(mdir / f"norm_{algo}_{variant}_s{seed}.npy", np.stack(norm))
    print("wrote", f, flush=True)


if __name__ == "__main__":
    main()
