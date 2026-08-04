"""FULL-YEAR backtest (Aug 2025 -> Aug 2026) of the top-10 configs on
Massive (Polygon) 1-MINUTE bars with real premarket volume.

Stages (each cached under data/massive/):
 1. Whole-market daily sweep via grouped-daily (1 call/day, ~315 days incl.
    50-day volume warmup) -> qualifying gapper stock-days for two pools:
    band (low<=16 reachable) and noceil.
 2. Upward-sector + halal filters (yfinance snapshots; reuses/extends the
    rules_ytd.json verdict cache).
 3. Per-config day picks -> Massive 1-min bars (cached per stock-day) ->
    simulate the 10 configs: $15k/position, 10% bar-volume cap,
    ORB + all-pattern entries, trail 20%/stop 5%, same-day flatten.

Top-10 configs (from CONFIGS-TESTED.md):
  1 A2cap14  band  7-noon top2 cap14   6 B2cap16 band 7-2PM top1 cap16
  2 A2cap16  band  7-noon top2 cap16   7 A2cap10 band 7-noon top2 cap10
  3 B3cap16  band  7-4PM  top2 cap16   8 C1      noceil 7-noon top2 nocap
  4 B3cap14  band  7-4PM  top2 cap14   9 CAP14t1 band 7-noon top1 cap14
  5 B2cap14  band  7-2PM  top1 cap14  10 V2a     band 7-noon top1 cap16
"""

import importlib.util
import json
import sys
from datetime import date as ddate, time as dtime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("pennystocks",
                                               ROOT / "day-trading.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

from trading import massive

MCACHE = ROOT / "data" / "massive"
M1DIR = MCACHE / "m1"
MCACHE.mkdir(parents=True, exist_ok=True)
M1DIR.mkdir(exist_ok=True)
RULES_F = ROOT / "data" / "backtest60" / "rules_ytd.json"

# CLI: python penny_year_backtest.py [label] [year_start] [year_end]
LABEL = sys.argv[1] if len(sys.argv) > 1 else "year"
YEAR_START = sys.argv[2] if len(sys.argv) > 2 else "2025-08-01"
YEAR_END = sys.argv[3] if len(sys.argv) > 3 else "2026-08-01"
WARMUP_START = (ddate.fromisoformat(YEAR_START)
                - timedelta(days=78)).isoformat()
MIN_GAIN = 10.0
MIN_RVOL = 5.0
BUDGET = 15_000.0

UPWARD_SECTOR_WORDS = [
    "technology", "software", "semiconductor", "artificial intelligence",
    "health", "biotech", "pharmaceutical", "drug", "medical",
    "industrial", "machinery", "engineering", "construction", "transport",
    "trucking", "railroads",
    "energy", "oil", "gas", "solar", "renewable", "petroleum",
    "materials", "chemical", "mining", "gold", "silver", "steel", "copper",
    "consumer defensive", "food", "beverage", "household", "grocery",
    "discount stores", "packaged foods",
    "real estate", "reit",
]

CONFIGS = [
    ("A2cap14", "band", dtime(12, 0), 2, 14.0),
    ("A2cap16", "band", dtime(12, 0), 2, 16.0),
    ("B3cap16", "band", dtime(16, 0), 2, 16.0),
    ("B3cap14", "band", dtime(16, 0), 2, 14.0),
    ("B2cap14", "band", dtime(14, 0), 1, 14.0),
    ("B2cap16", "band", dtime(14, 0), 1, 16.0),
    ("A2cap10", "band", dtime(12, 0), 2, 10.0),
    ("C1nocap", "noceil", dtime(12, 0), 2, 1e9),
    ("CAP14t1", "band", dtime(12, 0), 1, 14.0),
    ("V2a_t1", "band", dtime(12, 0), 1, 16.0),
]


def stage1_discover():
    cache_f = MCACHE / f"gappers_{LABEL}.json"
    if cache_f.exists():
        return json.loads(cache_f.read_text())
    universe = set(json.loads(
        (ROOT / "data/backtest60/universe.json").read_text()))
    hist = {}   # sym -> list of (date, high, low, close, volume)
    found = []
    d = ddate.fromisoformat(WARMUP_START)
    end = ddate.fromisoformat(YEAR_END)
    n_days = 0
    while d <= end:
        if d.weekday() < 5:
            rows = massive.grouped_daily(d.isoformat())
            n_days += 1
            if n_days % 20 == 0:
                print(f"  daily {d} ({n_days} sessions, "
                      f"{len(found)} hits so far)", flush=True)
            for r in rows:
                sym = r.get("T", "")
                if sym not in universe:
                    continue
                c = r.get("c") or 0
                if c > 75 or c <= 0.2:
                    continue
                h = hist.setdefault(sym, [])
                hi, lo, vol = r.get("h", 0), r.get("l", 0), r.get("v", 0)
                if len(h) >= 50 and d.isoformat() >= YEAR_START:
                    prev = h[-1][3]
                    if prev > 0 and (hi / prev - 1) * 100 >= MIN_GAIN \
                            and hi >= 2.0:
                        av = sum(x[4] for x in h[-50:]) / 50
                        if av > 0 and vol >= MIN_RVOL * av:
                            found.append({
                                "symbol": sym, "date": d.isoformat(),
                                "gain_pct": round((hi / prev - 1) * 100, 1),
                                "prev_close": round(float(prev), 4),
                                "rvol": round(float(vol / av), 1),
                                "band": bool(lo <= 16.0)})
                h.append((d.isoformat(), hi, lo, c, vol))
                if len(h) > 60:
                    del h[0]
        d += timedelta(days=1)
    cache_f.write_text(json.dumps(found))
    return found


def stage2_filter(cands):
    verdicts = json.loads(RULES_F.read_text()) if RULES_F.exists() else {}
    import yfinance as yf
    syms = sorted({c["symbol"] for c in cands})
    print(f"  {len(syms)} unique symbols; "
          f"{sum(1 for s in syms if s in verdicts)} already cached", flush=True)
    for n, sym in enumerate(syms):
        v = verdicts.get(sym)
        if v is None:
            v = {"float_ok": None, "halal_ok": None, "sector_raw": "",
                 "reason": ""}
            verdicts[sym] = v
        if v.get("halal_ok") is not None or v.get("reason"):
            continue
        try:
            t = yf.Ticker(sym)
            if not v.get("sector_raw"):
                info = t.info or {}
                v["sector_raw"] = (f"{info.get('sector', '')} / "
                                   f"{info.get('industry', '')}")
            if not any(w in v["sector_raw"].lower()
                       for w in UPWARD_SECTOR_WORDS):
                v["reason"] = "sector"
                continue
            h = ps.halal_check(sym, t)
            v["halal_ok"] = h["halal"]
            if not h["halal"]:
                v["reason"] = f"NOT HALAL: {h['fail_reason']}"
        except Exception as e:
            v["reason"] = f"error: {e}"
        if n % 20 == 0:
            RULES_F.write_text(json.dumps(verdicts))
            print(f"  ..verify {n}/{len(syms)}", flush=True)
    RULES_F.write_text(json.dumps(verdicts))

    out = []
    for c in cands:
        v = verdicts.get(c["symbol"], {})
        sector_ok = any(w in v.get("sector_raw", "").lower()
                        for w in UPWARD_SECTOR_WORDS)
        if sector_ok and v.get("halal_ok"):
            out.append(c)
    return out


def get_m1(sym, date):
    f = M1DIR / f"{sym}_{date}.csv"
    if not f.exists():
        df = massive.minute_bars(sym, date)
        if df is None or df.empty:
            f.write_text("EMPTY")
            return None
        out = df.reset_index()
        out["begins_at"] = out["begins_at"].dt.tz_convert("UTC")
        out.to_csv(f, index=False)
    if f.read_text(errors="ignore").startswith("EMPTY"):
        return None
    df = pd.read_csv(f)
    df["begins_at"] = (pd.to_datetime(df["begins_at"], utc=True)
                       .dt.tz_convert(ps.ET))
    return df.set_index("begins_at").sort_index()


def main():
    print("Stage 1: whole-market daily sweep via Massive grouped-daily...")
    cands = stage1_discover()
    print(f"  {len(cands)} qualifying stock-days "
          f"({len({c['symbol'] for c in cands})} symbols)")

    print("Stage 2: upward-sector + halal filters...")
    final = stage2_filter(cands)
    print(f"  {len(final)} stock-days survive "
          f"({len({c['symbol'] for c in final})} symbols)")
    pools = {"band": [c for c in final if c["band"]], "noceil": final}
    print(f"  band pool {len(pools['band'])}, noceil {len(pools['noceil'])}")

    # day picks (superset for prefetch)
    def picks(pool, top_n):
        by_day = {}
        for c in pool:
            by_day.setdefault(c["date"], []).append(c)
        return {d: sorted(cs, key=lambda x: -x["gain_pct"])[:top_n]
                for d, cs in by_day.items()}

    print("Stage 3: simulating 10 configs on Massive 1-min bars...")
    results = {}
    for name, pool_name, end_t, top_n, cap in CONFIGS:
        saved = ps.PRICE_MAX
        ps.PRICE_MAX = cap
        days = []
        total = 0.0
        try:
            for date, cs in sorted(picks(pools[pool_name], top_n).items()):
                day_pnl = 0.0
                traded = False
                for c in cs:
                    df = get_m1(c["symbol"], date)
                    if df is None:
                        continue
                    w = df[(df.index.time >= dtime(7, 0))
                           & (df.index.time < end_t)]
                    if len(w) < 20:
                        continue
                    tr = ps.simulate_trades(
                        w, verbose=False, buy_set=None, vol_confirm=False,
                        trail_pct=20, stop_pct=5,
                        prev_close=c["prev_close"], budget=BUDGET,
                        orb=True, max_vol_frac=0.10)
                    day_pnl += sum(t["pnl"] for t in tr)
                    traded = traded or bool(tr)
                if traded:
                    days.append(day_pnl)
                total += day_pnl
        finally:
            ps.PRICE_MAX = saved
        n = len(days)
        wins = sum(1 for x in days if x > 0)
        big = sum(1 for x in days if x >= 1000)
        results[name] = (total, n, wins, big,
                         min(days) if days else 0.0)
        print(f"  {name:<10} {n:>4}d  ${total:>+12.2f}  "
              f"${total / n if n else 0:>+9.2f}/d  {wins}W  "
              f">=1k:{big}  worst {min(days) if days else 0:+.2f}",
              flush=True)

    print(f"\n{'=' * 78}")
    print(f"  FULL YEAR Aug 2025 -> Aug 2026, $15k/pos, Massive 1-min bars")
    print(f"{'=' * 78}")
    print(f"{'CONFIG':<10} {'days':>5} {'total':>13} {'avg/day':>10} "
          f"{'win':>9} {'>=1k':>5} {'worst':>10}")
    for name, (tot, n, w, big, worst) in sorted(
            results.items(), key=lambda kv: -kv[1][0]):
        print(f"{name:<10} {n:>5} {tot:>+13.2f} "
              f"{tot / n if n else 0:>+10.2f} {w:>4}/{n:<4} {big:>5} "
              f"{worst:>+10.2f}")
    (MCACHE / f"year_results_{LABEL}.json").write_text(json.dumps(results))


if __name__ == "__main__":
    main()
