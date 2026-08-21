"""W-campaign Phase 4 (2026-08-21): CANNOT-VERIFY human-review queue.

WHY: the halal screen has three verdicts. CANNOT-VERIFY (haram revenue
plausible, share unmeasurable -- the 5% rule has NOT been run) is not
tradeable pending a human ruling. ~683 such names sit in
data/halal_universe.json and 584 of them recur in the 2-year gapper
pool (7,747 name-days). Live sees only 3-7 armable PASS names/day --
ruling on the highest-recurrence CV names is the compliant path to
widening that. THIS SCRIPT ONLY ASSEMBLES EVIDENCE; the user rules.

WHAT IT DOES
  1. Collect CV names from data/halal_universe.json by fail_reason
     containing "CANNOT-VERIFY". (The cached `verdict` field is sparse
     -- only newer screens write it -- so fail_reason is the key.)
  2. Rank by expected value = pool_days * (1 + live_days):
       pool_days  = appearances in gappers_novol_year.json +
                    gappers_novol_y2025.json (name-days)
       live_days  = days the name shows in a paper_days crossed_set.
     The task spec says frequency x live recurrence; a bare product
     zeroes every name outside the 5-day live sample, so live presence
     is a multiplier bonus (x2) rather than a hard factor. Top 50 kept.
  3. Per name, pull evidence from the EDGAR companyfacts bulk file
     already on disk (no network): enumerate us-gaap tags whose NAME is
     haram-adjacent, compute each revenue line's share of total revenue
     (RevenueFromContractWithCustomerExcludingAssessedTax -> Revenues ->
     SalesRevenueNet, same chain as plan/edgar_backfill.py) and emit a
     suggestion. companyfacts has NO segment dimensions and foreign
     filers are sparse, so NEEDS-MANUAL is the expected common case.
  4. Emit data/halal_review_queue.md (human) + .json (machine).

SUGGESTION LOGIC (suggestions only -- never a ruling):
  Matched tags are classified:
    DIRECT      the line itself is haram revenue (Casino/Gaming/Alcohol/
                Liquor/Wine/Beer/Brew/Distill/Tobacco/Cigar...).
    UPPER-BOUND the line CONTAINS haram revenue as an unknown subset
                (FoodAndBeverage/FoodService/Restaurant): its share is
                an upper bound on the haram share.
    CONTEXT     adjacent but not haram per se (Occupancy/Hotel/Lodging/
                Resort/Cruise rooms revenue): listed as evidence only.
  Then:
    DIRECT share  > 5%  -> FAIL-suggested  (>=50% adds "main line")
    DIRECT share  < 4%  -> PASS-suggested  (the haram line IS tagged
                                            and clears 5% with margin)
    DIRECT 4-5%         -> NEEDS-MANUAL    (no margin)
    else UPPER-BOUND < 4% -> PASS-suggested (even the superset clears)
    else                -> NEEDS-MANUAL
  Shares SUM across same-period direct tags (over-counting from tag
  overlap only ever errs toward manual review, never toward PASS).
  Evidence values are LATEST-FILED (this is research evidence for a
  human, not point-in-time backtest data -- restatements welcome).

  A PASS ruling still never bypasses the ratio gates: day-trading.py::
  halal_check applies the overlay ONLY at the CANNOT-VERIFY exit and
  re-runs the ratio verdict afterwards.

STALE TRIGGERS: entries flagged by pre-2026-08-14 screens carry trigger
words (defense/aerospace/entertainment/gaming/...) that the CURRENT
screen no longer free-text matches (label-only now -- see
HARAM_PRIMARY_LABEL / HARAM_AMBIGUOUS_ANY history in day-trading.py).
Those are annotated "(stale trigger)": a re-screen might not CV them at
all, which is itself useful to the reviewer.

Usage:
  python plan/build_review_queue.py [--top N]
"""

import argparse
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE = ROOT / "data" / "halal_universe.json"
GAPPERS = [ROOT / "data" / "massive" / "gappers_novol_year.json",
           ROOT / "data" / "massive" / "gappers_novol_y2025.json"]
PAPER_DAYS = ROOT / "data" / "paper_days"
ZIPF = ROOT / "data" / "edgar" / "companyfacts.zip"
TICKF = ROOT / "data" / "edgar" / "company_tickers.json"
OUT_MD = ROOT / "data" / "halal_review_queue.md"
OUT_JSON = ROOT / "data" / "halal_review_queue.json"
RULINGS = ROOT / "data" / "halal_rulings.json"

# Total-revenue fallback chain -- same convention as edgar_backfill.py.
REV_CHAIN = ["RevenueFromContractWithCustomerExcludingAssessedTax",
             "Revenues", "SalesRevenueNet",
             "RevenueFromContractWithCustomerIncludingAssessedTax",
             "SalesRevenueGoodsNet", "SalesRevenueServicesNet"]

# Haram-adjacent us-gaap tag-name fragments (case-sensitive CamelCase
# fragments; tags are standard us-gaap concept names). Classification
# drives the suggestion logic in the module docstring.
TAG_CLASSES = {
    "DIRECT": ["Casino", "Gaming", "Gambling", "Alcohol", "Liquor",
               "Wine", "Beer", "Brewer", "Distill", "Tobacco", "Cigar"],
    "UPPER-BOUND": ["FoodAndBeverage", "FoodService", "Restaurant"],
    "CONTEXT": ["Occupancy", "Hotel", "Lodging", "Resort", "Cruise",
                "Rooms"],
}

# Trigger words the CURRENT screen still free-text matches
# (REVENUE_SENSITIVE_WORDS in day-trading.py). Anything else found in a
# cached fail_reason came from an older screen and is annotated stale.
CURRENT_TRIGGERS = {"alcohol", "beer", "wine", "liquor", "spirits",
                    "restaurant", "dining", "beverage", "grocer",
                    "supermarket", "convenience store", "hotel",
                    "resort", "cruise", "hospitality", "tavern",
                    "brewpub", "catering", "delicatessen"}

FY_DAYS = (350, 380)
Q_DAYS = (70, 100)


def _days(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def cik_map():
    """UPPER ticker -> (CIK int, company title). '-'<->'.' variants
    indexed too (same convention as edgar_backfill.cik_map)."""
    raw = json.loads(TICKF.read_text())
    out = {}
    for e in raw.values():
        t = e["ticker"].upper()
        for k in {t, t.replace(".", "-"), t.replace("-", ".")}:
            out.setdefault(k, (e["cik_str"], e.get("title", "")))
    return out


def collect_cv(universe):
    """{SYM: {triggers, stale, loan_pct, cash_pct}} for CANNOT-VERIFY
    entries, keyed on fail_reason (the reliable field)."""
    out = {}
    for sym, v in universe.items():
        fr = v.get("fail_reason") or ""
        if "CANNOT-VERIFY" not in fr:
            continue
        m = re.search(r"CANNOT-VERIFY revenue mix \(([^)]*)\)", fr)
        if m:
            trig = [w.strip() for w in m.group(1).split(",")]
        elif "SPAC/blank-check" in fr:
            trig = ["spac/blank-check"]
        else:
            trig = ["unparsed"]
        out[sym.upper()] = {
            "triggers": trig,
            "stale_triggers": [t for t in trig
                               if t not in CURRENT_TRIGGERS
                               and t != "spac/blank-check"],
            "loan_pct": v.get("loan_pct"),
            "cash_pct": v.get("cash_pct"),
        }
    return out


def pool_counts(cv_syms):
    c = Counter()
    for gf in GAPPERS:
        for rec in json.loads(gf.read_text()):
            s = rec["symbol"].upper()
            if s in cv_syms:
                c[s] += 1
    return c


def live_counts(cv_syms):
    c = Counter()
    for f in sorted(PAPER_DAYS.glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        for s in {str(x).upper() for x in (d.get("crossed_set") or [])}:
            if s in cv_syms:
                c[s] += 1
    return c


def _facts_series(facts, tag):
    """USD duration facts for one us-gaap tag, LATEST-filed per period:
    {(start, end): val}."""
    node = (facts.get("us-gaap") or {}).get(tag) or {}
    out = {}
    for e in node.get("units", {}).get("USD", []):
        s, end, val = e.get("start"), e.get("end"), e.get("val")
        filed = e.get("filed") or ""
        if not s or not end or val is None:
            continue
        key = (s, end)
        if key not in out or filed > out[key][1]:
            out[key] = (float(val), filed)
    return {k: v[0] for k, v in out.items()}


def _pick_latest(series, want_annual=True):
    """Latest (start, end, val), preferring annual periods."""
    for lo, hi in ([FY_DAYS, Q_DAYS] if want_annual else [Q_DAYS]):
        best = None
        for (s, end), val in series.items():
            try:
                d = _days(s, end)
            except ValueError:
                continue
            if lo <= d <= hi and (best is None or end > best[1]):
                best = (s, end, val)
        if best:
            return best
    return None


def _total_rev_for(facts, start, end):
    """Total revenue for exactly (start, end) via the fallback chain;
    ~same-end/duration match as a fallback. -> (val, tag) or None."""
    for tag in REV_CHAIN:
        ser = _facts_series(facts, tag)
        if (start, end) in ser:
            return ser[(start, end)], tag
    for tag in REV_CHAIN:                     # fuzzy: same end +-7d
        for (s, e), val in _facts_series(facts, tag).items():
            try:
                if abs(_days(e, end)) <= 7 and abs(_days(s, start)) <= 14:
                    return val, tag
            except ValueError:
                continue
    return None


def edgar_evidence(zf, members, cik):
    """Enumerate haram-adjacent us-gaap tags for one filer and compute
    each revenue line's share of total revenue. Returns evidence dict."""
    name = f"CIK{cik:010d}.json"
    if name not in members:
        return {"status": "no companyfacts file", "tags": []}
    try:
        facts = json.loads(zf.read(name)).get("facts", {})
    except Exception as e:
        return {"status": f"companyfacts unreadable: {e}", "tags": []}
    gaap = facts.get("us-gaap") or {}
    rows = []
    for tag in sorted(gaap):
        cls = next((c for c, frags in TAG_CLASSES.items()
                    if any(f in tag for f in frags)), None)
        if cls is None:
            continue
        is_rev = (("Revenue" in tag or "Sales" in tag)
                  and not any(x in tag for x in
                              ("Cost", "Expense", "Tax", "Payable",
                               "Receivable", "Liabilit", "Accrued")))
        row = {"tag": tag, "class": cls, "revenue_line": is_rev,
               "share_pct": None, "period": None, "value": None,
               "total_rev": None, "total_rev_tag": None}
        if is_rev:
            latest = _pick_latest(_facts_series(facts, tag))
            if latest:
                s, e, val = latest
                row["period"] = f"{s}..{e}"
                row["value"] = val
                tot = _total_rev_for(facts, s, e)
                if tot and tot[0] > 0:
                    row["total_rev"], row["total_rev_tag"] = tot
                    row["share_pct"] = round(val / tot[0] * 100, 2)
        rows.append(row)
    return {"status": "ok", "tags": rows}


def suggest(evidence):
    """(verdict, reason, est_share) per the module-docstring logic."""
    if evidence["status"] != "ok":
        return "NEEDS-MANUAL", evidence["status"], None
    rev = [r for r in evidence["tags"]
           if r["revenue_line"] and r["share_pct"] is not None]
    direct = [r for r in rev if r["class"] == "DIRECT"]
    ub = [r for r in rev if r["class"] == "UPPER-BOUND"]
    if direct:
        # Sum direct shares over the modal period (overlap over-counts,
        # which only ever errs toward review, never toward PASS).
        period = Counter(r["period"] for r in direct).most_common(1)[0][0]
        tot = round(sum(r["share_pct"] for r in direct
                        if r["period"] == period), 2)
        tags = ", ".join(f"{r['tag']}={r['share_pct']}%" for r in direct
                         if r["period"] == period)
        when = f" [FY {period[:4]}]"
        if tot >= 50:
            return ("FAIL-suggested",
                    f"haram line IS the main line ({tot}% of revenue: "
                    f"{tags}){when}", tot)
        if tot > 5:
            return ("FAIL-suggested",
                    f"direct haram lines {tot}% of revenue (> 5%): "
                    f"{tags}{when}", tot)
        if tot < 4:
            return ("PASS-suggested",
                    f"direct haram lines tagged and only {tot}% of "
                    f"revenue (< 5% with margin): {tags}{when}", tot)
        return ("NEEDS-MANUAL",
                f"direct haram lines {tot}% -- inside 4-5%, no margin: "
                f"{tags}{when}", tot)
    if ub:
        period = Counter(r["period"] for r in ub).most_common(1)[0][0]
        tot = round(sum(r["share_pct"] for r in ub
                        if r["period"] == period), 2)
        tags = ", ".join(f"{r['tag']}={r['share_pct']}%" for r in ub
                         if r["period"] == period)
        when = f" [FY {period[:4]}]"
        if tot < 4:
            return ("PASS-suggested",
                    f"even the SUPERSET line (food+beverage) is only "
                    f"{tot}% of revenue: {tags}{when}", tot)
        return ("NEEDS-MANUAL",
                f"superset line {tot}% of revenue -- haram subset "
                f"unknown: {tags}{when}", None)
    n_ctx = sum(r["class"] == "CONTEXT" for r in evidence["tags"])
    if evidence["tags"]:
        return ("NEEDS-MANUAL",
                f"only context/cost tags matched ({len(evidence['tags'])}"
                f" tags, {n_ctx} context) -- no measurable haram revenue "
                f"line", None)
    return ("NEEDS-MANUAL",
            "no haram-adjacent us-gaap tags at all (companyfacts has no "
            "segment dimensions -- check the 10-K segment note by hand)",
            None)


def edgar_url(cik):
    return ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            f"&CIK={cik:010d}&type=10-K&dateb=&owner=include&count=10")


def build(top_n):
    universe = json.loads(UNIVERSE.read_text())
    cv = collect_cv(universe)
    pool = pool_counts(set(cv))
    live = live_counts(set(cv))
    ranked = sorted(cv, key=lambda s: (-pool.get(s, 0) * (1 + live.get(s, 0)),
                                       -pool.get(s, 0), s))
    picked = [s for s in ranked if pool.get(s, 0) > 0][:top_n]
    cm = cik_map()

    rows = []
    with zipfile.ZipFile(ZIPF) as zf:
        members = set(zf.namelist())
        for i, sym in enumerate(picked, 1):
            cik_t = cm.get(sym)
            if cik_t:
                ev = edgar_evidence(zf, members, cik_t[0])
            else:
                ev = {"status": "no CIK (foreign/delisted?)", "tags": []}
            verdict, reason, est = suggest(ev)
            rows.append({
                "rank": i,
                "symbol": sym,
                "company": cik_t[1] if cik_t else "?",
                "cik": cik_t[0] if cik_t else None,
                "score": pool.get(sym, 0) * (1 + live.get(sym, 0)),
                "pool_days": pool.get(sym, 0),
                "live_days": live.get(sym, 0),
                "triggers": cv[sym]["triggers"],
                "stale_triggers": cv[sym]["stale_triggers"],
                "loan_pct": cv[sym]["loan_pct"],
                "cash_pct": cv[sym]["cash_pct"],
                "evidence": ev,
                "suggested": verdict,
                "suggested_reason": reason,
                "est_haram_share_pct": est,
                "edgar_url": edgar_url(cik_t[0]) if cik_t else None,
            })
            print(f"  {i:>2} {sym:<6} pool={pool.get(sym,0):>3} "
                  f"live={live.get(sym,0)} {verdict:<15} {reason[:70]}",
                  flush=True)

    # Overlay the user's rulings (data/halal_rulings.json) so the MD
    # shows applied verdicts instead of blank boxes once names are ruled.
    # Ruled names DROP OUT of the CV queue on the next build (their
    # universe entries carry real verdicts), so the full rulings log is
    # also emitted as its own section -- the queue rolls forward to the
    # next unruled CV names while the completed review stays visible.
    try:
        rulings = {k: v for k, v in
                   json.loads(RULINGS.read_text()).items()
                   if not k.startswith("_") and isinstance(v, dict)}
    except Exception:
        rulings = {}
    for r in rows:
        r["ruling"] = rulings.get(r["symbol"])
    pool_r = pool_counts(set(rulings))
    rlog = []
    for sym, ru in rulings.items():
        u = universe.get(sym, {})
        live = (u.get("verdict")
                or ("PASS" if u.get("halal") else "FAIL"))
        rlog.append({"symbol": sym, "verdict": ru.get("verdict"),
                     "date": ru.get("date"), "basis": ru.get("basis"),
                     "haram_share_est": ru.get("haram_share_est"),
                     "pool_days": pool_r.get(sym, 0),
                     "live_verdict": live,
                     "live_reason": (u.get("fail_reason") or "")[:80]})
    rlog.sort(key=lambda x: (-x["pool_days"], x["symbol"]))

    cats = defaultdict(list)
    for r in rows:
        cats[r["triggers"][0] if r["triggers"] else "?"].append(r["symbol"])

    out = {
        "built": date.today().isoformat(),
        "purpose": "CANNOT-VERIFY human-review queue (W-campaign Phase "
                   "4). Suggestions are machine evidence only; the USER "
                   "rules. Rulings go in data/halal_rulings.json.",
        "ranking": "pool_days * (1 + live_days); pool = gappers_novol_"
                   "year+y2025 name-days; live = paper_days crossed_set "
                   "days",
        "cv_total": len(cv),
        "cv_in_pool": len(pool),
        "pool_name_days": sum(pool.values()),
        "queue": rows,
        "categories": {k: sorted(v) for k, v in sorted(cats.items())},
        "rulings_applied": rlog,
    }
    OUT_JSON.write_text(json.dumps(out, indent=1))
    write_md(out)
    print(f"\nwrote {OUT_JSON}\nwrote {OUT_MD}")
    dist = Counter(r["suggested"] for r in rows)
    print("suggested-verdict distribution:", dict(dist))
    return out


def write_md(out):
    L = []
    A = L.append
    A(f"# Halal review queue -- CANNOT-VERIFY names ({out['built']})")
    A("")
    A(f"{out['cv_total']} CANNOT-VERIFY names in the universe; "
      f"{out['cv_in_pool']} appear in the 2-year gapper pool across "
      f"{out['pool_name_days']} name-days. Top {len(out['queue'])} by "
      f"expected value below. **These are NOT tradeable until ruled.**")
    A("")
    A("HOW TO RULE: edit `data/halal_rulings.json` -- add "
      "`\"SYM\": {\"verdict\": \"PASS\"|\"FAIL\", \"date\": "
      "\"YYYY-MM-DD\", \"basis\": \"...\", \"haram_share_est\": N}`. "
      "The engine consults rulings ONLY for names its own screen calls "
      "CANNOT-VERIFY; a PASS ruling still has to clear the debt/cash "
      "ratio gates, and a FAIL ruling is final.")
    A("")
    A("Suggested verdicts are machine evidence, not rulings: "
      "PASS-suggested = the haram-adjacent line is tagged in EDGAR and "
      "< 5% of revenue with margin; FAIL-suggested = > 5% or the main "
      "line; NEEDS-MANUAL = companyfacts cannot see it (no segment "
      "dimensions) -- use the EDGAR link and read the segment note.")
    A("")
    A("## Category bulk view")
    A("")
    A("Rule a whole category in one stroke if you wish -- the members "
      "are listed so a category ruling can be copied into the rulings "
      "file per symbol:")
    A("")
    for cat, syms in out["categories"].items():
        A(f"- **{cat}** ({len(syms)}): {', '.join(syms)}")
    A("")
    A("## Queue (rank = pool-day frequency x live recurrence)")
    A("")
    A("| # | Sym | Company | Days | Why flagged | Evidence (EDGAR "
      "companyfacts) | Suggested | RULING |")
    A("|--:|-----|---------|-----:|-------------|------------------|"
      "-----------|--------|")
    for r in out["queue"]:
        trig = ", ".join(r["triggers"])
        if r["stale_triggers"]:
            trig += " *(stale trigger)*"
        days = f"{r['pool_days']}"
        if r["live_days"]:
            days += f" +{r['live_days']} live"
        ev = r["suggested_reason"].replace("|", "/")
        link = f" [EDGAR]({r['edgar_url']})" if r["edgar_url"] else ""
        ru = r.get("ruling")
        if ru and ru.get("verdict") in ("PASS", "FAIL"):
            box = (f"**{ru['verdict']}** (ruled {ru.get('date', '?')}): "
                   f"{ru.get('basis', '').replace('|', '/')}")
        elif ru:                      # reviewed, deliberately unresolved
            box = (f"CV stands (reviewed {ru.get('date', '?')}): "
                   f"{ru.get('basis', '').replace('|', '/')}")
        else:
            box = "`[ ]`"
        A(f"| {r['rank']} | **{r['symbol']}** | "
          f"{r['company'][:38].replace('|','/')} | {days} | {trig} | "
          f"{ev}{link} | {r['suggested']} | {box} |")
    A("")
    if out.get("rulings_applied"):
        A("## Rulings applied (delegated review, recorded in "
          "`data/halal_rulings.json`)")
        A("")
        A("`ruling` is the verdict on the COMPLIANCE question (the 5% "
          "rule); `live now` is what the full engine says today -- a "
          "PASS ruling still fails names whose debt/cash ratios are "
          "bad, and converts them automatically the day their ratios "
          "clear.")
        A("")
        A("| Sym | Pool-days | Ruling | Live now | Basis |")
        A("|-----|----------:|--------|----------|-------|")
        for r in out["rulings_applied"]:
            A(f"| **{r['symbol']}** | {r['pool_days']} | "
              f"{r['verdict']} | {r['live_verdict']} | "
              f"{(r['basis'] or '').replace('|', '/')} |")
        A("")
    A("## Notes")
    A("")
    A("- Evidence values are latest-filed EDGAR numbers (research "
      "evidence, not point-in-time backtest data).")
    A("- *(stale trigger)*: flagged by a pre-2026-08-14 screen on a "
      "word the current screen no longer free-text matches (defense/"
      "aerospace/entertainment/gaming are label-only now). A re-screen "
      "may not CV the name at all; the ruling still controls if it "
      "does.")
    A("- Ratio columns (loan/cash vs mcap) were computed at screen "
      "time and are re-checked live -- a PASS ruling never bypasses "
      "them.")
    A("")
    OUT_MD.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=50)
    args = ap.parse_args()
    if not ZIPF.exists():
        sys.exit(f"missing {ZIPF}")
    build(args.top)
