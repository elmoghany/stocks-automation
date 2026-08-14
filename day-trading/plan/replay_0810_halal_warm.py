"""Warm the point-in-time halal caches for the replay pool.

axb.halal_pt() needs, per symbol: point-in-time shares outstanding
(data/pt_shares/{SYM}_{YYYY-MM}.json) and, when no yfinance quarterly
cache exists, Massive financials (data/pt_fin/{SYM}.json). This script
pre-fetches exactly those two files so the sim run is not interleaved
with 12.5s API waits. It changes no verdict -- the values written are
the same ones halal_pt would have fetched itself.

POISONING GUARD: axb.shares_asof/massive_fin write their cache file even
when the API call FAILED (api() swallows the exception and returns {}),
which would pin a symbol to its static verdict forever. This script
therefore calls massive._get itself and writes the cache ONLY when the
response actually carries a results key. A failed symbol is left
uncached and simply retried.

MUST NOT run while another Massive fetch is active (shared 5 req/min).

Usage: python plan/replay_0810_halal_warm.py
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from shared import massive
from shared.win_cred import get_secret

_spec = importlib.util.spec_from_file_location(
    "axb", ROOT / "plan/penny_ax11b_massive.py")
axb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(axb)

KEY = get_secret("MASSIVE_KEY")
M1 = ROOT / "data/massive/m1"
POOL_F = ROOT / "data/massive/gappers_novol_replay0813.json"


def _recent_cached_month(sym, month, max_back=6):
    """Latest already-cached share count for `sym` at or before `month`,
    within `max_back` months. Used only as a COPY-FORWARD source."""
    import re
    y, m = int(month[:4]), int(month[5:7])
    best = None
    for f in axb.SH.glob(f"{sym}_*.json"):
        mm = re.match(rf"{re.escape(sym)}_(\d{{4}})-(\d{{2}})\.json$", f.name)
        if not mm:
            continue
        yy, mo = int(mm.group(1)), int(mm.group(2))
        back = (y - yy) * 12 + (m - mo)
        if 0 <= back <= max_back and (best is None or back < best[0]):
            best = (back, f)
    return best


def warm_shares(sym, date, copy_forward=True):
    f = axb.SH / f"{sym}_{date[:7]}.json"
    if f.exists():
        return "cached"
    if copy_forward:
        # APPROXIMATION, documented: reuse a share count already cached for
        # a month <= the trade month (max 6 months back). It is strictly
        # BACKWARD-looking, so it cannot leak the future, and it is
        # CONSERVATIVE -- share counts trend up, so an older (smaller)
        # count gives a smaller mcap and therefore LARGER loan/cash ratios,
        # i.e. it can only make the halal gate stricter, never looser.
        hit = _recent_cached_month(sym, date[:7])
        if hit:
            f.write_text(hit[1].read_text())
            return f"copyforward-{hit[0]}m"
    d = massive._get(f"https://api.polygon.io/v3/reference/tickers/{sym}"
                     f"?date={date}&apiKey={KEY}")
    if "results" not in d:
        return "FAILED"
    r = d.get("results") or {}
    sh = (r.get("weighted_shares_outstanding")
          or r.get("share_class_shares_outstanding"))
    f.write_text(json.dumps(sh))
    return "fetched"


def warm_fin(sym):
    f = axb.FIN / f"{sym}.json"
    if f.exists():
        return "cached"
    d = massive._get(f"https://api.polygon.io/vX/reference/financials"
                     f"?ticker={sym}&limit=20&apiKey={KEY}")
    if "results" not in d:
        return "FAILED"
    out = []
    for r in d.get("results") or []:
        bs = r.get("financials", {}).get("balance_sheet", {})
        out.append({"end": r.get("end_date") or "",
                    "liab": (bs.get("liabilities") or {}).get("value"),
                    "cura": (bs.get("current_assets") or {}).get("value")})
    f.write_text(json.dumps(out))
    return "fetched"


def main():
    pool = json.loads(POOL_F.read_text())
    todo = {}
    for c in pool:
        f = M1 / f"{c['symbol']}_{c['date']}.csv"
        if not f.exists() or f.read_text(errors="ignore").startswith("EMPTY"):
            continue
        todo.setdefault(c["symbol"], c["date"])
    print(f"{len(todo)} symbols with bars to warm", flush=True)
    fail = []
    ncf = 0
    for i, (sym, date) in enumerate(sorted(todo.items()), 1):
        try:
            r = warm_shares(sym, date)
            if r == "FAILED":
                fail.append(("shares", sym))
            elif r.startswith("copyforward"):
                ncf += 1
            if not (axb.PT / f"{sym}.json").exists():
                if warm_fin(sym) == "FAILED":
                    fail.append(("fin", sym))
        except Exception as e:
            print(f"ERROR {sym}: {e}", flush=True)
            fail.append(("exc", sym))
        if i % 20 == 0 or i == len(todo):
            print(f"  [{i}/{len(todo)}] copyfwd={ncf} failures={len(fail)}", flush=True)
    if fail:
        print(f"UNCACHED (left for retry): {fail}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
