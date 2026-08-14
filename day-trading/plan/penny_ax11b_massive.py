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
    permanently as empty (halal cache poisoning). Never bypass it."""
    from shared import massive
    try:
        return massive._get(url)
    except Exception:
        return {}


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
    f = SH / f"{sym}_{date[:7]}.json"
    if f.exists():
        return json.loads(f.read_text())
    d = api(f"https://api.polygon.io/v3/reference/tickers/{sym}?date={date}"
            f"&apiKey={KEY}")
    sh = (d.get("results") or {}).get("weighted_shares_outstanding") or \
        (d.get("results") or {}).get("share_class_shares_outstanding")
    f.write_text(json.dumps(sh))
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


def halal_pt(sym, date, prev_close):
    if not industry_clean(sym):
        return False
    sh = shares_asof(sym, date)
    if not sh or not prev_close:
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
        sel = None
        for q in qs:
            if (_filed_usable(q, date) if PT_FILED
                    else _avail(q["date"]) <= date):   # filed, not ended
                sel = q
        if sel:
            loan = sel["debt"] / mcap * 100
            cash = sel["cash"] / mcap * 100
            comb = loan + cash
            ann = sel["rev"] * 4
            haram = abs(sel["intinc"]) / ann * 100 if ann > 0 else 0
            return ((loan <= 10 or comb <= 20)
                    and (cash <= 10 or comb <= 20)
                    and comb <= 20 and haram < 5)
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
        return ((loan_ub <= 10 or comb_ub <= 20)
                and (cash_ub <= 10 or comb_ub <= 20) and comb_ub <= 20)
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
