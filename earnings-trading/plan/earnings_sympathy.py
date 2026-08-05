"""EARNINGS-X3 Strategy 3 (ET60-ET62): sympathy trades, $50k/event.

When a halal name BEATS and gaps UP big, do its halal sector/industry
peers (which are NOT reporting that day) drift up the same session?
Play: buy the peer at the open of the trigger's reaction day, sell at
the close (same-day, fits all rules).

  ET60 trigger gap >= +5%: buy all same-SECTOR halal peers
  ET61 trigger gap >= +5%: buy all same-INDUSTRY halal peers (finer)
  ET62 trigger gap >= +8%: same-industry peers only
Universe: the 305-name halal S&P900 set (earnings_halal_big.json).
Caches: data/sector_map.json (yf info), data/daily_cache_big.json
(1y of daily open/close per name). Excludes peers that have their own
event that date. Window Aug 2025..Jul 2026.
"""

import json
import sys
import time
import warnings
from collections import defaultdict
from pathlib import Path

import yfinance as yf

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
BUDGET = 50_000
EV_C = ROOT / "data/earnings_x2_events.json"
SEC_C = ROOT / "data/sector_map.json"
PX_C = ROOT / "data/daily_cache_big.json"


def halal_names():
    h = json.loads((ROOT / "data/earnings_halal_big.json").read_text())
    return sorted(s for s, v in h.items() if v)


def sector_map(syms):
    m = json.loads(SEC_C.read_text()) if SEC_C.exists() else {}
    todo = [s for s in syms if s not in m]
    for n, sym in enumerate(todo):
        try:
            info = yf.Ticker(sym).info or {}
            m[sym] = [info.get("sector", ""), info.get("industry", "")]
        except Exception:
            m[sym] = ["", ""]
        if n % 25 == 0:
            print(f"  sectors {n}/{len(todo)}", flush=True)
            SEC_C.write_text(json.dumps(m))
        time.sleep(0.1)
    SEC_C.write_text(json.dumps(m))
    return m


def daily_cache(syms):
    m = json.loads(PX_C.read_text()) if PX_C.exists() else {}
    todo = [s for s in syms if s not in m]
    for n, sym in enumerate(todo):
        try:
            h = yf.Ticker(sym).history(period="15mo", auto_adjust=True)
            h.index = h.index.tz_localize(None)
            m[sym] = {str(d.date()): [round(float(o), 4),
                                      round(float(c), 4)]
                      for d, o, c in zip(h.index, h["Open"], h["Close"])}
        except Exception:
            m[sym] = {}
        if n % 25 == 0:
            print(f"  daily {n}/{len(todo)}", flush=True)
            PX_C.write_text(json.dumps(m))
        time.sleep(0.1)
    PX_C.write_text(json.dumps(m))
    return m


def main():
    syms = halal_names()
    events = json.loads(EV_C.read_text())
    sec = sector_map(syms)
    px = daily_cache(syms)
    reporting = defaultdict(set)
    for e in events:
        reporting[e["date"]].add(e["sym"])

    def peers_of(trigger, date, level):
        key = sec.get(trigger, ["", ""])[level]
        if not key:
            return []
        return [s for s in syms
                if s != trigger and sec.get(s, ["", ""])[level] == key
                and s not in reporting[date] and date in px.get(s, {})]

    def run(gap_min, level, label):
        rets = []
        used = set()
        for e in events:
            if e.get("surprise") is None or e["surprise"] <= 0:
                continue
            gap = (e["open"] / e["pre_close"] - 1) * 100
            if gap < gap_min:
                continue
            for s in peers_of(e["sym"], e["date"], level):
                k = (s, e["date"])
                if k in used:          # one position per peer-day
                    continue
                used.add(k)
                o, c = px[s][e["date"]]
                if o > 0:
                    rets.append((c / o - 1) * 100)
        n = len(rets)
        if not n:
            print(f"{label}: n=0")
            return
        win = 100 * sum(1 for r in rets if r > 0) / n
        avg = sum(rets) / n
        tot = sum(BUDGET * r / 100 for r in rets)
        print(f"{label}  n={n:>5} win={win:5.1f}% avg={avg:+6.3f}% "
              f"tot=${tot:+,.0f}")
        return rets

    print(f"\nEARNINGS-X3 sympathy  ${BUDGET:,}/event")
    r60 = run(5, 0, "ET60 sector peers, trig>=+5% ")
    r61 = run(5, 1, "ET61 industry peers, trig>=+5%")
    r62 = run(8, 1, "ET62 industry peers, trig>=+8%")
    (ROOT / "data/earnings_sympathy_results.json").write_text(json.dumps(
        dict(ET60=[round(x, 3) for x in (r60 or [])],
             ET61=[round(x, 3) for x in (r61 or [])],
             ET62=[round(x, 3) for x in (r62 or [])])))


if __name__ == "__main__":
    main()
