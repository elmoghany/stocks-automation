"""Score a forecasting model's AMD predictions the same way for every model. Backtest only, no orders.

Input CSV columns: date, variant, horizon, pred_ret. One row per decision day: pred_ret is the predicted return from that day's close to the
close `horizon` trading days later, made with data up to that close only. variant names the model setup (e.g. zero_shot, ft_amd, ft_peers).

Trading rule: in AMD when pred_ret > enter, out when pred_ret < leave (leave <= enter). Decided at the close, filled at the next open, 5 bp
per side. Thresholds are picked on validation (2024-07-01 to 2025-06-30) by final value and then frozen for the test (2025-07-01 on).
Target: twice the final value of holding AMD over the test. Also prints how often the predicted direction was right and the rank
correlation with what happened (IC), with a block-shuffle luck check on the test value.

Usage: python fm_eval.py results/fm_<model>_forecasts.csv
"""
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
VAL, TEST = pd.Timestamp("2024-07-01"), pd.Timestamp("2025-07-01")
COST = 0.0005
px = pd.read_csv(HERE / "results" / "amd_daily_2012_cache.csv", index_col=0, parse_dates=True)
idx, o, c = px.index, px.open.values, px.close.values


def value(pos, lo, hi):
    was = np.r_[0.0, pos[:-1]]
    before = np.r_[0.0, was[:-1]]
    d = np.ones(len(pos))
    d[1:] = np.where((was[1:] == 1) & (before[1:] == 1), c[1:] / c[:-1], 1.0)
    d[1:] = np.where((was[1:] == 1) & (before[1:] == 0), c[1:] / o[1:] * (1 - COST), d[1:])
    d[1:] = np.where((was[1:] == 0) & (before[1:] == 1), o[1:] / c[:-1] * (1 - COST), d[1:])
    return float(np.prod(d[lo + 1:hi]))


def position(pred, enter, leave):
    pos, hold = np.zeros(len(pred)), False
    for i, p in enumerate(pred):
        if not np.isnan(p):
            hold = (p > enter) if not hold else not (p < leave)
        pos[i] = float(hold)
    return pos


def main(path):
    f = pd.read_csv(path, parse_dates=["date"])
    lo_v, lo_t, hi = int(idx.searchsorted(VAL)), int(idx.searchsorted(TEST)), len(idx)
    held_v, held_t = c[lo_t - 1] / c[lo_v], c[hi - 1] / c[lo_t]
    print(f"{path}\nAMD held: validation {held_v:.2f}x, test {held_t:.2f}x. Target on test: {2 * held_t:.2f}x")
    rows = []
    rng = np.random.default_rng(7)
    for (variant, h), g in f.groupby(["variant", "horizon"]):
        pred = g.set_index("date").pred_ret.reindex(idx).values
        real = np.r_[c[h:] / c[:-h] - 1, np.full(h, np.nan)]
        out = {"variant": variant, "horizon": h}
        for name, a, b in (("val", lo_v, lo_t), ("test", lo_t, hi)):
            ok = ~np.isnan(pred[a:b]) & ~np.isnan(real[a:b])
            p, r = pred[a:b][ok], real[a:b][ok]
            out[f"{name}_days"] = int(ok.sum())
            out[f"{name}_dir"] = float((np.sign(p) == np.sign(r)).mean()) if len(p) else np.nan
            out[f"{name}_ic"] = float(pd.Series(p).corr(pd.Series(r), method="spearman")) if len(p) > 5 else np.nan
            out[f"{name}_up_share"] = float((r > 0).mean()) if len(p) else np.nan
        grid = [(e, l) for e, l in itertools.product((-0.02, 0.0, 0.01, 0.02, 0.03, 0.05, 0.08), (-0.08, -0.05, -0.03, -0.02, -0.01, 0.0, 0.01)) if l <= e]
        best = max(grid, key=lambda t: value(position(pred, *t), lo_v, lo_t))
        pos = position(pred, *best)
        test = value(pos, lo_t, hi)
        fake = []
        block = 10
        seg = pred[lo_t:hi]
        chunks = [seg[i:i + block] for i in range(0, len(seg), block)]
        for _ in range(300):
            order = rng.permutation(len(chunks))
            mixed = pred.copy()
            mixed[lo_t:hi] = np.concatenate([chunks[i] for i in order])
            fake.append(value(position(mixed, *best), lo_t, hi))
        out.update({"enter": best[0], "leave": best[1], "val_mult": value(pos, lo_v, lo_t), "test_mult": test, "test_vs_held": test / held_t,
                    "test_trades": int((np.diff(pos[lo_t:hi], prepend=pos[lo_t - 1]) > 0).sum()), "test_in_market": float(pos[lo_t:hi].mean()),
                    "luck": float(np.mean(np.array(fake) >= test)), "median_grid_test": float(np.median([value(position(pred, *t), lo_t, hi) for t in grid]))})
        rows.append(out)
    t = pd.DataFrame(rows).sort_values("test_mult", ascending=False)
    t.to_csv(Path(path).with_name(Path(path).stem.replace("_forecasts", "") + "_scores.csv"), index=False)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(t.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    print("\nluck = share of 300 block-shuffled forecast orders doing as well on the test; under 0.05 is good. median_grid_test = test value of the median threshold pair, a check that the picked pair is not a fluke.")


if __name__ == "__main__":
    main(sys.argv[1])
