"""CATALYST-MINER (2026-09-16): EDGAR filings with ACCEPTANCE timestamps.

Source: https://data.sec.gov/submissions/CIK##########.json (free, no
key, User-Agent required, <= 10 req/s).  It lists every filing of the
issuer with `acceptanceDateTime` (UTC, to the second) and, for 8-Ks, the
`items` string ("1.01,2.03,9.01") -- so the item-level 8-K classes the
mandate names come straight from the SEC, no text parsing.  This is
strictly better than the daily-index form.idx, which carries only the
filing DATE.

Stage `filings`  -> data/filings_hist/{SYM}.json
    every filing with filingDate >= WIN_LO: accession, form, filed,
    accepted (UTC), items, reportDate, primaryDocument.  If the "recent"
    block does not reach back to WIN_LO the older paginated files are
    pulled too.  Symbols with no CIK in data/edgar/company_tickers.json
    are listed in _nocik.json (delisted / foreign / renamed).

Stage `form4`    -> data/filings_hist/form4/{SYM}.json
    for the WIDE universe only (the gapper pool is 94% non-halal and its
    Form 4 count is in the tens of thousands): every Form 4 / 4/A's raw
    ownership XML is fetched and its non-derivative transactions parsed
    (code P = open-market purchase, S = sale, A = grant, M = option
    exercise, F = tax withholding, ...) with A/D flag, shares, price and
    the reporting owner's relationship.  "Insider buy" = code P and
    acquired.  The Form 4's own acceptance time is the causal clock.

Resumable at the symbol level; errors go to _errors.json.

Usage:  python plan/cat_edgar.py --stage filings [--set wide|gap|all]
        python plan/cat_edgar.py --stage form4  [--set wide]
"""
import gzip
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cat_lib as C                                           # noqa: E402

H = {"User-Agent": C.SEC_UA, "Accept-Encoding": "gzip, deflate",
     "Host": "data.sec.gov"}
HW = {"User-Agent": C.SEC_UA, "Accept-Encoding": "gzip, deflate",
      "Host": "www.sec.gov"}
_LOCK = threading.Lock()
_NEXT = [0.0]
PACE = 0.14           # ~7 req/s across all threads (SEC cap is 10)


def _throttle():
    with _LOCK:
        now = time.monotonic()
        wait = _NEXT[0] - now
        _NEXT[0] = max(now, _NEXT[0]) + PACE
    if wait > 0:
        time.sleep(wait)


def _get(url, headers, tries=6):
    for a in range(tries):
        _throttle()
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=headers),
                                       timeout=60)
            b = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                b = gzip.decompress(b)
            return b
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (403, 429) or e.code >= 500:
                time.sleep(5 * (a + 1))
                continue
            raise
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(3)
    raise RuntimeError("edgar: retries exhausted " + url[:90])


# ------------------------------------------------------------ filings
def _rows(block, lo):
    out = []
    n = len(block["form"])
    for i in range(n):
        if block["filingDate"][i] < lo:
            continue
        out.append({"acc": block["accessionNumber"][i],
                    "form": block["form"][i],
                    "filed": block["filingDate"][i],
                    "accepted": block["acceptanceDateTime"][i],
                    "items": block.get("items", [""] * n)[i] or "",
                    "report": block.get("reportDate", [""] * n)[i] or "",
                    "doc": block.get("primaryDocument", [""] * n)[i] or ""})
    return out


def fetch_filings(sym, cik):
    f = C.FIL / f"{sym}.json"
    if f.exists():
        return sym, 0, "skip"
    b = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", H)
    if b is None:
        return sym, 0, "404"
    s = json.loads(b)
    rec = s["filings"]["recent"]
    rows = _rows(rec, C.WIN_LO)
    oldest = rec["filingDate"][-1] if rec["filingDate"] else "0000"
    if oldest > C.WIN_LO:
        for extra in s["filings"].get("files") or []:
            if extra.get("filingTo", "0000") < C.WIN_LO:
                continue
            bb = _get("https://data.sec.gov/submissions/" + extra["name"], H)
            if bb:
                rows += _rows(json.loads(bb), C.WIN_LO)
    rows.sort(key=lambda r: r["accepted"])
    C.write_json(f, {"sym": sym, "cik": cik, "name": s.get("name"),
                     "sic": s.get("sic"), "tickers": s.get("tickers"),
                     "exchanges": s.get("exchanges"),
                     "fetched_at": datetime.utcnow().isoformat() + "Z",
                     "recent_oldest": oldest, "n": len(rows),
                     "filings": rows})
    return sym, len(rows), "ok"


# ------------------------------------------------------------ form 4
_TXN = re.compile(r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>",
                  re.S)


def _val(tag, blob):
    m = re.search(rf"<{tag}>\s*(?:<value>)?\s*([^<]*?)\s*(?:</value>)?\s*</{tag}>",
                  blob, re.S)
    return (m.group(1).strip() if m else "")


def parse_form4(x):
    rel = {k: _val(k, x) for k in ("isDirector", "isOfficer",
                                   "isTenPercentOwner", "isOther")}
    owner = _val("rptOwnerName", x)
    txns = []
    for blob in _TXN.findall(x):
        try:
            sh = float(_val("transactionShares", blob) or 0)
        except ValueError:
            sh = 0.0
        try:
            px = float(_val("transactionPricePerShare", blob) or 0)
        except ValueError:
            px = 0.0
        txns.append({"code": _val("transactionCode", blob),
                     "ad": _val("transactionAcquiredDisposedCode", blob),
                     "shares": sh, "px": px,
                     "date": _val("transactionDate", blob)})
    return {"owner": owner, "rel": rel, "txns": txns}


def fetch_form4(sym):
    fo = C.FIL / "form4" / f"{sym}.json"
    if fo.exists():
        return sym, 0, "skip"
    fi = C.read_json(C.FIL / f"{sym}.json")
    if not fi:
        return sym, 0, "nofilings"
    cik = fi["cik"]
    out = {}
    part = C.FIL / "form4" / f"{sym}.part.json"
    out = C.read_json(part, {})
    f4 = [r for r in fi["filings"] if r["form"] in ("4", "4/A")]
    for k, r in enumerate(f4):
        if r["acc"] in out:
            continue
        acc = r["acc"].replace("-", "")
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/"
        doc = r["doc"].split("/")[-1]
        x = None
        if doc.endswith(".xml"):
            b = _get(base + doc, HW)
            x = b.decode("utf-8", "ignore") if b else None
        if x is None:
            b = _get(base, HW)
            if b:
                names = re.findall(r'href="[^"]*/([^"/]+?\.xml)"',
                                   b.decode("latin-1"))
                raw = [n for n in names if not n.startswith("xsl")]
                if raw:
                    bb = _get(base + raw[0], HW)
                    x = bb.decode("utf-8", "ignore") if bb else None
        rec = {"accepted": r["accepted"], "filed": r["filed"], "form": r["form"]}
        if x:
            rec.update(parse_form4(x))
        else:
            rec["missing"] = True
        out[r["acc"]] = rec
        if (k + 1) % 25 == 0:
            C.write_json(part, out)
    C.write_json(fo, out)
    if part.exists():
        part.unlink()
    return sym, len(out), "ok"


# ------------------------------------------------------------ driver
def main():
    a = sys.argv
    stage = a[a.index("--stage") + 1] if "--stage" in a else "filings"
    which = a[a.index("--set") + 1] if "--set" in a else (
        "all" if stage == "filings" else "wide")
    nth = int(a[a.index("--threads") + 1]) if "--threads" in a else 3
    syms = {"wide": C.wide_syms, "gap": C.gap_syms, "all": C.all_syms}[which]()
    errs = C.read_json(C.FIL / "_errors.json", {})
    t0 = time.time()
    if stage == "filings":
        cm = C.cik_map()
        nocik = sorted(s for s in syms if s not in cm)
        C.write_json(C.FIL / "_nocik.json", nocik)
        syms = [s for s in syms if s in cm]
        print(f"filings: {len(syms)} symbols with CIK, {len(nocik)} without",
              flush=True)
        jobs = [(fetch_filings, (s, cm[s])) for s in syms]
    else:
        (C.FIL / "form4").mkdir(exist_ok=True)
        print(f"form4: {len(syms)} symbols", flush=True)
        jobs = [(fetch_form4, (s,)) for s in syms]
    done = tot = 0
    with ThreadPoolExecutor(nth) as ex:
        futs = {ex.submit(fn, *args): args[0] for fn, args in jobs}
        for i, f in enumerate(as_completed(futs)):
            s = futs[f]
            try:
                sym, n, st = f.result()
                if st == "ok":
                    done += 1
                    tot += n
                elif st not in ("skip",):
                    errs[s] = st
                if st == "ok":
                    errs.pop(s, None)
            except Exception as e:
                errs[s] = str(e)[:200]
                print(f"  ERR {s}: {str(e)[:120]}", flush=True)
            if (i + 1) % 100 == 0 or stage == "form4":
                print(f"  [{i+1}/{len(jobs)}] {s} fetched={done} rows={tot} "
                      f"errs={len(errs)} {time.time()-t0:.0f}s", flush=True)
                C.write_json(C.FIL / "_errors.json", errs)
    C.write_json(C.FIL / "_errors.json", errs)
    print(f"{stage} done: {done} fetched, {tot} rows, {len(errs)} errors, "
          f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
