"""OPEN-UNIVERSE (2026-09-17) TEST 3: limit-at-bid entries on the open
universe's own picks.

UNIVERSE+QUOTES measured that on the causal wide HALAL universe, moving the
entry from a market order to a resting limit was worth **+$2,460/month** --
the single largest lever any line in this repo found -- and that the gain is
exactly the entry-side fee: $/ticket-FILLED is flat from a 0 to a 50 bps
offset because price improvement and adverse selection cancel to within a
basis point.

The open universe changes the size of that lever in a way worth measuring
rather than assuming.  UQ's gain was large partly because the incumbent
ladder charges 10 bps a side on books whose measured half-spread is 2.77.
On the top-600 slice the measured half-spread is **2.83 bps**, so the most a
limit entry can recover is about **$4.25 a ticket** -- and against that sits
the fill rate, which is the thing that cannot be assumed.

THE FILL RULE is plan/uq_fills.py's, restated so the poison test can be
scored against it:
  * at t0 = the start of minute m+1 -- the same instant the baseline table
    fills at -- post a buy limit at  L = mark(m) * (1 - k/10000), where
    mark(m) is the last printed close at or before minute m, a quantity
    plan/rl2/honesty.py proves is a function of bars <= m only;
  * it FILLS iff some 1-second bar in (t0, t0 + N*60s] has `l` <= L.  A
    1-second aggregate's `l` IS the minimum trade price in that second, so
    this is exact, not an approximation -- /v3/quotes and /v3/trades are 403
    on this tier and are not needed for this question;
  * the fill price is L, never better, although a gap through the limit
    would really fill at or inside it (the conservative side);
  * if it does not fill, NO TRADE happens and the ticket books $0.

The DECISION to post is a function of information <= t0.  The FILL is
revealed by prints strictly after t0.  That asymmetry is legitimate and is
the only honest way to grade an unexecuted limit.

ENTRY COST.  A resting limit that someone else crossed to does not pay the
half-spread, it earns it -- but it still pays adverse selection and the
impact of the size it took.  `cr_cost`'s `passive=True` convention charges
the impact term alone, which is strictly more expensive than
UNIVERSE-QUOTES' `passive_bps = 0.0`, and that is what is used here.

Usage:
  python plan/ou_limit.py --stage pairs   [--dates 448] [--k 10] [--wait 1]
  python plan/ou_limit.py --stage fetch   [--workers 32]
  python plan/ou_limit.py --stage score
"""
import gzip
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ou_lib as L                                            # noqa: E402
import ou_cost as OC                                          # noqa: E402
import ou_rank as OR                                          # noqa: E402
import ou_table as OTB                                        # noqa: E402

ET = ZoneInfo("America/New_York")
XDIR = L.ROOT / "data" / "massive" / "trades"
PAIRS_F = L.OUT / "limit_pairs.json"
PICKS_F = L.OUT / "limit_picks.json"
OFFSETS = [0.0, 2.0, 5.0, 10.0, 20.0, 30.0, 50.0]
WAITS = [1, 3, 5]


def _bar_ms(date, grid_min):
    """Epoch ms of the START of grid minute `grid_min` (04:00 base) in ET."""
    y, m, d = (int(x) for x in date.split("-"))
    base = datetime(y, m, d, 4, 0, tzinfo=ET).timestamp()
    return int((base + grid_min * 60) * 1000)


def candidate_policies():
    """The orderings the sweep put on top, plus the account-legal k."""
    sw = L.load("sweep.json")
    out = []
    for hh in ("h15", "h30", "h60"):
        for r in sw.get(hh, {}).get("rows", [])[:3]:
            f = r["ordering"][:-1]
            sg = 1 if r["ordering"].endswith("+") else -1
            out.append({"f": f, "sign": sg, "dec": r["dec"], "h": hh})
    seen, uniq = set(), []
    for c in out:
        k = (c["f"], c["sign"], c["dec"], c["h"])
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return uniq[:6]


def stage_pairs(topk=7):
    t = OR.OT()
    cands = candidate_policies()
    picks = []
    for c in cands:
        sc = t.f(c["f"]).astype(np.float64) * c["sign"]
        m = t.mask(split=None, dec=c["dec"], h=c["h"])
        pk = OR.picks(t, sc, m, topk)
        picks.append({"policy": c, "rows": [int(x) for x in pk]})
    # the 30-seed random control needs a tape too, but only ONE seed's worth
    # of symbol-days is fetched: the control is re-drawn from the SAME
    # candidate pool, so its fill statistics are estimated on that sample and
    # the estimate is reported with its own n.
    rng = np.random.default_rng(4242)
    m = t.mask(split=None, dec="10:00", h="h30")
    pk = OR.picks(t, rng.random(len(t.pnl["h30"])), m, topk)
    picks.append({"policy": {"f": "RANDOM", "sign": 1, "dec": "10:00",
                             "h": "h30"}, "rows": [int(x) for x in pk]})
    allrows = sorted({r for p in picks for r in p["rows"]})
    pairs = sorted({(t.sym_s[r], t.date_s[r]) for r in allrows})
    todo = [[s, d] for s, d in pairs
            if not (XDIR / f"{s}_{d}.json.gz").exists()]
    PAIRS_F.write_text(json.dumps(todo))
    PICKS_F.write_text(json.dumps(picks))
    print(f"[limit] {len(cands)} policies + random, {len(allrows):,} picks, "
          f"{len(pairs):,} distinct symbol-days, {len(todo):,} to fetch",
          flush=True)
    return todo


def stage_fetch(workers=32):
    if not PAIRS_F.exists():
        raise SystemExit("run --stage pairs first")
    cmd = [sys.executable, "-u", str(HERE / "uq_sec1.py"),
           "--pairs", str(PAIRS_F), "--workers", str(workers)]
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(L.ROOT), check=False)


def _sec_rows(sym, date):
    f = XDIR / f"{sym}_{date}.json.gz"
    if not f.exists():
        return None
    try:
        with gzip.open(f, "rt") as h:
            return json.load(h).get("rows") or []
    except Exception:
        return None


def _mark_and_bars(sym, date, cache):
    key = (sym, date)
    if key in cache:
        return cache[key]
    rec = OTB.load_symbol(sym)
    val = None
    if rec is not None:
        ds, o, h, l, c, v = rec
        di = {d: i for i, d in enumerate(ds)}
        if date in di:
            i = di[date]
            val = (o[i].astype(np.float64), c[i].astype(np.float64))
    if len(cache) > 400:
        cache.clear()
    cache[key] = val
    return val


def stage_score(topk=7):
    import wn_table as WT
    t = OR.OT()
    picks = json.loads(PICKS_F.read_text())
    cm = OC.MinuteCost()
    bars = {}
    out = []
    for blk in picks:
        pol = blk["policy"]
        rows = np.array(blk["rows"], int)
        h = pol["h"]
        H = dict(zip(WT.HNAMES, WT.HORIZONS))[h]
        dec_g = int(WT.STEPS[WT.DEC_T[t.dec.index(pol["dec"])]])
        for k_bps in OFFSETS:
            for nwait in WAITS:
                pnl, nfill, ntry = [], 0, 0
                dts = []
                for r in rows:
                    sym, date = str(t.sym_s[r]), str(t.date_s[r])
                    b = _mark_and_bars(sym, date, bars)
                    sec = _sec_rows(sym, date)
                    if b is None or sec is None:
                        continue
                    o_, c_ = b
                    ntry += 1
                    dts.append(date)
                    # mark(m): last printed close at or before the decision
                    w = c_[:dec_g + 1]
                    w = w[np.isfinite(w)]
                    if not w.size:
                        pnl.append(0.0)
                        continue
                    mark = float(w[-1])
                    lim = mark * (1.0 - k_bps / 1e4)
                    t0 = _bar_ms(date, dec_g + 1)
                    t1 = t0 + nwait * 60_000
                    lo = None
                    fill_ms = None
                    for row in sec:
                        ts = row[0]
                        if ts <= t0:
                            continue
                        if ts > t1:
                            break
                        if row[3] <= lim:
                            fill_ms = ts
                            break
                    if fill_ms is None:
                        pnl.append(0.0)
                        continue
                    fill_g = dec_g + 1 + int((fill_ms - t0) // 60_000)
                    fill_g = min(fill_g, L.NMIN - 1)
                    # exit: first printed minute at or after fill + H, else
                    # the day's last print (forced flatten)
                    pr = np.isfinite(c_)
                    last = int(np.max(np.flatnonzero(pr))) if pr.any() else -1
                    want = min(fill_g + H, L.NMIN - 1) if H < 10 ** 5 else last
                    nx = np.flatnonzero(pr[want:])
                    ex_g = (want + int(nx[0])) if nx.size else last
                    if ex_g > last or ex_g < 0:
                        ex_g = last
                    if ex_g < fill_g or last < 0:
                        pnl.append(0.0)
                        continue
                    ex_px = float(o_[ex_g]) if np.isfinite(o_[ex_g]) \
                        else float(c_[ex_g])
                    if not np.isfinite(ex_px) or ex_px <= 0:
                        pnl.append(0.0)
                        continue
                    no = min(L.TICKET, float(t.notional[r]) or L.TICKET)
                    c_en = cm.cost_bps(sym, date, fill_g, no, passive=True) / 1e4
                    c_ex = cm.cost_bps(sym, date, ex_g, no) / 1e4
                    ret = (ex_px * (1 - c_ex)) / (lim * (1 + c_en)) - 1.0
                    pnl.append(no * ret)
                    nfill += 1
                if ntry == 0:
                    continue
                pnl = np.array(pnl)
                r_ = OR.score_stats(t, pnl, rows[:len(pnl)],
                                    f"{pol['f']}{'+' if pol['sign'] > 0 else '-'}"
                                    f"|{pol['dec']}|{h}|LIM{k_bps:.0f}"
                                    f"/{nwait}m")
                r_["fill_rate"] = round(nfill / ntry, 4)
                r_["per_ticket_filled"] = round(
                    float(pnl[pnl != 0].mean()), 2) if (pnl != 0).any() else None
                r_["attempts"] = int(ntry)
                out.append(r_)
    out.sort(key=lambda r: -r["per_month"])
    L.write("limit.json", {"rows": out, "cost_report": cm.report()})
    for r in out[:20]:
        print(f"[limit] {r['label']:44s} fill {r['fill_rate']:.3f} "
              f"${r['per_month']:+9,.0f}/mo ${r['per_ticket']:+7.2f}/tkt "
              f"filled ${r['per_ticket_filled']}", flush=True)


def main():
    st = "pairs"
    if "--stage" in sys.argv:
        st = sys.argv[sys.argv.index("--stage") + 1]
    if st == "pairs":
        stage_pairs()
    elif st == "fetch":
        w = 32
        if "--workers" in sys.argv:
            w = int(sys.argv[sys.argv.index("--workers") + 1])
        stage_fetch(w)
    else:
        stage_score()


if __name__ == "__main__":
    main()
