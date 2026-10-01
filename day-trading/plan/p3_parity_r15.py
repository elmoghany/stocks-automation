"""PAPER-3BOOK parity test, book R15.

Replays EVERY day of the CATALYST-MINER window (the 448 dates of
plan/rl2/out/feat) through plan/p3_r15.py's LIVE code:
  * universe   = that day's rl2 panel symbols (alphabetical, as in the table)
  * earnings   = the historical event corpus (plan/cat_events.corpus()),
                 converted to the {report_date, timing} rows the live
                 Robinhood calendar gives, so the live freshness code runs
  * bars       = p3_lib.CacheFeed (data/massive m1w/m1/m1c as the live feed),
                 truncated to completed minutes exactly like live:
                 selection at wall 09:36 (bars <= 09:35), trade at EOD.
and compares the picks with the backtest's 112 tickets
(data/massive/cat/rule_detail.json "R15 fresh&green@09:35 h60").

    python plan/p3_parity_r15.py      -> data/paper/parity/r15.json
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p3_lib as L                                           # noqa: E402
import p3_r15 as R                                           # noqa: E402
import cat_events as E                                       # noqa: E402

OUT = L.DATA / "paper" / "parity" / "r15.json"
FEAT = HERE / "rl2" / "out" / "feat"
TAB = L.MASSIVE / "cat" / "table.npz"
RULE = "R15 fresh&green@09:35 h60"


def corpus_events(sym):
    """Historical earnings events -> live-calendar rows."""
    ev = E.corpus().get(sym)
    if ev is None or ev["_earn"].shape[0] == 0:
        return []
    out = []
    for ts in ev["_earn"][:, 0]:
        dt = datetime.fromtimestamp(float(ts), L.ET)
        timing = "am" if (dt.hour, dt.minute) == (7, 30) else "pm"
        out.append({"report_date": dt.date().isoformat(), "timing": timing})
    return out


def main():
    t0 = time.time()
    det = json.loads((L.MASSIVE / "cat" / "rule_detail.json").read_text())[RULE]
    z = np.load(TAB, allow_pickle=False)
    tab_dates = [str(x) for x in z["dates"]]
    rows = det["rows"]
    bt = {}
    for r, tk in zip(rows, det["tickets_list"]):
        bt[tk["date"]] = dict(tk, fill_px=float(z["fill_px"][r]),
                              tab_notional=float(z["notional"][r]),
                              tab_pnl=float(z["pnl_h60"][r]))
    dates = sorted(p.stem for p in FEAT.glob("*.npz"))
    ev_cache = {}
    live = {}
    for date in dates:
        uni = [str(s) for s in np.load(FEAT / f"{date}.npz")["syms"]]
        earnings = {}
        for s in uni:
            if s not in ev_cache:
                ev_cache[s] = corpus_events(s)
            if ev_cache[s]:
                earnings[s] = ev_cache[s]
        # live selection at wall 09:36 (completed bars <= 09:35 only)
        d1 = R.decide(date, R.FILL, L.CacheFeed(date, R.FILL), uni, earnings,
                      ticket=15_000.0)
        if not d1.get("sym"):
            continue
        sym = d1["sym"]
        # the trade itself, priced at EOD (bars of the whole day)
        full = L.CacheFeed(date, L.NMIN).bars(sym)
        d2 = R.decide(date, L.NMIN, L.CacheFeed(date, L.NMIN), uni, earnings,
                      ticket=15_000.0)
        assert d2.get("sym") == sym, (date, sym, d2.get("sym"))   # causal
        tr15 = R.model_trade(full, ticket=15_000.0)
        tr10 = R.model_trade(full, ticket=10_000.0)
        live[date] = {"sym": sym, "action_0936": d1["action"],
                      "cands": d1["candidates"], "fresh": d1.get("fresh"),
                      "tr15": tr15, "tr10": tr10,
                      "pnl15_10bps": R.pnl_of(tr15, 10.0)}
    # ---- compare
    matched, missed, extra, diffs = [], [], [], []
    for date, b in sorted(bt.items()):
        lv = live.get(date)
        if lv is None or lv["sym"] != b["sym"]:
            missed.append({"date": date, "bt_sym": b["sym"],
                           "live_sym": lv["sym"] if lv else None,
                           "live_cands": lv["cands"] if lv else None})
            continue
        t = lv["tr15"]
        ent_same = (t["entry"] is not None and abs(t["entry"] - b["fill_px"])
                    <= 1e-4 * max(1.0, b["fill_px"])) or (t["entry"] is None
                                                          and b["fill_px"] == 0)
        rec = {"date": date, "sym": b["sym"], "entry_live": t["entry"],
               "entry_bt": b["fill_px"], "entry_min_live": t["entry_k"],
               "exit_live": t["exit"], "exit_min_live": t["exit_k"],
               "pnl_live": round(lv["pnl15_10bps"], 2), "pnl_bt": b["tab_pnl"],
               "pnl_diff": round(lv["pnl15_10bps"] - b["tab_pnl"], 2),
               "notional_live": t["notional"], "notional_bt": b["tab_notional"],
               "entry_identical": bool(ent_same)}
        (matched if ent_same else diffs).append(rec)
    for date, lv in sorted(live.items()):
        if date not in bt:
            extra.append({"date": date, "live_sym": lv["sym"],
                          "pnl15_10bps": round(lv["pnl15_10bps"], 2),
                          "cands": lv["cands"]})
    n_bt = len(bt)
    ident = len(matched)
    pnl_d = [r["pnl_diff"] for r in matched]
    live_tk = [lv for lv in live.values()]

    def per_tkt(trs, bps):
        p = [R.pnl_of(t, bps) for t in trs]
        return round(float(np.mean(p)), 2) if p else None

    tr10 = [lv["tr10"] for lv in live_tk if lv["tr10"]["entry"] is not None
            and lv["tr10"]["notional"] >= R.MIN_NOTIONAL]
    exp = {"tickets": len(tr10), "days": len(dates),
           "tickets_per_day": round(len(tr10) / len(dates), 4),
           "mean_notional": round(float(np.mean([t["notional"] for t in tr10])), 0)
           if tr10 else None,
           "per_ticket_10k": {f"{b}bps": per_tkt(tr10, b) for b in (0, 6, 9, 10)},
           "per_day_10k": {f"{b}bps": round(sum(R.pnl_of(t, b) for t in tr10)
                                            / len(dates), 2) for b in (0, 6, 9, 10)},
           "note": "live-code replay at $10,000 tickets (notional = min($10k, "
                   "20% x 5-min volume x fill)); ext-hours exits keep +50 bps"}
    res = {
        "rule": RULE, "days_replayed": len(dates),
        "backtest_tickets": n_bt, "live_picks": len(live),
        "matched_identical_entry": ident,
        "matched_sym_diff_entry": len(diffs),
        "missed": len(missed), "extra": len(extra),
        "parity_pct": round(100.0 * ident / max(n_bt, 1), 1),
        "pnl_diff_abs_max": round(max(map(abs, pnl_d)), 2) if pnl_d else None,
        "pnl_diff_sum": round(sum(pnl_d), 2) if pnl_d else None,
        "backtest_per_ticket_10bps": det["per_ticket"],
        "live_replay_per_ticket_10bps_15k": round(float(np.mean(
            [lv["pnl15_10bps"] for lv in live_tk])), 2) if live_tk else None,
        "live_replay_total_10bps_15k": round(sum(lv["pnl15_10bps"]
                                                 for lv in live_tk), 2),
        "expectation_live": exp,
        "missed_list": missed, "extra_list": extra, "entry_diff_list": diffs,
        "matched_list": matched, "secs": round(time.time() - t0, 1)}
    L.write_atomic(OUT, res)
    print(json.dumps({k: v for k, v in res.items() if not k.endswith("_list")},
                     indent=1))
    for m in missed[:20]:
        print("MISSED", json.dumps(m)[:400])
    for x in extra[:20]:
        print("EXTRA", json.dumps(x)[:400])
    for x in diffs[:20]:
        print("ENTRY-DIFF", json.dumps(x)[:300])


if __name__ == "__main__":
    main()
