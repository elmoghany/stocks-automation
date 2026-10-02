"""SWING-EARNINGS (2026-10-01) step 1: daily panel + point-in-time universe.

Reads every data/massive/gd/{D}.json.gz (regular-session o/h/l/c/v, split-
adjusted as fetched) and writes data/research_oct/se_panel.npz:
  dates (D,), syms (S,), o,h,l,c,v (D,S) float32 NaN-if-absent,
  liq (D,S) bool  -- PIT liquid universe on date D, from PRIOR sessions only:
      operating equity (Polygon type CS/ADRC, not SIC 6726; ou_lib.is_operating
      -- present-day reference metadata) AND prior-60-session (>=40 present)
      median dollar volume >= $5M AND median close >= $5.
  adv20 (D,S)  prior-20-session mean dollar volume (excl. D)
  sig20 (D,S)  prior-20-session stdev of close-to-close log returns (excl. D)
  ma20ok (D,)  SPY prior close > its prior-20-close mean (known before D open)
Only symbols that are liquid on at least one date are kept (plus SPY).
"""
import gzip
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ou_lib as OU                                           # noqa: E402

ROOT = HERE.parent
GD = ROOT / "data" / "massive" / "gd"
OUT = ROOT / "data" / "research_oct"


def main():
    files = sorted(GD.glob("*.json.gz"))
    dates, per = [], []
    for f in files:
        rows = json.loads(gzip.open(f, "rt").read())
        if len(rows) < 3000:
            print("skip thin", f.name, len(rows))
            continue
        dates.append(f.name[:10])
        per.append({x["T"]: (x.get("o"), x.get("h"), x.get("l"), x.get("c"), x.get("v"))
                    for x in rows if x.get("T")})
    allsyms = sorted(set().union(*[set(p) for p in per]))
    oper = [s for s in allsyms if OU.is_operating(s) or s == "SPY"]
    sidx = {s: i for i, s in enumerate(oper)}
    D, S = len(dates), len(oper)
    A = np.full((5, D, S), np.nan, np.float64)
    for i, p in enumerate(per):
        for s, x in p.items():
            j = sidx.get(s)
            if j is None:
                continue
            A[:, i, j] = [np.nan if y is None else y for y in x]
    o, h, l, c, v = A
    dv = c * v
    liq = np.zeros((D, S), bool)
    adv20 = np.full((D, S), np.nan)
    sig20 = np.full((D, S), np.nan)
    lr = np.full((D, S), np.nan)
    with np.errstate(all="ignore"):
        lr[1:] = np.log(c[1:] / c[:-1])
        for i in range(D):
            lo = max(0, i - 60)
            if i - lo >= 40:
                wdv, wpx = dv[lo:i], c[lo:i]
                n = np.sum(~np.isnan(wdv), axis=0)
                mdv = np.nanmedian(wdv, axis=0)
                mpx = np.nanmedian(wpx, axis=0)
                liq[i] = (n >= 40) & (mdv >= 5e6) & (mpx >= 5.0)
            lo20 = max(0, i - 20)
            if i - lo20 >= 10:
                adv20[i] = np.nanmean(dv[lo20:i], axis=0)
                sig20[i] = np.nanstd(lr[lo20 + 1:i], axis=0)
    spy = sidx["SPY"]
    liq[:, spy] = False
    keep = liq.any(axis=0)
    keep[spy] = True
    ks = np.flatnonzero(keep)
    syms = np.array(oper)[ks]
    sc = c[:, spy]
    ma20ok = np.zeros(D, bool)
    for i in range(21, D):
        ma20ok[i] = sc[i - 1] > np.mean(sc[i - 20:i])
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / "se_panel.npz", dates=np.array(dates), syms=syms,
                        o=o[:, ks].astype(np.float32), h=h[:, ks].astype(np.float32),
                        l=l[:, ks].astype(np.float32), c=c[:, ks].astype(np.float32),
                        v=v[:, ks].astype(np.float32), liq=liq[:, ks],
                        adv20=adv20[:, ks].astype(np.float32),
                        sig20=sig20[:, ks].astype(np.float32), ma20ok=ma20ok)
    print(f"dates {D} {dates[0]}..{dates[-1]}; operating {S}; kept {len(ks)}; "
          f"liquid/day median {int(np.median(liq.sum(1)[60:]))}")


if __name__ == "__main__":
    main()
