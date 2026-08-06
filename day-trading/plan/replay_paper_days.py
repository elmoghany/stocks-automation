"""Replay the C30/C23 SIMULATOR over the live paper days (user
2026-08-06: "backtest the 3 days for c30") -- the definitive check on
whether the paper sessions matched what the backtest would have done.

Pipeline per date: rebuild the backtest's candidate pool from the
Massive grouped-daily sweep (same rules as penny_ax20_discover: clean
ticker, prev_close >= $2, high >= +10%, volume >= 5x trailing-50
average), walk it top-8 by gain exactly like run_experiment -- 7AM
calm-gap <= +20%, point-in-time halal -- then run the UNMODIFIED
sim_window with the C23 spec on 1-minute bars (fetched via the
harness's own lazy loader, so bars are cached identically).

Usage: python day-trading/plan/replay_paper_days.py [--fetch]
(--fetch is REQUIRED on a first run; without it, missing 1-min bars
produce a loud ERROR line rather than a silent skip.)
"""

import gzip
import importlib.util
import json
import sys
from collections import defaultdict
from datetime import time as dtime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT / "plan"))

_spec = importlib.util.spec_from_file_location(
    "penny_x100", ROOT / "plan" / "penny_x100.py")
x = importlib.util.module_from_spec(_spec)
sys.modules["penny_x100"] = x
_spec.loader.exec_module(x)

from shared import massive  # noqa: E402

GD = ROOT / "data/massive/gd"
DATES = ["2026-08-04", "2026-08-05", "2026-08-06"]
WARRANT_SUFFIX = ("W", "U", "R")

SPEC = dict(id="C30replay", desc="C23 rules (C30 sizing base)",
            pm_break=True, exit_1pm=True,
            sim=dict(orb_bars=5, max_vol_frac=0.20, vol_frac_window=10,
                     pressure_trail=(10, 0.30, 0.30, 10, 40),
                     scale_out_pressure_skip=0.30, wick_guard=3.0,
                     budget=15_000.0))


def clean_ticker(sym):
    if not sym or not sym.isalpha() or not sym.isupper():
        return False
    if len(sym) == 5 and sym.endswith(WARRANT_SUFFIX):
        return False
    return len(sym) <= 5


def gd(date):
    f = GD / f"{date}.json.gz"
    if f.exists():
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    try:
        rows = massive.grouped_daily(date)
    except Exception as e:
        print(f"ERROR: grouped-daily fetch failed for {date}: {e}",
              flush=True)
        return None
    slim = [{k: r.get(k) for k in ("T", "o", "h", "l", "c", "v")}
            for r in (rows or [])]
    if slim:
        with gzip.open(f, "wt", encoding="utf-8") as fh:
            json.dump(slim, fh)
        return slim
    print(f"ERROR: grouped-daily EMPTY for {date}", flush=True)
    return None


def build_pools():
    """Rolling 50-session volume history -> candidate pool per date."""
    dates = sorted(p.name[:10] for p in GD.glob("*.json.gz"))
    for d in DATES:
        if d not in dates and gd(d):
            dates.append(d)
    dates = sorted(set(dates))
    hist = defaultdict(list)
    pools = {}
    for k, d in enumerate(dates):
        rows = gd(d)
        if rows is None:
            continue
        if d in DATES:
            prev_rows = gd(dates[k - 1])
            pc_map = {r["T"]: r["c"] for r in (prev_rows or [])
                      if r.get("T") and r.get("c")}
            cands = []
            for r in rows:
                sym = r.get("T")
                if not clean_ticker(sym):
                    continue
                pc, h_, v = pc_map.get(sym), r.get("h"), r.get("v")
                if not pc or pc < 2 or not h_ or not v:
                    continue
                gain = (h_ / pc - 1) * 100
                if gain < 10:
                    continue
                hs = hist.get(sym, [])
                if len(hs) < 50:
                    continue
                avg = sum(z[1] for z in hs[-50:]) / 50
                if avg <= 0 or v < 5 * avg:
                    continue
                cands.append(dict(symbol=sym, date=d,
                                  gain_pct=round(gain, 2),
                                  rvol=round(v / avg, 2),
                                  prev_close=pc, hist_n=len(hs),
                                  volume=v))
            pools[d] = sorted(cands, key=lambda c: -c["gain_pct"])
        for r in rows:
            if r.get("T") and r.get("v"):
                hist[r["T"]].append((d, r["v"], r.get("c")))
    return pools


def replay(date, cands):
    """Mirror run_experiment's committed-candidate walk + sim."""
    print(f"\n=== {date}: pool {len(cands)} candidates ===")
    dfs = {}
    pool = x.rank_pool(cands, SPEC, date, dfs)[:SPEC.get("walk", 8)]
    committed = None
    for idx, c in enumerate(pool):
        df = dfs.get(c["symbol"])
        if df is None:
            df = x.get_lazy(c["symbol"], date)
            dfs[c["symbol"]] = df
        if df is None:
            print(f"  #{idx} {c['symbol']:<6} gain {c['gain_pct']:>7.1f}%"
                  f" rvol {c['rvol']:>6.1f}  ERROR: no 1-min bars "
                  f"(run with --fetch)")
            continue
        w = df[(df.index.time >= x.W_START)
               & (df.index.time < dtime(13, 0))]
        if len(w) < 20:
            print(f"  #{idx} {c['symbol']:<6} SKIP: only {len(w)} bars "
                  f"in the 7AM-1PM window")
            continue
        g7 = (float(w["Open"].iloc[0]) / c["prev_close"] - 1) * 100
        if g7 > 20.0:
            print(f"  #{idx} {c['symbol']:<6} gain {c['gain_pct']:>7.1f}%"
                  f" rvol {c['rvol']:>6.1f}  REJECT calm-gap "
                  f"(7AM {g7:+.1f}% > +20%)")
            continue
        if not x.axb.halal_pt(c["symbol"], date, c["prev_close"]):
            print(f"  #{idx} {c['symbol']:<6} gain {c['gain_pct']:>7.1f}%"
                  f" rvol {c['rvol']:>6.1f}  REJECT halal")
            continue
        print(f"  #{idx} {c['symbol']:<6} gain {c['gain_pct']:>7.1f}%"
              f" rvol {c['rvol']:>6.1f}  7AM {g7:+.1f}%  ** COMMITTED **")
        committed = (c, w, df)
        break
    if committed is None:
        print("  VERDICT: no committed candidate -> no-trade day")
        return 0.0, []
    c, w, df = committed
    spec = json.loads(json.dumps(SPEC))       # deep copy
    spec["sim"] = dict(SPEC["sim"])
    pm = x.premkt_metrics(df, c["prev_close"])
    if pm:
        spec["sim"]["extra_break_high"] = (
            c["prev_close"] * (1 + pm["pm_high_gain"] / 100))
    tr = x.sim_window(w, c, spec)
    pnl = sum(t["pnl"] for t in tr)
    print(f"  TRADES: {len(tr)} on {c['symbol']}, day P&L "
          f"${pnl:+,.2f} (on $15k)")
    for t in tr[:12]:
        print(f"    {str(t['entry_time'])[11:16]}->"
              f"{str(t['exit_time'])[11:16]} "
              f"{t['entry']:.2f}->{t['exit']:.2f} "
              f"${t['pnl']:+8.2f}  {t.get('reason','')}")
    return pnl, tr


def main():
    pools = build_pools()
    total = 0.0
    summary = {}
    for d in DATES:
        if d not in pools:
            print(f"\nERROR: no pool for {d} (grouped-daily unavailable)")
            continue
        pnl, tr = replay(d, pools[d])
        total += pnl
        summary[d] = dict(pnl=round(pnl, 2), trades=len(tr))
    print(f"\n3-day C30 backtest total: ${total:+,.2f} on a $15k slot")
    (ROOT / "data/massive/replay_paper_days.json").write_text(
        json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
