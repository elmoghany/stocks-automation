"""UNIVERSE+QUOTES (2026-09-16) -- constraint 2, stage 5: RANK FOR THE
FILL, not for the market.

The train-window grid (plan/uq_strat.py --stage select) produced a clean,
uncomfortable result: a limit entry roughly HALVES the toll for every
ranking -- a random ranking improves from -$26.18 to -$9.60 per ticket --
but the wide-net model's edge over random INVERTS, from +$3.98 under a
market fill to -$1.45..-$24.16 under all thirty limit configurations.

That is not mysterious. The wide-net model was fitted on the P&L of a
ticket that ALWAYS fills at the next bar's open. A limit only fills when
the price comes DOWN to it, so the model's ranking is being applied to a
conditional population it was never trained on: the names it likes most
are, disproportionately, the names that never trade down to the limit,
and the ones that do fill are the ones whose forecast went wrong first.

The fix is a different LABEL, not a different model. This module builds

    y(row) = the realized net dollar P&L of a $15,000 LIMIT ticket posted
             at that (date, symbol, decision minute), $0 if it never
             filled within N minutes

for every causally eligible row, and stores it as a plain array aligned
to data/massive/wn/table.npz. Feeding that to the SAME plan/wn_model.fit
(imported, same params, same early stopping, same walk-forward) asks the
model the question the strategy actually faces: "which name, if I post a
limit on it, pays?" Features are untouched and still poison-tested.

The label is future information -- it is a LABEL -- and it is never a
feature. The decision inputs (mark, volcap, the 32 features) remain
functions of bars <= m; only whether the posted order filled is read from
after t0, which is the allowance stated in plan/uq_poison.py.

Usage:
  python plan/uq_label.py --offset 10 --wait 1 [--h h30] [--exit 10]
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uq_econ as UE                                          # noqa: E402
import uq_fills as UF                                         # noqa: E402
from wn_lib import Table                                      # noqa: E402

OUT = HERE / "uq_out"
RTH = UF.RTH_DEC


def path(h, offset, wait, exit_bps):
    return OUT / (f"limlabel_{h}_o{offset:.0f}_w{wait}"
                  f"_x{exit_bps:.0f}.npz")


def build(h="h30", offset=10.0, wait=1, exit_bps=UF.FEE_BPS,
          passive_bps=0.0, chunk_days=40):
    t = Table()
    days = UE.cached_days(t, None)
    di = {d: i for i, d in enumerate(t.dates)}
    dec_i = [UF.DEC_ET.index(x) for x in RTH]
    n = len(t.date_i)
    y = np.zeros(n, np.float32)
    filled = np.zeros(n, bool)
    have = np.zeros(n, bool)
    print(f"label: {len(days)} tape-complete days", flush=True)
    for a in range(0, len(days), chunk_days):
        part = days[a:a + chunk_days]
        rows = np.flatnonzero(t.printed_m
                              & np.isin(t.date_i, [di[d] for d in part])
                              & np.isin(t.dec_i, dec_i))
        if rows.size == 0:
            continue
        res = UE.price_rows(t, rows, h, offsets=[offset], nwait=[wait],
                            exit_bps=exit_bps, passive_bps=passive_bps,
                            spread_offset=False, verbose=False)
        ht = res["have_tape"]
        y[rows[ht]] = res["lim"][(offset, wait)][ht]
        filled[rows[ht]] = res["filled"][(offset, wait)][ht]
        have[rows[ht]] = True
        print(f"  ..{min(a+chunk_days, len(days))}/{len(days)} days, "
              f"{int(have.sum()):,} rows, fill "
              f"{float(filled[have].mean()):.3f}", flush=True)
    f = path(h, offset, wait, exit_bps)
    np.savez_compressed(f, y=y, filled=filled, have=have)
    print(f"saved {f.name}: {int(have.sum()):,} labelled rows, "
          f"fill rate {float(filled[have].mean()):.4f}, "
          f"mean ${float(y[have].mean()):.2f}/attempt, "
          f"${float(y[have & filled].mean()):.2f}/filled")


if __name__ == "__main__":
    a = sys.argv
    g = lambda f, d: (type(d)(a[a.index(f) + 1]) if f in a else d)  # noqa: E731
    OUT.mkdir(parents=True, exist_ok=True)
    build(g("--h", "h30"), g("--offset", 10.0), g("--wait", 1),
          g("--exit", UF.FEE_BPS), g("--passive", 0.0))
