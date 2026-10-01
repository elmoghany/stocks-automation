"""PAPER-3BOOK (2026-10-01): shared plumbing for the three live paper books.

    R4   plan/p3_r4.py   CHAMPION-REPLAY "coil + no stop"     (gapper scanner)
    R15  plan/p3_r15.py  CATALYST-MINER fresh earnings & green @09:35, h60
    RL   plan/p3_rl.py   RL-SCOUT v2 approach-4 seed-0 rule   (wide universe)

PAPER ONLY, OPEN-ENDED. Real orders never, unless the user explicitly
authorizes them in conversation. Nothing in this package can place an
order: it reads bar/quote/scan files the session agent wrote and prints a
decision.

ONE GRID FOR EVERYTHING: minute index k = minutes since 04:00 ET,
0..959 (04:00..19:59). 09:30 = 330, 16:00 = 720. A bar with index k
covers [k, k+1) and is COMPLETE once the wall clock reaches k+1, so a
live call at wall minute `now` may only see bars k <= now-1. The
historical feed (CacheFeed, used by the parity test) applies the same
truncation, so live code and parity replay see the same object.

FILES (all per trading date D)
  data/rh_bars/{SYM}_{D}.csv          1-min bars, written by the agent
                                      (plan/p3_ingest.py or append_bars.py)
  data/paper/quotes_{D}.json          {SYM: {bid, ask, ts}} written by agent
  data/paper/{book}/                  per-book state (watcher state files,
                                      events, scan snapshots)
  data/paper_days/{D}.3book.json/.md  the ledger
"""
import csv
import json
import os
import subprocess
import sys
from datetime import date as ddate, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
PLAN = Path(__file__).resolve().parent
ROOT = PLAN.parent
DATA = ROOT / "data"
RH_BARS = DATA / "rh_bars"
MASSIVE = DATA / "massive"

BASE = 4 * 60
NMIN = 960
M_OPEN = 330
M_CLOSE = 720
TICKET = 10_000.0          # user's number: $10,000 per trade, every book
ACCOUNT = 100_000.0        # notional account per book
BOOKS = ("r4", "r15", "rl")


def mgrid(hh, mm=0):
    return hh * 60 + mm - BASE


def hhmm(k):
    k = int(k) + BASE
    return f"{k // 60:02d}:{k % 60:02d}"


def parse_hhmm(s):
    hh, mm = (int(x) for x in s.split(":"))
    return mgrid(hh, mm)


def now_et():
    return datetime.now(ET)


def now_min(dt=None):
    dt = dt or now_et()
    return dt.hour * 60 + dt.minute - BASE


_OFF = {}


def et_offset_min(date):
    """UTC->ET offset (minutes) at noon of `date` (-240 EDT / -300 EST)."""
    if date not in _OFF:
        d = datetime.strptime(date, "%Y-%m-%d").replace(hour=12, tzinfo=ET)
        _OFF[date] = int(d.utcoffset().total_seconds() // 60)
    return _OFF[date]


def utc_iso(date, k):
    """ISO UTC timestamp ('...Z') of grid minute k on `date`."""
    m = k + BASE - et_offset_min(date)
    return f"{date}T{m // 60:02d}:{m % 60:02d}:00Z"


# ------------------------------------------------------------------ bars
def read_bars_csv(path, date, upto=None):
    """(o, h, l, c, v) float64 arrays on the 960-minute grid, or None.

    Accepts both on-disk formats:
      RH (append_bars / p3_ingest):  begins_at,open,high,low,close,volume
                                     2026-09-18T11:00:00Z,...
      Massive (m1, m1c, m1w):        begins_at,Open,High,Low,Close,Volume
                                     2026-05-07 10:46:00+00:00,...
    Timestamps are UTC in both. `upto` keeps bars with index <= upto only
    (the live completed-bar rule). Duplicate minutes keep the last row."""
    p = Path(path)
    if not p.exists():
        return None
    off = et_offset_min(date)
    o = np.full(NMIN, np.nan)
    h = np.full(NMIN, np.nan)
    lo = np.full(NMIN, np.nan)
    c = np.full(NMIN, np.nan)
    v = np.zeros(NMIN)
    seen = False
    with open(p, newline="") as fh:
        rd = csv.reader(fh)
        hdr = next(rd, None)
        if hdr is None or (hdr and hdr[0].startswith("EMPTY")):
            return None
        for row in rd:
            if len(row) < 6:
                continue
            ts = row[0]
            if ts[:10] != date:
                continue
            try:
                k = int(ts[11:13]) * 60 + int(ts[14:16]) + off - BASE
            except ValueError:
                continue
            if not (0 <= k < NMIN) or (upto is not None and k > upto):
                continue
            try:
                o[k], h[k], lo[k], c[k] = (float(row[1]), float(row[2]),
                                           float(row[3]), float(row[4]))
                v[k] = float(row[5] or 0)
            except ValueError:
                continue
            seen = True
    return (o, h, lo, c, v) if seen else None


class LiveFeed:
    """Bars the session agent fetched from Robinhood, completed minutes
    only (index <= now-1)."""

    def __init__(self, date, now):
        self.date, self.now = date, now
        self._c = {}

    def bars(self, sym):
        if sym not in self._c:
            self._c[sym] = read_bars_csv(RH_BARS / f"{sym}_{self.date}.csv",
                                         self.date, upto=self.now - 1)
        return self._c[sym]


class CacheFeed(LiveFeed):
    """The historical minute caches standing in for the live feed (parity
    test). Search order m1w -> m1 -> m1c, same as the backtest builders."""

    DIRS = ("m1w", "m1", "m1c")

    def bars(self, sym):
        if sym not in self._c:
            out = None
            for d in self.DIRS:
                f = MASSIVE / d / f"{sym}_{self.date}.csv"
                if f.exists():
                    out = read_bars_csv(f, self.date, upto=self.now - 1)
                    break
            self._c[sym] = out
        return self._c[sym]


def ffill_last(c, k):
    """Last printed close at or before minute k (NaN if none)."""
    idx = np.flatnonzero(~np.isnan(c[:k + 1]))
    return float(c[idx[-1]]) if idx.size else float("nan")


# ------------------------------------------------------------------ io
def write_atomic(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str))
    os.replace(tmp, path)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def book_dir(book):
    d = DATA / "paper" / book
    d.mkdir(parents=True, exist_ok=True)
    return d


def quotes(date):
    return read_json(DATA / "paper" / f"quotes_{date}.json", {}) or {}


def ledger_path(date, ext="json"):
    return DATA / "paper_days" / f"{date}.3book.{ext}"


def load_tool_json(path):
    """A saved MCP tool result: the raw JSON, or a spilled-output file
    whose JSON may be wrapped ({"data": {"result": ...}} or a list of
    {"type": "text", "text": "<json>"} blocks)."""
    raw = Path(path).read_text(encoding="utf-8", errors="ignore").strip()
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        i = raw.find("{")
        d = json.loads(raw[i:]) if i >= 0 else {}
    if isinstance(d, list) and d and isinstance(d[0], dict) and "text" in d[0]:
        d = json.loads(d[0]["text"])
    return d


def scan_rows(d):
    """Rows of a run_scan result -> [{sym, cols{...}}]."""
    if isinstance(d, dict) and "data" in d:
        d = d["data"]
    if isinstance(d, dict) and "result" in d:
        d = d["result"]
    out = []
    for r in (d.get("results") or []) if isinstance(d, dict) else []:
        out.append({"sym": r.get("ticker") or r.get("columns", {}).get("Symbol"),
                    "cols": r.get("columns") or {}})
    return out


def fnum(x):
    try:
        v = float(x)
        return v if np.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


# ------------------------------------------------------------------ halal
def halal_tag(sym, date=None):
    """Halal verdict TAG (never a gate in PAPER-3BOOK): the fresh
    plan/live_halal.py verdict, cached per day in data/paper/halal_tags_{D}.json."""
    date = date or now_et().date().isoformat()
    f = DATA / "paper" / f"halal_tags_{date}.json"
    cache = read_json(f, {}) or {}
    if sym in cache:
        return cache[sym]
    try:
        out = subprocess.run([sys.executable, str(PLAN / "live_halal.py"), sym,
                              "--json"], capture_output=True, text=True,
                             timeout=180).stdout
        j = json.loads(out[out.find("{"):]) if "{" in out else {}
        j = j.get(sym, j) if isinstance(j, dict) else {}
        verdict = (j.get("verdict") or ("PASS" if j.get("halal") else
                                        "UNVERIFIED")).upper()
    except Exception as e:                          # noqa: BLE001
        verdict, j = "UNVERIFIED", {"error": str(e)}
    cache[sym] = {"verdict": verdict, "pass": verdict == "PASS"}
    write_atomic(f, cache)
    return cache[sym]


def emit(obj):
    """Print the machine-readable decision line the session agent parses."""
    print("P3 " + json.dumps(obj, default=str), flush=True)


if __name__ == "__main__":
    # python plan/p3_lib.py halal SYM   -> tag + cache (never a gate)
    if len(sys.argv) >= 3 and sys.argv[1] == "halal":
        emit(dict(halal=sys.argv[2].upper(),
                  **halal_tag(sys.argv[2].upper())))
