"""Replay the ADOPTED C37 config (label C37H) over the four live paper
days 2026-08-10..13 and print per-day trades, so backtest P&L can be
compared against what live paper trading actually made.

ADDITIVE ONLY. This imports plan/rotation_sim.py and calls its existing
day_candidates() / run_day() with CFGS["C37H"] unchanged. No config, no
ranker and no gate is modified here -- the only thing this file supplies
is a different POOL (data/massive/gappers_novol_replay0813.json, built by
plan/replay_0810_pool.py from the paper ledgers) and a different day list.

Two pool depths are reported, because they answer different questions:

  --full  (default) every ledger crosser that has bars. This is the pool
          LIVE actually saw (the scanner latches every +10% crosser), so
          it is the right basis for "did live leave money on the table".

  --walk16  only the 16 deepest by DAY-HIGH gain. The champion's own
          $665,667 was measured on an m1 cache backfilled to walk-8/12/16
          depth (median ~17 names/day with bars), so a 124-name pool hands
          the ranker more chances to find a gate-passing coiled name than
          the benchmark measurement ever had. This mode reproduces that
          coverage depth. NOTE the cut itself uses day-high gain, i.e. it
          is the same hindsight the causal-pool audit removed -- it is a
          COVERAGE emulation, not a causal pool, and is reported only as
          context for the benchmark.

  --today-screen  stack TODAY'S live halal screen on top of the
          champion's point-in-time gate, so a name we would now
          refuse never takes a ticket and rotation redeploys it.

Usage:  python plan/replay_0810_run.py [CFGID] [--walk16] [--today-screen]
"""
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

_spec = importlib.util.spec_from_file_location("rs", ROOT / "plan/rotation_sim.py")
rs = importlib.util.module_from_spec(_spec)
sys.modules["rs"] = rs
_spec.loader.exec_module(rs)

POOL_F = ROOT / "data/massive/gappers_novol_replay0813.json"
OUT_F = ROOT / "data/massive/replay0813_trades.json"

LIVE = {"2026-08-10": ("LFST", -65.78, 1),
        "2026-08-11": ("FRMI", -266.54, 1),
        "2026-08-12": ("BE", 104.58, 1),
        "2026-08-13": ("ANGX (VOID: ruled haram)", 0.0, 0)}


def main():
    args = sys.argv[1:]
    walk16 = "--walk16" in args
    today = "--today-screen" in args
    if today:
        # Guardrail (user, this task): "if the backtest picks a name we now
        # consider haram, SAY SO rather than banking its P&L". Strongest
        # form of that: re-run with the CURRENT screen stacked ON TOP of
        # the champion's point-in-time gate, so a now-haram name never
        # takes the ticket at all and rotation redeploys it. Patched on
        # the imported module -- rotation_sim.py itself is untouched.
        scr = json.loads((ROOT / "data/massive/replay0813_today_screen.json")
                         .read_text())
        _pt = rs.axb.halal_pt

        def _gated(sym, date, pc, _pt=_pt, _scr=scr):
            if not _scr.get(sym, {}).get("halal"):
                return False
            return _pt(sym, date, pc)
        rs.axb.halal_pt = _gated
    cfg_id = ([a for a in args if not a.startswith("--")] or ["C37H"])[0]
    cfg = rs.CFGS[cfg_id]
    print(f"{cfg_id}: {cfg['desc']}"
          f"   pool={'walk-16 by day-high gain' if walk16 else 'FULL ledger'}\n")
    pool = json.loads(POOL_F.read_text())
    byday = defaultdict(list)
    for c in pool:
        byday[c["date"]].append(c)

    allout = {}
    grand = 0.0
    for date in sorted(byday):
        cs = byday[date]
        if walk16:
            cs = sorted(cs, key=lambda x: -x["gain_pct"])[:16]
        dfs = {}
        cands = rs.day_candidates(cs, date, dfs, cfg.get("cand_top", 16),
                                  not cfg.get("biased_pool", False))
        withbars = sum(1 for c in cs
                       if (rs.M1 / f"{c['symbol']}_{date}.csv").exists()
                       and not (rs.M1 / f"{c['symbol']}_{date}.csv")
                       .read_text(errors="ignore").startswith("EMPTY"))
        tr = rs.run_day(cands, date, cfg, {}, None)
        p = sum(x["pnl"] for x in tr)
        grand += p
        tickets = sorted({x.get("ticket") for x in tr})
        lsym, lpnl, ltk = LIVE[date]
        print(f"=== {date}  pool={len(cs)} bars={withbars} "
              f"crossed_ranked={len(cands)}")
        for x in sorted(tr, key=lambda y: (y["ticket"], y["entry_time"])):
            print(f"    T{x['ticket']+1} {x['symbol']:<6} "
                  f"in {x['entry_time'].strftime('%H:%M')} @{x['entry']:.2f}"
                  f"  out {x['exit_time'].strftime('%H:%M')} "
                  f"@{x['exit']:.2f}  {str(x.get('reason','')):<22} "
                  f"${x['pnl']:+,.2f}")
        print(f"    BACKTEST {len(tickets)} tickets  ${p:+,.2f}   |   "
              f"LIVE {ltk} tickets {lsym} ${lpnl:+,.2f}   |   "
              f"gap ${p - lpnl:+,.2f}\n")
        allout[date] = {
            "backtest_pnl": round(p, 2),
            "backtest_tickets": len(tickets),
            "backtest_names": [x["symbol"] for x in tr],
            "pool_n": len(cs), "with_bars": withbars,
            "ranked_candidates": len(cands),
            "live_pnl": lpnl, "live_tickets": ltk, "live_name": lsym,
            "trades": [{"ticket": x["ticket"] + 1, "symbol": x["symbol"],
                        "entry": str(x["entry_time"]),
                        "entry_px": x["entry"],
                        "exit": str(x["exit_time"]), "exit_px": x["exit"],
                        "reason": str(x.get("reason", "")),
                        "peak_pct": x.get("peak_pct"),
                        "pnl": round(x["pnl"], 2)} for x in tr]}
    lt = sum(v["live_pnl"] for v in allout.values())
    print(f"TOTAL 4 days: backtest ${grand:+,.2f}  live ${lt:+,.2f}  "
          f"gap ${grand - lt:+,.2f}")
    out_f = OUT_F.with_name(OUT_F.stem + ("_walk16" if walk16 else "")
                            + ("_today" if today else "") + OUT_F.suffix)
    out_f.write_text(json.dumps({"config": cfg_id, "desc": cfg["desc"],
                                 "pool_mode": "walk16" if walk16 else "full",
                                 "gate": "pt+today" if today else "pt",
                                 "days": allout,
                                 "backtest_total": round(grand, 2),
                                 "live_total": round(lt, 2)}, indent=1))
    print(f"wrote {out_f}")


if __name__ == "__main__":
    main()
