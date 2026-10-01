"""LEGACY-8: time of day & hold length on HONEST old-champion trades + the
post-cross intraday return profile of gappers.

Read-only. Sources:
  data/massive/rotation_trades_{C37F,HOLD1}_hf3.json  (authoritative engine,
      post-2026-09-16 harness: RS_CROSS/RS_DEFER, hygiene, gap-through fills)
  plan/pa_out/cp_r4_legs.json  (cp_sim R4 = coil rank + no stop, and 30
      random-rank seeds on the same machinery; causal universe, honest fills)
  data/massive/cp_panel/*.npz  (04:00-16:00 minute grid; via plan/cp_lib)

Every number is normalised to a $10,000 ticket. Cost = bps PER SIDE.
No decision uses anything after its own minute: the cross minute is the
first RTH minute whose CLOSE >= 1.10 x prev_close and >= $2 (the live
scanner rule, complete on this cache -- see cp_lib docstring); entry is
the OPEN of the next printed bar.

    python plan/lm8_tod.py legs      # part A (seconds)
    python plan/lm8_tod.py panel     # parts B + C (one pass over 444 days)
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
COSTS = (0, 6, 12, 15, 18)


def hm(m):  # grid minute -> "HH:MM"
    t = m + 240
    return f"{t // 60:02d}:{t % 60:02d}"


def tstat_days(vals, days):
    """mean and t with day-clustering (mean of day means / se over days)."""
    by = defaultdict(list)
    for v, d in zip(vals, days):
        by[d].append(v)
    dm = np.array([np.mean(v) for v in by.values()])
    if len(dm) < 3:
        return float("nan")
    return dm.mean() / (dm.std(ddof=1) / np.sqrt(len(dm)))


def row(name, r, days, extra=""):
    """r = per-ticket fractional return. Prints $/tkt at $10k gross + costs."""
    r = np.asarray(r, float)
    if len(r) == 0:
        print(f"  {name:<26} n=0")
        return
    g = r.mean() * 1e4
    nets = " ".join(f"{g - 2 * c:+8.1f}" for c in COSTS[1:])
    srt = np.sort(r)[::-1]
    ex5 = srt[5:].mean() * 1e4 if len(r) > 10 else float("nan")
    print(f"  {name:<26} n={len(r):5d} gross={g:+8.1f} net@6/12/15/18={nets}"
          f"  med={np.median(r)*1e4:+7.1f} win={np.mean(r>0)*100:4.1f}% "
          f"ex-top5={ex5:+8.1f} tday={tstat_days(r, days):+5.2f} {extra}")


# ---------------------------------------------------------------- part A
def legs_c37(cfg):
    d = json.loads((ROOT / f"data/massive/rotation_trades_{cfg}_hf3.json").read_text())
    out = []
    for x in d:
        e = x["entry_time"][11:16]
        xx = x["exit_time"][11:16]
        em = int(e[:2]) * 60 + int(e[3:]) - 240
        xm = int(xx[:2]) * 60 + int(xx[3:]) - 240
        notional = x["entry"] * x["shares"]
        out.append(dict(date=x["date"], sym=x["symbol"], em=em, xm=xm,
                        r=x["pnl"] / notional if notional else 0.0,
                        reason=x["reason"].split()[0], ticket=x["ticket"]))
    return out


def legs_cp(key):
    d = json.loads((ROOT / "plan/pa_out/cp_r4_legs.json").read_text())
    keys = [k for k in d["legs"] if (k == key or (key == "RND" and k.startswith("RND")))]
    out = []
    for k in keys:
        for x in d["legs"][k]:
            out.append(dict(date=x["date"], sym=x["sym"], em=x["entry_min"],
                            xm=x["exit_min"], r=x["exit"] / x["entry"] - 1.0,
                            reason=x["reason"].split()[0], seed=k,
                            entry=x["entry"]))
    return out


EB = [(330, 335, "09:30-09:35"), (335, 345, "09:35-09:45"), (345, 360, "09:45-10:00"),
      (360, 390, "10:00-10:30"), (390, 420, "10:30-11:00"), (420, 480, "11:00-12:00"),
      (480, 540, "12:00-13:00"), (540, 600, "13:00-14:00"), (600, 631, "14:00-14:30")]
HB = [(0, 5), (5, 15), (15, 30), (30, 60), (60, 120), (120, 240), (240, 400)]


def part_a():
    sets = [("C37F-hf3 (live C37 rules)", legs_c37("C37F")),
            ("HOLD1-hf3 (same pick, hold->15:00)", legs_c37("HOLD1")),
            ("cp R4 (coil, no stop)", legs_cp("R4")),
            ("cp RND x30 (random rank, same machinery)", legs_cp("RND"))]
    for nm, lg in sets:
        print(f"\n=== {nm}: {len(lg)} legs, {len(set(x['date'] for x in lg))} days")
        r = [x["r"] for x in lg]
        dd = [x["date"] for x in lg]
        row("ALL", r, dd)
        print(" by ENTRY bucket")
        for a, b, lab in EB:
            s = [x for x in lg if a <= x["em"] < b]
            row(lab, [x["r"] for x in s], [x["date"] for x in s])
        print(" by HOLD minutes")
        for a, b in HB:
            s = [x for x in lg if a <= x["xm"] - x["em"] < b]
            row(f"hold {a}-{b}m", [x["r"] for x in s], [x["date"] for x in s])
        print(" by EXIT reason")
        for rs in sorted(set(x["reason"] for x in lg)):
            s = [x for x in lg if x["reason"] == rs]
            row(rs, [x["r"] for x in s], [x["date"] for x in s],
                f"medhold={np.median([x['xm']-x['em'] for x in s]):.0f}m")
        print(" by YEAR x entry before/after 10:00")
        for y0, y1, yl in (("2024", "2025-08-01", "Y1"), ("2025-08-01", "2027", "Y2")):
            for a, b, lab in ((330, 360, "<10:00"), (360, 631, ">=10:00")):
                s = [x for x in lg if y0 <= x["date"] < y1 and a <= x["em"] < b]
                row(f"{yl} {lab}", [x["r"] for x in s], [x["date"] for x in s])
        if "ticket" in lg[0]:
            print(" by ticket # in the day (rotation order)")
            for t in range(7):
                s = [x for x in lg if x["ticket"] == t]
                row(f"ticket {t}", [x["r"] for x in s], [x["date"] for x in s])


# ---------------------------------------------------------------- part B/C
HZ = [5, 10, 15, 30, 45, 60, 90, 120, 180, 240, 300]
SEGS = list(range(330, 720, 30))  # clock half-hours 09:30..15:30
TEXIT = [L.mgrid(h, m) for h, m in ((10, 0), (10, 30), (11, 0), (12, 0), (13, 0), (14, 0),
                                    (14, 30), (15, 0), (15, 30), (15, 50), (15, 59))]
NSTOP = [15, 30, 45, 60, 90, 120, 180]
COH = [(330, 331, "cross@09:30 (gap-open)"), (331, 360, "cross 09:31-09:59"),
       (360, 420, "cross 10:00-10:59"), (420, 540, "cross 11:00-12:59"),
       (540, 631, "cross 13:00-14:30")]


def first_open_after(d, i, m):
    """open of the first printed bar at minute > m; (price, minute)."""
    pr = d.printed[i, m + 1:]
    if not pr.any():
        return np.nan, L.NMIN
    k = m + 1 + int(pr.argmax())
    return d.o[i, k], k


def part_bc():
    dates = L.panel_dates()
    cp = json.loads((ROOT / "plan/pa_out/cp_r4_legs.json").read_text())["legs"]
    legs_by_date = defaultdict(list)
    for k, v in cp.items():
        for x in v:
            legs_by_date[x["date"]].append((k, x))
    # B rows: per crosser
    B = []  # (date, cohort-minute, liquid flag, ret dict)
    seg = defaultdict(list)  # (segment start, liq) -> [(ret, date)]
    C = defaultdict(list)    # (set, T) -> [(ret, date)]
    D = defaultdict(list)    # (set, N, state) -> [(r_final - r_N, date)]
    for di, date in enumerate(dates):
        d = L.load_day(date)
        if d is None:
            continue
        last = d.last
        cm = d.cross_minute("LAST")
        cdv = d.cumdv
        for i in np.where(cm <= 630)[0]:
            m = int(cm[i])
            px, em = first_open_after(d, i, m)
            if not np.isfinite(px) or px <= 0 or em > 631:
                continue
            liq = bool(cdv[i, m] >= 2e6)
            rec = {"date": date, "cm": m, "em": em, "liq": liq,
                   "gap": float(d.o[i, 330] / d.pc[i] - 1) if d.printed[i, 330] else np.nan}
            for h in HZ:
                t = em + h
                rec[f"h{h}"] = last[i, t] / px - 1 if t <= 719 else np.nan
            for T in TEXIT:
                rec[f"T{T}"] = last[i, T] / px - 1 if T > em else np.nan
            B.append(rec)
            for s in SEGS:
                e = min(s + 30, 719)
                if em <= s and np.isfinite(last[i, s]) and np.isfinite(last[i, e]):
                    rr = last[i, e] / last[i, s] - 1
                    seg[(s, "all")].append((rr, date))
                    if liq:
                        seg[(s, "liq")].append((rr, date))
        # C: re-price cp legs under alternative forced flatten times
        sidx = {s: k for k, s in enumerate(d.syms)}
        for key, x in legs_by_date.get(date, []):
            i = sidx.get(x["sym"])
            if i is None:
                continue
            setk = "R4" if key == "R4" else "RND"
            em_, xm_ = x["entry_min"], x["exit_min"]
            flat = x["reason"].startswith("flatten")
            base = x["exit"] / x["entry"] - 1
            for N in NSTOP:
                t = em_ + N
                if xm_ > t and t <= 659:
                    pN = last[i, t]
                    if np.isfinite(pN):
                        rN = pN / x["entry"] - 1
                        st = "under" if rN < 0 else "over"
                        D[(setk, N, st)].append((base - rN, date))
                        D[(setk, N, "any")].append((base - rN, date))
            for T in TEXIT:
                if em_ >= T - 1:
                    continue  # would not be entered under this window
                if xm_ >= T or (flat and T > xm_):
                    p = last[i, T - 1]  # close of the bar before T ~ fill at T
                    rr = p / x["entry"] - 1 if np.isfinite(p) else base
                else:
                    rr = base
                C[(setk, T)].append((rr, date))
        if (di + 1) % 100 == 0:
            print(f"  ..{di+1}/{len(dates)}", flush=True)

    print(f"\n=== B. post-cross path, {len(B)} crossers (entry = next open after "
          f"first RTH close >= +10%, >= $2), {len(dates)} days")
    for liqf, lab in ((None, "ALL"), (True, "LIQUID (cum $vol at cross >= $2M)")):
        S = [b for b in B if liqf is None or b["liq"] == liqf]
        print(f"\n -- {lab}: n={len(S)}")
        print("   forward return from entry, bp (mean / winsorised1% mean / median / %up / t-day)")
        for h in HZ:
            v = np.array([b[f"h{h}"] for b in S]); ok = np.isfinite(v)
            v2 = v[ok]; dd = [b["date"] for b, k in zip(S, ok) if k]
            lo, hi = np.percentile(v2, [1, 99]); w = np.clip(v2, lo, hi)
            print(f"   +{h:3d}m n={len(v2):5d} mean={v2.mean()*1e4:+7.1f} wins={w.mean()*1e4:+7.1f} "
                  f"med={np.median(v2)*1e4:+7.1f} up={np.mean(v2>0)*100:4.1f}% t={tstat_days(w, dd):+5.2f}")
        print("   by cross cohort: winsorised mean bp entry -> forced exit at T")
        hdr = " ".join(f"{hm(T):>7}" for T in TEXIT)
        print(f"   {'cohort':<24} {'n':>5} {hdr}")
        for a, b, cl in COH:
            Sc = [x for x in S if a <= x["cm"] < b]
            cells = []
            for T in TEXIT:
                v = np.array([x[f"T{T}"] for x in Sc]); v = v[np.isfinite(v)]
                if len(v) < 30:
                    cells.append(f"{'':>7}")
                    continue
                lo, hi = np.percentile(v, [1, 99])
                cells.append(f"{np.clip(v, lo, hi).mean()*1e4:+7.1f}")
            print(f"   {cl:<24} {len(Sc):5d} {' '.join(cells)}")
        print("   same, MEDIAN bp")
        for a, b, cl in COH:
            Sc = [x for x in S if a <= x["cm"] < b]
            cells = []
            for T in TEXIT:
                v = np.array([x[f"T{T}"] for x in Sc]); v = v[np.isfinite(v)]
                cells.append(f"{np.median(v)*1e4:+7.1f}" if len(v) >= 30 else f"{'':>7}")
            print(f"   {cl:<24} {len(Sc):5d} {' '.join(cells)}")

    print("\n=== B2. clock half-hour drift of names ALREADY crossed (held since before the "
          "segment), last->last, bp")
    for lab in ("all", "liq"):
        print(f" -- {lab}")
        for s in SEGS:
            v = seg.get((s, lab), [])
            if not v:
                continue
            r = np.array([a for a, _ in v]); dd = [b for _, b in v]
            lo, hi = np.percentile(r, [1, 99]); w = np.clip(r, lo, hi)
            y1 = np.array([a for a, b in zip(w, dd) if b < "2025-08-01"])
            y2 = np.array([a for a, b in zip(w, dd) if b >= "2025-08-01"])
            print(f"   {hm(s)}-{hm(min(s+30,719))} n={len(r):5d} mean={r.mean()*1e4:+7.1f} "
                  f"wins={w.mean()*1e4:+7.1f} med={np.median(r)*1e4:+6.1f} up={np.mean(r>0)*100:4.1f}% "
                  f"t={tstat_days(w, dd):+5.2f} Y1={y1.mean()*1e4:+6.1f} Y2={y2.mean()*1e4:+6.1f}")

    print("\n=== C. cp legs re-priced under a forced flatten at T (entries also stop at T); "
          "$ per $10k ticket")
    for setk in ("R4", "RND"):
        print(f" -- {setk}{' (30 seeds pooled)' if setk == 'RND' else ''}")
        for T in TEXIT:
            v = C.get((setk, T), [])
            if not v:
                continue
            row(f"flatten {hm(T)}", [a for a, _ in v], [b for _, b in v])

    print("\n=== D. causal TIME STOP: legs still open N min after entry; "
          "value of HOLDING ON (final - mark at N), bp; negative => time stop helps")
    for setk in ("R4", "RND"):
        print(f" -- {setk}")
        ntot = sum(1 for k in C if k[0] == setk) and len(C[(setk, L.mgrid(15, 0))])
        for N in NSTOP:
            for st in ("any", "under", "over"):
                v = D.get((setk, N, st), [])
                if not v:
                    continue
                r = np.array([a for a, _ in v]); dd = [b for _, b in v]
                y1 = np.array([a for a, b in v if b < "2025-08-01"])
                y2 = np.array([a for a, b in v if b >= "2025-08-01"])
                print(f"   N={N:3d} {st:<5} n={len(r):5d} ({len(r)/max(ntot,1)*100:4.1f}% of legs) "
                      f"hold-on mean={r.mean()*1e4:+7.1f} med={np.median(r)*1e4:+7.1f} "
                      f"t={tstat_days(r, dd):+5.2f} Y1={y1.mean()*1e4:+7.1f} Y2={y2.mean()*1e4:+7.1f}")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "legs"
    if which == "legs":
        part_a()
    else:
        part_bc()
