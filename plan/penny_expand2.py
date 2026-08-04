"""Float-limit relaxation variants (extends penny_expand_test.py).

  V5 no float limit   band $2-16, window 7-10AM
  V6 all relaxed      NO ceiling, NO float limit, window 7-16 full day

Everything else unchanged: halal, upward sectors, up>=10%, rvol>=5x,
ORB+dip entries, trail 20%/stop 5%, $15k/position, 10% bar-volume cap.
Symbols that previously failed the float gate get fresh halal checks
(lazy ordering meant halal was never computed for them).
"""

import importlib.util
import json
import sys
from datetime import time as dtime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("pennystocks",
                                               ROOT / "day-trading.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

sys.path.insert(0, str(ROOT / "plan"))
_espec = importlib.util.spec_from_file_location(
    "exp", ROOT / "plan" / "penny_expand_test.py")
exp = importlib.util.module_from_spec(_espec)
_espec.loader.exec_module(exp)
ytd = exp.ytd

CACHE = ROOT / "data" / "backtest60"


def filter_no_float(cands):
    """Halal + upward-sector only (float ignored). Fills missing halal."""
    cache_f = CACHE / "rules_ytd.json"
    verdicts = json.loads(cache_f.read_text())
    import yfinance as yf
    syms = sorted({c["symbol"] for c in cands})
    for n, sym in enumerate(syms):
        v = verdicts.get(sym)
        if v is None:
            v = {"float_ok": None, "halal_ok": None, "sector_raw": "",
                 "reason": ""}
            verdicts[sym] = v
        if v.get("halal_ok") is not None:
            continue
        sector_ok = any(w in v.get("sector_raw", "").lower()
                        for w in ytd.UPWARD_SECTOR_WORDS)
        if v.get("sector_raw") and not sector_ok:
            continue   # sector fails -> halal irrelevant
        try:
            t = yf.Ticker(sym)
            if not v.get("sector_raw"):
                info = t.info or {}
                v["sector_raw"] = (f"{info.get('sector', '')} / "
                                   f"{info.get('industry', '')}")
                if not any(w in v["sector_raw"].lower()
                           for w in ytd.UPWARD_SECTOR_WORDS):
                    continue
            h = ps.halal_check(sym, t)
            v["halal_ok"] = h["halal"]
            if not h["halal"]:
                v["reason"] = h["fail_reason"]
        except Exception as e:
            v["reason"] = f"error: {e}"
        if n % 20 == 0:
            cache_f.write_text(json.dumps(verdicts))
            print(f"  ..halal fill {n}/{len(syms)}", flush=True)
    cache_f.write_text(json.dumps(verdicts))

    out = []
    for c in cands:
        v = verdicts.get(c["symbol"], {})
        sector_ok = any(w in v.get("sector_raw", "").lower()
                        for w in ytd.UPWARD_SECTOR_WORDS)
        if sector_ok and v.get("halal_ok"):
            out.append(c)
    return out


def main():
    band_raw = json.loads((CACHE / "gappers_ytd.json").read_text())
    noceil_raw = json.loads((CACHE / "gappers_ytd_noceil.json").read_text())

    print("V5 candidate filtering (no float limit, band universe)...")
    v5 = filter_no_float(band_raw)
    print(f"  {len(v5)} stock-days ({len({c['symbol'] for c in v5})} symbols)")
    print("V6 candidate filtering (no float limit, no-ceiling universe)...")
    v6 = filter_no_float(noceil_raw)
    print(f"  {len(v6)} stock-days ({len({c['symbol'] for c in v6})} symbols)")

    print(f"\n$15,000/position, 10% bar-volume cap, one top gapper/day\n")
    print(f"{'VARIANT':<30} {'days':>6} {'total P&L':>12} {'avg $/day':>10} "
          f"{'win/day':>11} {'>=+$1k':>6} {'worst':>10}")
    print("-" * 94)
    exp.run_variant("V5 NO FLOAT, $2-16, 7-10AM", v5, dtime(10, 0), 16.0)
    exp.run_variant("V6 ALL RELAXED (ceil/float/day)", v6, dtime(16, 0), 1e9)


if __name__ == "__main__":
    main()
