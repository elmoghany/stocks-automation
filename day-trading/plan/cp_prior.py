"""CHAMPION-REPLAY: slowly-varying PRE-OPEN context per (symbol, date).

Everything here is dated STRICTLY BEFORE the session it labels:

  dvol60   median dollar volume over the PRIOR 60 grouped-daily bars
  range60  median (high-low)/close over the same bars
  ret5     close/close-5 - 1 over the prior bars
  nhist    how many prior bars existed (a listing-age proxy)
  prevhi   prior session's high / prior close - 1 (yesterday's range up)
  shares   point-in-time shares outstanding from data/pt_shares (the
           file is keyed by the DATE it was read for, so it is the
           number a live scanner would have had); float/sector from
           data/rh_fundamentals.json as a static fallback.

Grouped daily (data/massive/gd) is the only price source, so this
covers the whole market, not just names with minute bars.

    python plan/cp_prior.py --build
"""

import gzip
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
GD = ROOT / "data/massive/gd"
OUT = ROOT / "data/massive/cp_prior"
WIN = 60


def gd_dates():
    return sorted(p.name.split(".")[0] for p in GD.glob("*.json.gz"))


def gd_rows(date):
    f = GD / f"{date}.json.gz"
    if not f.exists():
        return []
    with gzip.open(f, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    hist = {}          # sym -> list of (c, dvol, rng)
    for date in gd_dates():
        rows = gd_rows(date)
        # ---- emit the PRIOR-only context for this date first --------
        out = {}
        med = __import__("statistics").median
        for r in rows:
            sym = r.get("T")
            h = hist.get(sym)
            if not h:
                continue
            w = h[-WIN:]
            out[sym] = [
                round(med([x[1] for x in w]), 2),            # dvol60
                round(med([x[2] for x in w]), 6),            # range60
                len(h),                                      # nhist
                round(w[-1][0], 6),                          # prev close
                round(w[-1][2], 6),                          # prev range
                round(w[-1][0] / w[-6][0] - 1, 6)
                if len(w) >= 6 and w[-6][0] else None,       # ret5
            ]
        with gzip.open(OUT / f"{date}.json.gz", "wt", encoding="utf-8",
                       compresslevel=1) as fh:
            json.dump(out, fh)
        # ---- then fold this date into history ------------------------
        for r in rows:
            sym = r.get("T")
            c = r.get("c") or 0.0
            v = r.get("v") or 0.0
            hi = r.get("h") or 0.0
            lo = r.get("l") or 0.0
            if c <= 0:
                continue
            h = hist.setdefault(sym, [])
            h.append((c, c * v, (hi - lo) / c if c else 0.0))
            if len(h) > WIN + 5:
                del h[0]
        print(f"  {date} {len(out)} syms", flush=True)


_CACHE = {}
_SHARES = {}
_FUND = None


def load(date):
    if date in _CACHE:
        return _CACHE[date]
    f = OUT / f"{date}.json.gz"
    if not f.exists():
        _CACHE[date] = {}
        return {}
    with gzip.open(f, "rt", encoding="utf-8") as fh:
        raw = json.load(fh)
    d = {s: {"dvol60": r[0], "range60": r[1], "nhist": r[2],
             "prevclose": r[3], "prevrange": r[4], "ret5": r[5]}
         for s, r in raw.items()}
    if len(_CACHE) > 40:
        _CACHE.clear()
    _CACHE[date] = d
    return d


def shares(sym, date):
    """Point-in-time shares outstanding; None when never read."""
    k = (sym, date)
    if k in _SHARES:
        return _SHARES[k]
    f = ROOT / f"data/pt_shares/{sym}_{date}.json"
    v = None
    if f.exists():
        try:
            v = float(json.loads(f.read_text()))
        except Exception:
            v = None
    if v is None:
        global _FUND
        if _FUND is None:
            ff = ROOT / "data/rh_fundamentals.json"
            _FUND = json.loads(ff.read_text()) if ff.exists() else {}
        e = _FUND.get(sym) or {}
        v = e.get("shares_outstanding")
    if len(_SHARES) > 200_000:
        _SHARES.clear()
    _SHARES[k] = v
    return v


def context(syms, date):
    """{sym: {...}} for a panel's symbol list, prior information only."""
    base = load(date)
    out = {}
    for s in syms:
        d = dict(base.get(s) or {})
        sh = shares(s, date)
        if sh:
            d["shares"] = sh
        out[s] = d
    return out


if __name__ == "__main__":
    if "--build" in sys.argv[1:]:
        build()
    else:
        print(__doc__)
