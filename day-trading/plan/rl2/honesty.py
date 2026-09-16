"""RL-SERIES v2 (2026-09-16): the adversarial battery.

Every number in rl2-audit.md is worthless unless these pass. They are run
before any model is trained and re-run after.

  poison          Replace every bar STRICTLY AFTER minute m with garbage
                  and recompute the whole feature block. Every feature,
                  the mark, the print mask and the size cap at every
                  decision step <= m must be BIT-IDENTICAL. 16 days x 4
                  cut points = 64 checks. This makes look-ahead in the
                  state impossible rather than merely unintended.
  hold_zero       A never-buy score matrix must return exactly $0 and 0
                  tickets, so any reported P&L is attributable to fills.
  cost_monotone   The same fixed policy must earn strictly more at zero
                  cost than at modelled cost, and more at modelled cost
                  than at 10x cost -- proof the fee/extended ladder is
                  live in the P&L.
  foresight       Score = the realized net return of the trade the
                  decision would open. If the harness cannot make money
                  WITH the future, a null result has no power.
  random          Uniform random scores over the SAME eligible set with
                  the SAME fills, exit rule and costs, 30 seeds. The
                  baseline that most often ends the conversation.

  The SHUFFLED-TARGET control lives in plan/rl2/bandit.py, because it has
  to shuffle the TRAINING LABEL, not the price path. v1's control permuted
  each symbol's intraday return sequence, which preserves the day's
  terminal price and turns the panel into a Brownian bridge pinned at both
  ends -- a mechanical artifact worth hundreds of dollars a ticket. v2
  shuffles `tgt` across (name, t) rows WITHIN each day, so per-row sums are
  not preserved and the only thing destroyed is the association between a
  row's features and its outcome.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import features as FT                                         # noqa: E402
import sim as SM                                              # noqa: E402

OUT = HERE / "out"
FEAT = OUT / "feat"
DAYS = OUT / "days"


def poison_check(n_days=16, cuts=(400, 550, 700, 850), seed=0):
    prof = FT.fit_profile()
    daily = FT.Daily()
    files = sorted(DAYS.glob("*.npz"))
    rng = np.random.default_rng(seed)
    pick = [files[i] for i in rng.choice(len(files), size=min(n_days, len(files)),
                                         replace=False)]
    checked = mism = 0
    detail = []
    for p in pick:
        date = p.stem
        syms, pc, bars = FT.load_raw(p)
        clean = FT.compute_day(date, syms, pc, bars, prof, daily)
        for cut in cuts:
            o, h, lo, c, v = (a.copy() for a in bars)
            sl = slice(cut + 1, None)
            shp = o[:, sl].shape
            g = rng.uniform(0.5, 500.0, size=shp)
            o[:, sl] = g
            h[:, sl] = g * rng.uniform(1.0, 1.5, size=shp)
            lo[:, sl] = g * rng.uniform(0.5, 1.0, size=shp)
            c[:, sl] = g * rng.uniform(0.7, 1.3, size=shp)
            v[:, sl] = rng.integers(1, 10 ** 7, size=shp)
            bad = FT.compute_day(date, syms, pc, (o, h, lo, c, v), prof, daily)
            # every decision step whose minute is <= cut
            keep = FT.STEPS <= cut
            ok = True
            for k in ("F", "mark", "printed", "volcap"):
                a, b = clean[k][keep], bad[k][keep]
                if not np.array_equal(np.nan_to_num(a, nan=-9e9),
                                      np.nan_to_num(b, nan=-9e9)):
                    ok = False
                    detail.append({"date": date, "cut": cut, "array": k})
            checked += 1
            mism += (not ok)
    return {"checks": checked, "mismatches": mism, "detail": detail[:20]}


def _days(dates):
    return [SM.Day(FEAT / f"{d}.npz") for d in dates]


def hold_zero(days):
    tot, n = 0.0, 0
    for d in days:
        sc = np.full((FT.T, d.S), -np.inf, np.float64)
        tr, p = SM.run_day(d, sc)
        tot += p
        n += len(tr)
    return {"total": tot, "tickets": n}


def cost_monotone(days, seed=0):
    """Same fixed (seeded-random) policy at 0x, 1x and 10x cost."""
    out = {}
    base_fee, base_ext = FT.FEE_BPS, FT.EXT_BPS
    scs = []
    for d in days:
        rng = np.random.default_rng(seed)
        scs.append(rng.random((FT.T, d.S)))
    for name, mult in (("zero", 0.0), ("modelled", 1.0), ("ten_x", 10.0)):
        FT.FEE_BPS, FT.EXT_BPS = base_fee * mult, base_ext * mult
        SM.FEE_BPS, SM.EXT_BPS = FT.FEE_BPS, FT.EXT_BPS
        tot = 0.0
        for d, sc in zip(days, scs):
            tot += SM.run_day(d, sc)[1]
        out[name] = round(tot, 2)
    FT.FEE_BPS, FT.EXT_BPS = base_fee, base_ext
    SM.FEE_BPS, SM.EXT_BPS = base_fee, base_ext
    return out


def foresight(days, horizon_idx=1, exit_rule=("horizon", 30),
              min_score=0.0, max_new=2):
    """Positive control: score = the trade's own realized net return.

    It must run under the SAME policy shape as approach 1 -- buy only
    where the predicted net return is positive, at most `max_new` per
    decision -- or it is not a control on the same harness. Scored with
    min_score=-inf it spends all seven tickets in the first premarket
    minute and loses money with perfect foresight, which measures the
    policy shape, not the harness.
    """
    trades = []
    for d in days:
        sc = np.where(d.tgt_ok[:, :, horizon_idx],
                      d.tgt[:, :, horizon_idx].astype(np.float64), -np.inf)
        trades += SM.run_day(d, sc, exit_rule, min_score=min_score,
                             max_new_per_step=max_new)[0]
    return SM.summarize(trades, len(days), "FORESIGHT-30")


def random_control(days, seeds=30, exit_rule=("horizon", 30), p_entry=1.0,
                   max_new=2, label="RANDOM"):
    """Uniform random scores, same eligibility / fills / costs / exit rule.

    `p_entry` is the per-(step, name) probability that the random score
    clears the buy threshold; it is how a random control is matched to a
    policy's ticket RATE, so a selective policy is not being compared
    with a control that trades every day to the cap.
    """
    rows = []
    for s in range(seeds):
        trades = []
        for d in days:
            rng = np.random.default_rng(10_000 + s)
            sc = rng.random((FT.T, d.S))
            trades += SM.run_day(d, sc, exit_rule,
                                 min_score=1.0 - p_entry,
                                 max_new_per_step=max_new)[0]
        rows.append(SM.summarize(trades, len(days), f"{label}-s{s}"))
    tot = np.array([r["total"] for r in rows])
    pt = np.array([r["per_ticket"] for r in rows])
    return {"seeds": seeds, "mean_total": round(float(tot.mean()), 2),
            "min_total": round(float(tot.min()), 2),
            "max_total": round(float(tot.max()), 2),
            "mean_per_ticket": round(float(pt.mean()), 3),
            "min_per_ticket": round(float(pt.min()), 3),
            "max_per_ticket": round(float(pt.max()), 3),
            "mean_tickets_per_day": round(
                float(np.mean([r["tickets_per_day"] for r in rows])), 2),
            "rows": rows}


def main():
    dates = sorted(p.stem for p in FEAT.glob("*.npz"))
    test = [d for d in dates if d >= "2025-08-01"]
    sub = test[::max(1, len(test) // 60)][:60]
    print(f"honesty: {len(dates)} feature days; battery on {len(sub)} test days",
          flush=True)
    res = {}
    res["poison"] = poison_check()
    print("poison:", res["poison"]["checks"], "checks",
          res["poison"]["mismatches"], "mismatches", flush=True)
    days = _days(sub)
    res["hold_zero"] = hold_zero(days)
    print("hold_zero:", res["hold_zero"], flush=True)
    res["cost_monotone"] = cost_monotone(days)
    print("cost_monotone:", res["cost_monotone"], flush=True)
    res["foresight_30"] = foresight(days)
    print("foresight_30:", res["foresight_30"], flush=True)
    res["foresight_30_nothresh"] = foresight(days, min_score=-np.inf,
                                             max_new=SM.MAX_TICKETS)
    print("foresight_30_nothresh:", res["foresight_30_nothresh"], flush=True)
    rc = random_control(days)
    res["random_30seeds"] = {k: v for k, v in rc.items() if k != "rows"}
    print("random_30:", res["random_30seeds"], flush=True)
    for p in (0.02, 0.005, 0.001):
        r = random_control(days, p_entry=p, label=f"RANDOM-p{p}")
        res[f"random_30seeds_p{p}"] = {k: v for k, v in r.items()
                                       if k != "rows"}
        print(f"random_30 p={p}:", res[f"random_30seeds_p{p}"], flush=True)
    (OUT / "honesty.json").write_text(json.dumps(res, indent=1))
    print("wrote", OUT / "honesty.json", flush=True)


if __name__ == "__main__":
    main()
