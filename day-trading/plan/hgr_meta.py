"""HALAL-GATE-REVIEW (2026-09-17) -- read-only metadata fetch.

Pulls Polygon `/v3/reference/tickers/{sym}` for every symbol in
`data/halal_universe.json` and caches the four fields the review needs
that our own caches do not carry:

    market_cap   -- to rank removals by size (halal_universe.json only
                    cached `mcap` for the 909 names the 2026-09-16
                    interest-leg rescreen re-decided)
    type         -- CS / ADRC / ETF / FUND / UNIT / WARRANT ... the only
                    field in reach that says whether a listing is a
                    COMMON STOCK at all. `clean_ticker` in
                    build_halal_universe.py filters on ticker SHAPE
                    only, so the 10,761-name denominator silently
                    contains ETFs, closed-end funds and trusts.
    sic_code     -- independent cross-check on data/sic_codes.json
                    (which comes from EDGAR submissions)
    name         -- for eyeballing

Read-only: writes ONE new cache file, data/hgr_ticker_meta.json, and
touches nothing the gate reads.  Re-runnable; already-cached symbols are
skipped.

Usage:  python plan/hgr_meta.py [--extra SYM,SYM,...]
"""
import json
import sys
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
from shared.win_cred import get_secret          # noqa: E402

KEY = get_secret("MASSIVE_KEY")
UNI = ROOT / "data/halal_universe.json"
OUT = ROOT / "data/hgr_ticker_meta.json"
FIELDS = ("name", "market_cap", "type", "sic_code", "sic_description",
          "primary_exchange", "active", "list_date",
          "weighted_shares_outstanding", "share_class_shares_outstanding")

_lock = threading.Lock()


def one(sym):
    url = f"https://api.polygon.io/v3/reference/tickers/{sym}?apiKey={KEY}"
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            d = json.load(r)
    except Exception as e:
        code = getattr(e, "code", None)
        if code == 404:
            return sym, {"status": "not-found"}
        return sym, None                      # transport: retry next run
    res = d.get("results") or {}
    if not res:
        return sym, {"status": "empty"}
    out = {k: res.get(k) for k in FIELDS}
    out["status"] = "ok"
    return sym, out


def main():
    syms = set(json.loads(UNI.read_text()).keys())
    for a in sys.argv[1:]:
        if a.startswith("--extra"):
            syms |= {s.strip().upper()
                     for s in a.split("=", 1)[-1].split(",") if s.strip()}
    cache = json.loads(OUT.read_text()) if OUT.exists() else {}
    todo = sorted(s for s in syms if s not in cache)
    print(f"{len(syms):,} symbols, {len(cache):,} cached, "
          f"{len(todo):,} to fetch", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=12) as ex:
        for sym, rec in ex.map(one, todo):
            done += 1
            if rec is not None:
                with _lock:
                    cache[sym] = rec
            if done % 500 == 0:
                OUT.write_text(json.dumps(cache))
                print(f"  {done:,}/{len(todo):,}", flush=True)
    OUT.write_text(json.dumps(cache))
    print(f"wrote {OUT} ({len(cache):,} symbols)")


if __name__ == "__main__":
    main()
