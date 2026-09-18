"""DIRECTION-DETECTOR: extended PRIOR-ONLY context per (symbol, date).

`plan/cp_prior.py` is CHAMPION-REPLAY's and is not modified. It carries
six fields (dvol60, range60, nhist, prevclose, prevrange, ret5). This
module adds the multi-day block DIRECTION-DETECTOR's feature list asks
for, on the same grouped-daily source and with the same contract:

  EVERY value emitted for date D is computed from grouped-daily bars
  STRICTLY BEFORE D. The build loop emits first and folds the day into
  history afterwards, exactly as cp_prior does, so a look-ahead would
  require reordering two statements.

  ret1        prev close / close[-2] - 1          (yesterday's move)
  ret20       prev close / close[-21] - 1
  hi60        prev close / max(high, prior 60) - 1 (<=0; distance below
                                                   the 60-session high)
  lo60        prev close / min(low, prior 60) - 1  (>=0)
  vol20       stdev of prior-20 daily log returns
  amihud60    median |daily return| / dollar volume x 1e6 (Amihud)
  dvol5       median dollar volume, prior 5 sessions
  dvolr       dvol5 / dvol60 (short-vs-long liquidity)
  ngap60      how many of the prior 60 sessions had high/prevclose-1
              >= 10%   (the name's own gapper FREQUENCY)
  gapwin60    of those, the share that CLOSED above the prior close
  prevvolr    prior session volume / median prior-60 volume

    "C:\\cornell\\venvs\\rl\\Scripts\\python.exe" plan/dd_prior.py --build
"""

import gzip
import json
import math
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GD = ROOT / "data/massive/gd"
OUT = ROOT / "data/massive/dd_prior"
WIN = 60

FIELDS = ["ret1", "ret20", "hi60", "lo60", "vol20", "amihud60", "dvol5",
          "dvolr", "ngap60", "gapwin60", "prevvolr"]


def gd_dates():
    return sorted(p.name.split(".")[0] for p in GD.glob("*.json.gz"))


def gd_rows(date):
    f = GD / f"{date}.json.gz"
    if not f.exists():
        return []
    with gzip.open(f, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def _stats(h):
    """h = list of (c, h, l, v, dvol) for the PRIOR sessions, oldest first."""
    n = len(h)
    if n < 2:
        return None
    w = h[-WIN:]
    c = [x[0] for x in w]
    hi = [x[1] for x in w]
    lo = [x[2] for x in w]
    vv = [x[3] for x in w]
    dv = [x[4] for x in w]
    pc = c[-1]
    out = {}
    out["ret1"] = (pc / c[-2] - 1.0) if n >= 2 and c[-2] else None
    out["ret20"] = (pc / c[-21] - 1.0) if len(c) >= 21 and c[-21] else None
    mx = max(hi) if hi else 0.0
    mn = min([x for x in lo if x > 0], default=0.0)
    out["hi60"] = (pc / mx - 1.0) if mx > 0 else None
    out["lo60"] = (pc / mn - 1.0) if mn > 0 else None
    if len(c) >= 6:
        r = [math.log(c[i] / c[i - 1]) for i in range(max(1, len(c) - 20),
                                                     len(c))
             if c[i] > 0 and c[i - 1] > 0]
        out["vol20"] = st.pstdev(r) if len(r) >= 3 else None
        ai = [abs(math.log(c[i] / c[i - 1])) / dv[i] * 1e6
              for i in range(max(1, len(c) - WIN), len(c))
              if c[i] > 0 and c[i - 1] > 0 and dv[i] > 0]
        out["amihud60"] = st.median(ai) if len(ai) >= 5 else None
    else:
        out["vol20"] = out["amihud60"] = None
    out["dvol5"] = st.median(dv[-5:]) if len(dv) >= 5 else None
    d60 = st.median(dv) if dv else 0.0
    out["dvolr"] = (out["dvol5"] / d60) if (out["dvol5"] and d60 > 0) \
        else None
    ng = gw = 0
    for i in range(1, len(w)):
        p = c[i - 1]
        if p > 0 and hi[i] / p - 1.0 >= 0.10:
            ng += 1
            if c[i] > p:
                gw += 1
    out["ngap60"] = float(ng)
    out["gapwin60"] = (gw / ng) if ng else None
    v60 = st.median(vv) if vv else 0.0
    out["prevvolr"] = (vv[-1] / v60) if v60 > 0 else None
    return out


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    hist = {}
    dates = gd_dates()
    for k, date in enumerate(dates):
        rows = gd_rows(date)
        out = {}
        for r in rows:
            sym = r.get("T")
            h = hist.get(sym)
            if not h:
                continue
            s = _stats(h)
            if s is None:
                continue
            out[sym] = [None if s[f] is None else round(float(s[f]), 8)
                        for f in FIELDS]
        with gzip.open(OUT / f"{date}.json.gz", "wt", encoding="utf-8",
                       compresslevel=1) as fh:
            json.dump(out, fh)
        for r in rows:
            sym = r.get("T")
            c = r.get("c") or 0.0
            v = r.get("v") or 0.0
            hi = r.get("h") or 0.0
            lo = r.get("l") or 0.0
            if c <= 0:
                continue
            h = hist.setdefault(sym, [])
            h.append((c, hi, lo, v, c * v))
            if len(h) > WIN + 25:
                del h[0]
        if (k + 1) % 25 == 0:
            print(f"  {k+1}/{len(dates)} {date} {len(out)} syms", flush=True)


_CACHE = {}


def load(date):
    if date in _CACHE:
        return _CACHE[date]
    f = OUT / f"{date}.json.gz"
    if not f.exists():
        _CACHE[date] = {}
        return {}
    with gzip.open(f, "rt", encoding="utf-8") as fh:
        raw = json.load(fh)
    d = {s: dict(zip(FIELDS, r)) for s, r in raw.items()}
    if len(_CACHE) > 30:
        _CACHE.clear()
    _CACHE[date] = d
    return d


if __name__ == "__main__":
    if "--build" in sys.argv[1:]:
        build()
    else:
        print(__doc__)
