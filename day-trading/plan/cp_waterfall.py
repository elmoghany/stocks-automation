"""CHAMPION-REPLAY part 1: decompose the champions' $774,534.

Assembles every epoch row this repo has produced for the rotation
champion into one waterfall, then attributes the drop TICKET BY TICKET
using the saved ledgers (data/massive/rotation_trades_*.json), so each
step is a set of trades that appeared or disappeared, not a subtraction
of two headline numbers.

    python plan/cp_waterfall.py            > the table
    python plan/cp_waterfall.py --tickets  > the ticket-level attribution
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "data/massive"

# (label, results-file suffix, config id, what changed at this step)
LADDER = [
    ("C37 as adopted", "_na", "VOLD",
     "hindsight top-16-by-FULL-DAY-GAIN pool cut, bar cache fetched only "
     "to full-day-gain depth, pre-2026-08-14 halal gate"),
    ("C37H", "_na", "C37H",
     "drop the hindsight top-16 sort (causal pool = every candidate WITH "
     "BARS); the biased CACHE is still underneath"),
    ("C37S", "_strict", "C37S", "live halal gate semantics (HALAL_STRICT)"),
    ("C37E", "_edgar", "C37E",
     "+ EDGAR filed-date cache so the strict gate can verify real "
     "quarterlies (still the biased cache)"),
    ("C37F", "", "C37F",
     "FULL-COVERAGE minute cache (backfill_m1_full): the pool becomes "
     "every candidate/day (~213) instead of the ~17 with gain-selected "
     "bars"),
    ("C37F-hl", "_hl_c37", "C37F",
     "+ pool hygiene (test symbols, split/relist artifacts, non-equity)"),
    ("C37F-fm", "_fm_c37", "C37F",
     "+ honest fills: gap-through stops fill at the bar OPEN, every sell "
     "clamped into [Low, High], causal bad-print peak guard"),
    ("C37F-rs", "_rs_bench", "C37F",
     "+ regular-session eligibility (RS_CROSS): a name is armable only "
     "after an IN-SESSION +10% print, so no premarket entry can be made "
     "on membership the day had not yet proved"),
    ("C37F-df", "_rs_def", "C37F",
     "+ deferred entry (RS_DEFER): the cross bar itself is not fillable, "
     "because its own high is what proved eligibility"),
    ("C37F-hf2", "_hf2", "C37F",
     "+ the repaired halal gate (415 armable names, 2026-09-16 v2)"),
]

COMPANION = [("HOLD1-fm", "_fm_h1", "HOLD1"), ("HOLD1-df", "_rs_def", "HOLD1"),
             ("HOLD1-hf2", "_hf2", "HOLD1")]


def row(suffix, cid):
    f = RES / f"rotation_results{suffix}.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text()).get(cid)
    if not d:
        return None
    out = dict(total=0, days=0, tickets=0, negm=0, nmonths=0, exbest=0,
               deployed=0.0)
    for lab in ("year", "y2025"):
        s = d.get(lab)
        if not s:
            continue
        out["total"] += s.get("total", 0)
        out["days"] += s.get("days", 0)
        out["tickets"] += s.get("tickets", 0) or 0
        out["negm"] += s.get("negm", 0)
        out["nmonths"] += s.get("nmonths", 0)
        out["exbest"] += s.get("total_ex_best", 0)
        out["deployed"] += s.get("deployed", 0) or 0
    out["flags"] = (int(bool(d.get("pool_hygiene"))),
                    int(bool(d.get("rs_cross"))), int(bool(d.get("rs_defer"))),
                    int(bool(d.get("halal_strict"))))
    return out


def ledger(tag):
    f = RES / f"rotation_trades_{tag}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text())


def table():
    print("## Waterfall: the rotation champion, epoch by epoch\n")
    print("| step | config | total $ | traded days | tickets | $/ticket | "
          "neg months | hyg/rs/df/halal |")
    print("|---|---|---:|---:|---:|---:|---:|---|")
    prev = None
    lines = []
    for lab, suf, cid, why in LADDER:
        r = row(suf, cid)
        if r is None:
            print(f"| {lab} | {cid} | MISSING | | | | | |")
            continue
        tk = r["tickets"]
        pt = (r["total"] / tk) if tk else float("nan")
        print(f"| {lab} | {cid} | {r['total']:+,} | {r['days']} | "
              f"{tk or '-'} | {pt:+.1f} | {r['negm']}/{r['nmonths']} | "
              f"{'/'.join(map(str, r['flags']))} |")
        if prev is not None:
            lines.append((lab, r["total"] - prev, why))
        prev = r["total"]
    print("\n## The steps, in dollars\n")
    print("| step | delta total $ | what was removed |")
    print("|---|---:|---|")
    for lab, d, why in lines:
        print(f"| -> {lab} | {d:+,} | {why} |")
    print("\n## Companion: the same epochs with the exits removed "
          "(HOLD1 = buy the same pick, flatten at 15:00)\n")
    print("| config | total $ | tickets | $/ticket |")
    print("|---|---:|---:|---:|")
    for lab, suf, cid in COMPANION:
        r = row(suf, cid)
        if r:
            tk = r["tickets"] or 1
            print(f"| {lab} | {r['total']:+,} | {r['tickets']} | "
                  f"{r['total']/tk:+.1f} |")


def tickets():
    """Ticket-level attribution across the three decisive steps."""
    eps = [("C37F-hl (biased fills)", "C37F_hl_c37"),
           ("C37F-fm (honest fills)", "C37F_fm_c37"),
           ("C37F-rs (RS eligibility)", "C37F_rs_bench"),
           ("C37F-df (deferred entry)", "C37F_rs_def"),
           ("C37F-hf2 (halal v2)", "C37F_hf2")]
    led = {}
    for lab, tag in eps:
        L = ledger(tag)
        if L is None:
            print(f"  ledger missing: {tag}")
            continue
        led[lab] = L
    print("\n## Ticket-level view of each epoch\n")
    print("| epoch | legs | total $ | premarket entries | their $ | "
          "RTH entries | their $ | top-10 legs' share of gross profit |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for lab, _ in eps:
        L = led.get(lab)
        if L is None:
            continue
        tot = sum(x["pnl"] for x in L)
        pm = [x for x in L if x["entry_time"][11:16] < "09:30"]
        rth = [x for x in L if x["entry_time"][11:16] >= "09:30"]
        pos = sorted((x["pnl"] for x in L), reverse=True)
        gp = sum(p for p in pos if p > 0) or 1
        top10 = sum(pos[:10])
        print(f"| {lab} | {len(L)} | {tot:+,.0f} | {len(pm)} | "
              f"{sum(x['pnl'] for x in pm):+,.0f} | {len(rth)} | "
              f"{sum(x['pnl'] for x in rth):+,.0f} | {top10/gp*100:.0f}% |")

    # which tickets the RS epoch dropped, and what they were worth
    a, b = led.get("C37F-fm (honest fills)"), led.get("C37F-df (deferred entry)")
    if a and b:
        ka = defaultdict(float)
        for x in a:
            ka[(x["date"], x["symbol"])] += x["pnl"]
        kb = defaultdict(float)
        for x in b:
            kb[(x["date"], x["symbol"])] += x["pnl"]
        only_a = {k: v for k, v in ka.items() if k not in kb}
        only_b = {k: v for k, v in kb.items() if k not in ka}
        both = [k for k in ka if k in kb]
        print("\n## What regular-session eligibility + deferred entry "
              "actually did to the ledger\n")
        print(f"- legs present ONLY in the leaky (premarket-armed) run: "
              f"**{len(only_a)}** name-days worth "
              f"**${sum(only_a.values()):+,.0f}**")
        print(f"- legs present ONLY in the causal run: **{len(only_b)}** "
              f"name-days worth **${sum(only_b.values()):+,.0f}**")
        print(f"- name-days in both: **{len(both)}**, leaky "
              f"${sum(ka[k] for k in both):+,.0f} vs causal "
              f"${sum(kb[k] for k in both):+,.0f}")
    # tail structure of the honest champion
    h = led.get("C37F-hf2 (halal v2)")
    if h:
        p = sorted(h, key=lambda x: -x["pnl"])
        tot = sum(x["pnl"] for x in h)
        print("\n## The honest champion's biggest legs\n")
        print("| # | date | symbol | entry | exit | reason | $ |")
        print("|---:|---|---|---|---|---|---:|")
        for i, x in enumerate(p[:8], 1):
            print(f"| {i} | {x['date']} | {x['symbol']} | "
                  f"{x['entry_time'][11:16]} | {x['exit_time'][11:16]} | "
                  f"{x['reason']} | {x['pnl']:+,.0f} |")
        for i, x in enumerate(p[-5:], 1):
            print(f"| -{6-i} | {x['date']} | {x['symbol']} | "
                  f"{x['entry_time'][11:16]} | {x['exit_time'][11:16]} | "
                  f"{x['reason']} | {x['pnl']:+,.0f} |")
        print(f"\ntotal {tot:+,.0f} over {len(h)} legs")


if __name__ == "__main__":
    table()
    if "--tickets" in sys.argv[1:]:
        tickets()
