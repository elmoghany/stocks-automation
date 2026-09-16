"""UNIVERSE+QUOTES (2026-09-16) -- constraint 2, stage 0: the minimal
Massive/Polygon wrappers this line needs that `shared/massive.py` does not
already have.

`shared/massive.py` is NOT edited -- its key resolution, its global
throttle and its 429 retry are imported and reused verbatim, so this
module cannot out-run the pacing every other job in the repo obeys.

WHAT IS ADDED
  quotes(sym, t0_ns, t1_ns)   /v3/quotes/{ticker}   historical NBBO
  trades(sym, t0_ns, t1_ns)   /v3/trades/{ticker}   historical prints
  ticker_reference(sym)       /v3/reference/tickers/{ticker} (undated)

WHAT IS DELIBERATELY NOT DONE
  No full-day tick pulls. A day of NBBO for one liquid name is 10^5-10^6
  quotes; the wide-net model acts on ~10^4 (symbol, day, decision-minute)
  points, and at each of those the only facts that matter are
    (a) the inside market in a +-10 s window around the decision instant,
    (b) the prints over the following 5 minutes, which decide whether a
        posted limit would have been hit.
  So the cache is keyed by (symbol, date, decision minute) and holds
  exactly those two windows. It is resumable: an existing file is never
  refetched, and an empty window is stored as an empty list so "we asked
  and the tape was silent" is distinguishable from "not fetched yet".

CACHE LAYOUT
  data/massive/quotes/{SYM}_{DATE}_{HHMM}.json.gz
      {"t0": ns, "lo": ns, "hi": ns, "q": [[t_ns, bid, bsz, ask, asz], ...]}
  data/massive/trades/{SYM}_{DATE}_{HHMM}.json.gz
      {"t0": ns, "lo": ns, "hi": ns, "x": [[t_ns, price, size], ...]}
  HHMM is the ET wall-clock minute of the DECISION INSTANT, which for a
  decision "at 09:35" is 09:36:00 -- the same instant the wide-net table
  fills at (the open of minute m+1). Stated explicitly because an off-by-
  one minute here would silently grade the fill against the wrong tape.
"""
import gzip
import json
import os
import sys
import time
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT.parent))
from shared import massive                                    # noqa: E402

massive._TH_INTERVAL = float(os.environ.get("MASSIVE_TH_INTERVAL", "0.25"))

ET = ZoneInfo("America/New_York")
QDIR = ROOT / "data" / "massive" / "quotes"
XDIR = ROOT / "data" / "massive" / "trades"
BASE = "https://api.polygon.io"

QUOTE_WIN_S = 10          # +- seconds of NBBO around the decision instant
TRADE_WIN_MIN = 5         # minutes of prints after it


def et_ns(date, hh, mm, ss=0):
    """ET wall clock -> epoch nanoseconds (DST resolved by zoneinfo)."""
    y, mo, d = (int(x) for x in date.split("-"))
    dt = datetime(y, mo, d, hh, mm, ss, tzinfo=ET)
    return int(dt.timestamp()) * 1_000_000_000


def _paged(url, cap=200_000):
    """Follow Polygon's next_url until the window is exhausted."""
    out = []
    u = url
    while u:
        d = massive._get(u + (f"&apiKey={massive._key()}"
                              if "apiKey=" not in u else ""))
        res = d.get("results") or []
        out.extend(res)
        if len(out) >= cap:
            break
        u = d.get("next_url")
    return out


def quotes(sym, t0_ns, t1_ns, limit=50000):
    """Historical NBBO rows in [t0_ns, t1_ns], ascending."""
    return _paged(f"{BASE}/v3/quotes/{sym}?timestamp.gte={t0_ns}"
                  f"&timestamp.lte={t1_ns}&order=asc&limit={limit}"
                  f"&sort=timestamp")


def trades(sym, t0_ns, t1_ns, limit=50000):
    """Historical trade prints in [t0_ns, t1_ns], ascending."""
    return _paged(f"{BASE}/v3/trades/{sym}?timestamp.gte={t0_ns}"
                  f"&timestamp.lte={t1_ns}&order=asc&limit={limit}"
                  f"&sort=timestamp")


def ticker_reference(sym):
    """Undated /v3/reference/tickers row ({} on 404)."""
    try:
        d = massive._get(f"{BASE}/v3/reference/tickers/{sym}"
                         f"?apiKey={massive._key()}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise
    return d.get("results") or {}


# ------------------------------------------------------------- cache API
def _qf(sym, date, hhmm):
    return QDIR / f"{sym}_{date}_{hhmm}.json.gz"


def _xf(sym, date, hhmm):
    return XDIR / f"{sym}_{date}_{hhmm}.json.gz"


def _wr(f, obj):
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.parent / f"{f.name}.{os.getpid()}.{id(obj)}.part"
    with gzip.open(tmp, "wt") as h:
        json.dump(obj, h, separators=(",", ":"))
    os.replace(tmp, f)


def _rd(f):
    with gzip.open(f, "rt") as h:
        return json.load(h)


def fetch_point(sym, date, hh, mm, retries=3):
    """Fetch (and cache) the two windows for one decision instant.
    Returns ('hit'|'got'|'fail', quotes_obj, trades_obj)."""
    hhmm = f"{hh:02d}{mm:02d}"
    qf, xf = _qf(sym, date, hhmm), _xf(sym, date, hhmm)
    if qf.exists() and xf.exists():
        try:
            return "hit", _rd(qf), _rd(xf)
        except Exception:
            pass
    t0 = et_ns(date, hh, mm)
    qlo, qhi = t0 - QUOTE_WIN_S * 10**9, t0 + QUOTE_WIN_S * 10**9
    xlo, xhi = t0, t0 + TRADE_WIN_MIN * 60 * 10**9
    for a in range(retries):
        try:
            q = quotes(sym, qlo, qhi)
            x = trades(sym, xlo, xhi)
        except Exception:
            if a == retries - 1:
                return "fail", None, None
            time.sleep(2 * (a + 1))
            continue
        qo = {"t0": t0, "lo": qlo, "hi": qhi,
              "q": [[r.get("sip_timestamp"), r.get("bid_price"),
                     r.get("bid_size"), r.get("ask_price"),
                     r.get("ask_size")] for r in q
                    if r.get("sip_timestamp") is not None]}
        xo = {"t0": t0, "lo": xlo, "hi": xhi,
              "x": [[r.get("sip_timestamp"), r.get("price"), r.get("size")]
                    for r in x if r.get("sip_timestamp") is not None]}
        _wr(qf, qo)
        _wr(xf, xo)
        return "got", qo, xo
    return "fail", None, None


def inside_at(qo, t_ns=None):
    """(bid, ask) from the LAST quote at or before t_ns (default t0).

    No-lookahead by construction: only quotes timestamped <= the decision
    instant are eligible. Returns (None, None) when the tape carried no
    two-sided quote in the window before t0.
    """
    if not qo:
        return None, None
    t = qo["t0"] if t_ns is None else t_ns
    b = a = None
    for row in qo["q"]:
        if row[0] is None or row[0] > t:
            break
        if row[1] and row[3] and row[3] > 0 and row[1] > 0:
            b, a = float(row[1]), float(row[3])
    return b, a


def first_fill(xo, limit_px, minutes, t0=None):
    """A BUY limit at `limit_px` posted at t0 fills iff a print lands at
    or below it within `minutes`. Returns the fill timestamp or None.

    The DECISION to post uses only information <= t0. Whether it fills is
    revealed by prints strictly AFTER t0 -- that is the tape answering the
    order, not the model peeking, and it is the only honest way to grade
    an unexecuted limit.
    """
    if not xo:
        return None
    t = xo["t0"] if t0 is None else t0
    hi = t + int(minutes * 60 * 10**9)
    for ts, px, _sz in xo["x"]:
        if ts is None or px is None or ts <= t:
            continue
        if ts > hi:
            break
        if float(px) <= limit_px:
            return ts
    return None


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "AAOI"
    date = sys.argv[2] if len(sys.argv) > 2 else "2026-08-05"
    st, qo, xo = fetch_point(sym, date, 9, 36)
    print(st, "quotes", len(qo["q"]) if qo else None,
          "trades", len(xo["x"]) if xo else None)
    b, a = inside_at(qo)
    print("inside at t0:", b, a,
          f"spread {10000*(a-b)/((a+b)/2):.1f} bps" if b and a else "")
    if b:
        for n in (1, 3, 5):
            print(f"  limit at bid {b}: fill within {n}m ->",
                  first_fill(xo, b, n) is not None)
