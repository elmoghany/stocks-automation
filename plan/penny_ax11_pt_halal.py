"""AX11: POINT-IN-TIME halal. Compliance measured with the market cap of
the TRADE DATE (shares x that day's prev close), not today's snapshot.
This is a correctness fix, not a relaxation: ratios are mcap-denominated
and prices moved enormously since. Sector filter dropped (AX13 proved it
inert). Everything else = live default (calm-gap, top-1 x $15k, 7-noon,
ORB+patterns, trail 20 / stop 8 / scale-out 1/3@+25%).

Balance-sheet items come from the nearest available quarterly statement
(yfinance holds ~5 quarters; older dates use the earliest available --
approximation noted). Industry screen unchanged. Statements cached per
symbol under data/pt_halal/.
"""

import importlib.util
import json
import sys
from datetime import time as dtime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("pennystocks",
                                               ROOT / "penny-stocks.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)
ps.SURGE_WINDOW_MIN = 50
ps.PRICE_MAX = float("inf")

M1 = ROOT / "data" / "massive" / "m1"
PT = ROOT / "data" / "pt_halal"
PT.mkdir(parents=True, exist_ok=True)
VER = json.loads((ROOT / "data/backtest60/rules_ytd.json").read_text())
HARAM = ps.HARAM_INDUSTRY_WORDS


def get(sym, date):
    f = M1 / f"{sym}_{date}.csv"
    if not f.exists() or f.read_text(errors="ignore").startswith("EMPTY"):
        return None
    df = pd.read_csv(f)
    df["begins_at"] = (pd.to_datetime(df["begins_at"], utc=True)
                       .dt.tz_convert(ps.ET))
    return df.set_index("begins_at").sort_index()


def statements(sym):
    """Cache quarterly debt/cash/revenue/interest series + shares + industry."""
    f = PT / f"{sym}.json"
    if f.exists():
        return json.loads(f.read_text())
    out = {"quarters": [], "shares": None, "industry": "", "err": ""}
    try:
        import yfinance as yf
        t = yf.Ticker(sym)
        info = t.info or {}
        out["shares"] = info.get("sharesOutstanding")
        out["industry"] = f"{info.get('sector','')} {info.get('industry','')}"
        bs = t.quarterly_balance_sheet
        inc = t.quarterly_income_stmt

        def val(df, names, col):
            for n in names:
                if df is not None and not df.empty and n in df.index:
                    v = df.loc[n].iloc[col]
                    if not pd.isna(v):
                        return float(v)
            return 0.0
        ncols = 0 if bs is None or bs.empty else len(bs.columns)
        for k in range(ncols):
            qdate = str(bs.columns[k].date())
            out["quarters"].append({
                "date": qdate,
                "debt": val(bs, ["Total Debt"], k),
                "cash": val(bs, ["Cash Cash Equivalents And Short Term Investments"], k),
                "rev": val(inc, ["Total Revenue", "Operating Revenue"], k)
                if inc is not None and not inc.empty and k < len(inc.columns) else 0.0,
                "intinc": val(inc, ["Interest Income",
                                    "Interest Income Non Operating",
                                    "Net Interest Income"], k)
                if inc is not None and not inc.empty and k < len(inc.columns) else 0.0,
            })
    except Exception as e:
        out["err"] = str(e)[:80]
    f.write_text(json.dumps(out))
    return out


def pt_halal(sym, date, prev_close):
    st = statements(sym)
    if not st["shares"] or not st["quarters"]:
        return None   # unknown -> fall back to static verdict
    if any(w in st["industry"].lower() for w in HARAM):
        return False
    mcap = st["shares"] * prev_close
    if mcap <= 0:
        return None
    # nearest quarter at-or-before date, else earliest available
    qs = sorted(st["quarters"], key=lambda q: q["date"])
    sel = None
    for q in qs:
        if q["date"] <= date:
            sel = q
    if sel is None:
        sel = qs[0]
    loan = sel["debt"] / mcap * 100
    cash = sel["cash"] / mcap * 100
    comb = loan + cash
    annual_rev = sel["rev"] * 4
    haram = (abs(sel["intinc"]) / annual_rev * 100) if annual_rev > 0 else 0
    return ((loan <= 10 or comb <= 20) and (cash <= 10 or comb <= 20)
            and comb <= 20 and haram < 5)


def halal_ok(sym, date, prev_close):
    pt = pt_halal(sym, date, prev_close)
    if pt is not None:
        return pt
    return bool(VER.get(sym, {}).get("halal_ok"))


def run(label):
    gap = json.loads((ROOT / f"data/massive/gappers_{label}.json").read_text())
    by_day = {}
    for c in gap:
        by_day.setdefault(c["date"], []).append(c)
    days = []
    monthly = {}
    checked = 0
    for date, cs in sorted(by_day.items()):
        picked = None
        for c in sorted(cs, key=lambda x: -x["gain_pct"])[:6]:
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
            checked += 1
            if not halal_ok(c["symbol"], date, c["prev_close"]):
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
            print(f"  ..{label} {len(days)} traded days, "
                  f"${sum(days):+,.0f}", flush=True)
    negm = sum(1 for v in monthly.values() if sum(v) < 0)
    tot = sum(days)
    print(f"AX11 pt-halal   {label:<6} {len(days):>4} {tot:>+12,.0f} "
          f"{tot / len(days) if days else 0:>+8,.0f} {negm:>4}/{len(monthly)}",
          flush=True)
    print("  monthly:", {m: round(sum(v)) for m, v in sorted(monthly.items())},
          flush=True)


if __name__ == "__main__":
    for label in ("year", "y2025"):
        run(label)
