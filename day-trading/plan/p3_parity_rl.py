"""PAPER-3BOOK parity test for the RL book.

Replays held-out days (2025-08-01 .. 2026-08-06) through plan/p3_rl.py's
LIVE engine, using the historical minute caches (data/massive/m1w, then
m1) as if they were the live feed, and compares with the backtest's own
trade dump (plan/crs_rl2_legs.json "RULE" = rl2 sim.run_day + rules.py,
published to the cent).

  * the engine is driven INCREMENTALLY: advance() is called at wall m+1
    (bar m complete: decide) and m+2 (bar m+1 complete: fill) for every
    5-minute step, exactly as the live session calls it;
  * STRICT mode (--strict-days N, default 12): on those days every call
    gets arrays physically truncated to the bars <= now-1, so nothing
    after the decision minute exists in memory; the result must be
    identical to the fast mode (asserted).

  python plan/p3_parity_rl.py [--days all|N] [--strict-days 12]
  -> data/paper/parity/rl.json
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p3_lib as P                                            # noqa: E402
import p3_rl as R                                             # noqa: E402

UNI = HERE / "rl2" / "out" / "universe"
LEGS = HERE / "crs_rl2_legs.json"
OUT = P.DATA / "paper" / "parity" / "rl.json"


def day_arrays(date):
    rows = json.loads((UNI / f"{date}.json").read_text())
    syms, arrs = [], []
    feed = P.CacheFeed(date, P.NMIN + 1)
    for r in sorted(rows, key=lambda r: r["symbol"]):
        b = feed.bars(r["symbol"])
        if b is None:
            continue
        syms.append(r["symbol"])
        arrs.append(b)
    A = [np.vstack([b[k] for b in arrs]) for k in range(5)]
    return syms, A


def run_day(date, cfg, strict=False, fee=R.FEE_BPS, vwap_from=0):
    syms, A = day_arrays(date)
    eng = R.Engine(cfg, syms, fee=fee)
    full = R.BarSrc(syms, *A, vwap_from=vwap_from)
    last = R.LAST_STEP if cfg["flat_bar"] is None else cfg["flat_bar"] - 1
    calls = sorted({n for m in range(330, last + 1, R.STEP)
                    for n in (m + 1, m + 2)} | {P.NMIN})
    if cfg["flat_bar"] is not None:
        calls = sorted(set(calls) | {cfg["flat_bar"] + 1})
    for now in calls:
        now = min(now, P.NMIN)
        src = (R.BarSrc(syms, *[a[:, :now] for a in A], vwap_from=vwap_from)
               if strict else full)
        eng.advance(src, now, eod=(now >= P.NMIN))
        if eng.st["done"]:
            break
    return eng.st["trades"]


class EmuSnapSrc(R.SnapSrc):
    """The LIVE snapshot code path (SnapSrc.view's scan branch) fed with
    snapshots synthesised from the cached bars exactly as the scan would
    report them at wall m+1 (px = last trade <= m, tt = minute of that
    trade, vwap = 04:00 VWAP), and bars only for marks/fills of held names
    -- i.e. what the agent would have."""

    def __init__(self, syms, A):
        self.syms = list(syms)
        self.full = R.BarSrc(syms, *A)
        b = self.full
        idx = np.where(b.printed, np.arange(b.N)[None, :], -1)
        np.maximum.accumulate(idx, axis=1, out=idx)
        self.snaps = {}
        for m in range(330, 721, R.STEP):
            vw = b.cdv[:, m] / np.maximum(b.cvol[:, m], 1.0)
            self.snaps[m] = {s_: dict(px=float(b.cf[i, m]),
                                      tt=int(idx[i, m]) if idx[i, m] >= 0 else None,
                                      vwap=float(vw[i]) if b.cvol[i, m] > 0 else float("nan"))
                             for i, s_ in enumerate(self.syms)
                             if np.isfinite(b.cf[i, m])}

    def _bars(self, i):
        return None

    def mark(self, i, m):
        return self.full.mark(i, m)

    def open_at(self, i, k):
        return self.full.open_at(i, k)

    def last_close(self, i, k):
        return self.full.last_close(i, k)


def snap_path_parity(dates, live_trades):
    base = {(t["date"], t["sym"], t["m_in"], round(t["px_in"], 6),
             t["m_out"], round(t["px_out"], 6)) for t in live_trades}
    got = set()
    for d in dates:
        syms, A = day_arrays(d)
        eng = R.Engine(R.CFG_LIVE, syms)
        src = EmuSnapSrc(syms, A)
        for now in sorted({n for m in range(330, 719, R.STEP)
                           for n in (m + 1, m + 2)} | {720}):
            eng.advance(src, now)
        for t in eng.st["trades"]:
            got.add((d, t["sym"], t["m_in"], round(t["px_in"], 6),
                     t["m_out"], round(t["px_out"], 6)))
    return dict(bars_path=len(base), snapshot_path=len(got),
                identical=len(base & got),
                pct=round(100.0 * len(base & got) / max(len(base), 1), 2),
                only_bars=sorted(map(list, base - got))[:10],
                only_snap=sorted(map(list, got - base))[:10])


def watcher_parity(trades_by_day, max_days=40):
    """Drive p3_rl.watch_exit (the paper_watch.py EXIT_MODE rl hook) minute
    by minute on each live-config trade and compare with the engine's exit."""
    n = ok = 0
    bad = []
    for d in sorted(trades_by_day)[:max_days]:
        for t in trades_by_day[d]:
            st = dict(sym=t["sym"], entry=t["px_in"], model_entry=None,
                      decision_min=t["step_in"], shares=t["sh"])
            got = None
            for now in range(t["step_in"] + 2, 721):
                b = P.CacheFeed(d, now).bars(t["sym"])
                r = R.watch_exit(d, st, b, now)
                if r and r.get("px") is not None:
                    got = r
                    break
            n += 1
            if got and got["min"] == t["m_out"] and abs(got["px"] - t["px_out"]) < 1e-6                     and abs(st["model_entry"] - t["px_in"]) < 1e-6:
                ok += 1
            else:
                bad.append(dict(date=d, sym=t["sym"], engine=(t["m_out"], t["px_out"], t["reason"]),
                                watcher=None if not got else (got["min"], got["px"], got["reason"])))
    return dict(trades=n, identical=ok, mismatches=bad[:20])


def compare(mine, ref):
    """match on (date, sym, m_in)."""
    key = lambda t: (t["date"], t["sym"], int(t["m_in"]))  # noqa
    A = {key(t): t for t in mine}
    B = {key(t): t for t in ref}
    matched = sorted(set(A) & set(B))
    d_in = [abs(A[k]["px_in"] - B[k]["px_in"]) for k in matched]
    d_out_m = [A[k]["m_out"] - B[k]["m_out"] for k in matched]
    d_out_px = [abs(A[k]["px_out"] - B[k]["px_out"]) for k in matched]
    ident = sum(1 for k in matched
                if abs(A[k]["px_in"] - B[k]["px_in"]) < 1e-6
                and A[k]["m_out"] == B[k]["m_out"]
                and abs(A[k]["px_out"] - B[k]["px_out"]) < 1e-6)
    return dict(ref=len(B), mine=len(A), matched=len(matched),
                missed=sorted(map(list, set(B) - set(A)))[:40],
                extra=sorted(map(list, set(A) - set(B)))[:40],
                n_missed=len(set(B) - set(A)), n_extra=len(set(A) - set(B)),
                entry_px_maxdiff=max(d_in) if d_in else None,
                exit_min_mismatch=sum(1 for x in d_out_m if x),
                exit_px_maxdiff=max(d_out_px) if d_out_px else None,
                identical_round_trips=ident,
                pct_identical_entries=round(100.0 * sum(
                    1 for x in d_in if x < 1e-6) / max(len(B), 1), 2))


def price(trades, ndays, bps):
    pn = []
    for t in trades:
        c_in = (bps + R.EXT_BPS * (t["m_in"] < 330 or t["m_in"] >= 720)) / 1e4
        c_out = (bps + R.EXT_BPS * (t["m_out"] < 330 or t["m_out"] >= 720)) / 1e4
        pn.append(t["sh"] * t["px_out"] * (1 - c_out)
                  - t["sh"] * t["px_in"] * (1 + c_in))
    pn = np.array(pn)
    return dict(bps=bps, tickets=len(pn), per_ticket=round(float(pn.mean()), 2)
                if len(pn) else 0.0, total=round(float(pn.sum()), 2),
                tkt_per_day=round(len(pn) / max(ndays, 1), 3),
                per_day=round(float(pn.sum()) / max(ndays, 1), 2),
                win_rate=round(float((pn > 0).mean()), 3) if len(pn) else 0,
                ext_exits=sum(1 for t in trades if t["m_out"] >= 720))


def main():
    a = sys.argv[1:]
    t0 = time.time()
    ref_all = json.loads(LEGS.read_text())
    ref = ref_all["legs"]["RULE"]
    dates = [d for d in ref_all["dates"]]
    nd = a[a.index("--days") + 1] if "--days" in a else "all"
    if nd != "all":
        # days with RULE legs first (multi-leg days included), then others
        by = {}
        for t in ref:
            by[t["date"]] = by.get(t["date"], 0) + 1
        legd = sorted(by, key=lambda d: (-by[d], d))
        dates = sorted(legd[:int(nd)])
    ns = int(a[a.index("--strict-days") + 1]) if "--strict-days" in a else 12
    out = {"dates": len(dates)}
    mine = []
    for k, d in enumerate(dates):
        for t in run_day(d, R.CFG_PUBLISHED):
            t["date"] = d
            mine.append(t)
        if (k + 1) % 25 == 0:
            print(f"  {k + 1}/{len(dates)} {time.time() - t0:.0f}s", flush=True)
    dset = set(dates)
    refd = [t for t in ref if t["date"] in dset]
    out["published_parity"] = compare(mine, refd)
    out["published_repriced"] = {b: price(mine, len(dates), b)
                                 for b in (0, 6, 10)}
    out["published_ref_10bps_total"] = round(sum(t["pnl"] for t in refd), 2)
    print(json.dumps(out["published_parity"])[:600], flush=True)
    # strict truncation check on the multi-leg days
    by = {}
    for t in refd:
        by[t["date"]] = by.get(t["date"], 0) + 1
    sd = sorted(by, key=lambda d: (-by[d], d))[:ns]
    bad = []
    for d in sd:
        f = [(x["sym"], x["m_in"], x["px_in"], x["m_out"], x["px_out"])
             for x in run_day(d, R.CFG_PUBLISHED, strict=False)]
        s = [(x["sym"], x["m_in"], x["px_in"], x["m_out"], x["px_out"])
             for x in run_day(d, R.CFG_PUBLISHED, strict=True)]
        if f != s:
            bad.append(d)
    out["strict_truncation"] = dict(days=sd, legs=sum(by[d] for d in sd),
                                    mismatching_days=bad)
    print("strict:", out["strict_truncation"], flush=True)
    # session-end variants: (a) published (b) RTH, x {published, live}
    rth_pub = dict(R.CFG_PUBLISHED, name="published-RTH", win=(330, 715),
                   flat_bar=719)
    ext_live = dict(R.CFG_LIVE, name="live-EXT", win=(330, 720),
                    flat_bar=None)
    for cfg in (rth_pub, R.CFG_LIVE, ext_live):
        tr = []
        for d in dates:
            for t in run_day(d, cfg):
                t["date"] = d
                tr.append(t)
        out[cfg["name"]] = {b: price(tr, len(dates), b) for b in (0, 6, 10)}
        if cfg is R.CFG_LIVE:
            byd = {}
            for t in tr:
                byd.setdefault(t["date"], []).append(t)
            out["watch_exit_parity"] = watcher_parity(byd)
            print("watch_exit:", json.dumps(out["watch_exit_parity"])[:400], flush=True)
            out["snapshot_path_parity"] = snap_path_parity(
                dates, [dict(t) for t in tr])
            print("snapshot path:", json.dumps(out["snapshot_path_parity"])[:400],
                  flush=True)
            out["live_trades"] = [{k: t[k] for k in ("date", "sym", "m_in",
                                                     "px_in", "m_out", "px_out",
                                                     "sh", "reason")}
                                  for t in tr]
        print(cfg["name"], json.dumps(out[cfg["name"]]), flush=True)
    # VWAP-window sensitivity (live config): the scan's dayVwap may not
    # start at 04:00; how many live entries move if VWAP starts at 07:00
    # or at 09:30 instead?
    base = {(t["date"], t["sym"], t["m_in"]) for t in out["live_trades"]}
    sens = {}
    for vf, lab in ((180, "vwap_from_0700"), (330, "vwap_from_0930")):
        tr = []
        for d in dates:
            for t in run_day(d, R.CFG_LIVE, vwap_from=vf):
                t["date"] = d
                tr.append(t)
        k = {(t["date"], t["sym"], t["m_in"]) for t in tr}
        sens[lab] = dict(entries=len(k), same=len(k & base),
                         pct_same=round(100.0 * len(k & base) / max(len(base), 1), 1),
                         priced={b: price(tr, len(dates), b) for b in (6, 10)})
        print(lab, sens[lab], flush=True)
    out["vwap_sensitivity_live"] = sens
    out["secs"] = round(time.time() - t0, 1)
    P.write_atomic(OUT, out)
    print(f"wrote {OUT} in {out['secs']}s")


if __name__ == "__main__":
    main()
