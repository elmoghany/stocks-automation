"""LEGACY-3 (2026-10-01): ENTRY-TRIGGER mining on the HONEST C37F epoch.

Re-runs the untouched C37F rotation (rotation_sim.run_day, no file edits)
under POOL_HYGIENE=1 RS_CROSS=1 RS_DEFER=1 with halal IGNORED (halal_pt
monkeypatched to True in-process only), and for every DECISION the
rotation makes (= every simulate_trades call: name armed at entry_start)
records, on the SAME name / same entry_start / same budget / same exits:

  real : the champion's trigger set (ORB-ratchet new-high break, PMH
         stop-buy, 8 reversal candles / MACD / RSI crosses) -> 'trig'
  imm  : triggers OFF, market buy at the first eligible bar (rand_entry=1)
  rnd_k: triggers OFF, market buy at a uniformly random bar within 30 min
         of the first eligible bar (rand_entry=(30, seed k)), k=0..NSEED-1

The controls are drawn UNCONDITIONALLY at decision time (no knowledge of
whether the trigger later fires), so 'all decisions' comparisons are
lookahead-free. Exits are the champion's own (pressure trail, -8% stop,
bearish candle exit, scale-out, 15:00 flatten).

Output: JSON in the session scratchpad (path = argv[1]), analysed by
plan/lm3_report.py. Usage: python plan/lm3_trig.py OUT.json [--days N]
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(POOL_HYGIENE="1", RS_CROSS="1", RS_DEFER="1")
os.environ.pop("ROTSHARD", None)
os.environ.pop("FEATCACHE", None)
ROOT = Path(__file__).resolve().parent.parent
sp = importlib.util.spec_from_file_location("rs", ROOT / "plan/rotation_sim.py")
rs = importlib.util.module_from_spec(sp)
sys.modules["rs"] = rs
sp.loader.exec_module(rs)

rs.axb.halal_pt = lambda *a, **k: True          # halal ignored (mandate)
dt = rs.dt
_orig_sim = dt.simulate_trades
_orig_memo = rs._memo_sim
NSEED = int(os.environ.get("LM3_SEEDS", "5"))

CUR = {}
DEC = []
CACHE = {}


def _first(tr):
    tr = [x for x in tr if x.get("entry_time") is not None]
    if not tr:
        return None
    fe = tr[0]["entry_time"]
    g = [x for x in tr if x["entry_time"] == fe]
    sh = sum(int(x.get("shares") or 0) for x in g)
    return dict(t=str(fe), px=g[0]["entry"], pnl=sum(x["pnl"] for x in g),
                trig=g[0].get("trig"), reason=g[0].get("reason"),
                xt=str(max(x["exit_time"] for x in g)), sh=sh,
                notional=sum((x.get("shares") or 0) * x["entry"] for x in g))


def _sim_wrap(w, **kw):
    real = _orig_sim(w, **kw)
    rk = dict(kw)
    rk["orb"] = False
    rk["buy_set"] = set()
    rk.pop("extra_break_high", None)
    ctl = {}
    ctl["imm"] = _first(_orig_sim(w, **dict(rk, rand_entry=(1, "lm3-imm"))))
    for s in range(NSEED):
        ctl[f"r{s}"] = _first(_orig_sim(
            w, **dict(rk, rand_entry=(30, f"lm3-{s}"))))
    CUR["ctl"] = ctl
    return real


def _memo_wrap(memo, key, fn):
    if key and key[0] == "sim":
        if key not in CACHE:
            CUR["ctl"] = None
            res = fn()
            CACHE[key] = (res, CUR["ctl"])
        res, ctl = CACHE[key]
        DEC.append(dict(date=CUR["date"], lab=CUR["lab"], sym=key[1],
                        es=str(key[2]), budget=key[3],
                        real=_first([dict(x) for x in res]), ctl=ctl))
        return [dict(x) for x in res]
    return _orig_memo(memo, key, fn)


dt.simulate_trades = _sim_wrap
rs._memo_sim = _memo_wrap


def main():
    out = Path(sys.argv[1])
    md = None
    if "--days" in sys.argv:
        md = int(sys.argv[sys.argv.index("--days") + 1])
    cfg = rs.CFGS["C37F"]
    cfg["_id"] = "C37F"
    cfg["_simkw"] = rs.build_simkw("C37F", cfg, echo=False)
    t0 = time.time()
    tickets = []
    for lab in rs.LABELS:
        byday = rs.px.load_by_day(lab, 50, "novol")
        items = sorted(byday.items())[:md] if md else sorted(byday.items())
        stride = int(os.environ.get("LM3_STRIDE", "1"))
        items = items[int(os.environ.get("LM3_OFF", "0"))::stride]
        for n, (date, cs) in enumerate(items, 1):
            CACHE.clear()
            CUR.update(date=date, lab=lab)
            cands = rs.day_candidates(cs, date, {}, 16, True)
            if not cands:
                continue
            tr = rs.run_day(cands, date, cfg, {}, None, rep=0, memo={})
            for x in tr:
                tickets.append(dict(lab=lab, date=date, sym=x.get("symbol"),
                                    ticket=x.get("ticket"),
                                    t=str(x["entry_time"]), px=x["entry"],
                                    xt=str(x["exit_time"]), xp=x["exit"],
                                    pnl=x["pnl"], trig=x.get("trig"),
                                    reason=x.get("reason"),
                                    sh=x.get("shares")))
            if n % 5 == 0:
                print(f"{lab} {n}/{len(items)} dec={len(DEC)} "
                      f"tk={len(tickets)} {time.time() - t0:.0f}s",
                      flush=True)
    out.write_text(json.dumps(dict(tickets=tickets, dec=DEC,
                                   nseed=NSEED, secs=time.time() - t0)))
    print("done", len(tickets), len(DEC), f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
