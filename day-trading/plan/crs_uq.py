"""COST-RESCORE (2026-10-01): UNIVERSE-QUOTES rank-for-the-fill (relabelled
limit policy, h30, offset 10 bps, wait 1, post_k 3, split 1 = held-out
year, max 7 tickets) + its inverted mirror + the 30-seed random control
(seeds 2000+s), exactly uq_relabel.stage_eval's frame, walked once through
uq_strat.run_many with price_ticket wrapped to record each ticket's GROSS
components (notional, fill px, exit px, ext flags, passive flag). The
policy path does not depend on cost (busy_until = exit minute; sizing is
min($15k, volcap*L)), so net(b) is exact:
    net = N * (X/F * (1 - x_c) - (1 + e_c)),
    e_c = (0 if passive else b) + 50*ext_in,  x_c = b + 50*ext_out  (bps).
Identity: net(10) must reproduce the published +$0.06/ticket, 1,210 tickets.
Writes plan/crs_uq_legs.json."""
import json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uq_relabel as UR
US, UE, UF = UR.US, UR.UE, UR.UF
h, offset, wait, post_k, split, seeds = "h30", 10.0, 1, 3, 1, 30
t0 = time.time()
t = UR.Table()
sc = np.load(UR.score_path(h, offset, wait, UF.FEE_BPS, split)).astype(float)
days = [d for d in UE.cached_days(t, split)
        if np.isfinite(sc[t.date_i == t.dates.index(d)]).any()]
fin = np.isfinite(sc)
scores = [sc, -sc]
for s in range(seeds):
    rg = np.random.default_rng(2000 + s)
    scores.append(np.where(fin, rg.random(len(sc)), np.nan))
REC = []
_pt = UE.price_ticket


def price_ticket(day, ti, si, h_, L, fill_t_ms, passive_bps, exit_bps, cap_mult=1.0, fill_px=None):
    pt = _pt(day, ti, si, h_, L, fill_t_ms, passive_bps, exit_bps, cap_mult, fill_px)
    if pt is not None and pt["notional"] >= UF.MIN_NOTIONAL:
        ex_px, ex_m = day.exit_leg(si, pt["fill_min"], UF.HORIZ[h_])
        REC.append(dict(N=float(pt["notional"]), F=float(pt["fill_px"]), X=float(ex_px),
                        ext_in=bool(UF.cost_frac(pt["fill_min"], 0.0) > 0),
                        ext_out=bool(UF.cost_frac(ex_m, 0.0) > 0),
                        passive=bool(passive_bps is not None and float(passive_bps) <= 1e-9),
                        pnl10=float(pt["pnl"])))
    return pt


UE.price_ticket = price_ticket
_sd = US.simulate_day


def simulate_day(*a, **k):
    REC.clear()
    out = _sd(*a, **k)
    assert len(out) == len(REC), (len(out), len(REC))
    for o, r in zip(out, REC):
        o.update(r)
    return out


US.simulate_day = simulate_day
kw = dict(offset=offset, wait=wait, post_k=post_k, h=h, exit_bps=UF.FEE_BPS,
          passive_bps=0.0, max_tickets=7)
acc = US.run_many(t, days, scores, [kw])
names = ["MODEL", "INVERTED"] + [f"RND{s}" for s in range(seeds)]
legs = {nm: [{k: v for k, v in x.items() if k in ("date", "sym", "N", "F", "X", "ext_in", "ext_out", "passive", "pnl", "pnl10", "fill_min", "exit_min")}
             for x in acc[(0, i)]] for i, nm in enumerate(names)}
(HERE / "crs_uq_legs.json").write_text(json.dumps({"dates": days, "legs": legs, "secs": time.time() - t0}, default=float))
m = legs["MODEL"]
print("done", len(m), round(float(np.mean([x["pnl"] for x in m])), 3), round(time.time() - t0))
