"""PAPER-3BOOK parity test for R4 (CHAMPION-REPLAY coil + no stop).

The live engine (plan/p3_r4.run_live) is driven MINUTE BY MINUTE with the
historical minute caches standing in for the live feed: at wall minute
`now` it sees only bars with index <= now-1 (the arrays are physically
truncated -- NaN after now-1 -- not merely bounded). Its legs are compared
with the published backtest dump plan/pa_out/cp_r4_legs.json (cp_sim,
965 legs, $66,760.10 at flat 10 bps).

  mode A  "code parity"   universe/coil/gap from the bars (cp_feat's own
                          definitions) -- tests that the live code IS the
                          backtest when fed the backtest's data.
  mode B  "scanner"       universe and coil from EMULATED scan snapshots
                          taken only at the 5-minute grid minutes, exactly
                          what the live session gets from the saved scan
                          (RTH high >= +10%, Last > $2, top 200 by coil,
                          sticky LAST rule observed only at snapshots).
  full    one end-of-day run per date over all 444 dates (mode A data,
          now = 16:00) -- the engine identity check, plus the LIVE-ticket
          ($10,000) expectation.

    python plan/p3_parity_r4.py [--days 20] [--full]
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as CL                                         # noqa: E402
import p3_lib as P                                          # noqa: E402
import p3_r4 as R                                           # noqa: E402

OUT = P.DATA / "paper" / "parity"
LEGS = P.PLAN / "pa_out" / "cp_r4_legs.json"


class FullDay:
    """All bars of a cp_panel day; `day_at(now)` = the truncated Day."""

    def __init__(self, date):
        z = np.load(P.MASSIVE / "cp_panel" / f"{date}.npz")
        self.syms = [str(s) for s in z["syms"]]
        self.pc = z["pc"].astype(float)
        self.arr = {k: z[k].astype(float) for k in "ohlcv"}

    def day_at(self, now):
        a = {k: v.copy() for k, v in self.arr.items()}
        if now < CL.NMIN:
            for k in "ohlc":
                a[k][:, max(now, 0):] = np.nan
            a["v"][:, max(now, 0):] = 0.0
        a["v"] = np.nan_to_num(a["v"])
        return CL.Day(dict(syms=np.array(self.syms), pc=self.pc, **a))


def snaps_from_bars(day, upto):
    """Emulated scan snapshots at grid minutes <= upto-1."""
    out = []
    rh_rth = day.runhigh_from(CL.M_OPEN)
    for m in R.GRID:
        if m > upto - 1:
            break
        last = day.last[:, m]
        hi_all = day.runhigh[:, m]
        ok = (rh_rth[:, m] >= CL.CROSS * day.pc) & (last >= CL.MIN_PRICE) \
            & np.isfinite(last)
        idx = np.flatnonzero(ok)
        with np.errstate(divide="ignore", invalid="ignore"):
            coil = (last / hi_all).astype(np.float32)
        idx = idx[np.argsort(-np.nan_to_num(coil[idx], nan=0.0),
                             kind="stable")][:200]
        out.append(dict(t=int(m), rows={day.syms[i]: dict(
            last=float(last[i]), pc=float(day.pc[i]),
            coil=float(coil[i]), vol=float(day.cumv[i, m])) for i in idx}))
    return out


def replay(fd_day, mode, tickets, minutes, cfg=R.CFG, date=""):
    seen = {}
    legs = []
    # a snapshot at grid m reads bars <= m only, so the full-day set
    # filtered to m <= now-1 is exactly what truncation would give
    allsnaps = (snaps_from_bars(fd_day.day_at(CL.NMIN), CL.NMIN)
                if mode in ("B", "D") else None)
    for now in minutes:
        day = fd_day.day_at(now)
        if mode in ("A", "C"):
            Fd = R.fd_from_bars(day)
            legs, st = R.run_live(day, Fd, now, tickets=tickets, cfg=cfg,
                                  date=date)
        else:
            Fd = R.fd_from_snaps(day, [x for x in allsnaps if x["t"] <= now - 1])
            Fd["has_bars"][:] = True
            legs, st = R.run_live(day, Fd, now, tickets=tickets, live=True,
                                  cfg=cfg, date=date)
        for lg in legs:
            k = (lg["sym"], lg["t"])
            if k not in seen:
                seen[k] = dict(first_seen=now)
            if not lg["open"] and "closed_seen" not in seen[k]:
                seen[k]["closed_seen"] = now
                seen[k]["leg"] = dict(lg)
    return legs, seen


def key(lg):
    return (lg["sym"], int(lg["entry_min"]))


def compare(bt, lv):
    b = {key(x): x for x in bt}
    v = {key(x): x for x in lv}
    match = [k for k in b if k in v]
    out = dict(bt=len(b), live=len(v), matched=len(match),
               missed=sorted(set(b) - set(v)), extra=sorted(set(v) - set(b)))
    de = [abs(v[k]["entry"] - b[k]["entry"]) for k in match]
    dx = [abs((v[k]["exit"] or 0) - b[k]["exit"]) for k in match]
    dxm = [abs((v[k]["exit_min"] or 0) - b[k]["exit_min"]) for k in match]
    out.update(entry_px_maxdiff=max(de) if de else 0.0,
               exit_px_maxdiff=max(dx) if dx else 0.0,
               exit_min_maxdiff=max(dxm) if dxm else 0,
               identical_exits=sum(1 for k in match
                                   if v[k]["exit_min"] == b[k]["exit_min"]
                                   and abs(v[k]["exit"] - b[k]["exit"]) < 1e-6))
    return out


def bt_next_open(dates, causal=False):
    """Ground truth for the LIVE convention: the published engine
    (cp_sim.run_day on cp_feat's stored grid) with ONLY the bearish fill
    moved to the next printed bar's open (LEGACY-14). cp_sim.py itself is
    untouched -- its _walk_exit is wrapped for the duration of this call."""
    import cp_feat as F
    import cp_sim as S
    orig = S._walk_exit

    def wrapped(day, Fd, i, em, entry, cfg):
        m, px, reason = orig(day, Fd, i, em, entry, cfg)
        if reason == "bearish":
            for m2 in range(m + 1, CL.NMIN):
                if day.printed[i, m2]:
                    return m2, float(day.o[i, m2]), reason
        return m, px, reason
    S._walk_exit = wrapped
    out = []
    try:
        for d in dates:
            Fd, day = F.load(d), CL.load_day(d)
            if Fd is None or day is None:
                continue
            cfg = R.CFG
            if causal:
                Fd = dict(Fd)
                Fd["vol"] = day.cumv[:, np.asarray(Fd["grid"])].astype(float)
                cfg = R.cfg_for(dict(R.CFG, tiebreak="causal"), Fd, d)
            for lg in S.run_day(day, Fd, cfg):
                lg["date"] = d
                out.append(lg)
    finally:
        S._walk_exit = orig
    return out


def main():
    a = sys.argv[1:]
    nd = int(a[a.index("--days") + 1]) if "--days" in a else 20
    D = json.loads(LEGS.read_text())
    bt = D["legs"]["R4"]
    by = {}
    for x in bt:
        by.setdefault(x["date"], []).append(x)
    dates = sorted(by)
    multi = [d for d in dates if len(by[d]) >= 3]
    pick = sorted(set(multi[::max(1, len(multi) // (nd // 2))][:nd // 2]
                      + dates[::max(1, len(dates) // (nd - nd // 2))]
                      [:nd - nd // 2]))
    pick = sorted(set(pick) | set([d for d in D["dates"] if d not in by][:2]))
    t0 = time.time()
    print("ground truth (next-open bearish) ...", flush=True)
    bt_no = bt_next_open(D["dates"], causal=True)
    by_no = {}
    for x in bt_no:
        by_no.setdefault(x["date"], []).append(x)
    res = dict(days=pick, per_day={}, modes={},
               note="A,B: published close-fill engine vs the published dump;"
                    " C/D: LIVE engine (next-open bearish fill, LEGACY-14; "
                    "causal tie-break, LEGACY-2) vs cp_sim with exactly those "
                    "two changes (bars / emulated scan snapshots)")
    minutes = list(range(CL.M_0935, CL.M_1500 + 3))
    modes = (("A", R.CFG, by), ("B", R.CFG, by),
             ("C", R.CFG_LIVE, by_no), ("D", R.CFG_LIVE, by_no))
    if "--modes-from-log" in a:
        # the minute-by-minute modes take ~25 min; a second pass for the
        # full/expectation block may reuse their logged totals verbatim
        import ast
        logf = Path(a[a.index("--modes-from-log") + 1])
        for ln in logf.read_text().splitlines():
            if ln.startswith("MODE "):
                res["modes"][ln[5]] = ast.literal_eval(ln.split(": ", 1)[1])
            elif ln.startswith("  ") and " bt " in ln and ": bt" in ln:
                mode, d = ln.split()[0], ln.split()[1].rstrip(":")
                res["per_day"].setdefault(d, {})[mode] = ln.strip()
        res["modes_source"] = str(logf)
        modes = ()
    for mode, cfg, ref in modes:
        tot = dict(bt=0, live=0, matched=0, missed=0, extra=0,
                   identical_exits=0, retro=0)
        lat = []
        for d in pick:
            fd = FullDay(d)
            legs, seen = replay(fd, mode, R.TICKETS_BT, minutes, cfg=cfg,
                                date=d)
            lv = [s_["leg"] for s_ in seen.values() if "leg" in s_]
            fin = {key(x): x for x in legs if not x["open"]}
            retro = sum(1 for x in lv if key(x) not in fin
                        or abs(fin[key(x)]["exit"] - x["exit"]) > 1e-9)
            c = compare(ref.get(d, []), lv)
            c["retro_changes"] = retro
            lat += [s_["closed_seen"] - s_["leg"]["exit_min"]
                    for s_ in seen.values() if "leg" in s_]
            res["per_day"].setdefault(d, {})[mode] = c
            for k in ("bt", "live", "matched", "identical_exits"):
                tot[k] += c[k]
            tot["missed"] += len(c["missed"])
            tot["extra"] += len(c["extra"])
            tot["retro"] += retro
            print(f"  {mode} {d}: bt {c['bt']} live {c['live']} matched "
                  f"{c['matched']} missed {c['missed']} extra {c['extra']} "
                  f"retro {retro} ({time.time() - t0:.0f}s)", flush=True)
        tot["match_rate"] = round(tot["matched"] / max(tot["bt"], 1), 4)
        tot["exit_known_after_bar_min"] = (
            dict(min=min(lat), max=max(lat), mean=round(float(np.mean(lat)), 2))
            if lat else None)
        res["modes"][mode] = tot
        print(f"MODE {mode}: {tot}", flush=True)
    if "--full" in a:
        def full(cfg, ref_legs, tickets):
            refk = {(x["date"],) + key(x): x for x in ref_legs}
            got = []
            for d in D["dates"]:
                fd = FullDay(d)
                day = fd.day_at(CL.NMIN)
                legs, _ = R.run_live(day, R.fd_from_bars(day), CL.NMIN,
                                     tickets=tickets, cfg=cfg, date=d)
                for lg in legs:
                    lg["date"] = d
                got += legs
            v = {(x["date"],) + key(x): x for x in got}
            m = [k for k in refk if k in v]
            ident = sum(1 for k in m
                        if v[k]["exit_min"] == refk[k]["exit_min"]
                        and abs(v[k]["exit"] - refk[k]["exit"]) < 1e-4
                        and abs(v[k]["entry"] - refk[k]["entry"]) < 1e-4
                        and v[k]["shares"] == refk[k]["shares"])
            return got, dict(ref=len(refk), live=len(v), matched=len(m),
                             identical=ident,
                             missed=len(set(refk) - set(v)),
                             extra=len(set(v) - set(refk)),
                             gross_ref=round(sum(x["gross"]
                                                 for x in ref_legs), 2),
                             gross_live=round(sum(x["gross"]
                                                  for x in got), 2))
        _, res["full_A_published"] = full(R.CFG, bt, R.TICKETS_BT)
        print("FULL A:", res["full_A_published"], flush=True)
        _, res["full_C_live_cfg"] = full(R.CFG_LIVE, bt_no, R.TICKETS_BT)
        print("FULL C:", res["full_C_live_cfg"], flush=True)
        nd_ = len(D["dates"])
        exp = {}
        for lab, cfg in (("live_next_open", R.CFG_LIVE),
                         ("live_next_open_index_tiebreak",
                          dict(R.CFG, bearish_fill="next_open")),
                         ("published_close", R.CFG)):
            legs10, _ = full(cfg, [], R.TICKETS_LIVE)
            aug = [x for x in legs10 if x["date"] >= "2026-08-01"]
            e = {}
            for bps in (0, 6, 10, 28.75):
                def net(xs):
                    return [x["gross"] - (x["entry"] + x["exit"])
                            * x["shares"] * bps / 1e4 for x in xs]
                pn = net(legs10)
                e[str(bps)] = dict(
                    per_ticket=round(float(np.mean(pn)), 2),
                    per_day=round(float(np.sum(pn)) / nd_, 2),
                    tickets_per_day=round(len(pn) / nd_, 3),
                    aug2026_total=round(float(np.sum(net(aug))), 2),
                    aug2026_tickets=len(aug))
            exp[lab] = e
        res["expectation_live"] = dict(ticket=P.TICKET, days=nd_,
                                       window=[D["dates"][0], D["dates"][-1]],
                                       by_bps=exp)
        print("EXPECTATION $10k:", json.dumps(exp), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "r4.json").write_text(json.dumps(res, indent=1, default=str))
    print("wrote", OUT / "r4.json", f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
