"""Day-17 ledger updater. Scratch file for the 2026-08-27 session only.

Heredoc-fed python through the Bash tool stalled once mid-session (2026-08-27
07:30 ET, 16-minute loss). Writing updates through a file removes that failure
mode: the update is idempotent, re-runnable, and visible in git if it half-runs.
"""
import json
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "data" / "paper_days" / "2026-08-27.json"


def load():
    return json.load(open(P))


def save(d):
    json.dump(d, open(P, "w"), indent=1)


def main():
    d = load()
    d["ops"]["heartbeat_et"] = "07:47"

    d["trigger_c"] = [
        {"symbol": "BTCT", "bar_et": "07:06", "signals": ["morning_star"],
         "tag": "STALE", "cadence": "5-min", "actionable": False},
        {"symbol": "BTCT", "bar_et": "07:10", "signals": ["tweezer_bottom"],
         "tag": "STALE", "cadence": "5-min", "actionable": False,
         "note": "dragonfly_doji also fired and was correctly IGNORED - not in the eight-member buy_set"},
        {"symbol": "BTCT", "bar_et": "07:11", "signals": ["morning_star"],
         "tag": "STALE", "cadence": "5-min", "actionable": False},
        {"symbol": "BTCT", "bar_et": "07:24",
         "signals": ["bullish_engulfing", "morning_star", "tweezer_bottom"],
         "tag": "STALE", "age_min": 5, "cadence": "5-min", "actionable": False,
         "note": ("TRIPLE signal - three of the eight buy_set patterns on one bar, the strongest Trigger C "
                  "of the session, read 5 minutes late. It would have been spread-vetoed at arming (BTCT was "
                  "2 ticks = 0.926% wide across the whole window), so no entry was lost - but CADENCE is what "
                  "refused it, and cadence is not allowed to be the thing that refuses.")},
    ]

    d["cadence_decision_2"] = {
        "time_et": "07:30",
        "decision": "ESCALATE to the mandated 1-minute Trigger C poll on BTCT (the TOP name), premarket.",
        "supersedes": "the 06:50 decision to poll OKTA only",
        "reason": ("BTCT took rank #1 at 07:14 and produced FOUR Trigger C fires (07:06, 07:10, 07:11, 07:24), "
                   "every one read STALE under the 5-8 minute cycle cadence - Day 16's #1 lesson reproducing in "
                   "a new session. The 06:50 decision was justified while BTCT was #3 and non-coiled; it stopped "
                   "being justified the moment BTCT became the top-ranked armable name."),
        "poll_shape": ("fetch 1-min bars -> merge -> run `trigger` -> READ THE TAG NOW -> only then wait. The "
                       "wait is never allowed between the trigger call and reading its output (Day-13 defect)."),
        "arming_check_deferred": ("quote + price_book are pulled ONLY when a [TAKEABLE NOW] tag appears, not "
                                  "every minute - the fill-arming rule's re-quote, and it halves per-poll cost."),
        "honest_note": ("With the tick-size floor, BTCT at 2.14 is armable only at EXACTLY one tick, so the odds "
                        "any fresh signal is takeable are low. Polling anyway: the tag does the refusing, not my "
                        "estimate of the odds."),
    }

    d["cycles"].append({
        "n": 7, "time_et": "07:29", "state": "FLAT-1m", "phase": "premarket",
        "rank": "3 crossed / 3 armable", "top": "BTCT", "armable_by_book": 0,
        "btct": {"last": 2.1401, "premkt_high": 2.25, "coil": 0.951, "press": 0.30, "trail10vol": 215534},
        "note": "BTCT printed a new premarket high 2.25 at 07:17 on 120k/124k-share bars, then faded to 2.14",
    })

    d["coverage_gaps"].append({
        "start_et": "07:30", "start_utc": "11:30", "end_et": "07:47", "end_utc": "11:47", "minutes": 17,
        "cause": ("A ledger-update tool call (python heredoc + git commit) stalled and was killed at its "
                  "2-minute timeout, and the stall was not noticed until the next call returned. The 1-minute "
                  "Trigger C poll that had just been declared at 07:30 therefore never started."),
        "settlement": "nothing to settle - flat, no position, no resting order, nothing armed before the gap",
        "entries_credited": 0,
        "rule": "OUTAGE rule 3 - no entries, rankings or verdicts credited for a gap window; no backfill",
        "self_criticism": ("The gap is 100% self-inflicted and it happened in the same minute I wrote that "
                           "cadence is 'the whole ball game'. Declaring a cadence and then losing 17 minutes to "
                           "an unverified write is worse than not declaring it, because the ledger would have "
                           "claimed 1-minute coverage that did not exist."),
        "fix_applied": ("ledger updates now go through plan/_d17_update.py rather than a heredoc, and every "
                        "write is verified by reading a field back before the session moves on"),
    })

    save(d)
    print("ok heartbeat", d["ops"]["heartbeat_et"], "cycles", len(d["cycles"]),
          "trigger_c", len(d["trigger_c"]), "gaps", len(d["coverage_gaps"]))


if __name__ == "__main__":
    main()
