"""LEADS-TEST lead 3: measure the panel's survivorship gap for LARGE caps on
many dates, cheaply. The panel (cp_panel) only holds names whose regular-
session HIGH reached +10%. The missing large caps are names that printed +10%
premarket but never reached +10% in the session. Candidates per date:
  guarded split-safe mcap >= $2B (lt_lead3.mcap_check, prev close >= $5,
  dvol60/mcap >= 5e-4), dvol60 >= $5M, NOT in the panel pool, grouped-daily
  open >= 1.03 x prev close (fetch prefilter; the census shows ~92% of liquid
  post-07:00 crossers open >= +3%; the rest is reported as residual bias).
Fetch 04:00-10:31 minute bars (adjusted=true) for those, slow and polite
(the shared key is rate-limited). Output data/research_oct/pmgap/{date}.json
    python plan/lt_pmgap_fetch.py [--ndates 120]
"""
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

P_ = Path(__file__).resolve().parent
sys.path.insert(0, str(P_))
ROOT = P_.parent
sys.path.insert(0, str(ROOT.parent))
from shared import massive                                   # noqa: E402
import cp_prior as PR                                        # noqa: E402
import cp_lib as L                                           # noqa: E402
import lt_lead3 as X                                         # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = ROOT / "data/research_oct/pmgap"
LOG = ROOT / "data/research_oct/lt_pmgap.log"


def log(m):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(time.strftime("%H:%M:%S ") + m + "\n")


def cands(date):
    pr = PR.load(date)
    day = L.load_day(date)
    pool = set(day.syms) if day is not None else set()
    out = []
    for r in PR.gd_rows(date):
        s = r.get("T")
        if not s or s in pool or not X.TICK_OK(s):
            continue
        e = pr.get(s) or {}
        pc, dv = e.get("prevclose") or 0, e.get("dvol60") or 0
        if pc < 5 or dv < 5e6 or (r.get("o") or 0) < 1.03 * pc:
            continue
        t = X.TYPES.get(s)
        if isinstance(t, str) and t not in ("CS", "ADRC"):
            continue
        m, ok, src = X.mcap_check(s, date, pc)
        if ok != "ok" or m is None or m < 2e9 or m > 5e12 or dv / m < 5e-4:
            continue
        out.append((s, pc, m, src))
    return out


def fetch(sym, date, key):
    d = datetime.fromisoformat(date)
    f = int(datetime(d.year, d.month, d.day, 4, 0, tzinfo=ET).timestamp() * 1000)
    t = int(datetime(d.year, d.month, d.day, 10, 31, tzinfo=ET).timestamp() * 1000)
    u = (f"{massive.BASE}/v2/aggs/ticker/{sym}/range/1/minute/{f}/{t}"
         f"?adjusted=true&sort=asc&limit=50000&apiKey={key}")
    for a in range(40):
        try:
            with urllib.request.urlopen(u, timeout=40) as r:
                j = json.load(r)
            d0 = datetime(d.year, d.month, d.day, 4, 0, tzinfo=ET).timestamp()
            return [[int((b["t"] / 1000 - d0) // 60), b["o"], b["h"], b["l"], b["c"], b.get("v", 0)]
                    for b in (j.get("results") or [])]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(min(20, 2 + a))
                continue
            return None
        except Exception:
            time.sleep(3)
    return None


def main():
    a = sys.argv[1:]
    nd = int(a[a.index("--ndates") + 1]) if "--ndates" in a else 120
    ds = [d for d in L.panel_dates() if d not in X.CENSUS]
    step = len(ds) / nd
    pick = [ds[int(i * step)] for i in range(nd)]
    # visit spread-out dates first so a partial run covers the whole window
    pick = [pick[i] for i in sorted(range(len(pick)), key=lambda i: (i % 6, i))]
    OUT.mkdir(parents=True, exist_ok=True)
    key = massive._key()
    log(f"start {len(pick)} dates")
    for n, d in enumerate(pick):
        f = OUT / f"{d}.json"
        if f.exists():
            continue
        cs = cands(d)
        res = {}
        for s, pc, m, src in cs:
            res[s] = dict(pc=pc, mcap=m, src=src, bars=fetch(s, d, key))
        f.write_text(json.dumps(res))
        log(f"{n+1}/{len(pick)} {d} cand {len(cs)} got {sum(v['bars'] is not None for v in res.values())}")
    log("DONE")


if __name__ == "__main__":
    main()
