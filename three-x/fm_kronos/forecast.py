"""Rolling daily AMD forecasts from a Kronos model (zero-shot or fine-tuned). Backtest only.

For every trading day D in [2024-07-01, 2026-11-11] the model sees only the last LOOKBACK daily bars up to and including D, samples
SAMPLES 20-step paths, and the mean path gives the predicted close 5/10/20 trading days ahead. pred_ret = pred_close / close_D - 1.
Future timestamps are the next 20 weekdays (calendar only, no price information).

Output rows: date,variant,horizon,pred_ret  (resumable: re-running skips dates already in the output file).
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ap = argparse.ArgumentParser()
ap.add_argument("--repo", required=True)
ap.add_argument("--prices", required=True)
ap.add_argument("--model", required=True)
ap.add_argument("--tokenizer", required=True)
ap.add_argument("--variant", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--lookback", type=int, default=400)
ap.add_argument("--samples", type=int, default=20)
ap.add_argument("--batch_days", type=int, default=8)
ap.add_argument("--max_context", type=int, default=512)
ap.add_argument("--start", default="2024-07-01")
ap.add_argument("--end", default="2026-11-11")
ap.add_argument("--limit", type=int, default=0)
a = ap.parse_args()

sys.path.insert(0, a.repo)
from model import Kronos, KronosTokenizer, KronosPredictor  # noqa: E402

torch.manual_seed(1234)
np.random.seed(1234)
px = pd.read_csv(a.prices, index_col=0, parse_dates=True)[["open", "high", "low", "close", "volume"]]
px["amount"] = px.volume * px[["open", "high", "low", "close"]].mean(axis=1)
days = [i for i, d in enumerate(px.index) if pd.Timestamp(a.start) <= d <= pd.Timestamp(a.end)]
if a.limit:
    days = days[: a.limit]

out = Path(a.out)
done = set()
if out.exists():
    old = pd.read_csv(out, parse_dates=["date"])
    done = set(old.date)
else:
    out.write_text("date,variant,horizon,pred_ret\n")
days = [i for i in days if px.index[i] not in done]
print(f"{a.variant}: {len(days)} days to do, device cuda={torch.cuda.is_available()}", flush=True)

tok = KronosTokenizer.from_pretrained(a.tokenizer)
mdl = Kronos.from_pretrained(a.model)
tok.eval()
mdl.eval()
pred = KronosPredictor(mdl, tok, max_context=a.max_context)

t0 = time.time()
for b in range(0, len(days), a.batch_days):
    chunk = days[b: b + a.batch_days]
    dfs, xs, ys = [], [], []
    for i in chunk:
        w = px.iloc[i - a.lookback + 1: i + 1]
        assert len(w) == a.lookback and w.index[-1] == px.index[i]
        dfs.append(w.reset_index(drop=True))
        xs.append(pd.Series(w.index))
        ys.append(pd.Series(pd.bdate_range(px.index[i] + pd.Timedelta(days=1), periods=20)))
    res = pred.predict_batch(dfs, xs, ys, pred_len=20, T=1.0, top_k=0, top_p=0.9, sample_count=a.samples, verbose=False)
    rows = []
    for i, r in zip(chunk, res):
        c0 = px.close.iloc[i]
        for h in (5, 10, 20):
            rows.append(f"{px.index[i].date()},{a.variant},{h},{r.close.iloc[h - 1] / c0 - 1:.6f}")
    with open(out, "a") as f:
        f.write("\n".join(rows) + "\n")
    print(f"{b + len(chunk)}/{len(days)} {time.time() - t0:.0f}s", flush=True)
print("done", flush=True)
