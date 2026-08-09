"""X100 campaign: 100 single-change experiments vs B0 (=AX20 champion)
toward 5x annual profit. Hard constraints in every experiment: max $15k
at risk at any moment, all positions closed same day, point-in-time
halal, window 7AM-noon ET (X064 exits-to-1PM requires user sign-off).

B0: gappers2, walk-8 by gain_pct, calm-gap<=20, halal_pt, sim(trail 20,
stop 8, ORB15, patterns, vol_frac 0.10/5min, scale-out 1/3@+25%).

Usage:
  python plan/penny_x100.py --ids X001,X002        run specific ids
  python plan/penny_x100.py --cache-only           all C/C* experiments
  python plan/penny_x100.py --fetch                allow lazy API fetches
  python plan/penny_x100.py --report               print sorted table

Results: data/massive/x100_results.json (resumable, keyed id|label),
per-day dumps data/massive/x100_days_{id}_{label}.json, and X-RESULTS.md.
"""

import importlib.util
import json
import random
import sys
from datetime import time as dtime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

_spec = importlib.util.spec_from_file_location(
    "axb", ROOT / "plan" / "penny_ax11b_massive.py")
axb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(axb)
ps = axb.ps

M1 = ROOT / "data" / "massive" / "m1"

_CAUSAL_RVOL = [None]


def causal_rvol_table():
    """Lazy-load the causal 30-day rvol table (plan/causal_rvol_build.py).

    Keyed "SYM|YYYY-MM-DD" -> {"0730": ratio, ..., "avg30": shares}.
    Loud failure if a spec asks for the gate and the table is absent --
    silently trading everything would look like a passing experiment."""
    if _CAUSAL_RVOL[0] is None:
        f = ROOT / "data" / "massive" / "causal_rvol.json"
        if not f.exists():
            raise RuntimeError(
                "ERROR: causal_rvol.json missing -- a spec requested "
                "causal_rvol but the table was never built. Run "
                "plan/causal_rvol_build.py. Refusing to run ungated.")
        _CAUSAL_RVOL[0] = json.loads(f.read_text())
    return _CAUSAL_RVOL[0]


_EFLAGS = [None]


def earnings_flags():
    """Z4xx: {"SYM|DATE": {"streak": n}} -- report in the prior 24h.
    Loud failure if requested before build_earnings_flags.py ran."""
    if _EFLAGS[0] is None:
        f = ROOT / "data" / "earnings_flags.json"
        if not f.exists():
            raise RuntimeError("ERROR: earnings_flags.json missing -- run "
                               "plan/build_earnings_flags.py first.")
        _EFLAGS[0] = json.loads(f.read_text())
    return _EFLAGS[0]


RES_F = ROOT / "data" / "massive" / "x100_results.json"
MD_F = ROOT / "X-RESULTS.md"
FETCH = "--fetch" in sys.argv
W_START, W_END = dtime(7, 0), dtime(12, 0)

BASE_SIM = dict(verbose=False, buy_set=None, vol_confirm=False,
                trail_pct=20, stop_pct=8, budget=15000, orb=True,
                orb_bars=15, max_vol_frac=0.10, vol_frac_window=5,
                scale_out_at=25.0)


# ----------------------------------------------------------------- data
_DF_CACHE = {}


def get_lazy(sym, date):
    key = (sym, date)
    if key in _DF_CACHE:
        return _DF_CACHE[key]
    df = _get_lazy_uncached(sym, date)
    _DF_CACHE[key] = df
    return df


def _get_lazy_uncached(sym, date):
    f = M1 / f"{sym}_{date}.csv"
    if FETCH and not f.exists():
        from shared import massive
        try:
            df = massive.minute_bars(sym, date)
        except Exception as e:
            print(f"  !! m1 {sym} {date}: {e}", flush=True)
            return None
        if df is None or df.empty:
            f.write_text("EMPTY")
        else:
            out = df.reset_index()
            out["begins_at"] = out["begins_at"].dt.tz_convert("UTC")
            out.to_csv(f, index=False)
    return axb.get(sym, date)


def premkt_metrics(df, prev_close):
    """Metrics computable from <=7AM bars only."""
    pre = df[df.index.time < W_START]
    if len(pre) == 0 or not prev_close:
        return None
    hi = float(pre["High"].max())
    last = float(pre["Close"].iloc[-1])
    dvol = float((pre["Close"] * pre["Volume"]).sum())
    pm_p = None
    if len(pre) >= 5:
        cd = ps.Candles(pre)
        pm_p = cd.pressure(cd.n - 1, 30, 20_000)
    return {"pm_gain": (last / prev_close - 1) * 100,
            "pm_high_gain": (hi / prev_close - 1) * 100,
            "pm_dvol": dvol,
            "pm_pressure": pm_p,
            "coil": last / hi if hi > 0 else 0}


def pm_pressure_for(spec, df, prev_close, sym, date):
    """pm_pressure with control variants (X229 shuffle / X230 lag)."""
    mode = spec.get("gap_pressure_control")
    if mode == "shuffle":
        return random.Random(f"x229-{sym}-{date}").uniform(-1, 1)
    pre = df[df.index.time < W_START]
    if mode == "lag":
        pre = pre.iloc[:-30] if len(pre) > 35 else pre.iloc[:5]
    if len(pre) < 5 or not prev_close:
        return None
    cd = ps.Candles(pre)
    return cd.pressure(cd.n - 1, 30, 20_000)


def load_by_day(label, min_hist, pool=None):
    """pool=None -> gappers2 (rvol>=5 discovery, the historical default).
    pool="novol" -> gappers_novol (same rules, NO volume filter) -- the
    universe as live paper trading actually sees it, where full-day
    volume is unknowable at decision time."""
    name = f"gappers_{pool}_{label}.json" if pool else f"gappers2_{label}.json"
    gap = json.loads((ROOT / f"data/massive/{name}").read_text())
    by_day = {}
    for c in gap:
        if c.get("hist_n", 99) < min_hist:
            continue
        by_day.setdefault(c["date"], []).append(c)
    return by_day


# ---------------------------------------------------------------- ranks
def rank_pool(cs, spec, date, dfs):
    """Order the walk pool. Pool = top-walk by gain_pct (B0 pool, kept
    fixed for comparability); rank mode reorders it."""
    walk = spec.get("walk", 8)
    pool = sorted(cs, key=lambda x: -x["gain_pct"])
    band = spec.get("band")
    if band:
        pool = [c for c in pool if band[0] <= c["gain_pct"] < band[1]]
    if spec.get("pm_dvol_min") or spec.get("rank", "gain") in (
            "pm_gain", "pm_dvol", "zblend", "coil", "pm_high_gain",
            "turnover", "random", "lag", "pm_pressure", "cross_time",
            "coil_press", "zcoilpress", "coil_quiet", "coil_liquid",
            "coil_pmgain", "coil_cont"):
        if spec.get("causal_cut"):
            # Z-series (user 2026-08-08: "only using current signal
            # instead of full day signal"): the top-walk cut itself must
            # not use full-day gain. Consider EVERY candidate with
            # cached bars, rank causally, cut top-walk AFTER the sort.
            # Residual bias disclosed: bar coverage was fetched by
            # full-day-gain depth (walk-16 backfill widens it).
            pool = [c for c in pool
                    if (M1 / f"{c['symbol']}_{date}.csv").exists()]
        else:
            pool = pool[:walk]
        mets = {}
        for c in pool:
            df = dfs.get(c["symbol"])
            if df is None:
                df = get_lazy(c["symbol"], date)
                dfs[c["symbol"]] = df
            m = premkt_metrics(df, c["prev_close"]) if df is not None else None
            mets[c["symbol"]] = m
        if spec.get("pm_dvol_min"):
            pool = [c for c in pool
                    if mets.get(c["symbol"])
                    and mets[c["symbol"]]["pm_dvol"] >= spec["pm_dvol_min"]]
        mode = spec.get("rank", "gain")
        if mode == "pm_gain":
            pool.sort(key=lambda c: -(mets.get(c["symbol"]) or
                                      {"pm_gain": -99})["pm_gain"])
        elif mode == "pm_high_gain":
            pool.sort(key=lambda c: -(mets.get(c["symbol"]) or
                                      {"pm_high_gain": -99})["pm_high_gain"])
        elif mode == "pm_dvol":
            pool.sort(key=lambda c: -(mets.get(c["symbol"]) or
                                      {"pm_dvol": -1})["pm_dvol"])
        elif mode == "coil":
            # coiled (7AM close within 5% of premarket high) first,
            # then by gain within each group
            pool.sort(key=lambda c: -(
                ((mets.get(c["symbol"]) or {"coil": 0})["coil"] >= 0.95)
                * 1000 + c["gain_pct"]))
        elif mode == "zblend":
            pms = [(mets.get(c["symbol"]) or {"pm_gain": 0})["pm_gain"]
                   for c in pool] or [1]
            rvs = [c["rvol"] for c in pool] or [1]
            def z(v, arr):
                mu = sum(arr) / len(arr)
                sd = (sum((x - mu) ** 2 for x in arr) / len(arr)) ** .5 or 1
                return (v - mu) / sd
            keys = {c["symbol"]: -(
                z((mets.get(c["symbol"]) or {"pm_gain": 0})["pm_gain"], pms)
                + z(c["rvol"], rvs)) for c in pool}
            pool.sort(key=lambda c: keys[c["symbol"]])
        elif mode == "turnover":
            def turn(c):
                m = mets.get(c["symbol"])
                sh = axb.shares_asof(c["symbol"], date) if m else None
                mc = (sh or 0) * (c["prev_close"] or 0)
                return m["pm_dvol"] / mc if m and mc > 0 else -1
            pool.sort(key=lambda c: -turn(c))
        elif mode == "random":
            rnd = random.Random(f"x094-{date}")
            rnd.shuffle(pool)
        elif mode == "lag":
            prev = spec["_lagmap"]
            pool.sort(key=lambda c: -prev.get((c["symbol"], date), 0))
        elif mode == "pm_pressure":
            # part-day signal: premarket buy-pressure (<=7AM bars)
            pool.sort(key=lambda c: -((mets.get(c["symbol"]) or {})
                                      .get("pm_pressure") or -99))
        elif mode == "coil_press":
            # phase-2 blend: coiled names first (7AM close within 5% of
            # the premarket high), pm_pressure orders within each group
            pool.sort(key=lambda c: -(
                (((mets.get(c["symbol"]) or {}).get("coil") or 0) >= 0.95)
                * 1000 + (((mets.get(c["symbol"]) or {})
                           .get("pm_pressure") or -1) + 1) * 100))
        elif mode == "zcoilpress":
            # phase-2 blend: z(coil) + z(pm_pressure), continuous
            cs_ = [((mets.get(c["symbol"]) or {}).get("coil") or 0)
                   for c in pool] or [1]
            ps_ = [((mets.get(c["symbol"]) or {}).get("pm_pressure") or 0)
                   for c in pool] or [1]
            def _z(v, arr):
                mu = sum(arr) / len(arr)
                sd = (sum((x - mu) ** 2 for x in arr) / len(arr)) ** .5 or 1
                return (v - mu) / sd
            keys = {c["symbol"]: -(
                _z(((mets.get(c["symbol"]) or {}).get("coil") or 0), cs_)
                + _z(((mets.get(c["symbol"]) or {}).get("pm_pressure") or 0),
                     ps_)) for c in pool}
            pool.sort(key=lambda c: keys[c["symbol"]])
        elif mode == "coil_pmgain":
            # coil group + PREMARKET gain order (causal fix for the
            # gain_pct tiebreak leak found 2026-08-09 via Z404/Z405)
            pool.sort(key=lambda c: (
                -((((mets.get(c["symbol"]) or {}).get("coil") or 0) >= 0.95)
                  * 1),
                -((mets.get(c["symbol"]) or {}).get("pm_gain") or -99)))
        elif mode == "coil_cont":
            # continuous coil: no group, no tiebreak -- pure signal
            pool.sort(key=lambda c: -((mets.get(c["symbol"]) or {})
                                      .get("coil") or 0))
        elif mode == "coil_quiet":
            # TWLO lesson (Z404): coiled names whose premarket was QUIET
            # -- price pinned at the high on low dollar volume reads as
            # buyers waiting, not churn. Coil group first, then
            # ASCENDING premarket dollar volume.
            pool.sort(key=lambda c: (
                -((((mets.get(c["symbol"]) or {}).get("coil") or 0) >= 0.95)
                  * 1), (mets.get(c["symbol"]) or {}).get("pm_dvol") or 0))
        elif mode == "coil_liquid":
            # TWLO lesson (Z405): among coiled names prefer the DEEPEST
            # books (highest historical avg dollar volume -- causal,
            # trailing 50d). TWLO's fills beat the model by 1.43%.
            def _adv(c):
                av = (c.get("volume") / c["rvol"]) if c.get("rvol") else 0
                return av * (c.get("prev_close") or 0)
            pool.sort(key=lambda c: (
                -((((mets.get(c["symbol"]) or {}).get("coil") or 0) >= 0.95)
                  * 1), -_adv(c)))
        elif mode == "cross_time":
            # part-day signal: the EARLIER a name first touched +10%,
            # the higher it ranks (never-crossed sinks to the bottom;
            # the gain_causal gate drops those later anyway)
            def xt(c):
                df = dfs.get(c["symbol"])
                pc = c.get("prev_close") or 0
                if df is None or pc <= 0:
                    return 1e9
                thr = 1.10 * pc
                for ts, bh in zip(df.index, df["High"].values):
                    if ts.time() > dtime(12, 0):
                        break
                    if float(bh) >= thr:
                        return ts.hour * 60 + ts.minute
                return 1e9
            pool.sort(key=xt)
        if spec.get("earnings_rank"):
            # Z401: earnings-day names first, prior order within groups
            ef = earnings_flags()
            pool.sort(key=lambda c, _p={id(c): i for i, c in
                                        enumerate(pool)}: (
                0 if f"{c['symbol']}|{date}" in ef else 1, _p[id(c)]))
        if spec.get("causal_cut"):
            pool = pool[:walk]
        return pool
    if spec.get("rank") == "rvol":
        pool = pool[:walk]
        pool.sort(key=lambda c: -c["rvol"])
        return pool
    if spec.get("rank") == "day2":
        # X342/X343: yesterday's strong pick, if in today's pool, first
        pool = pool[:walk]
        d2 = spec.get("_day2map", {}).get(date)
        if d2:
            pool.sort(key=lambda c: -((c["symbol"] == d2) * 1000
                                      + c["gain_pct"]))
        return pool
    if spec.get("rank") == "news":
        # X340: fresh-news candidates first (18h pre-7AM), then by gain;
        # missing cache = no news. X341 adds news_required.
        pool = pool[:walk]
        def n18(c):
            f = ROOT / "data" / "news_cache" / f"{c['symbol']}_{date}.json"
            if not f.exists():
                return 0
            try:
                return json.loads(f.read_text()).get("n18", 0)
            except Exception:
                return 0
        if spec.get("news_required"):
            pool = [c for c in pool if n18(c) > 0]
        pool.sort(key=lambda c: -((n18(c) > 0) * 1000 + c["gain_pct"]))
        return pool
    if spec.get("rank") == "rvol_boost":
        # X315: extreme-rvol monsters first, then by gain
        pool = pool[:walk]
        pool.sort(key=lambda c: -((c["rvol"] >= 100) * 1e6 + c["gain_pct"]))
        return pool
    if spec.get("rank") == "gainrvol":
        pool = pool[:walk]
        gr = {c["symbol"]: i for i, c in
              enumerate(sorted(pool, key=lambda x: -x["gain_pct"]))}
        rr = {c["symbol"]: i for i, c in
              enumerate(sorted(pool, key=lambda x: -x["rvol"]))}
        pool.sort(key=lambda c: gr[c["symbol"]] * .5 + rr[c["symbol"]] * .5)
        return pool
    return pool[:walk]


# ----------------------------------------------------------------- core
def sim_window(w, c, spec, sub=None):
    kw = dict(BASE_SIM)
    kw.update(spec.get("sim", {}))
    kw["prev_close"] = c["prev_close"]
    if spec.get("pm_break"):
        df = w  # premarket high needs full df -- passed via spec hook
    if sub is not None:
        w = w[w.index.time >= sub]
    if len(w) < 15:
        return []
    return ps.simulate_trades(w, **kw)


def apply_breaker(trades, breaker):
    if not trades or breaker is None:
        return trades
    out = []
    cum = 0.0
    consec_stops = 0
    # group by entry_time (positions), keep chronological
    from itertools import groupby
    positions = []
    for et, g in groupby(sorted(trades, key=lambda t: (t["entry_time"],
                                                       t["exit_time"])),
                         key=lambda t: t["entry_time"]):
        positions.append(list(g))
    for pos in positions:
        if breaker == "2stops" and consec_stops >= 2:
            break
        if isinstance(breaker, (int, float)) and cum <= breaker:
            break
        ppnl = sum(t["pnl"] for t in pos)
        out.extend(pos)
        cum += ppnl
        if any(t["reason"].startswith("stop") for t in pos):
            consec_stops += 1
        elif ppnl > 0:
            consec_stops = 0
    return out


def run_experiment(spec, label):
    xid = spec["id"]
    if spec.get("rank") == "lag":
        gap = json.loads(
            (ROOT / f"data/massive/gappers2_{label}.json").read_text())
        gmap = {(c["symbol"], c["date"]): c["gain_pct"] for c in gap}
        dates = sorted({c["date"] for c in gap})
        prevd = {d: dates[i - 1] for i, d in enumerate(dates) if i > 0}
        spec["_lagmap"] = {(s, d): gmap.get((s, prevd.get(d, "")), 0)
                           for (s, d) in gmap}
    for k, v in spec.get("globals", {}).items():
        setattr(ps, k, v)
    if spec.get("halal_strict"):
        real_ver = axb.VER
        axb.VER = {}
    if spec.get("halal_filing"):
        # leak #6 fix (user: "halal screen should come from last quarter
        # reports"): a quarter is usable only ~45 days after period end,
        # when its 10-Q is actually filed.
        axb.FILING_LAG_DAYS = 45
    by_day = load_by_day(label, spec.get("min_hist", 50), spec.get("pool"))
    calm_gap = spec.get("calm_gap", 20.0)
    recs = []
    monthly = {}
    if spec.get("rank") == "day2":
        # map: date -> yesterday's traded symbol if its day-P&L >= thresh
        # (built from the C21 champion day records -- causal, prior days)
        base = {}
        for lb in ("year", "y2025"):
            try:
                for r in json.loads((ROOT / f"data/massive/c21_trades_{lb}.json").read_text()):
                    base[r["date"]] = r
            except Exception:
                pass
        dates_sorted = sorted(by_day)
        d2map = {}
        th = spec.get("day2_thresh", 2000)
        for k in range(1, len(dates_sorted)):
            prev = base.get(dates_sorted[k - 1])
            if prev and prev["pnl"] >= th:
                d2map[dates_sorted[k]] = prev["symbol"]
        spec["_day2map"] = d2map
    try:
        for i, (date, cs) in enumerate(sorted(by_day.items())):
            if i % 50 == 0:
                print(f"  ..{xid} {label} {i}/{len(by_day)} "
                      f"({len(recs)}d ${sum(r['pnl'] for r in recs):+,.0f})",
                      flush=True)
            dfs = {}
            pool = rank_pool(cs, spec, date, dfs)
            # walk to committed candidate
            committed = None
            com_idx = -1
            calm_count = 0
            for idx, c in enumerate(pool):
                df = dfs.get(c["symbol"])
                if df is None:
                    df = get_lazy(c["symbol"], date)
                    dfs[c["symbol"]] = df
                if df is None:
                    continue
                w = df[(df.index.time >= W_START) & (df.index.time < W_END)]
                if spec.get("exit_1pm"):
                    # S068-S071 may override the 1PM edge via exit_end=(h,m)
                    _ee = spec.get("exit_end", (13, 0))
                    w = df[(df.index.time >= W_START)
                           & (df.index.time < dtime(*_ee))]
                if len(w) < 20:
                    continue
                g7 = ((float(w["Open"].iloc[0]) / c["prev_close"] - 1) * 100
                      if c["prev_close"] else 999)
                gbd = spec.get("gap_band_drop")
                if gbd is not None and gbd[0] <= g7 < gbd[1]:
                    continue          # X316: skip the worst gap band
                gap_lim = calm_gap
                if (calm_gap is not None and spec.get("rescue35")
                        and idx == 0):
                    gap_lim = 35.0
                if calm_gap is not None and g7 > gap_lim:
                    gp = spec.get("gap_pressure")
                    if gp is None:
                        continue
                    # pressure-conditioned admission (X201+): hot-gap
                    # candidates allowed when premarket buyers dominate
                    pmp = pm_pressure_for(spec, df, c["prev_close"],
                                          c["symbol"], date)
                    if pmp is None or pmp < gp[1]:
                        continue
                calm_count += 1
                if not axb.halal_pt(c["symbol"], date, c["prev_close"]):
                    continue
                if spec.get("rvol_admit") and c.get("hist_n", 99) < 50 \
                        and c["rvol"] < spec["rvol_admit"]:
                    continue
                # gain_causal: the pool admits a day because its HIGH
                # reached +10% -- knowable only in hindsight (the user:
                # "the backtest knows info that exist in the future.
                # cheats."). Honest mimic: find the FIRST minute price
                # touched +10% and bar entries until the NEXT minute;
                # never crossed by 12:00 -> never a candidate at all.
                if spec.get("gain_causal"):
                    pc = c.get("prev_close") or 0
                    if pc <= 0 or df is None:
                        continue
                    thr_px = 1.10 * pc
                    cross = None
                    for ts, bh in zip(df.index, df["High"].values):
                        if ts.time() > dtime(12, 0):
                            break
                        if float(bh) >= thr_px:
                            cross = ts
                            break
                    if cross is None:
                        continue
                    nxt = cross + __import__("pandas").Timedelta(minutes=1)
                    # leak #5 (scan cadence): the sim notices a crossing
                    # the next minute; a live session only re-scans every
                    # N minutes. rescan_min=30 -> visible at the next
                    # :00/:30 boundary AFTER the crossing.
                    rs = spec.get("rescan_min")
                    if rs:
                        mins = nxt.hour * 60 + nxt.minute
                        mins = ((mins + rs - 1) // rs) * rs
                        if mins >= 12 * 60:
                            continue      # never seen inside entry window
                        nxt = nxt.replace(hour=mins // 60,
                                          minute=mins % 60)
                    c["_gc_start"] = max(dtime(7, 0), nxt.time())
                    cb = spec.get("cross_before")
                    if cb is not None and c["_gc_start"] > dtime(*cb):
                        continue      # crossed too late in the morning
                # Z4xx earnings gates (TWLO case study 2026-08-09)
                eg = spec.get("earnings_gate")
                if eg is not None:
                    ef = earnings_flags()
                    key = f"{c['symbol']}|{date}"
                    if spec.get("earnings_shuffle"):
                        # ZC40 control: same flag COUNT, wrong days
                        import hashlib
                        hit = int(hashlib.md5(
                            key.encode()).hexdigest(), 16) % 100 < 4
                    else:
                        hit = key in ef
                    if eg and not hit:
                        continue          # earnings-day names only
                    if not eg and hit:
                        continue          # Z402: NON-earnings only
                    bm = spec.get("beats_min")
                    if bm and (not hit or ef.get(key, {})
                               .get("streak", 0) < bm):
                        continue
                # W010: old-style FULL-DAY filter on the novol pool.
                # NON-CAUSAL (peeks at the day's final volume) -- kept
                # only as a reference point, never adoptable live.
                if spec.get("rvol30_min") \
                        and c.get("rvol30", 0) < spec["rvol30_min"]:
                    continue
                # V-series: CAUSAL 30-day rvol measured at a decision
                # time, e.g. ("0730", 0.002). Volume printed by T over
                # the prior 30 sessions' average full day. Unlike the
                # pool's full-day rvol>=5, this is knowable when we act.
                cr = spec.get("causal_rvol")
                if cr is not None:
                    tkey, thr = cr
                    rec = causal_rvol_table().get(f"{c['symbol']}|{date}")
                    if rec is None:
                        # no 30-session baseline -> cannot verify, refuse.
                        continue
                    if rec.get(tkey, 0.0) < thr:
                        continue
                committed = (c, w, df)
                com_idx = idx
                break
            if committed is None:
                continue
            c, w, df = committed
            if spec.get("gain_causal") and c.get("_gc_start"):
                spec.setdefault("sim", {})["entry_start"] = c["_gc_start"]
            if spec.get("pm_break"):
                pm = premkt_metrics(df, c["prev_close"])
                if pm:
                    pmh = c["prev_close"] * (1 + pm["pm_high_gain"] / 100)
                    spec.setdefault("sim", {})["extra_break_high"] = pmh
            tr = sim_window(w, c, spec)
            if spec.get("pm_break"):
                spec["sim"].pop("extra_break_high", None)
            if spec.get("gain_causal"):
                spec.get("sim", {}).pop("entry_start", None)

            # --- fallback re-pick overlay (X015-X018)
            fb = spec.get("fallback")
            if fb is not None:
                t_sw, mode = fb
                first_entry = min((t["entry_time"] for t in tr), default=None)
                switch = (first_entry is None
                          or first_entry.time() >= t_sw)
                if switch and mode == "red":
                    at_t = w[w.index.time < t_sw]
                    switch = (len(at_t) > 5 and
                              float(at_t["Close"].iloc[-1])
                              < float(w["Open"].iloc[0]))
                if switch:
                    tr = []
                    for c2 in pool[com_idx + 1:]:
                        df2 = dfs.get(c2["symbol"])
                        if df2 is None:
                            df2 = get_lazy(c2["symbol"], date)
                        dfs[c2["symbol"]] = df2
                        if df2 is None:
                            continue
                        w2 = df2[(df2.index.time >= W_START)
                                 & (df2.index.time < W_END)]
                        if len(w2) < 20:
                            continue
                        g7b = ((float(w2["Open"].iloc[0]) / c2["prev_close"]
                                - 1) * 100 if c2["prev_close"] else 999)
                        if calm_gap is not None and g7b > calm_gap:
                            continue
                        if not axb.halal_pt(c2["symbol"], date,
                                            c2["prev_close"]):
                            continue
                        tr = sim_window(w2, c2, spec, sub=t_sw)
                        break

            # --- second-pick redeploy overlay (X027/X028)
            sp = spec.get("second_pick")
            if sp is not None and tr:
                gate, cutoff = sp
                last_exit = max(t["exit_time"] for t in tr)
                dp0 = sum(t["pnl"] for t in tr)
                if last_exit.time() < cutoff and (gate == "any" or dp0 > 0):
                    for c2 in pool[com_idx + 1:]:
                        df2 = dfs.get(c2["symbol"])
                        if df2 is None:
                            df2 = get_lazy(c2["symbol"], date)
                        dfs[c2["symbol"]] = df2
                        if df2 is None:
                            continue
                        w2 = df2[(df2.index.time >= W_START)
                                 & (df2.index.time < W_END)]
                        if len(w2) < 20:
                            continue
                        g7b = ((float(w2["Open"].iloc[0]) / c2["prev_close"]
                                - 1) * 100 if c2["prev_close"] else 999)
                        if g7b > (calm_gap or 999):
                            continue
                        if not axb.halal_pt(c2["symbol"], date,
                                            c2["prev_close"]):
                            continue
                        sub_t = (last_exit + __import__("pandas")
                                 .Timedelta(minutes=1)).time()
                        tr2 = sim_window(w2, c2, spec, sub=sub_t)
                        tr = tr + tr2
                        break

            # --- conditional split overlay (X075-X082)
            sp2 = spec.get("split")
            if sp2 is not None:
                tr = run_split(sp2, pool, dfs, date, calm_gap, spec, tr,
                               committed, com_idx)

            tr = apply_breaker(tr, spec.get("breaker"))
            if not tr:
                continue
            dp = sum(t["pnl"] for t in tr)
            recs.append({"date": date, "symbol": c["symbol"],
                         "pnl": round(dp, 2)})
            monthly.setdefault(date[:7], []).append(dp)
    finally:
        for k in spec.get("globals", {}):
            setattr(ps, k, {"MIN_DAY_GAIN_PCT": 10.0,
                            "SURGE_WINDOW_MIN": 50}[k])
        if spec.get("halal_strict"):
            axb.VER = real_ver
        if spec.get("halal_filing"):
            axb.FILING_LAG_DAYS = 0
    tot = sum(r["pnl"] for r in recs)
    negm = sum(1 for v in monthly.values() if sum(v) < 0)
    mkeys = sorted(monthly)
    hold = sum(sum(monthly[m]) for m in mkeys[-2:]) if mkeys else 0
    out = {"id": xid, "label": label, "days": len(recs),
           "total": round(tot), "avg": round(tot / len(recs)) if recs else 0,
           "negm": negm, "nmonths": len(monthly),
           "holdout_last2m": round(hold),
           "monthly": {m: round(sum(v)) for m, v in sorted(monthly.items())}}
    (ROOT / f"data/massive/x100_days_{xid}_{label}.json").write_text(
        json.dumps(recs))
    return out


def run_split(sp2, pool, dfs, date, calm_gap, spec, tr_main, committed, ci):
    """Conditional concurrent split. Returns combined trade list."""
    c1, w1, _ = committed
    # find slot-2 candidate
    cands2 = []
    for c2 in pool:
        if c2["symbol"] == c1["symbol"]:
            continue
        df2 = dfs.get(c2["symbol"])
        if df2 is None:
            df2 = get_lazy(c2["symbol"], date)
        dfs[c2["symbol"]] = df2
        if df2 is None:
            continue
        w2 = df2[(df2.index.time >= W_START) & (df2.index.time < W_END)]
        if len(w2) < 20:
            continue
        g7 = ((float(w2["Open"].iloc[0]) / c2["prev_close"] - 1) * 100
              if c2["prev_close"] else 999)
        if calm_gap is not None and g7 > calm_gap:
            continue
        if not axb.halal_pt(c2["symbol"], date, c2["prev_close"]):
            continue
        cands2.append((c2, w2))
        if len(cands2) >= 2:
            break
    mode = sp2.get("mode", "2x75")
    if mode == "lossrec":
        if not tr_main:
            return tr_main
        dp0 = sum(t["pnl"] for t in tr_main)
        last_exit = max(t["exit_time"] for t in tr_main)
        if dp0 < 0 and last_exit.time() < dtime(9, 30) and cands2:
            c2, w2 = cands2[0]
            kw = {"sim": dict(spec.get("sim", {}), budget=7500)}
            sub_t = (last_exit + __import__("pandas")
                     .Timedelta(minutes=1)).time()
            return tr_main + sim_window(w2, c2, {"sim": kw["sim"]},
                                        sub=sub_t)
        return tr_main
    if not cands2:
        return tr_main
    if sp2.get("both_gain25") and not (c1["gain_pct"] >= 25
                                       and cands2[0][0]["gain_pct"] >= 25):
        return tr_main
    sizes = sp2.get("sizes", [7500, 7500])
    vf = sp2.get("vol_frac", BASE_SIM["max_vol_frac"])
    kw1 = {"sim": dict(spec.get("sim", {}), budget=sizes[0],
                       max_vol_frac=vf)}
    tr1 = sim_window(w1, c1, kw1)
    out = list(tr1)
    slots = cands2[:len(sizes) - 1]
    for k, (c2, w2) in enumerate(slots):
        kw2 = dict(spec.get("sim", {}), budget=sizes[k + 1],
                   max_vol_frac=vf)
        if sp2.get("slot2_orb_only"):
            kw2["buy_set"] = set()
        out += sim_window(w2, c2, {"sim": kw2})
    return out


# ------------------------------------------------------- experiment table
def T(xid, desc, **kw):
    kw.setdefault("F", False)
    return dict(id=xid, desc=desc, **kw)


EXPERIMENTS = [
    # F1 pick-quality
    T("X001", "rank by premarket gain 7AM", rank="pm_gain"),
    T("X002", "rank by premarket $vol", rank="pm_dvol"),
    T("X003", "z(pm gain)+z(rvol) blend", rank="zblend"),
    T("X004", "rank by rvol", rank="rvol"),
    T("X005", "gain band 10-25%", band=(10, 25)),
    T("X006", "gain band 25-50%", band=(25, 50)),
    T("X007", "gain band >=50%", band=(50, 9999)),
    T("X008", "coiled: 7AM within 5% of pm high first", rank="coil"),
    T("X009", "news-tier first (needs news cache)", rank="news", F=True),
    T("X010", "rank by premarket-high gain", rank="pm_high_gain"),
    T("X011", "exclude gain >75% blowoffs", band=(10, 75)),
    T("X012", "require pm $vol >= $1M", pm_dvol_min=1_000_000),
    T("X013", "0.5 rank(gain)+0.5 rank(rvol)", rank="gainrvol"),
    T("X014", "rank by pm turnover vs shares", rank="turnover"),
    # F2 coverage/days
    T("X015", "fallback re-pick 8:30", F=True, fallback=(dtime(8, 30), "any")),
    T("X016", "fallback re-pick 9:00", F=True, fallback=(dtime(9, 0), "any")),
    T("X017", "fallback re-pick 9:30", F=True, fallback=(dtime(9, 30), "any")),
    T("X018", "fallback 8:30 if committed red", F=True,
      fallback=(dtime(8, 30), "red")),
    T("X019", "walk depth 12", F=True, walk=12),
    T("X020", "walk depth 16", F=True, walk=16),
    T("X021", "min_hist >= 25", F=True, min_hist=25),
    T("X022", "min_hist >= 10", F=True, min_hist=10),
    T("X023", "calm-gap 15%", calm_gap=15.0),
    T("X024", "calm-gap 25%", calm_gap=25.0),
    T("X025", "calm-gap 30%", calm_gap=30.0),
    T("X026", "calm gate removed", calm_gap=None),
    T("X027", "2nd pick if flat in profit pre-10:00", F=True,
      second_pick=("profit", dtime(10, 0))),
    T("X028", "2nd pick on any full exit pre-10:00", F=True,
      second_pick=("any", dtime(10, 0))),
    T("X029", "rank-1 rescue gap<=35 on zero-calm days", rescue35=True),
    T("X030", "admit hist<50 when rvol>=8", F=True, min_hist=10,
      rvol_admit=8.0),
    # F3 entries
    T("X031", "orb_bars 5", sim=dict(orb_bars=5)),
    T("X032", "orb_bars 10", sim=dict(orb_bars=10)),
    T("X033", "orb_bars 20", sim=dict(orb_bars=20)),
    T("X034", "orb_bars 30", sim=dict(orb_bars=30)),
    T("X035", "entry cutoff 10:00", sim=dict(entry_cutoff=dtime(10, 0))),
    T("X036", "entry cutoff 10:30", sim=dict(entry_cutoff=dtime(10, 30))),
    T("X037", "entry cutoff 11:00", sim=dict(entry_cutoff=dtime(11, 0))),
    T("X038", "premarket-high stop-buy extra trigger", pm_break=True),
    T("X039", "no entries before 7:15 (skip-first-15)",
      sim=dict(orb_bars=15)),   # OR=15 bars ~ first entries >=7:15 anyway;
                                # realized via entry_cutoff floor below
    T("X040", "vol_confirm on", sim=dict(vol_confirm=True)),
    T("X041", "strong patterns only", sim=dict(buy_set={"hammer",
      "inverted_hammer", "bullish_engulfing", "piercing", "morning_star",
      "three_white_soldiers"})),
    T("X042", "ORB-only entries", sim=dict(buy_set=set())),
    # F4 exits/tail
    T("X043", "no scale-out", sim=dict(scale_out_at=None)),
    T("X044", "scale frac 25%", sim=dict(scale_out_frac=0.25)),
    T("X045", "scale frac 50%", sim=dict(scale_out_frac=0.50)),
    T("X046", "scale at +50%", sim=dict(scale_out_at=50.0)),
    T("X047", "scale at +100%", sim=dict(scale_out_at=100.0)),
    T("X048", "scale at +15%", sim=dict(scale_out_at=15.0)),
    T("X049", "trail 15", sim=dict(trail_pct=15)),
    T("X050", "trail 25", sim=dict(trail_pct=25)),
    T("X051", "trail 30", sim=dict(trail_pct=30)),
    T("X052", "trail 35", sim=dict(trail_pct=35)),
    T("X053", "widen @+50 -> 30", sim=dict(trail_widen_at=50.0,
                                           trail_wide=30.0)),
    T("X054", "widen @+30 -> 30", sim=dict(trail_widen_at=30.0,
                                           trail_wide=30.0)),
    T("X055", "widen @+50 -> 40", sim=dict(trail_widen_at=50.0,
                                           trail_wide=40.0)),
    T("X056", "ATR-scaled trail k=6 [12,35]",
      sim=dict(atr_trail=(6.0, 12.0, 35.0))),
    T("X057", "ATR-scaled stop k=3 [5,12]",
      sim=dict(atr_stop=(3.0, 5.0, 12.0))),
    T("X058", "breakeven stop @+15%", sim=dict(breakeven_at=15.0)),
    T("X059", "breakeven stop @+10%", sim=dict(breakeven_at=10.0)),
    T("X060", "time-stop 45min if flat/red", sim=dict(time_stop_min=45)),
    T("X061", "time-stop 90min", sim=dict(time_stop_min=90)),
    T("X062", "two-tier scale 1/3@25 + 1/3@60",
      sim=dict(scale_out_2=(60.0, 0.5))),
    T("X063", "trail/stop-only exits",
      sim=dict(sell_mode="target_stop_only")),
    T("X064", "exits until 1PM [NEEDS SIGN-OFF]", exit_1pm=True),
    # F5 risk
    T("X065", "stop 5", sim=dict(stop_pct=5)),
    T("X066", "stop 6", sim=dict(stop_pct=6)),
    T("X067", "stop 10", sim=dict(stop_pct=10)),
    T("X068", "stop 12", sim=dict(stop_pct=12)),
    T("X069", "max_trades 1", sim=dict(max_trades=1)),
    T("X070", "max_trades 2", sim=dict(max_trades=2)),
    T("X071", "max_trades 3", sim=dict(max_trades=3)),
    T("X072", "circuit-breaker -$2k", breaker=-2000),
    T("X073", "circuit-breaker -$3k", breaker=-3000),
    T("X074", "halt after 2 consecutive stops", breaker="2stops"),
    # F6 concurrency
    T("X075", "2x$7.5k when >=2 calm-halal", F=True,
      split=dict(mode="2x75")),
    T("X076", "$10k/$5k rank-weighted", F=True,
      split=dict(mode="2x75", sizes=[10000, 5000])),
    T("X077", "split only when both gain>=25", F=True,
      split=dict(mode="2x75", both_gain25=True)),
    T("X078", "3x$5k when >=3 calm-halal", F=True,
      split=dict(mode="2x75", sizes=[5000, 5000, 5000])),
    T("X079", "2x$7.5k + vol_frac 0.20", F=True,
      split=dict(mode="2x75", vol_frac=0.20)),
    T("X080", "split gated on 10-day calm supply>=2", F=True,
      split=dict(mode="2x75", supply_gate=2.0)),
    T("X081", "2x$7.5k slot-2 ORB-only", F=True,
      split=dict(mode="2x75", slot2_orb_only=True)),
    T("X082", "loss-recovery $7.5k redeploy", F=True,
      split=dict(mode="lossrec")),
    # F7 sizing
    T("X083", "vol_frac 0.05", sim=dict(max_vol_frac=0.05)),
    T("X084", "vol_frac 0.15", sim=dict(max_vol_frac=0.15)),
    T("X085", "vol_frac 0.20", sim=dict(max_vol_frac=0.20)),
    T("X086", "vol_frac uncapped", sim=dict(max_vol_frac=None)),
    T("X087", "vol_frac_window 10", sim=dict(vol_frac_window=10)),
    T("X088", "vol_frac_window 1", sim=dict(vol_frac_window=1)),
    T("X089", "half-then-add at +10%", sim=dict(add_at=10.0)),
    T("X090", "half-then-add at +5%", sim=dict(add_at=5.0)),
    # F8 honesty & gates
    T("X091", "B0 anchor re-run"),
    T("X092", "fully-causal: pm_gain rank (flagship)", rank="pm_gain"),
    T("X093", "entry gate 5%", globals={"MIN_DAY_GAIN_PCT": 5.0}),
    T("X094", "random-rank control", rank="random"),
    T("X095", "lag-rank nonsense control", F=True, rank="lag"),
    T("X096", "slippage 10bps/side", sim=dict(slippage_bps=10.0)),
    T("X097", "pessimistic ORB fills", sim=dict(orb_fill_mode="close")),
    T("X098", "halal-strict (no static fallback)", halal_strict=True),
    T("X099", "entry gate 15%", globals={"MIN_DAY_GAIN_PCT": 15.0}),
    T("X100", "surge window 30", globals={"SURGE_WINDOW_MIN": 30}),
]

# ---- X200 campaign ----------------------------------------------------
C02SIM = dict(orb_bars=5, max_vol_frac=0.20, vol_frac_window=10)


def C2(xid, desc, **kw):
    """C02-based experiment: C02 sim + pm-high trigger + one change."""
    sim = dict(C02SIM)
    sim.update(kw.pop("sim", {}))
    return T(xid, desc, pm_break=True, sim=sim, **kw)


EXPERIMENTS += [
    # F1-A pressure-conditioned gap gate (premarket pressure admits >20%)
    C2("X201", "gap>20 ok if pm_pressure>=0.10", gap_pressure=(30, 0.10)),
    C2("X202", "gap>20 ok if pm_pressure>=0.20", gap_pressure=(30, 0.20)),
    C2("X203", "gap>20 ok if pm_pressure>=0.30", gap_pressure=(30, 0.30)),
    C2("X204", "gap>20 ok if pm_pressure>=0.40", gap_pressure=(30, 0.40)),
    C2("X205", "no calm gate; entry-time P gate T=0.2", calm_gap=None,
       sim=dict(gap_gate_pressure=(10, 0.20, 20.0))),
    C2("X206", "no calm gate; entry-time P gate T=0.3", calm_gap=None,
       sim=dict(gap_gate_pressure=(10, 0.30, 20.0))),
    # F1-B entry confirmation
    C2("X207", "all entries need P>=0.0", sim=dict(pressure_entry=(10, 0.0))),
    C2("X208", "all entries need P>=0.1", sim=dict(pressure_entry=(10, 0.1))),
    C2("X209", "all entries need P>=0.2", sim=dict(pressure_entry=(10, 0.2))),
    C2("X210", "patterns need P>=0.1 (ORB/PMH exempt)",
       sim=dict(pressure_entry_patterns=(10, 0.1))),
    # F1-C pressure exits
    C2("X211", "exit-in-profit when P<=-0.2",
       sim=dict(pressure_exit=(10, 0.2, "profit"))),
    C2("X212", "exit-in-profit when P<=-0.3",
       sim=dict(pressure_exit=(10, 0.3, "profit"))),
    C2("X213", "exit-in-profit when P<=-0.4",
       sim=dict(pressure_exit=(10, 0.4, "profit"))),
    C2("X214", "pressure exit REPLACES bearish patterns",
       sim=dict(sell_mode="target_stop_only",
                pressure_exit=(10, 0.3, "profit"))),
    C2("X215", "pressure exit even at a loss",
       sim=dict(pressure_exit=(10, 0.3, "always"))),
    C2("X216", "pressure exit window N=5",
       sim=dict(pressure_exit=(5, 0.3, "profit"))),
    C2("X217", "pressure exit window N=20",
       sim=dict(pressure_exit=(20, 0.3, "profit"))),
    # F1-D pressure-modulated trail
    C2("X218", "trail tightens to 12% when P<=-0.2",
       sim=dict(pressure_trail=(10, 0.20, None, 12, None))),
    C2("X219", "trail 12%/30% two-sided on P -/+0.3",
       sim=dict(pressure_trail=(10, 0.30, 0.30, 12, 30))),
    C2("X220", "trail widens to 30% when P>=+0.3",
       sim=dict(pressure_trail=(10, None, 0.30, None, 30))),
    # F1-E pressure re-entry
    C2("X221", "1 re-entry on P cross-up +0.2",
       sim=dict(pressure_reentry=(10, 0.20, 1, "any"))),
    C2("X222", "2 re-entries after stop/trail only",
       sim=dict(pressure_reentry=(10, 0.20, 2, "stoptrail"))),
    # F1-G controls (must FAIL)
    C2("X229", "CONTROL shuffled pm_pressure", gap_pressure=(30, 0.20),
       gap_pressure_control="shuffle"),
    C2("X230", "CONTROL lagged pm_pressure", gap_pressure=(30, 0.20),
       gap_pressure_control="lag"),
    # F2 neighborhood sweeps + combos
    C2("X231", "orb_bars 3", sim=dict(orb_bars=3)),
    C2("X232", "orb_bars 4", sim=dict(orb_bars=4)),
    C2("X233", "orb_bars 6", sim=dict(orb_bars=6)),
    C2("X234", "orb_bars 8", sim=dict(orb_bars=8)),
    C2("X235", "vol_frac 0.25", sim=dict(max_vol_frac=0.25)),
    C2("X236", "vol_frac 0.30", sim=dict(max_vol_frac=0.30)),
    C2("X237", "scale-out at +30%", sim=dict(scale_out_at=30.0)),
    C2("X238", "scale-out at +35%", sim=dict(scale_out_at=35.0)),
    C2("X239", "scale-out frac 0.25", sim=dict(scale_out_frac=0.25)),
    C2("X240", "C03 rank + C02 trigger", rank="pm_dvol"),
    C2("C08", "C02 + exits to 1PM (signed off)", exit_1pm=True),
]

# F1-F interaction matrix: gate width x pressure threshold
_i = 223
for _gl in (30.0, 50.0, None):
    for _t in (0.20, 0.30):
        if _gl is None:
            EXPERIMENTS.append(C2(f"X{_i}",
                f"no gate; entry-time P>={_t}", calm_gap=None,
                sim=dict(gap_gate_pressure=(10, _t, 20.0))))
        else:
            EXPERIMENTS.append(C2(f"X{_i}",
                f"gate {_gl:.0f}% + pm_pressure>={_t}", calm_gap=_gl,
                gap_pressure=(30, _t)))
        _i += 1

# F0 gap-gate sweep: 8 base configs x 8 gates
_BASES = {
    "AX20": dict(),
    "C01": dict(sim=dict(C02SIM)),
    "C02": dict(pm_break=True, sim=dict(C02SIM)),
    "C03": dict(rank="pm_dvol", sim=dict(C02SIM)),
    "C04": dict(sim=dict(orb_bars=5, max_vol_frac=None)),
    "C06": dict(exit_1pm=True, sim=dict(C02SIM)),
    "C07": dict(pm_break=True, sim=dict(C02SIM, slippage_bps=10.0)),
    "X086": dict(sim=dict(max_vol_frac=None)),
}
for _name, _base in _BASES.items():
    for _gap in (30, 40, 50, 60, 70, 80, 90, 100):
        spec = dict(_base)
        spec["sim"] = dict(_base.get("sim", {}))
        EXPERIMENTS.append(T(f"{_name}G{_gap}",
                             f"{_name} with calm-gap {_gap}%",
                             calm_gap=float(_gap), **spec))




# ---- X300 campaign (strict-noon C10 base) ----------------------------
from datetime import time as _dt
C10TRAIL = (10, 0.30, 0.30, 12, 30)
PATTERNS_ONLY = {"hammer", "inverted_hammer", "bullish_engulfing",
                 "piercing", "morning_star", "three_white_soldiers",
                 "tweezer_bottom", "bullish_spinning_top",
                 "dragonfly_doji"}


def C10(xid, desc, **kw):
    sim = dict(C02SIM, pressure_trail=C10TRAIL)
    sim.update(kw.pop("sim", {}))
    return T(xid, desc, pm_break=True, sim=sim, **kw)


EXPERIMENTS += [
    C10("X301", "C10 anchor re-run"),
    # A. pressure-trail neighborhood
    C10("X302", "trail thresh 0.20, N=5",
        sim=dict(pressure_trail=(5, 0.20, 0.20, 12, 30))),
    C10("X303", "trail thresh 0.40, N=5",
        sim=dict(pressure_trail=(5, 0.40, 0.40, 12, 30))),
    C10("X304", "trail thresh 0.20, N=20",
        sim=dict(pressure_trail=(20, 0.20, 0.20, 12, 30))),
    C10("X305", "trail thresh 0.40, N=20",
        sim=dict(pressure_trail=(20, 0.40, 0.40, 12, 30))),
    C10("X306", "widths 10/30", sim=dict(pressure_trail=(10, 0.30, 0.30, 10, 30))),
    C10("X307", "widths 12/40", sim=dict(pressure_trail=(10, 0.30, 0.30, 12, 40))),
    C10("X308", "widths 15/25", sim=dict(pressure_trail=(10, 0.30, 0.30, 15, 25))),
    C10("X309", "wide 40 only at P>=+0.5",
        sim=dict(pressure_trail=(10, 0.30, 0.50, 12, 40))),
    # B. monster amplification
    C10("X310", "skip scale-out when P>=+0.3",
        sim=dict(scale_out_pressure_skip=0.30)),
    C10("X311", "scale frac 0.25 when P>=+0.3",
        sim=dict(scale_out_frac_pressure=(0.30, 0.25))),
    # C. trigger refinement
    C10("X312", "PMH re-arm on new highs", sim=dict(pmh_rearm=True)),
    C10("X313", "pattern entries end 11:00",
        sim=dict(entry_cutoff_patterns=_dt(11, 0))),
    C10("X314", "no RSI/MACD pseudo-pattern entries",
        sim=dict(buy_set=PATTERNS_ONLY)),
    # D. pick hypotheses (post-hoc -- extra skepticism)
    C10("X315", "rvol>=100 candidates rank first", rank="rvol_boost"),
    C10("X316", "drop -5..0% gap band", gap_band_drop=(-5.0, 0.0)),
    C10("X317", "walk depth 3 (expected negative)", walk=3),
    # E. controls / hygiene / stress
    C10("X318", "CONTROL shuffled-pressure trail",
        sim=dict(pressure_trail=(10, 0.30, 0.30, 12, 30),
                 pressure_shuffle=True)),
    C10("X319", "wick guard 3x", sim=dict(wick_guard=3.0)),
    C10("X320", "C10 + 10bps slippage", sim=dict(slippage_bps=10.0)),
]
BYID = {e["id"]: e for e in EXPERIMENTS}




# ---- X321+ pressure-threshold sweeps on C21 base ---------------------
C21SIM = dict(C02SIM, pressure_trail=(10, 0.30, 0.30, 10, 40),
              scale_out_pressure_skip=0.30, wick_guard=3.0)


def C21(xid, desc, **kw):
    sim = dict(C21SIM)
    sim.update(kw.pop("sim", {}))
    return T(xid, desc, pm_break=True, sim=sim, **kw)


EXPERIMENTS += [C21("X321", "C21 anchor re-run")]
_i = 322
for _t in (0.15, 0.20, 0.25, 0.35, 0.40, 0.45):
    EXPERIMENTS.append(C21(f"X{_i}", f"trail threshold {_t}",
        sim=dict(pressure_trail=(10, _t, _t, 10, 40))))
    _i += 1
for _sk in (0.15, 0.20, 0.25, 0.35, 0.40, 0.45):
    EXPERIMENTS.append(C21(f"X{_i}", f"scale-skip threshold {_sk}",
        sim=dict(scale_out_pressure_skip=_sk)))
    _i += 1

# ---------------------------------------------------------------- S-campaign
# 100 experiments derived from the C30 statistical deep-dive
# (day-trading/plan/c30_stats.py). Baseline is C23 = C21 machinery inside
# the 1PM exit window -- the live champion (C30 = C23 + capped R50 sizing).
# Anchor S000 must reproduce +$412,879 / +$579,988 exactly.
def C23(xid, desc, **kw):
    sim = dict(C21SIM)
    sim.update(kw.pop("sim", {}))
    return T(xid, desc, pm_break=True, exit_1pm=True, sim=sim, **kw)


EXPERIMENTS += [C23("S000", "C23 anchor (identity check)")]

# --- A. Pressure-scaled sizing (finding: p_entry>=0.3 averaged 3x) ---
# pressure_size=(win, thr_hi, mult_hi, thr_lo, mult_lo)
for _n, _t in zip(range(1, 5), (0.20, 0.30, 0.40, 0.50)):
    EXPERIMENTS.append(C23(f"S{_n:03d}", f"size 1.5x when p>={_t}",
        sim=dict(pressure_size=(10, _t, 1.5, -9.9, 1.0))))
for _n, _m in zip(range(5, 9), (1.25, 1.5, 2.0, 2.5)):
    EXPERIMENTS.append(C23(f"S{_n:03d}", f"size {_m}x when p>=0.30",
        sim=dict(pressure_size=(10, 0.30, _m, -9.9, 1.0))))
for _n, (_lt, _lm) in zip(range(9, 13),
                          ((0.0, 0.75), (0.0, 0.50),
                           (-0.30, 0.75), (-0.30, 0.50))):
    EXPERIMENTS.append(C23(f"S{_n:03d}", f"size {_lm}x when p<{_lt}",
        sim=dict(pressure_size=(10, 9.9, 1.0, _lt, _lm))))
for _n, (_hm, _lm) in zip(range(13, 16),
                          ((1.5, 0.75), (1.5, 0.50), (2.0, 0.50))):
    EXPERIMENTS.append(C23(f"S{_n:03d}",
        f"both: {_hm}x p>=0.3 / {_lm}x p<0",
        sim=dict(pressure_size=(10, 0.30, _hm, 0.0, _lm))))
EXPERIMENTS.append(C23("S016", "pressure window 20 bars, 1.5x/0.5x",
    sim=dict(pressure_size=(20, 0.30, 1.5, 0.0, 0.50))))
EXPERIMENTS.append(C23("S017", "CONTROL shuffled pressure + sizing",
    sim=dict(pressure_size=(10, 0.30, 1.5, 0.0, 0.50),
             pressure_shuffle=True)))
EXPERIMENTS.append(C23("S018", "CONTROL inverted sizing (p>=0.3 -> 0.5x)",
    sim=dict(pressure_size=(10, 0.30, 0.50, 0.0, 1.5))))

# --- B. Trail capture / small-peak rescue (capture ratio 0.29) ---
for _n, _b in zip(range(19, 24), (2.0, 3.0, 4.0, 5.0, 8.0)):
    EXPERIMENTS.append(C23(f"S{_n:03d}", f"breakeven stop at +{_b}%",
        sim=dict(breakeven_at=_b)))
for _n, _b in zip(range(24, 28), (2.5, 3.5, 4.5, 6.0)):
    EXPERIMENTS.append(C23(f"S{_n:03d}", f"breakeven at +{_b}% (fine grid)",
        sim=dict(breakeven_at=_b)))
for _n, (_wa, _ww) in zip(range(28, 33),
                          ((10.0, 30.0), (15.0, 40.0), (20.0, 40.0),
                           (25.0, 50.0), (15.0, 50.0))):
    EXPERIMENTS.append(C23(f"S{_n:03d}",
        f"tiered trail widen@{_wa}% -> {_ww}%",
        sim=dict(trail_widen_at=_wa, trail_wide=_ww)))
for _n, _ts in zip(range(33, 37), (10, 15, 20, 30)):
    EXPERIMENTS.append(C23(f"S{_n:03d}", f"time stop {_ts} min",
        sim=dict(time_stop_min=_ts)))
for _n, _so in zip(range(37, 41), (15.0, 20.0, 30.0, 35.0)):
    EXPERIMENTS.append(C23(f"S{_n:03d}", f"scale-out at +{_so}%",
        sim=dict(scale_out_at=_so)))

# --- A-decisive: CAPITAL-NEUTRALITY controls -------------------------------
# Wave 1 showed BOTH the pressure-sizing variant (S002, +$64k) and its
# INVERTED control (S018, +$67k) beating C23 -- so the gain may be pure
# leverage (more average capital deployed), not pressure signal. These two
# deploy the same average capital as S002/S018 with NO pressure input at
# all: if they match, Family A is leverage and must be rejected.
EXPERIMENTS.append(C23("S041", "flat budget $16,126 (= S002 avg capital)",
    sim=dict(budget=16126.0)))
EXPERIMENTS.append(C23("S042", "flat budget $17,425 (= S018 avg capital)",
    sim=dict(budget=17425.0)))
# extended scale-out sweep: S037-S040 trended monotonically better with a
# LATER scale-out (+30%/+35% both-year positive but under the $30k floor)
for _n, _so in zip(range(43, 47), (40.0, 45.0, 50.0, 60.0)):
    EXPERIMENTS.append(C23(f"S{_n:03d}", f"scale-out at +{_so}%",
        sim=dict(scale_out_at=_so)))

# --- WAVE 2 -----------------------------------------------------------------
# C. Pattern pruning (c30_stats: dragonfly_doji net NEGATIVE -$1,186;
# inverted_hammer +$17/position = below transaction cost; ORB alone is 74%
# of all profit). buy_set is a whitelist filter over BULLISH_PATTERNS.
_ALLP = ["hammer", "inverted_hammer", "dragonfly_doji",
         "bullish_spinning_top", "bullish_engulfing", "tweezer_bottom",
         "morning_star", "rising_three", "rsi_cross_up", "macd_cross_up"]
# ranked by measured mean P&L/position (c30_stats section 5)
_RANKED = ["bullish_engulfing", "macd_cross_up", "morning_star",
           "bullish_spinning_top", "tweezer_bottom", "hammer",
           "rsi_cross_up", "inverted_hammer", "dragonfly_doji"]
EXPERIMENTS.append(C23("S048", "drop dragonfly_doji (net negative)",
    sim=dict(buy_set=set(_ALLP) - {"dragonfly_doji"})))
EXPERIMENTS.append(C23("S049", "drop inverted_hammer (below cost)",
    sim=dict(buy_set=set(_ALLP) - {"inverted_hammer"})))
EXPERIMENTS.append(C23("S050", "drop both weak patterns",
    sim=dict(buy_set=set(_ALLP) - {"dragonfly_doji", "inverted_hammer"})))
EXPERIMENTS.append(C23("S051", "drop bottom-3 (adds rsi_cross_up)",
    sim=dict(buy_set=set(_ALLP) - {"dragonfly_doji", "inverted_hammer",
                                   "rsi_cross_up"})))
EXPERIMENTS.append(C23("S052", "ORB/PMH only (no patterns at all)",
    sim=dict(buy_set=set())))
EXPERIMENTS.append(C23("S053", "ORB/PMH + bullish_engulfing only",
    sim=dict(buy_set={"bullish_engulfing"})))
for _n, _k in zip(range(54, 57), (3, 5, 7)):
    EXPERIMENTS.append(C23(f"S{_n:03d}", f"keep top-{_k} patterns by mean",
        sim=dict(buy_set=set(_RANKED[:_k]))))
EXPERIMENTS.append(C23("S057", "CONTROL keep only the 3 WORST patterns",
    sim=dict(buy_set=set(_RANKED[-3:]))))
EXPERIMENTS.append(C23("S058", "PMH re-arm on (best mean trigger, n=99)",
    sim=dict(pmh_rearm=True)))

# D. Window optimization (c30_stats: noon ENTRIES = 18% of positions but
# 3.1% of profit at ~$54/position ~= slippage; positions EXITING after noon
# carry +$191,196 -- so cut entries, keep the 1PM exit window).
for _n, _hm in zip(range(59, 64),
                   ((11, 0), (11, 15), (11, 30), (11, 45), (12, 0))):
    EXPERIMENTS.append(C23(f"S{_n:03d}",
        f"entry cutoff {_hm[0]}:{_hm[1]:02d} (exits still 1PM)",
        sim=dict(entry_cutoff=dtime(*_hm))))
for _n, _hm in zip(range(64, 68),
                   ((10, 0), (10, 30), (11, 0), (11, 30))):
    EXPERIMENTS.append(C23(f"S{_n:03d}",
        f"pattern-entry cutoff {_hm[0]}:{_hm[1]:02d} (ORB/PMH run on)",
        sim=dict(entry_cutoff_patterns=dtime(*_hm))))
# exit-window sweep needs the harness `exit_end` key (see run_experiment)
for _n, _hm in zip(range(68, 72),
                   ((12, 30), (13, 30), (14, 0), (15, 0))):
    EXPERIMENTS.append(C23(f"S{_n:03d}",
        f"exit window to {_hm[0]}:{_hm[1]:02d}", exit_end=_hm))

# --- WAVE 2b: prune the losing patterns UNDER the 15:00 exit window --------
# Re-measured on the S071 dump (4,102 positions): dragonfly_doji now
# -$5,074 total (mean -$53, t=-0.41) and inverted_hammer -$6,152 (mean
# -$24, t=-0.41) -- both NEGATIVE here, vs ~zero under the 1PM window.
# t-stats are still weak, so these must clear the both-year guardrail on
# their own; S076 is the paired control (drop two GOOD patterns instead --
# if that also "helps", the ranking is noise again, as in Wave 2).
_S71 = dict(exit_end=(15, 0))
EXPERIMENTS.append(C23("S072", "S071 + drop dragonfly_doji",
    sim=dict(buy_set=set(_ALLP) - {"dragonfly_doji"}), **_S71))
EXPERIMENTS.append(C23("S073", "S071 + drop inverted_hammer",
    sim=dict(buy_set=set(_ALLP) - {"inverted_hammer"}), **_S71))
EXPERIMENTS.append(C23("S074", "S071 + drop BOTH losing patterns",
    sim=dict(buy_set=set(_ALLP) - {"dragonfly_doji", "inverted_hammer"}),
    **_S71))
EXPERIMENTS.append(C23("S075", "S071 + drop both + rsi_cross_up",
    sim=dict(buy_set=set(_ALLP) - {"dragonfly_doji", "inverted_hammer",
                                   "rsi_cross_up"}), **_S71))
EXPERIMENTS.append(C23("S076",
    "CONTROL S071 + drop two GOOD patterns (spinning_top, morning_star)",
    sim=dict(buy_set=set(_ALLP) - {"bullish_spinning_top",
                                   "morning_star"}), **_S71))
# S077/S078: S071 under the C30 sizing regime the live book actually uses
# (capped R50). Flat-budget proxies at the measured liquidity tiers --
# the true dynamic R50 replay runs separately in c23_r50_dynamic-style.
EXPERIMENTS.append(C23("S077", "S071 at $60k slot (C30 mid-tier)",
    sim=dict(budget=60_000.0), **_S71))
EXPERIMENTS.append(C23("S078", "S071 at $120k slot (C30 cap)",
    sim=dict(budget=120_000.0), **_S71))
# User's real account is $100k. Max CONCURRENT positions in the whole
# backtest is 2 (verified), so the slot is peak exposure, not a per-day
# sum -- these are FLAT (no compounding) runs at that size.
EXPERIMENTS.append(C23("S079", "C23 1PM exit at $100k slot, FLAT",
    sim=dict(budget=100_000.0)))
EXPERIMENTS.append(C23("S080", "S071 15:00 exit at $100k slot, FLAT",
    sim=dict(budget=100_000.0), **_S71))
# CASH-ACCOUNT REALITY (user 2026-08-07): no margin, so T+1 settlement
# locks each $15k tranche after its round-trip. With $100k that is ~6
# round-trips per day, NOT the 10.5 the champion averages. max_trades
# caps positions per day -- sweep it for both exit windows.
for _n, _mt in zip(range(81, 86), (4, 5, 6, 7, 8)):
    EXPERIMENTS.append(C23(f"S{_n:03d}",
        f"C23 1PM, max {_mt} trades/day (cash-account cap)",
        sim=dict(max_trades=_mt)))
for _n, _mt in zip(range(86, 91), (4, 5, 6, 7, 8)):
    EXPERIMENTS.append(C23(f"S{_n:03d}",
        f"S071 15:00, max {_mt} trades/day (cash-account cap)",
        sim=dict(max_trades=_mt), **_S71))

# --- EXACT cash-account model: $100k of settled cash deployable per day,
# last ticket sized with whatever remains (user: "ok if we use 10k for the
# last trade"). daily_deploy_cap counts actual cost basis, so 6 x $15k +
# 1 x $10k = $100k exactly, then entries stop until tomorrow.
_NOPAT = set(_ALLP) - {"dragonfly_doji", "inverted_hammer"}
EXPERIMENTS.append(C23("S091", "C23 1PM + $100k/day cash cap",
    sim=dict(daily_deploy_cap=100_000.0)))
EXPERIMENTS.append(C23("S092", "S071 15:00 + $100k/day cash cap",
    sim=dict(daily_deploy_cap=100_000.0), **_S71))
EXPERIMENTS.append(C23("S093",
    "S071 15:00 + $100k/day cap + drop 2 losing patterns",
    sim=dict(daily_deploy_cap=100_000.0, buy_set=_NOPAT), **_S71))
EXPERIMENTS.append(C23("S094", "C23 1PM + $100k/day cap + drop 2 patterns",
    sim=dict(daily_deploy_cap=100_000.0, buy_set=_NOPAT)))

# --- C35 candidate: front-load the day's cash into the FIRST entry -----------
# Motivation: on C34, entry #1 has the best mean (+$1,204, 71% win) and
# value decays with entry number. 1x$25k + 5x$15k = $100k exactly, so this
# is CAPITAL-NEUTRAL vs C34 (both deploy up to the same daily cap) -- the
# Wave 1 leverage trap does not apply. S096/S097 are the controls: give the
# same $25k ticket to the 2nd or 3rd entry instead. If those gain equally,
# the effect is "one big ticket" rather than "the FIRST entry deserves it".
_C34 = dict(daily_deploy_cap=100_000.0, buy_set=_NOPAT)
EXPERIMENTS.append(C23("S095", "C35: 1st entry $25k, rest $15k, $100k cap",
    sim=dict(_C34, entry_ticket_schedule=(1, 25_000.0)), **_S71))
EXPERIMENTS.append(C23("S096", "CONTROL $25k on the 2nd entry instead",
    sim=dict(_C34, entry_ticket_schedule=(2, 25_000.0)), **_S71))
EXPERIMENTS.append(C23("S097", "CONTROL $25k on the 3rd entry instead",
    sim=dict(_C34, entry_ticket_schedule=(3, 25_000.0)), **_S71))
EXPERIMENTS.append(C23("S098", "C35b: 1st entry $35k, rest $15k",
    sim=dict(_C34, entry_ticket_schedule=(1, 35_000.0)), **_S71))
EXPERIMENTS.append(C23("S099", "C35c: 1st entry $20k, rest $15k",
    sim=dict(_C34, entry_ticket_schedule=(1, 20_000.0)), **_S71))

# --- V. CAUSAL 30-DAY rvol GATE (user 2026-08-07: "change the backtest
# to be 30d ... use volume at the time we checking for instead of using
# the whole day volume i.e. volume at 7:30 AM instead of volume at whole
# day. and backtest the 2 years")
#
# Everything is C35. The ONLY change is candidate admission: instead of
# inheriting the pool's non-causal full-day rvol>=5, each candidate must
# clear a floor on (volume printed by time T) / (30-session average full
# day). Volume is measured on 5-minute buckets; entries and exits still
# run on 1-minute bars, untouched.
#
# V000 is the coverage control: threshold 0.0 still drops candidate-days
# that lack a full 30-session baseline, so the gap between V000 and C35
# is DATA LOSS, not gate loss. Read every other V against V000, not
# against C35, or the two effects get conflated.
_VT = ["0700", "0730", "0800", "0900", "0930"]
_VF = [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05]
EXPERIMENTS.append(C23("V000", "causal-rvol COVERAGE CONTROL (floor 0)",
    sim=dict(_C34, entry_ticket_schedule=(1, 25_000.0)),
    causal_rvol=("0730", 0.0), **_S71))
_vn = 1
for _t in _VT:
    for _f in _VF:
        EXPERIMENTS.append(C23(
            f"V{_vn:03d}", f"causal 30d rvol at {_t[:2]}:{_t[2:]} >= {_f}",
            sim=dict(_C34, entry_ticket_schedule=(1, 25_000.0)),
            causal_rvol=(_t, _f), **_S71))
        _vn += 1

# --- W. NO-VOLUME-FILTER POOL (user 2026-08-07: "test multiple
# strategies, to see if ignoring the volume somehow increase the profit.
# or when checking the volume in a specific way different than 5x")
#
# Pool = gappers_novol: identical discovery to gappers2 with the rvol
# filter DROPPED -- 116,814 candidate-days vs 15,482 (the old scanner
# hid 87% of +10% gappers). Everything else is C35.
#   W000  volume fully ignored (the pure question)
#   W001+ causal 30d floors at 07:30 on the wide pool ("different eye")
#   W010  full-day rvol30>=5 re-imposed on the wide pool -- reproduces
#         the OLD style of filter on the new universe; non-causal, so a
#         reference point, not adoptable
_W35 = dict(_C34, entry_ticket_schedule=(1, 25_000.0))
EXPERIMENTS.append(C23("W000", "novol pool, volume IGNORED",
    sim=dict(_W35), pool="novol", **_S71))
for _wn, _wf in zip(range(1, 6), (0.001, 0.005, 0.01, 0.05, 0.10)):
    EXPERIMENTS.append(C23(
        f"W{_wn:03d}", f"novol pool + causal 07:30 rvol >= {_wf}",
        sim=dict(_W35), pool="novol", causal_rvol=("0730", _wf), **_S71))
EXPERIMENTS.append(C23("W006", "novol pool + causal 09:30 rvol >= 0.005",
    sim=dict(_W35), pool="novol", causal_rvol=("0930", 0.005), **_S71))
EXPERIMENTS.append(C23("W007", "novol pool + causal 09:30 rvol >= 0.05",
    sim=dict(_W35), pool="novol", causal_rvol=("0930", 0.05), **_S71))
EXPERIMENTS.append(C23("W010", "novol pool + NON-CAUSAL rvol30>=5 (ref)",
    sim=dict(_W35), pool="novol", rvol30_min=5.0, **_S71))

# --- look-ahead audit (user: "the backtest knows info that exist in
# the future. cheats. what should we test?"). Three leaks: (1) pool
# volume -- V/W series above; (2) pool admission by the day's HIGH
# reaching +10%, unknowable until it happens -> gain_causal bars
# entries until the minute AFTER the first +10% touch; (3) walk order
# by full-day gain -> rank="pm_gain" orders by premarket gain instead.
EXPERIMENTS.append(C23("V100", "C35 + first-crossing entry (old pool)",
    sim=dict(_W35), gain_causal=True, **_S71))
EXPERIMENTS.append(C23("W101", "novol + first-crossing entry",
    sim=dict(_W35), pool="novol", gain_causal=True, **_S71))
EXPERIMENTS.append(C23("W102", "novol + first-crossing + 07:30>=0.005",
    sim=dict(_W35), pool="novol", gain_causal=True,
    causal_rvol=("0730", 0.005), **_S71))
EXPERIMENTS.append(C23("W103", "novol + first-crossing + pm_gain rank",
    sim=dict(_W35), pool="novol", gain_causal=True, rank="pm_gain",
    **_S71))
# leaks #4 (entry-bar volume in sizing) and #5 (scan cadence)
EXPERIMENTS.append(C23("V101", "C35 + causal sizing volume (leak #4)",
    sim=dict(_W35, vol_frac_causal=True), **_S71))
EXPERIMENTS.append(C23("W104", "W101 + 30-min scan cadence (leak #5)",
    sim=dict(_W35), pool="novol", gain_causal=True, rescan_min=30,
    **_S71))
EXPERIMENTS.append(C23("W105", "honest-live: crossing+cadence+sizing",
    sim=dict(_W35, vol_frac_causal=True), pool="novol", gain_causal=True,
    rescan_min=30, **_S71))
# leaks #6-#9, each isolated on the old pool, then the full stack
EXPERIMENTS.append(C23("V102", "C35 + halal from last FILED quarter",
    sim=dict(_W35), halal_filing=True, **_S71))
EXPERIMENTS.append(C23("V103", "C35 + halt-aware stops/entries",
    sim=dict(_W35, halt_aware=True), **_S71))
for _pn, _bp in zip(range(4, 7), (25, 50, 100)):
    EXPERIMENTS.append(C23(f"V10{_pn}", f"C35 + premarket spread {_bp}bps",
        sim=dict(_W35, pm_spread_bps=float(_bp)), **_S71))
EXPERIMENTS.append(C23("W106", "HONEST STACK: all six fixes at once",
    sim=dict(_W35, vol_frac_causal=True, halt_aware=True,
             pm_spread_bps=50.0),
    pool="novol", gain_causal=True, rescan_min=30, halal_filing=True,
    **_S71))

# cadence refinement: 30-min visibility cost 25% (W104 vs W101) -- test
# whether a 5-minute live scan cadence recovers it before adopting any
# cadence into the honest stack
EXPERIMENTS.append(C23("W107", "W101 + 5-min scan cadence",
    sim=dict(_W35), pool="novol", gain_causal=True, rescan_min=5,
    **_S71))
EXPERIMENTS.append(C23("W108", "HONEST STACK, 5-min cadence",
    sim=dict(_W35, vol_frac_causal=True, halt_aware=True,
             pm_spread_bps=50.0),
    pool="novol", gain_causal=True, rescan_min=5, halal_filing=True,
    **_S71))

# W109: the ONLY fully-causal config -- W108 + walk ordered by
# premarket gain instead of full-day gain (leak #3, the last one).
EXPERIMENTS.append(C23("W109", "FULLY CAUSAL: W108 + pm_gain rank",
    sim=dict(_W35, vol_frac_causal=True, halt_aware=True,
             pm_spread_bps=50.0),
    pool="novol", gain_causal=True, rescan_min=5, halal_filing=True,
    rank="pm_gain", **_S71))

# --- Z. PART-DAY SIGNAL CAMPAIGN on the ADOPTED W109 baseline (user
# 2026-08-08: "adopt W109 ... try to reach similar results to [the
# hindsight configs] while not using future signals and only using
# current signal instead of full day signal. also, test other part-day
# signals that might help.")
# All fully causal: honest sim stack + first-crossing + 5-min cadence
# + filed halal. causal_cut removes the LAST residue (the top-8 walk
# cut was still by full-day gain, even in W109).
_ZH = dict(_W35, vol_frac_causal=True, halt_aware=True, pm_spread_bps=50.0)
_ZKW = dict(pool="novol", gain_causal=True, rescan_min=5,
            halal_filing=True)


def Z(zid, desc, **kw):
    kw2 = dict(_ZKW)
    kw2.update(kw)
    return C23(zid, desc, sim=dict(_ZH), **kw2, **_S71)


EXPERIMENTS += [
    Z("Z000", "W109 identity (helper check)", rank="pm_gain"),
    # rank families, each with the causal cut
    Z("Z001", "W110 cand: pm_gain rank + causal cut",
      rank="pm_gain", causal_cut=True),
    Z("Z002", "pm_high_gain rank + causal cut",
      rank="pm_high_gain", causal_cut=True),
    Z("Z003", "pm_dollar_volume rank + causal cut",
      rank="pm_dvol", causal_cut=True),
    Z("Z004", "pm_pressure rank + causal cut",
      rank="pm_pressure", causal_cut=True),
    Z("Z005", "earliest +10% crossing rank + causal cut",
      rank="cross_time", causal_cut=True),
    Z("Z006", "coil (7AM near pm-high) rank + causal cut",
      rank="coil", causal_cut=True),
    Z("Z007", "pm turnover (pm$ / mcap) rank + causal cut",
      rank="turnover", causal_cut=True),
    Z("ZC00", "CONTROL random rank + causal cut (must not win)",
      rank="random", causal_cut=True),
    # part-day gates on the Z001 base (adjacency sweep)
    Z("Z010", "Z001 + only names crossing before 09:00",
      rank="pm_gain", causal_cut=True, cross_before=(9, 0)),
    Z("Z011", "Z001 + only names crossing before 10:00",
      rank="pm_gain", causal_cut=True, cross_before=(10, 0)),
    Z("Z012", "Z001 + only names crossing before 11:00",
      rank="pm_gain", causal_cut=True, cross_before=(11, 0)),
    Z("Z013", "Z001 + calm-gap tightened to 15",
      rank="pm_gain", causal_cut=True, calm_gap=15.0),
    Z("Z014", "Z001 + calm-gap loosened to 25",
      rank="pm_gain", causal_cut=True, calm_gap=25.0),
]

# Z phase 2 (after walk-16 backfill): compose the phase-1 winners
# (coil, pm_pressure) + additive levers (deeper walk, fallback re-pick).
# Phase-1 rejects: crossing-time gates (monotone loss), calm-gap 15.
from datetime import time as _zt
EXPERIMENTS += [
    Z("Z100", "coil rank, walk 12", rank="coil", causal_cut=True, walk=12),
    Z("Z101", "coil-group + pressure order", rank="coil_press",
      causal_cut=True),
    Z("Z102", "z(coil)+z(pressure) blend", rank="zcoilpress",
      causal_cut=True),
    Z("Z103", "coil + fallback re-pick at 10:00", rank="coil",
      causal_cut=True, fallback=(_zt(10, 0), "time")),
    Z("Z104", "coil-group/pressure, walk 12", rank="coil_press",
      causal_cut=True, walk=12),
    Z("Z105", "coil + calm-gap 25", rank="coil", causal_cut=True,
      calm_gap=25.0),
]

# Z2xx: phase-1 winners RE-RUN after the walk-16 backfill (coverage
# was walk-8 when Z001/Z004/Z006 first ran -- the delta is the pure
# coverage effect on the causal cut).
EXPERIMENTS += [
    Z("Z201", "pm_gain + causal cut (walk-16 coverage)",
      rank="pm_gain", causal_cut=True),
    Z("Z204", "pm_pressure + causal cut (walk-16 coverage)",
      rank="pm_pressure", causal_cut=True),
    Z("Z206", "coil + causal cut (walk-16 coverage)",
      rank="coil", causal_cut=True),
]

# Z300: clean re-run of the phase-2 leader (coil walk-12) -- its first
# run (Z100, $701,728) started while the last ~10% of walk-16 bars were
# still downloading, so the adoption number needs a full-coverage pass.
EXPERIMENTS.append(Z("Z300", "coil rank walk 12, FULL walk-16 coverage",
                     rank="coil", causal_cut=True, walk=12))

# Z4xx: TWLO case-study family (2026-08-09). The Aug-7 winner was an
# earnings-gap: Q2 beat AMC Aug-6, 6th straight beat, quiet coiled
# premarket, deep book. Each trait tested separately on the Z300 base.
EXPERIMENTS += [
    Z("Z400", "earnings-day names ONLY", rank="coil", causal_cut=True,
      walk=12, earnings_gate=True),
    Z("Z401", "earnings-day priority, coil within", rank="coil",
      causal_cut=True, walk=12, earnings_rank=True),
    Z("Z402", "NON-earnings names only (complement)", rank="coil",
      causal_cut=True, walk=12, earnings_gate=False),
    Z("Z403", "earnings-day + >=3 straight beats", rank="coil",
      causal_cut=True, walk=12, earnings_gate=True, beats_min=3),
    Z("Z404", "quiet-coil rank (asc pm $vol tiebreak)",
      rank="coil_quiet", causal_cut=True, walk=12),
    Z("Z405", "liquid-coil rank (desc avg $vol tiebreak)",
      rank="coil_liquid", causal_cut=True, walk=12),
    Z("ZC40", "CONTROL hash-shuffled earnings flags", rank="coil",
      causal_cut=True, walk=12, earnings_gate=True,
      earnings_shuffle=True),
]

# Z406/Z407: causal tiebreaks for the coil group -- Z404/Z405 exposed
# that mode "coil" breaks ties by FULL-DAY gain (a future signal inside
# Z300 worth ~$150-200k). These test the two remaining causal orders.
EXPERIMENTS += [
    Z("Z406", "coil group + PM-gain order (causal)", rank="coil_pmgain",
      causal_cut=True, walk=12),
    Z("Z407", "continuous coil, no tiebreak", rank="coil_cont",
      causal_cut=True, walk=12),
]

# --- FILL REALISM on C35 (user 2026-08-07: "check the buy and exit if
# they are realistic"). The backtest fills breakouts AT the trigger; a
# real resting stop-limit fills somewhere between the trigger and its
# limit, or not at all on a gap-through. orb_fill_mode="close" is the
# pessimistic bound (fill at the breakout bar's CLOSE, i.e. the worst
# price inside that minute). slippage_bps charges both sides.
_C35 = dict(_C34, entry_ticket_schedule=(1, 25_000.0))
EXPERIMENTS.append(C23("S100", "C35 + pessimistic ORB fill (bar close)",
    sim=dict(_C35, orb_fill_mode="close"), **_S71))
EXPERIMENTS.append(C23("S101", "C35 + 10bps slippage per side",
    sim=dict(_C35, slippage_bps=10.0), **_S71))
EXPERIMENTS.append(C23("S102", "C35 + 25bps slippage per side",
    sim=dict(_C35, slippage_bps=25.0), **_S71))
EXPERIMENTS.append(C23("S103", "C35 + 50bps slippage (penny-spread worst case)",
    sim=dict(_C35, slippage_bps=50.0), **_S71))
EXPERIMENTS.append(C23("S104", "C35 WORST CASE: close fills + 25bps",
    sim=dict(_C35, orb_fill_mode="close", slippage_bps=25.0), **_S71))

BYID = {e["id"]: e for e in EXPERIMENTS}



from datetime import time as _dt2
EXPERIMENTS += [
    C21("X335", "monster mode: $2k by 9:30 -> no more banking",
        sim=dict(monster_mode=(2000, _dt2(9, 30)))),
    C21("X336", "monster mode + trail floor 40%",
        sim=dict(monster_mode=(2000, _dt2(9, 30), 40))),
    C21("X337", "monster mode $3k tell",
        sim=dict(monster_mode=(3000, _dt2(9, 30)))),
    C21("X338", "monster mode $1k tell",
        sim=dict(monster_mode=(1000, _dt2(9, 30)))),
]
BYID = {e["id"]: e for e in EXPERIMENTS}



EXPERIMENTS += [
    C21("X340", "news-priority rank (Y1 evidence only)", rank="news"),
    C21("X341", "news REQUIRED (Y1 evidence only)", rank="news",
        news_required=True),
]
BYID = {e["id"]: e for e in EXPERIMENTS}



EXPERIMENTS += [
    C21("X342", "day-2 continuation: yesterday pick >$2k ranks first",
        rank="day2", day2_thresh=2000),
    C21("X343", "day-2 continuation: yesterday MONSTER >$10k first",
        rank="day2", day2_thresh=10000),
]
BYID = {e["id"]: e for e in EXPERIMENTS}


# --------------------------------------------------------------- driver
def load_results():
    """Merged view across all shard files (workers write disjoint ids)."""
    out = {}
    for f in sorted((ROOT / "data" / "massive").glob("x100_results*.json")):
        try:
            out.update(json.loads(f.read_text()))
        except Exception:
            pass
    return out


def shard_file():
    for i, a in enumerate(sys.argv):
        if a == "--shard" and i + 1 < len(sys.argv):
            return (ROOT / "data" / "massive"
                    / f"x100_results_s{sys.argv[i + 1]}.json")
    return RES_F


def report():
    res = load_results()
    b0 = {lb: res.get(f"X091|{lb}", {}).get("total", 0)
          for lb in ("year", "y2025")}
    rows = []
    for e in EXPERIMENTS:
        r1 = res.get(f"{e['id']}|year")
        r2 = res.get(f"{e['id']}|y2025")
        if not r1 or not r2:
            continue
        d1 = r1["total"] - b0["year"]
        d2 = r2["total"] - b0["y2025"]
        rows.append((d1 + d2, e["id"], e["desc"], r1, r2, d1, d2))
    rows.sort(reverse=True)
    lines = ["# X100 results (sorted by combined delta vs X091 anchor)",
             "", "| id | change | Y1 total | Y2 total | dY1 | dY2 | "
             "dComb | negm | PASS |", "|---|---|---|---|---|---|---|---|---|"]
    for dc, xid, desc, r1, r2, d1, d2 in rows:
        ok = (d1 > 0 and d2 > 0 and dc >= 30000
              and r1["negm"] <= 0 + res.get("X091|year", {}).get("negm", 0)
              and r2["negm"] <= res.get("X091|y2025", {}).get("negm", 1))
        lines.append(
            f"| {xid} | {desc} | {r1['total']:+,} | {r2['total']:+,} | "
            f"{d1:+,} | {d2:+,} | {dc:+,} | {r1['negm']}/{r2['negm']} | "
            f"{'PASS' if ok else ''} |")
    MD_F.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:40]))
    print(f"...({len(rows)} rows) -> X-RESULTS.md")


def main():
    args = sys.argv[1:]
    if "--report" in args:
        report()
        return
    ids = None
    for i, a in enumerate(args):
        if a == "--ids" and i + 1 < len(args):
            ids = args[i + 1].split(",")
    cache_only = "--cache-only" in args
    sf = shard_file()
    mine = json.loads(sf.read_text()) if sf.exists() else {}
    todo = [e for e in EXPERIMENTS
            if (ids is None or e["id"] in ids)
            and not (cache_only and e.get("F"))]
    for e in todo:
        if (e.get("rank") == "news"
                and not any((ROOT / "data" / "news_cache").glob("*.json"))):
            print(f"{e['id']}: SKIP (news cache not built)", flush=True)
            continue
        for label in ("year", "y2025"):
            key = f"{e['id']}|{label}"
            if key in load_results():
                continue
            out = run_experiment(dict(e), label)
            mine[key] = out
            sf.write_text(json.dumps(mine))
            print(f"{e['id']:>5} {label:<6} {out['days']:>4}d "
                  f"${out['total']:>+11,} ${out['avg']:>+7,}/d "
                  f"{out['negm']}/{out['nmonths']}  [{e['desc']}]",
                  flush=True)


if __name__ == "__main__":
    main()
