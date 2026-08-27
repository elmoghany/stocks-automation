"""Day-17: settle the OKTA exit at the 15:00 flatten and close the ledger."""
import json
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "data" / "paper_days" / "2026-08-27.json"

ENTRY, SHARES = 163.85, 91
EXIT = 173.48          # inside bid at 14:57, = bar close 173.55 less half the ~0.14 spread
d = json.load(open(P))

pnl = round((EXIT - ENTRY) * SHARES, 2)
d["ops"]["heartbeat_et"] = "15:39"
d["status"] = "FLAT - session complete (exit settled from the tape)"
d["counts_as_traded_day"] = True
d["pnl_day"] = pnl

t = d["trades"][0]
t["status"] = "CLOSED"
t["exit_time_et"] = "14:57"
t["exit_mechanism"] = "15:00 flatten ladder, first rung at 14:57: marketable limit at bid -1% (floor 171.765)"
t["exit_px"] = EXIT
t["exit_proceeds"] = round(EXIT * SHARES, 2)
t["pnl"] = pnl
t["pnl_pct"] = round((EXIT / ENTRY - 1) * 100, 2)
t["hold_time"] = "5h45m (09:12 -> 14:57)"
t["peak_since_entry"] = 174.85
t["peak_et"] = "13:55"
t["exit_settlement"] = {
    "method": "OUTAGE / DEAD-MONITOR SETTLEMENT rule 2 - armed exit rules replayed over the gap from the tape",
    "why_credited": (
        "The 15:00 flatten is not a discretionary decision - it is a hard, fully specified rule fixed in this "
        "day's config before the session started (all_exits_by 15:00, flatten ladder from 14:57). The rule says "
        "explicitly: 'If none fired by 15:00 ET, exit at the 15:00 flatten.' That is what happened."),
    "rules_replayed": (
        "Every armed exit rule was tested bar by bar over 12:47-15:00 ET on 5-minute bars, whose lows bound the "
        "1-minute lows. Lowest print in the whole window was 170.10 at 12:50. Hard stop 150.742: never within "
        "11.4%. Trail 20% off the 174.85 peak = 139.88: never within 17.8%. Even a pressure-tightened 10% trail "
        "at 157.37 was never touched. Scale-out at 204.8125: never reached, peak was 174.85. NOTHING fired."),
    "exit_bar": "18:57:00Z (14:57 ET): open 173.550, high 173.610, low 173.3201, close 173.550, vol 6,053",
    "fill_basis": (
        "173.48 = the 14:57 bar close 173.55 less half the prevailing ~0.14 spread, i.e. the inside BID a "
        "marketable sell limit would have crossed into. The -1% ladder price (171.765) is a slippage FLOOR, not "
        "the expected fill."),
    "depth_note": (
        "No ladder sweep modelled and none needed: 91 shares of a $23B name trading 15,000+ per minute is far "
        "inside the inside quote. This is the opposite end of the Day-8 ANGX case, where 3,040 shares into a "
        "113-share bid cost $75.43 of self-flattery. The exit-depth correction scales with thinness, and here it "
        "rounds to zero."),
    "bracket": {
        "exit_optimistic_1457_close": 173.55, "pnl_optimistic": round((173.55 - ENTRY) * SHARES, 2),
        "exit_pessimistic_1457_low": 173.3201, "pnl_pessimistic": round((173.3201 - ENTRY) * SHARES, 2),
        "worst_case_with_entry_at_limit_cap": round((EXIT - 164.669) * SHARES, 2),
        "note": (
            "Two independent uncertainties compound: the ENTRY was settled at the 163.85 trigger with a 164.669 "
            "limit cap, and the EXIT is settled from a bar rather than observed. Full honest span is roughly "
            "+$802 to +$883. Booked at +$876.33 using the simulator's own conventions for both legs."),
    },
    "what_was_NOT_credited": (
        "No rotation, no re-rank, no second ticket, and no scale-out decision is credited for the 12:47-15:39 "
        "window. Only the two fully-armed rules - the resting entry stop and the hard 15:00 flatten - were "
        "settled. Every discretionary loop-layer judgement in that window stays unmade (OUTAGE rule 3)."),
}
t["fill_realism"] = {
    "assumed_entry_fill": 163.85, "entry_time_et": "09:12",
    "plus60s_mark": 163.9461, "plus60s_basis": "09:13 bar close",
    "delta_pct": 0.06,
    "note": (
        "Entry filled 0.06% BETTER than the +60s mark - the fourth fill-realism data point and the first "
        "FAVOURABLE one since Day 8. Prior: Day 5 LFST -1.6%, Day 15 CRML -0.92%, Day 16 SMMT -0.25%. The trend "
        "across the campaign is that the penalty shrinks as the name gets more liquid, and on a $23B name it "
        "flipped positive. Note this was a STOP fill at the trigger, not a pattern entry paying the ask, which "
        "is the more favourable of the two mechanics."),
}

d["coverage_gaps"].append({
    "start_et": "12:47", "start_utc": "16:47", "end_et": "15:39", "end_utc": "19:39", "minutes": 172,
    "cause": (
        "Both shells stopped responding. Bash hung on a plain posn.py call, then PowerShell hung on a bare "
        "Get-Date, then Bash hung again on `date -u`; several calls were killed at their timeouts and one was "
        "backgrounded. MCP market data kept working throughout, which is how the gap was eventually detected - "
        "a quote came back stamped 19:39:40Z."),
    "settlement": (
        "SETTLED. No armed rule fired anywhere in the window (lowest print 170.10 against a 150.742 stop), so "
        "the ticket exits on the 15:00 flatten per rule 2. See trades[0].exit_settlement."),
    "entries_credited": 0, "exits_credited": 1, "rankings_credited": 0, "rotations_credited": 0,
    "rule": "OUTAGE / DEAD-MONITOR SETTLEMENT rules 1-4",
    "bias_direction": (
        "Understates a full C37 session. The 14:30 entry cutoff passed unattended, so tickets 2-7 could not be "
        "deployed even though the bench had 129 crossers. It also means the exit price is a settlement rather "
        "than an observed fill - the direction of that error is unknown but bounded at about $21 by the bracket."),
    "worst_consequence": (
        "The 15:00 flatten deadline was BLOWN. The position was still open at 15:39 in reality; only the "
        "settlement convention makes it flat at 14:57. On a live account this is the failure that matters most - "
        "a paper ledger can settle to 15:00, a real broker account would simply still be holding overnight risk."),
    "self_criticism": (
        "Third and worst self-inflicted gap of the session, and the pattern is identical each time: issue a "
        "command, do not verify it returned, lose the clock. I twice wrote fixes into this ledger for exactly "
        "this and twice failed to apply them to the next call. The specific missing control is a CLOCK CHECK "
        "FROM AN INDEPENDENT SOURCE - MCP quote timestamps kept working the entire time and would have shown "
        "the drift immediately at any point."),
    "fix_for_next_session": (
        "1) Never let the shell be the only clock: read the timestamp on every MCP response and compare it to "
        "the expected session time. 2) Hard-schedule the flatten: from 14:30, poll on a short fixed cadence and "
        "treat any single tool call that exceeds ~2 minutes as a shell failure, switching immediately to "
        "MCP-only monitoring plus Write-tool ledger updates, both of which stayed healthy today. 3) The exit is "
        "the one thing that cannot be deferred - it should be driven from the independent clock, not from a "
        "shell loop."),
})

d["cycles"].append({
    "n": 12, "time_et": "14:57", "state": "EXIT (settled)", "phase": "regular",
    "action": f"15:00 flatten ladder; OKTA 91 sh sold at {EXIT} for {pnl:+.2f}",
    "note": "settled from the tape at 15:39 after a 2h52m shell outage; no rule had fired earlier",
})

json.dump(d, open(P, "w"), indent=1)
print(f"EXIT SETTLED  entry {ENTRY} -> exit {EXIT} x{SHARES}  P&L {pnl:+.2f} "
      f"({(EXIT / ENTRY - 1) * 100:+.2f}%)")
print("day pnl:", d["pnl_day"], "| gaps:", len(d["coverage_gaps"]))
