"""CLOSE-MOMENTUM (2026-09-16): the config runner over the decision-row
table, plus every control.

A CONFIG IS A SCORE. Selection is always: at each (date, decision) take
the top-k eligible rows by score; tickets are spent in decision order,
$15,000 x6 then $10,000, at most 7 concurrent and $100,000 a day, at most
one open ticket per symbol, 20%-of-trailing-5-minute size cap, $500
minimum, 10 bps a side (+50 outside 09:30-16:00, which no row here hits).
The reported row, the 30-seed random control, the inverted signal, the
shuffled-label control and the foresight control all go through the SAME
function; the only thing that differs is the score vector.

Anything fitted is fitted on Y1 (2024-10-22..2025-07-31) alone.

Usage:
  python plan/cm_single.py --stage profile|configs|controls|all
                           [--universe wide|gap]
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import cm_lib as L                                            # noqa: E402


class Table:
    def __init__(self, uni="wide"):
        z = np.load(L.OUT / f"rows_{uni}.npz", allow_pickle=False)
        self.uni = uni
        self.dates = [str(x) for x in z["dates"]]
        self.syms = [str(x) for x in z["syms"]]
        self.feat = [str(x) for x in z["features"]]
        self.dec = [str(x) for x in z["dec"]]
        self.exits = [str(x) for x in z["exits"]]
        self.date_i = z["date_i"]
        self.sym_i = z["sym_i"]
        self.dec_i = z["dec_i"].astype(np.int32)
        self.F = z["F"]
        self.printed_m = z["printed_m"]
        self.px_in = z["px_in"].astype(np.float64)
        self.volcap = z["volcap"].astype(np.float64)
        self.px_out = z["px_out"].astype(np.float64)
        self.fidx = {f: i for i, f in enumerate(self.feat)}
        self.xidx = {x: i for i, x in enumerate(self.exits)}
        self.didx = {d: i for i, d in enumerate(self.dec)}
        da = np.array(self.dates)
        self.date_s = da[self.date_i]
        self.split = np.array([L.split_of(d) for d in self.dates])[self.date_i]
        # rows grouped by (date, decision), pre-sorted once
        self.key = self.date_i.astype(np.int64) * 64 + self.dec_i
        self.order = np.argsort(self.key, kind="stable")
        k = self.key[self.order]
        self.grp_start = np.flatnonzero(np.r_[True, k[1:] != k[:-1]])
        self.grp_end = np.r_[self.grp_start[1:], len(k)]
        self.grp_key = k[self.grp_start]
        self.m_dec = np.array([L.idx(d) - 1 for d in self.dec])
        # per-date row groups, precomputed once: the shuffled control
        # permutes inside these, and rebuilding them per seed made the
        # control 40x slower than the row it controls.
        o = np.argsort(self.date_i, kind="stable")
        dd = self.date_i[o]
        st = np.flatnonzero(np.r_[True, dd[1:] != dd[:-1]])
        en = np.r_[st[1:], len(dd)]
        self.day_rows = [o[a:b] for a, b in zip(st, en)]

    def f(self, name):
        return self.F[:, self.fidx[name]]

    def ndays(self, split=None):
        if split is None:
            return len(self.dates)
        return int(sum(L.split_of(d) == split for d in self.dates))


# ------------------------------------------------------------------- run
def run(t, score, exit_lab, decs, topk=1, eligible=None, tickets=None,
        label=""):
    """Execute a config. Returns a list of trade dicts."""
    tickets = L.TICKETS if tickets is None else tickets
    xi = t.xidx[exit_lab]
    xm = L.idx(exit_lab)
    c_out = L.cost_frac(xm)
    dec_ids = [t.didx[d] for d in decs]
    elig = t.printed_m if eligible is None else (t.printed_m & eligible)
    elig = elig & np.isfinite(score) & np.isfinite(t.px_in) & (t.px_in > 0)
    elig = elig & np.isfinite(t.px_out[:, xi]) & (t.px_out[:, xi] > 0)
    # the exit must be strictly after the fill
    ok_dec = np.array([L.idx(d) < xm for d in t.dec])
    elig = elig & ok_dec[t.dec_i]

    trades = []
    gstart = {int(k): (s, e) for k, s, e in
              zip(t.grp_key, t.grp_start, t.grp_end)}
    for dnum in range(len(t.dates)):
        used = 0
        owned = set()
        for di in dec_ids:
            se = gstart.get(dnum * 64 + di)
            if se is None:
                continue
            rows = t.order[se[0]:se[1]]
            rows = rows[elig[rows]]
            if rows.size == 0:
                continue
            rows = rows[np.argsort(-score[rows], kind="stable")][:topk]
            m_in = t.m_dec[di] + 1
            c_in = L.cost_frac(m_in)
            for r in rows:
                if used >= len(tickets):
                    break
                s = int(t.sym_i[r])
                if s in owned:
                    continue
                px_in = t.px_in[r]
                sh = tickets[used] / px_in
                cap = t.volcap[r]
                if np.isfinite(cap):
                    sh = min(sh, cap)
                if sh * px_in < L.MIN_NOTIONAL:
                    continue
                used += 1
                owned.add(s)
                px_out = t.px_out[r, xi]
                cost = sh * px_in * (1.0 + c_in)
                trades.append({
                    "date": t.dates[dnum], "sym": t.syms[s], "row": int(r),
                    "dec": t.dec[di], "m_dec": int(t.m_dec[di]),
                    "m_in": int(m_in), "m_out": int(xm),
                    "px_in": float(px_in), "px_out": float(px_out),
                    "sh": float(sh), "notional": float(cost),
                    "pnl": float(sh * px_out * (1.0 - c_out) - cost),
                    "gross": float(sh * (px_out - px_in)),
                    "hold": int(xm - m_in), "i": s})
    return trades


def row(t, trades, label):
    return L.split_rows(trades, t.dates, label)


# -------------------------------------------------------------- controls
def random_control(t, exit_lab, decs, topk, eligible=None, seeds=30,
                   label="RANDOM"):
    """Same eligibility, window, fills, costs and ticket rate; the only
    difference is that the score is noise."""
    out = []
    for s in range(seeds):
        rng = np.random.default_rng(90_000 + s)
        sc = rng.random(len(t.px_in))
        tr = run(t, sc, exit_lab, decs, topk, eligible)
        out.append(L.summarize(tr, len(t.dates), f"{label}-s{s}"))
    return out


def percentile(value, controls, key="total"):
    v = np.array([c[key] for c in controls], float)
    return round(float((v < value).mean() * 100.0), 1)


def shuffled_control(t, score, exit_lab, decs, topk, eligible=None, seeds=10,
                     label="SHUFFLED"):
    """Permute the (fill, exit, cap) triple ACROSS ROWS WITHIN EACH DAY.

    This destroys the association between a row's features and its own
    outcome while preserving the day's outcome distribution, which is the
    corrected form of the control (plan/rl2/honesty.py's docstring: v1's
    control permuted the intraday path and produced a Brownian bridge
    worth hundreds of dollars a ticket)."""
    out = []
    for s in range(seeds):
        rng = np.random.default_rng(70_000 + s)
        t2 = _shuffle_day(t, rng)
        tr = run(t2, score, exit_lab, decs, topk, eligible)
        out.append(L.summarize(tr, len(t.dates), f"{label}-s{s}"))
    return out


class _View:
    """A Table with permuted outcome columns; everything else is shared."""

    def __init__(self, t):
        for k in ("uni", "dates", "syms", "feat", "dec", "exits", "date_i",
                  "sym_i", "dec_i", "F", "printed_m", "fidx", "xidx", "didx",
                  "date_s", "split", "key", "order", "grp_start", "grp_end",
                  "grp_key", "m_dec"):
            setattr(self, k, getattr(t, k))


def _shuffle_day(t, rng):
    v = _View(t)
    px_in = t.px_in.copy()
    px_out = t.px_out.copy()
    volcap = t.volcap.copy()
    for idx in t.day_rows:
        if idx.size < 2:
            continue
        perm = rng.permutation(idx.size)
        px_in[idx] = t.px_in[idx][perm]
        px_out[idx] = t.px_out[idx][perm]
        volcap[idx] = t.volcap[idx][perm]
    v.px_in, v.px_out, v.volcap = px_in, px_out, volcap
    return v


def foresight_score(t, exit_lab, dec=None):
    """Positive control: score = the realized net return of the very trade
    the decision would open. Must be strongly positive or a null has no
    power."""
    xi = t.xidx[exit_lab]
    c_in = L.cost_frac(L.idx(dec) if dec else L.idx("15:30"))
    c_out = L.cost_frac(L.idx(exit_lab))
    with np.errstate(all="ignore"):
        r = (t.px_out[:, xi] * (1 - c_out)) / np.maximum(
            t.px_in * (1 + c_in), 1e-9) - 1.0
    return np.where(np.isfinite(r), r, -np.inf)


def lookahead30_score(t):
    """The mandated foresight control in its 30-minute form: score = the
    return from the fill to the price 30 minutes later, i.e. 15:30->16:00
    for the last-half-hour decision."""
    return foresight_score(t, "15:59")


# --------------------------------------------------------------- stages
def stage_profile(t):
    """Unconditional expectancy: what a RANDOM eligible name pays for each
    (entry, exit) pair. This is the floor every hypothesis has to clear."""
    res = {}
    for dec in t.dec:
        for ex in t.exits:
            if L.idx(ex) <= L.idx(dec):
                continue
            rows = random_control(t, ex, [dec], topk=7, seeds=12,
                                  label=f"R-{dec}-{ex}")
            pt = np.array([r["per_ticket"] for r in rows])
            gt = np.array([r["total"] for r in rows])
            nt = np.array([r["tickets"] for r in rows])
            res[f"{dec}->{ex}"] = {
                "mean_per_ticket": round(float(pt.mean()), 2),
                "sd_per_ticket": round(float(pt.std(ddof=1)), 2),
                "mean_total": round(float(gt.mean()), 2),
                "mean_tickets": int(nt.mean()),
                "mean_per_month": round(float(gt.mean() / (len(t.dates)/21.0)), 2),
                "hold_min": L.idx(ex) - L.idx(dec)}
            print(f"  {dec}->{ex:6s} random x12: "
                  f"${res[f'{dec}->{ex}']['mean_per_ticket']:+7.2f}/tkt "
                  f"(sd {res[f'{dec}->{ex}']['sd_per_ticket']:.2f}) "
                  f"n={res[f'{dec}->{ex}']['mean_tickets']}", flush=True)
    return res


def gross_profile(t):
    """The same thing in GROSS terms and per name, with no ticket ladder:
    the mean net and gross return of every eligible row, by (entry, exit).
    This answers 'is there anything there at all before costs?'"""
    res = {}
    for di, dec in enumerate(t.dec):
        m_in = t.m_dec[di] + 1
        c_in = L.cost_frac(m_in)
        for ex in t.exits:
            if L.idx(ex) <= L.idx(dec):
                continue
            xi = t.xidx[ex]
            c_out = L.cost_frac(L.idx(ex))
            k = (t.dec_i == di) & t.printed_m & np.isfinite(t.px_in) \
                & (t.px_in > 0) & np.isfinite(t.px_out[:, xi]) \
                & (t.px_out[:, xi] > 0)
            if k.sum() < 100:
                continue
            g = t.px_out[k, xi] / t.px_in[k] - 1.0
            n = (t.px_out[k, xi] * (1 - c_out)) / (t.px_in[k] * (1 + c_in)) - 1
            res[f"{dec}->{ex}"] = {
                "rows": int(k.sum()),
                "gross_bps": round(float(g.mean() * 1e4), 2),
                "gross_bps_se": round(float(g.std(ddof=1) / np.sqrt(k.sum())
                                            * 1e4), 2),
                "gross_median_bps": round(float(np.median(g) * 1e4), 2),
                "net_bps": round(float(n.mean() * 1e4), 2),
                "gross_$_on_15k": round(float(g.mean() * 15000), 2),
                "net_$_on_15k": round(float(n.mean() * 15000), 2),
                "y1_gross_bps": round(float(
                    g[t.split[k] == 0].mean() * 1e4), 2),
                "y2_gross_bps": round(float(
                    g[t.split[k] == 1].mean() * 1e4), 2)}
    return res


if __name__ == "__main__":
    uni = sys.argv[sys.argv.index("--universe") + 1] \
        if "--universe" in sys.argv else "wide"
    stage = sys.argv[sys.argv.index("--stage") + 1] \
        if "--stage" in sys.argv else "profile"
    t = Table(uni)
    print(f"{uni}: {len(t.px_in):,} rows, {len(t.dates)} dates, "
          f"{len(t.syms)} symbols, decisions {t.dec}", flush=True)
    if stage in ("profile", "all"):
        gp = gross_profile(t)
        L.write_json(f"gross_profile_{uni}.json", gp)
        print("\n== unconditional gross/net per eligible row ==")
        for k, v in gp.items():
            print(f"  {k:16s} n={v['rows']:7,d}  gross {v['gross_bps']:+7.2f}"
                  f" +/- {v['gross_bps_se']:.2f} bp   net {v['net_bps']:+7.2f}"
                  f" bp   (${v['net_$_on_15k']:+7.2f} on $15k)   "
                  f"y1 {v['y1_gross_bps']:+6.2f} y2 {v['y2_gross_bps']:+6.2f}")
        print("\n== random-pick ticket expectancy ==")
        pr = stage_profile(t)
        L.write_json(f"rand_profile_{uni}.json", pr)
