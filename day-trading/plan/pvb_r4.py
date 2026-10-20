"""PAPER-VS-BT, book R4: the R4 backtests over the 11 paper days.

Universe = data/pvb/r4_universe.json (Polygon grouped-daily +10% pool, union
the live scanner's names; pc = Polygon prev close). Bars = one source dir
(default data/pvb/rhx: Robinhood 1-minute bars 04:00-15:05 ET fetched after
the close for every universe name). Per day it runs, on the 720-minute
04:00 grid exactly like plan/p3_r4_live.py:

  model     p3_r4.run_live (PARITY/MODEL track: CFG_LIVE, $10k tickets)
  live      p3_r4_live.live_sim, PINNED 0.6%, spread veto = LEGACY-9 bar
            proxy, HALT = no print within 5 min   (= the r4_live expectation)
  live_log  live_sim with the PAPER session's own book-check refusals
            (data/paper/r4/refusals_{D}.json, vetoes_{D}.json: SPREAD /
            DEPTH / HALT for that name at that grid) used instead of the
            proxy where a check was logged; proxy elsewhere
  noveto    live_sim with no spread veto

and compares the per-grid ranked top 8 against the live scanner snapshots.
Writes data/pvb/r4_bt_{tag}.json.

    python plan/pvb_r4.py [--bars DIR] [--tag rhx] [--coil bars|rth]

--coil rth replaces the bar coil (last / session high INCLUDING premarket,
the backtest's definition) with last / RTH-only high: what the live
scanner's Coil column turned out to be (plan/pvb_coilcheck.py).
"""
import json
import sys
import zlib
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as CL                                         # noqa: E402
import cp_sim as S                                          # noqa: E402
import p3_lib as P                                          # noqa: E402
import p3_r4 as R                                           # noqa: E402
import p3_r4_live as V                                      # noqa: E402

DAYS = ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09",
        "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16",
        "2026-10-19"]
PV = P.DATA / "pvb"


class DirFeed:
    def __init__(self, d, date, now=P.NMIN):
        self.d, self.date, self.now = Path(d), date, now

    def bars(self, sym):
        return P.read_bars_csv(self.d / f"{sym}_{self.date}.csv", self.date,
                               upto=self.now - 1)


def load_day(date, bars_dir, uni):
    u = uni[date]
    syms = sorted(u)
    pcs = [u[s]["pc"] or u[s].get("pc_scan") or np.nan for s in syms]
    feed = DirFeed(bars_dir, date)
    have = [s for s in syms if (Path(bars_dir) / f"{s}_{date}.csv").exists()]
    day = R.make_day(syms, pcs, feed)
    return day, syms, have


def logged_checks(date):
    """{(sym, grid_min): reason} from the paper session's book checks."""
    out, passed = {}, set()
    for f in (R.refusals_path(date), R.vetoes_path(date)):
        for v in P.read_json(f, []) or []:
            g = v.get("grid") or v.get("decision")
            if g is not None and v.get("result") == "PASS":
                passed.add((v["sym"], P.parse_hhmm(g)))
    for f in (R.refusals_path(date), R.vetoes_path(date)):
        for v in P.read_json(f, []) or []:
            g = v.get("grid") or v.get("decision")
            why = v.get("reason") or v.get("why") or ""
            if v.get("result", "VETO") != "VETO" or g is None:
                continue
            if (v["sym"], P.parse_hhmm(g)) in passed:
                continue
            if not any(k in str(why).upper() for k in ("SPREAD", "DEPTH",
                                                       "HALT")):
                continue
            out[(v["sym"], P.parse_hhmm(g) if isinstance(g, str) else int(g))] = \
                str(why)[:30]
    return out


def leg_out(lg):
    x = {k: (v.item() if hasattr(v, "item") else v) for k, v in lg.items()
         if k not in ("i",)}
    for k in ("t", "entry_min", "exit_min"):
        if x.get(k) is not None:
            x[k + "_hhmm"] = P.hhmm(int(x[k]))
    if x.get("gross") is not None:
        x["net15"] = round(V.net(lg), 2)
        x["gross"] = round(x["gross"], 2)
    return x


def ranked(Fd, gi, cfgr, n=8):
    cand = np.where(Fd["elig_last"][:, gi])[0]
    if len(cand) == 0:
        return []
    key = S.rank_key(Fd, gi, cfgr)[cand]
    return [str(Fd["syms"][int(i)]) for i in cand[np.argsort(key, kind="stable")]][:n]


def snap_ranked(date, snaps, t):
    """Live top 8 at grid t from the saved scan snapshots (sticky LAST
    rule from snapshots <= t, coil desc, volume desc, crc32 tie)."""
    seen = set()
    rows_t = None
    for x in snaps:
        if x["t"] > t:
            break
        for s, r in x["rows"].items():
            if r.get("pc") and r.get("last") and r["last"] >= CL.CROSS * r["pc"]:
                seen.add(s)
        if x["t"] == t:
            rows_t = x["rows"]
    if rows_t is None:
        return None
    el = [(s, r) for s, r in rows_t.items() if s in seen and r.get("last")
          and r["last"] >= CL.MIN_PRICE]
    el.sort(key=lambda kv: (-np.float32(kv[1].get("coil") or 0.0),
                            -(kv[1].get("vol") or -1.0),
                            zlib.crc32(f"{date}|{t}|{kv[0]}".encode())))
    return [s for s, _ in el[:8]]


def main():
    a = sys.argv[1:]
    bars_dir = Path(a[a.index("--bars") + 1]) if "--bars" in a else PV / "rhx"
    tag = a[a.index("--tag") + 1] if "--tag" in a else bars_dir.name
    days = a[a.index("--days") + 1].split(",") if "--days" in a else DAYS
    coil_mode = a[a.index("--coil") + 1] if "--coil" in a else "bars"
    uni = json.loads((PV / "r4_universe.json").read_text())
    res = {}
    for d in days:
        day, syms, have = load_day(d, bars_dir, uni)
        Fd = R.fd_from_bars(day)
        if coil_mode == "rth":            # emulate the live scanner's Coil
            rh = day.runhigh_from(CL.M_OPEN)[:, R.GRID]   # (RTH high only)
            with np.errstate(divide="ignore", invalid="ignore"):
                Fd["coil"] = np.where(rh > 0, day.last[:, R.GRID] / rh,
                                      np.nan).astype(np.float32)
        cfgr = R.cfg_for(R.CFG_LIVE, Fd, d)
        model, st = R.run_live(day, Fd, CL.NMIN, tickets=R.TICKETS_LIVE,
                               cfg=R.CFG_LIVE, date=d)
        logs = {}
        out = dict(n_universe=len(syms), n_bars=len(have))
        out["model"] = [leg_out(x) for x in model]
        lc = logged_checks(d)
        prox = V.proxy_check("spread")

        def check_log(dd, i, t):
            k = (str(dd.syms[i]), int(t))
            if k in lc:
                return "LOGGED " + lc[k]
            return prox(dd, i, t)
        for name, chk in (("live", prox), ("live_log", check_log),
                          ("noveto", None)):
            lg = []
            legs = V.live_sim(day, Fd, d, chk, cfgr=cfgr, pin_thr=R.PIN_THR,
                              log=lg)
            out[name] = [leg_out(x) for x in legs]
            logs[name] = [(P.hhmm(t), s, why) for t, s, why in lg]
        out["refusals_live"] = logs["live"]
        out["refusals_live_log"] = logs["live_log"]
        # ranked top 8 per grid: backtest bars vs live scanner snapshots
        sf = R.snaps_path(d)
        snaps = [json.loads(x) for x in sf.read_text().splitlines()
                 if x.strip()] if sf.exists() else []
        cmp = []
        for gi, m in enumerate(Fd["grid"]):
            m = int(m)
            if m >= R.CFG_LIVE["cutoff"]:
                break
            lv = snap_ranked(d, snaps, m)
            if lv is None:
                continue
            bt = ranked(Fd, gi, cfgr)
            cmp.append(dict(t=P.hhmm(m), bt=bt, live=lv,
                            overlap=len(set(bt) & set(lv)),
                            top1_same=bool(bt and lv and bt[0] == lv[0])))
        out["top8_compare"] = cmp
        res[d] = out
        tot = lambda k: round(sum(x.get("net15") or 0 for x in out[k]), 2)  # noqa
        print(d, f"uni {len(syms)} bars {len(have)}", flush=True)
        for k in ("model", "live", "live_log", "noveto"):
            print(f"   {k:8s} {tot(k):>9}", [(x["sym"], x["t_hhmm"],
                  x.get("exit_min_hhmm"), x.get("reason"), x.get("net15"))
                  for x in out[k]], flush=True)
        if cmp:
            print("   top8 overlap mean", round(np.mean([c["overlap"] for c in cmp]), 2),
                  "top1 same", sum(c["top1_same"] for c in cmp), "/", len(cmp),
                  flush=True)
    (PV / f"r4_bt_{tag}.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
