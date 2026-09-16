"""UNIVERSE+QUOTES (2026-09-16) -- constraint 1, stage 1:
widen the point-in-time fundamentals cache to EVERY liquid name.

The wide-net audit measured the funnel 4,575 liquid -> 728 labelled ->
61 halal-PASS per day and concluded that `data/pt_halal` COVERAGE, not
the halal rules, is what starves the cross-section. This module widens
the coverage. It does not touch the gate.

Four idempotent stages:

  extract   calls plan/edgar_backfill.cmd_extract() -- the EXISTING
            extractor, with its corrected tier-precedence debt logic,
            its `miss` flags, its filed dates and its honesty rules --
            on the union of the causal liquidity screen
            (plan/rl2/out/screen_syms.json, 6,371 symbols) and whatever
            was already extracted, so nothing already on disk is lost.
            Nothing in edgar_backfill.py is modified; it is imported.

  merge     calls plan/edgar_backfill.cmd_merge(), which writes
            data/pt_halal/{SYM}.json. The mandate for this line is
            "append NEW symbols only -- never modify existing files",
            and cmd_merge rewrites every file it touches, so this stage
            SHA-256s the whole directory first and RESTORES byte-for-byte
            any pre-existing file the merge changed. The restore count is
            reported; with an idempotent merge it is 0.

  shares    the one thing the existing caches cannot supply at the new
            width. `penny_ax11b_massive.halal_pt` needs a point-in-time
            share count (mcap = shares * prev_close) and refuses without
            one under HALAL_STRICT. `plan/rl2/cache/shares` covers 1,127
            symbols -- exactly the names that already carried a label --
            and widening it through Polygon would cost ~136,000 dated
            reference calls. companyfacts already contains the answer:
            the DEI cover-page share count, WITH its filing date. This
            stage reads it straight out of the same zip (multiprocess,
            no network) into a filed-dated series per symbol.

            Availability is by FILED date + 1 day, never by the as-of
            `end` date -- identical to `_filed_usable` in the gate. A
            cover-page number is knowable the day after the filing that
            carried it and not one day earlier.

  label     `industry_clean` under HALAL_STRICT refuses a symbol whose
            label is empty, and a pt_halal file created by cmd_merge has
            `industry: ""`. The label sources for a brand-new name are
            Polygon's reference `sic_description` / `name` (one call per
            symbol, no date). This stage caches them under
            plan/uq_out/ref/{SYM}.json and writes the description into
            the `industry` field of NEW pt_halal files only.

Usage:
  python plan/uq_edgar.py extract
  python plan/uq_edgar.py merge
  python plan/uq_edgar.py shares [--workers 8]
  python plan/uq_edgar.py label [--workers 16]
  python plan/uq_edgar.py sharescheck
"""
import gzip
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT.parent))

OUT = HERE / "uq_out"
OUT.mkdir(parents=True, exist_ok=True)
PT = ROOT / "data" / "pt_halal"
EDGAR = ROOT / "data" / "edgar"
ZIPF = EDGAR / "companyfacts.zip"
SYMF = OUT / "extract_symbols.json"
SHARES_F = OUT / "shares_pt.json.gz"
REF = OUT / "ref"

# DEI cover-page count first (it is the count the company itself puts on
# the front of the filing), then the us-gaap balance-sheet equivalents.
SHARE_SPECS = [("dei", "EntityCommonStockSharesOutstanding"),
               ("us-gaap", "CommonStockSharesOutstanding"),
               ("us-gaap", "CommonStockSharesIssued")]


def symbols():
    return json.loads(SYMF.read_text())


# ---------------------------------------------------------------- extract
def cmd_extract():
    import edgar_backfill as eb
    syms = symbols()
    print(f"extract: {len(syms):,} symbols (screen union + already "
          f"extracted)", flush=True)
    eb.cmd_extract(syms)


# ------------------------------------------------------------------ merge
def _hash_dir(d):
    out = {}
    for f in d.glob("*.json"):
        out[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def cmd_merge():
    import edgar_backfill as eb
    snap_dir = OUT / "pt_halal_pre"
    before = _hash_dir(PT)
    if not snap_dir.exists():
        shutil.copytree(PT, snap_dir)
    print(f"pt_halal before merge: {len(before):,} files "
          f"(snapshot {snap_dir})", flush=True)
    eb.cmd_merge()
    after = _hash_dir(PT)
    created = sorted(set(after) - set(before))
    changed = [n for n in before if after.get(n) != before[n]]
    restored = 0
    for n in changed:
        shutil.copyfile(snap_dir / n, PT / n)
        restored += 1
    assert _hash_dir(PT) == {**before, **{k: after[k] for k in created}}
    print(f"MERGE GUARD: {len(created):,} NEW pt_halal files kept, "
          f"{restored:,} pre-existing files restored byte-for-byte "
          f"(merge is {'idempotent' if not restored else 'NOT idempotent'})",
          flush=True)
    (OUT / "merge_report.json").write_text(json.dumps(
        {"before": len(before), "created": len(created),
         "restored": restored, "new_symbols": [n[:-5] for n in created]}))


# ----------------------------------------------------------------- shares
def _shares_one(args):
    """-> (sym, [[filed, val], ...]) read from companyfacts."""
    sym, cik = args
    try:
        with zipfile.ZipFile(ZIPF) as zf:
            facts = json.loads(zf.read(f"CIK{cik:010d}.json")).get("facts", {})
    except Exception:
        return sym, []
    # dei lives beside us-gaap at the top level of `facts`
    best = {}          # filed -> (end, val)  (latest as-of per filing)
    for ns, tag in SHARE_SPECS:
        node = ((facts.get(ns) or {}).get(tag) or {}).get("units", {})
        rows = node.get("shares") or []
        got = False
        for e in rows:
            end, val, filed = e.get("end"), e.get("val"), e.get("filed")
            if not end or not filed or not val or val <= 0:
                continue
            got = True
            cur = best.get(filed)
            if cur is None or end > cur[0]:
                best[filed] = (end, float(val))
        if got:
            break      # precedence, not a union
    return sym, [[f, best[f][1]] for f in sorted(best)]


def cmd_shares(workers=8):
    import edgar_backfill as eb
    cm = eb.cik_map()
    syms = symbols()
    todo = [(s, cm[s.upper()]) for s in syms if s.upper() in cm]
    print(f"shares: {len(todo):,}/{len(syms):,} symbols have a CIK",
          flush=True)
    from concurrent.futures import ProcessPoolExecutor
    out, n_empty = {}, 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, (sym, ser) in enumerate(ex.map(_shares_one, todo,
                                              chunksize=8), 1):
            if ser:
                out[sym] = ser
            else:
                n_empty += 1
            if i % 1000 == 0:
                print(f"  ..{i:,}/{len(todo):,} ({len(out):,} with a "
                      f"series)", flush=True)
    with gzip.open(SHARES_F, "wt") as f:
        json.dump(out, f)
    npts = sum(len(v) for v in out.values())
    print(f"SHARES: {len(out):,} symbols, {npts:,} filed share counts, "
          f"{n_empty:,} with none -> {SHARES_F}", flush=True)


def cmd_sharescheck():
    """EDGAR cover-page shares vs the Polygon counts already cached, on
    the dates Polygon was asked about. Both sides are on disk; this is a
    free honesty check on the substitution the `shares` stage makes."""
    import bisect
    with gzip.open(SHARES_F, "rt") as f:
        ed = json.load(f)
    cache = ROOT / "plan" / "rl2" / "cache" / "shares"
    rows, miss = [], 0
    for p in cache.glob("*.json"):
        sym, dt = p.stem.rsplit("_", 1)
        try:
            pv = json.loads(p.read_text())
        except Exception:
            continue
        if not pv:
            continue
        ser = ed.get(sym)
        if not ser:
            miss += 1
            continue
        i = bisect.bisect_right([r[0] for r in ser], dt)
        if i == 0:
            miss += 1
            continue
        rows.append((sym, dt, float(pv), ser[i - 1][1]))
    if not rows:
        print("no overlap")
        return
    import numpy as np
    pv = np.array([r[2] for r in rows])
    ev = np.array([r[3] for r in rows])
    rat = ev / pv
    q = np.percentile(rat, [1, 5, 25, 50, 75, 95, 99])
    print(f"SHARES CHECK: {len(rows):,} overlapping (symbol, date) pairs, "
          f"{miss:,} with no EDGAR series")
    print("  EDGAR/Polygon ratio  p1 %.3f  p5 %.3f  p25 %.3f  med %.3f  "
          "p75 %.3f  p95 %.3f  p99 %.3f" % tuple(q))
    for lo, hi in ((0.95, 1.05), (0.9, 1.1), (0.8, 1.25), (0.5, 2.0)):
        print(f"  within [{lo}, {hi}]: "
              f"{float(np.mean((rat >= lo) & (rat <= hi))):.3f}")
    (OUT / "shares_check.json").write_text(json.dumps(
        {"n": len(rows), "no_series": miss,
         "pct": dict(zip(["p1", "p5", "p25", "p50", "p75", "p95", "p99"],
                         [float(x) for x in q])),
         "within_5pct": float(np.mean((rat >= .95) & (rat <= 1.05))),
         "within_10pct": float(np.mean((rat >= .9) & (rat <= 1.1)))},
        indent=1))


# ------------------------------------------------------------------ label
def cmd_label(workers=16):
    """Polygon reference row (undated) for every symbol that has no
    usable industry label, cached to plan/uq_out/ref/{SYM}.json. Writes
    `industry` into NEW pt_halal files only (a file listed in
    merge_report.json); pre-existing files are never opened for writing.
    """
    import uq_massive as um
    REF.mkdir(parents=True, exist_ok=True)
    new = set(json.loads((OUT / "merge_report.json").read_text())
              ["new_symbols"])
    syms = [s for s in symbols() if s in new]
    todo = [s for s in syms if not (REF / f"{s}.json").exists()]
    print(f"label: {len(syms):,} new pt_halal symbols, "
          f"{len(todo):,} reference rows to fetch", flush=True)
    from concurrent.futures import ThreadPoolExecutor

    def one(s):
        try:
            r = um.ticker_reference(s)
        except Exception as e:
            return s, {"_err": f"{type(e).__name__}: {e}"}
        (REF / f"{s}.json").write_text(json.dumps(r))
        return s, r

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for s, _r in ex.map(one, todo):
            done += 1
            if done % 250 == 0:
                print(f"  ..{done:,}/{len(todo):,}", flush=True)
    n_set = n_blank = 0
    for s in syms:
        f = REF / f"{s}.json"
        if not f.exists():
            n_blank += 1
            continue
        r = json.loads(f.read_text())
        lab = (r.get("sic_description") or "").strip()
        ptf = PT / f"{s}.json"
        if not ptf.exists():
            continue
        st = json.loads(ptf.read_text())
        if st.get("industry"):
            continue
        if not lab:
            n_blank += 1
            continue
        st["industry"] = lab
        st["industry_src"] = "polygon:sic_description"
        ptf.write_text(json.dumps(st))
        n_set += 1
    print(f"LABEL: industry written into {n_set:,} NEW pt_halal files, "
          f"{n_blank:,} left blank (no SIC description)", flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "extract"
    w = int(a[a.index("--workers") + 1]) if "--workers" in a else None
    if cmd == "extract":
        cmd_extract()
    elif cmd == "merge":
        cmd_merge()
    elif cmd == "shares":
        cmd_shares(w or 8)
    elif cmd == "sharescheck":
        cmd_sharescheck()
    elif cmd == "label":
        cmd_label(w or 16)
    else:
        sys.exit(f"unknown command {cmd}")
