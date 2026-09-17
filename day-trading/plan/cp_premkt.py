"""CHAMPION-REPLAY part 3b: the PREMARKET-ONLY CROSSER census.

THE HOLE. Pool membership in every C31..C37 run is the grouped-daily
REGULAR-SESSION high >= +10% over prev close. The live Robinhood
scanner has no such rule: it lists whatever is Last > $2 and %Change >
10% at the moment you look, premarket included. So the pool contains
every premarket crosser that WENT ON to print +10% in the session and
none of the ones that faded before 09:30 -- which is exactly why a
premarket entry taken against that pool is survivorship-conditioned
(MX retraction #2).

This measures the missing set directly. `cp_fetch.py --job B` fetches
minute bars for the whole scannable market on sampled dates (clean
ticker, prev close >= $1.82 so a +10% cross prints >= $2, prior-60
median dollar volume >= $100k). Here each sampled date is scanned
minute by minute from 04:00 with the LIVE rule, and every name is
classified:

  RTH-CROSSER      crosses at or after 09:30 -> it is in the pool, the
                   causal universe already contains it
  PM-AND-RTH       crosses premarket AND again in the session -> in the
                   pool; a premarket entry on it is legitimate ONLY
                   because the session later confirmed it, which the
                   trader could not know
  PM-ONLY          crosses premarket and NEVER in the session -> the
                   missing set. Invisible to every backtest in this
                   repo, fully visible to the live scanner.

    python plan/cp_premkt.py --census
"""

import sys
from datetime import date as ddate, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_fetch                                             # noqa: E402
import cp_prior as P                                        # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
M1 = ROOT / "data/massive/m1"
M1C = ROOT / "data/massive/m1c"
ET = ZoneInfo("America/New_York")
GRID_START = 4 * 60
NMIN = 720
M_OPEN = 9 * 60 + 30 - GRID_START
M_1500 = 15 * 60 - GRID_START
CROSS = 1.10
MIN_PRICE = 2.0


def _off(date_str):
    d = ddate.fromisoformat(date_str)
    return int(datetime(d.year, d.month, d.day, 12, 0,
                        tzinfo=ET).utcoffset().total_seconds() // 60)


def read_bars(sym, date):
    """(o,h,l,c,v) on the 04:00-16:00 grid, NaN where nothing printed."""
    for base in (M1, M1C):
        f = base / f"{sym}_{date}.csv"
        if not f.exists():
            continue
        raw = f.read_text(errors="ignore")
        if raw.startswith("EMPTY"):
            return None
        off = _off(date)
        o = np.full(NMIN, np.nan)
        h = np.full(NMIN, np.nan)
        lo = np.full(NMIN, np.nan)
        c = np.full(NMIN, np.nan)
        v = np.zeros(NMIN)
        got = 0
        for ln in raw.splitlines()[1:]:
            try:
                ts, rest = ln.split(",", 1)
                m = int(ts[11:13]) * 60 + int(ts[14:16]) + off - GRID_START
                if m < 0 or m >= NMIN:
                    continue
                a, b, cc, d, e = rest.split(",")
                o[m] = float(a); h[m] = float(b); lo[m] = float(cc)
                c[m] = float(d); v[m] = float(e)
                got += 1
            except Exception:
                continue
        return (o, h, lo, c, v) if got else None
    return None


def classify(sym, date, pc):
    b = read_bars(sym, date)
    if b is None or pc <= 0:
        return None
    o, h, l, c, v = b
    thr = CROSS * pc
    pr = np.isfinite(c)
    hit = pr & (c >= thr) & (c >= MIN_PRICE)
    pm = np.where(hit[:M_OPEN])[0]
    rth = np.where(hit[M_OPEN:])[0]
    if len(pm) == 0 and len(rth) == 0:
        return None
    kind = ("PM-AND-RTH" if len(pm) and len(rth)
            else "PM-ONLY" if len(pm) else "RTH-CROSSER")
    out = dict(sym=sym, date=date, kind=kind, pc=float(pc))
    if len(pm):
        m0 = int(pm[0])
        out["pm_cross_min"] = m0
        out["pm_cross_px"] = float(c[m0])
        out["pm_dvol"] = float(np.nansum(np.nan_to_num(c[:M_OPEN])
                                         * v[:M_OPEN]))
        # what a live premarket entry at the next print would have done
        nxt = next((m for m in range(m0 + 1, NMIN) if pr[m]), None)
        if nxt is not None:
            e = float(o[nxt])
            seg = slice(nxt + 1, M_1500 + 1)
            hh = h[seg][np.isfinite(h[seg])]
            ll = l[seg][np.isfinite(l[seg])]
            cc = c[seg][np.isfinite(c[seg])]
            if e > 0 and len(cc):
                out["entry"] = e
                out["mfe"] = float(hh.max() / e - 1) if len(hh) else np.nan
                out["mae"] = float(ll.min() / e - 1) if len(ll) else np.nan
                out["to1500"] = float(cc[-1] / e - 1)
                out["to_open"] = (float(c[M_OPEN] / e - 1)
                                  if pr[M_OPEN] else np.nan)
    if len(rth):
        out["rth_cross_min"] = int(rth[0]) + M_OPEN
    return out


def census(ndates=16):
    """Only the sampled dates whose WHOLE candidate list is on disk are
    scored -- a partially fetched date would under-count the missing
    set, which is the one number this census exists to produce."""
    rows = []
    for date in cp_fetch.sample_dates(ndates):
        pr = P.load(date)
        if not pr:
            continue
        want = [r.get("T") for r in P.gd_rows(date)]
        miss = sum(1 for s in want
                   if cp_fetch.clean_ticker(s)
                   and (pr.get(s) or {}).get("prevclose", 0) >= 1.82
                   and (pr.get(s) or {}).get("dvol60", 0) >= 100_000
                   and not cp_fetch.have(s, date))
        if miss:
            print(f"  {date}: SKIPPED, {miss} names not fetched yet",
                  flush=True)
            continue
        n = {"RTH-CROSSER": 0, "PM-AND-RTH": 0, "PM-ONLY": 0}
        got = 0
        for r in P.gd_rows(date):
            s = r.get("T")
            if not cp_fetch.clean_ticker(s):
                continue
            e = pr.get(s)
            if not e or (e.get("prevclose") or 0) < 1.82:
                continue
            if (e.get("dvol60") or 0) < 100_000:
                continue
            got += 1
            o = classify(s, date, e["prevclose"])
            if o:
                n[o["kind"]] += 1
                rows.append(o)
        print(f"  {date}: scanned {got} names -> RTH {n['RTH-CROSSER']}, "
              f"PM+RTH {n['PM-AND-RTH']}, PM-ONLY {n['PM-ONLY']}",
              flush=True)
    return rows


def report(rows):
    import json
    kinds = {}
    for r in rows:
        kinds.setdefault(r["kind"], []).append(r)
    dates = sorted({r["date"] for r in rows})
    print(f"\n## Premarket census over {len(dates)} complete market days\n")
    print("| class | name-days | per day | share of the premarket "
          "scanner list |")
    print("|---|---:|---:|---:|")
    pm_tot = len(kinds.get("PM-ONLY", [])) + len(kinds.get("PM-AND-RTH", []))
    for k in ("RTH-CROSSER", "PM-AND-RTH", "PM-ONLY"):
        v = kinds.get(k, [])
        share = (f"{len(v)/pm_tot*100:.0f}%"
                 if k != "RTH-CROSSER" and pm_tot else "-")
        print(f"| {k} | {len(v)} | {len(v)/max(len(dates),1):.1f} | "
              f"{share} |")
    print("\n## What a live PREMARKET entry earns, by class\n")
    print("| class | n with a fill | median MFE to 15:00 | median MAE | "
          "median return to 15:00 | median return to the OPEN | "
          "mean return to 15:00 |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for k in ("PM-AND-RTH", "PM-ONLY"):
        v = [r for r in kinds.get(k, []) if "to1500" in r]
        if not v:
            continue
        f = lambda key: np.array([r[key] for r in v if np.isfinite(
            r.get(key, np.nan))])
        print(f"| {k} | {len(v)} | {np.median(f('mfe'))*100:+.1f}% | "
              f"{np.median(f('mae'))*100:+.1f}% | "
              f"{np.median(f('to1500'))*100:+.1f}% | "
              f"{np.median(f('to_open'))*100:+.1f}% | "
              f"{np.mean(f('to1500'))*100:+.1f}% |")
    (ROOT / "data/massive/cp/premkt_census.json").write_text(
        json.dumps(rows, default=float))


if __name__ == "__main__":
    if "--census" in sys.argv[1:]:
        a=sys.argv[1:]
        n=int(a[a.index("--ndates")+1]) if "--ndates" in a else 16
        report(census(n))
    else:
        print(__doc__)
