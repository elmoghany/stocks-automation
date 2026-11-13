"""Rolling daily AMD forecasts from a Chronos-2 model (hub id or local fine-tuned dir).

Usage: python forecast.py MODEL VARIANT OUT_CSV [--cov] [--ctx 512] [--limit N] [--batch 16]
Input to the model is log(close) (log price), median (q0.5) forecast for the next 20 trading days; pred_ret = exp(q50[h]-logc_D)-1.
With --cov: past covariates log QQQ and log SMH (adjusted closes, up to D) and a known-future covariate days_to_next_earn.
Only data up to and including day D is in the context for day D.
"""
import argparse
import time

import numpy as np
import pandas as pd
import torch

from common import H, amd, forecast_days, idx, logc, peers, to_rows, days_to_next_earn, future_dates

ap = argparse.ArgumentParser()
ap.add_argument("model")
ap.add_argument("variant")
ap.add_argument("out")
ap.add_argument("--cov", action="store_true")
ap.add_argument("--ctx", type=int, default=512)
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--batch", type=int, default=16)
ap.add_argument("--dfrom", default="")
ap.add_argument("--dto", default="")
a = ap.parse_args()

from chronos import Chronos2Pipeline

torch.set_num_threads(4)
pipe = Chronos2Pipeline.from_pretrained(a.model, device_map=("cuda" if torch.cuda.is_available() else "cpu"))
qi = list(pipe.quantiles).index(0.5) if hasattr(pipe, "quantiles") else 10
print("median idx", qi, flush=True)

lq = np.log(peers["QQQ"].reindex(idx).ffill())
ls = np.log(peers["SMH"].reindex(idx).ffill())
dte = pd.Series(days_to_next_earn(idx), index=idx)

days = forecast_days() if not a.dfrom else idx[(idx >= a.dfrom) & (idx <= a.dto)]
if a.limit:
    days = days[: a.limit]
pos = {d: i for i, d in enumerate(idx)}
rows, t0 = [], time.time()
for b0 in range(0, len(days), a.batch):
    chunk = days[b0:b0 + a.batch]
    inputs = []
    for d in chunk:
        i = pos[d]
        lo = max(0, i + 1 - a.ctx)
        inp = {"target": logc.values[lo:i + 1].astype("float32")}
        if a.cov:
            inp["past_covariates"] = {"qqq": lq.values[lo:i + 1].astype("float32"), "smh": ls.values[lo:i + 1].astype("float32"),
                                      "dte": dte.values[lo:i + 1]}
            inp["future_covariates"] = {"dte": days_to_next_earn(future_dates(d)).astype("float32")}
        inputs.append(inp)
    out = pipe.predict(inputs, prediction_length=H, batch_size=a.batch)
    q50 = np.stack([o[0, qi, :].float().numpy() for o in out])
    rows += to_rows(a.variant, chunk, q50)
    print(f"{b0 + len(chunk)}/{len(days)} {time.time() - t0:.0f}s", flush=True)
pd.DataFrame(rows, columns=["date", "variant", "horizon", "pred_ret"]).to_csv(a.out, index=False)
print("wrote", a.out)
