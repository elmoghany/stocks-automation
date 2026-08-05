"""EARNINGS-TRADING book (separate from the penny day-trading book).

User hypothesis (2026-08-05): trade the earnings REACTION on halal
large/mid caps -- e.g. SHOP +20% on results this morning, AMD's report
yesterday. Some names rise, some fall; halal rules out shorting, so the
two playable shapes are:
  - continuation: the stock GAPS UP on results -> buy at the post-news
    open, sell same day at the close (news is out; same-day, no ORB).
  - dip-buy: the stock GAPS DOWN on results -> buy the open, bet on an
    intraday bounce, sell at the close.
Overnight drift variants (hold to next close) are tested too but are
flagged OVERNIGHT -- outside the same-day rule, separate sign-off.

This is DIFFERENT from plan/earnings_probe.py (buy BEFORE the release,
hold through it) which was tested and REJECTED (baseline -0.02%/event).
Here we act AFTER the news, so there is no announcement risk -- the
question is whether the reaction continues or reverts intraday.

Experiment IDs: ET01..ET09 (permanent, registered in CONFIGS-TESTED.md).
Gates per event (all known at the post-news open):
  halal (day-trading.halal_check, cached -- NOTE: current fundamentals,
  a point-in-time approximation), gap size vs prior close, and for
  "strong" variants: 5y total return >= +100% and price > 200-day SMA
  computed point-in-time at the pre-earnings close.
Sizing: $15k notional per event (event study; no concurrency cap yet --
if a strategy passes, budget-capped replay comes next).
Window: last year only, Aug 2025..Jul 2026 (user directive 2026-08-05:
"backtest last year only for earnings").
Data: yfinance daily bars + get_earnings_dates (needs lxml).
Caches: data/earnings_halal.json, data/earnings_rx_events.json.
"""

import importlib.util
import json
import sys
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

UNIVERSE = """AAPL MSFT NVDA GOOGL AMZN META TSLA AVGO AMD QCOM TXN MU
ADBE CRM ORCL NOW INTU PANW CRWD FTNT ZS DDOG NET SNOW PLTR ANET SMCI
DELL HPQ CSCO IBM ACN LRCX AMAT KLAC ASML TSM ARM CDNS SNPS MRVL ON
NXPI ADI MCHP LLY UNH JNJ ABBV MRK PFE TMO ABT DHR ISRG SYK BSX MDT
REGN VRTX GILD AMGN BIIB MRNA ZTS DXCM EW HCA CI ELV CVS WMT COST PG
KO PEP MCD SBUX NKE LULU TJX HD LOW TGT DG DLTR ORLY AZO ROST YUM CMG
DPZ KHC GIS HSY CL KMB EL MNST CAT DE HON GE RTX LMT NOC GD BA UNP
CSX NSC UPS FDX EMR ETN PH ITW MMM ROK DOV XOM CVX COP EOG SLB PSX
VLO MPC OXY HES DVN FANG LIN APD SHW ECL FCX NEM NUE STLD VMC MLM
DIS NFLX CMCSA TMUS VZ T SPOT UBER ABNB BKNG MAR HLT RCL CCL DAL UAL
LUV AXP V MA PYPL SHOP""".split()

WINDOW = ("2025-08-01", "2026-07-31")   # last year only (user directive)
BUDGET = 15_000
HALAL_CACHE = ROOT / "data/earnings_halal.json"
EVENTS_CACHE = ROOT / "data/earnings_rx_events.json"


def halal_universe():
    cache = {}
    if HALAL_CACHE.exists():
        cache = json.loads(HALAL_CACHE.read_text())
    todo = [s for s in UNIVERSE if s not in cache]
    for n, sym in enumerate(todo):
        try:
            r = dt.halal_check(sym)
            cache[sym] = {"halal": bool(r["halal"]),
                          "fail": r.get("fail_reason", "")}
        except Exception as e:
            cache[sym] = {"halal": False, "fail": f"ERR {e}"}
        if n % 20 == 0:
            print(f"  halal {n}/{len(todo)}", flush=True)
            HALAL_CACHE.write_text(json.dumps(cache))
    HALAL_CACHE.write_text(json.dumps(cache))
    ok = [s for s in UNIVERSE if cache.get(s, {}).get("halal")]
    print(f"halal universe: {len(ok)}/{len(UNIVERSE)}", flush=True)
    return ok


def build_events(syms):
    """Per event: gap % (post open vs pre close), same-day open->close
    return, next-day close->close drift, and point-in-time strength.

    Reaction-day convention (FIXED 2026-08-05 -- the first version
    normalized the yfinance timestamp to midnight, which put pm
    reporters' "reaction" on the report day itself instead of the next
    session): using the announcement HOUR,
      pm (>=15h, after the close): pre = the report-day session,
          post = the NEXT session (that's where the reaction gap is);
      am (<=9h, before the open): pre = last session before the report
          date, post = the report-date session.
    Mid-day timestamps (ambiguous) are skipped."""
    out = {}
    for n, sym in enumerate(syms):
        try:
            t = yf.Ticker(sym)
            h = t.history(period="6y", auto_adjust=True)
            if len(h) < 500:
                continue
            h.index = h.index.tz_localize(None)
            ed = t.get_earnings_dates(limit=40)
            if ed is None or len(ed) == 0:
                continue
            stamps = {}
            for ts in ed.index:
                d = ts.tz_localize(None)
                stamps.setdefault(d.normalize(), d)
            closes, opens, idx = h["Close"], h["Open"], h.index
            evs = []
            for d, ts in sorted(stamps.items()):
                if ts.hour >= 15:              # pm: reaction is next day
                    pre_c = idx[idx <= d]
                    post_c = idx[idx > d]
                elif ts.hour <= 9:             # am: reaction is that day
                    pre_c = idx[idx < d]
                    post_c = idx[idx >= d]
                else:                          # ambiguous mid-day stamp
                    continue
                if len(pre_c) == 0 or len(post_c) == 0:
                    continue
                pre, post = pre_c[-1], post_c[0]
                after = idx[idx > post]
                gap = (opens[post] / closes[pre] - 1) * 100
                day = (closes[post] / opens[post] - 1) * 100
                d2 = ((closes[after[0]] / closes[post] - 1) * 100
                      if len(after) else None)
                past = closes[closes.index <= pre]
                mom5 = ((past.iloc[-1] / past.iloc[-1250] - 1) * 100
                        if len(past) >= 1250 else None)
                sma200 = past.tail(200).mean() if len(past) >= 200 else None
                strong = (mom5 is not None and mom5 >= 100
                          and sma200 is not None
                          and past.iloc[-1] > sma200)
                evs.append(dict(date=str(post.date()),
                                gap=round(gap, 2), day=round(day, 2),
                                d2=round(d2, 2) if d2 is not None else None,
                                strong=bool(strong)))
            if evs:
                out[sym] = evs
        except Exception as e:
            print(f"  {sym}: {e}", flush=True)
        if n % 20 == 0:
            print(f"  events {n}/{len(syms)}", flush=True)
    EVENTS_CACHE.write_text(json.dumps(out))
    print(f"saved {sum(len(v) for v in out.values())} events "
          f"across {len(out)} symbols", flush=True)
    return out


# (id, description, event filter, return field, overnight?)
STRATEGIES = [
    ("ET01", "gap >= +3%: buy post-news open, sell close",
     lambda e: e["gap"] >= 3, "day", False),
    ("ET02", "gap >= +5%: buy open, sell close",
     lambda e: e["gap"] >= 5, "day", False),
    ("ET03", "gap <= -3% dip-buy: buy open, sell close",
     lambda e: e["gap"] <= -3, "day", False),
    ("ET04", "gap <= -5% dip-buy: buy open, sell close",
     lambda e: e["gap"] <= -5, "day", False),
    ("ET05", "gap >= +3% AND 5y-strong: buy open, sell close",
     lambda e: e["gap"] >= 3 and e["strong"], "day", False),
    ("ET06", "gap <= -3% dip-buy AND 5y-strong",
     lambda e: e["gap"] <= -3 and e["strong"], "day", False),
    ("ET07", "|gap| < 3% (control -- no-surprise events)",
     lambda e: abs(e["gap"]) < 3, "day", False),
    ("ET08", "OVERNIGHT gap >= +3%: hold post day close -> next close",
     lambda e: e["gap"] >= 3, "d2", True),
    ("ET09", "OVERNIGHT gap <= -3% dip: post close -> next close",
     lambda e: e["gap"] <= -3, "d2", True),
]


def run(events):
    flat = [dict(sym=s, **e) for s, evs in events.items() for e in evs]
    lo, hi = WINDOW
    rows = []
    for xid, desc, filt, field, overnight in STRATEGIES:
        sel = [e for e in flat
               if lo <= e["date"] <= hi and filt(e)
               and e.get(field) is not None]
        rets = [e[field] for e in sel]
        n = len(rets)
        row = {"id": xid, "desc": desc, "overnight": overnight,
               "n": n,
               "win": round(100 * sum(1 for r in rets if r > 0) / n, 1)
               if n else None,
               "avg": round(sum(rets) / n, 3) if n else None,
               "tot": round(sum(BUDGET * r / 100 for r in rets)) if n else 0,
               "best": (max(sel, key=lambda e: e[field])["sym"]
                        if n else None),
               "worst": (min(sel, key=lambda e: e[field])["sym"]
                         if n else None)}
        row["pass"] = row["tot"] > 0 and not overnight
        rows.append(row)
    return rows


def report(rows):
    print(f"\nwindow {WINDOW[0]} .. {WINDOW[1]}, $15k/event")
    print(f"{'id':<5} {'n':>5} {'win%':>5} {'avg%':>7} {'tot$':>9}"
          f"  verdict  desc")
    for r in rows:
        v = ("PASS" if r["pass"] else
             "OVN" if r["overnight"] else "fail")
        print(f"{r['id']:<5} {r['n']:>5} {r['win'] or 0:>5} "
              f"{r['avg'] or 0:>7} {r['tot']:>9,}  {v:<7}  {r['desc']}")
    (ROOT / "data/earnings_trading_results.json").write_text(
        json.dumps(rows, indent=1))


def main():
    syms = halal_universe()
    if EVENTS_CACHE.exists() and "--refetch" not in sys.argv:
        events = json.loads(EVENTS_CACHE.read_text())
        events = {s: v for s, v in events.items() if s in syms}
    else:
        events = build_events(syms)
    report(run(events))


if __name__ == "__main__":
    main()
