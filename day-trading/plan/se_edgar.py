"""SWING-EARNINGS step 2: point-in-time earnings timestamps from EDGAR.

For every symbol in se_panel (PIT-liquid at least once), fetch
data.sec.gov/submissions/CIK##########.json (+ older pages back to
2024-06-01) and keep the 8-K / 8-K/A rows whose items include 2.02
(Results of Operations and Financial Condition) with the SEC acceptance
datetime (UTC, to the second).  The acceptance time is the causal clock:
the market knew the numbers no later than that.

CIK map = data/edgar/company_tickers.json (present-day tickers; renamed /
delisted symbols have no CIK -> no events -> listed in _nocik).
Output: data/research_oct/edgar_202.json  {sym: [[accepted_utc, form], ...]}
Resumable (flush every 200 symbols).  Uses cat_edgar's throttled getter
(~7 req/s, SEC cap 10).
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cat_edgar as E                                         # noqa: E402

E.PACE = 0.4          # 2.5 req/s: the box shares SEC's per-IP budget with other agents

ROOT = HERE.parent
OUT = ROOT / "data" / "research_oct"
F = OUT / "se_edgar_202.json"
LO = "2024-06-01"


def rows(block):
    out = []
    n = len(block["form"])
    items = block.get("items", [""] * n)
    for i in range(n):
        if block["filingDate"][i] < LO:
            continue
        fm = block["form"][i]
        if fm.startswith("8-K") and "2.02" in (items[i] or ""):
            out.append([block["acceptanceDateTime"][i], fm])
    return out


def fetch(sym, cik):
    b = E._get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", E.H)
    if b is None:
        return sym, None
    s = json.loads(b)
    rec = s["filings"]["recent"]
    r = rows(rec)
    oldest = rec["filingDate"][-1] if rec["filingDate"] else "0000"
    if oldest > LO:
        for extra in s["filings"].get("files") or []:
            if extra.get("filingTo", "0000") < LO:
                continue
            bb = E._get("https://data.sec.gov/submissions/" + extra["name"], E.H)
            if bb:
                r += rows(json.loads(bb))
    return sym, sorted(r)


def main():
    P = np.load(OUT / "se_panel.npz")
    syms = [s for s in P["syms"].tolist() if s != "SPY"]
    ct = json.loads((ROOT / "data" / "edgar" / "company_tickers.json").read_text())
    cmap = {}
    for x in (ct.values() if isinstance(ct, dict) else ct):
        cmap.setdefault(x["ticker"].upper().replace("-", "."), int(x["cik_str"]))
        cmap.setdefault(x["ticker"].upper(), int(x["cik_str"]))
    done = json.loads(F.read_text()) if F.exists() else {}
    done.pop("_nocik", None)
    # seed from the CATALYST-MINER cache (fetched 2026-09-17, same SEC source)
    fh = ROOT / "data" / "filings_hist"
    seeded = 0
    for s in syms:
        if s in done or not (fh / f"{s}.json").exists():
            continue
        x = json.loads((fh / f"{s}.json").read_text())
        done[s] = sorted([r["accepted"], r["form"]] for r in x.get("filings", [])
                         if r["form"].startswith("8-K") and "2.02" in (r.get("items") or "")
                         and r["filed"] >= LO)
        seeded += 1
    print("seeded from filings_hist", seeded, flush=True)
    F.write_text(json.dumps(done))
    todo, nocik = [], []
    for s in syms:
        if s in done:
            continue
        k = cmap.get(s) or cmap.get(s.replace(".", "-"))
        (todo.append((s, k)) if k else nocik.append(s))
    print(f"symbols {len(syms)}; done {len(done)}; todo {len(todo)}; no CIK {len(nocik)}",
          flush=True)
    n = 0
    with ThreadPoolExecutor(1) as ex:
        futs = [ex.submit(fetch, s, k) for s, k in todo]
        for fu in as_completed(futs):
            try:
                s, r = fu.result()
            except Exception as e:                            # noqa: BLE001
                print("ERR", e, flush=True)
                continue
            done[s] = r if r is not None else []
            n += 1
            if n % 50 == 0:
                F.write_text(json.dumps(done))
                print(f"  {n}/{len(todo)}", flush=True)
    done["_nocik"] = nocik
    F.write_text(json.dumps(done))
    nev = sum(len(v) for k, v in done.items() if not k.startswith("_"))
    print(f"DONE symbols {len(done) - 1}, 2.02 filings {nev}", flush=True)


if __name__ == "__main__":
    main()
