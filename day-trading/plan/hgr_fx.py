"""HALAL-GATE-REVIEW (2026-09-17) -- the REPORTING-CURRENCY bug, measured.

`halal_check` divides yfinance statement values by a market cap in USD.
yfinance publishes statements in the filer's OWN reporting currency
(`info["financialCurrency"]`), so every foreign private issuer that
reports in IDR / KRW / JPY / INR / CNY / ARS ... has its loan and cash
legs inflated by the FX rate and is hard-FAILed on a ratio that is not
a ratio. TLK (Telkom Indonesia) is cached at cash/mcap = 387,135% and
loan/mcap = 554,387%: those are rupiah over dollars.

This script MEASURES the class without changing anything:
  * reads every name the universe refuses on a ratio leg,
  * fetches `financialCurrency` for it,
  * converts the cached legs with the live <CUR>USD=X rate,
  * and reports how many would PASS the UNCHANGED 10/10/20 once the
    two sides of the ratio are in the same unit.

The haram leg is unaffected -- interest and revenue are both in the
filer's currency, so their ratio is already unit-free.

Usage: python plan/hgr_fx.py [--max-combined-floor 50] [--out FILE]
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
OUT = D / "hgr_fx.json"
FLOOR = 20.0
for i, a in enumerate(sys.argv):
    if a == "--floor":
        FLOOR = float(sys.argv[i + 1])
    if a == "--out":
        OUT = Path(sys.argv[i + 1])

UNI = json.loads((D / "halal_universe.json").read_text())
META = json.loads((D / "hgr_ticker_meta.json").read_text())
_FX: dict = {"USD": 1.0}


def fx(cur):
    """Local units per USD. yfinance quotes <CUR>USD=X as USD per unit."""
    if cur in _FX:
        return _FX[cur]
    rate = None
    for tk, inv in ((f"{cur}USD=X", False), (f"USD{cur}=X", True)):
        try:
            h = yf.Ticker(tk).history(period="5d")
            if h is not None and not h.empty:
                v = float(h["Close"].iloc[-1])
                if v > 0:
                    rate = (v if inv else 1.0 / v)
                    break
        except Exception:
            continue
    _FX[cur] = rate
    return rate


def one(sym):
    try:
        return sym, (yf.Ticker(sym).info or {}).get("financialCurrency")
    except Exception:
        return sym, None


def main():
    cands = [s for s, r in UNI.items()
             if (r.get("fail_reason") or "").startswith(
                 ("LOAN>10", "CASH>10", "COMBINED>20"))
             and (r.get("combined") or 0) >= FLOOR]
    print(f"{len(cands):,} ratio refusals with combined >= {FLOOR:g}%",
          flush=True)
    cur = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        for n, (s, c) in enumerate(ex.map(one, cands), 1):
            cur[s] = c
            if n % 200 == 0:
                print(f"  {n:,}/{len(cands):,}", flush=True)
    nonusd = {s: c for s, c in cur.items() if c and c != "USD"}
    print(f"non-USD reporting currency: {len(nonusd):,}")
    by = {}
    for s, c in nonusd.items():
        by[c] = by.get(c, 0) + 1
    print("  " + ", ".join(f"{k} {v}" for k, v in
                           sorted(by.items(), key=lambda x: -x[1])))
    would, rows = [], []
    for s, c in sorted(nonusd.items()):
        r = fx(c)
        if not r:
            continue
        u = UNI[s]
        lo = (u.get("loan_pct") or 0) / r
        ca = (u.get("cash_pct") or 0) / r
        cb = lo + ca
        hp = u.get("haram_pct")
        ok = lo <= 10 and ca <= 10 and cb <= 20 and (hp is not None and hp < 5)
        rows.append({"sym": s, "cur": c, "fx": r,
                     "loan_was": u.get("loan_pct"), "loan_now": round(lo, 2),
                     "cash_was": u.get("cash_pct"), "cash_now": round(ca, 2),
                     "comb_now": round(cb, 2), "haram": hp, "pass": ok,
                     "mcap": (META.get(s) or {}).get("market_cap")})
        if ok:
            would.append(s)
    print(f"\nWOULD PASS the UNCHANGED 10/10/20 once converted: "
          f"{len(would):,}")
    rows.sort(key=lambda x: -(x["mcap"] or 0))
    for x in rows[:40]:
        print(f"  {x['sym']:<6} {x['cur']:<4} fx {x['fx']:>10,.2f}  "
              f"loan {str(x['loan_was']):>12} -> {x['loan_now']:>8}  "
              f"cash {str(x['cash_was']):>12} -> {x['cash_now']:>8}  "
              f"haram {x['haram']}  {'ARMS' if x['pass'] else ''}")
    OUT.write_text(json.dumps({"floor": FLOOR, "currency": cur,
                               "rows": rows, "would_pass": would}, indent=1))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
