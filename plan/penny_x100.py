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

_spec = importlib.util.spec_from_file_location(
    "axb", ROOT / "plan" / "penny_ax11b_massive.py")
axb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(axb)
ps = axb.ps

M1 = ROOT / "data" / "massive" / "m1"
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
        from trading import massive
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


def load_by_day(label, min_hist):
    gap = json.loads(
        (ROOT / f"data/massive/gappers2_{label}.json").read_text())
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
            "turnover", "random", "lag"):
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
    by_day = load_by_day(label, spec.get("min_hist", 50))
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
                    w = df[(df.index.time >= W_START)
                           & (df.index.time < dtime(13, 0))]
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
                committed = (c, w, df)
                com_idx = idx
                break
            if committed is None:
                continue
            c, w, df = committed
            if spec.get("pm_break"):
                pm = premkt_metrics(df, c["prev_close"])
                if pm:
                    pmh = c["prev_close"] * (1 + pm["pm_high_gain"] / 100)
                    spec.setdefault("sim", {})["extra_break_high"] = pmh
            tr = sim_window(w, c, spec)
            if spec.get("pm_break"):
                spec["sim"].pop("extra_break_high", None)

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
                        df2 = dfs.get(c2["symbol"]) or get_lazy(c2["symbol"],
                                                                date)
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
                        df2 = dfs.get(c2["symbol"]) or get_lazy(c2["symbol"],
                                                                date)
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
        df2 = dfs.get(c2["symbol"]) or get_lazy(c2["symbol"], date)
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
