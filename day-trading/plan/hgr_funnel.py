"""HALAL-GATE-REVIEW (2026-09-17) -- the funnel, read-only.

Answers "why did 1,260 become 415" with counts at every step, and
separates a RULE from a DATA GAP at each one. Reads only caches:

    data/halal_universe.json        the verdicts (10,761)
    data/halal_list.pre-2026-09-16.json   the 1,260 pre-fix armable
    data/halal_flips_2026-09-16*.json     the two rebuild flip reports
    data/sic_codes.json             EDGAR SIC per symbol
    data/hgr_ticker_meta.json       Polygon type / market cap / SIC
    data/edgar/extracted/*.json     what the filer actually tagged
    data/halal_external/*           Zoya / Musaffa / Shariah ETFs

Nothing is written except the report tables on stdout (and, with
--json, data/hgr_funnel.json for the write-up).

Usage:  python plan/hgr_funnel.py [--json]
"""
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"


def load(p, default=None):
    try:
        return json.loads((D / p).read_text())
    except Exception:
        return default


UNI = load(("halal_universe.v2.json" if "--before" in sys.argv
            else "halal_universe.json"), {})
META = load("hgr_ticker_meta.json", {})
SIC = load("sic_codes.json", {})
PRE = (load("halal_list.pre-2026-09-16.json", {}) or {}).get("symbols", [])
FL1 = load("halal_flips_2026-09-16.json", {})
FL2 = load("halal_flips_2026-09-16.interest-leg.json", {})
EXT_DIR = D / "edgar/extracted"

EQUITY_TYPES = {"CS", "ADRC"}


def mcap(sym):
    v = (META.get(sym) or {}).get("market_cap")
    if v:
        return float(v)
    v = (UNI.get(sym) or {}).get("mcap")
    return float(v) if v else 0.0


def ptype(sym):
    return (META.get(sym) or {}).get("type") or "?"


def pname(sym):
    return ((META.get(sym) or {}).get("name") or "")[:34]


def sic_of(sym):
    r = SIC.get(sym) or {}
    s = str(r.get("sic") or "")
    return (s if s.isdigit() else ""), (r.get("desc") or "")


# ------------------------------------------------------------- staging
STEPS = [
    ("industry-keyword", ("HARAM INDUSTRY",), "RULE"),
    ("sic-6xxx", ("FINANCIAL SECTOR",), "RULE"),
    ("user/external ruling", ("HARAM by user ruling",
                              "HARAM by external-screener"), "RULE"),
    ("market-cap missing", ("MARKET CAP MISSING",), "DATA"),
    ("no fundamentals at all", ("NO FUNDAMENTALS DATA",), "DATA"),
    ("missing statement row", ("unverified: missing",), "DATA->RULE"),
    ("leg uncomputable", ("unverified: debt", "unverified: cash",
                          "unverified: combined",
                          "unverified: haram"), "DATA->RULE"),
    ("revenue-mix unverifiable", ("FAIL (unverified revenue mix",),
     "DATA->RULE"),
    ("ratio LOAN>10", ("LOAN>10",), "RULE"),
    ("ratio CASH>10", ("CASH>10",), "RULE"),
    ("ratio COMBINED>20", ("COMBINED>20",), "RULE"),
    ("haram >=5% TTM", ("HARAM>=5%",), "RULE"),
]


def step_of(rec):
    if rec.get("halal"):
        return "PASS"
    fr = (rec.get("fail_reason") or "")
    for name, keys, _kind in STEPS:
        if any(fr.startswith(k) for k in keys):
            return name
    if fr.startswith("ERROR"):
        return "gate error"
    return f"other: {fr[:40]}"


def main():
    out = {}
    syms = sorted(UNI)
    eq = [s for s in syms if ptype(s) in EQUITY_TYPES]
    print(f"UNIVERSE {len(syms):,} symbols "
          f"(clean ticker, close >= $2, grouped-daily tape)")
    tc = Counter(ptype(s) for s in syms)
    print("  by Polygon listing type:")
    for k, v in tc.most_common():
        print(f"    {k:<8} {v:>6,}")
    print(f"  COMMON EQUITY (CS+ADRC): {len(eq):,}   "
          f"NOT common equity: {len(syms)-len(eq):,}")
    out["type_counts"] = dict(tc)
    out["n_equity"] = len(eq)

    for label, pool in (("ALL SYMBOLS", syms), ("COMMON EQUITY ONLY", eq)):
        print(f"\n--- FUNNEL, {label} ({len(pool):,}) ---")
        c = Counter(step_of(UNI[s]) for s in pool)
        kind = {n: k for n, _x, k in STEPS}
        rows = []
        for name, _keys, k in STEPS:
            if c.get(name):
                rows.append((name, c[name], k))
        for name, n in c.items():
            if name not in kind and name != "PASS":
                rows.append((name, n, "?"))
        for name, n, k in rows:
            print(f"  {n:>6,}  {k:<10} {name}")
        print(f"  {c.get('PASS', 0):>6,}  ARMABLE")
        out[f"funnel_{'all' if pool is syms else 'equity'}"] = dict(c)

    # what a no-data name actually is
    nd = [s for s in syms if step_of(UNI[s]) == "no fundamentals at all"]
    print(f"\n--- THE {len(nd):,} 'NO FUNDAMENTALS DATA' NAMES ---")
    for k, v in Counter(ptype(s) for s in nd).most_common():
        print(f"    {k:<8} {v:>6,}")
    nd_eq = [s for s in nd if ptype(s) in EQUITY_TYPES]
    have_edgar = [s for s in nd_eq if (EXT_DIR / f"{s}.json").exists()]
    print(f"  common equity among them: {len(nd_eq):,}"
          f"  (with an EDGAR extract on disk: {len(have_edgar):,})")
    out["no_data_equity"] = len(nd_eq)

    # ---- the 1,260 -> 415 removals, by cause, largest names ----------
    pre = [s for s in PRE if s in UNI]
    now_fail = [s for s in pre if not UNI[s].get("halal")]
    print(f"\n--- THE PRE-FIX 1,260: {len(now_fail):,} NO LONGER ARMABLE ---")
    by = defaultdict(list)
    for f in (FL1.get("to_fail") or []):
        by[f["cause"]].append(f)
    for c, rows in sorted(by.items(), key=lambda x: -len(x[1])):
        print(f"  {len(rows):>4}  {c}")
    out["v1_causes"] = {c: len(r) for c, r in by.items()}

    for c in sorted(by, key=lambda x: -len(by[x])):
        rows = sorted(by[c], key=lambda r: -mcap(r["symbol"]))[:30]
        print(f"\n  == {c.upper()} -- 30 largest by market cap ==")
        print(f"  {'SYM':<6} {'mcap$bn':>9} {'type':<5} {'loan':>7}"
              f" {'cash':>7} {'comb':>7} {'haram':>7}  reason")
        for r in rows:
            n = r["now"]
            print(f"  {r['symbol']:<6} {mcap(r['symbol'])/1e9:>9,.2f} "
                  f"{ptype(r['symbol']):<5} "
                  f"{str(n.get('loan_pct')):>7} {str(n.get('cash_pct')):>7} "
                  f"{str(n.get('combined')):>7} {str(n.get('haram_pct')):>7}"
                  f"  {(r.get('reason') or '')[:58]}")

    # ---- strict-10: how many fail ONLY the cash leg, 10-20% ----------
    print("\n--- STRICT 10/10/20: WHICH LEG BINDS ---")
    only_cash = only_loan = both = 0
    cash_1020 = []
    for s, r in UNI.items():
        fr = r.get("fail_reason") or ""
        if not (fr.startswith("LOAN>10") or fr.startswith("CASH>10")):
            continue
        lo, ca, cb = r.get("loan_pct"), r.get("cash_pct"), r.get("combined")
        if None in (lo, ca, cb):
            continue
        lbad, cbad = lo > 10, ca > 10
        if lbad and cbad:
            both += 1
        elif cbad:
            only_cash += 1
            if ca <= 20 and cb <= 30 and (r.get("haram_pct") or 0) < 5:
                cash_1020.append((s, lo, ca, cb, r.get("haram_pct")))
        elif lbad:
            only_loan += 1
    print(f"  fails only the LOAN leg : {only_loan:,}")
    print(f"  fails only the CASH leg : {only_cash:,}")
    print(f"  fails both              : {both:,}")
    print(f"  cash 10-20%, loan<=10, haram<5 (AAOIFI would pass at 33): "
          f"{len(cash_1020):,}")
    for s, lo, ca, cb, hp in sorted(cash_1020,
                                    key=lambda x: -mcap(x[0]))[:25]:
        print(f"    {s:<6} {mcap(s)/1e9:>8,.2f}bn loan {lo:>6} cash {ca:>6}"
              f" comb {cb:>6} haram {hp}")
    out["strict10"] = {"only_loan": only_loan, "only_cash": only_cash,
                       "both": both, "cash_10_20": len(cash_1020)}

    # ---- AAOIFI 33/33/5 counterfactual on the SAME cached numbers ----
    print("\n--- COUNTERFACTUALS ON THE CACHED RATIOS ---")
    def count_under(loan_cap, cash_cap, comb_cap):
        n = 0
        for s, r in UNI.items():
            fr = r.get("fail_reason") or ""
            if r.get("halal"):
                n += 1
                continue
            # only names that REACHED the ratio legs can flip
            if not fr.startswith(("LOAN>10", "CASH>10", "COMBINED>20")):
                continue
            lo, ca, cb = r.get("loan_pct"), r.get("cash_pct"), \
                r.get("combined")
            hp = r.get("haram_pct")
            if None in (lo, ca, cb) or hp is None:
                continue
            if lo <= loan_cap and ca <= cash_cap and cb <= comb_cap \
                    and hp < 5:
                n += 1
        return n
    for lab, a, b, cc in (("user 10/10/20", 10, 10, 20),
                          ("10/10/no-combined", 10, 10, 1e9),
                          ("20/20/40", 20, 20, 40),
                          ("AAOIFI 33/33/-", 33, 33, 1e9),
                          ("33/33/66", 33, 33, 66)):
        print(f"  {lab:<20} -> {count_under(a, b, cc):,} armable "
              f"(ratio legs only; every other screen unchanged)")
        out.setdefault("counterfactual", {})[lab] = count_under(a, b, cc)

    if "--json" in sys.argv:
        (D / "hgr_funnel.json").write_text(json.dumps(out, indent=1))
        print("\nwrote data/hgr_funnel.json")


if __name__ == "__main__":
    main()
