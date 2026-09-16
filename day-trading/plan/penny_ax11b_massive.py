"""AX11b: point-in-time halal with MASSIVE financials + point-in-time
shares. Compliance chain per (symbol, trade date):
  1. haram-industry screen (static sector_raw / yf)
  2. mcap_t = shares-as-of-date (Massive v3 tickers) x prev_close
  3. precise test via cached yfinance quarterlies (data/pt_halal) if the
     nearest quarter exists at-or-before the date
  4. else CONSERVATIVE BOUNDS via Massive financials (period end <= date):
     treat ALL liabilities as debt and ALL current assets as cash; pass
     only if even these upper bounds satisfy 10/10/20 -- never passes a
     stock the true data would fail
  5. else static verdict; else fail.
Everything else: live default (calm-gap top-8 walk, $15k, 7-noon,
trail 20 / stop 8 / scale-out 1/3@+25%). Both years.
"""

import importlib.util
import json
import sys
import urllib.request
from datetime import time as dtime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
_spec = importlib.util.spec_from_file_location("pennystocks",
                                               ROOT / "day-trading.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)
ps.SURGE_WINDOW_MIN = 50
ps.PRICE_MAX = float("inf")

from shared.win_cred import get_secret
KEY = get_secret("MASSIVE_KEY")
M1 = ROOT / "data" / "massive" / "m1"
PT = ROOT / "data" / "pt_halal"
FIN = ROOT / "data" / "pt_fin"
SH = ROOT / "data" / "pt_shares"
FIN.mkdir(exist_ok=True)
SH.mkdir(exist_ok=True)
VER = json.loads((ROOT / "data/backtest60/rules_ytd.json").read_text())
HARAM = ps.HARAM_INDUSTRY_WORDS


def api(url):
    """Throttled + retried via trading.massive._get. A raw urllib call
    here once bypassed the rate limiter, and a 429 could be cached
    permanently as empty (halal cache poisoning). Never bypass it.

    Return contract (2026-09-01): {} means TRANSPORT FAILURE (429s
    exhausted, timeout, DNS) and must never be cached by a caller; a
    404 is a real answer ("no reference row for this symbol/date") and
    comes back as a dict with results=None so callers can cache it."""
    from shared import massive
    import urllib.error
    try:
        return massive._get(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"status": "NOT_FOUND", "results": None}
        return {}
    except Exception:
        return {}


def _write_atomic(f, obj):
    """Parallel shards share these caches; never leave a torn file."""
    import os
    import time
    tmp = f.with_name(f"{f.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj))
    for i in range(6):
        try:
            os.replace(tmp, f)
            return
        except PermissionError:      # Windows: sibling has f open
            time.sleep(0.2 * (i + 1))
    try:
        tmp.unlink()                 # give up: sibling wrote the same value
    except OSError:
        pass


def get(sym, date):
    f = M1 / f"{sym}_{date}.csv"
    if not f.exists() or f.read_text(errors="ignore").startswith("EMPTY"):
        return None
    df = pd.read_csv(f)
    df["begins_at"] = (pd.to_datetime(df["begins_at"], utc=True)
                       .dt.tz_convert(ps.ET))
    return df.set_index("begins_at").sort_index()


def massive_fin(sym):
    f = FIN / f"{sym}.json"
    if f.exists():
        return json.loads(f.read_text())
    d = api(f"https://api.polygon.io/vX/reference/financials?ticker={sym}"
            f"&limit=20&apiKey={KEY}")
    out = []
    for r in d.get("results") or []:
        bs = r.get("financials", {}).get("balance_sheet", {})
        out.append({"end": r.get("end_date") or "",
                    "liab": (bs.get("liabilities") or {}).get("value"),
                    "cura": (bs.get("current_assets") or {}).get("value")})
    f.write_text(json.dumps(out))
    return out


def shares_asof(sym, date):
    """Shares outstanding as of `date` (Massive v3 tickers, ?date=).

    HALAL-LEAK EPOCH 2026-09-01 (audit): the cache was keyed by MONTH,
    so the first date queried in a month answered for every other date
    in it -- including EARLIER dates (a look-ahead when the first query
    happened to be late in the month), and a transport failure ({} from
    api()) was cached as null forever (761 of 14,634 files are null).
    Under HALAL_STRICT (the live-gate epoch every ladder run uses) the
    cache is keyed by the EXACT as-of date, {sym}_{date}.json; the old
    month files are left in place and never read by this path (nothing
    migrated). The legacy month key survives ONLY for the non-strict
    identity chain (S095/Z104 in idgate.py), so those gates stay EXACT
    by construction. In BOTH modes a transport failure is never cached.
    """
    if HALAL_STRICT:
        f = SH / f"{sym}_{date}.json"
    else:
        f = SH / f"{sym}_{date[:7]}.json"
    if f.exists():
        import time
        for i in range(4):
            try:
                return json.loads(f.read_text())
            except (PermissionError, json.JSONDecodeError):
                time.sleep(0.1 * (i + 1))   # sibling mid-replace (Windows)
    d = api(f"https://api.polygon.io/v3/reference/tickers/{sym}?date={date}"
            f"&apiKey={KEY}")
    if not d:
        return None              # transport failure: NOT cached, retried
    res = d.get("results") or {}
    sh = res.get("weighted_shares_outstanding") or \
        res.get("share_class_shares_outstanding")
    _write_atomic(f, sh)         # real answer (incl. 404 / no field) cached
    return sh


# GATE RECONCILIATION (2026-08-14). The replay of Paper Days 5-8 showed
# this gate and the LIVE gate are different functions in BOTH directions:
# halal_pt REFUSED LFST/FRMI/SLN/NESR (live passed them on real
# quarterlies) and PASSED CAVA/HYLN/HP/HPK/KOPN (live refuses them).
# So $665,667 was earned under a gate we do not trade. Three causes:
#   1. unknown industry -> ALLOW here, but "absence of evidence is not
#      compliance" live. This is why the CAVA/HYLN class passes.
#   2. substring matching here vs word-boundary live ("pub" in "public").
#   3. the conservative-bounds path below uses TOTAL LIABILITIES and
#      CURRENT ASSETS as proxies for debt and cash -- far stricter than
#      the real ratio, which is why the LFST/FRMI class is refused.
# HALAL_STRICT=1 switches this module to the live semantics. Default OFF
# so every stored result and identity gate reproduces untouched; adopt
# only after re-baselining the champion against it.
import os as _os
HALAL_STRICT = _os.environ.get("HALAL_STRICT") == "1"


def industry_clean(sym):
    sec = VER.get(sym, {}).get("sector_raw", "")
    ind = ""
    st_f = PT / f"{sym}.json"
    if st_f.exists():
        try:
            ind = json.loads(st_f.read_text()).get("industry", "") or ""
        except Exception:
            ind = ""
    label = f"{sec} {ind}".strip()
    if HALAL_STRICT:
        # live semantics: word-boundary match on the label, and an
        # unknown label REFUSES rather than allows.
        if not label:
            return False
        return not ps._kw_hits(ps.HARAM_PRIMARY_LABEL
                               + ps.HARAM_PRIMARY_ANY, label)
    if sec:
        return not any(w in sec.lower() for w in HARAM)
    if ind.strip():
        return not any(w in ind.lower() for w in HARAM)
    return True   # unknown industry -> allow (ratios still must pass)


# Filing lag (user 2026-08-07: "halal screen should come from last
# quarter reports"): a quarter ending Mar 31 is not PUBLIC until its
# 10-Q is filed, ~40-45 days later. 0 = legacy behaviour (select by
# period end -- peeks ~45 days into unfiled statements). 45 = the
# SEC 10-Q deadline for non-accelerated filers, our conservative
# stand-in since the caches don't store true filing dates.
FILING_LAG_DAYS = 0


def _avail(period_end):
    """Date a report becomes usable: period end + filing lag."""
    if not FILING_LAG_DAYS:
        return period_end
    from datetime import date as _d, timedelta as _td
    try:
        return (_d.fromisoformat(period_end[:10])
                + _td(days=FILING_LAG_DAYS)).isoformat()
    except ValueError:
        return "9999-12-31"      # unparseable date -> never usable


# PT_FILED=1 (2026-08-14, EDGAR backfill): prefer the TRUE 10-Q/10-K
# filing date stored by plan/edgar_backfill.py over the flat _avail
# lag, and see the EDGAR-only quarters stored under "quarters_edgar"
# (a side key precisely so this flag-OFF module can never read them --
# S095/Z104 identity holds by construction, not by hope). A filed
# report counts as usable the day AFTER filing: companyfacts carries
# only the filing DATE, and most acceptances land after the close, so
# same-day use at a 7AM scan would be a leak. DEFAULT OFF: with the
# flag unset the selection below reads only q["date"] via _avail,
# byte-identical to the pre-backfill behaviour.
PT_FILED = _os.environ.get("PT_FILED") == "1"


def _filed_usable(q, date):
    """PT_FILED availability: real filed date + 1 day when present,
    else the legacy _avail lag on the period end."""
    f = q.get("filed")
    if not f:
        return _avail(q["date"]) <= date
    from datetime import date as _d, timedelta as _td
    try:
        return (_d.fromisoformat(f[:10]) + _td(days=1)).isoformat() <= date
    except ValueError:
        return False             # unparseable filed date -> never usable


def sector_clean(sym):
    """SIC 6000-6999 sector screen (user decision 2026-09-16, the same
    rule the live gate runs in day-trading.py::_sic_financial_fail).

    Banks, lenders, insurers, asset managers, brokers, exchanges, REITs
    and funds are a hard FAIL; SIC 6770 blank checks (SPACs) are
    deliberately EXEMPT from the class rule and judged on their data. A
    quirk-coded operating company is restored only by an explicit PASS
    ruling with a basis. A symbol with no SIC in data/sic_codes.json is
    not excluded here -- the keyword screen and the ratios still run.

    Present-day classification applied to a point-in-time decision, like
    the industry label above it: a company's SIC essentially never moves,
    and the alternative (no sector screen at all in the backtest) is the
    gate the audit found 213 financial names sitting inside."""
    fail, sic, _desc = ps._sic_financial_fail(sym)
    if not fail:
        return True
    r = ps._halal_ruling(sym)
    return bool(isinstance(r, dict) and r.get("verdict") == "PASS"
                and str(r.get("basis") or "").strip())


def _q_miss(q):
    """Which statement rows a cached quarter cannot vouch for.

    HALAL-FIX EPOCH 2026-09-16 (user decision 4: "a missing statement
    row never reads as 0"). EDGAR-extracted quarters carry an explicit
    `miss` list naming every line the filing did not tag
    (plan/edgar_backfill.py). Legacy yfinance-cached quarters predate
    the flag and were written under the same absent-row-reads-as-0 bug
    the live gate had, so for those an exact 0.0 is read as UNVERIFIED:
    the conservative direction, and only 648 of 34,203 cached quarters
    are legacy."""
    if "miss" in q:
        return [f for f in q["miss"] if f in ("debt", "cash", "rev",
                                              "intinc")]
    return [k for k in ("debt", "cash", "rev", "intinc") if not q.get(k)]


def _qspan(a, b):
    from datetime import date as _d
    try:
        return abs((_d.fromisoformat(b[:10]) - _d.fromisoformat(a[:10])).days)
    except ValueError:
        return 0


def _ttm_pt(usable, maxq=4):
    """(revenue, interest, n_quarters, quarters) over the last <= `maxq`
    NON-OVERLAPPING filed quarters ending at usable[-1] -- the
    period-matched 5% test (user decision 3).

    The pre-fix line was `ann = sel["rev"] * 4` against ONE quarter of
    interest income, i.e. a 20% threshold wearing a 5% label. Summing
    both sides over the identical quarters is correct for any window
    length, so a name with only one or two filed quarters is still
    measured honestly rather than annualized by guesswork. The window
    stops at the first earlier quarter that cannot vouch for its
    revenue or interest rows; it never silently includes a zero.
    Quarters whose period ends are less than 45 days apart are the
    yfinance/EDGAR duplicate of one period and are skipped.

    INTEREST-LEG REFINEMENT (2026-09-16): the window is now defined by
    REVENUE ALONE, which is what the live gate has always done. It used
    to stop at the first quarter missing revenue OR interest, so an
    untagged interest line silently SHORTENED the window -- and
    17,718 of the 33,555 cached quarters carry no interest tag, because
    most filers never tag an immaterial one. Interest coverage is not a
    window question; it is resolved over the finished window by
    `_interest_leg_pt`, which can also prove the leg from the
    non-operating bound. The picked quarters are returned so that
    resolver sees exactly the span the revenue side used."""
    picked, last = [], None
    for q in reversed(usable):
        if last is not None and _qspan(q["date"], last) < 45:
            continue
        if picked and ("rev" in _q_miss(q)):
            break                    # window stops, what we have stands
        picked.append(q)
        last = q["date"]
        if len(picked) >= maxq:
            break
    return (sum(q["rev"] for q in picked),
            sum(q["intinc"] for q in picked), len(picked), picked)


# 8%/yr is the plausibility cap on what cash can earn -- see the long
# note at day-trading.py::_edgar_flows. Same constant, same doctrine,
# deliberately duplicated rather than imported: `ps` is the scanner
# module, not day-trading.py, and this module must not grow a dependency
# on the live engine's import graph.
INTINC_MAX_YIELD = 0.08


def _interest_leg_pt(picked, ttm_rev):
    """(haram_pct, source) for the 5% leg, or (None, None) = unverified.

    The same four-rung ladder the live gate runs (defects A and B of the
    2026-09-16 rebuild, documented at day-trading.py::_edgar_flows):

      1. the quarter's own `intinc`, IF every picked quarter tags it AND
         the TTM sum survives the 8%/yr plausibility cap on mean cash.
         A row that claims a yield no cash account earns is a MIS-TAG;
         it is discarded, never used to FAIL the name.
      2. `intinc_edgar` -- EDGAR's own reading under the five-tag
         precedence, attached to every merged quarter by
         plan/edgar_backfill.py.
      3. `nonop` -- TTM |non-operating income| / TTM revenue. Interest
         on cash is a SUBSET of non-operating income, so a bucket under
         5% PROVES the interest inside it is under 5%. A bound at or
         over 5% proves nothing.
      4. nothing resolved -> unverified -> the caller refuses."""
    if not picked or not ttm_rev or ttm_rev <= 0:
        return None, None
    n = len(picked)
    base = sum(abs(q.get("cash") or 0.0) for q in picked) / n
    cap = INTINC_MAX_YIELD * base * (n / 4.0)
    if not any("intinc" in _q_miss(q) for q in picked):
        v = sum(q["intinc"] for q in picked)
        pct = abs(v) / ttm_rev * 100
        # the cap fires only where it is NEEDED -- see the long note at
        # the same branch in day-trading.py::halal_check. It catches
        # OVER-statements by construction, so a row that is implausible
        # AND already under 5% is a conservative over-reading of a leg
        # that is clear either way; discarding it would refuse a name
        # that is provably clear.
        if base <= 0 or abs(v) <= cap:
            return pct, "filed"
        if pct < 5:
            return pct, "filed (over the plausibility cap, kept)"
    if all(q.get("intinc_edgar") is not None for q in picked):
        v = sum(q["intinc_edgar"] for q in picked)
        return abs(v) / ttm_rev * 100, "edgar-interest"
    if all(q.get("nonop") is not None for q in picked):
        bp = abs(sum(q["nonop"] for q in picked)) / ttm_rev * 100
        if bp < 5:
            return bp, "upper-bound"
    return None, None


def halal_pt(sym, date, prev_close):
    """Point-in-time halal gate for the backtest.

    HALAL-FIX EPOCH 2026-09-16 -- the same four user decisions the live
    gate took, so the two gates stop disagreeing on doctrine:
      1. STRICT 10/10/20: loan <= 10 AND cash <= 10 AND combined <= 20.
         The old `(loan <= 10 or comb <= 20)` legs were unreachable.
      2. SIC 6000-6999 is a hard FAIL (sector_clean), 6770 excepted.
      3. The 5% test is TTM interest / TTM revenue over the same
         quarters (_ttm_pt), not one quarter over four.
      4. A missing statement row is never 0 (_q_miss) -- refuse.
    The conservative-bounds path below is unchanged and still stricter
    than all of this; it is reached only with HALAL_STRICT off.

    INTEREST-LEG REFINEMENT (2026-09-16, same day): decision 4 keeps
    refusing a missing debt/cash/revenue row, but the INTEREST row now
    goes through the four-rung ladder in `_interest_leg_pt` -- vendor
    row under an 8%/yr plausibility cap, then EDGAR's own tagged
    interest, then the proven non-operating upper bound, then refuse.
    Same semantics as the live gate, on the same doctrine."""
    if not industry_clean(sym):
        return False
    if not sector_clean(sym):
        return False
    sh = shares_asof(sym, date)
    if not sh or not prev_close:
        # HALAL-LEAK EPOCH 2026-09-01: this fallback to the STATIC
        # present-day verdict (rules_ytd.json) fired BEFORE the strict
        # refusal below whenever shares/prev_close were missing (~55%
        # of share lookups per the audit) -- a present-day answer to a
        # point-in-time question. Live's rule is "missing data is a
        # FAIL", so under HALAL_STRICT refuse here too.
        if HALAL_STRICT:
            return False
        return bool(VER.get(sym, {}).get("halal_ok"))
    mcap = sh * prev_close
    # precise (yf quarterlies cache)
    st_f = PT / f"{sym}.json"
    if st_f.exists():
        st = json.loads(st_f.read_text())
        qs = sorted(st.get("quarters", []), key=lambda q: q["date"])
        if PT_FILED:
            # EDGAR-only quarters live under "quarters_edgar" so that
            # the default-off reader above can never select them.
            seen = {q["date"] for q in qs}
            qs = sorted(qs + [q for q in st.get("quarters_edgar", [])
                              if q["date"] not in seen],
                        key=lambda q: q["date"])
        usable = [q for q in qs
                  if (_filed_usable(q, date) if PT_FILED
                      else _avail(q["date"]) <= date)]  # filed, not ended
        sel = usable[-1] if usable else None
        if sel:
            # INTEREST-LEG REFINEMENT (2026-09-16): a missing debt, cash
            # or revenue row still refuses on the spot, but a missing
            # INTEREST row no longer does -- it is resolved (or proven
            # under 5% from the non-operating bound) over the whole
            # window below. Untagged interest is the single commonest
            # gap in the cache and "missing" is not "unverifiable" when
            # a proven upper bound exists.
            if {"debt", "cash", "rev"} & set(_q_miss(sel)):
                return False          # unverified: missing statement row
            loan = sel["debt"] / mcap * 100
            cash = sel["cash"] / mcap * 100
            comb = loan + cash
            rev, _intinc, _n, picked = _ttm_pt(usable)
            if rev <= 0:
                return False          # no verifiable revenue -> no 5% test
            haram, _src = _interest_leg_pt(picked, rev)
            if haram is None:
                return False          # interest leg unverified -> refuse
            return (loan <= 10 and cash <= 10 and comb <= 20 and haram < 5)
    if HALAL_STRICT:
        # No FILED quarterly available point-in-time => we cannot verify.
        # The bounds path below substitutes total liabilities for debt
        # and current assets for cash, which is not the test live runs --
        # it refused LFST/FRMI/SLN/NESR that live passed on real
        # statements. Live's rule is "missing data is a FAIL, never a
        # pass", so refuse rather than approximate.
        return False
    # conservative bounds (Massive financials)
    fins = massive_fin(sym)
    sel = None
    for r in sorted(fins, key=lambda x: x["end"]):
        if r["end"] and _avail(r["end"]) <= date:
            sel = r
    if sel and sel["liab"] is not None and sel["cura"] is not None:
        loan_ub = sel["liab"] / mcap * 100
        cash_ub = sel["cura"] / mcap * 100
        comb_ub = loan_ub + cash_ub
        return (loan_ub <= 10 and cash_ub <= 10 and comb_ub <= 20)
    return bool(VER.get(sym, {}).get("halal_ok"))


def run(label):
    gap = json.loads((ROOT / f"data/massive/gappers_{label}.json").read_text())
    by_day = {}
    for c in gap:
        by_day.setdefault(c["date"], []).append(c)
    days = []
    monthly = {}
    for date, cs in sorted(by_day.items()):
        picked = None
        for c in sorted(cs, key=lambda x: -x["gain_pct"])[:8]:
            df = get(c["symbol"], date)
            if df is None:
                continue
            w = df[(df.index.time >= dtime(7, 0))
                   & (df.index.time < dtime(12, 0))]
            if len(w) < 20:
                continue
            g7 = ((float(w["Open"].iloc[0]) / c["prev_close"] - 1) * 100
                  if c["prev_close"] else 999)
            if g7 > 20:
                continue
            if not halal_pt(c["symbol"], date, c["prev_close"]):
                continue
            picked = (c, w)
            break
        if picked is None:
            continue
        c, w = picked
        tr = ps.simulate_trades(w, verbose=False, buy_set=None,
                                vol_confirm=False, trail_pct=20, stop_pct=8,
                                prev_close=c["prev_close"], budget=15000,
                                orb=True, orb_bars=15, max_vol_frac=0.10,
                                vol_frac_window=5, scale_out_at=25.0)
        if not tr:
            continue
        dp = sum(x["pnl"] for x in tr)
        days.append(dp)
        monthly.setdefault(date[:7], []).append(dp)
        if len(days) % 40 == 0:
            print(f"  ..{label} {len(days)}d ${sum(days):+,.0f}", flush=True)
    negm = sum(1 for v in monthly.values() if sum(v) < 0)
    tot = sum(days)
    print(f"AX11b massive-pt {label:<6} {len(days):>4} {tot:>+12,.0f} "
          f"{tot / len(days) if days else 0:>+8,.0f} {negm:>3}/{len(monthly)}",
          flush=True)
    print("  monthly:", {m: round(sum(v)) for m, v in sorted(monthly.items())},
          flush=True)


if __name__ == "__main__":
    for label in ("year", "y2025"):
        run(label)
