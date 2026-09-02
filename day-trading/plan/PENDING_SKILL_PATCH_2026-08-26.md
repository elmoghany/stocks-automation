# PENDING PATCH — `.claude/skills/daytrading-morning.md` (Day-16 postmortem)

The Day-16 session could not apply this itself: **everything under `.claude/`
is write-protected for the agent**, the same guard that stops it self-granting
permissions in `.claude/settings.json`. `plan/paper_day_prompt.txt` carries the
same instruction and *was* updated, so the operational path is covered — this
patch keeps the skill (the canonical protocol) in sync. Apply by hand.

Insert as **step 0 of "## Pre-open (from 6:40)"**, immediately before the
existing step 1 (`Trading-day guard...`):

```markdown
0. **CAPABILITY PROBE — LIVENESS IS NOT CAPABILITY** (Day 16, 2026-08-26).
   Straight after the day-file skeleton, run three cheap probes and record
   them in the day JSON at `ops.capability_probe`: `python -c "print(1)"`,
   `git status --short`, and one MCP call (`get_equity_quotes SPY`).
   Day 16 wrote its skeleton, was logged "confirmed live" by the launcher's
   720 s check and read healthy by the 12:00 watchdog — while unable to run
   python, commit, or fetch a single bar, because `--permission-mode
   acceptEdits` auto-approves *edits only*. Every presence guard in this
   campaign keys on the day file, and the day file is exactly the artefact a
   crippled session can still produce. Any DENIED probe → loud `errors[]`
   entry, a `PERMISSION_BLOCKED_{date}.flag` runbook, a line appended to
   `data/scheduler_log.txt`, a PushNotification — then keep re-probing until
   15:00 (the tradeable window is 09:30–14:30, so a mid-morning unblock
   still trades). **Never improvise around it**: no hand-ranking, no
   substitute price feed, no entries credited for the gap. A blocked day is
   an ops failure — `pnl 0`, `counts_as_traded_day false`, denominator
   unchanged. It is not a flat day.
```

Optionally also append to the `Paper-session ops hardening` history block:

```markdown
4. CAPABILITY PROBE (2026-08-26, Day 16). The dual-timer and watchdog rules
   above all test PRESENCE. Presence and capability are independent: Day 16's
   headless agent was present and inert, and every guard read it as healthy.
   Probe the three capabilities the session actually consumes — python, git
   write, market MCP — and alarm on them exactly as loudly as on a missing
   session. Grants for an unattended run belong on the launcher command line
   (version-controlled), not in an unversioned user-level allowlist that can
   vanish silently. Second-order defect from the same day: the day file is both
   the liveness signal AND the launcher's no-double-launch lock, so a crippled
   session blocks its own relaunch until a human moves the file aside. Split
   them — a separate SESSION_ALIVE_{date}.flag, refreshed only by a session
   whose capability probe came back green.
```
