"""RL-SERIES v2, ITERATION PASS (2026-09-16): the WIDER feature block.

The first pass's finding was that the 26 intraday features carry no
cross-sectional information once the clock is taken away from the model
(plan/rl2/bandit2.py --rth 1 --target xs lands exactly on the 50th
percentile of its matched random control). The obvious missing information
is NOT intraday: it is multi-day position -- where the name sits in its own
recent range and how it has been trending -- plus the opening range, which
is the single most-used intraday reference in practice and was absent.

This writes plan/rl2/out/feat2/{D}.npz: byte-identical to feat/{D}.npz
except that F gains 11 columns. Everything else (mark, printed, fill_o,
volcap, flat_*, tgt, tgt_ok) is copied unchanged, so the two feature blocks
are exactly comparable and the first pass stays reproducible from feat/.

NEW COLUMNS (all causal)
  ret_5d, ret_20d, ret_60d   log return of the grouped-daily close over the
                             prior 5 / 20 / 60 TRADING days, all dates < D
  dist_20d_high, dist_20d_low  log(prev_close / max|min close over prior 20d)
  vol_20d                    stdev of prior-20d daily log returns
  dvol_ratio_5_60            log(median $vol prior 5d / median prior 60d)
  px_vs_ma20                 log(prev_close / mean close prior 20d)
  gap_open                   log(first printed close at/after 09:30 /
                             prev_close); 0 before 09:30, so it can never be
                             read early
  or_pos                     position of the mark inside the 09:30-10:00
                             opening range; 0 before 10:00
  or_break                   log(mark / opening-range high); 0 before 10:00
"""
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import features as FT                                         # noqa: E402

FEAT = HERE / "out" / "feat"
FEAT2 = HERE / "out" / "feat2"
OR_END = FT.RTH_LO + 30                 # 10:00 ET

NEW_NAMES = ["ret_5d", "ret_20d", "ret_60d", "dist_20d_high", "dist_20d_low",
             "vol_20d", "dvol_ratio_5_60", "px_vs_ma20", "gap_open",
             "or_pos", "or_break"]
FEATURE_NAMES2 = FT.FEATURE_NAMES + NEW_NAMES
NF2 = len(FEATURE_NAMES2)


class Daily2(FT.Daily):
    def multi(self, date, syms):
        i = self.didx[date]
        j = np.array([self.sidx.get(s, -1) for s in syms])
        ok = j >= 0
        jj = np.where(ok, j, 0)
        c = self.close[:, jj]
        v = self.vol[:, jj]

        def ret(k):
            if i - 1 - k < 0:
                return np.zeros(len(jj))
            with np.errstate(all="ignore"):
                return np.log(np.maximum(c[i - 1], 1e-9) /
                              np.maximum(c[i - 1 - k], 1e-9))
        w20 = c[max(0, i - 20):i]
        w60dv = (v * c)[max(0, i - 60):i]
        w5dv = (v * c)[max(0, i - 5):i]
        with np.errstate(all="ignore"):
            hi20 = np.nanmax(w20, axis=0) if len(w20) else np.full(len(jj), np.nan)
            lo20 = np.nanmin(w20, axis=0) if len(w20) else np.full(len(jj), np.nan)
            ma20 = np.nanmean(w20, axis=0) if len(w20) else np.full(len(jj), np.nan)
            r20 = np.diff(np.log(np.maximum(w20, 1e-9)), axis=0) if len(w20) > 1 \
                else np.zeros((1, len(jj)))
            vol20 = np.nanstd(r20, axis=0)
            m5 = np.nanmedian(w5dv, axis=0) if len(w5dv) else np.full(len(jj), np.nan)
            m60 = np.nanmedian(w60dv, axis=0) if len(w60dv) else np.full(len(jj), np.nan)
            pc = c[i - 1] if i >= 1 else np.full(len(jj), np.nan)
            out = np.stack([
                ret(5), ret(20), ret(60),
                np.log(np.maximum(pc, 1e-9) / np.maximum(hi20, 1e-9)),
                np.log(np.maximum(pc, 1e-9) / np.maximum(lo20, 1e-9)),
                vol20,
                np.log((np.nan_to_num(m5) + 1.0) / (np.nan_to_num(m60) + 1.0)),
                np.log(np.maximum(pc, 1e-9) / np.maximum(ma20, 1e-9)),
            ])
        out[:, ~ok] = 0.0
        return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)


def main():
    FEAT2.mkdir(parents=True, exist_ok=True)
    daily = Daily2()
    DAYS = HERE / "out" / "days"
    files = sorted(FEAT.glob("*.npz"))
    t0 = time.time()
    for k, p in enumerate(files):
        date = p.stem
        z = dict(np.load(p, allow_pickle=False))
        syms = [str(s) for s in z["syms"]]
        F = z["F"]
        T, S, _ = F.shape
        md = daily.multi(date, syms)                       # (8, S)
        raw = np.load(DAYS / f"{date}.npz", allow_pickle=False)
        o = raw["o"].astype(np.float64)
        h = raw["h"].astype(np.float64)
        lo = raw["l"].astype(np.float64)
        c = raw["c"].astype(np.float64)
        pc = z["prev_close"].astype(np.float64)
        mark = z["mark"].astype(np.float64)
        M = FT.STEPS
        cf = FT.ffill_rows(c)
        with np.errstate(all="ignore"):
            op = cf[:, FT.RTH_LO]
            gap_open = np.log(np.maximum(op, 1e-9) / np.maximum(pc, 1e-9))
            gap_open = np.nan_to_num(gap_open)
            seg_h = h[:, FT.RTH_LO:OR_END]
            seg_l = lo[:, FT.RTH_LO:OR_END]
            orh = np.nanmax(np.where(np.isnan(seg_h), -np.inf, seg_h), axis=1)
            orl = np.nanmin(np.where(np.isnan(seg_l), np.inf, seg_l), axis=1)
            orh = np.where(np.isfinite(orh), orh, np.nan)
            orl = np.where(np.isfinite(orl), orl, np.nan)
            rng = np.maximum(orh - orl, 1e-9)
            after_open = (M >= FT.RTH_LO)[:, None]
            after_or = (M >= OR_END)[:, None]
            f_gap = np.where(after_open, gap_open[None, :], 0.0)
            f_pos = np.where(after_or,
                             np.nan_to_num((mark - orl[None, :]) / rng[None, :]),
                             0.0)
            f_brk = np.where(after_or,
                             np.nan_to_num(np.log(np.maximum(mark, 1e-9) /
                                                  np.maximum(orh[None, :], 1e-9))),
                             0.0)
        add = np.empty((T, S, len(NEW_NAMES)), np.float32)
        for a in range(8):
            add[:, :, a] = md[a][None, :]
        add[:, :, 8] = f_gap
        add[:, :, 9] = np.clip(f_pos, -5, 5)
        add[:, :, 10] = np.clip(f_brk, -1, 1)
        z["F"] = np.concatenate([F, np.nan_to_num(add)], axis=2)
        np.savez_compressed(FEAT2 / f"{date}.npz", **z)
        if (k + 1) % 100 == 0:
            el = time.time() - t0
            print(f"  [{k+1}/{len(files)}] {date} {el:.0f}s", flush=True)
    (HERE / "out" / "feature_names2.json").write_text(json.dumps(FEATURE_NAMES2))
    print(f"feat2: {len(files)} days, NF={NF2}, {time.time()-t0:.0f}s",
          flush=True)


if __name__ == "__main__":
    main()
