"""ONE-TIME (then monthly) HALAL UNIVERSE PRE-SCREEN.

USER (2026-08-08): "analyze which stocks are halal based on recent
quarterly earnings, if not exist, use half year earning, if not exist,
use annual earnings. and save those stocks, so when we scan stocks, we
only scan the halal stocks, instead of wasting time search for so many
stocks... the halal skill should update stocks every first of each
month."

Universe: every clean ticker with close >= $2 in the most recent
grouped-daily file (data/massive/gd) -- the same universe the scanner
can ever surface.

Verdict: day-trading.py::halal_check VERBATIM -- the same function the
live session calls, so the pre-screen and the live gate cannot
disagree. Its source chain is already quarterly -> annual -> info;
half-year filers (foreign 6-K reporters) appear in yfinance's quarterly
table with 6-month period ends, so the user's quarterly -> half-year ->
annual chain is what this yields in practice. `source` records which
tier answered.

Market cap: names where yfinance has no mcap AND no shares outstanding
cannot be ratio-screened (the SSP bug class). They are NOT marked
haram -- they land in needs_mcap.json for the agent to backfill via
Robinhood (update_rh_fundamentals.py) and re-run; halal_check picks the
RH cap up automatically through load_rh_fundamentals.

Output (data/):
  halal_universe.json  full verdicts {sym: {halal, source, ratios...}}
  halal_list.json      just the PASSING symbols (what the scanner uses)
  needs_mcap.json      unverifiable pending an RH market cap

Resumable: flushes every 50 symbols, skips already-done on re-run.
Refresh monthly (1st): delete halal_universe.json first for a clean
pass, or pass --refresh.
"""

import gzip
import importlib.util
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

_spec = importlib.util.spec_from_file_location("dt", ROOT / "day-trading.py")
dt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dt)

GD = ROOT / "data/massive/gd"
UNI_F = ROOT / "data/halal_universe.json"
LIST_F = ROOT / "data/halal_list.json"
NEED_F = ROOT / "data/needs_mcap.json"
SIC_F = ROOT / "data/sic_codes.json"
EDGAR_TICKERS = ROOT / "data/edgar/company_tickers.json"
MIN_PRICE = 2.0
THREADS = 2          # v1 with 6 threads: yfinance rate-limited after ~900
                     # symbols and returned empty statements for the next
                     # 9,800 -- the no-data guard refused them all (105
                     # halal of 10,761, 97% "NO FUNDAMENTALS DATA").
                     # Slow and steady is the only way through 10k names.
PACE_SEC = 0.7       # per-request pause
# nightly Task Scheduler run sets HALAL_SLOW=1: single-file through the
# night, gentle enough that the limiter never engages
import os as _os
if _os.environ.get("HALAL_SLOW"):
    THREADS, PACE_SEC = 1, 2.5
BREAKER = 30         # consecutive no-data results -> assume rate-limited
BREAKER_SLEEP = 600  # and stand down for 10 minutes


def clean_ticker(sym):
    if not sym or not sym.isalpha() or not sym.isupper():
        return False
    if len(sym) == 5 and sym.endswith(("W", "U", "R")):
        return False
    return len(sym) <= 5


def universe():
    latest = sorted(GD.glob("*.json.gz"))[-1]
    with gzip.open(latest, "rt", encoding="utf-8") as f:
        rows = json.load(f)
    syms = sorted(r["T"] for r in rows
                  if clean_ticker(r.get("T") or "")
                  and (r.get("c") or 0) >= MIN_PRICE)
    print(f"universe from {latest.name}: {len(syms):,} symbols "
          f"(clean ticker, close >= ${MIN_PRICE:.0f})", flush=True)
    return syms


def _retryable(res):
    """A verdict that only says 'no data' is a FAILED FETCH, not a
    verdict -- must be retried on the next pass, never cached as done."""
    return (res.get("source") in ("none", "error")
            or "NO FUNDAMENTALS DATA" in (res.get("fail_reason") or ""))


# KEY NAMES MUST MATCH halal_check's OUTPUT (see the note in screen_one).
# `haram_src` and `interest_flags` joined on 2026-09-16 with the
# interest-leg refinement: the 5% verdict is no longer answerable from
# the percentage alone -- 2.16% MEASURED from a filer's own interest tag
# and 2.16% PROVEN as a ceiling from its non-operating bucket are
# different claims, and a cache that stores only the number cannot tell
# a later reader which one it holds.
CACHED_KEYS = ("halal", "verdict", "source", "loan_pct", "cash_pct",
               "combined", "haram_pct", "haram_src", "interest_flags",
               "fail_reason")


def screen_one(sym):
    time.sleep(PACE_SEC)
    try:
        r = dt.halal_check(sym)
        # KEY NAMES MUST MATCH halal_check's OUTPUT. They did not: it
        # returns "combined" and "haram_pct", so "combined_pct" and
        # "haram_rev_pct" cached None for every one of the 1,347 names
        # in the 2026-08-09 universe -- silently, because nothing read
        # them back. Also cache "verdict" so CANNOT-VERIFY (reviewable)
        # stays distinguishable from FAIL (permanently out); both set
        # halal=False, so the flag alone conflates them.
        return sym, {k: r.get(k) for k in CACHED_KEYS}
    except Exception as e:
        return sym, {"halal": False, "source": "error",
                     "fail_reason": f"ERROR: {type(e).__name__}: {e}"}


# ---------------------------------------------------------------- SIC
# SIC CACHE (user decision 2026-09-16, halal audit fix 2). The gate
# hard-FAILs SIC 6000-6999, so it needs a SIC per symbol -- and the
# LIVE gate must never block a 07:00 scan on an SEC round-trip. This
# builds the cache offline:
#
#   data/edgar/company_tickers.json   ticker -> CIK
#   data.sec.gov/submissions/CIK##########.json   CIK -> sic
#
# companyfacts.zip carries only {cik, entityName, facts} -- no `sic` --
# so the submissions endpoint is the only EDGAR source for it.
# Resumable: already-cached symbols are skipped, so a re-run after an
# interruption costs only the remainder.
#
# Names with NO SIC (no CIK at all -- ETFs and 1940-Act funds have
# none, which is itself a tell) are NOT excluded on SIC grounds; the
# keyword screen and the ratios still decide them.
SEC_UA = "stocks-automation halal-gate m.osama.elmoghany@gmail.com"


def cik_map():
    """UPPER ticker -> CIK int, incl. the '-'/'.' spelling variants."""
    raw = json.loads(EDGAR_TICKERS.read_text())
    out = {}
    for e in raw.values():
        t_ = str(e["ticker"]).upper()
        for k in {t_, t_.replace(".", "-"), t_.replace("-", ".")}:
            out.setdefault(k, e["cik_str"])
    return out


def _cached_symbols():
    """Every symbol that already has a verdict or a ruling -- the names
    the sector screen must be able to answer for, beyond today's tape."""
    out = set()
    try:
        out |= set(json.loads(UNI_F.read_text()))
    except Exception:
        pass
    try:
        r = json.loads((ROOT / "data/halal_rulings.json").read_text())
        out |= {s for s in r if not s.startswith("_")}
        out |= set(r.get("_lifted") or {})
    except Exception:
        pass
    return out


SIC_THREADS = 5      # SEC asks for <10 req/s; 5 in flight stays inside it
                     # and takes the full 10,908-name universe from ~3h
                     # (serial, SEC latency dominates) to ~25 min.


def cmd_sic(syms=None, pace=0.05, threads=SIC_THREADS):
    import urllib.request
    from threading import Lock
    cache = json.loads(SIC_F.read_text()) if SIC_F.exists() else {}
    # The universe is TODAY's >= $2 grouped-daily list; halal_universe
    # also holds names that have since dropped below $2 or off the tape,
    # and the rescreen still has to sector-screen those. Covering only
    # universe() left 55 armable names (mostly SIC 6770 shells) with no
    # SIC at all -- i.e. silently exempt from the sector screen.
    syms = syms or sorted(set(universe()) | _cached_symbols())
    cm = cik_map()
    today = time.strftime("%Y-%m-%d")
    todo = [s for s in syms if s not in cache]
    print(f"SIC: {len(cache):,} cached, {len(todo):,} to fetch", flush=True)
    lock = Lock()
    counts = {"ok": 0, "nocik": 0, "err": 0}

    def one(s):
        cik = cm.get(s.upper())
        if cik is None:
            return s, {"sic": "", "status": "no-cik",
                       "source": "edgar/company_tickers.json",
                       "fetched": today}, "nocik"
        url = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
        time.sleep(pace)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": SEC_UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode())
            return s, {"sic": str(d.get("sic") or ""),
                       "desc": d.get("sicDescription") or "",
                       "name": d.get("name") or "",
                       "cik": cik,
                       "status": "ok" if d.get("sic") else "no-sic",
                       "source": "edgar/submissions",
                       "fetched": today}, "ok"
        except Exception as e:
            # NOT cached: a transport failure is not an answer. Caching
            # it would silently exempt the name from the sector screen
            # forever -- the halal-cache-poisoning failure mode.
            return s, None, f"err {type(e).__name__}: {e}"

    with ThreadPoolExecutor(max_workers=threads) as ex:
        for i, (s, rec, kind) in enumerate(ex.map(one, todo), 1):
            if rec is None:
                counts["err"] += 1
                if counts["err"] <= 20:
                    print(f"  SIC {s}: {kind}", flush=True)
            else:
                cache[s] = rec
                counts[kind] += 1
            if i % 500 == 0:
                with lock:
                    SIC_F.write_text(json.dumps(cache))
                print(f"  ..sic {i:,}/{len(todo):,} (ok {counts['ok']:,} / "
                      f"no-cik {counts['nocik']:,} / err {counts['err']:,})",
                      flush=True)
    SIC_F.write_text(json.dumps(cache))
    fin = sum(1 for v in cache.values()
              if str(v.get("sic", "")).isdigit()
              and 6000 <= int(v["sic"]) <= 6999 and v["sic"] != "6770")
    spac = sum(1 for v in cache.values() if v.get("sic") == "6770")
    nosic = sum(1 for v in cache.values()
                if not str(v.get("sic", "")).isdigit())
    print(f"SIC cache -> {SIC_F.name}: {len(cache):,} symbols | "
          f"financial 6000-6999 (ex 6770) {fin:,} | blank-check 6770 "
          f"{spac:,} | no usable SIC {nosic:,} (not excluded on SIC "
          f"grounds) | fetch errors {counts['err']:,}")
    return cache


# ------------------------------------------------------- RESCREEN MODE
# HALAL-FIX EPOCH 2026-09-16. The four gate fixes (strict 10/10/20,
# SIC 6000-6999, TTM 5%, missing-row refusal) all NARROW the gate; the
# only loosening is the lifted blanket SPAC rulings. So a full 10,761
# name re-fetch is not needed to rebuild the list correctly: only names
# that can still be PASS, or that a lifted ruling could return to PASS,
# can change. Everything else is already FAIL/null under a strictly
# more permissive gate and stays that way.
#
# `--rescreen` re-runs the FIXED halal_check on exactly that candidate
# set, keeps every other cached verdict, backs the old files up and
# writes a flip report attributing each change to its cause.
def _legacy_probe(sym, t, mcap):
    """What the PRE-FIX gate's ratio legs would have said on the SAME
    fresh statements. Report-only: this exists so a flip can be
    attributed to the GATE CHANGE rather than to two weeks of price and
    filing drift, and it is never consulted by any verdict. Replicates
    the old arithmetic exactly -- absent row -> 0, column 0 only,
    interest / (revenue x 4), and the `or combined <= 20` legs."""
    import pandas as pd

    def gv(df, names):
        if df is None or getattr(df, "empty", True):
            return 0.0
        for n in names:
            if n in df.index:
                v = df.iloc[df.index.get_loc(n), 0]
                if not pd.isna(v):
                    return float(v)
        return 0.0
    try:
        bs, inc = t.quarterly_balance_sheet, t.quarterly_income_stmt
        if (bs is None or getattr(bs, "empty", True)) and \
                (inc is None or getattr(inc, "empty", True)):
            bs, inc = t.balance_sheet, t.income_stmt
    except Exception:
        return None
    debt = gv(bs, ["Total Debt"])
    cash = gv(bs, ["Cash Cash Equivalents And Short Term Investments"])
    rev = gv(inc, ["Total Revenue", "Operating Revenue"])
    inti = gv(inc, ["Interest Income", "Interest Income Non Operating",
                    "Net Interest Income"])
    if not mcap or mcap <= 0:
        return None
    loan, csh = debt / mcap * 100, cash / mcap * 100
    comb = loan + csh
    ann = rev * 4
    haram = (abs(inti) / ann * 100) if ann > 0 else 0.0
    return {
        "loan_pct": round(loan, 2), "cash_pct": round(csh, 2),
        "combined": round(comb, 2), "haram_pct": round(haram, 2),
        "ratios_ok": ((loan <= 10 or comb <= 20)
                      and (csh <= 10 or comb <= 20)
                      and comb <= 20 and haram < 5),
    }


CAUSES = [
    ("SIC-6xxx", ("FINANCIAL SECTOR (SIC",)),
    ("missing-row", ("unverified: missing",)),
    ("strict-10", ("LOAN>10", "CASH>10")),
    ("TTM-5%", ("HARAM>=5%",)),
    ("ruling", ("HARAM by user ruling", "external-screener ruling")),
    ("industry", ("HARAM INDUSTRY",)),
    ("combined>20", ("COMBINED>20",)),
    ("unverified-revenue-mix", ("unverified revenue mix",)),
    ("no-data", ("NO FUNDAMENTALS DATA", "MARKET CAP MISSING")),
]


def _cause(reason):
    for name, keys in CAUSES:
        if any(k in (reason or "") for k in keys):
            return name
    return "other"


def _restore_cause(rec):
    """Which rung of the interest-leg ladder brought a name back."""
    src = rec.get("haram_src") or "none"
    pre = ("plausibility-cap rescue + "
           if "intinc_implausible" in (rec.get("interest_flags") or [])
           else "")
    if src.startswith("upper-bound"):
        return f"{pre}upper-bound (nonoperating income)"
    if src.startswith("edgar-interest"):
        return f"{pre}EDGAR interest"
    if src == "yfinance":
        return f"{pre}vendor row (data drift, not the refinement)"
    return f"{pre}{src}"


def _rescreen_one(sym):
    import yfinance as yf
    time.sleep(PACE_SEC)
    try:
        t = yf.Ticker(sym)
        r = dt.halal_check(sym, t)
        rec = {k: r.get(k) for k in CACHED_KEYS}
        mc = (dt.load_rh_fundamentals().get(sym.upper()) or {}).get(
            "market_cap")
        if not mc:
            try:
                mc = (t.info or {}).get("marketCap")
            except Exception:
                mc = None
        rec["mcap"] = float(mc or 0) or None
        return sym, rec, _legacy_probe(sym, t, float(mc or 0))
    except Exception as e:
        return sym, {"halal": False, "source": "error",
                     "fail_reason": f"ERROR: {type(e).__name__}: {e}"}, None


# --------------------------------------------- INTEREST-LEG EPOCH (v2)
# The refinement of 2026-09-16 (same day, after the v1 rebuild) touches
# EXACTLY ONE leg -- the 5% interest test -- and only ever LOOSENS it,
# in two ways and no others:
#   * a vendor "interest income" row that fails an 8%/yr plausibility
#     cap on mean cash is discarded as a mis-tag instead of failing the
#     name (MRVL's $1.9bn divestiture gain);
#   * an untagged interest row can be PROVEN under 5% from EDGAR's
#     non-operating bucket instead of refusing the name.
# So the names whose verdict can move are: everything v1 refused on the
# interest leg (missing interest income, or HARAM>=5% under either
# gate's wording), plus every v1 PASS -- a PASS can flip the OTHER way
# if its vendor row is implausible and EDGAR then measures the leg over
# 5%, and re-running them is also how every armable name gets its
# `haram_src` recorded. Nothing else is re-fetched: a name refused for
# SIC 6xxx, a strict-10 leg, a missing debt/cash/revenue row or no
# fundamentals at all cannot be moved by a change to the interest leg,
# and re-screening it would cost two yfinance round-trips to confirm a
# verdict that is already correct.
INTEREST_KEYS = ("interest income", "HARAM>=5%")


def _interest_leg_candidates(done, ruled):
    return sorted({s for s, r in done.items() if r.get("halal")}
                  | {s for s, r in done.items()
                     if any(k in (r.get("fail_reason") or "")
                            for k in INTEREST_KEYS)}
                  | {s for s, r in done.items()
                     if r.get("source") in ("error", None)}
                  | (ruled & set(done)))


def cmd_rescreen(list_f=None, epoch="2026-09-16"):
    """Re-screen the names whose verdict the 2026-09-16 fixes can move.

    `list_f` parks the rebuilt armable list somewhere OTHER than
    data/halal_list.json. A live paper session reads halal_list.json
    every scan cycle, so a rebuild that lands mid-session would change
    the armable set under a running engine; --park-list writes
    halal_list.NEW.json instead and the swap happens after the close.

    `epoch` selects the candidate rule and the backup/report stamps:
    "2026-09-16" is the four-fix rebuild (v1, candidates = everything
    the PRE-FIX gate passed) and "interest-leg" is the same-day
    refinement (v2, candidates = whatever the interest leg can move --
    see _interest_leg_candidates)."""
    list_f = list_f or LIST_F
    done = json.loads(UNI_F.read_text())
    rulings = json.loads((ROOT / "data/halal_rulings.json").read_text())
    ruled = {s for s, r in rulings.items()
             if not s.startswith("_") and isinstance(r, dict)}
    # LIFTED rulings are the ONLY loosening in this epoch -- a name whose
    # FAIL ruling was withdrawn can legitimately return to PASS on its
    # data, so it has to be re-screened even though it is cached FAIL.
    ruled |= set(rulings.get("_lifted") or {})
    # PRE-FIX SNAPSHOT: flips are measured against the verdicts the OLD
    # gate left, not against whatever a half-finished pass wrote, so the
    # rescreen is re-runnable and its report always says the same thing.
    if epoch == "interest-leg":
        # v2 baseline is v1 -- the flips this pass reports are the ones
        # the INTEREST-LEG change caused, not the four-fix rebuild's,
        # which is already written up in the pre-2026-09-16 report.
        stamp, flips_f = "v1", \
            ROOT / "data/halal_flips_2026-09-16.interest-leg.json"
        baseline = dict(done)
        cands = _interest_leg_candidates(done, ruled)
        print(f"rescreen (interest-leg v2): {len(cands):,} candidates "
              f"({sum(1 for s in cands if done[s].get('halal')):,} v1 PASS, "
              f"{sum(1 for s in cands if any(k in (done[s].get('fail_reason') or '') for k in INTEREST_KEYS)):,} "
              f"refused on the interest leg, plus ruled/lifted names and "
              f"any crashed evaluation)", flush=True)
    else:
        stamp, flips_f = "pre-2026-09-16", \
            ROOT / "data/halal_flips_2026-09-16.json"
        baseline = done
        bak_u = UNI_F.with_name(f"{UNI_F.stem}.{stamp}{UNI_F.suffix}")
        if bak_u.exists():
            baseline = json.loads(bak_u.read_text())
        cands = sorted({s for s, r in done.items() if r.get("halal")}
                       | {s for s, r in baseline.items()
                          if r.get("halal") and s in done}
                       # a crashed evaluation is NOT a verdict (same rule
                       # as _retryable): always re-screened
                       | {s for s, r in done.items()
                          if r.get("source") in ("error", None)}
                       | (ruled & set(done)))
        print(f"rescreen: {len(cands):,} candidates "
              f"({sum(1 for s in cands if (baseline.get(s) or {}).get('halal')):,}"
              f" PASS under the pre-fix gate, plus ruled/lifted names and "
              f"any crashed evaluation)", flush=True)
    for f in (UNI_F, list_f if list_f.exists() else LIST_F):
        bak = f.with_name(f"{f.stem}.{stamp}{f.suffix}")
        if not bak.exists():
            bak.write_text(f.read_text())
            print(f"  backup {f.name} -> {bak.name}", flush=True)
    before = {s: dict((baseline.get(s) or done[s])) for s in cands}
    legacy = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=THREADS) as ex:
        for n, (sym, res, leg) in enumerate(ex.map(_rescreen_one, cands), 1):
            done[sym] = res
            if leg:
                legacy[sym] = leg
            if n % 50 == 0 or n == len(cands):
                UNI_F.write_text(json.dumps(done))
                el = time.time() - t0
                print(f"  [{n:,}/{len(cands):,}] still PASS: "
                      f"{sum(1 for s in cands[:n] if done[s].get('halal')):,}"
                      f" (eta {el/n*(len(cands)-n)/60:.0f} min)", flush=True)
    UNI_F.write_text(json.dumps(done))

    flips = {"to_fail": [], "to_pass": [], "by_cause": {}}
    for s in cands:
        was, now = before[s].get("halal"), done[s].get("halal")
        if was and not now:
            c = _cause(done[s].get("fail_reason"))
            leg = legacy.get(s) or {}
            # a leg the OLD gate would ALSO have failed on this same
            # fresh data is drift, not the gate change
            if c in ("strict-10", "TTM-5%", "combined>20") \
                    and leg and not leg.get("ratios_ok"):
                c = f"{c} (also fails old gate on today's data)"
            flips["to_fail"].append(
                {"symbol": s, "cause": c,
                 "was": {k: before[s].get(k) for k in
                         ("loan_pct", "cash_pct", "combined", "haram_pct")},
                 "now": {k: done[s].get(k) for k in
                         ("loan_pct", "cash_pct", "combined", "haram_pct")},
                 "legacy_on_fresh_data": leg,
                 "reason": done[s].get("fail_reason")})
            flips["by_cause"][c] = flips["by_cause"].get(c, 0) + 1
        elif now and not was:
            # RESTORED-BY-CAUSE (interest-leg epoch). Which rung of the
            # resolution ladder answered is the whole point of the
            # report: "restored" is not a result, "restored because
            # EDGAR tags the interest at 1.15% of revenue" is.
            rc = _restore_cause(done[s])
            flips["to_pass"].append(
                {"symbol": s, "was_reason": before[s].get("fail_reason"),
                 "cause": rc, "haram_src": done[s].get("haram_src"),
                 "interest_flags": done[s].get("interest_flags"),
                 "mcap": done[s].get("mcap"),
                 "now": {k: done[s].get(k) for k in
                         ("loan_pct", "cash_pct", "combined", "haram_pct")}})
            flips["by_cause"][f"RESTORED: {rc}"] = \
                flips["by_cause"].get(f"RESTORED: {rc}", 0) + 1
    # WHAT THE RULE STILL COSTS: every name still refused because the
    # interest leg could not be resolved AND could not be bounded,
    # largest first, so the price of "unverified is HARAM" is a list
    # and not an adjective.
    flips["still_missing_interest"] = sorted(
        ({"symbol": s, "mcap": done[s].get("mcap"),
          "haram_src": done[s].get("haram_src"),
          "interest_flags": done[s].get("interest_flags"),
          "reason": done[s].get("fail_reason")}
         for s in cands
         if not done[s].get("halal")
         and "interest income" in (done[s].get("fail_reason") or "")),
        key=lambda r: -(r["mcap"] or 0))
    flips["haram_src_of_armable"] = {}
    for s, r in done.items():
        if r.get("halal"):
            k = r.get("haram_src") or "none"
            flips["haram_src_of_armable"][k] = \
                flips["haram_src_of_armable"].get(k, 0) + 1
    halal = sorted(s for s, r in done.items() if r.get("halal"))
    list_f.write_text(json.dumps(
        {"updated": time.strftime("%Y-%m-%d"), "n": len(halal),
         "symbols": halal}))
    if list_f != LIST_F:
        print(f"  armable list PARKED at {list_f.name} -- "
              f"{LIST_F.name} left untouched for the live session",
              flush=True)
    flips_f.write_text(json.dumps(flips, indent=1))
    was_armable = sum(1 for r in before.values() if r.get("halal"))
    print(f"\nARMABLE {was_armable:,} -> {len(halal):,}")
    print(f"PASS -> FAIL: {len(flips['to_fail']):,}   "
          f"FAIL -> PASS: {len(flips['to_pass']):,}")
    for c, n in sorted(flips["by_cause"].items(), key=lambda x: -x[1]):
        print(f"  {c:<48} {n:,}")
    print(f"armable by interest-leg evidence: "
          f"{flips['haram_src_of_armable']}")
    print(f"still refused for a missing interest row: "
          f"{len(flips['still_missing_interest']):,}")
    for r in flips["still_missing_interest"][:20]:
        print(f"  {r['symbol']:<6} mcap "
              f"{(r['mcap'] or 0)/1e9:>8,.2f}bn  {(r['reason'] or '')[:90]}")
    print(f"flip report -> {flips_f.name}")


def main():
    if "--refresh" in sys.argv and UNI_F.exists():
        UNI_F.unlink()
    done = json.loads(UNI_F.read_text()) if UNI_F.exists() else {}
    # drop failed fetches so they are re-tried, keep real verdicts
    retry = [s for s, r in done.items() if _retryable(r)]
    for s_ in retry:
        del done[s_]
    if retry:
        print(f"{len(retry):,} previous no-data results queued for retry",
              flush=True)
    syms = [s for s in universe() if s not in done]
    print(f"{len(done):,} already screened, {len(syms):,} to do", flush=True)

    t0 = time.time()
    streak = [0]
    with ThreadPoolExecutor(max_workers=THREADS) as ex:
        for n, (sym, res) in enumerate(ex.map(screen_one, syms), 1):
            done[sym] = res
            streak[0] = streak[0] + 1 if _retryable(res) else 0
            if streak[0] >= BREAKER:
                # CANARY CHECK (2026-08-08 supervisor diagnosis): long
                # no-data runs are usually a legitimate desert of
                # ETFs/ETNs/preferreds, NOT rate limiting -- the
                # alphabetical queue is full of them. Only stand down if
                # a known-good symbol ALSO fails; otherwise keep moving.
                _, canary = screen_one("AAPL")
                if not _retryable(canary):
                    streak[0] = 0      # fundamentals flow fine: no limit
                else:
                    print(f"  RATE-LIMITED (canary AAPL failed after "
                          f"{BREAKER} no-data) -- sleeping "
                          f"{BREAKER_SLEEP//60} min", flush=True)
                    UNI_F.write_text(json.dumps(done))
                    time.sleep(BREAKER_SLEEP)
                    streak[0] = 0
            if n % 50 == 0 or n == len(syms):
                UNI_F.write_text(json.dumps(done))
                el = time.time() - t0
                eta = el / n * (len(syms) - n) / 60
                h = sum(1 for r in done.values() if r.get("halal"))
                print(f"  [{n:,}/{len(syms):,}] halal so far: {h:,} "
                      f"(eta {eta:.0f} min)", flush=True)
    UNI_F.write_text(json.dumps(done))

    halal = sorted(s for s, r in done.items() if r.get("halal"))
    needs = sorted(s for s, r in done.items()
                   if not r.get("halal")
                   and "NO FUNDAMENTALS DATA" in (r.get("fail_reason") or ""))
    LIST_F.write_text(json.dumps(
        {"updated": time.strftime("%Y-%m-%d"), "n": len(halal),
         "symbols": halal}))
    NEED_F.write_text(json.dumps(needs))
    by_src = {}
    for r in done.values():
        if r.get("halal"):
            by_src[r.get("source")] = by_src.get(r.get("source"), 0) + 1
    print(f"\nHALAL: {len(halal):,} of {len(done):,} "
          f"({100*len(halal)/max(len(done),1):.1f}%)  by source: {by_src}")
    print(f"UNVERIFIABLE (need RH mcap backfill): {len(needs):,} "
          f"-> data/needs_mcap.json")
    print(f"scanner list -> {LIST_F.name}", flush=True)


if __name__ == "__main__":
    if "--sic" in sys.argv:
        # SIC cache for the sector screen. Run this BEFORE a refresh or
        # a rescreen: halal_check reads data/sic_codes.json from disk
        # only and a name missing from it is simply not SIC-screened.
        cmd_sic()
    elif "--rescreen" in sys.argv:
        cmd_rescreen(LIST_F.with_name("halal_list.NEW.json")
                     if "--park-list" in sys.argv else None,
                     epoch=("interest-leg" if "--interest-leg" in sys.argv
                            else "2026-09-16"))
    else:
        main()
