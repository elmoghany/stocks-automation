"""TimesFM 2.5 on AMD: zero-shot, zero-shot on log prices, and LoRA fine-tuning on log prices (cluster GPU).
Research/backtest only. Public price data only (AMD OHLC cache + public peer closes <= 2024-06-30).

  python tfm.py zs      --out fc_zs.csv        # official `timesfm` package, google/timesfm-2.5-200m-pytorch
  python tfm.py hfcheck --out hfcheck.json     # HF transformers port vs official package on a sample
  python tfm.py ft      --variant ft_amd|ft_peers --adapter DIR
  python tfm.py fcft    --variant ft_amd|ft_peers --adapter DIR --out fc_ft_amd.csv
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
DATA = HERE / "data"
TRAIN_END = pd.Timestamp("2024-06-30")
ES_START = pd.Timestamp("2023-07-01")      # early-stopping targets live in 2023-07-01..2024-06-30 (all still inside the train period)
FC_START, FC_END = pd.Timestamp("2024-07-01"), pd.Timestamp("2026-11-11")
CTX = 512
HZ = 20
HORIZONS = (5, 10, 20)


def load_amd():
    px = pd.read_csv(DATA / "amd_daily_2012_cache.csv", index_col=0, parse_dates=True)
    return px.close.astype(float)


def forecast_days(close):
    idx = close.index
    days = [i for i, d in enumerate(idx) if FC_START <= d <= FC_END]
    return days


def contexts(close, days, log):
    v = close.values
    out = []
    for i in days:
        w = v[max(0, i + 1 - CTX): i + 1]       # data up to and including day D only
        out.append(np.log(w) if log else w.copy())
    return out


def to_rows(close, days, fc, log, variant):
    """fc: (n_days, >=20) forecasts in input units. pred_ret = predicted close / close_D - 1."""
    rows = []
    v = close.values
    for k, i in enumerate(days):
        for h in HORIZONS:
            if log:
                r = float(np.exp(fc[k, h - 1] - np.log(v[i])) - 1)
            else:
                r = float(fc[k, h - 1] / v[i] - 1)
            rows.append((close.index[i].date().isoformat(), variant, h, r))
    return pd.DataFrame(rows, columns=["date", "variant", "horizon", "pred_ret"])


# ---------------------------------------------------------------- official package, zero-shot
def official_forecast(ctxs, log):
    import timesfm
    m = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
    m.compile(timesfm.ForecastConfig(max_context=CTX, max_horizon=32, normalize_inputs=True, use_continuous_quantile_head=True,
                                     force_flip_invariance=True, infer_is_positive=not log, fix_quantile_crossing=True, per_core_batch_size=64))
    outs = []
    for s in range(0, len(ctxs), 64):
        pf, _ = m.forecast(horizon=HZ, inputs=ctxs[s:s + 64])
        outs.append(np.asarray(pf))
    return np.concatenate(outs)


def cmd_zs(a):
    close = load_amd()
    days = forecast_days(close)
    print(len(days), "forecast days", close.index[days[0]].date(), close.index[days[-1]].date(), flush=True)
    parts = []
    for variant, log in (("zero_shot", False), ("zero_shot_log", True)):
        t = time.time()
        fc = official_forecast(contexts(close, days, log), log)
        np.save(HERE / f"raw_{variant}.npy", fc)
        parts.append(to_rows(close, days, fc, log, variant))
        print(variant, "done", round(time.time() - t), "s", flush=True)
    pd.concat(parts).to_csv(a.out, index=False)


# ---------------------------------------------------------------- HF port helpers
def hf_model(adapter=None, device=None):
    import torch
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    import torch
    from transformers import TimesFm2_5ModelForPrediction
    m = TimesFm2_5ModelForPrediction.from_pretrained("google/timesfm-2.5-200m-transformers", torch_dtype=torch.float32).to(device)
    if adapter:
        from peft import PeftModel
        m = PeftModel.from_pretrained(m, adapter)
    m.eval()
    return m


def hf_forecast(m, ctxs, log, device=None, bs=32):
    import torch
    device = next(m.parameters()).device
    outs = []
    with torch.no_grad():
        for s in range(0, len(ctxs), bs):
            batch = [torch.tensor(c, dtype=torch.float32, device=device) for c in ctxs[s:s + bs]]
            o = m(past_values=batch, forecast_context_len=CTX, truncate_negative=False if log else None)
            outs.append(o.mean_predictions[:, :HZ].float().cpu().numpy())
    return np.concatenate(outs)


def cmd_hfcheck(a):
    close = load_amd()
    days = forecast_days(close)[::10]
    res = {}
    m = hf_model()
    for variant, log in (("zero_shot", False), ("zero_shot_log", True)):
        ctx = contexts(close, days, log)
        off = official_forecast(ctx, log)
        hf = hf_forecast(m, ctx, log)
        ro = to_rows(close, days, off, log, variant).pred_ret.values
        rh = to_rows(close, days, hf, log, variant).pred_ret.values
        res[variant] = {"n": len(days), "corr_pred_ret": float(np.corrcoef(ro, rh)[0, 1]), "max_abs_diff_pred_ret": float(np.abs(ro - rh).max()),
                        "mean_abs_pred_ret_official": float(np.abs(ro).mean())}
        print(variant, res[variant], flush=True)
    json.dump(res, open(a.out, "w"), indent=1)


# ---------------------------------------------------------------- fine-tuning
def build_pool(variant):
    """Log-price series, each cut at TRAIN_END. ft_amd: AMD only. ft_peers: AMD plus peers."""
    amd = load_amd()
    amd = amd[amd.index <= TRAIN_END]
    pool = {"AMD": np.log(amd)}
    if variant == "ft_peers":
        peers = pd.read_csv(DATA / "peers_close_to_2024-06-30.csv", index_col=0, parse_dates=True)
        for t in peers.columns:
            s = peers[t].dropna()
            s = s[s.index <= TRAIN_END]
            pool[t] = np.log(s)
    for k, s in pool.items():
        assert s.index.max() <= TRAIN_END, k
    return pool


def windows(pool, kind, rng=None, n=None):
    """Return (ctx, tgt) arrays. kind train: target end date < ES_START. kind es: target end date in ES window. Contexts always inside train period."""
    items = []
    for name, s in pool.items():
        dates, v = s.index, s.values
        L = len(v)
        for t in range(CTX, L - HZ + 1):              # context v[t-CTX:t], target v[t:t+HZ]
            end = dates[t + HZ - 1]
            if (kind == "train" and end < ES_START) or (kind == "es" and end >= ES_START):
                items.append((name, t))
    return items


def get_batch(pool, items):
    import torch
    c = np.stack([pool[n].values[t - CTX:t] for n, t in items]).astype(np.float32)
    y = np.stack([pool[n].values[t:t + HZ] for n, t in items]).astype(np.float32)
    return torch.tensor(c), torch.tensor(y)


def cmd_ft(a):
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import TimesFm2_5ModelForPrediction
    torch.manual_seed(7)
    rng = np.random.default_rng(7)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    pool = build_pool(a.variant)
    tr_all = windows(pool, "train")
    es_all = windows(pool, "es")
    amd_tr = [x for x in tr_all if x[0] == "AMD"]
    oth_tr = [x for x in tr_all if x[0] != "AMD"]
    es = es_all[::2] if a.variant == "ft_peers" else [x for x in es_all if x[0] == "AMD"]
    print(a.variant, "series", len(pool), "train windows AMD", len(amd_tr), "other", len(oth_tr), "early-stop windows", len(es), flush=True)
    print("train target end max", max(pool["AMD"].index[t + HZ - 1] for _, t in amd_tr).date(), "| es dates",
          min(pool["AMD"].index[t + HZ - 1] for n, t in es if n == "AMD").date(), "..", max(pool["AMD"].index[t + HZ - 1] for n, t in es if n == "AMD").date(), flush=True)

    model = TimesFm2_5ModelForPrediction.from_pretrained("google/timesfm-2.5-200m-transformers", torch_dtype=torch.float32).to(dev)
    cfg = LoraConfig(r=a.r, lora_alpha=2 * a.r, target_modules="all-linear", lora_dropout=0.05, bias="none")
    model = get_peft_model(model, cfg)
    model.print_trainable_parameters()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.01)
    steps_per_epoch = a.per_epoch // a.bs
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=a.epochs * steps_per_epoch)

    def sample():
        if a.variant == "ft_amd":
            return [amd_tr[i] for i in rng.integers(0, len(amd_tr), a.per_epoch)]
        k = a.per_epoch // 2     # half the windows are AMD, half peers
        return [amd_tr[i] for i in rng.integers(0, len(amd_tr), k)] + [oth_tr[i] for i in rng.integers(0, len(oth_tr), a.per_epoch - k)]

    def evaluate():
        model.eval()
        tot, n, pa, ya = 0.0, 0, [], []
        with torch.no_grad():
            for s in range(0, len(es), 64):
                sub = es[s:s + 64]
                c, y = get_batch(pool, sub)
                c, y = c.to(dev), y.to(dev)
                o = model(past_values=c, future_values=y, forecast_context_len=CTX, truncate_negative=False)
                tot += o.loss.item() * len(sub)
                n += len(sub)
                for j, (nm, _) in enumerate(sub):
                    if nm == "AMD":
                        pa.append(float(o.mean_predictions[j, HZ - 1] - c[j, -1]))
                        ya.append(float(y[j, HZ - 1] - c[j, -1]))
        ic = float(np.corrcoef(pa, ya)[0, 1]) if len(pa) > 5 else float("nan")
        return tot / n, ic, float(np.std(pa))

    t0 = time.time()
    vl, ic, sd = evaluate()
    best, bad, best_ep = 1e9, 0, -1           # adapter saved = best early-stopping epoch among epochs >= 1; epoch-0 loss (= zero-shot log) logged for comparison
    print(f"epoch 0 (zero-shot, log prices) es_loss {vl:.4f} AMD es corr(pred20,real20) {ic:.3f} pred_sd {sd:.4f}", flush=True)
    log = [{"epoch": 0, "es_loss": vl, "es_ic": ic}]
    for ep in range(1, a.epochs + 1):
        model.train()
        items = sample()
        rng.shuffle(items)
        trl = 0.0
        for s in range(steps_per_epoch):
            c, y = get_batch(pool, items[s * a.bs:(s + 1) * a.bs])
            o = model(past_values=c.to(dev), future_values=y.to(dev), forecast_context_len=CTX, truncate_negative=False)
            o.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); opt.zero_grad(); sched.step()
            trl += o.loss.item()
        vl, ic, sd = evaluate()
        print(f"epoch {ep} train_loss {trl / steps_per_epoch:.4f} es_loss {vl:.4f} AMD es corr {ic:.3f} pred_sd {sd:.4f} t={time.time() - t0:.0f}s", flush=True)
        log.append({"epoch": ep, "train_loss": trl / steps_per_epoch, "es_loss": vl, "es_ic": ic})
        if vl < best - 1e-5:
            best, bad, best_ep = vl, 0, ep
            model.save_pretrained(a.adapter)
            print("  saved best", flush=True)
        else:
            bad += 1
            if bad >= a.patience:
                print("  early stop", flush=True)
                break
    json.dump({"args": vars(a), "log": log, "best_es_loss": best, "best_epoch": best_ep, "epoch0_es_loss": log[0]["es_loss"], "seconds": time.time() - t0, "gpu": torch.cuda.get_device_name(0) if dev == "cuda" else "cpu"},
              open(Path(a.adapter) / "train_log.json", "w"), indent=1)


def cmd_fcft(a):
    close = load_amd()
    days = forecast_days(close)
    m = hf_model(a.adapter)
    ctx = contexts(close, days, True)
    fc = hf_forecast(m, ctx, True)
    np.save(HERE / f"raw_{a.variant}.npy", fc)
    to_rows(close, days, fc, True, a.variant).to_csv(a.out, index=False)
    print("wrote", a.out, flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd")
    p.add_argument("--out")
    p.add_argument("--variant")
    p.add_argument("--adapter")
    p.add_argument("--epochs", type=int, default=12)
    p.add_argument("--patience", type=int, default=3)
    p.add_argument("--bs", type=int, default=32)
    p.add_argument("--per_epoch", type=int, default=3200)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--r", type=int, default=8)
    a = p.parse_args()
    {"zs": cmd_zs, "hfcheck": cmd_hfcheck, "ft": cmd_ft, "fcft": cmd_fcft}[a.cmd](a)
