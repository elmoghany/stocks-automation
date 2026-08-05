"""AX round 2 -- adaptation experiments per user directive. Both years,
$15k/day, one change each from AX00 (C1 top-1 + calm-gap, 7-noon).

  AX02  gapper-supply throttle (1 calm candidate -> half size)
  AX04  premarket-structure scoring picks the candidate (not raw gain)
  AX06  scale-out ladder: bank 1/3 at +25%, trail the rest
  AX08  adaptive trail: widen 20%->30% once +100%
  AX12  hot-sector v2: sectors where qualifying gappers CLUSTERED in the
        trailing 10 sessions (>=3 hits) -- replaces ETF trend list
  AX13  DROP the hot-sector filter entirely (halal + rest unchanged)
  AX14x top-N gainers sweep, $15k split across N: N in 1,2,3,4,5,6,8,10
  AX15  afternoon session: same machine, window 2PM-8PM (incl after-hours)
  AX16x exit sweep: trail 15/25/30 (stop5) and stop 3/8 (trail20)
  AX17a VWAP-cross entry (replaces ORB+patterns)
  AX17b EMA9>EMA21 cross entry
"""

import importlib.util
import json
import sys
from datetime import time as dtime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
_spec = importlib.util.spec_from_file_location("pennystocks",
                                               ROOT / "day-trading.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)
ps.SURGE_WINDOW_MIN = 50
ps.PRICE_MAX = float("inf")

M1 = ROOT / "data" / "massive" / "m1"
VER = json.loads((ROOT / "data/backtest60/rules_ytd.json").read_text())
UP = ["technology", "software", "semiconductor", "artificial intelligence",
      "health", "biotech", "pharmaceutical", "drug", "medical",
      "industrial", "machinery", "engineering", "construction", "transport",
      "trucking", "railroads", "energy", "oil", "gas", "solar", "renewable",
      "petroleum", "materials", "chemical", "mining", "gold", "silver",
      "steel", "copper", "consumer defensive", "food", "beverage",
      "household", "grocery", "discount stores", "packaged foods",
      "real estate", "reit"]


def get(sym, date):
    f = M1 / f"{sym}_{date}.csv"
    if not f.exists() or f.read_text(errors="ignore").startswith("EMPTY"):
        return None
    df = pd.read_csv(f)
    df["begins_at"] = (pd.to_datetime(df["begins_at"], utc=True)
                       .dt.tz_convert(ps.ET))
    return df.set_index("begins_at").sort_index()


def pools(label, sector_mode):
    gap = json.loads((ROOT / f"data/massive/gappers_{label}.json").read_text())
    halal = [c for c in gap if VER.get(c["symbol"], {}).get("halal_ok")]
    if sector_mode == "none":
        keep = halal
    elif sector_mode == "static":
        keep = [c for c in halal
                if any(w in VER[c["symbol"]].get("sector_raw", "").lower()
                       for w in UP)]
    elif sector_mode == "cluster":
        # sectors with >=3 halal gappers in trailing 10 sessions
        by_date = {}
        for c in halal:
            by_date.setdefault(c["date"], []).append(c)
        dates = sorted(by_date)
        keep = []
        recent = []   # list of (date, sector)
        for d in dates:
            cnt = {}
            for _, sec in recent[-400:]:
                cnt[sec] = cnt.get(sec, 0) + 1
            hot = {s for s, n in cnt.items() if n >= 3}
            for c in by_date[d]:
                sec = VER[c["symbol"]].get("sector_raw", "").split("/")[0].strip()
                if sec in hot:
                    keep.append(c)
            for c in by_date[d]:
                sec = VER[c["symbol"]].get("sector_raw", "").split("/")[0].strip()
                recent.append((d, sec))
            recent = [(dd, ss) for dd, ss in recent
                      if dd in dates[max(0, dates.index(d) - 10):dates.index(d) + 1]]
    by_day = {}
    for c in keep:
        by_day.setdefault(c["date"], []).append(c)
    return by_day


def g7(c, w):
    return ((float(w["Open"].iloc[0]) / c["prev_close"] - 1) * 100
            if c["prev_close"] else 999)


def structure_score(w):
    pre = w[w.index.time < dtime(9, 30)]
    if len(pre) < 10:
        return 0.0
    lows = pre["Low"].resample("15min").min().dropna()
    hl = sum(1 for a, b in zip(lows, lows[1:]) if b > a)
    rng = pre["High"].max() - pre["Low"].min()
    pos = (pre["Close"].iloc[-1] - pre["Low"].min()) / rng if rng > 0 else 0
    return hl + 2 * pos


def run(label, name, sector_mode="static", top_n=1, budget=None,
        window=(dtime(7, 0), dtime(12, 0)), pick="gain", throttle=False,
        sim_kw=None):
    by_day = pools(label, sector_mode)
    days = []
    monthly = {}
    for date, cs in sorted(by_day.items()):
        ranked = sorted(cs, key=lambda x: -x["gain_pct"])
        calm = []
        for c in ranked[:8]:
            df = get(c["symbol"], date)
            if df is None:
                continue
            w = df[(df.index.time >= window[0]) & (df.index.time < window[1])]
            if len(w) < 15:
                continue
            if g7(c, w) <= 20:
                calm.append((c, w))
        if not calm:
            continue
        if pick == "structure":
            calm.sort(key=lambda cw: -structure_score(cw[1]))
        picks = calm[:top_n]
        per = (budget if budget else 15000) / len(picks) if top_n > 1 \
            else (budget if budget else 15000)
        if throttle and len(calm) == 1:
            per *= 0.5
        dp = 0.0
        traded = False
        for c, w in picks:
            kw = dict(verbose=False, buy_set=None, vol_confirm=False,
                      trail_pct=20, stop_pct=5, prev_close=c["prev_close"],
                      budget=per, orb=True, orb_bars=15, max_vol_frac=0.10,
                      vol_frac_window=5)
            kw.update(sim_kw or {})
            tr = ps.simulate_trades(w, **kw)
            dp += sum(x["pnl"] for x in tr)
            traded = traded or bool(tr)
        if traded:
            days.append(dp)
            monthly.setdefault(date[:7], []).append(dp)
    negm = sum(1 for v in monthly.values() if sum(v) < 0)
    tot = sum(days)
    print(f"{name:<26} {label:<6} {len(days):>4} {tot:>+12,.0f} "
          f"{tot / len(days) if days else 0:>+8,.0f} {negm:>4}/{len(monthly):<3}",
          flush=True)


def vwap_sim(w, prev_close, entry_mode):
    cd = ps.Candles(w)
    tp = (w["High"] + w["Low"] + w["Close"]) / 3
    cum_v = w["Volume"].cumsum()
    vwap = ((tp * w["Volume"]).cumsum() / cum_v.replace(0, 1)).values
    ema9 = w["Close"].ewm(span=9, adjust=False).mean().values
    ema21 = w["Close"].ewm(span=21, adjust=False).mean().values
    c, h, l = cd.c, cd.h, cd.l
    n = cd.n
    shares = 0
    entry = peak = 0.0
    pnl = 0.0
    trades = 0
    for i in range(15, n):
        px = c[i]
        if shares == 0:
            if entry_mode == "vwap":
                sig = c[i] > vwap[i] and c[i - 1] <= vwap[i - 1]
            else:
                sig = ema9[i] > ema21[i] and ema9[i - 1] <= ema21[i - 1]
            if sig and px >= 2.0 and (not prev_close
                                      or px >= prev_close * 1.10):
                vbase = sum(cd.v[max(0, i - 4):i + 1])
                shares = min(int(15000 // px), int(vbase * 0.10) or 1)
                if shares < 1:
                    shares = 0
                    continue
                entry = peak = px
        else:
            peak = max(peak, h[i])
            stop = max(entry * 0.95, peak * 0.80)
            if l[i] <= stop:
                pnl += (stop - entry) * shares
                trades += 1
                shares = 0
    if shares:
        pnl += (c[n - 1] - entry) * shares
        trades += 1
    return pnl, trades


def run_signal(label, name, entry_mode):
    by_day = pools(label, "static")
    days = []
    monthly = {}
    for date, cs in sorted(by_day.items()):
        picked = None
        for c in sorted(cs, key=lambda x: -x["gain_pct"])[:4]:
            df = get(c["symbol"], date)
            if df is None:
                continue
            w = df[(df.index.time >= dtime(7, 0))
                   & (df.index.time < dtime(12, 0))]
            if len(w) < 20:
                continue
            if g7(c, w) <= 20:
                picked = (c, w)
                break
        if picked is None:
            continue
        c, w = picked
        pnl, ntr = vwap_sim(w, c["prev_close"], entry_mode)
        if ntr == 0:
            continue
        days.append(pnl)
        monthly.setdefault(date[:7], []).append(pnl)
    negm = sum(1 for v in monthly.values() if sum(v) < 0)
    tot = sum(days)
    print(f"{name:<26} {label:<6} {len(days):>4} {tot:>+12,.0f} "
          f"{tot / len(days) if days else 0:>+8,.0f} {negm:>4}/{len(monthly):<3}",
          flush=True)


def main():
    print(f"{'EXPERIMENT':<26} {'year':<6} {'days':>4} {'total':>12} "
          f"{'avg/d':>8} {'negm':>8}")
    for label in ("year", "y2025"):
        run(label, "AX00 baseline")
        run(label, "AX02 supply-throttle", throttle=True)
        run(label, "AX04 structure-scoring", pick="structure")
        run(label, "AX06 scale-out 1/3@+25%",
            sim_kw=dict(scale_out_at=25.0))
        run(label, "AX08 trail widen @+100%",
            sim_kw=dict(trail_widen_at=100.0))
        run(label, "AX12 cluster-sectors", sector_mode="cluster")
        run(label, "AX13 NO sector filter", sector_mode="none")
        for n in (2, 3, 4, 5, 6, 8, 10):
            run(label, f"AX14-{n} top-{n} split", top_n=n)
        run(label, "AX15 afternoon 2-8PM",
            window=(dtime(14, 0), dtime(20, 0)))
        for t in (15, 25, 30):
            run(label, f"AX16 trail {t}%", sim_kw=dict(trail_pct=t))
        for st in (3, 8):
            run(label, f"AX16 stop {st}%", sim_kw=dict(stop_pct=st))
        run_signal(label, "AX17a VWAP-cross entry", "vwap")
        run_signal(label, "AX17b EMA9/21 entry", "ema")


if __name__ == "__main__":
    main()
