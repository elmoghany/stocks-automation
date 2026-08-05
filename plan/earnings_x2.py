"""EARNINGS-X2 campaign (ET12-ET31): the two user strategies of
2026-08-05, many variants, on the broad halal universe (S&P 500 + 400
midcaps via plan/build_universe.py, price > $2).

STRATEGY A -- post-earnings dip-buy (news is OUT; company BEAT):
  buy the dip either at the next-morning open or in the same-evening
  after-hours (pm reporters), gates: halal + EPS beat (+ optional
  5y-strong uptrend, strong financials, buy/sell-volume pressure),
  exits: same-day close, or targets +8/+10/+15% (sell when the day's
  high crosses the target), holding capped at 1-2 sessions.
STRATEGY B -- pre-earnings run-up:
  buy N sessions before the report (N in 1,2,3,5,7), sell at the last
  close BEFORE the release ("a few minutes before" for pm reporters is
  approximated by the report-day close). Variants: only-if-dipping
  (entry after a 5-session decline), strong/financial gates, positive
  entry-day volume pressure. NOTE: N>2 exceeds the user's preferred
  1-2 day hold; those rows are labeled HOLD>2.

Reaction-day convention uses the announcement HOUR (pm -> reaction is
the NEXT session; am -> the report-day session; mid-day stamps skipped).
Beat = yfinance 'Surprise(%)' > 0. Strong = 5y total return >= +100%
AND price > 200d SMA, point-in-time at the last pre-release close.
Strong financials = latest quarterly net income > 0 (current statement,
point-in-time approximation; cached). Pressure = sum over hourly bars
of v*(2(c-l)-(h-l))/(h-l) divided by sum(v), yfinance 1h bars
(prepost=True; ~730d reach). $15k notional per event.
Window: Aug 2025..Jul 2026. Caches: data/earnings_x2_events.json,
data/earnings_halal_big.json, data/earnings_fin_big.json.
Controls: ET31 runs the dip-buy on MISSES -- the beat gate must matter.
"""

import importlib.util
import json
import sys
import time
import warnings
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("dt", ROOT / "day-trading.py")
dt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dt)
from plan.build_universe import load as load_universe  # noqa: E402

WINDOW = ("2025-08-01", "2026-07-31")
BUDGET = 15_000
LAGS = (1, 2, 3, 5, 7)
HALAL_C = ROOT / "data/earnings_halal_big.json"
FIN_C = ROOT / "data/earnings_fin_big.json"
EV_C = ROOT / "data/earnings_x2_events.json"


def screen_universe(syms):
    """Halal + latest-quarter-profitable, cached, resumable."""
    halal = json.loads(HALAL_C.read_text()) if HALAL_C.exists() else {}
    fin = json.loads(FIN_C.read_text()) if FIN_C.exists() else {}
    todo = [s for s in syms if s not in halal]
    for n, sym in enumerate(todo):
        try:
            t = yf.Ticker(sym)
            r = dt.halal_check(sym, t=t)
            halal[sym] = bool(r["halal"])
            if halal[sym] and sym not in fin:
                inc = t.quarterly_income_stmt
                ni = None
                if inc is not None and not inc.empty \
                        and "Net Income" in inc.index:
                    v = inc.loc["Net Income"].iloc[0]
                    ni = None if pd.isna(v) else float(v)
                fin[sym] = bool(ni is not None and ni > 0)
        except Exception:
            halal[sym] = False
        if n % 25 == 0:
            print(f"  screen {n}/{len(todo)}", flush=True)
            HALAL_C.write_text(json.dumps(halal))
            FIN_C.write_text(json.dumps(fin))
        time.sleep(0.15)
    HALAL_C.write_text(json.dumps(halal))
    FIN_C.write_text(json.dumps(fin))
    ok = [s for s in syms if halal.get(s)]
    print(f"halal: {len(ok)}/{len(syms)} "
          f"(profitable: {sum(1 for s in ok if fin.get(s))})", flush=True)
    return ok, fin


def day_pressure(bars):
    """Volume-pressure in [-1,1] over a set of OHLCV bars."""
    sv = v = 0.0
    for _, b in bars.iterrows():
        h, l, c = float(b["High"]), float(b["Low"]), float(b["Close"])
        vol = float(b["Volume"])
        if h > l and vol > 0:
            sv += vol * (2 * (c - l) - (h - l)) / (h - l)
            v += vol
    return sv / v if v > 0 else None


def build_events(syms, fin):
    lo, hi = WINDOW
    out = []
    for n, sym in enumerate(syms):
        try:
            t = yf.Ticker(sym)
            h = t.history(period="6y", auto_adjust=True)
            if len(h) < 500 or float(h["Close"].iloc[-1]) <= 2:
                continue
            h.index = h.index.tz_localize(None)
            ed = t.get_earnings_dates(limit=12)
            if ed is None or len(ed) == 0:
                continue
            try:
                hh = t.history(period="729d", interval="1h", prepost=True)
            except Exception:
                hh = pd.DataFrame()
        except Exception as e:
            print(f"  {sym}: {e}", flush=True)
            continue
        closes, opens = h["Close"], h["Open"]
        highs = h["High"]
        idx = h.index
        surprises = {}
        for ts, row in ed.iterrows():
            d = ts.tz_localize(None)
            sp = row.get("Surprise(%)")
            surprises.setdefault(
                d.normalize(),
                (d, None if pd.isna(sp) else float(sp)))
        for d, (ts, surprise) in sorted(surprises.items()):
            if ts.hour >= 15:
                pre_c, post_c, timing = idx[idx <= d], idx[idx > d], "pm"
            elif ts.hour <= 9:
                pre_c, post_c, timing = idx[idx < d], idx[idx >= d], "am"
            else:
                continue
            if len(pre_c) == 0 or len(post_c) == 0:
                continue
            pre, post = pre_c[-1], post_c[0]
            if not (lo <= str(post.date()) <= hi):
                continue
            after = idx[idx > post]
            past = closes[closes.index <= pre]
            if float(past.iloc[-1]) <= 2:
                continue
            mom5 = ((past.iloc[-1] / past.iloc[-1250] - 1) * 100
                    if len(past) >= 1250 else None)
            sma200 = past.tail(200).mean() if len(past) >= 200 else None
            strong = (mom5 is not None and mom5 >= 100
                      and sma200 is not None and past.iloc[-1] > sma200)
            ev = dict(
                sym=sym, date=str(post.date()), timing=timing,
                surprise=surprise, strong=bool(strong),
                fin=bool(fin.get(sym)),
                pre_close=round(float(closes[pre]), 4),
                open=round(float(opens[post]), 4),
                high=round(float(highs[post]), 4),
                close=round(float(closes[post]), 4),
                high1=round(float(highs[after[0]]), 4) if len(after)
                else None,
                close1=round(float(closes[after[0]]), 4) if len(after)
                else None)
            # pre-earnings run-up ladder: entry close L sessions before
            # pre, plus was-it-dipping and entry-day pressure
            pos = idx.get_loc(pre)
            for L in LAGS:
                if pos - L < 0:
                    continue
                eday = idx[pos - L]
                ev[f"lag{L}"] = round(float(closes[eday]), 4)
                if pos - L - 5 >= 0:
                    ev[f"dip{L}"] = bool(closes[eday]
                                         < closes[idx[pos - L - 5]])
                if not hh.empty:
                    bars = hh[(hh.index.date == eday.date())]
                    p = day_pressure(bars) if len(bars) else None
                    if p is not None:
                        ev[f"p{L}"] = round(p, 3)
            # after-hours entry (pm only): first post-16:00 hourly bar
            # on the report day, and that evening's pressure
            if timing == "pm" and not hh.empty:
                ah = hh[(hh.index.date == pre.date())
                        & (hh.index.hour >= 16)]
                if len(ah):
                    ev["ah_px"] = round(float(ah["Close"].iloc[0]), 4)
                    ev["ah_p"] = (round(day_pressure(ah), 3)
                                  if day_pressure(ah) is not None
                                  else None)
            # reaction-morning first-hour pressure (for the causal
            # pressure-gated variant: gate on bar 1, enter bar 2)
            if not hh.empty:
                rb = hh[(hh.index.date == post.date())
                        & (hh.index.hour >= 9) & (hh.index.hour < 16)]
                if len(rb) >= 2:
                    ev["p_h1"] = (round(day_pressure(rb.iloc[:1]), 3)
                                  if day_pressure(rb.iloc[:1]) is not None
                                  else None)
                    ev["h2_open"] = round(float(rb["Open"].iloc[1]), 4)
            out.append(ev)
        if n % 25 == 0:
            print(f"  events {n}/{len(syms)} ({len(out)})", flush=True)
            EV_C.write_text(json.dumps(out))
        time.sleep(0.1)
    EV_C.write_text(json.dumps(out))
    print(f"saved {len(out)} events", flush=True)
    return out


def target_exit(entry, days, tgt):
    """days = [(high, close), ...] in session order; sell at +tgt% the
    first time a session high crosses it, else at the last close."""
    for hi_, cl in days:
        if hi_ is not None and hi_ >= entry * (1 + tgt / 100):
            return tgt
        last = cl
    return (last / entry - 1) * 100 if last else None


def beat(e):
    return e.get("surprise") is not None and e["surprise"] > 0


def dipped(e, thr):
    return (e["open"] / e["pre_close"] - 1) * 100 <= thr


def morning(e, tgt=None, cap=1):
    entry = e["open"]
    if tgt is None:
        return (e["close"] / entry - 1) * 100
    days = [(e["high"], e["close"])]
    if cap >= 2 and e.get("close1"):
        days.append((e.get("high1"), e["close1"]))
    return target_exit(entry, days, tgt)


def afterhours(e, tgt=None):
    entry = e.get("ah_px")
    if not entry or not e.get("close"):
        return None
    if tgt is None:
        return (e["close"] / entry - 1) * 100
    return target_exit(entry, [(e["high"], e["close"])], tgt)


def runup(e, L):
    px = e.get(f"lag{L}")
    return (e["pre_close"] / px - 1) * 100 if px else None


# (id, description, callable event -> ret% or None)
def EXPERIMENTS():
    A_gates = lambda e: beat(e) and e["strong"] and e["fin"]  # noqa: E731
    return [
        ("ET12", "A dip<=-3% + beat: morning open -> close",
         lambda e: morning(e) if dipped(e, -3) and beat(e) else None),
        ("ET13", "A dip<=-3% + beat + strong + fin: open -> close",
         lambda e: morning(e) if dipped(e, -3) and A_gates(e) else None),
        ("ET14", "A = ET13 with +8% target (1d)",
         lambda e: morning(e, 8) if dipped(e, -3) and A_gates(e) else None),
        ("ET15", "A = ET13 with +10% target (1d)",
         lambda e: morning(e, 10) if dipped(e, -3) and A_gates(e)
         else None),
        ("ET16", "A = ET13 with +15% target (1d)",
         lambda e: morning(e, 15) if dipped(e, -3) and A_gates(e)
         else None),
        ("ET17", "A = ET13 with +10% target, 2-day cap",
         lambda e: morning(e, 10, cap=2) if dipped(e, -3) and A_gates(e)
         else None),
        ("ET18", "A after-hours entry (pm, AH<=-3% vs close) + beat"
                 " + strong + fin -> next close",
         lambda e: afterhours(e) if e.get("ah_px")
         and (e["ah_px"] / e["pre_close"] - 1) * 100 <= -3
         and A_gates(e) else None),
        ("ET19", "A = ET18 with +10% target next day",
         lambda e: afterhours(e, 10) if e.get("ah_px")
         and (e["ah_px"] / e["pre_close"] - 1) * 100 <= -3
         and A_gates(e) else None),
        ("ET20", "A dip + beat + first-hour pressure>=+0.2: enter h2"
                 " open -> close",
         lambda e: ((e["close"] / e["h2_open"] - 1) * 100
                    if dipped(e, -3) and beat(e)
                    and e.get("p_h1") is not None and e["p_h1"] >= 0.2
                    and e.get("h2_open") else None)),
        ("ET21", "A deep dip<=-7% + beat + strong + fin, +10% tgt, 2d",
         lambda e: morning(e, 10, cap=2) if dipped(e, -7) and A_gates(e)
         else None),
        ("ET22", "B buy 7 sessions before -> sell last close pre-release",
         lambda e: runup(e, 7)),
        ("ET23", "B buy 5 before -> pre-release close",
         lambda e: runup(e, 5)),
        ("ET24", "B buy 3 before -> pre-release close",
         lambda e: runup(e, 3)),
        ("ET25", "B buy 2 before -> pre-release close",
         lambda e: runup(e, 2)),
        ("ET26", "B buy 1 before -> pre-release close",
         lambda e: runup(e, 1)),
        ("ET27", "B lag5, only if dipping (5d decline at entry)",
         lambda e: runup(e, 5) if e.get("dip5") else None),
        ("ET28", "B lag5 + strong + fin",
         lambda e: runup(e, 5) if e["strong"] and e["fin"] else None),
        ("ET29", "B lag2 + strong + fin + dipping",
         lambda e: runup(e, 2) if e["strong"] and e["fin"]
         and e.get("dip2") else None),
        ("ET30", "B lag5 + entry-day pressure >= 0",
         lambda e: runup(e, 5) if e.get("p5") is not None
         and e["p5"] >= 0 else None),
        ("ET31", "CONTROL: dip-buy morning on MISSES (surprise<0)",
         lambda e: morning(e) if dipped(e, -3)
         and e.get("surprise") is not None and e["surprise"] < 0
         else None),
    ]


def run(events):
    rows = []
    for xid, desc, fn in EXPERIMENTS():
        rets = []
        for e in events:
            try:
                r = fn(e)
            except Exception:
                r = None
            if r is not None:
                rets.append(r)
        n = len(rets)
        rows.append(dict(
            id=xid, desc=desc, n=n,
            win=round(100 * sum(1 for r in rets if r > 0) / n, 1)
            if n else None,
            avg=round(sum(rets) / n, 3) if n else None,
            tot=round(sum(BUDGET * r / 100 for r in rets)) if n else 0))
    return rows


def report(rows):
    print(f"\nEARNINGS-X2  [{WINDOW[0]}..{WINDOW[1]}]  $15k/event")
    print(f"{'id':<5} {'n':>5} {'win%':>5} {'avg%':>7} {'tot$':>10}  desc")
    for r in rows:
        hold = " HOLD>2" if r["id"] in ("ET22", "ET23") else ""
        print(f"{r['id']:<5} {r['n']:>5} {r['win'] or 0:>5} "
              f"{r['avg'] or 0:>7} {r['tot']:>10,}  {r['desc']}{hold}")
    (ROOT / "data/earnings_x2_results.json").write_text(
        json.dumps(rows, indent=1))


def main():
    syms = load_universe()
    ok, fin = screen_universe(syms)
    if EV_C.exists() and "--refetch" not in sys.argv:
        events = json.loads(EV_C.read_text())
    else:
        events = build_events(ok, fin)
    report(run(events))


if __name__ == "__main__":
    main()
