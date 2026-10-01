"""LEGACY-4 follow-up: the one premarket slice that was not negative on the
12-day honest census (market cap >= $2B) re-measured over all 444 sessions.

Universe: every panel name-day (data/massive/cp/rows.npz = RTH crossers,
bars on disk) whose premarket high reached +10%, i.e. PM-AND-RTH. That set
is survivorship-conditioned (it later printed +10% in the session); the
census says PM-ONLY is ~5% of large-cap premarket crossers, so the report
adds that share back at the census PM-ONLY outcome.

Entries (all causal):
  PM   : first premarket close >= +10% (and >= $2), fill = OPEN of the next
         printed bar (census convention)
  RS   : first regular-session close >= +10%, fill = OPEN of the next
         printed bar (RS_CROSS + RS_DEFER convention)
Exits: OPEN of first print at/after 09:30, 09:45, 10:00, 10:30; last close
<= 15:00.

    python plan/lm4_largecap.py
"""
import json
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_premkt as PM                                      # noqa: E402
import lm4_premkt as LM                                     # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MO = PM.M_OPEN
EXITS = {"0930": MO, "0945": MO + 15, "1000": MO + 30, "1030": MO + 60}


def run(entry_kind, recs, ev):
    res = []
    for (d, s), f in recs.items():
        b = PM.read_bars(s, d)
        if b is None:
            continue
        o, h, l, c, v = b
        pr = np.isfinite(c)
        thr = max(1.10 * f["pc"], 2.0)
        rng = range(0, MO) if entry_kind == "PM" else range(MO, PM.M_1500)
        m0 = next((m for m in rng if pr[m] and c[m] >= thr), None)
        if m0 is None:
            continue
        nxt = LM.first_print_at(pr, m0 + 1)
        if nxt is None or nxt > PM.M_1500:
            continue
        e = o[nxt]
        r = dict(date=d, sym=s, m0=m0, mcap=f["shares"] * f["pc"])
        for k, mm in EXITS.items():
            if mm <= nxt:
                r[k] = np.nan
                continue
            kk = LM.first_print_at(pr, mm)
            r[k] = o[kk] / e - 1 if kk is not None and kk <= PM.M_1500 else np.nan
        seg = [k for k in range(nxt + 1, PM.M_1500 + 1) if pr[k]]
        r["1500"] = c[seg[-1]] / e - 1 if seg else np.nan
        t1, t0 = LM.ts_of(d, m0), LM.prev_close_ts(d)
        r["cat"] = (float(any(((a > t0) & (a <= t1)).any()
                              for a in ev[s].values() if len(a)))
                    if s in ev else np.nan)
        r["earn"] = (float(((ev[s]["earnings"] > t0 - 86400)
                            & (ev[s]["earnings"] <= t1)).any())
                     if s in ev and "earnings" in ev[s] else np.nan)
        res.append(r)
    return res


def summ(name, rs, dates):
    half = dates[len(dates) // 2]
    ks = [k for k in list(EXITS) + ["1500"]]
    line = f"| {name} | {len(rs)} | {len({r['date'] for r in rs})} |"
    for k in ks:
        a = np.array([r[k] for r in rs], float)
        a = a[np.isfinite(a)]
        line += f" {a.mean()*1e4:+.0f} ({np.median(a)*1e4:+.0f}) |" if len(a) else " - |"
    best = max(ks, key=lambda k: np.nanmean([r[k] for r in rs]) if rs else -1)
    h1 = np.nanmean([r[best] for r in rs if r["date"] < half]) * 1e4
    h2 = np.nanmean([r[best] for r in rs if r["date"] >= half]) * 1e4
    dm = defaultdict(list)
    for r in rs:
        if np.isfinite(r[best]):
            dm[r["date"]].append(r[best])
    t = LM.tstat([np.mean(x) for x in dm.values()])
    hit = np.nanmean([r[best] > 0 for r in rs if np.isfinite(r[best])])
    print(line + f" {best}: H1 {h1:+.0f} / H2 {h2:+.0f}, t(day) {t:+.2f}, "
          f"win {hit:.0%} |")


if __name__ == "__main__":
    st, _ = LM.static_table()
    ev = pickle.load(open(ROOT / "data/massive/cat/events.pkl", "rb"))
    dates = sorted({d for d, _ in st})
    pmx = {k: f for k, f in st.items()
           if np.isfinite(f["pm_high_gain"]) and f["pm_high_gain"] >= 0.10}
    print(f"panel name-days {len(st)}, premarket +10% (PM-AND-RTH) {len(pmx)}; "
          f"with shares {sum(np.isfinite(f['shares']) for f in pmx.values())}")
    hdr = ("| slice | n | days | ->09:30 | ->09:45 | ->10:00 | ->10:30 | "
           "->15:00 | best exit: halves, t, win |")
    for kind in ("PM", "RS"):
        print(f"\n## entry {kind} -- mean (median) gross bps\n")
        print(hdr)
        print("|---|---:|---:|---:|---:|---:|---:|---:|---|")
        cap = {k: f for k, f in pmx.items() if np.isfinite(f["shares"])}
        R = run(kind, cap, ev)
        for name, fn in (
                ("all with shares", lambda r: True),
                ("mcap <300M", lambda r: r["mcap"] < 3e8),
                ("mcap 300M-2B", lambda r: 3e8 <= r["mcap"] < 2e9),
                ("mcap >=2B", lambda r: r["mcap"] >= 2e9),
                ("mcap >=10B", lambda r: r["mcap"] >= 1e10),
                ("mcap >=2B & earnings<=24h", lambda r: r["mcap"] >= 2e9 and r["earn"] == 1),
                ("mcap >=2B & no earnings", lambda r: r["mcap"] >= 2e9 and r["earn"] == 0),
                ("mcap >=2B & any catalyst", lambda r: r["mcap"] >= 2e9 and r["cat"] == 1),
                ("mcap >=2B & cross>=07:00", lambda r: r["mcap"] >= 2e9 and r["m0"] >= 180),
                ("mcap >=2B & cross<07:00", lambda r: r["mcap"] >= 2e9 and r["m0"] < 180)):
            sub = [r for r in R if fn(r)]
            if len(sub) >= 5:
                summ(name, sub, dates)
