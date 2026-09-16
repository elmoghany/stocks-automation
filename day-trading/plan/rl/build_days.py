"""RL-SERIES (2026-09-16): build per-day intraday tensors for the RL env.

INPUT
  data/massive/gappers_novol_{y2025,year,aug2026}.json  -- the +10% gapper
      pool rows. ONLY symbol/date/prev_close are read; gain_pct/high/close/
      volume are DAY-AGGREGATE (future) fields and never reach the tensors.
  data/massive/m1/{SYM}_{date}.csv                      -- 1-min bars, UTC
  plan/rl/halal_offline.load().halal_pt                 -- the repo's
      point-in-time halal gate (HALAL_STRICT=1 PT_FILED=1) with the network
      removed; see halal_offline.py for the two offline substitutions and
      the cache-coverage confound they carry.

OUTPUT  plan/rl/out/days/{label}/{date}.npz
  syms      (S,)      ticker strings
  prev_close(S,)
  o,h,l,c,v (S,960)   float32, NaN where the minute printed nothing (v=0).
                      Minute grid is 04:00..19:59 ET, index = ET
                      minute-of-day - 240. ET offset is resolved once per
                      day via zoneinfo, so DST is handled.
  onset     (S,)      int16: first minute index >= 330 (09:30 ET) whose HIGH
                      reached 1.10 * prev_close -- the first moment at which
                      the name's POOL MEMBERSHIP is implied by PAST data.
                      -1 = never printed the cross in the regular session.

WHY onset EXISTS (NOTES "MX-SERIES RETRACTION #2", 2026-09-16): a row is in
gappers_novol_* iff its REGULAR-SESSION high cleared +10%. Looking at the
name before that print conditions the universe on the future; that is how
+$214k of a previously-claimed edge was manufactured. The env may only see
a name at minute m if 0 <= onset <= m. A consequence, inherited and
intended: no premarket (< 09:30) entries are reachable at all.

CAUSAL PER-DAY CAP: at most S_MAX names per day, ranked by CUMULATIVE
DOLLAR VOLUME 04:00-09:29 ET -- strictly before the first legal decision
minute, so the cap cannot see the day's outcome. Binding rate is reported.
"""
import csv
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import halal_offline                                       # noqa: E402

ROOT = HERE.parents[1]
OUT = HERE / "out"
M1 = ROOT / "data" / "massive" / "m1"
ET = ZoneInfo("America/New_York")

NMIN = 960            # 04:00 .. 19:59 ET
BASE_MIN = 4 * 60
RTH_LO = 9 * 60 + 30 - BASE_MIN      # 330  (09:30)
RTH_HI = 16 * 60 - BASE_MIN          # 720  (16:00)
GAP = 1.0999          # +10% over prev_close (the pool's own definition)
S_MAX = 96

_off_cache = {}


def et_offset_min(date):
    """UTC->ET shift in minutes for `date` (negative; -240 EDT, -300 EST)."""
    if date not in _off_cache:
        d = datetime.strptime(date, "%Y-%m-%d").replace(hour=12, tzinfo=ET)
        _off_cache[date] = int(d.utcoffset().total_seconds() // 60)
    return _off_cache[date]


def read_m1(sym, date):
    """(o,h,l,c,v) on the 960-slot ET minute grid, or None if no usable bar.

    CSV timestamps are UTC ('YYYY-MM-DD HH:MM:SS+00:00'). The 04:00-20:00 ET
    window maps entirely inside the same UTC date, so a fixed per-day offset
    is exact. Duplicate minutes keep the last row.
    """
    f = M1 / f"{sym}_{date}.csv"
    if not f.exists():
        return None
    off = et_offset_min(date)
    o = np.full(NMIN, np.nan, np.float32)
    h = np.full(NMIN, np.nan, np.float32)
    lo = np.full(NMIN, np.nan, np.float32)
    c = np.full(NMIN, np.nan, np.float32)
    v = np.zeros(NMIN, np.float32)
    seen = False
    with open(f, newline="") as fh:
        rd = csv.reader(fh)
        if next(rd, None) is None:
            return None
        for row in rd:
            if len(row) < 6:
                continue
            ts = row[0]
            if ts[:10] != date:
                continue
            try:
                k = int(ts[11:13]) * 60 + int(ts[14:16]) + off - BASE_MIN
            except ValueError:
                continue
            if not (0 <= k < NMIN):
                continue
            try:
                o[k] = float(row[1]); h[k] = float(row[2])
                lo[k] = float(row[3]); c[k] = float(row[4]); v[k] = float(row[5])
            except ValueError:
                continue
            seen = True
    return (o, h, lo, c, v) if seen else None


def build_label(label, pax, only_dates=None):
    rows = json.loads(
        (ROOT / "data" / "massive" / f"gappers_novol_{label}.json").read_text())
    by_date = defaultdict(list)
    for r in rows:
        by_date[r["date"]].append(r)
    outdir = OUT / "days" / label
    outdir.mkdir(parents=True, exist_ok=True)

    st = dict(label=label, n_rows=len(rows), n_dates=len(by_date), bad_pc=0,
              halal_fail=0, no_m1=0, no_onset=0, kept=0, cap_dropped=0,
              days_written=0, days_empty=0, onset_hist=[])
    s_hist = []
    dates = sorted(by_date)
    if only_dates:
        dates = [d for d in dates if d in only_dates]
    t0 = time.time()
    for di, date in enumerate(dates):
        cand = []
        for r in by_date[date]:
            sym, pc = r["symbol"], r.get("prev_close")
            if not pc or pc <= 0:
                st["bad_pc"] += 1
                continue
            try:
                ok = bool(pax.halal_pt(sym, date, pc))
            except Exception:
                ok = False
            if not ok:
                st["halal_fail"] += 1
                continue
            bars = read_m1(sym, date)
            if bars is None:
                st["no_m1"] += 1
                continue
            o, h, lo, c, v = bars
            hh = h[RTH_LO:]
            hit = np.where(hh >= pc * GAP)[0]
            if len(hit) == 0:
                st["no_onset"] += 1
                continue
            on = int(hit[0]) + RTH_LO
            pmdv = float(np.nansum(np.nan_to_num(c[:RTH_LO]) * v[:RTH_LO]))
            cand.append((pmdv, sym, float(pc), o, h, lo, c, v, on))
        if not cand:
            st["days_empty"] += 1
            continue
        st["kept"] += len(cand)
        if len(cand) > S_MAX:
            cand.sort(key=lambda x: -x[0])
            st["cap_dropped"] += len(cand) - S_MAX
            cand = cand[:S_MAX]
        cand.sort(key=lambda x: x[1])
        S = len(cand)
        s_hist.append(S)
        st["onset_hist"].extend(int(x[8]) for x in cand)
        arr = {k: np.empty((S, NMIN), np.float32) for k in "ohlcv"}
        for i, x in enumerate(cand):
            for j, k in enumerate("ohlcv"):
                arr[k][i] = x[3 + j]
        np.savez_compressed(
            outdir / f"{date}.npz",
            syms=np.array([x[1] for x in cand]),
            prev_close=np.array([x[2] for x in cand], np.float32),
            onset=np.array([x[8] for x in cand], np.int16), **arr)
        st["days_written"] += 1
        if st["days_written"] % 20 == 0:
            el = time.time() - t0
            print(f"  {label} {date} {di + 1}/{len(dates)} S={S} "
                  f"{el:.0f}s eta {el / (di + 1) * (len(dates) - di - 1):.0f}s",
                  flush=True)
    oh = sorted(st.pop("onset_hist"))
    if oh:
        st["onset_min_p10_p50_p90"] = [oh[0], oh[int(.1 * len(oh))],
                                       oh[len(oh) // 2], oh[int(.9 * len(oh))]]
        st["onset_frac_at_0930"] = round(sum(1 for x in oh if x == RTH_LO) / len(oh), 3)
        st["onset_frac_after_1600"] = round(sum(1 for x in oh if x >= RTH_HI) / len(oh), 4)
    sh = sorted(s_hist)
    if sh:
        st.update(S_min=sh[0], S_p50=sh[len(sh) // 2],
                  S_p90=sh[int(.9 * len(sh))], S_max=sh[-1],
                  S_mean=round(sum(sh) / len(sh), 1))
    st["shares_lookup"] = halal_offline.stats()
    return st


def main():
    args = [a for a in sys.argv[1:]]
    labels = [a for a in args if not a.startswith("--")] or \
        ["y2025", "year", "aug2026"]
    pax = halal_offline.load()
    OUT.mkdir(exist_ok=True)
    allst = {}
    for lb in labels:
        s = build_label(lb, pax)
        allst[lb] = s
        print(json.dumps(s), flush=True)
    p = OUT / "build_days_stats.json"
    old = json.loads(p.read_text()) if p.exists() else {}
    old.update(allst)
    old["_params"] = dict(S_MAX=S_MAX, GAP=GAP, NMIN=NMIN, RTH_LO=RTH_LO,
                          RTH_HI=RTH_HI, gate="HALAL_STRICT=1 PT_FILED=1 offline")
    p.write_text(json.dumps(old, indent=1))
    print("wrote", p, flush=True)


if __name__ == "__main__":
    main()
