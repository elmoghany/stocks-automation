"""HALAL GATE AUDIT (2026-09-16) -- independent recompute from EDGAR.

User question: "is halal stocks correct or tickers calc correctly?"

This script does NOT import day-trading.py::halal_check and does NOT
reuse plan/edgar_backfill.py's extractor. It re-derives the four inputs
(debt, cash, interest income, revenue), the share count and the market
cap straight out of data/edgar/companyfacts.zip + data/massive/gd, runs
the user's 10/10/20 + 5% arithmetic itself, and DIFFs the result against
the cached verdict in data/halal_universe.json. A second implementation
is the only way to catch a tag-choice or None-handling bug in the first
one: re-running the same code would agree with itself by construction.

Read-only on every engine file. Output: JSON to stdout / --out.

Usage:
  python plan/halal_audit.py --sample            # seeded 25 PASS + 25 FAIL
  python plan/halal_audit.py --syms QCOM,DELL    # explicit
  python plan/halal_audit.py --zero-ratio        # the loan==cash==0 class
"""

import argparse
import gzip
import json
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZIPF = ROOT / "data/edgar/companyfacts.zip"
TICKF = ROOT / "data/edgar/company_tickers.json"
GD = ROOT / "data/massive/gd"
UNI_F = ROOT / "data/halal_universe.json"
LIST_F = ROOT / "data/halal_list.json"
RH_F = ROOT / "data/rh_fundamentals.json"

# Snapshot date of the cached universe (halal_list.json `updated`). The
# cached verdicts were computed with a market cap as of that day, so the
# apples-to-apples diff uses the same day's close.
ASOF = "2026-09-01"
FORMS = {"10-Q", "10-K", "10-Q/A", "10-K/A",
         # foreign private issuers file these instead; 11 of the 68
         # sampled names (CCJ, GGB, MGA, NICE, HBM, ...) have NO 10-Q at
         # all, so a US-forms-only reader reports CANNOT-VERIFY on names
         # the live gate happily screened off yfinance data.
         "20-F", "40-F", "6-K", "20-F/A", "40-F/A"}

# ---- tag map, written from the user's spec, deliberately INDEPENDENT --
# Interest-bearing debt. Component tags (summed) first; if no component
# is tagged at a period end, fall back to the total tags (max, so two
# overlapping totals never double-count).
DEBT_PARTS = [
    "LongTermDebtNoncurrent", "LongTermDebtCurrent", "ShortTermBorrowings",
    "NotesPayableCurrent", "NotesPayableNoncurrent", "LongTermNotesPayable",
    "ConvertibleNotesPayableCurrent", "ConvertibleNotesPayableNoncurrent",
    "ConvertibleDebtCurrent", "ConvertibleDebtNoncurrent",
    "LinesOfCreditCurrent", "LineOfCredit", "CommercialPaper",
    "LoansPayableCurrent", "LoansPayableNoncurrent",
    "SecuredDebtCurrent", "SecuredDebt", "UnsecuredDebt",
    "FinanceLeaseLiabilityCurrent", "FinanceLeaseLiabilityNoncurrent",
]
DEBT_TOTALS = [
    "DebtLongtermAndShorttermCombinedAmount", "LongTermDebt", "DebtCurrent",
    "NotesPayable", "ConvertibleDebt", "LoansPayable", "ShortTermDebt",
]
# Operating leases are NOT included: they are not interest-bearing
# borrowings under AAOIFI/most screens. Recorded here so the choice is
# explicit rather than accidental.
OPLEASE = ["OperatingLeaseLiabilityCurrent",
           "OperatingLeaseLiabilityNoncurrent"]

CASH_MAIN = [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    "CashAndDueFromBanks",
]
CASH_STI = [
    "ShortTermInvestments", "MarketableSecuritiesCurrent",
    "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    "AvailableForSaleSecuritiesCurrent", "AvailableForSaleSecurities",
    "HeldToMaturitySecuritiesCurrent", "TradingSecuritiesCurrent",
    "OtherShortTermInvestments",
]
REV_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
    "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
    "SalesRevenueGoodsNet", "SalesRevenueServicesNet",
    "RevenuesNetOfInterestExpense", "RegulatedAndUnregulatedOperatingRevenue",
]
INT_TAGS = [
    "InvestmentIncomeInterest", "InterestAndDividendIncomeOperating",
    "InvestmentIncomeInterestAndDividend", "InterestIncomeOther",
    "InterestAndOtherIncome", "InterestIncomeExpenseNet",
    "InterestIncomeExpenseAfterProvisionForLoanLoss", "InvestmentIncomeNet",
]


def cik_map():
    out = {}
    for e in json.loads(TICKF.read_text()).values():
        t = e["ticker"].upper()
        for k in {t, t.replace(".", "-"), t.replace("-", ".")}:
            out.setdefault(k, e["cik_str"])
    return out


def _units(facts, tag):
    """All USD facts for a us-gaap tag, 10-Q/10-K only."""
    d = ((facts.get("us-gaap") or {}).get(tag) or {}).get("units", {})
    return [e for e in d.get("USD", []) if e.get("form") in FORMS]


def instants(facts, tag):
    """{period_end: (value, filed)} for balance-sheet (instant) facts.
    Latest FILED wins for a given period end -- an amended filing
    supersedes the original."""
    out = {}
    for e in _units(facts, tag):
        if e.get("start") or e.get("val") is None:
            continue                      # duration fact, not an instant
        end, filed = e["end"], e.get("filed") or ""
        if end not in out or filed > out[end][1]:
            out[end] = (float(e["val"]), filed)
    return out


def durations(facts, tag, lo=60, hi=100):
    """{period_end: (value, filed, days)} for flow facts whose period is
    quarter-length. `lo/hi` widen to capture 13-week retail quarters."""
    from datetime import date
    out = {}
    for e in _units(facts, tag):
        if not e.get("start") or e.get("val") is None:
            continue
        try:
            d = (date.fromisoformat(e["end"])
                 - date.fromisoformat(e["start"])).days
        except ValueError:
            continue
        if not lo <= d <= hi:
            continue
        end, filed = e["end"], e.get("filed") or ""
        if end not in out or filed > out[end][1]:
            out[end] = (float(e["val"]), filed, d)
    return out


def annuals(facts, tags, lo=330, hi=400):
    """Annual (FY) flow facts, used when a filer tags no quarterly
    revenue at all (foreign/annual-only reporters)."""
    best = {}
    for tag in tags:
        for e in _units(facts, tag):
            if not e.get("start") or e.get("val") is None:
                continue
            from datetime import date
            try:
                d = (date.fromisoformat(e["end"])
                     - date.fromisoformat(e["start"])).days
            except ValueError:
                continue
            if lo <= d <= hi and e["end"] not in best:
                best[e["end"]] = (float(e["val"]), e.get("filed") or "")
    return best


def debt_at(facts, end):
    """(value, which_tags, tier) -- MAX(sum of components, best total).

    BUG THIS AVOIDS (the finding of this audit; see edgar_backfill.py
    _debt_at, which does NOT do this): a strict tier PRECEDENCE rule --
    "if any tier-1 component is tagged, never look at the tier-2
    totals" -- silently drops the main borrowing whenever a filer tags
    the current portion under a component tag but the noncurrent balance
    under an aggregate tag. QCOM 2026-06-28 tags LongTermDebtCurrent
    1,991M + CommercialPaper 498M (tier 1) and LongTermDebt 12,781M
    (tier 2): precedence returns 2,489M, 6.1x under the true 15,270M.
    MAX is the safe reconciliation -- a total never double-counts its
    own components, and over-counting debt only ever REFUSES more."""
    parts, used = 0.0, []
    for t in DEBT_PARTS:
        v = instants(facts, t).get(end)
        if v:
            parts += v[0]
            used.append(t)
    tot, tt = 0.0, []
    for t in DEBT_TOTALS:
        v = instants(facts, t).get(end)
        if v and v[0] > tot:
            tot, tt = v[0], [t]
    if not used and not tt:
        return None, [], "none"    # NOT 0 -- absence is not zero here
    if tot > parts:
        return tot, tt, f"total(parts={parts:.0f})"
    return parts, used, f"parts(total={tot:.0f})"


def cash_at(facts, end):
    main, mt = None, None
    for t in CASH_MAIN:
        v = instants(facts, t).get(end)
        if v is not None:
            main, mt = v[0], t
            break
    sti, st = 0.0, []
    for t in CASH_STI:             # MAX: totals vs components overlap
        v = instants(facts, t).get(end)
        if v and v[0] > sti:
            sti, st = v[0], [t]
    if main is None:
        return (None, [], 0.0) if not st else (sti, st, sti)
    return main + sti, ([mt] + st), sti


def flow_at(facts, tags, end):
    for t in tags:
        v = durations(facts, t).get(end)
        if v is not None:
            return v[0], t, v[2]
    return None, None, None


def latest_quarter(facts, asof):
    """The most recent period end whose 10-Q/10-K was FILED on or before
    `asof` and that carries a balance sheet (a cash anchor)."""
    anchors = {}
    for t in CASH_MAIN:
        for end, (v, filed) in instants(facts, t).items():
            if filed and filed <= asof:
                if end not in anchors or filed < anchors[end]:
                    anchors[end] = filed
    if not anchors:
        return None, None
    end = max(anchors)
    return end, anchors[end]


def shares_latest(facts, asof):
    best = None
    for e in ((facts.get("dei") or {})
              .get("EntityCommonStockSharesOutstanding") or {}) \
            .get("units", {}).get("shares", []):
        if e.get("val") is None or not e.get("end"):
            continue
        if (e.get("filed") or "") > asof:
            continue
        if best is None or e["end"] > best[0]:
            best = (e["end"], float(e["val"]), e.get("filed") or "")
    return best


_GD_CACHE = {}


def closes(date):
    if date in _GD_CACHE:
        return _GD_CACHE[date]
    f = GD / f"{date}.json.gz"
    if not f.exists():
        _GD_CACHE[date] = {}
        return {}
    with gzip.open(f, "rt", encoding="utf-8") as fh:
        rows = json.load(fh)
    m = {r["T"]: r.get("c") for r in rows if r.get("T")}
    _GD_CACHE[date] = m
    return m


_GD_DATES = None


def close_near(sym, date, back=12):
    """Last close for `sym` on or before `date` (walks back over
    weekends/holidays and thin days)."""
    global _GD_DATES
    if _GD_DATES is None:
        _GD_DATES = sorted(p.name[:-8] for p in GD.glob("*.json.gz"))
    cand = [d for d in _GD_DATES if d <= date][-back:]
    for d in reversed(cand):
        c = closes(d).get(sym)
        if c:
            return float(c), d
    return None, None


def recompute(sym, facts, asof=ASOF):
    """Independent verdict for `sym`. Every leg reports whether it was
    OBSERVED or MISSING -- a missing leg is never silently 0."""
    out = {"symbol": sym, "asof": asof, "notes": []}
    end, filed = latest_quarter(facts, asof)
    if end is None:
        out["status"] = "NO-EDGAR-QUARTER"
        return out
    out["period_end"], out["filed"] = end, filed

    d, dtags, dtier = debt_at(facts, end)
    c, ctags, sti = cash_at(facts, end)
    rev, rtag, rdays = flow_at(facts, REV_TAGS, end)
    inti, itag, _ = flow_at(facts, INT_TAGS, end)
    oplease = sum((instants(facts, t).get(end) or (0, ""))[0] for t in OPLEASE)

    out["debt"] = d
    out["debt_tags"] = dtags
    out["debt_tier"] = dtier
    out["cash"] = c
    out["cash_tags"] = ctags
    out["sti"] = sti
    out["rev_q"] = rev
    out["rev_tag"] = rtag
    out["rev_days"] = rdays
    out["intinc_q"] = inti
    out["intinc_tag"] = itag
    out["oplease_excluded"] = oplease

    if rev is None:                 # half-year filer (foreign 6-K/20-F)
        for t in REV_TAGS:
            v = durations(facts, t, lo=150, hi=200).get(end)
            if v is not None:
                out["rev_halfyear"] = v[0]
                out["rev_tag"] = t
                out["notes"].append("revenue: HALF-YEAR period -- the "
                                    "live gate annualizes any quarterly "
                                    "row x4, which double-counts these")
                break
    if rev is None and out.get("rev_halfyear") is None:   # annual-only
        ann = annuals(facts, REV_TAGS)
        usable = {e: v for e, v in ann.items() if v[1] and v[1] <= asof}
        if usable:
            e2 = max(usable)
            out["rev_annual"] = usable[e2][0]
            out["rev_annual_end"] = e2
            out["notes"].append("revenue: annual only (no quarterly tag)")

    sh = shares_latest(facts, asof)
    out["shares"] = sh[1] if sh else None
    out["shares_asof"] = sh[0] if sh else None
    px, pxd = close_near(sym, asof)
    out["close"] = px
    out["close_date"] = pxd
    pxf, pxfd = close_near(sym, filed) if filed else (None, None)
    out["close_at_filing"] = pxf

    mcap = (sh[1] * px) if (sh and px) else None
    out["mcap_edgar"] = mcap
    out["mcap_at_filing"] = (sh[1] * pxf) if (sh and pxf) else None

    if mcap and mcap > 0:
        out["loan_pct"] = (d / mcap * 100) if d is not None else None
        out["cash_pct"] = (c / mcap * 100) if c is not None else None
        if out["loan_pct"] is not None and out["cash_pct"] is not None:
            out["combined"] = out["loan_pct"] + out["cash_pct"]
    # ---- revenue and interest income on a MATCHED period basis -------
    # mult = how many of this period fit in a year.
    if rev is not None:
        rev_val, rev_mult = rev, 4
    elif out.get("rev_halfyear") is not None:
        rev_val, rev_mult = out["rev_halfyear"], 2
    elif out.get("rev_annual") is not None:
        rev_val, rev_mult = out["rev_annual"], 1
    else:
        rev_val, rev_mult = None, None
    ann_rev = (rev_val * rev_mult) if rev_val is not None else None
    out["annual_rev"] = ann_rev

    int_mult = 4
    if inti is None:
        for lo, hi, m in ((150, 200, 2), (330, 400, 1)):
            for t in INT_TAGS:
                v = durations(facts, t, lo=lo, hi=hi).get(end)
                if v is not None:
                    inti, int_mult = v[0], m
                    out["intinc_tag"], out["intinc_basis"] = t, f"{lo}-{hi}d"
                    break
            if inti is not None:
                break
    out["intinc_period"] = inti
    out["intinc_annualized"] = (inti * int_mult) if inti is not None else None

    if inti is None:
        out["haram_pct"] = None
        out["notes"].append("interest income: NO TAG -> unverified, not 0 "
                            "(the live gate reads a missing row as 0, "
                            "which PASSES the 5% test vacuously)")
    elif ann_rev and ann_rev > 0:
        # CORRECT: annualized interest income / annualized revenue.
        out["haram_pct"] = abs(inti * int_mult) / ann_rev * 100
        # What the live gate computes: a SINGLE-PERIOD interest income
        # divided by the ANNUALIZED revenue -- a units mismatch that
        # divides the true ratio by 4 (see day-trading.py:755,760).
        out["haram_pct_livegate_formula"] = abs(inti) / ann_rev * 100

    miss = [k for k in ("debt", "cash", "rev_q") if out.get(k) is None
            and not (k == "rev_q" and (out.get("rev_annual") is not None
                                       or out.get("rev_halfyear")
                                       is not None))]
    if miss:
        out["notes"].append(f"MISSING legs: {','.join(miss)}")
    if mcap is None:
        out["notes"].append("no mcap (shares or close missing)")

    cm, lp, cp = out.get("combined"), out.get("loan_pct"), out.get("cash_pct")
    if cm is None:
        out["verdict"] = "CANNOT-VERIFY"
    else:
        ratio_ok = ((lp <= 10 or cm <= 20) and (cp <= 10 or cm <= 20)
                    and cm <= 20)
        hp = out.get("haram_pct")
        haram_ok = (hp is not None and hp < 5)
        out["ratio_ok"] = ratio_ok
        out["haram_ok_strict"] = haram_ok
        # LENIENT mirrors the live gate (missing interest income -> 0 ->
        # passes); STRICT refuses an unverifiable 5% test.
        out["verdict"] = "PASS" if (ratio_ok and (hp is None or hp < 5)) \
            else "FAIL"
        out["verdict_strict"] = "PASS" if (ratio_ok and haram_ok) else "FAIL"
    out["status"] = "OK"
    return out


def load_facts(zf, members, cik):
    name = f"CIK{cik:010d}.json"
    if name not in members:
        return None
    with zf.open(name) as fh:
        return json.loads(fh.read().decode("utf-8")).get("facts") or {}


SAMPLE_PASS = ["ANAB", "CCJ", "DGXX", "ECG", "GRDN", "GRND", "HBM", "IDXX",
               "MXF", "NICE", "ONC", "OSK", "PI", "PLBL", "PVLA", "SLN",
               "SMWB", "SYRE", "TDAC", "TGEN", "TVA", "USAU", "WAVE", "WYY",
               "ZETA"]
SAMPLE_FAIL = ["AIOT", "ALKS", "APAM", "APO", "AVTX", "BWFG", "COR", "CRH",
               "FPH", "GGB", "HRZN", "JCAP", "METC", "MFA", "MGA", "MKSI",
               "NRG", "PNC", "SHPH", "STRO", "TRC", "VNO", "WEYS", "WSC",
               "XNDU"]
TRADED = ["ANGX", "ASST", "BE", "CRML", "DELL", "FRMI", "GTLB", "HIVE",
          "LFST", "MMED", "MRVI", "MRVL", "NEOV", "OKTA", "QCOM", "RARE",
          "RDDT", "SMMT"]


# ---- SIC blind-spot sweep -------------------------------------------------
# Haram-suggestive SIC ranges. The 2026-09-16 sweep over all 1,260 armable
# names found 220 hits, 213 of them financial -- including 126 SIC 6770
# blank-check SPACs -- and ZERO hits in tobacco / gambling / motion pictures /
# ordnance / grocery, which is the keyword screen doing its job.
SIC_BUCKETS = [
    ("blank_check_SPAC", lambda s: s == "6770"),
    ("financial", lambda s: s.startswith("6")),
    ("alcohol_beverage", lambda s: "2080" <= s <= "2085"),
    ("tobacco", lambda s: s == "2111"),
    ("meat_pork", lambda s: s in ("2011", "2013")),
    ("gambling_amusement", lambda s: s in ("7990", "7993", "7999")),
    ("motion_pictures", lambda s: "7812" <= s <= "7841"),
    ("ordnance", lambda s: s in ("3480", "3489")),
    ("aerospace_adjacent", lambda s: s in ("3721", "3724", "3728", "3760",
                                           "3761", "3764", "3769")),
    ("eating_drinking", lambda s: "5810" <= s <= "5813"),
    ("grocery", lambda s: s == "5411"),
    ("drug_stores", lambda s: s == "5912"),
]
SIC_CACHE = ROOT / "data/halal_sic.json"


def fetch_sic(syms, ua="halal-audit m.osama.elmoghany@gmail.com"):
    """{SYM: {sic, sicDescription, name}} from EDGAR submissions, cached and
    resumable. SEC returns 403 without a descriptive User-Agent, and asks for
    <10 req/s -- hence the sleep. 2026-09-16 run: 1,255/1,260 resolved, 0
    errors, 5 with no company CIK at all (HLAL JPO MNZL RISE SPUS -- ETFs)."""
    import time
    import urllib.request
    cache = {}
    if SIC_CACHE.exists():
        cache = json.loads(SIC_CACHE.read_text())
    cm = cik_map()
    todo = [s for s in syms if s not in cache]
    for i, s in enumerate(todo, 1):
        cik = cm.get(s)
        if cik is None:
            cache[s] = {"error": "no-cik"}
            continue
        url = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode())
            cache[s] = {"sic": d.get("sic") or "",
                        "sicDescription": d.get("sicDescription") or "",
                        "name": d.get("name") or ""}
        except Exception as e:
            cache[s] = {"error": f"{type(e).__name__}: {e}"}
        time.sleep(0.15)
        if i % 100 == 0:
            SIC_CACHE.write_text(json.dumps(cache))
            print(f"  sic {i}/{len(todo)}", flush=True)
    SIC_CACHE.write_text(json.dumps(cache))
    return cache


def sic_sweep(armable, uni):
    cache = fetch_sic(sorted(armable))
    from collections import Counter
    hits, counts, by_sic = [], Counter(), Counter()
    for s in sorted(armable):
        e = cache.get(s) or {}
        sic = (e.get("sic") or "").strip()
        if not sic:
            continue
        by_sic[(sic, e.get("sicDescription", ""))] += 1
        b = [n for n, f in SIC_BUCKETS if f(sic)]
        if b:
            counts.update(b)
            v = uni.get(s, {})
            hits.append({"symbol": s, "sic": sic,
                         "desc": e.get("sicDescription"), "name": e.get("name"),
                         "buckets": b, "verdict": v.get("verdict"),
                         "loan_pct": v.get("loan_pct"),
                         "cash_pct": v.get("cash_pct"),
                         "combined": v.get("combined"),
                         "haram_pct": v.get("haram_pct")})
    return {"n_armable": len(armable), "n_with_sic": sum(by_sic.values()),
            "bucket_counts": dict(counts),
            "by_sic": {f"{k[0]} {k[1]}": v for k, v in sorted(by_sic.items())},
            "hits": hits}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--zero-ratio", action="store_true")
    ap.add_argument("--sic", action="store_true",
                    help="SIC blind-spot sweep over the armable list "
                         "(fetches EDGAR submissions, caches to "
                         "data/halal_sic.json, resumable)")
    ap.add_argument("--syms", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    if a.sic:
        uni = json.loads(UNI_F.read_text())
        armable = set(json.loads(LIST_F.read_text())["symbols"])
        res = sic_sweep(armable, uni)
        txt = json.dumps(res, indent=1)
        if a.out:
            Path(a.out).write_text(txt)
            print(f"wrote {a.out}: {res['bucket_counts']}")
        else:
            print(txt)
        return

    uni = json.loads(UNI_F.read_text())
    armable = set(json.loads(LIST_F.read_text())["symbols"])
    syms = []
    if a.sample:
        syms = SAMPLE_PASS + SAMPLE_FAIL + TRADED
    if a.zero_ratio:
        syms += sorted(k for k, v in uni.items()
                       if v.get("verdict") == "PASS"
                       and (v.get("loan_pct") or 0) == 0
                       and (v.get("cash_pct") or 0) == 0)
    if a.syms:
        syms += [s.strip().upper() for s in a.syms.split(",") if s.strip()]
    syms = sorted(dict.fromkeys(syms))

    cm = cik_map()
    rh = json.loads(RH_F.read_text()) if RH_F.exists() else {}
    rows, stats = [], defaultdict(int)
    with zipfile.ZipFile(ZIPF) as zf:
        members = set(zf.namelist())
        for s in syms:
            cik = cm.get(s)
            cached = uni.get(s, {})
            if cik is None:
                rows.append({"symbol": s, "status": "NO-CIK",
                             "cached": cached})
                stats["no_cik"] += 1
                continue
            facts = load_facts(zf, members, cik)
            if facts is None:
                rows.append({"symbol": s, "status": "NO-COMPANYFACTS",
                             "cik": cik, "cached": cached})
                stats["no_facts"] += 1
                continue
            r = recompute(s, facts)
            r["cik"] = cik
            r["cached"] = cached
            r["armable"] = s in armable
            r["rh_mcap"] = (rh.get(s) or {}).get("market_cap")
            # ---- the diff --------------------------------------------
            d = {}
            for k in ("loan_pct", "cash_pct", "combined", "haram_pct"):
                mine, theirs = r.get(k), cached.get(k)
                if mine is None or theirs is None:
                    d[k] = None
                else:
                    d[k] = round(mine - theirs, 2)
            r["delta"] = d
            r["verdict_flip"] = (r.get("verdict") != cached.get("verdict")
                                 and r.get("status") == "OK")
            big = [k for k, v in d.items() if v is not None and abs(v) > 2]
            r["big_delta"] = big
            if r["verdict_flip"]:
                stats["flip"] += 1
            if big:
                stats["delta_gt_2pp"] += 1
            rows.append(r)
            stats["ok"] += 1

    res = {"asof": ASOF, "n": len(rows), "stats": dict(stats), "rows": rows}
    txt = json.dumps(res, indent=1, default=str)
    if a.out:
        Path(a.out).write_text(txt)
        print(f"wrote {a.out} ({len(rows)} rows) stats={dict(stats)}")
    else:
        print(txt)


if __name__ == "__main__":
    main()
