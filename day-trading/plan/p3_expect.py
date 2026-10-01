"""PAPER-3BOOK: build data/paper/p3_expectations.json, the per-book
backtest expectation every EOD is scored against (never C37).

Inputs (all produced by committed code):
  data/paper/parity/r4.json   expectation_live (live code, $10k tickets,
                              next-open bearish fill) -- plan/p3_parity_r4.py
  data/paper/parity/r15.json  expectation_live  -- plan/p3_parity_r15.py
  data/paper/parity/rl.json   expectation_live  -- plan/p3_parity_rl.py
  plan/pa_out/cp_r4_legs.json, data/massive/cat/rule_detail.json,
  plan/crs_rl2_legs.json      backtest leg dumps, for the ex-top-5 figures

Realistic cost per side (cost-rescore.md / LEGACY-14 / LIVE-COST-TRUTH):
  R4  15 bps (gapper entries, LEGACY-14's middle of 12-18; the R4-fill-
      specific estimate is 28.75, reported alongside)
  R15  9 bps (wide universe at 09:35, PESSIMISM-AUDIT)
  RL   6 bps (wide universe all-day)

    python plan/p3_expect.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_lib as P                                          # noqa: E402

PAR = P.DATA / "paper" / "parity"
COST = {"r4": 15.0, "r15": 9.0, "rl": 6.0}


def lin(by, b):
    """per-ticket / per-day at b bps, linear between the 0 and 10 rows."""
    k0, k10 = by.get("0") or by.get("0bps"), by.get("10") or by.get("10bps")
    return k0 + (k10 - k0) * b / 10.0


def ex_top5(rets, b, ticket=P.TICKET):
    """$/ticket at $10k from gross returns per $, minus 2*b bps, with and
    without the five best tickets."""
    r = np.sort(np.asarray(rets, float))
    net = r * ticket - 2 * b / 1e4 * ticket
    return (round(float(net.mean()), 2),
            round(float(net[:-5].mean()), 2) if len(net) > 5 else None)


def main():
    out = {"built": P.now_et().isoformat(), "ticket": P.TICKET,
           "cost_bps_per_side": COST, "note":
           "per_trade / per_day at the book's realistic cost from the live-"
           "code replay at $10k; ex_top5 from the backtest leg dump at the "
           "same cost. Score live raw AND ex-top-5."}
    # R4
    r4 = json.loads((PAR / "r4.json").read_text())
    by = r4["expectation_live"]["by_bps"]["live_next_open"]
    pt = {k: v["per_ticket"] for k, v in by.items()}
    pdy = {k: v["per_day"] for k, v in by.items()}
    tpd = by["0"]["tickets_per_day"]
    legs = json.loads((P.PLAN / "pa_out" / "cp_r4_legs.json").read_text())
    rets = [x["gross"] / (x["entry"] * x["shares"])
            for x in legs["legs"]["R4"]]
    raw, ex5 = ex_top5(rets, COST["r4"])
    out["r4"] = dict(per_trade=round(lin(pt, COST["r4"]), 2),
                     per_day=round(lin(pdy, COST["r4"]), 2),
                     trades_per_day=tpd,
                     per_trade_at_28_75bps=by["28.75"]["per_ticket"],
                     per_day_at_28_75bps=by["28.75"]["per_day"],
                     backtest_per_trade=raw, backtest_per_trade_ex_top5=ex5,
                     aug2026_note="R4 lost -$4,392 over the 22 out-of-sample "
                     "August-2026 sessions (LEGACY-14 / champion-replay "
                     "OOS block); a red first weeks is inside expectation",
                     legacy15_note="with the live 0.5% spread veto the kept "
                     "legs are ~ -$28 gross per $10k ex-top-5 (LEGACY-15); "
                     "the backtest edge lives in the thin names the veto "
                     "refuses -- the SHADOW book measures that")
    # R15
    r15 = json.loads((PAR / "r15.json").read_text())["expectation_live"]
    ml = json.loads((PAR / "r15.json").read_text()).get("matched_list") or []
    rets15 = [(x["exit_live"] - x["entry_live"]) / x["entry_live"]
              for x in ml if x.get("exit_live") and x.get("entry_live")]
    raw15, ex515 = ex_top5(rets15, COST["r15"]) if rets15 else (None, None)
    out["r15"] = dict(per_trade=round(lin(r15["per_ticket_10k"], COST["r15"]), 2),
                      per_day=round(lin(r15["per_day_10k"], COST["r15"]), 2),
                      trades_per_day=r15["tickets_per_day"],
                      backtest_per_trade=raw15,
                      backtest_per_trade_ex_top5=ex515)
    # RL
    rlf = PAR / "rl.json"
    if rlf.exists():
        live = json.loads(rlf.read_text()).get("live") or {}
        pt = {k: v["per_ticket"] for k, v in live.items()}
        pdy = {k: v["per_day"] for k, v in live.items()}
        rl = dict(tickets_per_day=(live.get("0") or {}).get("tkt_per_day"))
        rlegs = json.loads((P.PLAN / "crs_rl2_legs.json").read_text())
        rets_rl = [(x["px_out"] - x["px_in"]) / x["px_in"]
                   for x in rlegs["legs"]["RULE"]]
        rawrl, ex5rl = ex_top5(rets_rl, COST["rl"])
        out["rl"] = dict(per_trade=round(lin(pt, COST["rl"]), 2) if pt else None,
                         per_day=round(lin(pdy, COST["rl"]), 2) if pdy else None,
                         trades_per_day=rl.get("tickets_per_day"),
                         backtest_per_trade=rawrl,
                         backtest_per_trade_ex_top5=ex5rl)
    P.write_atomic(P.DATA / "paper" / "p3_expectations.json", out)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
