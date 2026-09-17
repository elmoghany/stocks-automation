"""HALAL-GATE-REVIEW (2026-09-17) -- write Class-B rulings for names no
filed statement can answer.

USER RULING 2026-09-17, rung 2: "...or check the Zoya website. Do not
just reject it." A name that survives the last-available ladder still
refused (`unverified: missing <field>`) is looked up on Zoya and
Musaffa and adopted under the STANDING Class-B exception
(2026-08-22: "the only exception for my halal rules: the stocks that
are not verifiable because we could not find its finances. then for
these use zoya and etc.").

FOUR GUARDS, all stricter than the bare Class-B rule, because a Class-B
PASS bypasses our ratio legs entirely (`_b_ruling_or` returns PASS with
loan/cash/haram = None) and the user's 10/10/20 is 3x stricter than the
AAOIFI thresholds those screeners use:

  1. COMMON EQUITY ONLY (Polygon type CS/ADRC). A closed-end bond fund
     is not "a company whose finances we could not find"; it is a
     vehicle whose income IS interest, and it stays refused.
  2. AT LEAST ONE AFFIRMATION and NO CONFLICT -- Zoya "Shariah-
     compliant" or Musaffa "halal", and the other source must not say
     not-compliant/not-halal. questionable/doubtful never affirm and,
     on their own, never refuse.
  3. EVERY LEG WE *CAN* COMPUTE MUST STILL PASS the user's own
     10/10/20 and the 5% test. External evidence is admitted only for
     the leg that is genuinely missing -- it never launders a leg our
     own data already failed. (This is stricter than SOURCES.md's
     Class-B text, deliberately, and is flagged as a doctrinal question
     in halal-gate-review.md.)
  4. NEVER OVERWRITE an existing ruling, and never write a FAIL: a bare
     external non-compliant leaves the default FAIL standing
     (SOURCES.md rule 2), and a FAIL ruling is final on every path.

Usage: python plan/hgr_rulings.py [--write]     (dry-run without --write)
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
RUL = D / "halal_rulings.json"
UNI = json.loads((D / "halal_universe.json").read_text())
META = json.loads((D / "hgr_ticker_meta.json").read_text())


def _load(p):
    try:
        return json.loads((D / p).read_text())
    except Exception:
        return {}


SV_NEW = _load("halal_external/screener_verdicts.2026-09-17.json")
SV_OLD = _load("halal_external/screener_verdicts.json")


def ext(sym):
    z = (SV_NEW.get("zoya") or {}).get(sym) or \
        (SV_OLD.get("zoya") or {}).get(sym) or {}
    m = (SV_NEW.get("musaffa") or {}).get(sym) or \
        (SV_OLD.get("musaffa") or {}).get(sym) or {}
    return z, m


def main():
    rul = json.loads(RUL.read_text())
    made, skipped = [], []
    for sym, r in sorted(UNI.items()):
        fr = r.get("fail_reason") or ""
        if not fr.startswith("unverified"):
            continue
        if (META.get(sym) or {}).get("type") not in ("CS", "ADRC"):
            skipped.append((sym, "not common equity"))
            continue
        if sym in rul:
            skipped.append((sym, "already ruled"))
            continue
        z, m = ext(sym)
        zs, ms = z.get("status"), m.get("status")
        affirm = (zs == "Shariah-compliant") or (ms == "halal")
        conflict = (zs == "not Shariah-compliant") or (ms == "not halal")
        if not affirm:
            skipped.append((sym, f"no affirmation (zoya={zs} mus={ms})"))
            continue
        if conflict:
            skipped.append((sym, f"conflict (zoya={zs} mus={ms})"))
            continue
        lo, ca, cb = r.get("loan_pct"), r.get("cash_pct"), r.get("combined")
        hp = r.get("haram_pct")
        bad = []
        if lo is not None and lo > 10:
            bad.append(f"loan {lo}")
        if ca is not None and ca > 10:
            bad.append(f"cash {ca}")
        if cb is not None and cb > 20:
            bad.append(f"combined {cb}")
        if hp is not None and hp >= 5:
            bad.append(f"haram {hp}")
        if bad:
            skipped.append((sym, "our own computable legs fail: "
                                 + ", ".join(bad)))
            continue
        miss = fr.split(" -- ")[0].replace("unverified: missing ", "")
        src = []
        if zs:
            src.append(f"Zoya {z.get('fetched', '?')}: {zs}")
        if ms:
            src.append(f"Musaffa {m.get('asof') or m.get('fetched', '?')}"
                       f": {ms}")
        rul[sym] = {
            "verdict": "PASS",
            "date": time.strftime("%Y-%m-%d"),
            "class": "B-no-financials",
            "basis": (f"last-available statement absent ({miss}) after the "
                      f"2026-09-17 ladder (yfinance quarterly -> annual -> "
                      f"EDGAR companyfacts, <=15 months); {'; '.join(src)}. "
                      f"Adopted whole under the user's 2026-08-22 Class-B "
                      f"exception, per the 2026-09-17 ruling. Legs we CAN "
                      f"compute all clear the house 10/10/20: loan {lo}, "
                      f"cash {ca}, combined {cb}, haram {hp}."),
            "haram_share_est": None,
        }
        made.append((sym, zs, ms, lo, ca, cb, hp))
    print(f"WOULD WRITE {len(made)} Class-B PASS rulings")
    def mc(s):
        return float((META.get(s) or {}).get("market_cap") or 0)
    for s, zs, ms, lo, ca, cb, hp in sorted(made, key=lambda x: -mc(x[0])):
        print(f"  {s:<6} {mc(s)/1e9:>9,.2f}bn zoya={str(zs):<22} "
              f"mus={str(ms):<10} loan {lo} cash {ca} comb {cb} haram {hp}")
    from collections import Counter
    print("\nSKIPPED:", Counter(k.split(" (")[0].split(":")[0]
                                for _s, k in skipped).most_common())
    if "--write" in sys.argv:
        RUL.write_text(json.dumps(rul, indent=1))
        print(f"\nwrote {len(made)} rulings -> {RUL.name} "
              f"({len([k for k in rul if not k.startswith('_')])} total)")


if __name__ == "__main__":
    main()
