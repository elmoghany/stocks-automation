"""OPEN-UNIVERSE (2026-09-17) TEST 2, step 2: the ticket table and the
top-k policies on the open universe's minute subset.

WIDE-NET's step 1 was "take the top 30 per day and find the pattern on which a
$15k purchase usually wins".  This is the same sweep on a universe 10x wider
and, crucially, 60x more liquid: TOP-30 BY SEVERAL CAUSAL ORDERINGS x 14
DECISION TIMES x 5 HORIZONS, then the account-legal top-k policies (k = 1, 3,
5, 7 tickets a day at $15,000, <= $100,000 a day).

EVERY ROW IS REPORTED UNDER TWO COST MODELS, per the mandate:
  flat10    the incumbent ladder, already folded into the table's `pnl_*`
  measured  plan/ou_cost.MinuteCost -- max(Corwin-Schultz, Abdi-Ranaldo) on
            trailing 1-minute bars plus the Y = 1.0 square-root impact term,
            per (name, minute), re-priced from the stored legs.

CONTROLS, identical eligibility and identical fills in every case:
  * 30-seed RANDOM ordering over the same candidate set;
  * INVERTED (the ordering with its sign flipped) -- it is one of the sweep's
    own rows by construction;
  * SHUFFLED labels (the P&L vector permuted within each cross-section), which
    must land on the random control.

CAUSALITY.  Every ordering is a column of the table's feature block, which
plan/rl2/honesty.py poison-tested 64/64 and plan/ou_poison.py re-tests on this
cache: replacing every bar after the decision minute with garbage moves no
feature and no pick.

Usage:
  python plan/ou_rank.py --stage sweep     [--h h30]
  python plan/ou_rank.py --stage policy
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ou_lib as L                                            # noqa: E402
import ou_cost as OC                                          # noqa: E402
from wn_lib import Table, HNAMES                              # noqa: E402

RTH_DEC = ["09:35", "09:45", "10:00", "10:30", "11:00", "12:00", "13:00",
           "14:00", "15:00"]
# the causal orderings swept.  Each is a feature of the table's own block, so
# each is already covered by the poison test; both signs are always run.
ORDERINGS = ["ret_since_open", "dist_vwap_day", "dist_vwap30", "ret5",
             "ret15", "ret30", "ret60", "rvol_profile", "rvol30", "dv_burst",
             "log_dv5", "bar_range5", "amihud30", "gap_vs_prevclose",
             "dist_hi", "dist_lo", "log_price", "log_mdv20", "prev_day_ret",
             "xs_rank_ret30", "coil", "print_density30"]
SEEDS = 30


class OT(Table):
    """The open-universe table plus measured-cost re-pricing."""

    def __init__(self, path=None):
        super().__init__(path or (L.OUT / "table.npz"))
        z = np.load(path or (L.OUT / "table.npz"), allow_pickle=False)
        self.expx = {h: z["expx_" + h] for h in HNAMES}
        self.exmin = {h: z["exmin_" + h].astype(np.int32) for h in HNAMES}
        self.sym_s = np.array(self.syms)[self.sym_i]
        import wn_table as WT
        self.ent_min = np.minimum(WT.STEPS[WT.DEC_T] + 1,
                                  L.NMIN - 1)[self.dec_i]
        self._mp = {}

    # ---- identity gate: the flat ladder on the stored legs must reproduce
    # ---- wn_table.day_block's own pnl_* to float32
    def flat_pnl(self, h):
        en = self.fill_px
        ex = self.expx[h]
        c_en = L.cost_frac(self.ent_min)
        c_ex = L.cost_frac(self.exmin[h])
        with np.errstate(all="ignore"):
            r = (ex * (1.0 - c_ex)) / np.maximum(en * (1.0 + c_en), 1e-9) - 1.0
        return np.where(self.ok[h], self.notional * np.nan_to_num(r), 0.0)

    def measured_pnl(self, h, rows, cm=None):
        """Measured-cost P&L for a SUBSET of rows (the picks), $ per ticket."""
        cm = cm or self._mp.setdefault("cm", OC.MinuteCost())
        sy = self.sym_s[rows]
        dt = self.date_s[rows]
        no = self.notional[rows]
        c_en = cm.vec(sy, dt, self.ent_min[rows], no) / 1e4
        ex = self.expx[h][rows]
        en = self.fill_px[rows]
        with np.errstate(all="ignore"):
            gross = ex / np.maximum(en, 1e-9)
        c_ex = cm.vec(sy, dt, self.exmin[h][rows],
                      no * np.nan_to_num(gross, nan=1.0)) / 1e4
        with np.errstate(all="ignore"):
            r = gross * (1.0 - c_ex) / (1.0 + c_en) - 1.0
        return np.where(self.ok[h][rows], no * np.nan_to_num(r), 0.0)


def picks(t, score, mask, topk):
    """Row indices of the top-k per (date, decision time) inside `mask`."""
    idx = np.flatnonzero(mask & np.isfinite(score))
    if idx.size == 0:
        return np.zeros(0, int)
    key = t.date_i[idx].astype(np.int64) * 64 + t.dec_i[idx]
    order = np.lexsort((-score[idx], key))
    idx, key = idx[order], key[order]
    first = np.r_[True, key[1:] != key[:-1]]
    starts = np.flatnonzero(first)
    ends = np.r_[starts[1:], len(idx)]
    return np.concatenate([idx[s:min(s + topk, e)]
                           for s, e in zip(starts, ends)])


def score_stats(t, pnl, rows, label):
    d = t.date_s[rows]
    by = {}
    for dd, p in zip(d, pnl):
        by[dd] = by.get(dd, 0.0) + float(p)
    ds = sorted(by)
    return L.summarise(np.array([by[x] for x in ds]), ds,
                       np.asarray(pnl, float), label)


def ic_of(t, score, mask, h):
    """Mean cross-sectional Spearman rank IC of `score` against the label."""
    idx = np.flatnonzero(mask & np.isfinite(score) & t.ok[h])
    if idx.size == 0:
        return np.nan
    key = t.date_i[idx].astype(np.int64) * 64 + t.dec_i[idx]
    order = np.argsort(key, kind="stable")
    idx, key = idx[order], key[order]
    starts = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
    ends = np.r_[starts[1:], len(idx)]
    lab = t.pnl[h]
    out = []
    for s, e in zip(starts, ends):
        if e - s < 20:
            continue
        v = L.spearman(score[idx[s:e]], lab[idx[s:e]])
        if np.isfinite(v):
            out.append(v)
    return float(np.mean(out)) if out else np.nan


def stage_sweep(t, h="h30", split=1, topn=30):
    """Top-30 by every causal ordering x decision time, on the OOS split."""
    rows = []
    for dec in RTH_DEC:
        m = t.mask(split=split, dec=dec, h=h)
        if m.sum() < 100:
            continue
        for f in ORDERINGS:
            if f not in t.fidx:
                continue
            base = t.f(f).astype(np.float64)
            for sg in (1, -1):
                sc = base * sg
                pk = picks(t, sc, m, topn)
                if pk.size == 0:
                    continue
                pn = t.pnl[h][pk]
                rows.append({
                    "ordering": f"{f}{'+' if sg > 0 else '-'}",
                    "dec": dec, "h": h, "topn": topn,
                    "tickets": int(pk.size),
                    "per_ticket_flat10": round(float(pn.mean()), 2),
                    "ic": round(float(ic_of(t, sc, m, h)), 4)})
    rows.sort(key=lambda r: -r["per_ticket_flat10"])
    # matched random control on the same mask, same top-30 count
    ctl = []
    for k in range(SEEDS):
        rng = np.random.default_rng(900 + k)
        m = t.mask(split=split, dec="10:00", h=h)
        sc = rng.random(len(t.pnl[h]))
        pk = picks(t, sc, m, topn)
        ctl.append(float(t.pnl[h][pk].mean()))
    return {"rows": rows[:40], "worst": rows[-10:],
            "n_rows": len(rows),
            "random_top30_per_ticket": round(float(np.mean(ctl)), 2),
            "random_sd": round(float(np.std(ctl, ddof=1)), 2)}


def stage_policy(t, cands, split=1, ks=(1, 3, 5, 7), hs=("h15", "h30", "h60"),
                 measured=True):
    """Account-legal top-k policies for the candidate orderings."""
    out = []
    cm = OC.MinuteCost()
    for f, sg, dec in cands:
        sc = t.f(f).astype(np.float64) * sg
        for h in hs:
            m = t.mask(split=split, dec=dec, h=h)
            for k in ks:
                pk = picks(t, sc, m, k)
                if pk.size == 0:
                    continue
                r = score_stats(t, t.pnl[h][pk], pk,
                                f"{f}{'+' if sg > 0 else '-'}|{dec}|{h}|k{k}")
                r["cost_model"] = "flat10"
                r["ic"] = round(float(ic_of(t, sc, m, h)), 4)
                out.append(r)
                if measured:
                    mp = t.measured_pnl(h, pk, cm)
                    rm = score_stats(t, mp, pk, r["label"])
                    rm["cost_model"] = "measured"
                    out.append(rm)
    out.sort(key=lambda r: -r["per_month"])
    return out, cm.report()


def controls(t, dec, h, k, split=1, seeds=SEEDS):
    m = t.mask(split=split, dec=dec, h=h)
    rnd = []
    for s in range(seeds):
        rng = np.random.default_rng(1300 + s)
        pk = picks(t, rng.random(len(t.pnl[h])), m, k)
        rnd.append(score_stats(t, t.pnl[h][pk], pk, f"rand{s}"))
    return rnd


def main():
    stage = "sweep"
    if "--stage" in sys.argv:
        stage = sys.argv[sys.argv.index("--stage") + 1]
    h = "h30"
    if "--h" in sys.argv:
        h = sys.argv[sys.argv.index("--h") + 1]
    t = OT()
    print(f"table: {len(t.pnl[h]):,} rows, {len(t.dates)} dates, "
          f"{len(t.syms)} symbols, splits "
          f"{[int((t.split == i).sum()) for i in (0, 1, 2)]}", flush=True)
    if stage == "sweep":
        res = {}
        for hh in ("h15", "h30", "h60", "h120", "flat"):
            res[hh] = stage_sweep(t, hh)
            top = res[hh]["rows"][0]
            print(f"[sweep] {hh}: best top-30 {top['ordering']:>22s} @"
                  f"{top['dec']} ${top['per_ticket_flat10']:+7.2f}/tkt "
                  f"(IC {top['ic']:+.4f})   random "
                  f"${res[hh]['random_top30_per_ticket']:+7.2f}", flush=True)
        L.write("sweep.json", res)
    elif stage == "policy":
        sw = L.load("sweep.json")
        cands = []
        for hh in sw:
            for r in sw[hh]["rows"][:6]:
                f = r["ordering"][:-1]
                sg = 1 if r["ordering"].endswith("+") else -1
                if (f, sg, r["dec"]) not in cands:
                    cands.append((f, sg, r["dec"]))
        cands = cands[:12]
        rows, rep = stage_policy(t, cands)
        for r in rows[:15]:
            print(f"[policy] {r['label']:44s} {r['cost_model']:8s} "
                  f"${r['per_month']:+9,.0f}/mo ${r['per_ticket']:+7.2f}/tkt "
                  f"n={r['tickets']:5d} Y1 {r['y1_per_month']} Y2 "
                  f"{r['y2_per_month']}", flush=True)
        L.write("policy.json", {"rows": rows, "cost_report": rep,
                                "candidates": cands})
    print("done", flush=True)


if __name__ == "__main__":
    main()
