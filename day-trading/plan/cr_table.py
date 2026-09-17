"""COST-REBASE: a re-priceable copy of the wide-net cross-section.

WHY THIS AND NOT A REBUILD. `data/massive/wn/table.npz` stores only NET
P&L, with the 10 bps ladder already folded into it, and the exit price
and exit minute are not stored at all. Rebuilding it under a new cost
model would mean re-running plan/rl2/features.py (448 days) and
plan/wn_table.py. But `uq_fills.DayTape` already reconstructs every
ticket from the raw caches EXACTLY -- UNIVERSE-QUOTES' identity gate is
96,780 checks / 0 mismatches, worst $0.0000 -- so the cheap and exact
route is to recover the four cost-free quantities per row

    entry price, exit price, exit minute, notional

and price them under any cost model with

    pnl = notional * [ Px*(1-c_out)/Pe - (1+c_in) ]

which is algebraically the same expression wn_table.py uses. Nothing is
rebuilt, nothing is overwritten, and the flat-10 re-pricing reproduces
`table.npz` to the dollar (`--verify`), which IS the identity gate for
this line's wide-universe leg.

Eligibility and SIZE are cost-invariant (notional = min($15k,
volcap*Pe); `printed`/`ok` are printability tests), so swapping the
cost cannot move which rows exist or how big they are -- per-ticket
deltas are clean.

Usage:
  python plan/cr_table.py --build [--h h30]
  python plan/cr_table.py --verify [--h h30]
  python plan/cr_table.py --price  [--h h30]      # adds measured pnl
"""
import importlib.util
import json
import sys
import time
from datetime import time as dtime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT.parent))

import cr_cost as CC                                        # noqa: E402

OUT = HERE / "cr_out"
WN = ROOT / "data" / "massive" / "wn"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


UF = _load("uq_fills", HERE / "uq_fills.py")
WL = _load("wn_lib", HERE / "wn_lib.py")


def path_of(h):
    return OUT / f"rows_{h}.npz"


def build(h="h30"):
    t = WL.Table()
    n = len(t.pnl[h])
    dates = list(t.dates)
    syms = list(t.syms)
    ent = np.zeros(n)
    exp = np.zeros(n)
    exm = np.full(n, -1, np.int32)
    enm = np.full(n, -1, np.int32)
    notion = np.zeros(n)
    good = np.zeros(n, bool)
    order = np.argsort(t.date_i, kind="stable")
    t0 = time.monotonic()
    di_prev, day = -1, None
    for k, r in enumerate(order):
        di = int(t.date_i[r])
        if di != di_prev:
            day = UF.DayTape(dates[di], need_tape=False)
            di_prev = di
        si = day.sidx.get(syms[int(t.sym_i[r])])
        if si is None:
            continue
        ti = int(UF.DEC_T[int(t.dec_i[r])])
        m = int(UF.STEPS[ti])
        me = min(m + 1, UF.NMIN - 1)
        if not day.printed[si, me]:
            continue
        e = float(day.o[si, me])
        nt = min(UF.TICKET, day.volcap[ti, si] * e)
        if not np.isfinite(nt):
            continue
        xp, xm = day.exit_leg(si, me, UF.HORIZ[h])
        if not np.isfinite(xp) or xm < me:
            continue
        ent[r], exp[r], exm[r], enm[r], notion[r], good[r] = \
            e, xp, xm, me, nt, True
        if (k + 1) % 50000 == 0:
            el = time.monotonic() - t0
            print(f"  [{k+1:,}/{n:,}] {el/60:.1f}m", flush=True)
    OUT.mkdir(exist_ok=True)
    np.savez_compressed(
        path_of(h), ent=ent, exp=exp, exm=exm, enm=enm, notion=notion,
        good=good, date_i=t.date_i, sym_i=t.sym_i, dec_i=t.dec_i,
        dates=np.array(dates), syms=np.array(syms))
    print(f"built {path_of(h)}  good={good.sum():,}/{n:,} "
          f"in {(time.monotonic()-t0)/60:.1f}m")


def flat_pnl(z, fee_bps=10.0, ext_bps=50.0):
    ci = (fee_bps + ext_bps * ((z["enm"] < UF.RTH_LO)
                               | (z["enm"] >= UF.RTH_HI))) / 1e4
    co = (fee_bps + ext_bps * ((z["exm"] < UF.RTH_LO)
                               | (z["exm"] >= UF.RTH_HI))) / 1e4
    with np.errstate(divide="ignore", invalid="ignore"):
        p = z["notion"] * (z["exp"] * (1 - co) / np.maximum(z["ent"], 1e-12)
                           - (1 + ci))
    return np.where(z["good"], p, 0.0)


def verify(h="h30"):
    z = dict(np.load(path_of(h), allow_pickle=False))
    t = WL.Table()
    ref = t.pnl[h]
    got = flat_pnl(z)
    d = np.abs(got - ref)
    m = z["good"]
    print(f"identity vs table.npz[{h}]: {int(m.sum()):,} rows, "
          f"worst |diff| ${d[m].max():.6f}, "
          f"n>1e-6: {int((d[m] > 1e-6).sum()):,}")
    # rows we could not reconstruct must be $0 in the table too
    bad = (~m) & (np.abs(ref) > 1e-9)
    print(f"unreconstructed rows with non-zero table pnl: {int(bad.sum()):,}")
    return dict(worst=float(d[m].max()),
                n_mismatch=int((d[m] > 1e-6).sum()),
                n_rows=int(m.sum()), n_bad=int(bad.sum()))


def _clock(minute):
    mm = 240 + int(minute)          # rl2 grid: minute 0 = 04:00 ET
    return dtime((mm // 60) % 24, mm % 60)


def cost_legs(z, cm):
    """Half-spread and impact, per row, for the entry and the exit leg.

    ONE pass over the symbol-days; the two variants (with and without
    the impact term) are then pure arithmetic on the returned arrays.
    Extended-hours floors are applied here, after the combination, so
    they behave the same way in both variants.
    """
    n = len(z["ent"])
    hi_ = np.zeros(n)
    ii_ = np.zeros(n)
    ho_ = np.zeros(n)
    io_ = np.zeros(n)
    dates, syms = list(z["dates"]), list(z["syms"])
    idx = np.flatnonzero(z["good"])
    key = z["date_i"].astype(np.int64) * 100000 + z["sym_i"]
    order = idx[np.argsort(key[idx], kind="stable")]
    t0 = time.monotonic()
    for k, r in enumerate(order):
        d = str(dates[int(z["date_i"][r])])
        s = str(syms[int(z["sym_i"][r])])
        hi_[r], ii_[r], _ = cm.parts(s, d, _clock(z["enm"][r]),
                                     z["notion"][r])
        ho_[r], io_[r], _ = cm.parts(s, d, _clock(z["exm"][r]),
                                     z["notion"][r] * z["exp"][r]
                                     / max(z["ent"][r], 1e-12))
        if (k + 1) % 25000 == 0:
            print(f"  legs [{k+1:,}/{len(order):,}] "
                  f"{(time.monotonic()-t0)/60:.1f}m", flush=True)
    return hi_, ii_, ho_, io_


def combine(z, half_i, imp_i, half_o, imp_o, coef=1.0, floor=None,
            ext_floor=60.0):
    floor = CC.FLOOR_BPS if floor is None else floor
    ci = np.maximum(floor, half_i + coef * imp_i)
    co = np.maximum(floor, half_o + coef * imp_o)
    ext_i = (z["enm"] < UF.RTH_LO) | (z["enm"] >= UF.RTH_HI)
    ext_o = (z["exm"] < UF.RTH_LO) | (z["exm"] >= UF.RTH_HI)
    ci = np.where(ext_i, np.maximum(ci, ext_floor), ci)
    co = np.where(ext_o, np.maximum(co, ext_floor), co)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = z["notion"] * (z["exp"] * (1 - co / 1e4)
                           / np.maximum(z["ent"], 1e-12)
                           - (1 + ci / 1e4))
    return np.where(z["good"], p, 0.0), ci, co


def main():
    a = sys.argv[1:]
    h = a[a.index("--h") + 1] if "--h" in a else "h30"
    if "--build" in a:
        build(h)
    if "--verify" in a:
        r = verify(h)
        (OUT / f"table_identity_{h}.json").write_text(json.dumps(r, indent=1))
    if "--price" in a:
        z = dict(np.load(path_of(h), allow_pickle=False))
        # EXT FLOOR 60 bps, not 10: the wide-net / rl2 / UQ ladder charges
        # FEE_BPS + EXT_BPS = 10 + 50 outside 09:30-16:00, so "measured or
        # the incumbent floor, whichever is larger" means 60 there. The
        # engine path uses 10 because day-trading.py pays its 50 bps
        # premarket haircut separately, through pm_spread_bps.
        g = z["good"]
        out = {"pnl_flat10": flat_pnl(z)}
        rep = {"n": int(g.sum()),
               "mean_pnl_flat10": float(flat_pnl(z)[g].mean())}
        # TWO variants, and the difference between them IS the finding:
        #   measured   = half-spread + square-root impact (Y = 1.0)
        #   spreadonly = half-spread only (Y = 0), i.e. the literal
        #                "re-price at the measured spread" that the
        #                UNIVERSE-QUOTES audit's ranked idea #2 asked for
        cm = CC.CostModel(ext_floor_bps=60.0)
        hi_, ii_, ho_, io_ = cost_legs(z, cm)
        np.savez_compressed(OUT / f"legs_{h}.npz", half_in=hi_, imp_in=ii_,
                            half_out=ho_, imp_out=io_)
        for name, coef in (("measured", CC.IMPACT_COEF),
                           ("spreadonly", 0.0),
                           ("imp03", 0.3), ("imp05", 0.5)):
            p, ci, co = combine(z, hi_, ii_, ho_, io_, coef=coef)
            out[f"pnl_{name}"] = p
            out[f"c_in_bps_{name}"] = ci
            out[f"c_out_bps_{name}"] = co
            rep[name] = dict(
                mean_c_in=float(ci[g].mean()),
                median_c_in=float(np.median(ci[g])),
                mean_c_out=float(co[g].mean()),
                median_c_out=float(np.median(co[g])),
                frac_c_in_gt10=float((ci[g] > 10).mean()),
                mean_pnl=float(p[g].mean()),
                delta_vs_flat=float(p[g].mean()
                                    - flat_pnl(z)[g].mean()))
            print(name, json.dumps(rep[name]), flush=True)
        np.savez_compressed(OUT / f"priced_{h}.npz", **out)
        (OUT / f"priced_{h}_report.json").write_text(
            json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
