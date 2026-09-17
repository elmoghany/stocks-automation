"""UNIVERSE+QUOTES (2026-09-16): the poison test for the LIMIT-FILL
pipeline.

WHAT THE FILL RULE IS ALLOWED TO SEE -- stated before the test, so the
test can be scored against it rather than around it.

  At decision instant t0 (the start of minute m+1) the strategy posts a
  buy limit at  L = mark(m) * (1 - k/10000).
    * mark(m) -- the last printed close at or before minute m -- and the
      notional cap volcap(m) -- 20% of the trailing 5 minutes of share
      volume -- are the ONLY inputs to the decision, and both are
      functions of 1-minute bars with index <= m. They must be
      BIT-IDENTICAL when every bar after m is replaced by garbage.
    * the 32 model features and the candidate gate `printed_m` likewise.
    * WHETHER the order fills is decided by 1-second prints with
      timestamp > t0. That is the tape answering an order that was
      already posted, not the model peeking, and it is the ONE thing the
      pipeline is allowed to read from after t0. The test therefore
      asserts the fill outcome MOVES when those prints are garbaged --
      a fill rule that did not move would not be reading the tape at all
      -- and DOES NOT MOVE when prints BEFORE t0 are garbaged.

  Note a real improvement over the baseline table while we are here: the
  baseline's notional is min($15,000, volcap * open(m+1)), which reads
  minute m+1 -- the fill. The limit pipeline's notional is
  min($15,000, volcap * L), which reads nothing after m. So the limit
  ticket's SIZE is causal where the market ticket's was not.

Usage: python plan/uq_poison.py [--days 10]
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))

import features as FT                                   # noqa: E402
import uq_econ as UE                                    # noqa: E402
import uq_fills as UF                                   # noqa: E402
import uq_sec1                                          # noqa: E402
import wn_table as WT                                   # noqa: E402

DAYS = HERE / "rl2" / "out" / "days"
OUT = HERE / "uq_out"
OFFS = [0.0, 10.0, 30.0]
CUTS = ("09:35", "10:30", "13:00", "15:00")


def _scan_from_rows(rows, lo_ms, hi_ms):
    ts, rm, cur = [], [], float("inf")
    for r in rows:
        t = r[0]
        if t < lo_ms or t >= hi_ms:
            continue
        lw = r[3]
        if lw is None:
            continue
        if lw < cur:
            cur = lw
            ts.append(t)
            rm.append(cur)
    if not ts:
        return None
    return np.asarray(ts, np.int64), np.asarray(rm, float)


def main(ndays=10, seed=11, per_day=60):
    prof = FT.fit_profile()
    daily = FT.Daily()
    sic2, earn = WT.load_sic2(), WT.load_earn()
    files = sorted(DAYS.glob("*.npz"))
    rng = np.random.default_rng(seed)
    pick = [files[i] for i in rng.choice(len(files),
                                         min(ndays * 6, len(files)),
                                         replace=False)]
    pick = [p for p in pick
            if uq_sec1.have(str(np.load(p, allow_pickle=False)["syms"][0]),
                            p.stem)][:ndays]
    if not pick:
        raise SystemExit("no sampled day has a 1-second tape yet")
    arr_chk = arr_mis = 0
    price_chk = price_mis = 0
    fill_moved = fill_tested = 0
    pre_chk = pre_mis = 0
    detail = []
    for p in pick:
        date = p.stem
        syms, pc, bars = FT.load_raw(p)
        z_clean = FT.compute_day(date, syms, pc, bars, prof, daily)
        b_clean = WT.day_block(date, z_clean, sic2, earn)
        t0_04 = UF.DayTape(date, need_tape=False).t0_04
        rows_cache = {}
        for cut in CUTS:
            ci = WT.DEC_ET.index(cut)
            ti = int(WT.DEC_T[ci])
            m = int(WT.STEPS[ti])
            o, h, lo, c, v = (a.copy() for a in bars)
            sl = slice(m + 1, None)
            shp = o[:, sl].shape
            g = rng.uniform(0.5, 500.0, size=shp)
            o[:, sl] = g
            h[:, sl] = g * rng.uniform(1.0, 1.5, size=shp)
            lo[:, sl] = g * rng.uniform(0.5, 1.0, size=shp)
            c[:, sl] = g * rng.uniform(0.7, 1.3, size=shp)
            v[:, sl] = rng.integers(1, 10 ** 7, size=shp)
            z_bad = FT.compute_day(date, syms, pc, (o, h, lo, c, v), prof,
                                   daily)
            b_bad = WT.day_block(date, z_bad, sic2, earn)
            keep = WT.STEPS[WT.DEC_T] <= m
            for k, a, b in (("F", b_clean["F"][keep], b_bad["F"][keep]),
                            ("printed_m", b_clean["printed_m"][keep],
                             b_bad["printed_m"][keep]),
                            ("mark", z_clean["mark"][:ti + 1],
                             z_bad["mark"][:ti + 1]),
                            ("volcap", z_clean["volcap"][:ti + 1],
                             z_bad["volcap"][:ti + 1])):
                aa = np.nan_to_num(np.asarray(a), nan=-9e9)
                bb = np.nan_to_num(np.asarray(b), nan=-9e9)
                arr_chk += 1
                if not np.array_equal(aa, bb):
                    arr_mis += 1
                    detail.append({"date": date, "cut": cut, "array": k,
                                   "n_diff": int((aa != bb).sum())})
            # ---- the POSTED ORDER itself: limit price and ticket size
            mk_c = z_clean["mark"][ti].astype(np.float64)
            mk_b = z_bad["mark"][ti].astype(np.float64)
            vc_c = z_clean["volcap"][ti].astype(np.float64)
            vc_b = z_bad["volcap"][ti].astype(np.float64)
            for k in OFFS:
                Lc = mk_c * (1 - k / 1e4)
                Lb = mk_b * (1 - k / 1e4)
                nc = np.minimum(UF.TICKET, vc_c * Lc)
                nb = np.minimum(UF.TICKET, vc_b * Lb)
                price_chk += 2
                if not np.array_equal(np.nan_to_num(Lc), np.nan_to_num(Lb)):
                    price_mis += 1
                    detail.append({"date": date, "cut": cut,
                                   "array": f"limit_price_k{k:.0f}"})
                if not np.array_equal(np.nan_to_num(nc), np.nan_to_num(nb)):
                    price_mis += 1
                    detail.append({"date": date, "cut": cut,
                                   "array": f"notional_k{k:.0f}"})
            # ---- the fill rule: must MOVE on post-t0 garbage, must NOT
            # ---- move on pre-t0 garbage
            me = min(m + 1, UF.NMIN - 1)
            lo_ms = t0_04 + me * 60_000
            hi_ms = lo_ms + 5 * 60_000
            ss = [s for s in b_clean["syms"] if uq_sec1.have(s, date)]
            ss = ss[:per_day]
            for s in ss:
                if s not in rows_cache:
                    rows_cache[s] = uq_sec1.load(s, date) or []
                rows = rows_cache[s]
                si = b_clean["syms"].index(s)
                ref = float(mk_c[si])
                if not np.isfinite(ref) or ref <= 0:
                    continue
                L = ref * (1 - 10.0 / 1e4)
                real = UE.fill_ms(_scan_from_rows(rows, lo_ms, hi_ms), L)
                # (i) garbage every print AFTER t0
                post = [[r[0], r[1], r[2],
                         (r[3] * 7.7 + 313.0) if r[3] is not None else None,
                         r[4], r[5], r[6]] if r[0] >= lo_ms else r
                        for r in rows]
                got = UE.fill_ms(_scan_from_rows(post, lo_ms, hi_ms), L)
                fill_tested += 1
                if (real is None) != (got is None) or real != got:
                    fill_moved += 1
                # (ii) garbage every print BEFORE t0 -- the fill must not
                # care, because the rule never looks there
                pre = [[r[0], r[1], r[2],
                        (r[3] * 3.1 + 77.0) if r[3] is not None else None,
                        r[4], r[5], r[6]] if r[0] < lo_ms else r
                       for r in rows]
                got2 = UE.fill_ms(_scan_from_rows(pre, lo_ms, hi_ms), L)
                pre_chk += 1
                if got2 != real:
                    pre_mis += 1
                    detail.append({"date": date, "cut": cut, "sym": s,
                                   "array": "fill_leaked_pre_t0"})
        print(f"  {date}: arrays {arr_chk}/{arr_mis} mism, "
              f"order {price_chk}/{price_mis} mism, fills moved "
              f"{fill_moved}/{fill_tested}, pre-t0 leaks {pre_mis}",
              flush=True)
    res = {"days": len(pick), "cuts": list(CUTS),
           "array_checks": arr_chk, "array_mismatches": arr_mis,
           "order_checks": price_chk, "order_mismatches": price_mis,
           "fill_tested": fill_tested, "fill_moved": fill_moved,
           "fill_moved_frac": round(fill_moved / max(fill_tested, 1), 4),
           "pre_t0_checks": pre_chk, "pre_t0_leaks": pre_mis,
           "detail": detail[:20],
           "PASS": bool(arr_mis == 0 and price_mis == 0 and pre_mis == 0
                        and fill_moved > 0.5 * fill_tested)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "poison.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "detail"},
                     indent=1))


if __name__ == "__main__":
    a = sys.argv
    main(int(a[a.index("--days") + 1]) if "--days" in a else 10)
