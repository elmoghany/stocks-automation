"""EARNINGS-X3 Strategy 1 (ET40-ET45): minute-level entries/exits on
post-earnings dip mornings, $50k/event (user raised the slot from $15k
2026-08-05).

The daily-bar champion (ET12: beat + open gap <= -3%, buy open, sell
close) buys blindly into the dip and eats tail losses (LII -12.4%).
Here we replay every ET12-qualifying reaction day on 1-minute bars
(Massive/Polygon, throttled 5 req/min, cached) and test penny-book
mechanics scaled to large-cap moves:

  ET40 anchor: buy 9:30 open, sell 15:59 close (must ~match daily ET12)
  ET41 bounce-confirm entry: enter when a 1-min close crosses above the
       prior bar's high AND rolling volume-pressure P(10) >= 0 (first
       such bar after 9:30; skip day if none by 11:00)
  ET42 open entry + trail exit: 2% trailing stop from the running peak,
       widened to 4% while P(10) >= +0.3; sell at close latest
  ET43 = ET41 entry + ET42 trail exit
  ET44 open entry + hard stop -3% (tail-cutter), else close
  ET45 = ET43 but one slot/day only, deepest qualifying dip
Pressure = the day-trading sv formula on 1-min bars, 10-bar window.
Events: earnings_x2_events.json (beat + gap<=-3%). Cache:
data/minute_cache/{SYM}_{date}.csv. ~250 event-days -> first fetch
~1 hour at the free-tier throttle; reruns are instant.
"""

import json
import sys
import time
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
from shared import massive  # noqa: E402

EV_C = ROOT / "data/earnings_x2_events.json"
CACHE = ROOT / "data/minute_cache"
CACHE.mkdir(parents=True, exist_ok=True)
BUDGET = 50_000


def beat(e):
    return e.get("surprise") is not None and e["surprise"] > 0


def qualifying():
    ev = json.loads(EV_C.read_text())
    sel = [e for e in ev if beat(e)
           and (e["open"] / e["pre_close"] - 1) * 100 <= -3]
    sel.sort(key=lambda e: (e["date"], e["sym"]))
    return sel


def bars_for(sym, date):
    f = CACHE / f"{sym}_{date}.csv"
    if f.exists():
        try:
            df = pd.read_csv(f, index_col=0, parse_dates=True)
            return df if len(df) else None
        except Exception:
            return None
    try:
        df = massive.minute_bars(sym, date)
    except Exception as e:
        print(f"  {sym} {date}: {e}", flush=True)
        return None
    (df if df is not None else pd.DataFrame()).to_csv(f)
    return df if df is not None and len(df) else None


def session(df):
    """Regular-session 1-min bars in ET, 9:30-15:59."""
    d = df.copy()
    idx = d.index.tz_localize("UTC").tz_convert("America/New_York") \
        if d.index.tz is None else d.index.tz_convert("America/New_York")
    d.index = idx
    d = d.between_time("09:30", "15:59")
    return d if len(d) >= 60 else None


def pressures(d, win=10):
    sv, v = [], []
    for _, b in d.iterrows():
        h, l, c, vol = b["High"], b["Low"], b["Close"], b["Volume"]
        if h > l and vol > 0:
            sv.append(vol * (2 * (c - l) - (h - l)) / (h - l))
            v.append(vol)
        else:
            sv.append(0.0)
            v.append(0.0)
    ps = []
    csv_, cv = 0.0, 0.0
    svs, vs = pd.Series(sv), pd.Series(v)
    for i in range(len(d)):
        lo = max(0, i - win + 1)
        vv = vs.iloc[lo:i + 1].sum()
        ps.append(svs.iloc[lo:i + 1].sum() / vv if vv > 0 else None)
    return ps


def run_day(d, mode):
    """Return trade %-return for one reaction day under a mode."""
    o = d["Open"].iloc[0]
    closes = d["Close"].values
    highs = d["High"].values
    ps = pressures(d)
    n = len(d)

    def entry_bounce():
        # first bar (after the first) whose close crosses the prior
        # bar's high with non-negative pressure, by 11:00
        cutoff = d.index[0].replace(hour=11, minute=0)
        for i in range(1, n):
            if d.index[i] > cutoff:
                return None, None
            if closes[i] > highs[i - 1] and (ps[i] is not None
                                             and ps[i] >= 0):
                return i, closes[i]
        return None, None

    def trail_exit(ei, ep):
        peak = ep
        for i in range(ei + 1, n):
            peak = max(peak, closes[i])
            wide = ps[i] is not None and ps[i] >= 0.3
            stop = peak * (1 - (0.04 if wide else 0.02))
            if closes[i] <= stop:
                return (closes[i] / ep - 1) * 100
        return (closes[-1] / ep - 1) * 100

    if mode == "ET40":
        return (closes[-1] / o - 1) * 100
    if mode == "ET41":
        ei, ep = entry_bounce()
        return None if ei is None else (closes[-1] / ep - 1) * 100
    if mode == "ET42":
        return trail_exit(0, o)
    if mode == "ET43":
        ei, ep = entry_bounce()
        return None if ei is None else trail_exit(ei, ep)
    if mode == "ET44":
        for i in range(1, n):
            if closes[i] <= o * 0.97:
                return (closes[i] / o - 1) * 100
        return (closes[-1] / o - 1) * 100


def main():
    sel = qualifying()
    print(f"{len(sel)} qualifying event-days", flush=True)
    per_day = {}
    results = {m: [] for m in ("ET40", "ET41", "ET42", "ET43", "ET44")}
    got = 0
    for k, e in enumerate(sel):
        df = bars_for(e["sym"], e["date"])
        if df is None:
            continue
        d = session(df)
        if d is None:
            continue
        got += 1
        dip = (e["open"] / e["pre_close"] - 1) * 100
        for m in results:
            r = run_day(d, m)
            if r is not None:
                results[m].append(r)
                if m == "ET43":
                    per_day.setdefault(e["date"], []).append((dip, r))
        if k % 20 == 0:
            print(f"  {k}/{len(sel)} ({got} usable)", flush=True)
    # ET45: one slot/day, deepest dip, ET43 mechanics
    et45 = [min(v, key=lambda x: x[0])[1] for v in per_day.values()]
    results["ET45"] = et45

    print(f"\nEARNINGS-X3 minute-level  ${BUDGET:,}/event "
          f"({got} usable days)")
    for m, rets in results.items():
        if not rets:
            print(f"{m}: n=0")
            continue
        n_ = len(rets)
        win = 100 * sum(1 for r in rets if r > 0) / n_
        avg = sum(rets) / n_
        tot = sum(BUDGET * r / 100 for r in rets)
        print(f"{m}  n={n_:>3} win={win:5.1f}% avg={avg:+6.3f}% "
              f"tot=${tot:+,.0f}")
    (ROOT / "data/earnings_minute_results.json").write_text(json.dumps(
        {m: [round(r, 3) for r in v] for m, v in results.items()}))


if __name__ == "__main__":
    main()
