"""R-campaign Phase 0: the Correlation Atlas.

QUESTION (user 2026-08-09): "find a mathematical or correlation relation
between the future signals and the signals we can estimate based on
current available signals at a specific time not knowing future."

For every bar-covered novol candidate-day, at four decision times
(07:00, crossing+1min, 09:30, 10:30), compute CAUSAL features and
correlate them -- per day, Spearman, then aggregated -- against:
  fwd_ret   price at T -> 15:00 close   (the money)
  fullgain  the day's final gain_pct    (the future signal itself)
  finrvol   the day's final rvol        (the other future signal)
  drawup    max high after T / price at T

Features (all computable at T):
  coil, gain_T, high_gain_T, dvol_T, pressure_T   (bars <= T)
  cross_min      first minute High >= 1.1*prev_close (time-of-day)
  gap7           7AM open gap vs prev close
  spread_proxy   median (H-L)/C of bars <= T
  prev_rvol      YESTERDAY's volume / its trailing 30d avg  (causal!)
  conf15_ret / conf15_dvol / conf15_prs   the 15 min AFTER crossing
                 (only defined for T >= crossing+16min)
  news           n18 count from the news cache (0 if absent)
  alpha_rank     ALPHABETICAL ticker rank -- nonsense control, must
                 show IC ~ 0 or the methodology is broken

Outputs: data/r_atlas.json (raw rows) + printed IC report.
Zero API calls -- local caches only.
"""

import gzip
import importlib.util
import json
import sys
from collections import defaultdict
from datetime import time as dtime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("dt", ROOT / "day-trading.py")
dt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dt)

M1 = ROOT / "data/massive/m1"
GD = ROOT / "data/massive/gd"
NEWS = ROOT / "data/news_cache"
OUT = ROOT / "data/r_atlas.json"
TIMES = {"0700": dtime(7, 0), "0930": dtime(9, 30), "1030": dtime(10, 30)}


def load_prev_rvol():
    """sym -> {date: yesterday's vol / trailing-30 avg} from gd cache."""
    per = defaultdict(list)
    for f in sorted(GD.glob("*.json.gz")):
        d = f.name[:10]
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                for r in json.load(fh):
                    if r.get("T") and r.get("v"):
                        per[r["T"]].append((d, float(r["v"])))
        except Exception:
            print(f"ERROR: unreadable {f.name}", flush=True)
    out = defaultdict(dict)
    for sym, rows in per.items():
        rows.sort()
        vols = [v for _, v in rows]
        for i in range(31, len(rows)):
            avg = sum(vols[i - 31:i - 1]) / 30
            if avg > 0:
                # value AS OF rows[i][0]: yesterday's (i-1) vol / its 30d avg
                out[sym][rows[i][0]] = vols[i - 1] / avg
    return out


def feats_at(df, prev_close, t):
    """Causal features from bars strictly <= t."""
    w = df[df.index.time <= t]
    if len(w) < 3 or not prev_close:
        return None
    last = float(w["Close"].iloc[-1])
    hi = float(w["High"].max())
    dvol = float((w["Close"] * w["Volume"]).sum())
    prs = None
    if len(w) >= 5:
        cd = dt.Candles(w)
        prs = cd.pressure(cd.n - 1, 30, 20_000)
    sp = float(((w["High"] - w["Low"]) / w["Close"]).median())
    return {"coil": last / hi if hi > 0 else 0,
            "gain_T": (last / prev_close - 1) * 100,
            "high_gain_T": (hi / prev_close - 1) * 100,
            "dvol_T": dvol, "pressure_T": prs,
            "spread_proxy": sp, "px_T": last}


def main():
    prev_rvol = load_prev_rvol()
    print(f"prev_rvol table: {len(prev_rvol):,} symbols", flush=True)
    rows = []
    cands = []
    for lab in ("year", "y2025"):
        for c in json.loads(
                (ROOT / f"data/massive/gappers_novol_{lab}.json").read_text()):
            if c.get("hist_n", 99) >= 50 and \
                    (M1 / f"{c['symbol']}_{c['date']}.csv").exists():
                cands.append((lab, c))
    print(f"{len(cands):,} bar-covered candidate-days", flush=True)

    for n, (lab, c) in enumerate(cands, 1):
        sym, d, pc = c["symbol"], c["date"], c.get("prev_close") or 0
        f = M1 / f"{sym}_{d}.csv"
        if pc <= 0 or f.read_text(errors="ignore").startswith("EMPTY"):
            continue
        try:
            df = pd.read_csv(f, index_col=0, parse_dates=True)
            df.index = df.index.tz_convert("America/New_York")
        except Exception:
            continue
        # crossing minute
        thr = 1.10 * pc
        cross = None
        for ts, hi in zip(df.index, df["High"].values):
            if ts.time() > dtime(12, 0):
                break
            if float(hi) >= thr:
                cross = ts
                break
        # close at 15:00 & post-T drawup base
        sess = df[df.index.time <= dtime(15, 0)]
        if len(sess) < 10:
            continue
        close15 = float(sess["Close"].iloc[-1])
        news_f = NEWS / f"{sym}_{d}.json"
        try:
            n18 = json.loads(news_f.read_text()).get("n18", 0) \
                if news_f.exists() else 0
        except Exception:
            n18 = 0
        base = {"sym": sym, "date": d, "lab": lab,
                "fullgain": c["gain_pct"], "finrvol": c.get("rvol"),
                "prev_rvol": prev_rvol.get(sym, {}).get(d),
                "news": n18,
                "cross_min": (cross.hour * 60 + cross.minute)
                if cross is not None else None,
                "gap7": None}
        w7 = df[df.index.time <= dtime(7, 0)]
        if len(w7):
            base["gap7"] = (float(w7["Close"].iloc[-1]) / pc - 1) * 100

        tset = dict(TIMES)
        if cross is not None:
            tset["cross1"] = (pd.Timestamp(cross) +
                              pd.Timedelta(minutes=1)).time()
        for tkey, t in tset.items():
            ft = feats_at(df, pc, t)
            if ft is None or ft["px_T"] <= 0:
                continue
            after = df[df.index.time > t]
            after = after[after.index.time <= dtime(15, 0)]
            if not len(after):
                continue
            r = dict(base)
            r["T"] = tkey
            r.update(ft)
            r["fwd_ret"] = (close15 / ft["px_T"] - 1) * 100
            r["drawup"] = (float(after["High"].max()) / ft["px_T"] - 1) * 100
            if cross is not None and tkey in ("0930", "1030"):
                c15 = df[(df.index > cross) &
                         (df.index <= cross + pd.Timedelta(minutes=15))]
                if len(c15):
                    px_c = float(df.loc[df.index == cross, "Close"].iloc[0]) \
                        if (df.index == cross).any() else ft["px_T"]
                    r["conf15_ret"] = (float(c15["Close"].iloc[-1]) /
                                       px_c - 1) * 100
                    r["conf15_dvol"] = float(
                        (c15["Close"] * c15["Volume"]).sum())
            rows.append(r)
        if n % 1000 == 0:
            print(f"  {n:,}/{len(cands):,}", flush=True)

    OUT.write_text(json.dumps(rows))
    print(f"{len(rows):,} feature rows -> {OUT.name}\n", flush=True)

    # ---------------- IC report ----------------
    A = pd.DataFrame(rows)
    A["alpha_rank"] = A["sym"].rank(method="dense")   # nonsense control
    FEATS = ["coil", "gain_T", "high_gain_T", "dvol_T", "pressure_T",
             "spread_proxy", "prev_rvol", "gap7", "cross_min", "news",
             "conf15_ret", "conf15_dvol", "alpha_rank"]
    TGTS = ["fwd_ret", "fullgain", "finrvol", "drawup"]

    def ic_table(sub, title):
        print(f"--- {title} (n={len(sub):,}) ---")
        hdr = f"{'feature':<14}" + "".join(f"{t:>10}" for t in TGTS) + \
            f"{'nIC':>7}"
        print(hdr)
        for ftr in FEATS:
            line = f"{ftr:<14}"
            nn = 0
            for tgt in TGTS:
                ics = []
                for _, g in sub.groupby("date"):
                    g2 = g[[ftr, tgt]].dropna()
                    if len(g2) >= 5:
                        ic = g2[ftr].corr(g2[tgt], method="spearman")
                        if ic == ic:
                            ics.append(ic)
                if ics:
                    m = sum(ics) / len(ics)
                    nn = len(ics)
                    line += f"{m:>+10.3f}"
                else:
                    line += f"{'--':>10}"
            print(line + f"{nn:>7}")
        print()

    for tkey in ("0700", "cross1", "0930", "1030"):
        sub = A[A["T"] == tkey]
        if len(sub):
            ic_table(sub, f"decision time {tkey}")
    # Y1/Y2 stability for the money target at 0930
    s = A[A["T"] == "0930"]
    for lab in ("year", "y2025"):
        ic_table(s[s["lab"] == lab], f"0930 {lab} (stability)")


if __name__ == "__main__":
    main()
