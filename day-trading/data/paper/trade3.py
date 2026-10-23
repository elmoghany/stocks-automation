"""PAPER-3BOOK 2026-10-23: append an entry trade row to today's ledger.
usage: python data/paper/trade3.py BOOK SYM DECISION_MIN BID ASK SHARES HALAL NOTE..."""
import json, sys
import datetime as _dt, zoneinfo as _z

now = _dt.datetime.now(_z.ZoneInfo("America/New_York"))
day = now.strftime("%Y-%m-%d")
book, sym, dec, bid, ask, sh, halal = sys.argv[1:8]
p = f"data/paper_days/{day}.3book.json"
d = json.load(open(p))
bid, ask, sh = float(bid), float(ask), int(sh)
row = {"book": book, "sym": sym, "decision_min": dec, "entry_time": now.strftime("%H:%M:%S"), "ask": ask, "bid": bid,
       "mid": round((bid + ask) / 2, 4), "shares": sh, "notional": round(sh * ask, 2), "halal": halal,
       "model_note": " ".join(sys.argv[8:])}
d["trades"].append(row)
json.dump(d, open(p, "w"), indent=1)
print("TRADE", row)
