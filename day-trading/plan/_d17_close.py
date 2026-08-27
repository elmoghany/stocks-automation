"""Day-17: lessons, veto rates, campaign arithmetic, verdict. Closes the ledger."""
import json
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "data" / "paper_days" / "2026-08-27.json"
d = json.load(open(P))

PRIOR_DAYS, PRIOR_PER_DAY = 14, -112.95
prior_total = round(PRIOR_DAYS * PRIOR_PER_DAY, 2)
new_total = round(prior_total + d["pnl_day"], 2)
new_days = PRIOR_DAYS + 1

d["premarket_veto_rate"] = {
    "decisions": 3, "vetoed": 3, "rate_pct": 100.0,
    "by_rule": {"spread": 3, "depth": 0, "chase": 0},
    "note": (
        "3/3 premarket, matching the historical 90-100% the V-series flagged as too aggressive. But the tick "
        "analysis reframes it: BTCT's two vetoes were EXACTLY two ticks on a $2.14 stock, i.e. the cap measuring "
        "tick size, while OKTA's 0.557% was 88 ticks and a real liquidity statement. Depth and fill-arming "
        "refused nothing all day. The single arming that cleared all four checks made +$876."),
    "did_the_veto_cost_money": (
        "No. BTCT was refused at 07:15 with the stock near 2.19; it closed the session at 2.06. The spread veto "
        "was a save, not a cost, on the only name it refused."),
}

d["campaign"] = {
    "scored_days_before": PRIOR_DAYS, "cumulative_before": prior_total, "per_day_before": PRIOR_PER_DAY,
    "day17_pnl": d["pnl_day"],
    "scored_days_now": new_days, "cumulative_now": new_total,
    "per_day_now": round(new_total / new_days, 2),
    "honest_baseline_per_day": -163,
    "vs_baseline_today": round(d["pnl_day"] - (-163), 2),
    "vs_baseline_cumulative_per_day": round(new_total / new_days - (-163), 2),
    "note": (
        "Best single day of the campaign. Cumulative live improves from -$112.95/day to -$47.00/day over 15 "
        "scored days, against a -$163/day honest backtest baseline - live now beats the honest backtest by "
        "$116/day. Still negative in absolute terms; one good day does not make an edge. Judge weeks, not days."),
}

d["lessons"] = [
    ("THE HALAL GATE AND THE LIQUIDITY GATE AGREED FOR ONCE, AND THAT IS WHERE THE MONEY WAS. Day 8's structural "
     "finding is that the tradeable books are the leveraged ones. Today OKTA gapped +21% on earnings at a $23B "
     "market cap AND passed the ratio test (combined 12.84 via the one-side carve-out). The rest of the board "
     "behaved exactly as the structural note predicts - CRM at loan 25.4, UCTT at combined 24.77, AAPG at 111.6, "
     "MBUU at 29.7, four liquid names and four financing refusals. The whole day's P&L came from the one name "
     "where the two gates did not conflict. That is worth measuring: how often does the pool contain a "
     "large-cap that clears the ratios, and is that the real driver of the campaign's good days?"),

    ("NEW: THE 0.5% SPREAD CAP IS PART LIQUIDITY RULE, PART TICK-SIZE ARTIFACT. One tick over price P is 0.01/P, "
     "so 0.02/P <= 0.005 gives P >= $4.00 - below $4 a name can NEVER show a two-tick market inside the cap and "
     "must be quoted exactly one tick wide to be armable. Today the same rule vetoed BTCT at exactly 2 ticks "
     "(0.926%, 0.943% on a $2.14 stock) and OKTA at 88 ticks (0.557%): one measured tick size, the other "
     "measured illiquidity. The scan filters Last > $2 and gapper pools skew cheap, so this is a MECHANICAL "
     "candidate for the 90-100% premarket veto rate that has been blamed on miscalibration. The V-series "
     "modelled the veto on a bar-range proxy with no tick floor, so it could not have seen this. Test: split "
     "the veto ledger at $4.00 and check whether sub-$4 spreads cluster at exact tick multiples."),

    ("DAY 16'S L2-vs-NBBO FINDING DID NOT REPRODUCE, AND MAY BE A MEASUREMENT ARTIFACT. Two paired readings "
     "taken seconds apart agreed exactly today (OKTA 1.829/1.829, BTCT 0.943/0.943). I nearly logged a "
     "divergence anyway: BTCT's NBBO read 0.459% at 07:14:07 and its L2 read 0.943% at 07:15:13 - straddling "
     "the cap, so it would have decided the entry - but a re-quote at 07:15:23 returned 0.943%, identical to "
     "the book. The reads were 66 seconds apart on a name moving 2.5% per minute. Day 16's TH observation is "
     "timestamped '09:42-09:43' and may have the same defect. A spread comparison across a one-minute gap on a "
     "gapper measures PRICE MOVEMENT, not feed disagreement."),

    ("THE DAY WAS WON BY AN ORDER ARMED AT 08:27, NOT BY THE SESSION'S ATTENTION. Three self-inflicted shell "
     "outages cost 4h01m; the second swallowed the market open and the third blew the 15:00 flatten deadline. "
     "The P&L survived only because Trigger B was armed with stop, limit, size, protective stop, scale-out and "
     "trail law fully specified and COMMITTED TO GIT before the gap opened, which is exactly the case OUTAGE "
     "rule 2 exists for. This is the strongest evidence yet for resting orders over loop-layer decisions - and "
     "it should be read as a warning, not a reassurance. A paper ledger can settle to 15:00; a real account "
     "would still have been holding at 15:39."),

    ("MCP TIMESTAMPS ARE AN INDEPENDENT CLOCK AND SHOULD BE THE PRIMARY ONE. Both shells died three times while "
     "MCP market data kept working throughout. The outages were only detected when a quote came back stamped "
     "19:39:40Z - two hours and fifty-two minutes after I thought it was. Every MCP response carries a venue "
     "timestamp; reading it costs nothing and would have exposed all three drifts immediately. The shell must "
     "never be the only clock, and from 14:30 the flatten must be driven off the independent clock."),

    ("CADENCE MUST TRACK THE BOOK, NOT THE CLOCK. BTCT fired four buy_set signals premarket including a TRIPLE "
     "at 07:24 (bullish_engulfing + morning_star + tweezer_bottom), all read STALE. None was takeable - BTCT was "
     "two ticks wide across the whole window and would have been spread-vetoed at arming. That is the honest "
     "resolution of Day 16's cadence lesson: polling a name whose spread cannot clear the cap buys nothing, "
     "polling one whose book is tradeable is mandatory. But cadence, not the veto, is what actually refused "
     "those four signals, and cadence is not allowed to be the thing that refuses."),

    ("FOURTH CONSECUTIVE SINGLE-HOLDER DAY, WITH A NEW TWIST. One position, 5h45m, $14,910 of $100,000 deployed. "
     "Days 8, 15, 16, 17 all single-holder - the modal outcome now, not the exception. Today added something "
     "new: the 12:10 bench showed the pool had TRIPLED to 129 names BECAUSE OF OUR OWN POSITION - OKTA's "
     "earnings dragged the whole security/software complex through the +10% gate (CRWD, VEEV, RPD, SAIL, FIG, "
     "PANW, SNPS, TENB). Rotating among those would have been the same bet several times, not diversification. "
     "Does the champion's backtest contain sector-cluster days, and does rotation help or hurt on them?"),

    ("FILL REALISM TURNED POSITIVE FOR THE FIRST TIME SINCE DAY 8. Entry 163.85 against a +60s mark of 163.9461 "
     "= +0.06% FAVOURABLE. Series: Day 5 LFST -1.6%, Day 15 CRML -0.92%, Day 16 SMMT -0.25%, today +0.06%. The "
     "penalty has shrunk monotonically as names got more liquid and has now flipped. Caveat that matters: this "
     "was a STOP fill at the trigger, not a pattern entry paying the ask - the more favourable mechanic of the "
     "two, so it is not a like-for-like continuation of the series."),

    ("EXIT-DEPTH SELF-FLATTERY ROUNDED TO ZERO, CONFIRMING IT SCALES WITH THINNESS. 91 shares of a $23B name "
     "trading 15k+/minute needs no ladder sweep at all. Day 8's ANGX cost $75.43 on a thin book, Day 16's SMMT "
     "$8.42 on a liquid one, today ~$0. Three points now support the same shape: the honest exit correction is "
     "proportional to thinness, not a constant haircut."),

    ("A QUESTION-1-ONLY SCREEN WOULD HAVE ARMED AN INSURER. BVC is ON halal_list.json with the cleanest ratios "
     "on the board (loan 0.00, cash 0.56) and ranked #2 by gain. RH's own profile lists life insurance, "
     "annuities and critical-illness products plus financial-product referrals. Question 2 was the only thing "
     "that refused it - the ANGX pattern, caught pre-arming for the second session running. It was ALSO "
     "premarket-dark (25/25 interpolated bars at a flat 12.10 against a 14.86 scanner mark), so the fake-gap "
     "detector and the compliance gate independently rejected the same name."),

    ("DO NOT INHERIT fake_gap ACROSS DAYS. Day 16 listed RPGL as a fake gap; RPGL is also a halal PASS. Seeding "
     "today's drop-list from that entry would have silently excluded a tradeable name for a reason that is "
     "DAY-SCOPED by construction - a fake gap means 'this name did not trade premarket TODAY'. halal FAIL is "
     "permanent and inherits; fake_gap is not and must be re-detected each session."),
]

d["verdict"] = (
    "GREEN on P&L, RED on process. 1 ticket, OKTA +$876.33 (+5.88%), flat at the 15:00 flatten, zero real "
    "orders - the best single day of the campaign, +$1,039 better than the -$163/day honest baseline, and "
    "cumulative live improves from -$112.95/day to -$47.00/day over 15 scored days. But the day was won by an "
    "order armed at 08:27 and by a settlement rule, not by the session's attention: three self-inflicted shell "
    "outages cost 4h01m, swallowed the market open, and blew the 15:00 flatten deadline outright. Both legs of "
    "the trade are SETTLED from the tape rather than observed, with an honest span of roughly +$802 to +$883. "
    "The process findings are worth more than the P&L: the tick-size floor gives a mechanical candidate "
    "explanation for the premarket veto anomaly, and Day 16's L2-vs-NBBO divergence failed to reproduce and "
    "looks like a stale-comparison artifact."
)

json.dump(d, open(P, "w"), indent=1)
print("CLOSED. pnl", d["pnl_day"], "| lessons", len(d["lessons"]),
      "| cumulative", d["campaign"]["cumulative_now"], "=", d["campaign"]["per_day_now"], "/day")
