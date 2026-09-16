"""SEC EDGAR point-in-time fundamentals backfill (2026-08-14).

WHY: the strict backtest gate (HALAL_STRICT=1 in penny_ax11b_massive)
refuses any name whose FILED quarterly is absent from data/pt_halal/.
That cache covered 133/2429 candidate symbols, so C37S ($405,826) is a
LOWER bound and C37H ($665,667) an upper bound. EDGAR's companyfacts
bulk file has the real statements WITH exact filing dates -- this
script backfills them so the interval can be tightened honestly.

DATA FLOW (three stages, each idempotent):
  extract  companyfacts.zip -> data/edgar/extracted/{SYM}.json
           (raw EDGAR quarters + per-field tag provenance + filed date)
  merge    extracted -> data/pt_halal/{SYM}.json
           * existing quarters: values UNTOUCHED, gain a "filed" key
             (unknown keys are ignored by every existing reader)
           * EDGAR-only quarters: written under "quarters_edgar", a
             NEW top-level key. NOT into "quarters" -- the legacy
             (flag-off) gate selects from st["quarters"], so inlining
             new quarters would flip legacy verdicts (the LFST class:
             bounds-refused today, precise-passed with data) and break
             the S095/Z104 identity gate BY DATA ALONE. The side key
             is invisible to every existing reader; only the
             PT_FILED=1 path in penny_ax11b_massive merges it in.
  report   coverage before/after + (symbol, day) decision gains over
           the backtest pools.

HONESTY RULES:
  * value per field = the EARLIEST-FILED 10-Q/10-K entry for that
    period (as-originally-reported; later restatements are future
    information).
  * a quarter EXISTS only when a real filed balance sheet for that
    period end is in EDGAR (cash anchor tag required -- universal on
    genuine balance sheets). No filing => no quarter => the strict
    gate keeps refusing. Absence of a STATEMENT is never fabricated.
  * an absent LINE on a present statement reads as that statement's
    own zero. This is the INCUMBENT pt_halal semantics: the yfinance
    builder (plan/penny_ax11_pt_halal.py val()) writes 0.0 for any
    absent row, and the live gate passed LFST/FRMI under exactly
    those semantics. The task-spec alternative (missing tag = absent
    quarter) was tested and REFUSES both of the task's own sanity
    names: LFST tags no interest-income concept at all (only
    InterestExpense) and FRMI is pre-revenue with no revenue tag.
    Every zero-substitution is counted loudly (zero:debt / zero:rev /
    zero:intinc in the stats).
  * fallback tag nets only ever err CONSERVATIVE: extra debt/cash
    concepts and net-interest concepts can only REFUSE more, never
    false-pass (the gate takes abs(intinc) and upper-bounds debt).
  * fiscal-Q4 flows (rev, intinc) may be derived as FY minus the three
    same-tag sibling quarters that tile the fiscal year (exact
    arithmetic on filed numbers, counted + logged as derived).
  * foreign 20-F/6-K filers are NOT forced; they are counted.

INTEREST-LEG REFINEMENT (2026-09-16). Two keys were added, neither of
which touches a value any existing reader scores:
  * `flows` (extracted only) -- {intinc|nonop: {period_end: [val, filed,
    derived, tag]}}, the interest series under the five-tag precedence
    and the non-operating-income series that upper-bounds it. Kept
    outside `quarters` because a filed interest figure must not be lost
    when the balance-sheet anchor for that period end is absent.
  * `intinc_edgar` / `nonop` on merged pt_halal quarters -- EDGAR's own
    interest reading and the bound, attached ALONGSIDE the untouched
    vendor numbers so halal_pt can fall through a mis-tagged vendor row
    and can PROVE an untagged interest line is under 5%.

Usage:
  python plan/edgar_backfill.py extract [--symbols A,B,... | --universe]
  python plan/edgar_backfill.py merge
  python plan/edgar_backfill.py report
  python plan/edgar_backfill.py spot SYM [SYM...]
"""

import json
import shutil
import sys
import zipfile
from collections import Counter
from datetime import date as D, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDGAR = ROOT / "data" / "edgar"
ZIPF = EDGAR / "companyfacts.zip"
TICKF = EDGAR / "company_tickers.json"
EXTR = EDGAR / "extracted"
BACKUP = EDGAR / "pt_halal_backup"
PT = ROOT / "data" / "pt_halal"
M1 = ROOT / "data" / "massive" / "m1"

MIN_END = "2024-03-31"          # quarters ending here onward
FORMS = {"10-Q", "10-K", "10-Q/A", "10-K/A"}
FOREIGN = {"20-F", "6-K", "40-F", "20-F/A", "6-K/A", "40-F/A"}

# --- tag map (task spec first, standard alternates after). Tiered so
# fallbacks never double-count. Wider nets only ever REFUSE more.
DEBT_T1 = ["LongTermDebtNoncurrent", "LongTermDebtCurrent",
           "ShortTermBorrowings",
           # disjoint balance-sheet debt lines the spec trio misses on
           # notes-payable shells (the ABAT class):
           "NotesPayableCurrent", "LongTermNotesPayable",
           "ConvertibleNotesPayableCurrent", "ConvertibleDebtCurrent",
           "ConvertibleDebtNoncurrent", "LinesOfCreditCurrent",
           "CommercialPaper", "LoansPayableCurrent",
           # finance leases are interest-bearing debt-equivalents and
           # yfinance 'Total Debt' (the incumbent cache) includes them:
           "FinanceLeaseLiabilityCurrent", "FinanceLeaseLiabilityNoncurrent"]
DEBT_T2 = ["DebtCurrent", "LongTermDebt", "NotesPayable",
           "ConvertibleDebt", "LoansPayable", "ShortTermDebt"]
# tier-2 totals may over-count vs each other -- OVER-counting debt only
# ever REFUSES more, never false-passes, so it is the conservative side.
DEBT_T3 = ["DebtLongtermAndShorttermCombinedAmount"]
CASH_TAGS = ["CashAndCashEquivalentsAtCarryingValue",       # anchor
             "CashCashEquivalentsRestrictedCashAndRestrictedCash"
             "Equivalents"]     # fallback; incl. restricted = stricter
# Short-term-investments net: the MAX across these concepts (max never
# double-counts total-vs-component tagging). Spot check that forced
# this: ABSI holds $117M in marketable securities tagged only under
# MarketableSecuritiesCurrent -- ShortTermInvestments alone read $0,
# and UNDER-counted cash is the FALSE-PASS direction for the cash leg.
STI_TAGS = ["ShortTermInvestments", "MarketableSecuritiesCurrent",
            "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
            "AvailableForSaleSecuritiesCurrent",
            "HeldToMaturitySecuritiesCurrent", "TradingSecuritiesCurrent"]
REV_TAGS = ["RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues", "SalesRevenueNet",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "SalesRevenueGoodsNet", "SalesRevenueServicesNet",
            "RevenuesNetOfInterestExpense",
            "RegulatedAndUnregulatedOperatingRevenue"]
# INTEREST INCOME -- TAG PRECEDENCE (user decision 2026-09-16, the
# interest-leg refinement). These five concepts, in this order, are the
# ones that actually mean "interest earned on our cash". The first one
# present for a period wins; there is no summing across them (they are
# alternative spellings of the same line, not components).
#
# TWO TAGS WERE REMOVED from the pre-refinement list and the removal is
# deliberate, not an oversight:
#   * InterestIncomeExpenseNet -- interest income MINUS interest
#     expense. A bank concept. For a borrower it is usually NEGATIVE and
#     |x| then measures interest PAID, which the 5% income test does not
#     ask about. Reading it as interest income is the same class of
#     error as yfinance's "Net Interest Income" fallback (defect A).
#   * InvestmentIncomeNet -- total investment income net of expense,
#     incl. dividends and realised gains. It is a BOUND on interest, not
#     interest, so it moved to BOUND_TAGS below where it belongs.
INT_TAGS = ["InvestmentIncomeInterest", "InterestIncomeOperating",
            "InterestAndDividendIncomeOperating", "InterestIncomeOther",
            "InvestmentIncomeInterestAndDividend"]
# PROVEN UPPER BOUND on interest income (user decision 2026-09-16).
# Interest earned on cash is a NON-OPERATING item on a US-GAAP income
# statement, so it is a SUBSET of the non-operating bucket: if the whole
# bucket is under 5% of revenue then the interest inside it is too,
# whatever the filer chose to tag. That is a PROOF, not an estimate, and
# it is what lets the gate clear the ~337 names that simply never tag an
# immaterial interest line ("missing" is not "unverifiable" when a
# proven upper bound exists). Precedence, not a sum -- these overlap.
BOUND_TAGS = ["NonoperatingIncomeExpense", "OtherNonoperatingIncomeExpense",
              "InvestmentIncomeNet"]


def m1_symbols():
    return sorted({f.name.rsplit("_", 1)[0] for f in M1.glob("*.csv")})


def universe_symbols():
    """Every name the LIVE gate can be asked about (halal_universe keys
    + today's armable list). Added 2026-09-16: the live interest-leg
    resolver reads data/edgar/extracted/{SYM}.json from disk only, so a
    name with no extracted file is silently unresolvable -- and the
    m1-only extract covered just 925 of the 1,260 names the rescreen
    re-decides. Extraction is a local zip read; widening it is cheap."""
    out = set()
    for f in ("data/halal_universe.json", "data/halal_list.json",
              "data/halal_list.NEW.json"):
        p = ROOT / f
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        out |= set(d.get("symbols") or d) if isinstance(d, dict) else set()
    return sorted(s for s in out if isinstance(s, str)
                  and not s.startswith("_"))


def cik_map():
    """UPPER ticker -> CIK int. Also index the '-'<->'.' variants."""
    raw = json.loads(TICKF.read_text())
    out = {}
    for e in raw.values():
        t = e["ticker"].upper()
        for k in {t, t.replace(".", "-"), t.replace("-", ".")}:
            out.setdefault(k, e["cik_str"])
    return out


def _days(a, b):
    return (D.fromisoformat(b) - D.fromisoformat(a)).days


def _inst(facts, tag):
    """Instant USD facts: {end: (val, filed)}, earliest-filed original."""
    node = (facts.get("us-gaap") or {}).get(tag)
    out = {}
    for e in (node or {}).get("units", {}).get("USD", []):
        end, val, filed = e.get("end"), e.get("val"), e.get("filed")
        if (e.get("form") not in FORMS or not end or not filed
                or val is None or end < MIN_END or e.get("start")):
            continue
        if end not in out or filed < out[end][1]:
            out[end] = (float(val), filed)
    return out


def _dur(facts, tag):
    """Duration USD facts for one tag.
    Returns (quarterly {end: (val, filed, start)},
             annual   [(start, end, val, filed)])."""
    node = (facts.get("us-gaap") or {}).get(tag)
    q, ann = {}, []
    for e in (node or {}).get("units", {}).get("USD", []):
        s, end = e.get("start"), e.get("end")
        val, filed = e.get("val"), e.get("filed")
        if (e.get("form") not in FORMS or not s or not end or not filed
                or val is None):
            continue
        try:
            d = _days(s, end)
        except ValueError:
            continue
        if 70 <= d <= 100:
            # NO MIN_END cut here: pre-window quarters are needed as
            # SIBLINGS when tiling a fiscal-Q4 whose year ends just
            # inside the window (FYs ending Mar-Jun 2024).
            if end not in q or filed < q[end][1]:
                q[end] = (float(val), filed, s)
        elif 350 <= d <= 380 and end >= MIN_END:
            ann.append((s, end, float(val), filed))
    return q, ann


def _derive_q4(q, ann, all_q):
    """FY - (three same-tag sibling quarters tiling the year) = fiscal
    Q4 flow. Exact arithmetic on filed numbers; requires the three
    siblings to actually tile [fy_start, q4_start) and the residual
    period to be quarter-length. Returns {end: (val, filed, 'derived')}"""
    out = {}
    for s, end, val, filed in ann:
        if end in q or end in out:
            continue                       # direct quarterly exists
        sibs = [(e, v) for e, (v, _f, st) in all_q.items()
                if s <= st < e <= end and e < end]
        sibs = sorted(sibs)[-3:]
        if len(sibs) != 3:
            continue
        last_end = sibs[-1][0]
        try:
            q4d = _days(last_end, end)
        except ValueError:
            continue
        if not 70 <= q4d <= 100:
            continue
        out[end] = (float(val) - sum(v for _, v in sibs), filed, "derived")
    return out


def _flow_series(facts, tags, stats, field):
    """First-hit tag series for a flow field (rev / intinc / nonop):
    {end: (val, filed, derived?, tag)} + per-tag hit accounting.

    `tags` is a PRECEDENCE list: the first tag that carries a period
    wins it, and later tags only fill periods still empty. The winning
    tag is carried in the tuple so a verdict can name its own evidence
    (2026-09-16 -- "interest per InvestmentIncomeInterest" and "per
    InterestIncomeOther" are not the same claim)."""
    out = {}
    for tag in tags:
        q, ann = _dur(facts, tag)
        der = _derive_q4(q, ann, dict(q))
        n_new = 0
        for end, (val, filed, *_rest) in {**q, **der}.items():
            if end not in out:
                out[end] = (val, filed, end in der, tag)
                n_new += 1
                if end in der:
                    stats[f"{field}:derived_q4"] += 1
        if n_new:
            stats[f"{field}:{tag}"] += n_new
    return out


def _debt_at(facts, end, cache):
    """Tiered debt at period end. Returns (val, filed) or None.
    Tier presence rule: >=1 tag of the tier present -> missing tier
    siblings read as 0 (an absent balance-sheet line IS zero on that
    statement -- unlike a missing statement, which stays absent).

    TIER-PRECEDENCE BUG, fixed 2026-09-16 (halal audit Bug 5).
    This used to RETURN the first tier that had any tag present, so a
    filer that tags a small tier-1 component AND the tier-2 aggregate
    had the aggregate discarded. QCOM's 2026-06-28 10-Q tags
    LongTermDebtCurrent 1,991M + CommercialPaper 498M (tier 1) *and*
    LongTermDebt 12,781M (tier 2): precedence returned 2,489M against a
    true 15,270M (6.1x understated). Measured prevalence at the time:
    4.5% of symbols (20 of 449 sampled) at their latest quarter --
    TSLA x27.5, WFC x7.2, CTEV x312.

    Now every tier is summed and the MAXIMUM is taken. Over-counting
    debt only ever REFUSES more, which is the safe direction for a gate
    whose job is to refuse; under-counting is the false-PASS direction.
    Caveat kept from the audit (Sec 2.3): even max(components, aggregate)
    is not universally right -- MKSI tags LongTermDebt 2,544M and
    ShortTermBorrowings 1,399M as DISJOINT lines (true total ~4,023M),
    which no fixed tag rule recovers. XBRL debt does not reduce to one
    rule; this is the conservative approximation, not the truth."""
    best = None
    for tier in (DEBT_T1, DEBT_T2, DEBT_T3):
        got = [cache[t][end] for t in tier if end in cache[t]]
        if not got:
            continue
        cand = (sum(v for v, _ in got), max(f for _, f in got))
        if best is None or cand[0] > best[0]:
            best = cand
    return best


def extract_symbol(facts, stats):
    """-> (quarters list, shares, forms_seen) honoring the honesty rules."""
    cash_by_tag = [(t, _inst(facts, t)) for t in CASH_TAGS]
    sti = {}
    for t in STI_TAGS:            # MAX across concepts per period end
        for end, (v, f) in _inst(facts, t).items():
            if end not in sti or v > sti[end][0]:
                sti[end] = (v, f)
    debt_cache = {t: _inst(facts, t) for t in DEBT_T1 + DEBT_T2 + DEBT_T3}
    rev = _flow_series(facts, REV_TAGS, stats, "rev")
    inti = _flow_series(facts, INT_TAGS, stats, "intinc")
    # the proven upper bound on interest (2026-09-16 interest-leg
    # refinement). Kept as its OWN series rather than folded into
    # `intinc`: it is evidence about a CEILING, and a gate that cannot
    # tell a measurement from a bound cannot honestly say which one
    # cleared a name.
    bound = _flow_series(facts, BOUND_TAGS, stats, "nonop")

    # a quarter EXISTS iff a filed balance sheet anchors it (cash tag
    # present at that period end). Absent LINES on that statement read
    # as the statement's own zero -- incumbent pt_halal semantics.
    ends = sorted({e for _, c in cash_by_tag for e in c}
                  | {e for e in rev if e >= MIN_END})
    quarters = []
    for end in ends:
        cash_hit = next(((t, c[end]) for t, c in cash_by_tag
                         if end in c), None)
        if cash_hit is None:
            stats["q_dropped_no_balance_sheet"] += 1
            continue
        ctag, (cval, cfil) = cash_hit
        filed = [cfil]
        # MISSING-ROW FLAGS (2026-09-16 halal fix, user decision 4:
        # "a missing statement row never reads as 0"). The 0.0 defaults
        # below are kept so the stored schema is unchanged, but each
        # absent line is now NAMED in `miss` so halal_pt can REFUSE the
        # quarter instead of scoring a fabricated zero. `cash` can never
        # be missing: a quarter only exists here because a cash tag
        # anchored it.
        miss = []
        d = _debt_at(facts, end, debt_cache)
        if d is None:
            d = (0.0, cfil)                    # no debt line tagged
            stats["zero:debt"] += 1
            miss.append("debt")
        rv = rev.get(end)
        if rv is None:
            rv = (0.0, cfil, False, None)      # no revenue line tagged
            stats["zero:rev"] += 1
            miss.append("rev")
        iv = inti.get(end)
        if iv is None:
            iv = (0.0, cfil, False, None)      # no interest-income line
            stats["zero:intinc"] += 1
            miss.append("intinc")
        bv = bound.get(end)
        if bv is None:
            bv = (0.0, cfil, False, None)      # no non-operating line
            stats["zero:nonop"] += 1
            miss.append("nonop")               # filtered out by _q_miss
        sval, sfil = sti.get(end, (0.0, cfil))
        if not any((d[0], cval + sval, rv[0], iv[0])):
            # all-zero row (inception-date artifacts, e.g. FRMI's
            # "period from inception" instants): carries no statement
            # information yet would VACUOUSLY PASS the ratio gate
            # (0/mcap everywhere). Refuse to write it.
            stats["q_dropped_all_zero"] += 1
            continue
        filed += [d[1], sfil, rv[1], iv[1]]
        quarters.append({
            "date": end,
            "debt": d[0],
            "cash": cval + sval,
            "rev": rv[0],
            "intinc": iv[0],
            "nonop": bv[0],
            "filed": max(filed),
            "miss": miss,
            "src": {"debt_filed": d[1], "cash_filed": cfil,
                    "rev_derived": rv[2], "intinc_derived": iv[2],
                    "intinc_tag": iv[3], "nonop_tag": bv[3]},
        })
        stats["q_ok"] += 1
        if end in sti:
            stats["cash:+ShortTermInvestments"] += 1
        stats[f"cash:{ctag}"] += 1
    shares = None
    for e in ((facts.get("dei") or {})
              .get("EntityCommonStockSharesOutstanding") or {}) \
            .get("units", {}).get("shares", []):
        if e.get("val") is not None and e.get("end"):
            if shares is None or e["end"] > shares[0]:
                shares = (e["end"], e["val"])
    forms = Counter(e.get("form") for tag in (facts.get("us-gaap") or {})
                    .values() for us in tag.get("units", {}).values()
                    for e in us)
    # INTEREST-LEG FLOWS (2026-09-16), stored SEPARATELY from `quarters`
    # on purpose. A quarter only EXISTS above when a cash tag anchors a
    # filed balance sheet at that period end; the 5% test is an INCOME
    # question and must not lose a filed interest figure because the
    # balance-sheet anchor for the same period end is missing or dated a
    # few days apart. Keyed by period end -> [value, filed, derived, tag].
    flows = {
        "intinc": {e: [v[0], v[1], v[2], v[3]] for e, v in inti.items()
                   if e >= MIN_END},
        "nonop": {e: [v[0], v[1], v[2], v[3]] for e, v in bound.items()
                  if e >= MIN_END},
    }
    return quarters, (shares[1] if shares else None), forms, flows


def cmd_extract(only=None):
    EXTR.mkdir(parents=True, exist_ok=True)
    syms = only or m1_symbols()
    cm = cik_map()
    stats = Counter()
    no_cik, foreign_only, no_quarters, ok = [], [], [], 0
    with zipfile.ZipFile(ZIPF) as zf:
        members = set(zf.namelist())
        for i, sym in enumerate(syms, 1):
            cik = cm.get(sym.upper())
            if cik is None:
                no_cik.append(sym)
                continue
            name = f"CIK{cik:010d}.json"
            if name not in members:
                no_cik.append(sym)
                continue
            try:
                facts = json.loads(zf.read(name)).get("facts", {})
                quarters, shares, forms, flows = extract_symbol(facts, stats)
            except Exception as e:            # never write partial junk
                print(f"  ERROR {sym}: {e}", flush=True)
                stats["errors"] += 1
                continue
            domestic = any(f in FORMS for f in forms)
            if not quarters:
                (foreign_only if (set(forms) & FOREIGN and not domestic)
                 else no_quarters).append(sym)
            else:
                ok += 1
            (EXTR / f"{sym}.json").write_text(json.dumps({
                "cik": cik, "quarters": quarters, "shares": shares,
                "flows": flows,
                "foreign_only": bool(set(forms) & FOREIGN and not domestic),
            }))
            if i % 250 == 0:
                print(f"  ..{i}/{len(syms)} ({ok} with quarters)",
                      flush=True)
    print(f"\nEXTRACT: {len(syms)} symbols | {ok} with >=1 full quarter | "
          f"{len(no_cik)} no CIK/companyfacts | {len(foreign_only)} "
          f"foreign-filer-only (20-F/6-K, not forced) | "
          f"{len(no_quarters)} domestic but no complete quarter")
    print("\nPER-TAG HIT RATES (quarters contributed):")
    for k in sorted(stats):
        print(f"  {k:<55} {stats[k]}")
    (EDGAR / "extract_stats.json").write_text(json.dumps({
        "stats": dict(stats), "no_cik": no_cik,
        "foreign_only": foreign_only, "no_quarters": no_quarters}))


def _fuzzy_match(date, existing_dates, tol=4):
    """EDGAR period end vs yfinance quarter date: same quarter when
    within `tol` days (52/53-week fiscal calendars vs month ends)."""
    for ex in existing_dates:
        try:
            if abs(_days(date, ex)) <= tol:
                return ex
        except ValueError:
            continue
    return None


def cmd_merge():
    if not BACKUP.exists():
        shutil.copytree(PT, BACKUP)
        print(f"backup: {PT} -> {BACKUP}")
    created = updated = side_q = filed_attached = flow_attached = 0
    for f in sorted(EXTR.glob("*.json")):
        ex = json.loads(f.read_text())
        if not ex["quarters"]:
            continue
        sym = f.stem
        ptf = PT / f"{sym}.json"
        if ptf.exists():
            st = json.loads(ptf.read_text())
            created_this = False
        else:
            st = {"quarters": [], "shares": ex.get("shares"),
                  "industry": "", "err": ""}
            created_this = True
        by_date = {q["date"]: q for q in st.get("quarters", [])}
        # INTEREST-LEG SIDE FACTS (2026-09-16). The four scored fields
        # (debt/cash/rev/intinc) of an existing yfinance quarter stay
        # UNTOUCHED -- that is what keeps every flag-off reader and the
        # S095/Z104 identity gate byte-stable. What the quarter gains is
        # EDGAR's own interest figure and the non-operating upper bound
        # under NEW key names, so halal_pt can (a) fall through when the
        # vendor's `intinc` is implausible and (b) prove an untagged
        # interest line is under 5% instead of refusing the name. Both
        # keys are REBUILT (and cleared) every run, like quarters_edgar,
        # so the merge stays idempotent.
        flows = ex.get("flows") or {}
        f_int, f_non = flows.get("intinc") or {}, flows.get("nonop") or {}
        for q in st.get("quarters", []):
            for key, src in (("intinc_edgar", f_int), ("nonop", f_non)):
                hit = q["date"] if q["date"] in src else \
                    _fuzzy_match(q["date"], src)
                if hit:
                    q[key] = src[hit][0]
                    flow_attached += 1
                else:
                    q.pop(key, None)
        side = []
        for q in sorted(ex["quarters"], key=lambda x: x["date"]):
            hit = q["date"] if q["date"] in by_date else \
                _fuzzy_match(q["date"], by_date)
            if hit:
                # existing quarter: values untouched, gains "filed"
                if by_date[hit].get("filed") != q["filed"]:
                    by_date[hit]["filed"] = q["filed"]
                    filed_attached += 1
            else:
                nq = {k: q[k] for k in
                      ("date", "debt", "cash", "rev",
                       "intinc", "filed", "miss")}
                # an EDGAR-only quarter IS the EDGAR reading, so its own
                # intinc is also the "edgar-interest" answer; carrying it
                # under both names keeps the resolver one code path.
                if "intinc" not in q["miss"]:
                    nq["intinc_edgar"] = q["intinc"]
                if "nonop" not in q["miss"]:
                    nq["nonop"] = q["nonop"]
                side.append(nq)
        # side list rebuilt from scratch each run -> idempotent
        st["quarters_edgar"] = side
        side_q += len(side)
        if not st.get("shares") and ex.get("shares"):
            st["shares"] = ex["shares"]
        ptf.write_text(json.dumps(st))
        created += created_this
        updated += not created_this
    print(f"MERGE: {created} pt_halal files created, {updated} updated, "
          f"{side_q} EDGAR-only quarters (side key), "
          f"{filed_attached} filed dates attached to existing quarters, "
          f"{flow_attached} interest/bound facts attached")


def _usable(qs, date, lag=45):
    """strict-legacy availability: period end + lag <= date."""
    return any((D.fromisoformat(q["date"]) + timedelta(days=lag)
                ).isoformat() <= date for q in qs)


def _usable_filed(qs, date):
    """PT_FILED availability: filed + 1 day <= date, else end+45."""
    for q in qs:
        f = q.get("filed")
        if f:
            if (D.fromisoformat(f[:10]) + timedelta(days=1)
                    ).isoformat() <= date:
                return True
        elif (D.fromisoformat(q["date"]) + timedelta(days=45)
              ).isoformat() <= date:
            return True
    return False


def cmd_report():
    syms = m1_symbols()
    n_before = n_after = 0
    qcount = Counter()
    for sym in syms:
        old = BACKUP / f"{sym}.json"
        new = PT / f"{sym}.json"
        if old.exists() and json.loads(old.read_text()).get("quarters"):
            n_before += 1
        if new.exists():
            st = json.loads(new.read_text())
            qs = ([q for q in st.get("quarters", []) if q.get("filed")]
                  + st.get("quarters_edgar", []))
            if qs:
                n_after += 1
                qcount[sym] = len(qs)
    print(f"COVERAGE: symbols with >=1 quarter  before={n_before}  "
          f"after(filed-dated)={n_after}  of {len(syms)} candidates")
    if qcount:
        vals = sorted(qcount.values())
        print(f"filed quarters/symbol: min={vals[0]} "
              f"median={vals[len(vals)//2]} max={vals[-1]} "
              f"total={sum(vals)}")
    # (symbol, day) decisions of the backtest pools that gain a FILED qtr
    for lab in ("year", "y2025"):
        gf = ROOT / f"data/massive/gappers_novol_{lab}.json"
        if not gf.exists():
            continue
        gap = [c for c in json.loads(gf.read_text())
               if c.get("hist_n", 99) >= 50]
        gain = tot = before_ok = after_ok = 0
        cache = {}
        for c in gap:
            sym, date = c["symbol"], c["date"]
            if sym not in cache:
                oldf, newf = BACKUP / f"{sym}.json", PT / f"{sym}.json"
                oq = (json.loads(oldf.read_text()).get("quarters", [])
                      if oldf.exists() else [])
                st = json.loads(newf.read_text()) if newf.exists() else {}
                nq = st.get("quarters", []) + st.get("quarters_edgar", [])
                cache[sym] = (oq, nq)
            oq, nq = cache[sym]
            tot += 1
            b = _usable(oq, date)
            a = _usable_filed(nq, date)
            before_ok += b
            after_ok += a
            gain += (a and not b)
        print(f"{lab}: {tot} (symbol,day) decisions | strict-verifiable "
              f"before {before_ok} ({100*before_ok/tot:.1f}%) -> after "
              f"{after_ok} ({100*after_ok/tot:.1f}%) | gained {gain}")


def cmd_spot(syms):
    for sym in syms:
        print(f"\n=== {sym} ===")
        exf = EXTR / f"{sym}.json"
        if not exf.exists():
            print("  (not extracted)")
            continue
        ex = json.loads(exf.read_text())
        print(f"  CIK {ex['cik']}  shares {ex.get('shares')}")
        for q in ex["quarters"]:
            print(f"  {q['date']}  debt={q['debt']:>16,.0f}  "
                  f"cash={q['cash']:>16,.0f}  rev={q['rev']:>16,.0f}  "
                  f"intinc={q['intinc']:>14,.0f}  filed={q['filed']}"
                  f"{'  [rev derived-Q4]' if q['src']['rev_derived'] else ''}")


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "extract"
    if cmd == "extract":
        only = None
        if "--symbols" in args:
            only = args[args.index("--symbols") + 1].split(",")
        elif "--universe" in args:
            only = sorted(set(m1_symbols()) | set(universe_symbols()))
        cmd_extract(only)
    elif cmd == "merge":
        cmd_merge()
    elif cmd == "report":
        cmd_report()
    elif cmd == "spot":
        cmd_spot(args[1:])
    else:
        sys.exit(f"unknown command {cmd}")
