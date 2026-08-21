# Trader-Mimicry Pilot — Pre-Registration (W-campaign Phase 3.4)

**Registered:** 2026-08-21, BEFORE any VOD/archive data was gathered for this pilot.
**Design authority:** `day-trading/trader-mimicry-survey.md` (user-approved). This file binds the
backtest/reconstruction phase. No live mimicry starts from this phase.

## Arms (user-approved)

| Arm | Directory | Role |
|---|---|---|
| Ross Cameron (Warrior Trading, YouTube `@DaytradeWarrior`) | `cameron/` | **Calibration** — his workflow is our strategy's ancestor; measures our execution/latency vs the source |
| TraderTV Live (YouTube `@TraderTVLive`) | `tradertv/` | **Universe-widening** — best surveyed halal pass-rate (~40–60%) |
| Madaz (X `@madaznfootballr` + free recap videos) | `madaz/` | **Backtest-only** — real-time following pre-judged infeasible; archive precision itself is under test |

Target: 2–4 recent weeks of reconstruction per arm.

## Data & extraction protocol

- **Sources:** public YouTube VODs/recaps and public X posts only. No signups, no logins, no
  paywalls, no paid rooms. watch-skill in `--transcript-only` mode (captions-first); **no vision
  model**. A VOD without usable captions is SKIPPED and logged as a coverage gap — it is not
  transcribed by other means for this phase.
- **VOD log:** every VOD processed (or skipped) is recorded in `<arm>/vods.json`:
  `{video_id, url, title, upload_date, duration_s, stream_start_et (if live VOD), status
  (processed | skipped-no-captions | skipped-other), calls_extracted}`.
- **Call record:** every extracted call goes to `<arm>/calls.json`, one row per call:
  `{arm, video_id, vod_ts_s, call_ts_et, ticker, side (long|short), their_px_context
  (stated price/level or null), quote (verbatim transcript snippet), confidence}`.
- **Timestamping standard (binding):** a call COUNTS only if the transcript pins it precisely
  enough to price at 1-minute granularity:
  - Live-stream VODs: caption timestamp + stream start time (`release_timestamp` from video
    metadata) → ET clock time. Counts.
  - Recap/highlight videos: counts ONLY if the trader states a clock time ("at 9:32 I bought…")
    or the platform time is verbally anchored; otherwise the call is logged with
    `confidence: "untimed"` and EXCLUDED from decay/sim measurement.
  - X posts: post timestamp is an UPPER BOUND on entry time (post-fill). Logged, and usable only
    for scanner-overlap/attention analysis, not for entry-decay measurement, unless the post
    itself states the fill time.
- **Side:** short calls are logged but NEVER simulated (cash account, long only). They count
  toward feed volume but not toward mimicable calls.

## Measurement protocol (per counted call)

1. **Halal gate:** `day-trading.py::halal_check` (current screen: debt/mcap ≤10%, cash/mcap ≤10%,
   combined ≤20%, haram revenue <5%, industry screen, refuse-on-no-data). Only verdict
   **PASS** is mimicable. Verdict distribution (PASS / FAIL / CANNOT-VERIFY / NO-DATA) is
   reported per arm. Note: this is today's screen applied retroactively (current fundamentals,
   not point-in-time) — acceptable for a 2–4-week lookback and disclosed here.
2. **Signal decay:** Polygon minute bars (paid key `MASSIVE_KEY`, Credential Manager), full
   session including premarket. Marks:
   - `p0` = Open of the first minute bar with `begins_at >= call_ts`
   - `p60` = Open of the first minute bar with `begins_at >= call_ts + 60s`
   - `p300` = Open of the first minute bar with `begins_at >= call_ts + 300s`
   Decay table reports median and mean of `(p60/p0 − 1)` and `(p300/p0 − 1)` per arm, long calls
   only. Missing bars (halt/no prints) → call excluded from decay, counted as a coverage note.
3. **Mimic simulation ("their entry, our everything else"):** simple explicit replay (documented
   choice — `simulate_trades` entries are pattern-triggered; mimic entries are exogenous
   timestamps, so a replay is cleaner and auditable):
   - Entry: $15,000 ticket at `p60` (honest latency assumption), whole shares.
   - Exit machinery (C37/Z104 base values from `plan/penny_x100.py::BASE_SIM`): hard stop −8%
     from entry; 20% trailing stop from the post-entry high; flatten at 15:00 ET; evaluated on
     minute bars (Low breaches stop → fill at stop price; conservative: stop checked before
     trail, both before new-high update on the same bar).
   - Slippage stress: results shown raw and at 10 bps/side (the C37 stress convention).
   - Arm P&L reported two ways: (a) every PASS call independently; (b) sequential
     one-position-at-a-time (a call arriving while a mimic position is open is skipped),
     $100k/day deploy cap — the cash-account-realistic number.
4. **Scanner overlap:** would our +10% cross scanner have surfaced the name that day —
   first minute bar (premarket included) with `High ≥ 1.10 × prev_close` at or before 14:00 ET
   (the `rotation_sim.py` candidate definition). Overlap % = share of counted calls whose ticker
   crossed that day. Also reported: whether the cross printed BEFORE the call (attention adds
   nothing) vs after (mimicry was earlier than our scanner).

## Kill criteria (verbatim from the approved survey)

> **Kill criteria (pre-registered):** after 20 sessions per feed — fewer than 2 halal-passing calls
> per week, or +60s entry edge ≤ 0 after slippage model, or >80% scanner overlap → kill that arm.

Backtest-phase application: the same thresholds judged on the reconstructed weeks (a reconstruction
that cannot produce timestamped calls at all is also a valid KILL — imprecision is a finding).
Verdict per arm in `PILOT-BACKTEST.md`: CONTINUE to live-mimic phase / KILL with reason.

## Firewall rule (binding)

**Mimic results NEVER mix into the C37 ledger.** Nothing under `data/paper_mimic/` feeds
`data/paper_days/`, the C37 replay numbers, or any adopted-config accounting. This pilot measures
someone else's signal under our rules; it is not our strategy's P&L.
