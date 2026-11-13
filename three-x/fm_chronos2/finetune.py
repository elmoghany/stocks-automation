"""Fine-tune Chronos-2 on log-close series. Only data up to --train_end is used for fitting; windows for early stopping
come from a held-out tail of the training period, never from validation (2024-07..2025-06) or test.

Usage: python finetune.py BASE_MODEL OUT_DIR --set amd|peers --train_end 2024-06-30 [--val_from 2024-01-01]
       [--steps 300] [--lr 1e-5] [--ctx 256] [--batch 32] [--mode full|lora]

Stage A (model selection): --val_from 2024-01-01 trains only on data before it; the config is then judged on rolling forecasts over
2024-01..2024-06 (holdout.py). Stage B (final): no --val_from, trains on data up to 2024-06-30 with the chosen config.
Nothing after 2024-06-30 is ever used.
"""
import argparse
import time

import numpy as np
import pandas as pd
import torch

from common import H, amd, idx, logc, peers

ap = argparse.ArgumentParser()
ap.add_argument("base")
ap.add_argument("out")
ap.add_argument("--set", default="amd")
ap.add_argument("--train_end", default="2024-06-30")
ap.add_argument("--val_from", default="")
ap.add_argument("--steps", type=int, default=300)
ap.add_argument("--lr", type=float, default=1e-5)
ap.add_argument("--ctx", type=int, default=256)
ap.add_argument("--batch", type=int, default=32)
ap.add_argument("--mode", default="full")
a = ap.parse_args()
assert pd.Timestamp(a.train_end) <= pd.Timestamp("2024-06-30")

from chronos import Chronos2Pipeline

torch.set_num_threads(4)
series = {"AMD": logc}
if a.set == "peers":
    for t in peers.columns:
        series[t] = np.log(peers[t].dropna())


def cut(s, end):
    return s[s.index <= pd.Timestamp(end)].values.astype("float32")


end_tr = a.val_from and (pd.Timestamp(a.val_from) - pd.Timedelta(days=1)) or a.train_end
train = [{"target": cut(s, end_tr)} for s in series.values()]
val = None
print("train lens", [len(x["target"]) for x in train], "val", None if val is None else [len(x["target"]) for x in val], flush=True)

pipe = Chronos2Pipeline.from_pretrained(a.base, device_map=("cuda" if torch.cuda.is_available() else "cpu"))
t0 = time.time()
kw = {}
ft = pipe.fit(train, prediction_length=H, finetune_mode=a.mode, context_length=a.ctx, learning_rate=a.lr, num_steps=a.steps,
              batch_size=a.batch, output_dir=a.out, logging_steps=max(a.steps // 20, 5), **kw)
print(f"fit done {time.time() - t0:.0f}s", flush=True)
