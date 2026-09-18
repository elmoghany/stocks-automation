"""DIRECTION-DETECTOR: the name's OWN history of post-cross behaviour.

The mandate's feature list asks for "the name's OWN history of
post-cross behaviour (how it behaved on its prior gapper days --
causal, prior days only)". This module builds exactly that.

CONTRACT. For date D the emitted block for symbol s summarises the
sessions BEFORE D on which s was on the live scanner. The build walks
the panel dates in order and EMITS BEFORE FOLDING, so the current
session can never enter its own context.

Per prior gapper day of s (cross = the LAST-rule cross minute, entry
deferred to the next printed bar, exactly the engine's convention):

    rc    return from the deferred post-cross fill to the 15:00 last
    mfe   max high after the cross / fill - 1
    mae   min low after the cross / fill - 1

Emitted aggregate (all prior days, most-recent 20 kept):

    own_n        how many prior gapper days exist in the panel
    own_med_rc   median rc
    own_mean_rc  mean rc
    own_win      share of prior gapper days with rc > 0
    own_med_mfe  median mfe
    own_med_mae  median mae
    own_last_rc  rc on the most recent prior gapper day
    own_since    panel sessions since that day

    "C:\\cornell\\venvs\\rl\\Scripts\\python.exe" plan/dd_own.py --build
"""

import gzip
import json
import statistics as st
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L                                          # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/massive/dd_own"
KEEP = 20
FIELDS = ["own_n", "own_med_rc", "own_mean_rc", "own_win", "own_med_mfe",
          "own_med_mae", "own_last_rc", "own_since"]


def day_outcomes(day):
    """{sym: (rc, mfe, mae)} for every name that crossed in session."""
    cm = day.cross_minute(mode="LAST", start=L.M_OPEN, end=L.M_1500)
    out = {}
    last = day.last
    for i in range(day.n):
        m = int(cm[i])
        if m >= L.NMIN or m >= L.M_1500:
            continue
        # deferred fill: the next printed bar's open
        em = None
        for k in range(m + 1, min(m + 61, L.M_1500)):
            if day.printed[i, k]:
                em = k
                break
        if em is None:
            continue
        px = float(day.o[i, em])
        if not np.isfinite(px) or px <= 0:
            continue
        end = float(last[i, L.M_1500])
        if not np.isfinite(end):
            continue
        sel = day.printed[i, em:L.M_1500 + 1]
        if not sel.any():
            continue
        hh = float(np.nanmax(np.where(sel, day.h[i, em:L.M_1500 + 1],
                                      np.nan)))
        ll = float(np.nanmin(np.where(sel, day.l[i, em:L.M_1500 + 1],
                                      np.nan)))
        out[day.syms[i]] = (end / px - 1.0, hh / px - 1.0, ll / px - 1.0)
    return out


def _agg(h, di):
    """h = list of (date_index, rc, mfe, mae), oldest first."""
    rc = [x[1] for x in h]
    mf = [x[2] for x in h]
    ma = [x[3] for x in h]
    return [float(len(h)), st.median(rc), float(np.mean(rc)),
            float(np.mean([1.0 if x > 0 else 0.0 for x in rc])),
            st.median(mf), st.median(ma), rc[-1], float(di - h[-1][0])]


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    hist = {}
    dates = L.panel_dates()
    for di, date in enumerate(dates):
        day = L.load_day(date)
        if day is None:
            continue
        out = {}
        for s in day.syms:
            h = hist.get(s)
            if h:
                out[s] = [round(float(x), 8) for x in _agg(h, di)]
        with gzip.open(OUT / f"{date}.json.gz", "wt", encoding="utf-8",
                       compresslevel=1) as fh:
            json.dump(out, fh)
        for s, (rc, mf, ma) in day_outcomes(day).items():
            h = hist.setdefault(s, [])
            h.append((di, rc, mf, ma))
            if len(h) > KEEP:
                del h[0]
        if (di + 1) % 25 == 0:
            print(f"  {di+1}/{len(dates)} {date} ctx={len(out)}", flush=True)
    print(f"dd_own: {len(list(OUT.glob('*.json.gz')))} dates")


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
