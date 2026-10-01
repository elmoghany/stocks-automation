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


def r4_shadow(date, booked_syms):
    """LEGACY-15 SHADOW legs: R4 model legs the live book refused on the
    spread/depth veto (never entered). Entry = the ask at the first VETO,
    exit = the model's exit (next-open bearish convention), $10k ticket."""
    vet = P.read_json(P.book_dir("r4") / f"vetoes_{date}.json", []) or []
    first = {}
    for v in vet:
        if v["result"] == "VETO":
            first.setdefault(v["key"], v)
    if not first:
        return []
    try:
        import p3_r4
        legs, _ = p3_r4.live_decision(date, P.M_CLOSE + 1)
    except Exception as e:                              # noqa: BLE001
        return [dict(error=f"r4 replay failed: {e}")]
    out = []
    for key, v in first.items():
        if v["sym"] in booked_syms:
            continue                          # later PASS -> it was traded
        lg = next((x for x in legs if x["sym"] == v["sym"]
                   and P.hhmm(x["t"]) == v["decision"]), None)
        sh = int(P.TICKET // v["ask"]) if v["ask"] else 0
        if lg is None or lg.get("exit") is None:
            out.append(dict(key=key, sym=v["sym"], status="no model exit"))
            continue
        out.append(dict(key=key, sym=v["sym"], shares=sh, entry=v["ask"],
                        exit=lg["exit"], exit_min=P.hhmm(lg["exit_min"]),
                        reason=lg["reason"], why=v["why"],
                        pnl=round((lg["exit"] - v["ask"]) * sh, 2)))
    return out


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
        e = exp.get(book, {})
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
            sh = r4_shadow(date, {x["sym"] for x in tr})
            s["shadow_legs"] = sh
            s["shadow_pnl"] = round(sum(x.get("pnl") or 0 for x in sh), 2)
            s["parity_book_pnl"] = round(s["pnl"] + s["shadow_pnl"], 2)
        eod[book] = s
        sb["rows"].append(dict(date=date, book=book, trades=s["trades"],
                               pnl=s["pnl"], model_pnl=s["model_pnl"],
                               pnl_halal_pass=s["pnl_halal_pass"],
                               halal_pass_trades=s["halal_pass_trades"],
                               cost_usd_vs_mid=s["cost_usd_vs_mid"],
                               trade_pnls=[x["pnl"] for x in tr
                                           if x["pnl"] is not None],
                               shadow_pnl=s.get("shadow_pnl", 0.0)))
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
            c["parity_book_pnl"] = round(c["pnl"] + c["shadow_pnl"], 2)
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
        L.append(f"| {book} | {s['trades']} | {s['pnl']:+,.2f} | "
                 f"{s['model_pnl']:+,.2f} | {s['halal_pass_trades']} | "
                 f"{s['pnl_halal_pass']:+,.2f} | "
                 f"{s['cost_bps_per_side_vs_mid_mean'] if s['cost_bps_per_side_vs_mid_mean'] is not None else 'n/a'} bps | "
                 f"{e.get('per_day', 'n/a')} | {e.get('per_trade', 'n/a')} | "
                 f"{(s.get('vs_expectation') or {}).get('pnl_minus_expected_day', 'n/a')} |")
    L += ["", "## Trades", ""]
    for book in P.BOOKS:
        for x in eod[book]["trade_list"]:
            L.append(f"- {book} {x['sym']} x{x['shares']}: entry "
                     f"{x['entry']} (model {x['model_entry']}) exit {x['exit']}"
                     f" (model {x['model_exit']}) {x['reason']} P&L "
                     f"{x['pnl']:+,.2f} (model {x['model_pnl']}) halal "
                     f"{x['halal']} cost vs mid {x['cost_usd_vs_mid']} $")
    sh = eod["r4"].get("shadow_legs") or []
    if sh:
        L += ["", "## R4 SHADOW legs (vetoed on spread/depth, scored at the "
              "model exit; the backtest-parity book = trades + shadow)", ""]
        for x in sh:
            L.append(f"- {x}")
        L.append(f"- R4 parity-book P&L today: {eod['r4']['parity_book_pnl']:+,.2f}")
    L += ["", "## Cumulative (since the first PAPER-3BOOK day)", "",
          "| book | days | trades | P&L | P&L ex-top-5 | model P&L | "
          "halal-PASS P&L | expected P&L | expected trades | cost vs mid $ |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for book in P.BOOKS:
        c = cum[book]
        L.append(f"| {book} | {c['days']} | {c['trades']} | {c['pnl']:+,.2f}"
                 f" | {c['pnl_ex_top5'] if c['pnl_ex_top5'] is not None else 'n/a (<6 trades)'}"
                 f" | {c['model_pnl']:+,.2f} | {c['pnl_halal_pass']:+,.2f} | "
                 f"{c.get('expected_pnl', 'n/a')} | "
                 f"{c.get('expected_trades', 'n/a')} | {c['cost_usd_vs_mid']} |")
    notes = led.get("notes") or []
    if notes:
        L += ["", "## Session notes", ""] + [f"- {n}" for n in notes]
    P.ledger_path(date, "md").write_text("\n".join(L) + "\n", encoding="utf-8")
    P.emit(dict(eod=date, **{b: {k: eod[b][k] for k in
                                 ("trades", "pnl", "model_pnl",
                                  "pnl_halal_pass")} for b in P.BOOKS}))


if __name__ == "__main__":
    main()
