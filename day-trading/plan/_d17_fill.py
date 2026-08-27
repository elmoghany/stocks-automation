"""Day-17: settle the OKTA Trigger B fill from the tape and log the outage."""
import json
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "data" / "paper_days" / "2026-08-27.json"

d = json.load(open(P))
d["ops"]["heartbeat_et"] = "09:32"
d["status"] = "HOLDING - OKTA 91 sh from 163.85 (settled fill), 6 tickets remain"
d["counts_as_traded_day"] = True

d["armed"][0]["status"] = "FILLED 09:12 ET (settled from the tape, see coverage gap 2)"

d["trades"].append({
    "ticket": 1, "symbol": "OKTA", "side": "BUY", "status": "OPEN",
    "entry_trigger": "B - premarket/session-high stop-buy, armed 08:27 at the 163.85 premarket high",
    "armed_et": "08:27",
    "entry_time_et": "09:12",
    "entry_bar_utc": "2026-08-27T13:12:00Z",
    "order_type": "STOP-LIMIT BUY (paper, resting): stop 163.85, limit 164.669",
    "entry_px": 163.85,
    "shares": 91,
    "notional": 14910.35,
    "prev_close": 134.42,
    "gain_at_entry_pct": 21.89,
    "session": "pre (09:12 ET is premarket; C37 allows entries from 07:00)",
    "fill_settlement": {
        "method": "OUTAGE / DEAD-MONITOR SETTLEMENT rule 2 - a rule ARMED BEFORE the gap, settled from the tape",
        "why_this_is_not_a_backfill": (
            "The order was armed at 08:27 with stop, limit, size, protective stop, scale-out level and trail law "
            "all fully specified, and committed to git at 08:27 BEFORE the gap opened at 08:36. Nothing about the "
            "entry was decided with hindsight. This is precisely the case the settlement rule exists for, and it "
            "is the opposite of crediting a rotation pick or a trigger that was never executed live (rule 3)."),
        "trigger_bar": "13:12:00Z (09:12 ET): open 163.20, high 164.05, low 163.00, close 164.00, vol 3,699",
        "intrabar_semantic": (
            "a resting BUY stop fills intrabar against the bar HIGH, not against a polled price - the bar high "
            "164.05 crossed the 163.85 stop, and 164.05 is inside the 164.669 limit, so the order fills"),
        "fill_price_basis": (
            "163.85, the trigger price. This is the simulator's convention and the FILL-ARMING RULE's stated "
            "purpose: 'the sim fills breaks AT the trigger, not at a post-break sweep'."),
        "bracket": {
            "optimistic": 163.85, "pessimistic": 164.669,
            "pessimistic_basis": "the 164.669 limit cap, the worst price the order could legally have taken",
            "notional_spread": 74.53,
            "note": "P&L uncertainty from the settlement is bounded at $74.53 on this ticket and is disclosed, not hidden."},
        "verification": (
            "plan/bars_paste.py re-ran the intrabar stop test over the cached 1-minute bars with "
            "--after=2026-08-27T12:27:00Z so pre-arm bars could not falsely trip it, and reported "
            "'STOP 163.85 WOULD FILL at 2026-08-27T13:12:00Z (bar high 164.050000)'. Mechanical, not asserted."),
    },
    "size_checks": {"trailing10_traded_min_volume_at_arm": 3293, "cap_20pct": 659, "shares": 91,
                    "pct_of_cap": 13.8, "binding": False},
    "spread_check_at_arm": {"spread_pct_L2": 0.2665, "spread_pct_NBBO": 0.349, "cap_pct": 0.5, "verdict": "PASS"},
    "depth_check_at_arm": {"cum_ask_inside_to_limit": 1056, "intended": 91, "pct_of_intended": 1160.4,
                           "verdict": "PASS"},
    "protective_stop": 150.742,
    "stop_basis": "max(entry x 0.92, peak x 0.60) = 163.85 x 0.92; armed at the moment of fill",
    "scale_out_level": 204.8125,
    "scale_out_rule": "bank 1/3 at +25% UNLESS 10-bar pressure >= +0.3",
    "trail_rule": "20% from peak; 10% when 10-bar pressure <= -0.3; 40% when >= +0.3",
    "peak_since_entry": 169.11,
    "peak_et": "09:27",
    "max_adverse_since_entry": {"px": 161.2026, "et": "09:22", "drawdown_pct": -1.62},
    "gap_window_exit_replay": (
        "No exit rule fired during the unmonitored window. Replayed bar by bar in time order over 09:12-09:28: "
        "hard stop 150.742 never approached (lowest print since entry 161.2026, 6.9% above it); 20% trail from a "
        "169.11 peak sits at 135.29 and even the tightened 10% trail sits at 152.20, both far below every bar; "
        "scale-out at 204.8125 never reached. Bearish-pattern exits are LOOP-LAYER judgement calls and are "
        "deliberately NOT settled from hindsight - only the armed rules are."),
    "notes": "NO REAL ORDER. Paper ledger only. First fill of Day 17.",
})

d["coverage_gaps"].append({
    "start_et": "08:36", "start_utc": "12:36", "end_et": "09:28", "end_utc": "13:28", "minutes": 52,
    "cause": (
        "Shell failure. A `python -c` written with double quotes contained an escaped \\$(date ...) which leaked "
        "the backslash into the shell command that followed it; the malformed `while` loop then wedged the "
        "persistent Bash session so completely that even a bare `date -u` timed out. PowerShell was also "
        "unusable at first because `cd <path>` in a compound command triggers a permission prompt that hangs a "
        "non-interactive session. Recovery came from calling PowerShell WITHOUT cd and using `git -C` and "
        "absolute paths."),
    "settlement": (
        "SETTLED, not backfilled. The armed Trigger B stop-limit filled at 09:12 ET inside this window and is "
        "credited under rule 2 because it was armed and committed at 08:27, before the gap. All exit rules were "
        "replayed over the window and none fired. See trades[0].fill_settlement."),
    "entries_credited": 1,
    "entries_credited_justification": "one, and only because it was a fully specified resting order armed before the gap",
    "rankings_credited": 0,
    "verdicts_credited": 0,
    "rule": "OUTAGE / DEAD-MONITOR SETTLEMENT rules 1-3",
    "bias_direction": (
        "The gap costs COVERAGE, not this entry. What was genuinely lost is 52 minutes of Trigger C polling and "
        "re-ranking across the 09:30 open - the single densest decision window of the day - and any chance to "
        "rotate. A full C37 session would have had the open under 1-minute watch; this one did not."),
    "self_criticism": (
        "Second self-inflicted gap of the session, and far more expensive than the first: it swallowed the "
        "market open. Both had the same root cause - issuing a compound shell command and not verifying it "
        "returned. The 07:30 fix (write through a script file) was applied to ledger writes but NOT to the "
        "shell-quoting pattern that actually caused this one."),
    "fix_applied": (
        "1) never embed an escaped $ inside a double-quoted python -c that is chained to further shell commands; "
        "2) never use `cd` in a compound command - use absolute paths and `git -C`; "
        "3) treat PowerShell as the fallback shell when Bash stops responding, and verify the clock from MCP "
        "quote timestamps, which kept working throughout and are an independent clock source."),
})

d["cycles"].append({
    "n": 10, "time_et": "09:12", "state": "ENTRY (settled)", "phase": "premarket",
    "top": "OKTA", "action": "Trigger B stop-limit filled intrabar at 163.85 x 91 sh",
    "note": "discovered at 09:28 on recovery from the shell outage, not observed live",
})

json.dump(d, open(P, "w"), indent=1)
print("SETTLED entry. status:", d["status"])
print("trades:", len(d["trades"]), "gaps:", len(d["coverage_gaps"]))
