"""HALAL-GATE-REVIEW (2026-09-17) -- benchmark against professional screens.

Read-only. Compares data/halal_universe.json against
  * Zoya + Musaffa public verdicts (2026-08-22 archive + today's refresh)
  * Shariah-ETF membership (HLAL SPUS SPTE SPRE UMMA; US funds only --
    SPWO/UMMA hold non-US listings whose local tickers collide, so
    global-fund membership only corroborates, per SOURCES.md)
and splits every "they pass / we refuse" into
  RATIO   -- we refuse only because 10 < leg <= 33 (their AAOIFI band):
             an INTENDED divergence, the user chose the stricter number
  DATA    -- we refuse for a missing row, no fundamentals, no market cap
  CLASS   -- industry keyword, SIC 6xxx, a user ruling: doctrine
  HARAM   -- the 5% interest leg

Usage: python plan/hgr_bench.py [--sanity]
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
UNI = json.loads((D / ("halal_universe.v2.json"
                      if "--before" in sys.argv
                      else "halal_universe.json")).read_text())
META = json.loads((D / "hgr_ticker_meta.json").read_text()) \
    if (D / "hgr_ticker_meta.json").exists() else {}


def _load(p):
    try:
        return json.loads((D / p).read_text())
    except Exception:
        return {}


SV_OLD = _load("halal_external/screener_verdicts.json")
SV_NEW = _load("halal_external/screener_verdicts.2026-09-17.json")
ETF = _load("halal_external/etf_holdings.json")

US_FUNDS = ("HLAL", "SPUS", "SPTE", "SPRE")      # US-listing funds only
ETF_MEMBERS = set()
for f in US_FUNDS:
    for h in ((ETF.get("funds") or {}).get(f) or {}).get("holdings") or []:
        t = (h.get("ticker") or "").strip().upper()
        if t and t.isalpha():
            ETF_MEMBERS.add(t)


def external(sym):
    """(zoya, musaffa) newest verdict available for `sym`."""
    z = (SV_NEW.get("zoya") or {}).get(sym) \
        or (SV_OLD.get("zoya") or {}).get(sym) or {}
    m = (SV_NEW.get("musaffa") or {}).get(sym) \
        or (SV_OLD.get("musaffa") or {}).get(sym) or {}
    return z.get("status"), m.get("status")


def they_pass(sym):
    z, m = external(sym)
    return (z == "Shariah-compliant") or (m == "halal") or \
        (sym in ETF_MEMBERS)


def they_refuse(sym):
    z, m = external(sym)
    return (z == "not Shariah-compliant") or (m == "not halal")


def our_cause(sym):
    r = UNI.get(sym)
    if r is None:
        return "not in universe", ""
    if r.get("halal"):
        return "PASS", ""
    fr = r.get("fail_reason") or ""
    if fr.startswith("HARAM INDUSTRY"):
        return "CLASS industry", fr[:60]
    if fr.startswith("FINANCIAL SECTOR"):
        return "CLASS sic-6xxx", fr[:60]
    if fr.startswith(("HARAM by user ruling", "HARAM by external")):
        return "CLASS ruling", fr[:60]
    if fr.startswith("FAIL (unverified revenue mix"):
        return "CLASS revenue-mix", fr[:60]
    if fr.startswith(("NO FUNDAMENTALS", "MARKET CAP")):
        return "DATA no-data", fr[:60]
    if fr.startswith("unverified"):
        return "DATA missing-row", fr[:60]
    if fr.startswith("HARAM>=5%"):
        return "HARAM 5%", fr[:60]
    if fr.startswith(("LOAN>10", "CASH>10", "COMBINED>20")):
        lo, ca = r.get("loan_pct"), r.get("cash_pct")
        band = (lo is not None and ca is not None
                and lo <= 33 and ca <= 33)
        return ("RATIO in 10-33 band" if band else "RATIO blown past 33"), \
            f"loan {lo} cash {ca} comb {r.get('combined')}"
    return "other", fr[:60]


SANITY = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMD", "TSLA", "ADBE", "CRM",
          "INTU", "ISRG", "LLY", "JNJ", "PG", "KO", "PEP", "COST", "NKE",
          "ORCL", "CSCO", "QCOM", "AVGO", "TXN", "AMAT", "LRCX", "KLAC",
          "ASML", "NFLX", "PFE", "MRK", "TMO", "ABT", "DHR", "UNH", "HD",
          "LOW", "WMT", "CAT", "DE", "HON", "LIN"]


def main():
    covered = sorted({s for s in UNI
                      if external(s) != (None, None) or s in ETF_MEMBERS})
    print(f"externally covered symbols in our universe: {len(covered):,} "
          f"(Zoya/Musaffa verdicts + {len(ETF_MEMBERS):,} US Shariah-ETF "
          f"holdings)")
    tp = [s for s in covered if they_pass(s)]
    print(f"  they PASS: {len(tp):,}")
    c = Counter(our_cause(s)[0] for s in tp)
    for k, v in c.most_common():
        print(f"    {v:>5,}  {k}")
    print("\n  -- WE REFUSE / THEY PASS, largest 40 by market cap --")
    def mc(s):
        return float((META.get(s) or {}).get("market_cap") or 0)
    rows = [s for s in tp if our_cause(s)[0] != "PASS"]
    for s in sorted(rows, key=lambda x: -mc(x))[:40]:
        cause, detail = our_cause(s)
        z, m = external(s)
        print(f"    {s:<6} {mc(s)/1e9:>9,.2f}bn  {cause:<20} "
              f"zoya={str(z):<22} mus={str(m):<10} {detail[:46]}")

    tr = [s for s in covered if they_refuse(s) and not they_pass(s)]
    ours_pass_theirs_not = [s for s in tr if our_cause(s)[0] == "PASS"]
    print(f"\n  they REFUSE: {len(tr):,}; of those WE PASS: "
          f"{len(ours_pass_theirs_not)}")
    for s in sorted(ours_pass_theirs_not, key=lambda x: -mc(x))[:40]:
        z, m = external(s)
        r = UNI[s]
        print(f"    {s:<6} {mc(s)/1e9:>9,.2f}bn loan {r.get('loan_pct')}"
              f" cash {r.get('cash_pct')} haram {r.get('haram_pct')}"
              f"  zoya={z} mus={m}")

    if "--sanity" in sys.argv:
        print("\n--- 40-NAME SANITY LIST ---")
        print(f"{'SYM':<6} {'ours':<6} {'zoya':<24} {'mus':<10} {'ETF':<4} "
              f"reason")
        for s in SANITY:
            r = UNI.get(s) or {}
            z, m = external(s)
            cause, _d = our_cause(s)
            print(f"{s:<6} {('PASS' if r.get('halal') else 'FAIL'):<6} "
                  f"{str(z):<24} {str(m):<10} "
                  f"{('yes' if s in ETF_MEMBERS else '-'):<4} "
                  f"{(r.get('fail_reason') or '')[:72]}")


if __name__ == "__main__":
    main()
