"""HALAL-GATE-REVIEW (2026-09-17) -- Zoya / Musaffa public-verdict sweep.

USER RULING 2026-09-17: "For the missing statement, use the last
available statement or check the Zoya website. Do not just reject it."

Rung 2 of that ruling: a name the gate still cannot resolve from ANY
filed statement is looked up on the two professional screeners whose
public pages carry a verdict, and adopted under the standing Class-B
rule (SOURCES.md: "no financials findable at all -> the external
screener's FULL verdict is adopted whole").

Public pages only, no login, paced. Verdict text only -- the reason and
the percentages sit behind their accounts and are not taken.

  zoya.finance/stocks/<lowercase>   "<X> stock is Shariah-compliant" |
                                    "not Shariah-compliant" | "questionable"
  musaffa.com/stock/<UPPER>         "classified as HALAL|NOT HALAL|DOUBTFUL
                                     by Musaffa under AAOIFI"

Writes data/halal_external/screener_verdicts.2026-09-17.json (a NEW
file; the 2026-08-22 archive is never overwritten) and prints a summary.

Usage:
  python plan/hgr_screeners.py --syms A,B,C
  python plan/hgr_screeners.py --file data/hgr_unresolved.json
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/halal_external/screener_verdicts.2026-09-17.json"
OLD = ROOT / "data/halal_external/screener_verdicts.json"
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "stocks-automation halal-research "
                     "m.osama.elmoghany@gmail.com")}
# SOURCES.md paces the sweep at 1.6-2.4 s/request. MEASURED 2026-09-17:
# a Zoya page takes 22.9 s to render and a Musaffa page 10.6 s, so a
# serial sweep of 283 names is 2.7 HOURS and the pace constant never
# binds. Four workers per site instead: each site then sees roughly one
# request every 5-6 s, which is SLOWER than the documented pace, not
# faster -- the politeness budget is spent on latency, not on sleeping.
PACE = 0.0
WORKERS = 4


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as f:
        return f.status, f.read().decode("utf-8", "ignore")


def zoya(sym):
    try:
        code, h = _get(f"https://zoya.finance/stocks/{sym.lower()}")
    except Exception as e:
        return {"http": getattr(e, "code", None) or 0,
                "status": None, "err": type(e).__name__}
    low = h.lower()
    # ORDER MATTERS: "not shariah-compliant" contains "shariah-compliant"
    for needle, verdict in (("not shariah-compliant", "not Shariah-compliant"),
                            ("is questionable", "questionable"),
                            ("stock is questionable", "questionable"),
                            ("shariah-compliant", "Shariah-compliant")):
        if needle in low:
            return {"http": code, "status": verdict,
                    "fetched": time.strftime("%Y-%m-%d")}
    return {"http": code, "status": None, "fetched": time.strftime("%Y-%m-%d")}


_MUS = re.compile(r"classified as\s+([A-Za-z ]{3,12}?)\s+by\s+Musaffa", re.I)
_MUSAS = re.compile(r"As of\s+([A-Z][a-z]+\s+\d{4})", re.I)


def musaffa(sym):
    try:
        code, h = _get(f"https://musaffa.com/stock/{sym.upper()}")
    except Exception as e:
        return {"http": getattr(e, "code", None) or 0,
                "status": None, "err": type(e).__name__}
    m = _MUS.search(h)
    a = _MUSAS.search(h)
    st = None
    if m:
        v = m.group(1).strip().lower()
        st = {"halal": "halal", "not halal": "not halal",
              "doubtful": "doubtful"}.get(v, v)
    return {"http": code, "status": st,
            "asof": a.group(1) if a else None,
            "fetched": time.strftime("%Y-%m-%d")}


def main():
    syms = []
    for i, a in enumerate(sys.argv):
        if a == "--syms":
            syms = [s.strip().upper()
                    for s in sys.argv[i + 1].split(",") if s.strip()]
        if a == "--file":
            raw = json.loads(Path(sys.argv[i + 1]).read_text())
            syms = [s.upper() for s in
                    (raw if isinstance(raw, list) else raw.get("symbols", []))]
    if not syms:
        sys.exit("need --syms or --file")
    cache = json.loads(OUT.read_text()) if OUT.exists() else \
        {"built": time.strftime("%Y-%m-%d"), "zoya": {}, "musaffa": {}}
    todo = [s for s in syms if s not in cache["zoya"]
            or s not in cache["musaffa"]]
    print(f"{len(syms):,} symbols, {len(todo):,} to fetch "
          f"({len(syms)-len(todo):,} already in today's cache)", flush=True)
    from concurrent.futures import ThreadPoolExecutor

    def one(s):
        z = cache["zoya"].get(s) or zoya(s)
        m = cache["musaffa"].get(s) or musaffa(s)
        return s, z, m

    def _answer(rec):
        """A TRANSPORT failure is not a verdict and must never be cached:
        caching it would silently mark the name 'no coverage' forever --
        the same cache-poisoning rule cmd_sic already follows. http 404
        IS an answer (the screener does not cover the name)."""
        return bool(rec) and (rec.get("http") or 0) >= 200

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, (s, z, m) in enumerate(ex.map(one, todo), 1):
            if _answer(z):
                cache["zoya"][s] = z
            if _answer(m):
                cache["musaffa"][s] = m
            if i % 10 == 0:
                OUT.write_text(json.dumps(cache))
                print(f"  {i:,}/{len(todo):,}", flush=True)
    OUT.write_text(json.dumps(cache))
    zc = {}
    mc = {}
    for s in syms:
        zc[cache["zoya"].get(s, {}).get("status")] = \
            zc.get(cache["zoya"].get(s, {}).get("status"), 0) + 1
        mc[cache["musaffa"].get(s, {}).get("status")] = \
            mc.get(cache["musaffa"].get(s, {}).get("status"), 0) + 1
    print(f"\nzoya:    {zc}")
    print(f"musaffa: {mc}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
