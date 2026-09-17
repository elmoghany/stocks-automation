"""CLOSE-MOMENTUM (2026-09-16): controls for every row that is worth a
second look.

For each candidate config this runs, on the SAME eligibility, window,
fills, exit bar, topk and costs:

  RANDOM    30 seeds of uniform noise as the score -- the distribution the
            config's total and total-EX-BEST-DAY are scored against.
  INVERTED  the same score with its sign flipped. A real signal should
            lose roughly as much as it wins; a config that is positive
            with BOTH signs is measuring the window, not the signal.
  SHUFFLED  10 seeds with the (fill price, exit price, size cap) triple
            permuted across rows within each day, which destroys the
            feature->outcome association and nothing else.
  BOOTSTRAP 2,000 resamples of the config's own DAILY P&L series -- the
            honest sampling error on $/month, which is what decides
            whether a +$300/month row is distinguishable from zero.

The percentile leg of the pass bar is reported but flagged: rl2 §3.8(b)
showed that a policy's ticket-rate and entry-time profile alone can score
90+ percentile, and that a shuffled-target model scored HIGHER than the
real one. $/month net and the shuffled control are the metrics that mean
something.

Usage:  python plan/cm_controls.py [--universe wide] [--top 12]
Writes: data/massive/cm/controls_{universe}.json
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import cm_lib as L                                            # noqa: E402
import cm_configs as C                                        # noqa: E402
import cm_single as S                                         # noqa: E402

NRAND = 30
NSHUF = 10
NBOOT = 2000


def daily_series(trades, dates):
    by = {}
    for x in trades:
        by[x["date"]] = by.get(x["date"], 0.0) + x["pnl"]
    return np.array([by.get(d, 0.0) for d in dates])


def bootstrap(trades, dates, n=NBOOT, seed=0):
    ser = daily_series(trades, dates)
    if ser.size == 0:
        return {}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, ser.size, size=(n, ser.size))
    tot = ser[idx].sum(axis=1)
    per_month = tot / (len(dates) / 21.0)
    se = ser.std(ddof=1) / np.sqrt(ser.size)
    return {"per_month_p5": round(float(np.percentile(per_month, 5)), 1),
            "per_month_p50": round(float(np.percentile(per_month, 50)), 1),
            "per_month_p95": round(float(np.percentile(per_month, 95)), 1),
            "p_total_le_0": round(float((tot <= 0).mean()), 4),
            "daily_mean": round(float(ser.mean()), 2),
            "daily_t": round(float(ser.mean() / se) if se > 0 else 0.0, 2)}


def one(t, name, score, decs, exit_lab, topk, gate=None, seed0=0):
    tr = S.run(t, score, exit_lab, decs, topk=topk, eligible=gate)
    base = L.split_rows(tr, t.dates, name)
    inv = S.run(t, -np.asarray(score, float), exit_lab, decs, topk=topk,
                eligible=gate)
    rnd = [L.summarize(S.run(t, np.random.default_rng(90_000 + s)
                             .random(len(t.px_in)), exit_lab, decs,
                             topk=topk, eligible=gate),
                       len(t.dates), f"RAND-s{s}") for s in range(NRAND)]
    shf = []
    for s in range(NSHUF):
        t2 = S._shuffle_day(t, np.random.default_rng(70_000 + s))
        shf.append(L.summarize(S.run(t2, score, exit_lab, decs, topk=topk,
                                     eligible=gate), len(t.dates),
                               f"SHUF-s{s}"))
    rt = np.array([r["total"] for r in rnd])
    rx = np.array([r["ex_best_total"] for r in rnd])
    rp = np.array([r["per_ticket"] for r in rnd])
    st = np.array([r["total"] for r in shf])
    a = base["all"]
    return {
        "row": base,
        "inverted": L.summarize(inv, len(t.dates), name + "-INV"),
        "random": {"n": NRAND,
                   "mean_total": round(float(rt.mean()), 1),
                   "sd_total": round(float(rt.std(ddof=1)), 1),
                   "mean_per_ticket": round(float(rp.mean()), 2),
                   "sd_per_ticket": round(float(rp.std(ddof=1)), 2),
                   "mean_tickets": int(np.mean([r["tickets"] for r in rnd]))},
        "shuffled": {"n": NSHUF,
                     "mean_total": round(float(st.mean()), 1),
                     "mean_per_ticket": round(
                         float(np.mean([r["per_ticket"] for r in shf])), 2)},
        "pctile_total": round(float((rt < a["total"]).mean() * 100), 1),
        "pctile_ex_best": round(float((rx < a["ex_best_total"]).mean() * 100),
                                1),
        "edge_vs_random_per_ticket": round(
            a["per_ticket"] - float(rp.mean()), 2),
        "bootstrap": bootstrap(tr, t.dates, seed=seed0),
    }


def candidates(t):
    """Everything worth controlling: the pre-registered last-hour rows (so
    the null is stated with its own controls, not just asserted), plus the
    best rows of the sweep at every ticket rate."""
    cfg = json.loads((L.OUT / f"configs_{t.uni}.json").read_text())
    spec_by_name = {}
    for s in C.specs(t):
        spec_by_name[s["name"]] = s
    want = []
    # pre-registered: the published hypothesis, stated with controls
    for nm in ("H1-first|15:59|k7", "H1-first|15:59|k1", "H1-mid|15:59|k7",
               "H1x-rank-first|15:59|k7", "H4-dm-sum|15:59|k7",
               "H4-flat@15:30|15:59|k7", "H2-rvol@15:00|15:59|k1",
               "H2-rvol@15:30|15:59|k1", "H3-flat@12:00->15:59|15:59|k7"):
        if nm in cfg:
            want.append(nm)
    # plus the best of the sweep by $/month and by $/ticket
    rows = sorted(cfg.items(), key=lambda kv: -kv[1]["all"]["per_month"])
    want += [k for k, _ in rows[:10]]
    rows = sorted(cfg.items(), key=lambda kv: -kv[1]["all"]["per_ticket"])
    want += [k for k, _ in rows[:6]]
    seen, out = set(), []
    for nm in want:
        if nm in seen:
            continue
        seen.add(nm)
        base, ex, kk = nm.rsplit("|", 2)
        sp = spec_by_name.get(base)
        if sp is None:
            continue
        out.append((nm, sp, ex, int(kk[1:])))
    return out


def main():
    uni = sys.argv[sys.argv.index("--universe") + 1] \
        if "--universe" in sys.argv else "wide"
    t = S.Table(uni)
    cands = candidates(t)
    print(f"{len(cands)} candidates on {uni}", flush=True)
    res = {}
    for i, (nm, sp, ex, k) in enumerate(cands):
        res[nm] = one(t, nm, sp["score"], sp["decs"], ex, k, sp["gate"], i)
        r = res[nm]
        a = r["row"]["all"]
        print(f"[{i+1}/{len(cands)}] {nm:34s} n={a['tickets']:5d} "
              f"${a['per_ticket']:+8.2f}/tkt ${a['per_month']:+8.1f}/mo | "
              f"rand ${r['random']['mean_per_ticket']:+7.2f} "
              f"(pct {r['pctile_total']:5.1f} / exbest {r['pctile_ex_best']:5.1f}) "
              f"| inv ${r['inverted']['per_ticket']:+7.2f} "
              f"| shuf ${r['shuffled']['mean_per_ticket']:+7.2f} "
              f"| boot p5 {r['bootstrap'].get('per_month_p5', 0):+8.1f} "
              f"t={r['bootstrap'].get('daily_t', 0):+5.2f}", flush=True)
    L.write_json(f"controls_{uni}.json", res)
    print("wrote", L.OUT / f"controls_{uni}.json", flush=True)


if __name__ == "__main__":
    main()
