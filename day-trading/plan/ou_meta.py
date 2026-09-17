"""OPEN-UNIVERSE (2026-09-17) step 0: ticker reference metadata.

USER DIRECTION (2026-09-17): "work on the agents but IGNORE whether the stock
is halal for now".  The edge search therefore runs on the FULL liquid US
universe and the halal list is applied post-hoc (plan/ou_halal.py).

Dropping the halal screen removes the only filter in this repo that also
happened to exclude non-operating listings, so the universe builder needs a
`type` for every symbol that clears the liquidity screen.  `data/hgr_ticker_
meta.json` (HALAL-GATE-REVIEW, 2026-09-17) already carries 9,466 rows in the
exact shape this needs; this module only TOPS IT UP with the symbols that the
$5M/$5 screen produces and that cache does not have.  It never rewrites a row
that is already there, so the halal line's file cannot drift underneath it.

Two passes per missing symbol:
  1. undated  /v3/reference/tickers/{SYM}
  2. on 404, dated  /v3/reference/tickers/{SYM}?date=2025-06-02  -- a symbol
     that has since been delisted or renamed has no undated row but does have
     an as-of row inside the study window.

Usage:  python plan/ou_meta.py            (reads plan/ou_out/screen_union.json)
"""
import json
import sys
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT.parent))
from shared.win_cred import get_secret                        # noqa: E402

KEY = get_secret("MASSIVE_KEY")
META = ROOT / "data" / "hgr_ticker_meta.json"
UNION = HERE / "ou_out" / "screen_union.json"
ASOF = "2025-06-02"
FIELDS = ("name", "market_cap", "type", "sic_code", "sic_description",
          "primary_exchange", "active", "list_date",
          "weighted_shares_outstanding", "share_class_shares_outstanding")

_lock = threading.Lock()


def _hit(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"__404__": True}
            if e.code == 429:
                import time
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except Exception:
            import time
            time.sleep(2)
    return None


def one(sym):
    d = _hit(f"https://api.polygon.io/v3/reference/tickers/{sym}?apiKey={KEY}")
    if d is not None and d.get("__404__"):
        d = _hit(f"https://api.polygon.io/v3/reference/tickers/{sym}"
                 f"?date={ASOF}&apiKey={KEY}")
        if d is not None and d.get("__404__"):
            return sym, {"status": "not-found"}
    if d is None:
        return sym, None
    res = d.get("results") or {}
    if not res:
        return sym, {"status": "empty"}
    out = {k: res.get(k) for k in FIELDS}
    out["status"] = "ok"
    return sym, out


def main():
    syms = json.loads(UNION.read_text())
    cache = json.loads(META.read_text()) if META.exists() else {}
    todo = sorted(s for s in syms if s not in cache)
    print(f"{len(syms):,} screened symbols, {len(cache):,} cached, "
          f"{len(todo):,} to fetch", flush=True)
    if not todo:
        return
    done = 0
    with ThreadPoolExecutor(max_workers=12) as ex:
        for sym, rec in ex.map(one, todo):
            done += 1
            if rec is not None:
                with _lock:
                    cache[sym] = rec
            if done % 200 == 0:
                print(f"  {done:,}/{len(todo):,}", flush=True)
    META.write_text(json.dumps(cache))
    print(f"wrote {META} ({len(cache):,} symbols)", flush=True)


if __name__ == "__main__":
    main()
