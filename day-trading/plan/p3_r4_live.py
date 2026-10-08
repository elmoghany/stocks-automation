"""PAPER-3BOOK R4-FIX (2026-10-08): backtest + replay tests of the R4 LIVE
track (plan/p3_r4.live_screen / live_step). Paper only; reads caches, never
places anything.

  --pinned   PINNED filter effect on the R4 backtest legs (the 965 published
             legs of plan/pa_out/cp_r4_legs.json and the live-config model
             legs re-run through p3_r4.run_live at $10k), at 0.6% and 0.4%
  --expect   the LIVE policy backtested over the 444 in-sample days (+ the 22
             Aug-2026 OOS days reported apart). The live spread veto is
             approximated from bars by the LEGACY-9 causal estimator
             (max(CS, AR) on the 30 bars <= t, lm9_feat.half_at): refuse when
             the implied full spread 2 x half > 50 bps (= LEGACY-15's "live
             0.5% cap" proxy); the literal reading (half > 50 bps) is reported
             as a sensitivity. A pick that does not print within 5 minutes is
             refused as HALT (the bar proxy of a halted / dead quote). Writes
             data/paper/parity/r4_live.json and p3_expectations.json "r4_live"
  --replay   minute-by-minute replay of live_step on cached days (scan
             snapshots emulated from bars, arrays physically truncated at
             now-1, the watcher's watch_exit closing legs) with a simulated
             veto; checks it matches the event sim and that the live book
             trades at the same / next grid after a refused or halted pick
  --oct      2026-10-05..10-08 from the saved scan snapshots + agent bars

    python plan/p3_r4_live.py --pinned --expect --replay --oct
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as CL                                         # noqa: E402
import cp_run as CR                                         # noqa: E402
import cp_sim as S                                          # noqa: E402
import p3_lib as P                                          # noqa: E402
import p3_parity_r4 as T                                    # noqa: E402
import p3_r4 as R                                           # noqa: E402

OUT = P.DATA / "paper" / "parity" / "r4_live.json"
COST = 15.0
FILL_MAX = 5           # a pick must print within 5 min of t+1 (HALT proxy)
SPREAD_PROXY = 50.0    # bps, full spread = 2 x LEGACY-9 half


def half_bps(day, i, t):
    from lm9_feat import half_at
    return float(half_at(day, i, t + 1)[0])          # bars [t-29, t]


def proxy_check(mode):
    """Book-check proxy from bars. mode: None | 'spread' (2*half > 50) |
    'half' (half > 50, literal)."""
    def f(day, i, t):
        if mode is None:
            return None
        h = half_bps(day, i, t)
        x = 2 * h if mode == "spread" else h
        return "SPREAD" if x > SPREAD_PROXY else None
    return f


def halt_proxy(day, i, t):
    em, _ = R.next_print(day, i, t + 1, CL.NMIN, limit=FILL_MAX)
    return em


def live_sim(day, Fd, date, check, cfgr=None, pin_thr=None, now=CL.NMIN,
             cfg=R.CFG_LIVE, log=None):
    """Event-driven LIVE track over one day (the same live_screen; book
    checks by `check`; HALT = no print within FILL_MAX; model fill = open
    of that print; R4 exits by walk_exit). Returns legs."""
    cfgr = cfgr or R.cfg_for(cfg, Fd, date)
    gidx = {int(m): k for k, m in enumerate(Fd["grid"])}
    legs, t, deployed = [], int(cfg["t_start"]), 0.0
    while len(legs) < cfg["ntickets"] and t < cfg["cutoff"]:
        if t not in gidx:
            t += 1
            continue
        if deployed + P.TICKET > R.DAY_CAP:
            break
        rows = R.live_screen(day, Fd, gidx[t], cfgr, pin_thr=pin_thr)
        leg = None
        for r in rows:
            if r["verdict"] != "OK":
                if log is not None:
                    log.append((t, r["sym"], r["verdict"]))
                continue
            i = r["i"]
            why = check(day, i, t) if check else None
            if why is None and halt_proxy(day, i, t) is None:
                why = "HALT"
            if why:
                if log is not None:
                    log.append((t, r["sym"], why))
                continue
            # LIVE size: floor(min($10k, shares_cap x px) / px), shares_cap
            # = 20% of the 5 bars <= t (what the agent sees at wall t+1);
            # model fill = open of the first print after t (<= 5 min)
            em = halt_proxy(day, i, t)
            px = float(day.o[i, em])
            sh = int(min(P.TICKET / px, r["shares_cap"]))
            xm, xpx, why, _ = R.walk_exit(day, i, em, px, now, cfg)
            if not (px >= cfg["min_px"]) or sh < 1 or why == "NOFLAT":
                if log is not None:
                    log.append((t, r["sym"], "NOFILL"))
                continue
            leg = dict(i=i, sym=r["sym"], t=int(t), entry_min=int(em),
                       entry=px, shares=sh, exit_min=None if xm is None
                       else int(xm), exit=xpx, reason=why, open=xm is None,
                       gross=None if xm is None else (xpx - px) * sh)
            break
        if leg is None:
            t += cfg["step"]
            continue
        legs.append(leg)
        if leg["open"]:
            break
        deployed += leg["shares"] * leg["entry"]
        # a "flatten" leg whose last print came before 15:00 is only known
        # to be over at 15:00 (live holds it until the watcher's flatten);
        # cp_sim/run_live release it at its last print (a look-ahead the
        # parity track keeps, the live sim must not)
        rel = cfg["exit_end"] if leg["reason"] == "flatten" else leg["exit_min"]
        t = max(t + cfg["step"], rel + 1)
    return legs


def net(lg, bps=COST):
    return lg["gross"] - (lg["entry"] + lg["exit"]) * lg["shares"] * bps / 1e4


def stats(legs, nd):
    if not legs:
        return dict(n=0)
    g = np.array([x["gross"] for x in legs])
    n15 = np.array([net(x) for x in legs])
    s = np.sort(n15)
    return dict(n=len(legs), trades_per_day=round(len(legs) / nd, 3),
                gross_per_trade=round(float(g.mean()), 2),
                per_trade=round(float(n15.mean()), 2),
                per_day=round(float(n15.sum()) / nd, 2),
                total=round(float(n15.sum()), 2),
                per_trade_ex_top5=round(float(s[:-5].mean()), 2)
                if len(s) > 5 else None,
                ex_top5_total=round(float(s[:-5].sum()), 2)
                if len(s) > 5 else None,
                top5=[round(float(v), 2) for v in s[-5:][::-1]])


# ------------------------------------------------------------ the pass
VARIANTS = {
    # name: (pin_thr or None = filter off, proxy mode)
    "live_pin06_spread": (0.006, "spread"),
    "live_pin04_spread": (0.004, "spread"),
    "live_nopin_spread": (9e-9, "spread"),
    "live_pin06_half": (0.006, "half"),
    "live_pin04_half": (0.004, "half"),
    "live_pin06_noveto": (0.006, None),
    "live_nopin_noveto": (9e-9, None),
}


def one_day(d, want_variants=True):
    fd = T.FullDay(d)
    day = fd.day_at(CL.NMIN)
    Fd = R.fd_from_bars(day)
    model, _ = R.run_live(day, Fd, CL.NMIN, tickets=R.TICKETS_LIVE,
                          cfg=R.CFG_LIVE, date=d)
    for lg in model:
        lg["date"] = d
        lg["range15"] = R.pinned_range(day, lg["i"], lg["t"])
        lg["half"] = half_bps(day, lg["i"], lg["t"])
    out = dict(model=model, var={})
    if want_variants:
        cfgr = R.cfg_for(R.CFG_LIVE, Fd, d)
        for k, (thr, mode) in VARIANTS.items():
            lg = live_sim(day, Fd, d, proxy_check(mode), cfgr=cfgr,
                          pin_thr=thr)
            for x in lg:
                x["date"] = d
            out["var"][k] = lg
    return out, day


def clean(lg):
    return {k: (v.item() if hasattr(v, "item") else v) for k, v in lg.items()
            if k != "i"}


def run_pass(dates):
    t0 = time.time()
    model, var = [], {k: [] for k in VARIANTS}
    pub = json.loads(T.LEGS.read_text())["legs"]["R4"]
    pub_by = {}
    for x in pub:
        pub_by.setdefault(x["date"], []).append(x)
    for n, d in enumerate(dates):
        o, day = one_day(d)
        model += o["model"]
        for k in VARIANTS:
            var[k] += o["var"][k]
        idx = {s: i for i, s in enumerate(day.syms)}
        for x in pub_by.get(d, []):
            i = idx.get(x["sym"])
            tt = int(max(g for g in R.GRID if g < x["entry_min"]))
            x["t_est"] = tt
            x["range15"] = None if i is None else R.pinned_range(day, i, tt)
        if n % 50 == 0:
            print(f"  {n}/{len(dates)} {d} {time.time() - t0:.0f}s",
                  flush=True)
    return model, var, pub


def pinned_report(model, pub):
    rep = {}
    for lab, legs, size in (("published_965", pub, "dump size"),
                            ("live_cfg_model_10k", model, "$10k")):
        g = sorted(legs, key=lambda x: -x["gross"])
        top5 = [(x["date"], x["sym"], round(x["gross"], 2)) for x in g[:5]]
        r = {"legs": len(legs), "size": size, "top5_by_gross": top5}
        for thr in (0.006, 0.004):
            rm = [x for x in legs if x.get("range15") is not None
                  and x["range15"] < thr]
            r[f"thr_{thr}"] = dict(
                removed=len(rm), removed_pct=round(100 * len(rm) / len(legs), 2),
                removed_gross=round(sum(x["gross"] for x in rm), 2),
                removed_gross_per_10k=round(sum(
                    x["gross"] / (x["entry"] * x["shares"]) * 1e4 for x in rm), 2),
                removed_top5=[k for k in top5 if any(
                    (x["date"], x["sym"]) == k[:2] and round(x["gross"], 2) == k[2]
                    for x in rm)],
                removed_list=[(x["date"], x["sym"], round(x["range15"] * 100, 3),
                               round(x["gross"], 2)) for x in rm][:60])
        rep[lab] = r
    return rep


def main():
    a = sys.argv[1:]
    res = P.read_json(OUT, {}) or {}
    if "--pinned" in a or "--expect" in a:
        ins, oos = CR.dates(), CR.dates(oos=True)
        print("pass: in-sample", len(ins), flush=True)
        m_in, v_in, pub = run_pass(ins)
        print("pass: OOS", len(oos), flush=True)
        m_oos, v_oos, _ = run_pass(oos)
        rep = pinned_report(m_in, pub)
        res["pinned"] = rep
        # threshold rule (user): > 5% of legs or any top-5 tail leg removed
        # at 0.6% -> use 0.4%
        bad = any(rep[k]["thr_0.006"]["removed_pct"] > 5
                  or rep[k]["thr_0.006"]["removed_top5"] for k in rep)
        res["pin_threshold"] = 0.004 if bad else 0.006
        res["pin_rule"] = ("0.6% removes > 5% of legs or a top-5 tail leg -> "
                           "tightened to 0.4%" if bad else
                           "0.6% kept (<= 5% of legs, no top-5 tail leg)")
        print(json.dumps({k: {kk: (vv if kk != "removed_list" else len(vv))
                              for kk, vv in v.items()} if isinstance(v, dict)
                          else v for k, v in rep.items()}, indent=1,
                         default=str), flush=True)
        print("PIN THRESHOLD", res["pin_threshold"], res["pin_rule"])
        nd_in, nd_oos = len(ins), len(oos)
        res["model_track"] = dict(insample=stats(m_in, nd_in),
                                  oos_aug2026=stats(m_oos, nd_oos))
        res["variants"] = {k: dict(insample=stats(v_in[k], nd_in),
                                   oos_aug2026=stats(v_oos[k], nd_oos))
                           for k in VARIANTS}
        res["days"] = dict(insample=nd_in, oos=nd_oos)
        res["notes"] = (
            "LIVE-track policy backtest (p3_r4.live_screen through "
            "p3_r4_live.live_sim): model fills (open of the first print "
            "after t, within 5 min, else HALT), $10k, 15 bps/side. Spread "
            "veto proxy = LEGACY-9 max(CS,AR) on bars [t-29,t]: 'spread' "
            "refuses 2*half > 50 bps (the live 0.5% full-spread cap, "
            "LEGACY-15's proxy); 'half' refuses half > 50 bps (literal). "
            "Depth (25%) is not modelled.")
        for k in res["variants"]:
            print(k, res["variants"][k], flush=True)
        print("model", res["model_track"], flush=True)
        thr = res["pin_threshold"]
        key = f"live_pin{'06' if thr == 0.006 else '04'}_spread"
        res["chosen"] = key
        OUT.write_text(json.dumps(res, indent=1, default=float))
        expf = P.DATA / "paper" / "p3_expectations.json"
        exp = P.read_json(expf, {}) or {}
        v = res["variants"][key]["insample"]
        vo = res["variants"][key]["oos_aug2026"]
        exp["r4_live"] = dict(
            per_trade=v["per_trade"], per_day=v["per_day"],
            trades_per_day=v["trades_per_day"],
            gross_per_trade=v["gross_per_trade"],
            backtest_per_trade_ex_top5=v["per_trade_ex_top5"],
            pin_threshold=thr, variant=key,
            oos_aug2026=dict(per_trade=vo.get("per_trade"),
                             trades_per_day=vo.get("trades_per_day"),
                             total=vo.get("total")),
            built=P.now_et().isoformat(),
            note="R4 LIVE track (R4-FIX 2026-10-08): first of the ranked top "
                 "8 passing gap gate, PINNED filter, halt, spread <= 0.5% "
                 "(bar proxy: LEGACY-9 2*half > 50 bps) at each grid while "
                 "flat; $10k; 15 bps/side; 444 in-sample days "
                 "(plan/p3_r4_live.py, data/paper/parity/r4_live.json). The "
                 "'r4' key stays the PARITY/MODEL track expectation.")
        if "r4" in exp:
            exp["r4"]["role"] = "PARITY/MODEL track (unchanged backtest)"
        P.write_atomic(expf, exp)
        print("r4_live expectation:", exp["r4_live"], flush=True)
    if "--replay" in a:
        res["replay"] = replay_tests()
        OUT.write_text(json.dumps(res, indent=1, default=float))
    if "--oct" in a:
        res["oct_replay"] = oct_replay()
    if "--oct-full" in a:                 # 10-08 with full-day RH bars
        res["oct_replay_1008_full"] = oct_replay(
            ("2026-10-08",), a[a.index("--oct-full") + 1], proxy=True)
        OUT.write_text(json.dumps(res, indent=1, default=float))


# ------------------------------------------------------------ replay tests
def replay_day(d, veto, pin_thr=None, minutes=None):
    """Minute-by-minute LIVE track through p3_r4.live_step, as the session
    would run it: emulated scan snapshots <= now-1, physically truncated
    bars, veto(sym, t, full_day, i) = the simulated book check at wall t+1,
    the r4 watcher's watch_exit closing the leg. Returns (legs, events)."""
    fd = T.FullDay(d)
    full = fd.day_at(CL.NMIN)
    snaps = T.snaps_from_bars(full, CL.NMIN)
    hist, refused, legs, ev = [], {}, [], []
    open_st = None
    minutes = minutes or range(CL.M_0935 + 1, CL.M_1500 + 3)
    sidx = {s: i for i, s in enumerate(full.syms)}
    for now in minutes:
        day = fd.day_at(now)
        if open_st is not None:                         # the watcher
            i = sidx[open_st["sym"]]
            bars = tuple(np.asarray(getattr(day, k)[i]) for k in "ohlc") + \
                (np.asarray(day.v[i]),)
            ex = R.watch_exit(d, open_st, bars, now)
            if ex is not None and ex.get("px") is not None:
                lg = legs[-1]
                lg.update(exit=ex["px"], exit_min=ex["min"], reason=ex["reason"],
                          entry=open_st["model_entry"],
                          entry_min=open_st["model_entry_min"], open=False)
                lg["gross"] = (lg["exit"] - lg["entry"]) * lg["shares"]
                hist[-1].update(open=False, exit_min=now - 1)
                ev.append((P.hhmm(now), "EXIT", lg["sym"], lg["reason"]))
                open_st = None
        if open_st is not None or now - 1 >= R.CFG_LIVE["cutoff"] + 5:
            continue
        Fd = R.fd_from_snaps(day, [x for x in snaps if x["t"] <= now - 1])
        Fd["has_bars"][:] = True
        for _ in range(12):
            st = R.live_step(day, Fd, now, hist, refused, d, pin_thr=pin_thr)
            if st["state"] != "PICK":
                if st["state"] == "NONE":
                    ev.append((P.hhmm(now), "NONE", P.hhmm(st["t"]),
                               [f"{r['sym']}:{r['verdict']}" for r in st["rows"]]))
                break
            t, sym, i = st["t"], st["sym"], sidx[st["sym"]]
            why = veto(sym, t, full, i)
            if why:
                refused[(sym, t)] = why
                ev.append((P.hhmm(now), "REFUSED", sym, P.hhmm(t), why))
                continue
            # entered at wall now (t+1); model fill = next print after t
            em, _ = R.next_print(full, i, t + 1, CL.NMIN)
            px = float(full.o[i, em])
            sh = int(min(P.TICKET / px, st["shares_cap"]))
            open_st = dict(sym=sym, decision_min=t)
            legs.append(dict(sym=sym, t=t, shares=sh, open=True, date=d))
            hist.append(dict(sym=sym, t=t, open=True, notional=sh * px))
            ev.append((P.hhmm(now), "ENTER", sym, P.hhmm(t)))
            break
    return legs, ev


def replay_tests():
    """(1) consistency: replay == event sim with the same simulated veto;
    (2) a refused / halted pick -> the live book trades at the same grid
    (next candidate) or the next grid, never idles behind the model."""
    out = {}
    ins = CR.dates()
    pub = json.loads(T.LEGS.read_text())["legs"]["R4"]
    cnt = {}
    for x in pub:
        cnt[x["date"]] = cnt.get(x["date"], 0) + 1
    busy = sorted(cnt, key=lambda d: -cnt[d])[:4]
    days = sorted(set(busy + ins[::111][:4]))
    out["days"] = days
    thr = R.PIN_THR

    def mk_veto(kind):
        grids = set()

        def v(sym, t, full, i):
            if kind == "proxy":
                why = proxy_check("spread")(full, i, t)
                if why:
                    return why
            elif kind == "first_at_grid":       # the top pick of EVERY grid
                if t not in grids:              # is refused (SPREAD)
                    grids.add(t)
                    return "SPREAD"
            elif kind == "halt_0935":           # every name halted at 09:35
                if t == CL.M_0935:
                    return "HALT"
            if halt_proxy(full, i, t) is None:
                return "HALT"
            return None
        return v

    cons = []
    for kind in ("proxy", "halt_0935", "first_at_grid"):
        for d in days:
            veto = mk_veto(kind)
            legs, ev = replay_day(d, veto, pin_thr=thr)
            fd = T.FullDay(d)
            day = fd.day_at(CL.NMIN)
            # same universe/coil source as the replay (emulated snapshots,
            # each grid reading snapshots <= that grid only): isolates the
            # clock logic. The bar-universe sim is reported alongside.
            Fs = R.fd_from_snaps(day, T.snaps_from_bars(day, CL.NMIN))
            Fs["has_bars"][:] = True
            veto2 = mk_veto(kind)
            sim = live_sim(day, Fs, d,
                           lambda dd, i, t: veto2(str(dd.syms[i]), t, dd, i),
                           pin_thr=thr)
            veto3 = mk_veto(kind)
            simb = live_sim(day, R.fd_from_bars(day), d,
                            lambda dd, i, t: veto3(str(dd.syms[i]), t, dd, i),
                            pin_thr=thr)
            a_ = [(x["sym"], x["t"], x.get("exit_min")) for x in legs]
            b_ = [(x["sym"], x["t"], x.get("exit_min")) for x in sim]
            c_ = [(x["sym"], x["t"], x.get("exit_min")) for x in simb]
            ga = sum(x.get("gross") or 0 for x in legs)
            gb = sum(x.get("gross") or 0 for x in sim)
            row = dict(kind=kind, day=d, replay=len(a_), sim=len(b_),
                       identical=a_ == b_ and abs(ga - gb) < 1e-6,
                       bar_universe_sim=len(c_), bar_universe_same=a_ == c_,
                       replay_legs=[(s, P.hhmm(t), P.hhmm(x) if x else None)
                                    for s, t, x in a_])
            if kind != "proxy":
                row["events"] = [e for e in ev if e[1] in
                                 ("REFUSED", "ENTER", "EXIT")][:14]
            if kind == "halt_0935":
                first = next((e for e in ev if e[1] == "ENTER"), None)
                row["first_entry"] = first
                row["traded_by_0945"] = bool(first) and \
                    P.parse_hhmm(first[3]) <= CL.M_0935 + 10
            if kind == "first_at_grid":
                ref = [e for e in ev if e[1] == "REFUSED"]
                ent = [e for e in ev if e[1] == "ENTER"]
                row["same_grid_fallthrough"] = sum(
                    1 for r in ref if any(e[3] == r[3] and e[0] == r[0]
                                          for e in ent))
            cons.append(row)
            print("  REPLAY", kind, d, "replay", len(a_), "sim", len(b_),
                  "IDENTICAL" if a_ == b_ else f"DIFF {a_} vs {b_}",
                  row.get("first_entry", ""), flush=True)
    out["cases"] = cons
    out["all_identical"] = all(r["identical"] for r in cons)
    out["bar_universe_same"] = sum(r["bar_universe_same"] for r in cons)
    out["halt_0935_traded_by_0945"] = [r["traded_by_0945"] for r in cons
                                       if r["kind"] == "halt_0935"]
    # (3) the 10-08 failure mode: model holds a name live refused; live
    # keeps trading. Count, on the proxy days, live entries made while the
    # MODEL track was holding a different name.
    print("REPLAY all identical:", out["all_identical"], flush=True)
    return out


# ------------------------------------------------------------ Oct replay
def oct_replay(days=("2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"),
               bars_dir=None, proxy=False):
    """2026-10-05..10-08 from the saved scan snapshots (data/paper/r4/
    snaps_*.jsonl) and the agent's bars (data/rh_bars). Coverage is partial:
    the sessions ingested scans only at some grids (every grid 09:35-10:30
    on 10-08) and fetched bars only for the names they needed. Book checks
    replayed from the logged vetoes (same name, same grid) where they
    exist; otherwise the logged quote of that minute (quotes file holds the
    last quote only) is not available -> 'unchecked' (assumed PASS)."""
    out = {}
    if bars_dir:                     # full-day bars fetched after the close
        P.RH_BARS = Path(bars_dir)
    for d in days:
        snaps = [json.loads(x) for x in
                 R.snaps_path(d).read_text().splitlines() if x.strip()]
        vet = P.read_json(R.vetoes_path(d), []) or []
        vmap = {}
        for v in vet:
            vmap.setdefault((v["sym"], v["decision"]), []).append(v)
        syms, pcs = [], []
        for x in snaps:
            for s, r in x["rows"].items():
                if s not in syms:
                    syms.append(s)
                    pcs.append(r["pc"])
        hist, refused, ev, open_st = [], {}, [], None
        grids = sorted(int(x["t"]) for x in snaps)
        for now in range(CL.M_0935 + 1, CL.M_1500 + 3):
            feed = P.LiveFeed(d, now)
            day = R.make_day(syms, pcs, feed)
            if open_st is not None:
                b = feed.bars(open_st["sym"])
                ex = R.watch_exit(d, open_st, b, now)
                if ex is not None and ex.get("px") is not None:
                    me = open_st.get("model_entry")
                    sh = int(P.TICKET // me) if me else 0
                    ev.append((P.hhmm(now), "EXIT", open_st["sym"],
                               ex["reason"], round(ex["px"], 4),
                               "entry", me, "gross_10k",
                               round((ex["px"] - me) * sh, 2) if me else None))
                    hist[-1].update(open=False, exit_min=now - 1)
                    open_st = None
                elif now >= CL.M_1500 + 2:
                    ev.append((P.hhmm(now), "NO-EXIT (bars end)",
                               open_st["sym"], open_st.get("model_entry")))
                continue
            if (now - 1) not in grids:
                continue
            Fd = R.fd_from_snaps(day, [x for x in snaps if x["t"] <= now - 1])
            for _ in range(12):
                st = R.live_step(day, Fd, now, hist, refused, d)
                if st["state"] == "NEED_DATA":
                    ev.append((P.hhmm(now), "NO-BARS", st["need_bars"]))
                    # names the session never fetched: skip them
                    for s in st["need_bars"]:
                        Fd["has_bars"][list(day.syms).index(s)] = True
                        refused[(s, st["t"])] = "NOBARS"
                    continue
                if st["state"] != "PICK":
                    if st.get("rows") is not None:
                        ev.append((P.hhmm(now), st["state"],
                                   [f"{r['sym']}:{r['verdict']}"
                                    for r in st["rows"]]))
                    break
                t, sym = st["t"], st["sym"]
                chk = vmap.get((sym, P.hhmm(t)))
                if chk and all(c["result"] == "VETO" for c in chk):
                    why = chk[0].get("reason") or chk[0]["why"][:40]
                elif chk is None and sym in ("SMXT", "INHD") and \
                        P.hhmm(t) in ("09:35", "10:05"):
                    why = "HALT (session notes)"
                else:
                    why = None
                    if proxy and not chk:    # no live check logged: the
                        i = list(day.syms).index(sym)     # bar proxies
                        full = R.make_day(syms, pcs, P.LiveFeed(d, CL.NMIN))
                        why = proxy_check("spread")(full, i, t)
                        if why is None and halt_proxy(full, i, t) is None:
                            why = "HALT (no print in 5 min)"
                        if why:
                            why += " (bar proxy)"
                if why:
                    refused[(sym, t)] = why
                    ev.append((P.hhmm(now), "REFUSED", sym, P.hhmm(t), why))
                    continue
                open_st = dict(sym=sym, decision_min=t)
                hist.append(dict(sym=sym, t=t, open=True))
                ev.append((P.hhmm(now), "ENTER", sym, P.hhmm(t),
                           "checked PASS" if chk else "unchecked",
                           [f"{r['sym']}:{r['verdict']}" for r in st["rows"]]))
                break
        out[d] = dict(grids_with_snapshots=[P.hhmm(g) for g in grids],
                      events=ev)
        print("OCT", d, flush=True)
        for e in ev:
            print("   ", e, flush=True)
    return out


def cli_test(d="2024-10-24"):
    """The live CLI glue on a historical day (scan files -> --scan ingest,
    agent bars, --now, --check-book refusals, next candidate, refusal log,
    position file -> HOLD). Every file it writes is removed at the end."""
    import subprocess
    fd = T.FullDay(d)
    full = fd.day_at(CL.NMIN)
    snaps = {x["t"]: x for x in T.snaps_from_bars(full, CL.NMIN)}
    made = []

    def write_bars(sym, upto):
        i = fd.syms.index(sym)
        rows = ["begins_at,open,high,low,close,volume"]
        for k in range(0, upto):
            if np.isnan(fd.arr["c"][i, k]):
                continue
            rows.append(f"{P.utc_iso(d, k)},{fd.arr['o'][i, k]},"
                        f"{fd.arr['h'][i, k]},{fd.arr['l'][i, k]},"
                        f"{fd.arr['c'][i, k]},{fd.arr['v'][i, k]}")
        f = P.RH_BARS / f"{sym}_{d}.csv"
        f.write_text("\n".join(rows) + "\n")
        made.append(f)

    def cli(*a):
        o = subprocess.run([sys.executable, str(P.PLAN / "p3_r4.py"),
                            "--date", d, *a], capture_output=True,
                           text=True).stdout
        ln = [x for x in o.splitlines() if x.startswith("P3 ")]
        return json.loads(ln[-1][3:]) if ln else {"raw": o}

    res, ok = [], True
    try:
        t = CL.M_0935
        sn = snaps[t]
        sc = P.DATA / "paper" / "r4" / f"scan_{d}_TEST.json"
        sc.write_text(json.dumps({"data": {"result": {"results": [
            {"ticker": s, "columns": {"PriceReg": str(r["last"]),
                                      "PrevClose": str(r["pc"]),
                                      "Coil": str(r["coil"]),
                                      "Volume": str(r["vol"])}}
            for s, r in sn["rows"].items()]}}}))
        made.append(sc)
        cli("--scan", str(sc), "--at", "09:35", "--now", "09:36")
        o = cli("--now", "09:36")
        res.append(("now 09:36", o.get("action"), o.get("need_bars")))
        if o.get("action") == "NEED_DATA":
            for s in o["need_bars"]:
                write_bars(s, t + 1)
            o = cli("--now", "09:36")
        res.append(("now 09:36", o.get("action"), o.get("sym"),
                    o.get("screen")))
        ok &= o.get("action") == "ENTER"
        first = o.get("sym")
        c = cli("--check-book", first, "--decision", "09:35", "--bid", "10",
                "--ask", "10.5", "--now", "09:36")
        res.append(("check", first, c.get("result"), c.get("reason")))
        ok &= c.get("reason") == "SPREAD"
        o2 = cli("--now", "09:37")
        res.append(("now 09:37", o2.get("action"), o2.get("sym")))
        ok &= o2.get("action") == "ENTER" and o2.get("sym") != first
        second = o2.get("sym")
        c2 = cli("--check-book", second, "--decision", "09:35", "--bid", "5",
                 "--ask", "5", "--now", "09:37")
        res.append(("check", second, c2.get("result"), c2.get("reason")))
        ok &= c2.get("reason") == "HALT"
        o3 = cli("--now", "09:37")
        res.append(("now 09:37", o3.get("action"), o3.get("sym"),
                    o3.get("screen")))
        ok &= o3.get("sym") not in (first, second)
        o4 = cli("--now", "09:43")
        res.append(("now 09:43 (grid 09:40 has no scan snapshot)", o4.get("action"),
                    o4.get("reason")))
        ok &= o4.get("action") == "NOTHING"
        pf = P.book_dir("r4") / f"position_{o3.get('sym')}.json"
        pf.write_text(json.dumps(dict(sym=o3.get("sym"), date=d, entry=10.0,
                                      shares=100, decision_min=t)))
        made.append(pf)
        o5 = cli("--now", "09:41")
        res.append(("now 09:41 holding", o5.get("action"), o5.get("sym"),
                    o5.get("track_bars")))
        ok &= o5.get("action") == "HOLD"
        ref = P.read_json(R.refusals_path(d), [])
        res.append(("refusals", [(x["sym"], x["grid"], x["reason"])
                                 for x in ref]))
        ok &= any(x["reason"] == "SPREAD" for x in ref) and \
            any(x["reason"] == "HALT" for x in ref)
    finally:
        for f in made + [R.snaps_path(d), R.refusals_path(d),
                         R.vetoes_path(d)]:
            Path(f).unlink(missing_ok=True)
    for r in res:
        print("  CLI", r, flush=True)
    print("CLI TEST", "PASS" if ok else "FAIL", flush=True)
    return dict(steps=[list(map(str, r)) for r in res], passed=bool(ok))


if __name__ == "__main__":
    if "--cli" in sys.argv:
        r = cli_test()
        res = P.read_json(OUT, {}) or {}
        res["cli_test"] = r
        OUT.write_text(json.dumps(res, indent=1, default=float))
        sys.exit(0 if r["passed"] else 1)
    main()
