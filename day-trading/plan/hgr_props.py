"""HALAL-GATE-REVIEW (2026-09-17) -- price each PROPOSED change.

Read-only. For every change the review proposes, prints the armable
count it would produce, so the user is choosing between numbers rather
than between adjectives. Runs against the CURRENT
data/halal_universe.json (pass --before to price them against the
2026-09-16 415-name state instead).

Usage: python plan/hgr_props.py [--before]
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
UNI = json.loads((D / ("halal_universe.v2.json" if "--before" in sys.argv
                       else "halal_universe.json")).read_text())
META = json.loads((D / "hgr_ticker_meta.json").read_text())
SIC = json.loads((D / "sic_codes.json").read_text())
EQ = {"CS", "ADRC"}


def typ(s):
    return (META.get(s) or {}).get("type") or "?"


def mc(s):
    return float((META.get(s) or {}).get("market_cap") or 0)


base = sorted(s for s, r in UNI.items() if r.get("halal"))
print(f"BASE armable: {len(base):,}")
print(f"  by listing type: {Counter(typ(s) for s in base).most_common()}")

# ---- P1: common equity only -----------------------------------------
non = [s for s in base if typ(s) not in EQ]
print(f"\nP1  universe = common equity only (Polygon type CS/ADRC)")
print(f"    removes {len(non)} armable non-equities: "
      + ", ".join(f"{s} ({typ(s)}, {(META.get(s) or {}).get('name','')[:28]})"
                  for s in non))
print(f"    armable {len(base):,} -> {len(base)-len(non):,}; the SCREEN "
      f"shrinks from 10,761 to 4,590 symbols")

# ---- P2: the threshold ladder ---------------------------------------
print("\nP2  ratio thresholds (ratio legs only, every other screen "
      "unchanged)")


def ladder(lc, cc, cb_cap):
    n = 0
    for s, r in UNI.items():
        fr = r.get("fail_reason") or ""
        if r.get("halal"):
            n += 1
            continue
        if not fr.startswith(("LOAN>10", "CASH>10", "COMBINED>20")):
            continue
        lo, ca, cb, hp = (r.get("loan_pct"), r.get("cash_pct"),
                          r.get("combined"), r.get("haram_pct"))
        if None in (lo, ca, cb) or hp is None:
            continue
        if lo <= lc and ca <= cc and cb <= cb_cap and hp < 5:
            n += 1
    return n


for lab, a, b, c in (("10/10/20  (today)", 10, 10, 20),
                     ("12/12/24", 12, 12, 24),
                     ("15/15/30", 15, 15, 30),
                     ("20/20/40", 20, 20, 40),
                     ("25/25/50", 25, 25, 50),
                     ("33/33/66  (AAOIFI)", 33, 33, 66)):
    print(f"    {lab:<20} -> {ladder(a, b, c):,}")

# ---- P3: an absent DEBT line on a complete balance sheet reads 0 -----
print("\nP3  an absent DEBT line on an otherwise-complete filed balance "
      "sheet reads as ZERO")
cand = []
for s, r in UNI.items():
    fr = r.get("fail_reason") or ""
    if not fr.startswith("unverified: missing"):
        continue
    miss = fr.split(" -- ")[0].replace("unverified: missing ", "")
    if set(x.strip() for x in miss.split(",")) != {"debt"}:
        continue
    ca, hp = r.get("cash_pct"), r.get("haram_pct")
    if ca is None or hp is None:
        continue
    if ca <= 10 and hp < 5:            # loan would be 0 -> combined = cash
        cand.append((s, ca, hp))
cand.sort(key=lambda x: -mc(x[0]))
print(f"    would restore {len(cand)} names "
      f"(cash leg and 5% leg already clear; loan would be 0)")
for s, ca, hp in cand[:25]:
    print(f"      {s:<6} {mc(s)/1e9:>9,.2f}bn cash {ca:>6} haram {hp}")
print(f"    armable {len(base):,} -> {len(base)+len(cand):,}")

# ---- P4: SIC 6xxx false positives ------------------------------------
print("\nP4  SIC 6xxx false positives restorable by an explicit PASS "
      "ruling with a basis")
FALSE_POS = ["IDCC", "RGLD", "TFPM", "TPL", "USIO", "TRNO", "CHCI", "VMET",
             "RMCO", "AGNT"]
n4 = 0
for s in FALSE_POS:
    r = UNI.get(s)
    if not r:
        continue
    lo, ca, cb, hp = (r.get("loan_pct"), r.get("cash_pct"),
                      r.get("combined"), r.get("haram_pct"))
    ok = (lo is not None and ca is not None and cb is not None
          and hp is not None and lo <= 10 and ca <= 10 and cb <= 20
          and hp < 5)
    n4 += bool(ok)
    print(f"      {s:<6} {mc(s)/1e9:>9,.2f}bn SIC "
          f"{(SIC.get(s) or {}).get('sic','')} "
          f"{((SIC.get(s) or {}).get('desc') or '')[:30]:<30} "
          f"loan {lo} cash {ca} comb {cb} haram {hp} -> "
          f"{'WOULD ARM' if ok else 'still fails a ratio leg'}")
print(f"    armable {len(base):,} -> {len(base)+n4:,}")

# ---- P5: revenue-mix keyword -> review queue -------------------------
rm = [s for s, r in UNI.items()
      if (r.get("fail_reason") or "").startswith("FAIL (unverified revenue")]
rm_ok = []
for s in rm:
    r = UNI[s]
    lo, ca, cb, hp = (r.get("loan_pct"), r.get("cash_pct"),
                      r.get("combined"), r.get("haram_pct"))
    if None in (lo, ca, cb) or hp is None:
        continue
    if lo <= 10 and ca <= 10 and cb <= 20 and hp < 5:
        rm_ok.append(s)
print(f"\nP5  revenue-mix keyword ({len(rm)} names) -> review queue "
      f"instead of automatic FAIL")
print(f"    {len(rm_ok)} of them already clear every ratio leg, so a "
      f"cleared revenue mix would arm them")
print(f"    armable {len(base):,} -> up to {len(base)+len(rm_ok):,} "
      f"(each needs a segment-revenue reading or an external verdict)")
kw = Counter()
for s in rm_ok:
    fr = UNI[s]["fail_reason"]
    kw[fr.split("revenue mix: ")[1].split(")")[0]] += 1
print(f"    by trigger: {kw.most_common(12)}")

# ---- P6: ADR market-cap artifacts ------------------------------------
print("\nP6  market-cap denominator artifacts (ADR cap vs whole company)")
bad = []
for s, r in UNI.items():
    ca = r.get("cash_pct")
    if ca is not None and ca > 60:
        bad.append((s, ca, typ(s)))
bad.sort(key=lambda x: -x[1])
print(f"    {len(bad)} names show cash > 60% of market cap "
      f"({sum(1 for _s, _c, t in bad if t == 'ADRC')} of them ADRs)")
for s, ca, t in bad[:15]:
    print(f"      {s:<6} {t:<5} cash {ca:>8}%  loan "
          f"{UNI[s].get('loan_pct')}")
