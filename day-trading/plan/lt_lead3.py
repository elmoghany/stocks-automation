"""LEADS-TEST lead 3: large-cap (>= $2B) first +10% premarket close 07:00-09:29,
buy the next print, sell 10:00.

DATA (no new bars could be fetched: the Polygon key answered 429 "exceeded the
maximum requests per minute" to ~90% of calls all session, see LEADS-TEST.md):
  * 12 CENSUS dates: whole scannable market in data/massive/m1c (+ m1), i.e.
    every name with prev close >= $1.82 and dvol60 >= $100k -> NO survivorship
    (names that never confirm +10% in the regular session are included).
  * the other 454 panel dates: data/massive/cp_panel = gapper pool (RTH high
    >= +10%) -> SURVIVORSHIP-CONDITIONED; reported separately, with the bias
    measured on the census dates (panel subset vs whole market, same days).
MARKET CAP (split-safe, point in time):
  shares = data/pt_shares/{sym}_{D}.json (read for date D = what a live
  scanner had); fallback present-day rh_fundamentals shares (flagged).
  pc = previous close as of D (panel pool record / grouped-daily as-of).
  mcap = shares x pc.  SPLIT CHECK (data/research_oct/splits.json): if the
  symbol has any split executed in [D-120d, today], mcap is recomputed under
  the alternative adjustment (pc x cumulative split factor after D, and
  shares / factor) and the record is REJECTED unless every version agrees on
  the >= $2B side. Also rejected: type not CS/ADRC (ticker_types.json),
  first-bar open / pc outside [0.5, 2] (pool hygiene), pc*shares undefined.
FEATURES at the cross minute t (bars <= t only): dvol60, spread half
  max(CS,AR)/2 on [t-29, t], sigma1 (RMS 1-min log return 04:00..t).
FILLS: entry = OPEN of the next printed bar after t; exits = OPEN of the first
  print at/after 09:30 / 10:00 / 10:30; "stack" = 5% close-target / 10% trail /
  bearish>=1% (next open) capped at the 10:00 exit.
    python plan/lt_lead3.py
"""
import json
import sys
from datetime import date as ddate, timedelta
from pathlib import Path

import numpy as np

P_ = Path(__file__).resolve().parent
sys.path.insert(0, str(P_))
import cp_lib as L                                          # noqa: E402
import cp_prior as PR                                       # noqa: E402
import cp_premkt as PM                                      # noqa: E402
import cp_cost as C                                         # noqa: E402
import cp_sim as S                                          # noqa: E402
import lt_lib as LL                                         # noqa: E402

ROOT = P_.parent
CENSUS = ['2024-10-22', '2024-12-13', '2025-02-10', '2025-04-03', '2025-05-28',
          '2025-07-22', '2025-09-12', '2025-11-04', '2025-12-29', '2026-02-23',
          '2026-04-16', '2026-06-09']
M700, M930, M1000, M1030 = 180, 330, 360, 390
CEN_SYMS = {}
for _r in json.loads((ROOT / "data/massive/cp/premkt_census.json").read_text()):
    if _r["kind"] != "RTH-CROSSER":
        CEN_SYMS.setdefault(_r["date"], set()).add(_r["sym"])
TYPES = json.loads((ROOT / "data/massive/ticker_types.json").read_text())
FUND = json.loads((ROOT / "data/rh_fundamentals.json").read_text())
SPL = {}
for r in json.loads((ROOT / "data/research_oct/splits.json").read_text()):
    if r.get("split_from") and r.get("split_to"):
        SPL.setdefault(r["ticker"], []).append(
            (r["execution_date"], r["split_to"] / r["split_from"]))


HU = json.loads((ROOT / "data/halal_universe.json").read_text())
NOW_D = "2026-09-16"          # date of the present-day mcap snapshot (approx.)
_NOWPX = None


def now_px(sym):
    """unadjusted close on NOW_D from grouped daily (fetched that day)."""
    global _NOWPX
    if _NOWPX is None:
        _NOWPX = {r["T"]: r.get("c") for r in PR.gd_rows(NOW_D) if r.get("T")}
    return _NOWPX.get(sym)


def present_mcap(sym):
    v = (HU.get(sym) or {}).get("mcap")
    if not v:
        v = (FUND.get(sym) or {}).get("market_cap")
    return float(v) if v else None


def TICK_OK(s):
    import re
    return re.fullmatch(r"[A-Z]{1,5}", s) is not None


def pt_shares(sym, d):
    f = ROOT / f"data/pt_shares/{sym}_{d}.json"
    if f.exists():
        try:
            return float(json.loads(f.read_text())), "pit"
        except Exception:
            pass
    e = FUND.get(sym) or {}
    v = e.get("shares_outstanding")
    return (float(v), "present") if v else (None, None)


def mcap_check(sym, d, pc):
    sh, src = pt_shares(sym, d)
    if (not sh or src == "present") and pc and pc > 0:
        # fallback: present-day mcap scaled by price, split-corrected:
        # shares_D = (mcap_now / px_now) / F, F = prod(to/from) of splits in (D, now]
        mn, pn = present_mcap(sym), now_px(sym)
        if mn and pn:
            F = 1.0
            for x, f in SPL.get(sym, []):
                if d < x <= NOW_D:
                    F *= f
            sh, src = (mn / pn) / F, "present-scaled"
    if not sh or not pc or pc <= 0:
        return None, "no-shares", src
    m = sh * pc
    lo = (ddate.fromisoformat(d) - timedelta(days=120)).isoformat()
    sp = [(x, f) for x, f in SPL.get(sym, []) if x >= lo]
    if sp:
        fac = 1.0
        for x, f in sp:
            if x > d:
                fac *= f          # shares multiply by split_to/split_from
        alts = [m, m * fac, m / fac, sh * pc * (1 / fac if fac else 1)]
        for x, f in sp:
            alts += [m * f, m / f]
        side = {a >= 2e9 for a in alts}
        if len(side) > 1:
            return m, "split-ambiguous", src
    return m, "ok", src


def half(o, h, l, c, m_end, win=30):
    a, e = max(0, m_end - win + 1), m_end + 1
    sel = ~np.isnan(c[a:e])
    cs, ar = C._cs_ar(np.where(sel, o[a:e], np.nan), np.where(sel, h[a:e], np.nan),
                      np.where(sel, l[a:e], np.nan), np.where(sel, c[a:e], np.nan))
    vals = [x for x in (cs, ar) if x is not None and np.isfinite(x)]
    return max(max(vals) / 2.0, 1.0) if vals else 10.0


def sig1(c, t):
    r = np.diff(np.log(c[:t + 1]))
    ok = ~np.isnan(r)
    return float(np.sqrt(np.mean(r[ok] ** 2))) if ok.sum() > 1 else np.nan


class One:
    def __init__(self, o, h, l, c):
        self.o, self.h, self.l, self.c = o[None], h[None], l[None], c[None]
        self.printed = ~np.isnan(self.c)


def first_print(c, m0, m1=None):
    m1 = m1 or len(c) - 1
    for m in range(m0, m1 + 1):
        if not np.isnan(c[m]):
            return m
    return None


def stack_exit(o, h, l, c, em, entry, cap):
    peak, pend = h[em], None
    one = One(o, h, l, c)
    for m in range(em + 1, cap):
        if np.isnan(c[m]):
            continue
        if pend:
            return m, float(o[m]), pend
        lvl = peak * 0.9
        if l[m] <= lvl:
            return m, float(min(max(min(lvl, o[m]), l[m]), h[m])), "trail"
        peak = max(peak, h[m])
        if c[m] >= entry * 1.05:
            pend = "target"
        elif c[m] >= entry * 1.01 and S._bearish(one, 0, m):
            pend = "bearish"
    m = first_print(c, cap)
    return (m, float(o[m]), "time") if m is not None else (None, None, None)


def events(date, census):
    pr = PR.load(date)
    day = L.load_day(date)
    names = {}
    if day is not None:
        for i, s in enumerate(day.syms):
            names[s] = (float(day.pc[i]), day.o[i], day.h[i], day.l[i], day.c[i], day.v[i], True)
    if census:
        # the census already scanned the whole m1c market minute by minute
        # with the live rule; every premarket +10% closer is listed there
        for s in CEN_SYMS.get(date, ()):
            if s in names or s not in pr:
                continue
            b = PM.read_bars(s, date)
            if b is None:
                continue
            names[s] = (pr[s]["prevclose"],) + tuple(b) + (False,)
    out = []
    for s, (pc, o, h, l, c, v, inpool) in names.items():
        if not pc or pc <= 0:
            continue
        pre = c[:M930]
        hit = np.where(~np.isnan(pre) & (pre >= 1.10 * pc) & (pre >= 2.0))[0]
        if not len(hit):
            continue
        t = int(hit[0])
        fp = first_print(c, 0)
        typ = TYPES.get(s)
        pool_ok = (not isinstance(typ, str) or typ in ("CS", "ADRC", "?")) and \
            fp is not None and 0.5 <= o[fp] / pc <= 2.0
        rec = dict(date=date, sym=s, t=t, pc=pc, inpool=inpool, census=census,
                   pool_ok=bool(pool_ok), type=typ if isinstance(typ, str) else None)
        e = pr.get(s) or {}
        rec["dv60"] = e.get("dvol60") or 0.0
        m, why, src = mcap_check(s, date, pc)
        rec.update(mcap=m, mcap_ok=why, sh_src=src)
        # RTH confirm (never-confirmers included; flag only)
        rc = c[M930:]
        rec["rth_confirm"] = bool(np.any(~np.isnan(rc) & (rc >= 1.10 * pc)))
        if t < M700:
            rec["early"] = True
            out.append(rec)
            continue
        rec["early"] = False
        em = first_print(c, t + 1, M930)
        if em is None:
            continue
        ep = float(o[em])
        rec.update(em=em, ep=ep, half=half(o, h, l, c, t), sig=sig1(c, t),
                   h_e=half(o, h, l, c, em - 1))
        for nm, mm in (("x0930", M930), ("x1000", M1000), ("x1030", M1030)):
            xm = first_print(c, mm)
            rec[nm] = float(o[xm]) / ep - 1 if xm is not None else None
            if nm == "x1000" and xm is not None:
                rec["h_x"] = half(o, h, l, c, xm - 1)
        xm, xp, why = stack_exit(o, h, l, c, em, ep, M1000)
        rec["xstack"] = xp / ep - 1 if xp else None
        rec["stack_why"] = why
        out.append(rec)
    return out


def main():
    dates = sorted(set(L.panel_dates()))
    allev = []
    for n, d in enumerate(dates):
        allev += events(d, d in CENSUS)
        if (n + 1) % 100 == 0:
            print(n + 1, len(allev), flush=True)
    (ROOT / "data/research_oct/lt_lead3_events.json").write_text(json.dumps(allev, default=float))
    print("events", len(allev))


if __name__ == "__main__":
    main()
