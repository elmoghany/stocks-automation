"""LIVE-COST-TRUTH: what did the 42 paper legs (21 tickets, 2026-08-10..09-17) cost per side?

IMPORTANT: none of these are real Robinhood executions (every ledger: REAL_ORDER false /
PAPER). Each fill was BOOKED by the session's own convention from a live RH quote/L2 book
or from bars. So "cost" here = booked fill vs what the market showed, three ways:
  c_mid   vs the logged bid/ask mid at order time (only where both sides were logged, <=60 s)
  c_open  vs the OPEN of the fill minute (the price a bar backtest fills a market order at)
  c_vw    vs the VWAP of the fill minute (1-s tape where cached, else Polygon m1 `vw`)
plus the decomposition:
  c_touch vs the touched side (ask for buys, bid for sells): sweep/haircut BEYOND the spread
  hs      half-spread at order time (bps), genuine market cost of crossing
  bt_ref  the backtest's own booking price (B/A: max(trigger, fill-minute open);
          C: open of the bar after the signal bar; exits: fill-minute open)
  real_stop (B/A with 1-s tape): VWAP of the first 3 s once the tape trades >= trigger
          after arming -> what a resting stop-MARKET would really have paid vs the trigger.
cost_bps = side * (fill / ref - 1) * 1e4, positive = cost to us.

  python plan/lct_cost.py      -> plan/lct_out/legs.json + printed tables
Reads only (pa_out m1 + tape caches, data/massive/trades*, liquidity_truth).
"""
import gzip
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from pa_live import F  # noqa: E402  (date, sym, side, HH:MM[:SS], px, shares, quote)

OUT = HERE / "lct_out"
M1 = HERE / "pa_out" / "m1"
MAS = ROOT / "data" / "massive"
ET = ZoneInfo("America/New_York")

# per leg, same order as F:
# kind: B stop-buy, A ORB stop-buy, C pattern marketable-limit, L ladder exit, S stop/trail exit
# trig: stop level (B/A) ; sig: signal-bar HH:MM (C) ; arm: armed HH:MM:SS (B/A)
# q: (bid, ask, age_s) logged at order time (age relative to fill; None side = unknown)
# conv: booking convention in one phrase
M = [
    dict(kind="B", trig=12.045, arm="09:46:00", q=(11.99, 12.03, -60), conv="stop already met -> ask-side sweep 4 levels"),
    dict(kind="L", q=(12.02, 12.03, -240), conv="bid-side sweep vs 14:53 book"),
    dict(kind="B", trig=7.27, arm="08:24:00", q=(7.26, 7.27, -26), conv="fill AT trigger"),
    dict(kind="L", conv="outage; settled from tape bars"),
    dict(kind="B", trig=235.37, arm="09:24:24", q=(234.0, 235.0, -96), conv="fill AT trigger"),
    dict(kind="L", conv="inside bid"),
    dict(kind="B", trig=4.265, arm="11:00:00", conv="fill AT trigger"),
    dict(kind="L", q=(4.28, None, 0), conv="bid-side sweep 3040 sh into a thin bid"),
    dict(kind="B", trig=178.90, arm="09:32:43", q=(178.36, 178.90, -2), conv="inside ask 178.91 after the stop"),
    dict(kind="L", q=(177.27, None, 0), conv="inside bid"),
    dict(kind="B", trig=2.98, arm="07:40:00", conv="fill AT trigger"),
    dict(kind="L", conv="settled from tape"),
    dict(kind="B", trig=245.12, arm="08:50:00", conv="fill AT trigger"),
    dict(kind="L", q=(233.67, 233.77, 60), conv="close-out at bid"),
    dict(kind="C", sig="07:12", q=(28.47, 28.60, -9), conv="inside ask"),
    dict(kind="S", trig=26.31, conv="-8% stop booked AT stop level"),
    dict(kind="C", sig="11:11", q=(8.14, 8.15, 0), conv="inside ask"),
    dict(kind="L", conv="inside bid"),
    dict(kind="C", sig="08:55", q=(17.50, 17.55, -6), conv="inside ask"),
    dict(kind="L", conv="ladder sweep"),
    dict(kind="C", sig="10:01", q=(None, 7.62, 0), sp_bps=26, conv="inside ask"),
    dict(kind="L", q=(7.83, None, 0), conv="bid-side sweep 2 levels"),
    dict(kind="C", sig="09:52", q=(14.85, 14.89, -4), conv="inside ask"),
    dict(kind="L", conv="ladder sweep"),
    dict(kind="B", trig=163.85, arm="08:27:00", conv="fill AT trigger"),
    dict(kind="L", q=(173.48, 173.62, 0), conv="bar close less half the ~0.14 spread"),
    dict(kind="C", sig="09:44", q=(None, 4.21, 0), conv="ask-side sweep 2 levels"),
    dict(kind="L", conv="ladder sweep"),
    dict(kind="B", trig=22.6199, arm="11:44:00", conv="fill AT trigger"),
    dict(kind="L", q=(22.73, None, 0), conv="inside bid"),
    dict(kind="B", trig=55.80, arm="07:33:00", sp_bps=128, conv="fill AT trigger"),
    dict(kind="S", trig=51.561, conv="trail booked AT stop level (bar low 50.28)"),
    dict(kind="B", trig=474.40, arm="09:33:16", conv="fill AT trigger"),
    dict(kind="S", trig=436.448, conv="-8% stop booked AT stop level"),
    dict(kind="C", sig="10:17", q=(None, 51.31, 0), conv="ask-side sweep 3 levels"),
    dict(kind="L", q=(49.46, 49.48, -6), conv="bid x 0.999 (10 bps haircut); ask from the 2c spread 48 s later"),
    dict(kind="C", sig="09:09", q=(184.72, 184.85, -1), conv="L2 inside ask 184.89"),
    dict(kind="L", q=(173.80, None, 0), conv="bid x 0.999 (10 bps haircut)"),
    dict(kind="C", sig="10:18", q=(63.45, 63.59, 0), conv="inside ask"),
    dict(kind="L", q=(63.72, None, 0), conv="bid x 0.999 (10 bps haircut), rung 2"),
    dict(kind="A", trig=211.975, arm="09:35:00", sp_bps=47, conv="fill AT ORB level"),
    dict(kind="L", q=(217.83, None, 0), conv="bid x 0.999 (10 bps haircut)"),
]
assert len(M) == len(F)


def ms(d, hm, ss=0):
    y, mo, dd = map(int, d.split("-"))
    return int(datetime(y, mo, dd, int(hm[:2]), int(hm[3:5]), ss, tzinfo=ET).timestamp() * 1000)


def tape(sym, d):
    rows = []
    for sub in ("trades_pm", "trades"):
        p = MAS / sub / f"{sym}_{d}.json.gz"
        if p.exists():
            with gzip.open(p, "rt") as h:
                r = json.load(h)
            rows += r["rows"] if isinstance(r, dict) else r
    if not rows:
        return None
    R = np.array(rows, dtype=float)
    return R[np.argsort(R[:, 0])]


def tvwap(R, a, b):
    k = (R[:, 0] >= a) & (R[:, 0] < b) & (R[:, 5] > 0)
    if not k.any():
        return None
    tp = (R[k, 2] + R[k, 3] + R[k, 4]) / 3.0
    return float((tp * R[k, 5]).sum() / R[k, 5].sum())


def bps(side, px, ref):
    return None if not ref else side * (px / ref - 1) * 1e4


def main():
    out = []
    for (d, s, side, hm, px, sh, _), m in zip(F, M):
        bars = {b["t"]: b for b in json.loads((M1 / f"{s}_{d}.json").read_text())}
        t0 = ms(d, hm)
        b = bars.get(t0) or {}
        R = tape(s, d)
        vw_t = tvwap(R, t0, t0 + 60000) if R is not None else None
        vw = vw_t or b.get("vw")
        r = dict(date=d, sym=s, side=side, t=hm, px=px, notional=round(px * sh),
                 kind=m["kind"], conv=m["conv"],
                 session="pre" if hm < "09:30" else "rth",
                 min_dollar_vol=round(b.get("v", 0) * b.get("vw", px)),
                 vw_src="tape" if vw_t else ("m1" if b.get("vw") else None))
        r["c_open"] = bps(side, px, b.get("o"))
        r["c_vw"] = bps(side, px, vw)
        if R is not None and len(hm) > 5:
            tc = t0 + int(hm[6:8]) * 1000
            r["c_vw10s"] = bps(side, px, tvwap(R, tc - 10000, tc + 11000))
        q = m.get("q")
        hs = None
        if q:
            bid, ask, age = q
            touch = ask if side > 0 else bid
            if touch:
                r["c_touch"] = bps(side, px, touch)
            if bid and ask:
                mid = (bid + ask) / 2
                hs = (ask - bid) / mid * 1e4 / 2
                if abs(age) <= 60:
                    r["c_mid"] = bps(side, px, mid)
        if hs is None and m.get("sp_bps"):
            hs = m["sp_bps"] / 2
        r["hs"] = hs
        # backtest booking reference
        if m["kind"] in ("B", "A"):
            o = b.get("o")
            ref = max(m["trig"], o) if o else m["trig"]
            r["bt_ref"] = ref
            r["c_vs_trig"] = bps(side, px, m["trig"])
            if R is not None:
                ta = ms(d, m["arm"][:5], int(m["arm"][6:8]))
                k = np.where((R[:, 0] >= ta) & (R[:, 2] >= m["trig"]))[0]
                if len(k) and abs(R[k[0], 0] - t0) <= 120000:   # crossing must match the booked minute
                    t1 = R[k[0], 0]
                    rs = tvwap(R, t1, t1 + 3000)
                    r["real_stop"] = rs
                    r["real_stop_vs_trig"] = bps(side, rs, m["trig"])
                    r["real_stop_t"] = datetime.fromtimestamp(t1 / 1000, ET).strftime("%H:%M:%S")
        elif m["kind"] == "C":
            nb = bars.get(ms(d, m["sig"]) + 60000) or {}
            r["bt_ref"] = nb.get("o")
            r["lag_min"] = (t0 - ms(d, m["sig"])) // 60000 - 1
        elif m["kind"] == "S":
            r["bt_ref"] = m["trig"]
            r["c_vs_stoplevel_low"] = bps(side, px, b.get("l"))
        else:
            r["bt_ref"] = b.get("o")
        r["c_bt"] = bps(side, px, r["bt_ref"])
        out.append(r)

    OUT.mkdir(exist_ok=True)

    def st(rows, key):
        v = np.array([x[key] for x in rows if x.get(key) is not None and abs(x[key]) < 300])
        if not len(v):
            return "  n=0"
        return f"n={len(v):2d} med {np.median(v):6.1f} mean {v.mean():6.1f}"

    liquid = lambda x: x["min_dollar_vol"] >= 1_500_000  # noqa: E731  ticket <= 1% of the minute
    buckets = [
        ("ALL", lambda x: True),
        ("entries B/A stop-buy", lambda x: x["kind"] in "BA"),
        ("entries C pattern", lambda x: x["kind"] == "C"),
        ("exits L ladder", lambda x: x["kind"] == "L"),
        ("exits S stop/trail", lambda x: x["kind"] == "S"),
        ("premarket", lambda x: x["session"] == "pre"),
        ("regular", lambda x: x["session"] == "rth"),
        ("rth, minute $vol>=1.5M", lambda x: x["session"] == "rth" and liquid(x)),
        ("rth, minute $vol<1.5M", lambda x: x["session"] == "rth" and not liquid(x)),
        ("rth liquid, excl S", lambda x: x["session"] == "rth" and liquid(x) and x["kind"] != "S"),
        ("rth excl S", lambda x: x["session"] == "rth" and x["kind"] != "S"),
    ]
    summ = {}
    for nm, f in buckets:
        rows = [x for x in out if f(x)]
        line = {k: st(rows, k) for k in ("c_mid", "c_open", "c_vw", "c_bt", "c_touch", "hs")}
        summ[nm] = line
        print(f"{nm:26s} n={len(rows):2d} |", " | ".join(f"{k} {v}" for k, v in line.items()))
    print()
    for x in out:
        f = lambda k: ("%7.1f" % x[k]) if x.get(k) is not None else "      ."  # noqa: E731
        print(f"{x['date']} {x['sym']:5s} {'B' if x['side'] > 0 else 'S'} {x['t']:8s} {x['kind']} {x['session']} "
              f"$v/min {x['min_dollar_vol'] / 1e6:6.2f}M mid{f('c_mid')} open{f('c_open')} vw{f('c_vw')} "
              f"bt{f('c_bt')} touch{f('c_touch')} hs{f('hs')} trig{f('c_vs_trig')} "
              f"realstop{f('real_stop_vs_trig')} {x.get('real_stop_t', '')}")
    print()
    # decomposition, regular session, excluding S (stop/trail booked at the level)
    for nm, f in (("rth entries", lambda x: x["session"] == "rth" and x["side"] > 0),
                  ("rth ladder exits", lambda x: x["kind"] == "L"),
                  ("rth liquid entries", lambda x: x["session"] == "rth" and x["side"] > 0 and liquid(x)),
                  ("rth liquid ladder exits", lambda x: x["kind"] == "L" and liquid(x)),
                  ("C entries (all sessions)", lambda x: x["kind"] == "C"),
                  ("B/A entries (all sessions)", lambda x: x["kind"] in "BA")):
        rows = [x for x in out if f(x)]
        print(f"{nm:28s} n={len(rows):2d} |", " | ".join(f"{k} {st(rows, k)}" for k in
              ("hs", "c_touch", "c_mid", "c_bt", "c_vw", "real_stop_vs_trig", "lag_min")))
    (OUT / "legs.json").write_text(json.dumps(dict(legs=out, summary=summ), indent=1, default=float))


if __name__ == "__main__":
    main()
