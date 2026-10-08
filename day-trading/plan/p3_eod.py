"""PAPER-3BOOK end-of-day summary (and the cumulative scoreboard).

Paper only, open-ended. Real orders never, unless the user explicitly
authorizes them in conversation.

Reads, per book (r4, r15, rl):
  data/paper_days/{D}.{book}.flatten.json   every exit the watcher booked
                                            (official quote fill + model fill)
  data/paper/halal_tags_{D}.json            halal TAG per symbol (live_halal)
  data/paper/p3_expectations.json           backtest expectation per book
  data/paper_days/{D}.3book.json            the session ledger (merged into)
Writes:
  data/paper_days/{D}.3book.json  -> "eod" block
  data/paper_days/{D}.3book.md    -> human summary
  data/paper_days/3book_scoreboard.json  cumulative, one row per book-day

R4 (R4-FIX 2026-10-08) is two rows: the R4 LIVE book (its trades, scored
against p3_expectations "r4_live") and the R4 PARITY/MODEL track (the
model legs replayed from the day's scans + bars at model fills, $10k,
scored against "r4"), plus SHADOW legs (model legs live did not take) and
the live track's refused candidates by reason (data/paper/r4/refusals_{D}).

Every book is scored against ITS OWN backtest expectation at realistic
cost (per trade and per day), never against C37. P&L is reported for all
trades and for halal-PASS trades only. Realized cost per side is measured
against the quote MID captured at the decision minute.

    python plan/p3_eod.py [--date D]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_lib as P                                          # noqa: E402

NAMES = {"r4": "R4 champion-replay coil, no stop (gapper scanner)",
         "r15": "R15 fresh earnings & green @09:35, h60",
         "rl": "RL-SCOUT v2 approach-4 seed-0 rule"}


def book_trades(date, book):
    fl = P.read_json(P.DATA / "paper_days" / f"{date}.{book}.flatten.json",
                     {}) or {}
    tags = P.read_json(P.DATA / "paper" / f"halal_tags_{date}.json", {}) or {}
    out = []
    for r in fl.get("records", []):
        p3 = r.get("p3") or {}
        sh = r.get("shares_exited") or r.get("shares_initial") or 0
        eq, xq = p3.get("entry_quote") or {}, p3.get("exit_quote") or {}
        cost_usd, cost_bps = None, None
        if eq.get("mid") and xq.get("mid") and r.get("vwap"):
            c_in = (r["entry"] - eq["mid"]) * sh
            c_out = (xq["mid"] - r["vwap"]) * sh
            cost_usd = round(c_in + c_out, 2)
            notional = (r["entry"] + r["vwap"]) * sh
            cost_bps = round(cost_usd / notional * 1e4, 2) if notional else None
        h = tags.get(r["sym"]) or {}
        out.append(dict(
            sym=r["sym"], shares=sh, entry=r["entry"], exit=r.get("vwap"),
            pnl=r.get("pnl"), model_entry=p3.get("model_entry"),
            model_exit=p3.get("model_exit"), model_pnl=p3.get("model_pnl"),
            reason=p3.get("reason") or r.get("exit_kind"),
            entry_cost_bps_vs_mid=eq.get("cost_bps_vs_mid"),
            exit_cost_bps_vs_mid=p3.get("exit_cost_bps_vs_mid"),
            cost_usd_vs_mid=cost_usd, cost_bps_per_side_vs_mid=cost_bps,
            official_src=p3.get("official_src"),
            halal=h.get("verdict", "UNTAGGED"),
            halal_pass=bool(h.get("pass"))))
    return out


def summarize(trades):
    def tot(xs, k):
        v = [x[k] for x in xs if x.get(k) is not None]
        return round(sum(v), 2) if v else 0.0
    hp = [x for x in trades if x["halal_pass"]]
    costs = [x["cost_bps_per_side_vs_mid"] for x in trades
             if x["cost_bps_per_side_vs_mid"] is not None]
    return dict(trades=len(trades), pnl=tot(trades, "pnl"),
                model_pnl=tot(trades, "model_pnl"),
                halal_pass_trades=len(hp), pnl_halal_pass=tot(hp, "pnl"),
                per_trade=round(tot(trades, "pnl") / len(trades), 2)
                if trades else None,
                cost_bps_per_side_vs_mid_mean=round(sum(costs) / len(costs), 2)
                if costs else None,
                cost_usd_vs_mid=tot(trades, "cost_usd_vs_mid"))


def r4_parity(date, trades):
    """R4-FIX (2026-10-08): the PARITY/MODEL track = today's model legs
    (p3_r4.run_live replayed on the day's snapshots + bars, model fills,
    $10k), scored apart from the LIVE book. SHADOW legs = model legs the
    live book did not take; entry = the ask of the first live-track book
    refusal of that (sym, grid) if one was logged, else the model entry."""
    vet = P.read_json(P.book_dir("r4") / f"vetoes_{date}.json", []) or []
    first = {}
    for v in vet:
        if v["result"] == "VETO":
            first.setdefault(v["key"], v)
    try:
        import p3_r4
        legs, st = p3_r4.live_decision(date, P.M_CLOSE + 1)
    except Exception as e:                              # noqa: BLE001
        return dict(error=f"r4 replay failed: {e}", legs=[], shadow=[])
    taken = {(x["sym"], x.get("model_entry")) for x in trades}
    taken_syms = {x["sym"] for x in trades}
    model, shadow = [], []
    for lg in legs:
        if lg.get("exit") is None:
            model.append(dict(sym=lg["sym"], decision=P.hhmm(lg["t"]),
                              status="no model exit (bars missing?)"))
            continue
        g = (lg["exit"] - lg["entry"]) * lg["shares"]
        n15 = g - (lg["entry"] + lg["exit"]) * lg["shares"] * 15 / 1e4
        row = dict(sym=lg["sym"], decision=P.hhmm(lg["t"]),
                   entry_min=P.hhmm(lg["entry_min"]), entry=lg["entry"],
                   exit_min=P.hhmm(lg["exit_min"]), exit=lg["exit"],
                   shares=lg["shares"], reason=lg["reason"],
                   gross=round(g, 2), net15=round(n15, 2))
        model.append(row)
        if lg["sym"] in taken_syms:
            continue                       # the live book traded this name
        v = first.get(f"{lg['sym']}@{P.hhmm(lg['t'])}")
        if v and v.get("ask"):
            ent, src = float(v["ask"]), "first refusal ask"
            sh = int(P.TICKET // ent)
        else:
            ent, src, sh = lg["entry"], "model entry (not checked)", \
                lg["shares"]
        shadow.append(dict(key=f"{lg['sym']}@{P.hhmm(lg['t'])}",
                           sym=lg["sym"], shares=sh, entry=ent,
                           entry_src=src, exit=lg["exit"],
                           exit_min=P.hhmm(lg["exit_min"]),
                           reason=lg["reason"],
                           why=(v or {}).get("why", "live took another name "
                                             "or was holding"),
                           pnl=round((lg["exit"] - ent) * sh, 2)))
    ok = [x for x in model if "gross" in x]
    _ = taken
    return dict(legs=model, shadow=shadow, state=st.get("state"),
                trades=len(ok), pnl=round(sum(x["gross"] for x in ok), 2),
                net15=round(sum(x["net15"] for x in ok), 2))


def r4_refusals(date):
    """LIVE-track refused candidates by reason (unique sym x grid)."""
    log = P.read_json(P.book_dir("r4") / f"refusals_{date}.json", []) or []
    by = {}
    for x in log:
        by[x["reason"]] = by.get(x["reason"], 0) + 1
    return dict(sorted(by.items(), key=lambda kv: -kv[1]))


def ex_top5(pnls):
    xs = sorted(pnls)
    return round(sum(xs[:-5]), 2) if len(xs) > 5 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    a = ap.parse_args()
    date = a.date or P.now_et().date().isoformat()
    exp = P.read_json(P.DATA / "paper" / "p3_expectations.json", {}) or {}
    sb_f = P.DATA / "paper_days" / "3book_scoreboard.json"
    sb = P.read_json(sb_f, {"rows": []}) or {"rows": []}
    sb["rows"] = [r for r in sb["rows"] if r["date"] != date]
    eod = {}
    for book in P.BOOKS:
        tr = book_trades(date, book)
        s = summarize(tr)
        e = exp.get("r4_live", exp.get("r4", {})) if book == "r4" \
            else exp.get(book, {})
        s["expectation"] = e
        if e:
            s["vs_expectation"] = dict(
                pnl_minus_expected_day=round(s["pnl"] - e["per_day"], 2),
                per_trade_minus_expected=None if s["per_trade"] is None
                else round(s["per_trade"] - e["per_trade"], 2),
                trades_minus_expected_rate=round(
                    s["trades"] - e["trades_per_day"], 2))
        s["trade_list"] = tr
        if book == "r4":
            par = r4_parity(date, tr)
            sh = par.get("shadow") or []
            s["shadow_legs"] = sh
            s["shadow_pnl"] = round(sum(x.get("pnl") or 0 for x in sh), 2)
            ep = exp.get("r4", {})
            s["parity"] = dict(
                trades=par.get("trades", 0), pnl=par.get("pnl", 0.0),
                net15=par.get("net15", 0.0), legs=par.get("legs", []),
                error=par.get("error"), expectation=ep,
                pnl_minus_expected_day=round(par.get("net15", 0.0)
                                             - ep.get("per_day", 0.0), 2)
                if ep else None)
            s["parity_book_pnl"] = par.get("pnl", 0.0)
            s["refused_by_reason"] = r4_refusals(date)
        eod[book] = s
        sb["rows"].append(dict(date=date, book=book, trades=s["trades"],
                               pnl=s["pnl"], model_pnl=s["model_pnl"],
                               pnl_halal_pass=s["pnl_halal_pass"],
                               halal_pass_trades=s["halal_pass_trades"],
                               cost_usd_vs_mid=s["cost_usd_vs_mid"],
                               trade_pnls=[x["pnl"] for x in tr
                                           if x["pnl"] is not None],
                               shadow_pnl=s.get("shadow_pnl", 0.0),
                               **({} if book != "r4" else dict(
                                   parity_trades=s["parity"]["trades"],
                                   parity_pnl=s["parity"]["pnl"],
                                   parity_net15=s["parity"]["net15"],
                                   refused=s["refused_by_reason"],
                                   live_track=True))))
    sb["rows"].sort(key=lambda r: (r["date"], r["book"]))
    cum = {}
    for book in P.BOOKS:
        rows = [r for r in sb["rows"] if r["book"] == book]
        nd = len(rows)
        e = exp.get(book, {})
        c = dict(days=nd, trades=sum(r["trades"] for r in rows),
                 pnl=round(sum(r["pnl"] for r in rows), 2),
                 model_pnl=round(sum(r["model_pnl"] for r in rows), 2),
                 pnl_halal_pass=round(sum(r["pnl_halal_pass"] for r in rows), 2),
                 cost_usd_vs_mid=round(sum(r["cost_usd_vs_mid"] or 0
                                           for r in rows), 2))
        allp = [p for r in rows for p in (r.get("trade_pnls") or [])]
        c["pnl_ex_top5"] = ex_top5(allp)
        c["per_trade_ex_top5"] = (round(c["pnl_ex_top5"] / (len(allp) - 5), 2)
                                  if c["pnl_ex_top5"] is not None else None)
        if book == "r4":
            c["shadow_pnl"] = round(sum(r.get("shadow_pnl") or 0
                                        for r in rows), 2)
            # parity book: model-track P&L where recorded (R4-FIX on),
            # live + shadow before (the old lockstep definition)
            c["parity_book_pnl"] = round(sum(
                r["parity_pnl"] if "parity_pnl" in r
                else r["pnl"] + (r.get("shadow_pnl") or 0) for r in rows), 2)
            c["parity_trades"] = sum(r.get("parity_trades", 0) for r in rows)
            c["parity_net15"] = round(sum(r.get("parity_net15", 0)
                                          for r in rows), 2)
            ep = exp.get("r4", {})
            if ep:
                c["parity_expected_pnl"] = round(ep["per_day"] * nd, 2)
            c["live_track_days"] = sum(1 for r in rows if r.get("live_track"))
            ref = {}
            for r in rows:
                for k, v in (r.get("refused") or {}).items():
                    ref[k] = ref.get(k, 0) + v
            c["refused_by_reason"] = ref
            e = exp.get("r4_live", e)
        if e:
            c["expected_pnl"] = round(e["per_day"] * nd, 2)
            c["expected_trades"] = round(e["trades_per_day"] * nd, 2)
        cum[book] = c
    sb["cumulative"] = cum
    P.write_atomic(sb_f, sb)

    led_f = P.ledger_path(date)
    led = P.read_json(led_f, {}) or {}
    led.setdefault("date", date)
    led.setdefault("mode", "PAPER-3BOOK")
    led["eod"] = eod
    led["cumulative"] = cum
    P.write_atomic(led_f, led)

    L = [f"# PAPER-3BOOK {date}", "",
         "Paper only, open-ended. Real orders never, unless the user "
         "explicitly authorizes them in conversation.", "",
         "| book | trades | P&L (quote fills) | P&L model fills | halal-PASS "
         "trades | P&L halal-PASS | cost/side vs mid | expected/day | "
         "expected/trade | vs expectation (day) |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for book in P.BOOKS:
        s, e = eod[book], eod[book].get("expectation") or {}
        lab = "r4 LIVE" if book == "r4" else book
        L.append(f"| {lab} | {s['trades']} | {s['pnl']:+,.2f} | "
                 f"{s['model_pnl']:+,.2f} | {s['halal_pass_trades']} | "
                 f"{s['pnl_halal_pass']:+,.2f} | "
                 f"{s['cost_bps_per_side_vs_mid_mean'] if s['cost_bps_per_side_vs_mid_mean'] is not None else 'n/a'} bps | "
                 f"{e.get('per_day', 'n/a')} | {e.get('per_trade', 'n/a')} | "
                 f"{(s.get('vs_expectation') or {}).get('pnl_minus_expected_day', 'n/a')} |")
        if book == "r4":
            pa = s["parity"]
            ep = pa.get("expectation") or {}
            L.append(f"| r4 PARITY (model track, $10k, model fills; net "
                     f"15 bps {pa['net15']:+,.2f}) | {pa['trades']} | n/a | "
                     f"{pa['pnl']:+,.2f} | - | - | - | "
                     f"{ep.get('per_day', 'n/a')} | "
                     f"{ep.get('per_trade', 'n/a')} | "
                     f"{pa.get('pnl_minus_expected_day', 'n/a')} |")
    ref = eod["r4"].get("refused_by_reason") or {}
    L += ["", "R4 LIVE refused candidates today (unique name x grid): "
          + (", ".join(f"{k} {v}" for k, v in ref.items()) or "none")]
    if eod["r4"]["parity"].get("error"):
        L.append(f"R4 PARITY replay error: {eod['r4']['parity']['error']}")
    L += ["", "## Trades", ""]
    for book in P.BOOKS:
        for x in eod[book]["trade_list"]:
            L.append(f"- {book} {x['sym']} x{x['shares']}: entry "
                     f"{x['entry']} (model {x['model_entry']}) exit {x['exit']}"
                     f" (model {x['model_exit']}) {x['reason']} P&L "
                     f"{x['pnl']:+,.2f} (model {x['model_pnl']}) halal "
                     f"{x['halal']} cost vs mid {x['cost_usd_vs_mid']} $")
    pl = eod["r4"]["parity"].get("legs") or []
    if pl:
        L += ["", "## R4 PARITY / MODEL track legs (scoring only)", ""]
        for x in pl:
            L.append(f"- {x}")
    sh = eod["r4"].get("shadow_legs") or []
    if sh:
        L += ["", "## R4 SHADOW legs (model legs the live book did not take;"
              " entry = first refusal ask when logged, exit = the model's)",
              ""]
        for x in sh:
            L.append(f"- {x}")
        L.append(f"- R4 shadow P&L today: {eod['r4']['shadow_pnl']:+,.2f}; "
                 f"R4 parity (model) P&L today: "
                 f"{eod['r4']['parity_book_pnl']:+,.2f}")
    L += ["", "## Cumulative (since the first PAPER-3BOOK day)", "",
          "| book | days | trades | P&L | P&L ex-top-5 | model P&L | "
          "halal-PASS P&L | expected P&L | expected trades | cost vs mid $ |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for book in P.BOOKS:
        c = cum[book]
        lab = "r4 LIVE" if book == "r4" else book
        L.append(f"| {lab} | {c['days']} | {c['trades']} | {c['pnl']:+,.2f}"
                 f" | {c['pnl_ex_top5'] if c['pnl_ex_top5'] is not None else 'n/a (<6 trades)'}"
                 f" | {c['model_pnl']:+,.2f} | {c['pnl_halal_pass']:+,.2f} | "
                 f"{c.get('expected_pnl', 'n/a')} | "
                 f"{c.get('expected_trades', 'n/a')} | {c['cost_usd_vs_mid']} |")
        if book == "r4":
            L.append(f"| r4 PARITY (model) | {c['days']} | "
                     f"{c['parity_trades']} | {c['parity_book_pnl']:+,.2f} | "
                     f"n/a | net 15 bps {c['parity_net15']:+,.2f} | - | "
                     f"{c.get('parity_expected_pnl', 'n/a')} | "
                     f"{round(exp.get('r4', {}).get('trades_per_day', 0) * c['days'], 2)} | - |")
    rc = cum["r4"].get("refused_by_reason") or {}
    if rc:
        L += ["", "R4 LIVE refused candidates, cumulative: "
              + ", ".join(f"{k} {v}" for k, v in rc.items())]
    notes = led.get("notes") or []
    if notes:
        L += ["", "## Session notes", ""] + [f"- {n}" for n in notes]
    P.ledger_path(date, "md").write_text("\n".join(L) + "\n", encoding="utf-8")
    P.emit(dict(eod=date, **{b: {k: eod[b][k] for k in
                                 ("trades", "pnl", "model_pnl",
                                  "pnl_halal_pass")} for b in P.BOOKS}))


if __name__ == "__main__":
    main()
