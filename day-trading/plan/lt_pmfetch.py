"""LEADS-TEST lead 3: whole-market (liquid) premarket minute bars on >=120 dates.

Universe per date D (all PRIOR info except the fetch prefilter, see below):
  clean ticker [A-Z]{1,5}; dvol60 (median c*v over the prior 60 grouped-daily
  rows) >= $5M (the hygiene liquidity floor, causal).
FETCH PREFILTER (look-ahead, measured): grouped-daily OPEN(D) / prevclose >= 1.02.
  A name whose premarket printed +10% after 07:00 almost always opens >= +2%;
  the census days (whole market, no prefilter) measure exactly what this drops
  (lt_lead3.py reports the bias). Names that never confirm +10% in the regular
  session ARE included (no survivorship on the RTH cross).

Bars: adjusted=true, window D-1 15:00 ET .. D 10:31 ET, so the previous close is
taken from the SAME adjusted series as the premarket prints (split-safe gap).

Output: data/research_oct/pm/{D}.pkl.gz  {sym: dict(t=minute-of-day ET array
  relative to D 00:00 (negative = D-1), o,h,l,c,v)} ; resumable per date.
Key from Credential Manager via shared.massive (never printed).
    python plan/lt_pmfetch.py [--workers 6]
"""
import gzip
import json
import pickle
import re
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent))
from shared import massive                                   # noqa: E402

ET = ZoneInfo("America/New_York")
GD = ROOT / "data/massive/gd"
OUT = ROOT / "data/research_oct/pm"
LOG = ROOT / "data/research_oct/lt_pmfetch.log"
TICK = re.compile(r"[A-Z]{1,5}")


def gd_dates():
    return sorted(p.name.split(".")[0] for p in GD.glob("*.json.gz"))


def gd_rows(d):
    with gzip.open(GD / f"{d}.json.gz", "rt", encoding="utf-8") as fh:
        return json.load(fh)


def pick_dates():
    ds = gd_dates()
    y1 = [d for d in ds if "2024-10-22" <= d <= "2025-07-31"]
    y2 = [d for d in ds if "2025-08-01" <= d <= "2026-07-31"]
    oos = [d for d in ds if d >= "2026-08-01"]

    def even(lst, n):
        if len(lst) <= n:
            return list(lst)
        step = len(lst) / n
        return [lst[int(i * step)] for i in range(n)]
    a, b, c = even(y1, 40), even(y2, 40), even(oos, 40)
    out = []
    for k in range(max(len(a), len(b), len(c))):     # interleave
        for lst in (c, a, b):
            if k < len(lst):
                out.append(lst[k])
    return out


def prior_ctx(date, ds, cache={}):
    """dvol60 and prevclose from the 60 grouped-daily rows before `date`."""
    k = ds.index(date)
    hist = {}
    for d in ds[max(0, k - 60):k]:
        if d not in cache:
            cache[d] = {r["T"]: (r.get("c") or 0.0, (r.get("c") or 0.0) * (r.get("v") or 0.0))
                        for r in gd_rows(d) if r.get("T")}
        for s, (c, dv) in cache[d].items():
            hist.setdefault(s, []).append((c, dv))
    if len(cache) > 80:
        for d in sorted(cache)[:20]:
            cache.pop(d, None)
    return {s: (statistics.median(x[1] for x in h), h[-1][0])
            for s, h in hist.items() if len(h) >= 20}


def candidates(date, ds):
    ctx = prior_ctx(date, ds)
    rows = {r["T"]: r for r in gd_rows(date) if r.get("T")}
    out = []
    for s, (dv60, pc) in ctx.items():
        if not TICK.fullmatch(s) or dv60 < 5e6 or pc <= 0:
            continue
        r = rows.get(s)
        if not r or (r.get("o") or 0) < 1.02 * pc:
            continue
        out.append(s)
    return sorted(out), ds[ds.index(date) - 1]


_lock = threading.Lock()
ST = {"429": 0, "ok": 0, "empty": 0, "fail": 0}


def fetch(sym, prev, date, key):
    p = datetime.fromisoformat(prev)
    d = datetime.fromisoformat(date)
    f = int(datetime(p.year, p.month, p.day, 15, 0, tzinfo=ET).timestamp() * 1000)
    t = int(datetime(d.year, d.month, d.day, 10, 31, tzinfo=ET).timestamp() * 1000)
    u = (f"{massive.BASE}/v2/aggs/ticker/{sym}/range/1/minute/{f}/{t}"
         f"?adjusted=true&sort=asc&limit=50000&apiKey={key}")
    for a in range(12):
        try:
            with urllib.request.urlopen(u, timeout=40) as r:
                j = json.load(r)
            res = j.get("results") or []
            d0 = datetime(d.year, d.month, d.day, tzinfo=ET).timestamp()
            tt, o, h, lo, c, v = [], [], [], [], [], []
            for b in res:
                tt.append(int((b["t"] / 1000 - d0) // 60))
                o.append(b["o"]); h.append(b["h"]); lo.append(b["l"])
                c.append(b["c"]); v.append(b.get("v", 0.0))
            with _lock:
                ST["ok" if res else "empty"] += 1
                if (ST["ok"] + ST["empty"]) % 100 == 0:
                    log(f"  calls {ST}")
            return sym, dict(t=tt, o=o, h=h, l=lo, c=c, v=v)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                with _lock:
                    ST["429"] += 1
                time.sleep(min(30, 1.5 * (a + 1)))
                continue
            if e.code in (401, 403, 404):
                break
            time.sleep(2)
        except Exception:
            time.sleep(2)
    with _lock:
        ST["fail"] += 1
    return sym, None


def log(msg):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(time.strftime("%H:%M:%S ") + msg + "\n")


def main():
    a = sys.argv[1:]
    workers = int(a[a.index("--workers") + 1]) if "--workers" in a else 6
    OUT.mkdir(parents=True, exist_ok=True)
    ds = gd_dates()
    dates = pick_dates()
    log(f"start {len(dates)} dates workers={workers}")
    key = massive._key()
    t0 = time.time()
    for n, date in enumerate(dates):
        f = OUT / f"{date}.pkl.gz"
        if f.exists():
            continue
        syms, prev = candidates(date, ds)
        res = {}
        with ThreadPoolExecutor(workers) as ex:
            for s, b in ex.map(lambda s: fetch(s, prev, date, key), syms):
                if b is not None:
                    res[s] = b
        tmp = f.with_suffix(".tmp")
        with gzip.open(tmp, "wb", compresslevel=5) as fh:
            pickle.dump(dict(date=date, prev=prev, syms=syms, bars=res), fh)
        tmp.replace(f)
        log(f"{n+1}/{len(dates)} {date} cand={len(syms)} got={len(res)} "
            f"{ST} {round(time.time()-t0)}s")
    log("DONE")


if __name__ == "__main__":
    main()
