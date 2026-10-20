"""PVB-FIX (2026-10-19) regression tests for the four live-paper bugs found
by PAPER-VS-BT (research-oct/PAPER-VS-BACKTEST.md). Read-only on the
session's saved inputs (data/paper/r4/snaps_*.jsonl, vetoes, data/rh_bars,
data/paper/rl/snap_*.jsonl); every file a test writes goes to a temp dir.

  1  R4 coil includes the PREMARKET high (bars 04:00..t): SKDD 10-15 09:35
     scan coil 1.000 -> 0.975, and the live pick is no longer SKDD
  2  scan coil > 1.0: TERG / MLCC 10-19 09:35 are dropped (no volume = bad
     row), the model track is not stuck at 09:35, and a bar-less top name
     (MLCC forced valid) is skipped MODEL_NOBARS_MIN minutes after it was
     first asked -- the model track can never freeze for the day
  3  R4 DEPTH uses the capped intended shares: ASTT 10-12 (cap 320) and
     INT 10-19 (cap 100) now PASS on their logged quotes / depth
  4  RL ENTER carries shares_cap: ABUS 10-16 11:25 -> cap 1,505 (the
     session bought 2,380); floor(min($10k, cap x ask) / ask) <= the limit

    python plan/pvb_fix_selftest.py
"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_lib as P                                          # noqa: E402
import p3_r4 as R                                           # noqa: E402
import p3_rl as RL                                          # noqa: E402

RES = []


def check(name, ok, detail=""):
    RES.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  -- {detail}" if detail
                                                  else ""), flush=True)


def gi_of(t):
    return [int(g) for g in R.GRID].index(t)


# ------------------------------------------------------------------ bug 1
def test_premarket_high():
    # unit cases
    c, n = R.snap_coil(dict(last=9.75, high=10.0, coil=0.975, vol=5), 12.0)
    check("1a snap_coil uses a higher bar (premarket) high",
          n == "pm_high" and abs(c - 9.75 / 12.0) < 1e-12, f"{c} {n}")
    c, n = R.snap_coil(dict(last=9.75, high=10.0, coil=0.975, vol=5), 9.9)
    check("1b snap_coil keeps the scan coil when the scan high is higher",
          n is None and c == 0.975, f"{c} {n}")
    c, n = R.snap_coil(dict(last=9.75, coil=0.975, vol=5), float("nan"))
    check("1c snap_coil without bars = the scan coil", n is None and c == 0.975)
    # SKDD 10-15 (PVB: live 1.000 vs 0.975 on bars)
    d, t, now = "2026-10-15", P.parse_hhmm("09:35"), P.parse_hhmm("09:37")
    day, Fd = R.load_live(d, now)
    i = day.syms.index("SKDD")
    snap = [json.loads(x) for x in R.snaps_path(d).read_text().splitlines()
            if x.strip()]
    r = [x for x in snap if x["t"] == t][0]["rows"]["SKDD"]
    bh = float(np.nanmax(np.where(day.printed[i, :t + 1], day.h[i, :t + 1],
                                  np.nan)))
    pm = float(np.nanmax(np.where(day.printed[i, :R.CL.M_OPEN],
                                  day.h[i, :R.CL.M_OPEN], np.nan)))
    got = float(Fd["coil"][i, gi_of(t)])
    check("1d SKDD 10-15 09:35 coil = scan last / bar high 04:00..09:35",
          abs(got - np.float32(r["last"] / bh)) < 1e-6 and r["coil"] == 1.0
          and bh == pm,
          f"scan coil {r['coil']} -> {got:.4f} (last {r['last']}, premarket "
          f"high {pm}, scan HighAll {r['high']})")
    rows = R.live_screen(day, Fd, gi_of(t), R.cfg_for(R.CFG_LIVE, Fd, d))
    pick = next(x["sym"] for x in rows if x["verdict"] == "OK")
    check("1e SKDD is no longer the 10-15 09:35 live pick", pick != "SKDD"
          and "SKDD" not in [x["sym"] for x in rows[:1]],
          f"pick {pick}; screen {[x['sym'] for x in rows]}")


# ------------------------------------------------------------------ bug 2
def test_coil_above_one():
    c, n = R.snap_coil(dict(last=34.305, high=30.7058, coil=1.1172, vol=0.0))
    check("2a coil > 1 with no volume = bad row", c is None and n == "bad")
    c, n = R.snap_coil(dict(last=10.05, high=10.0, coil=1.005, vol=1000.0))
    check("2b coil > 1 with volume = clamped to 1.0", c == 1.0 and n == "clamp")
    d, t, now = "2026-10-19", P.parse_hhmm("09:35"), P.parse_hhmm("09:37")
    day, Fd = R.load_live(d, now)
    gi = gi_of(t)
    bad = sorted(k[0] for k, v in Fd["coil_notes"].items()
                 if k[1] == t and v["note"] == "bad")
    el = {s for s in ("TERG", "MLCC")
          if Fd["elig_last"][day.syms.index(s), gi]}
    check("2c TERG and MLCC 10-19 09:35 flagged bad and not eligible",
          bad == ["MLCC", "TERG"] and not el, f"bad {bad}")
    cmax = float(np.nanmax(Fd["coil"]))
    check("2d no live coil above 1.0 on 10-19", cmax <= 1.0, f"max {cmax}")
    legs, st = R.run_live(day, Fd, now, live=True, date=d)
    check("2e 10-19 model track at 09:37 is not stuck on MLCC/TERG",
          st["state"] != "NEED_DATA" and "MLCC" not in st.get("ranked", []),
          f"{st['state']} {st.get('sym')}")
    # forced freeze: MLCC made a VALID top row (coil 1, huge volume) but it
    # has no bars (the session's bars call returned none)
    snaps = [json.loads(x) for x in R.snaps_path(d).read_text().splitlines()
             if x.strip()]
    for x in snaps:
        if "MLCC" in x["rows"]:
            x["rows"]["MLCC"].update(coil=1.0, vol=9e12, high=51.88)
    old_need = None
    asks, states, frozen_run, run = {}, [], 0, 0
    for now in range(P.parse_hhmm("09:36"), P.parse_hhmm("10:30")):
        feed = P.LiveFeed(d, now)
        dy = R.make_day(list(day.syms), list(day.pc), feed)
        F = R.fd_from_snaps(dy, [x for x in snaps if x["t"] <= now - 1])
        if old_need is None:
            _, s0 = R.run_live(dy, F, now, live=True, date=d)
            old_need = s0
        late = {s for s, w in asks.items() if now - w >= R.MODEL_NOBARS_MIN}
        _, s1 = R.run_live(dy, F, now, live=True, date=d, skip=late)
        if s1["state"] == "NEED_DATA":
            for s in s1["need_bars"]:
                asks.setdefault(s, now)
            run += 1
            frozen_run = max(frozen_run, run)
        else:
            run = 0
        states.append((P.hhmm(now), s1["state"], s1.get("sym")))
    check("2f forced: the OLD path freezes (NEED_DATA on MLCC, no skip)",
          old_need["state"] == "NEED_DATA" and "MLCC" in old_need["need_bars"],
          f"{old_need.get('need_bars')}")
    check("2g forced: with the skip the model never waits more than "
          f"{R.MODEL_NOBARS_MIN} minutes on a bar-less name",
          frozen_run <= R.MODEL_NOBARS_MIN and states[-1][1] != "NEED_DATA",
          f"longest NEED_DATA run {frozen_run} min; 10:29 state "
          f"{states[-1]}")
    # model_skip / CLI path: NOBARS marks and asks file in a temp book dir
    tmp = Path(tempfile.mkdtemp())
    orig = R.model_asks_path
    try:
        R.model_asks_path = lambda date: tmp / f"model_asks_{date}.json"
        P.write_atomic(R.model_asks_path(d), {"MLCC": dict(at=336, t=335),
                                              "ZZZ": dict(at=339, t=335)})
        sk, late = R.model_skip(d, 341, {("ABC", 340): "NOBARS",
                                          ("DEF", 340): "SPREAD"})
        check("2h model_skip = NOBARS marks + asks >= 5 min old",
              sk == {"ABC", "MLCC"} and set(late) == {"MLCC"}, f"{sk}")
    finally:
        R.model_asks_path = orig
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ bug 3
def test_depth_cap():
    for d, sym, cap_exp in (("2026-10-12", "ASTT", 320),
                            ("2026-10-19", "INT", 100)):
        v = [x for x in P.read_json(R.vetoes_path(d), [])
             if x["sym"] == sym and x["decision"] == "09:35"][0]
        now = P.parse_hhmm(v["at"])
        day, Fd = R.load_live(d, now)
        rows = R.live_screen(day, Fd, gi_of(P.parse_hhmm("09:35")),
                             R.cfg_for(R.CFG_LIVE, Fd, d))
        cap = next(x["shares_cap"] for x in rows if x["sym"] == sym)
        old = R.book_verdict(v["bid"], v["ask"], v["depth"])
        new = R.book_verdict(v["bid"], v["ask"], v["depth"], shares_cap=cap)
        check(f"3 {sym} {d}: DEPTH re-judged at the capped shares -> PASS",
              cap == cap_exp and not old["ok"] and old["reason"] == "DEPTH"
              and new["ok"] and new["want"] == min(int(P.TICKET // v["ask"]),
                                                   cap),
              f"cap {cap}, depth {v['depth']}: old want {old['want']} "
              f"{old['reason']} -> new want {new['want']} PASS")
    # check_book reads the cap the ENTER line saved (temp book dir)
    tmp = Path(tempfile.mkdtemp())
    o_s, o_v, o_r = R.screen_path, R.vetoes_path, R.refusals_path
    try:
        R.screen_path = lambda date: tmp / f"screen_{date}.json"
        R.vetoes_path = lambda date: tmp / f"vetoes_{date}.json"
        R.refusals_path = lambda date: tmp / f"refusals_{date}.json"
        P.write_atomic(R.screen_path("2026-10-19"), {"09:35": {"INT": 100}})
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            R.check_book("2026-10-19", P.parse_hhmm("09:37"), "INT", "09:35",
                         14.96, 15.03, 100.0)
        o = json.loads(buf.getvalue().strip().splitlines()[-1][3:])
        check("3c check_book uses the saved shares_cap (INT 10-19)",
              o["result"] == "PASS" and o["shares"] == 100
              and o["shares_cap"] == 100, f"{o['result']} shares {o['shares']}")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            R.check_book("2026-10-19", P.parse_hhmm("09:37"), "INT", "09:35",
                         14.96, 15.03, 20.0)
        o = json.loads(buf.getvalue().strip().splitlines()[-1][3:])
        check("3d a genuinely thin book is still refused (20 < 25% of 100)",
              o["result"] == "VETO" and o["reason"] == "DEPTH")
    finally:
        R.screen_path, R.vetoes_path, R.refusals_path = o_s, o_v, o_r
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ bug 4
def test_rl_cap():
    d = "2026-10-16"
    tmp = Path(tempfile.mkdtemp())
    orig = RL.state_path
    lines = []
    try:
        RL.state_path = lambda date: tmp / f"state_{date}.json"
        for now in range(P.parse_hhmm("09:31"), P.parse_hhmm("11:28")):
            for _ in range(2):              # NEED_DATA confirm -> re-run
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    RL.live(d, P.hhmm(now))
                o = [json.loads(x[3:]) for x in buf.getvalue().splitlines()
                     if x.startswith("P3 ")][-1]
                lines.append(o)
                if o["action"] != "NEED_DATA" or o.get("need_scan"):
                    break
    finally:
        RL.state_path = orig
        shutil.rmtree(tmp, ignore_errors=True)
    ent = [o for o in lines if o["action"] in ("ENTER", "ENTER-STALE")
           and o.get("sym") == "ABUS"]
    o = ent[0] if ent else {}
    cap = o.get("shares_cap")
    ask = 4.20                              # the session's 10-16 ABUS ask
    sh = min(int(P.TICKET // ask), cap) if cap else None
    check("4 ABUS 10-16 RL ENTER carries shares_cap; shares <= the limit",
          bool(ent) and cap == 1505 and sh is not None and sh <= 1505,
          f"{o.get('action')} {o.get('decision_min')} shares_cap {cap} -> "
          f"{sh} sh at ask {ask} (session bought 2,380)")


if __name__ == "__main__":
    test_premarket_high()
    test_coil_above_one()
    test_depth_cap()
    test_rl_cap()
    n = sum(ok for _, ok, _ in RES)
    print(f"PVB-FIX SELFTEST {n}/{len(RES)}",
          "ALL PASS" if n == len(RES) else "FAILURES", flush=True)
    sys.exit(0 if n == len(RES) else 1)
