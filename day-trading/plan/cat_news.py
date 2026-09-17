"""CATALYST-MINER (2026-09-16): Polygon /v2/reference/news corpus.

One JSON per symbol-month under data/news_hist/{SYM}/{YYYY-MM}.json
(an EMPTY list is written for a month with no article, so a symbol whose
_done.json exists has every month of the window on disk).  Resumable:
a symbol with _done.json is skipped.  Failures go to _errors.json and
the symbol is retried on the next run.

The endpoint is paged with `next_url`; the whole 2024-08 .. 2026-09
window is pulled in one paged pass per symbol (limit 1000/page), then
split by published month.  `ticker=SYM` matches every article that
lists SYM in `tickers`, including multi-ticker market round-ups; the
`n_tickers` field is kept so those can be down-weighted later.

This module owns its own HTTP wrapper (shared/massive.py is not
modified, per the mandate).  Pacing: a global 0.2 s between request
starts across NTHREADS workers -- the paid Starter tier has no
documented per-minute cap, and 429s are retried with back-off anyway.

Usage:  python plan/cat_news.py [--set wide|gap|all] [--threads 4]
"""
import json
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cat_lib as C                                           # noqa: E402
from shared.win_cred import get_secret                        # noqa: E402

BASE = "https://api.polygon.io/v2/reference/news"
KEY = get_secret("MASSIVE_KEY")
_LOCK = threading.Lock()
_NEXT = [0.0]
PACE = 0.2


def _throttle():
    with _LOCK:
        now = time.monotonic()
        wait = _NEXT[0] - now
        _NEXT[0] = max(now, _NEXT[0]) + PACE
    if wait > 0:
        time.sleep(wait)


def _get(url, tries=6):
    for a in range(tries):
        _throttle()
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(3 * (a + 1))
                continue
            raise
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(3)
    raise RuntimeError("news: retries exhausted " + url[:90])


def months(lo=C.WIN_LO, hi=C.WIN_HI):
    y, m = int(lo[:4]), int(lo[5:7])
    out = []
    while f"{y:04d}-{m:02d}" < hi[:7]:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


MONTHS = months()


def slim(a, sym):
    ins = None
    for i in a.get("insights") or []:
        if i.get("ticker") == sym:
            ins = i.get("sentiment")
    return {"id": a.get("id"), "ts": a.get("published_utc"),
            "pub": (a.get("publisher") or {}).get("name"),
            "title": a.get("title") or "",
            "desc": (a.get("description") or "")[:600],
            "n_tickers": len(a.get("tickers") or []),
            "kw": (a.get("keywords") or [])[:12],
            "sent": ins}


def fetch_symbol(sym):
    d = C.NEWS / sym
    if (d / "_done.json").exists():
        return sym, 0, "skip"
    q = urllib.parse.urlencode({
        "ticker": sym, "published_utc.gte": C.WIN_LO + "T00:00:00Z",
        "published_utc.lt": C.WIN_HI + "T00:00:00Z", "order": "asc",
        "limit": 1000, "apiKey": KEY})
    url = BASE + "?" + q
    arts, pages = [], 0
    while url and pages < 50:
        r = _get(url)
        arts += r.get("results") or []
        pages += 1
        url = r.get("next_url")
        if url:
            url += "&apiKey=" + KEY
    by_m = {m: [] for m in MONTHS}
    seen = set()
    for a in arts:
        if a.get("id") in seen:
            continue
        seen.add(a.get("id"))
        m = (a.get("published_utc") or "")[:7]
        if m in by_m:
            by_m[m].append(slim(a, sym))
    d.mkdir(parents=True, exist_ok=True)
    for m, lst in by_m.items():
        C.write_json(d / f"{m}.json", lst)
    C.write_json(d / "_done.json", {
        "sym": sym, "n": len(seen), "pages": pages,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "first": arts[0]["published_utc"] if arts else None,
        "last": arts[-1]["published_utc"] if arts else None})
    return sym, len(seen), "ok"


def main():
    a = sys.argv
    which = a[a.index("--set") + 1] if "--set" in a else "all"
    nth = int(a[a.index("--threads") + 1]) if "--threads" in a else 4
    syms = {"wide": C.wide_syms, "gap": C.gap_syms, "all": C.all_syms}[which]()
    print(f"news: {len(syms)} symbols, {len(MONTHS)} months, "
          f"{nth} threads", flush=True)
    errs = C.read_json(C.NEWS / "_errors.json", {})
    done = 0
    tot = 0
    t0 = time.time()
    with ThreadPoolExecutor(nth) as ex:
        futs = {ex.submit(fetch_symbol, s): s for s in syms}
        for i, f in enumerate(as_completed(futs)):
            s = futs[f]
            try:
                sym, n, st = f.result()
                if st == "ok":
                    done += 1
                    tot += n
                errs.pop(s, None)
            except Exception as e:
                errs[s] = str(e)[:200]
                print(f"  ERR {s}: {str(e)[:120]}", flush=True)
            if (i + 1) % 100 == 0:
                print(f"  [{i+1}/{len(syms)}] fetched={done} arts={tot} "
                      f"errs={len(errs)} {time.time()-t0:.0f}s", flush=True)
                C.write_json(C.NEWS / "_errors.json", errs)
    C.write_json(C.NEWS / "_errors.json", errs)
    print(f"news done: {done} fetched, {tot} articles, {len(errs)} errors, "
          f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
