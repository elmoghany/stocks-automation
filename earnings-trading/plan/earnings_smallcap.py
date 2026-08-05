"""EARNINGS-X3 Strategy 2 (ET50-ET53): extend the post-earnings
dip-buy to SMALL CAPS (S&P 600), $50k/event. Small caps dip deeper and
bounce harder after earnings; the question is whether that survives the
halal screen and the beat gate at this size.

  ET50 S&P600: beat + gap<=-3%, buy open, sell close (ET12 rules)
  ET51 S&P600: deeper dips only (gap<=-5%)
  ET52 COMBINED universe (S&P900 + S&P600): one $50k slot/day,
       deepest qualifying dip (the adopted slot rule)
  ET53 S&P600 + 5y-strong + profitable quarter
Universe: Wikipedia S&P 600 list. Halal cache:
data/earnings_halal_600.json; events: data/earnings_sc_events.json
(daily bars only -- no hourly needed). Window Aug 2025..Jul 2026.
Reaction-day convention: announcement hour (pm -> next session).
"""

import importlib.util
import json
import sys
import time
import urllib.request
import warnings
from collections import defaultdict
from io import StringIO
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
_spec = importlib.util.spec_from_file_location(
    "dt", ROOT.parent / "day-trading" / "day-trading.py")
dt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dt)

WINDOW = ("2025-08-01", "2026-07-31")
BUDGET = 50_000
U_C = ROOT / "data/universe_600.json"
HALAL_C = ROOT / "data/earnings_halal_600.json"
FIN_C = ROOT / "data/earnings_fin_600.json"
EV_C = ROOT / "data/earnings_sc_events.json"
BIG_EV = ROOT / "data/earnings_x2_events.json"


def universe600():
    if U_C.exists():
        return json.loads(U_C.read_text())
    req = urllib.request.Request(
        "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
        headers={"User-Agent": "Mozilla/5.0 (research script)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "replace")
    for tb in pd.read_html(StringIO(html)):
        if "Symbol" in tb.columns and len(tb) >= 400:
            syms = sorted({str(v).strip().replace(".", "-")
                           for v in tb["Symbol"].dropna()})
            U_C.write_text(json.dumps(syms))
            print(f"S&P600 universe: {len(syms)}")
            return syms
    raise RuntimeError("S&P600 table not found")


def screen(syms):
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
    print(f"halal: {len(ok)}/{len(syms)}", flush=True)
    return ok, fin


def build_events(syms, fin):
    lo, hi = WINDOW
    out = (json.loads(EV_C.read_text()) if EV_C.exists() else [])
    done = {e["sym"] for e in out}
    syms = [s for s in syms if s not in done]
    if done:
        print(f"  resuming: {len(done)} cached, {len(syms)} to go",
              flush=True)
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
        except Exception:
            continue
        closes, opens, highs, idx = h["Close"], h["Open"], h["High"], h.index
        stamps = {}
        for ts, row in ed.iterrows():
            d = ts.tz_localize(None)
            sp = row.get("Surprise(%)")
            stamps.setdefault(d.normalize(),
                              (d, None if pd.isna(sp) else float(sp)))
        for d, (ts, surprise) in sorted(stamps.items()):
            if ts.hour >= 15:
                pre_c, post_c = idx[idx <= d], idx[idx > d]
            elif ts.hour <= 9:
                pre_c, post_c = idx[idx < d], idx[idx >= d]
            else:
                continue
            if len(pre_c) == 0 or len(post_c) == 0:
                continue
            pre, post = pre_c[-1], post_c[0]
            if not (lo <= str(post.date()) <= hi):
                continue
            past = closes[closes.index <= pre]
            if float(past.iloc[-1]) <= 2:
                continue
            mom5 = ((past.iloc[-1] / past.iloc[-1250] - 1) * 100
                    if len(past) >= 1250 else None)
            sma200 = past.tail(200).mean() if len(past) >= 200 else None
            strong = (mom5 is not None and mom5 >= 100
                      and sma200 is not None and past.iloc[-1] > sma200)
            out.append(dict(
                sym=sym, date=str(post.date()), surprise=surprise,
                strong=bool(strong), fin=bool(fin.get(sym)),
                pre_close=round(float(closes[pre]), 4),
                open=round(float(opens[post]), 4),
                high=round(float(highs[post]), 4),
                close=round(float(closes[post]), 4)))
        if n % 25 == 0:
            print(f"  events {n}/{len(syms)} ({len(out)})", flush=True)
            EV_C.write_text(json.dumps(out))
        time.sleep(0.1)
    EV_C.write_text(json.dumps(out))
    print(f"saved {len(out)} events", flush=True)
    return out


def beat(e):
    return e.get("surprise") is not None and e["surprise"] > 0


def dip_pct(e):
    return (e["open"] / e["pre_close"] - 1) * 100


def ret(e):
    return (e["close"] / e["open"] - 1) * 100


def stat(label, rets):
    n = len(rets)
    if not n:
        print(f"{label}: n=0")
        return
    win = 100 * sum(1 for r in rets if r > 0) / n
    avg = sum(rets) / n
    tot = sum(BUDGET * r / 100 for r in rets)
    print(f"{label}  n={n:>4} win={win:5.1f}% avg={avg:+6.3f}% "
          f"tot=${tot:+,.0f}")


def main():
    syms = universe600()
    ok, fin = screen(syms)
    if EV_C.exists() and "--resume" not in sys.argv:
        ev = json.loads(EV_C.read_text())
    else:
        ev = build_events(ok, fin)
    q = [e for e in ev if beat(e) and dip_pct(e) <= -3]
    print(f"\nEARNINGS-X3 small caps  ${BUDGET:,}/event "
          f"[{WINDOW[0]}..{WINDOW[1]}]")
    stat("ET50 sc dip<=-3%+beat        ", [ret(e) for e in q])
    stat("ET51 sc dip<=-5%+beat        ",
         [ret(e) for e in q if dip_pct(e) <= -5])
    stat("ET53 sc + strong + fin       ",
         [ret(e) for e in q if e["strong"] and e["fin"]])
    big = json.loads(BIG_EV.read_text())
    allq = q + [e for e in big if beat(e) and dip_pct(e) <= -3]
    by_day = defaultdict(list)
    for e in allq:
        by_day[e["date"]].append(e)
    slot = [ret(min(v, key=dip_pct)) for v in by_day.values()]
    stat("ET52 combined 1-slot deepest ", slot)
    (ROOT / "data/earnings_sc_results.json").write_text(json.dumps(
        dict(ET50=[round(ret(e), 3) for e in q],
             ET52=[round(r, 3) for r in slot])))


if __name__ == "__main__":
    main()
