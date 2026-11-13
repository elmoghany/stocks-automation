"""Fine-tune the Kronos PREDICTOR (tokenizer frozen) on daily price CSVs. One GPU, no torchrun, no Qlib.

Hard data rule: nothing after 2024-06-30 is ever used. Training windows must END on or before TRAIN_END (2023-06-30); early-stopping
windows end in (2023-06-30, 2024-06-30] and their loss is measured only on the last PRED_LEN target tokens (the forecast part), so the
stopping signal is "forecast quality on a held-out year", not reconstruction of bars the model trained on.

mode amd   : AMD only.
mode peers : AMD + peer chip stocks/ETFs (NVDA INTC QCOM AVGO MU TXN AMAT LRCX KLAC ADI MCHP NXPI ON SWKS QQQ SMH), also <= 2024-06-30.
Step 0 (pretrained weights) is evaluated too; if no step beats it, the saved model IS the pretrained one and that is reported.
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ap = argparse.ArgumentParser()
ap.add_argument("--repo", required=True)
ap.add_argument("--data", required=True, help="dir with AMD.csv and peer csvs")
ap.add_argument("--model", required=True)
ap.add_argument("--tokenizer", required=True)
ap.add_argument("--mode", choices=["amd", "peers"], required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--lookback", type=int, default=400)
ap.add_argument("--pred_len", type=int, default=20)
ap.add_argument("--batch", type=int, default=32)
ap.add_argument("--lr", type=float, default=4e-5)
ap.add_argument("--steps_per_epoch", type=int, default=100)
ap.add_argument("--max_epochs", type=int, default=15)
ap.add_argument("--patience", type=int, default=3)
ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()

sys.path.insert(0, a.repo)
from model import Kronos, KronosTokenizer  # noqa: E402

TRAIN_END, ES_END = pd.Timestamp("2023-06-30"), pd.Timestamp("2024-06-30")
random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
dev = "cuda" if torch.cuda.is_available() else "cpu"
L, P = a.lookback, a.pred_len
W = L + P

names = ["AMD"] if a.mode == "amd" else ["AMD", "NVDA", "INTC", "QCOM", "AVGO", "MU", "TXN", "AMAT", "LRCX", "KLAC", "ADI", "MCHP", "NXPI", "ON", "SWKS", "QQQ", "SMH"]
series = {}
for n in names:
    df = pd.read_csv(Path(a.data) / f"{n}.csv", index_col=0, parse_dates=True)[["open", "high", "low", "close", "volume"]]
    df = df[df.index <= ES_END]  # nothing later is even loaded
    df["amount"] = df.volume * df[["open", "high", "low", "close"]].mean(axis=1)
    ts = df.index.to_series()
    stamp = np.stack([ts.dt.minute, ts.dt.hour, ts.dt.weekday, ts.dt.day, ts.dt.month], 1).astype(np.float32)
    series[n] = (df[["open", "high", "low", "close", "volume", "amount"]].values.astype(np.float32), stamp, df.index)

train, es = [], []
for n, (x, s, idx) in series.items():
    for end in range(W - 1, len(idx)):
        d = idx[end]
        if d <= TRAIN_END:
            train.append((n, end - W + 1))
        elif d <= ES_END and (end % 5 == 0) and (n == "AMD" or a.mode == "peers"):
            es.append((n, end - W + 1))
print(f"mode={a.mode} train windows {len(train)}, early-stop windows {len(es)}", flush=True)


def get(n, st):
    x, s, _ = series[n]
    w, ws = x[st: st + W], s[st: st + W]
    m, sd = w[:L].mean(0), w[:L].std(0)
    w = np.clip((w - m) / (sd + 1e-5), -5, 5)
    return w, ws


def batch(items):
    xs, ss = zip(*[get(*it) for it in items])
    return torch.from_numpy(np.stack(xs)).to(dev), torch.from_numpy(np.stack(ss)).to(dev)


tok = KronosTokenizer.from_pretrained(a.tokenizer).eval().to(dev)
for p in tok.parameters():
    p.requires_grad_(False)
mdl = Kronos.from_pretrained(a.model).to(dev)


def loss_fn(items, last_only):
    x, s = batch(items)
    with torch.no_grad():
        t0, t1 = tok.encode(x, half=True)
    lg = mdl(t0[:, :-1], t1[:, :-1], s[:, :-1])
    if last_only:
        sl = slice(-P, None)
        return mdl.head.compute_loss(lg[0][:, sl], lg[1][:, sl], t0[:, 1:][:, sl], t1[:, 1:][:, sl])
    return mdl.head.compute_loss(lg[0], lg[1], t0[:, 1:], t1[:, 1:])


@torch.no_grad()
def es_loss():
    mdl.eval()
    tot, n = 0.0, 0
    for i in range(0, len(es), 64):
        c = es[i: i + 64]
        tot += loss_fn(c, True)[0].item() * len(c)
        n += len(c)
    return tot / n


opt = torch.optim.AdamW([p for p in mdl.parameters() if p.requires_grad], lr=a.lr, betas=(0.9, 0.95), weight_decay=0.1)
total = a.max_epochs * a.steps_per_epoch
sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda t: min(1.0, (t + 1) / 30) * (0.1 + 0.9 * 0.5 * (1 + np.cos(np.pi * t / total))))
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
log = {"mode": a.mode, "train_windows": len(train), "es_windows": len(es), "epochs": []}
best = es_loss()
log["es_loss_step0_pretrained"] = best
best_epoch, bad = 0, 0
mdl.save_pretrained(out / "best")
print(f"step 0 (pretrained) early-stop loss {best:.4f}", flush=True)
t_start = time.time()
for ep in range(1, a.max_epochs + 1):
    mdl.train()
    run = 0.0
    for _ in range(a.steps_per_epoch):
        items = random.sample(train, a.batch)
        loss = loss_fn(items, False)[0]
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(mdl.parameters(), 3.0)
        opt.step()
        sched.step()
        run += loss.item()
    v = es_loss()
    log["epochs"].append({"epoch": ep, "train_loss": run / a.steps_per_epoch, "es_loss": v, "secs": time.time() - t_start})
    print(f"epoch {ep} train {run / a.steps_per_epoch:.4f} es {v:.4f} ({time.time() - t_start:.0f}s)", flush=True)
    if v < best - 1e-4:
        best, best_epoch, bad = v, ep, 0
        mdl.save_pretrained(out / "best")
    else:
        bad += 1
        if bad >= a.patience:
            break
log.update(best_es_loss=best, best_epoch=best_epoch, total_secs=time.time() - t_start, device=dev, gpu=torch.cuda.get_device_name(0) if dev == "cuda" else None)
(out / "log.json").write_text(json.dumps(log, indent=1))
print("finished", json.dumps({k: log[k] for k in ("best_es_loss", "best_epoch", "es_loss_step0_pretrained")}), flush=True)
