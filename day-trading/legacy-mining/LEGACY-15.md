# LEGACY-15: what the live C37 paper ledgers showed that the backtests could not

Analyst: LEGACY-15 of 15, 2026-10-01. Scope: the live paper sessions. That is 21 C37 sessions, 2026-08-10 → 09-18 (`data/paper_days/*.json|md`), plus Days 1–4 (C21/C30/C35, a single TWLO ticket, not analysed). I used the veto logs, `data/liquidity_truth.json`, the scan dumps and scan_state files, and the cached minute bars.

Rules followed: halal is ignored; nothing was fetched; no existing file was edited; costs are stated gross and net.

Scripts (all read-only; run in this order):
- `plan/lm15_index.py`: indexes the cached m1 bars for the paper dates. Coverage runs to 09-01; after that only the traded names have bars.
- `plan/lm15_vetoes.py`: pulls 222 veto decisions from the ledgers and liquidity_truth, giving 43 symbol-days.
- `plan/lm15_cf.py`: the counterfactual "what if we had ignored the veto".
- `plan/lm15_traded.py`: the same simulation on the 21 tickets, as a control.
- `plan/lm15_summary.py`
- `plan/lm15_movers.py`: the best mover of each day and why we didn't trade it.
- `plan/lm15_r4veto.py` and `plan/lm15_r4veto2.py`: a live-style book veto on R4's 965 legs and its 30-seed random controls, using the cp_panel.
- `plan/lm15_gain.py`: P&L by how far the name was already up at entry.

Counterfactual simulation: the C37 skeleton.
- Entry: buy at the ask (last trade + ½ the logged spread) at the minute of the veto.
- Exits: −8% hard stop on intrabar lows (a gap-through fills at the open), otherwise flatten at the 14:59 close less 5 bps.
- Run on the 21 real tickets, this same simulation gives −1.14% per ticket. They were booked at −$193 on ~$15k, about −1.29%. So the simulation is a fair control.

## 1. The ledger itself (21 C37 tickets)

| slice | n | booked $ | $/ticket (~$15k) |
|---|---:|---:|---:|
| all | 21 | **−4,048** | −193 |
| entered premarket (< 09:30) | 9 | −2,424 | **−269** |
| entered in RTH | 12 | −1,624 | −135 |
| B stop-buy / A ORB | 11 | −1,338 | −122 |
| C reversal pattern | 10 | −2,710 | −271 |

- **Three exits carry 87% of the loss.** RARE (−8% stop), GTLB (trail) and DELL (−8% stop) total −$3,512. The other 18 tickets total −$536.
- On these tickets the stop width barely matters in the simulation: −8% gives −1.14%, 12% gives −1.01%, 20% gives −0.99%, and no stop gives −0.99%.
- **Utilisation:** 21 tickets in 21 sessions against 7 available per day, so about 15% of the budget was used. The binding constraint was eligibility plus vetoes, never capital.
- Large-cap news gappers (BE, RDDT, MRVL, OKTA, DELL, QCOM, GTLB×2, VICR) total −$3,175 over 9 tickets. The "coil" premise was fitted on small caps and doesn't transfer (see the 09-08 QCOM finding).

## 2. Did the vetoes save money? Yes, clearly

There were 41 refused symbol-days (SPREAD > 0.5%, DEPTH < 25% of the ticket, or CHASE). 33 of them have bars.

| counterfactual (ignore the veto) | n | net mean | median | win | gross mean |
|---|---:|---:|---:|---:|---:|
| all refused names | 33 | **−2.93%** (−$293 / $10k) | −4.71% | 33% | −1.43% |
| premarket refusals | 24 | −3.28% | −8.05% | | |
| post-open refusals | 9 | −2.01% | −2.10% | | |
| premarket refusal, deferred to the 09:31 open instead | 24 | −2.54% | −4.51% | | |
| refused and **never** became tradeable that day | 23 | **−4.46%** (14 of 23 hit −8%) | −8.05% | 22% | −2.65% |
| refused, later passed and was traded (taken at the veto minute instead) | 10 | +0.58% | | | |
| … what the later real entry actually made | 10 | −1.16% | | | |
| *control: the 21 traded tickets, same simulation* | 21 | −1.14% | +0.27% | 52% | |

- **The veto policy as run** gave 0 on the 23 never-tradeable names and −1.16% on the 10 later entries, a mean of −0.35% per refused name. Ignoring the veto would have given −2.93%. **That is ~2.6 pp, or about $260 per refused name at $10k, saved.**
- Waiting for the book to tighten cost ~1.7 pp on the 10 names that did tighten, because the price ran up while we waited. The 23 names that never tightened were the real losers. The losses there are a gross fade (−2.65%), not just spread.
- **By rule:** SPREAD −2.38% (n=27), DEPTH −8.05% (n=3, all stopped out), CHASE −2.77% (n=3).
- **Spread size is not monotone** among refusals: 0.5–1% −3.97%, 1–2% −1.44%, > 2% −3.98%. The cap works as a binary gate. Nothing argues for loosening it to 1%.
- **Pool-wide confirmation (no lookahead).** I used R4's 30 random-pick control seeds: 34,901 legs on the cp_panel over 444 sessions. I computed a causal Corwin–Schultz/Abdi–Ranaldo spread proxy from the 30 bars **before** entry, then split the legs into quintiles. Gross $ per $10k, before any cost:

  | proxy quintile | Q1 (tightest) | Q2 | Q3 | Q4 | Q5 (widest) |
  |---|---:|---:|---:|---:|---:|
  | gross | +20 | +10 | −14 | −11 | **−48** |
  | ex-top-5 | +8 | +5 | −18 | −19 | −54 |

  The bar-range proxy (HL10) gives the same shape: +17 → −54. **Wide books are worse on gross and also cost more.** That matches the live counterfactual.

## 3. R4 against a live book: its edge lives in the names the live book refuses

- **R4 overall:** +$82.5 gross per $10k over 965 legs.
- **Its top 10 legs are all thin names.** No-trade share over the trailing 30 minutes is 0.53–0.87. The bar-model round-trip cost is 107–2,070 bps.
- **A > 50 bps proxy-spread veto (the live 0.5% cap):**
  - It refuses 255 legs, worth +$152 gross per $10k.
  - It keeps 710 legs, worth +$58.
  - **Ex-top-5, both groups are negative: kept −$28, refused −$37.**
- **Every proxy quintile is negative ex-top-5** except the tightest CS/AR quintile (+$23).
- **A $-volume floor is not a fix.** Trailing 10-minute $vol ≥ $1M keeps 26% of R4 at +$131, but the same floor on the random legs is −$17 vs −$3. That effect is specific to R4's tail, not general. Don't adopt it.
- **Implication:** a live R4 book with the spread veto cannot reproduce the backtest's +$69/ticket. Its honest expectation is the kept, ex-tail figure (≈ −$28 gross per $10k), with the occasional lottery leg on top.

## 4. The best mover of the day was untradeable. Was that lost money? No

Coverage: 8 sessions with dated scan dumps (08-27 → 09-18).
- **Day's #1 common-stock mover:** halal-refused 8 of 8 days (4 `halal_fail`, 4 `inherited_fail`).
- **Top 4 per day:** 13 halal_fail, 11 inherited_fail, 6 "candidate, not top-ranked / no trigger", 1 SPAC, 1 cannot-verify. **None was lost to a book veto.**
- **Timing:** these names (DUKR +65–130%, AEMD +452%, RETO +409%, IMCC +384%) mostly printed their % peak at first sight, at 06:2x–07:0x premarket.
- **Outcome where bars exist** (Aug, n=8): first-seen → 14:59 averaged **−12.7%** (median −10.5%). Only FLYE was positive (+9.4%). These are fades.
- **Pool check** on the random legs, gross per $10k by gain at entry:

  | gain at entry | +10–20% | +20–35% | +35–50% | +50–100% | > +100% |
  |---|---:|---:|---:|---:|---:|
  | n | 17,145 | 3,542 | 756 | 629 | 506 |
  | gross | +2 | −13 | −64 | −90 | +157 |
  | ex-top-5 | | | | | +97 |

  The fade is real for +35–100%. Above +100% is a lottery tail. With halal now ignored, the new books will see these names. Don't chase them on the theory that "we were missing the big ones".

## 5. Ops: time lost and how

**RTH (09:30–15:00): 886 of 6,930 minutes lost (12.8%)**, almost all in three sessions:
- 08-11: internet outage 10:35–15:00 with FRMI open, settled after the fact.
- 08-17: login expiry 10:09–15:00.
- 08-24: the headless agent ended its turn and the whole day was lost.

**Premarket (07:00–09:30): about 460 of 3,150 minutes lost (~15%):**
- Scheduler queues and late starts: 08-10, 08-11, 08-12, 08-14.
- Login expiry: 08-19, 09-16 (59 minutes).
- Permission block: 08-26.
- A tool call stalled at its 2-minute timeout: 08-27.

**Legal signals missed through process:** a Trigger C was stale by the time it was read four times (08-14 RDDT; 09-02 07:47; 09-08 PHVS ×2). In every case there was a pacing wait chained inside the same tool call as the signal read, or the polling started late.

**Silent data corruption:** on 09-01, undated `scan_dump_HHMM` filenames injected four of the previous day's names into the latched crossed set.

**After 09-02:** with a separate `paper_watch` process plus the SESSION_ALIVE heartbeat and watchdog, no RTH minute was lost (only the 59-minute premarket gap on 09-16).

## 6. Where execution slippage came from

Measured in `live-cost-truth.md`; not re-done here.
- **Half-spread at the order:** RTH entries 11–15 bps. Premarket 18–64 bps.
- **Ladder exits (14:50–14:58):** 2–4 bps.
- **Stop-buy bookings:** the "fill at trigger" convention books 0 bps against the backtest but 15.7 bps against the mid. On DELL (09-02) the arm went in mid-bar with the ask already above the trigger, so that convention is optimistic.
- **Four of 21 tickets were cut by depth:** MRVI 38%, ASST 54%, NEOV $4.8k, ANGX $13k. At $10k tickets this binds less.
- **L2 vs NBBO:** the L2 book was one tick wider than the NBBO twice (Day 17, 08-28 TII).

## TAKEAWAYS (for the R4 / R15 / RL2 three-book paper session)

1. **Keep the live spread veto, binary, on every gapper (R4) entry, and pre-register R4's ex-tail expectation.**
   - **Rule:** at the decision second, refuse if the inside spread is > 0.5% of mid, or if displayed depth to limit is < 25% of the ticket. Re-check every cycle and enter only when the book passes. Never "defer to the 09:31 open" or loosen the cap.
   - **Live evidence:** it saved about $260 per refused name at $10k (n=33). The pool shows the same direction: widest-quintile legs gross −$48 per $10k vs +$20 for the tightest (n=34,901).
   - **Value:** about **+$260/refused name ≈ +$2–5k/month** compared with running without the veto. That is loss avoided, not profit.
   - **Expectation:** judge live R4 against its kept, ex-top-5 backtest (≈ −$28 per $10k gross, ≈ −$58 net at 15 bps/side), not against +$69.
   - **Test:**
     - Offline: add the CS/AR > 50 bps proxy veto inside the R4 rotation sim, and also inside its 30 random seeds. Then compare the percentile and ex-top-5 numbers.
     - Live: re-run `plan/lm15_cf.py` after each session once bars are backfilled. The pass condition is that the refused names' ignore-veto mean stays below the traded mean.
2. **Run RTH only: start the agent at 09:15 ET and arm nothing premarket.**
   - **Why:**
     - Premarket entries lost −$269 per ticket (n=9), against −$135 in RTH.
     - The premarket veto rate was 90–100%.
     - Premarket refusals lost −3.3% if taken, and −2.5% even if deferred to the open.
     - The scheduler and login failures clustered 06:20–09:18.
   - **Cost to the books:** R4 enters ≥ 09:36 and R15 at 09:35, so nothing in them needs the premarket. This removes about 175 of 520 minutes per day (~1/3) of agent runtime and the failure exposure that goes with it.
   - **Value:** compared with C37 practice (~0.43 premarket tickets per day at −$179 per $10k ticket), about **+$77/day, ≈ +$1.6k/month at $10k**. Again, loss avoided.
   - **Test:** log `ops_minutes_lost_RTH` and `stale_signals` per session. The target is 0 and 0 over the first 10 sessions.
3. **Exits and staleness must not depend on the agent being alive or idle.**
   - **Rule:** from the fill second, every open position's exit rule and its 14:57 flatten are owned by the separate `paper_watch` process. The agent only opens positions. No tool call may contain both a signal read and a wait: a TAKEABLE tag goes straight to the quote and book check in the same minute.
   - **Evidence:** two sessions lost most of RTH with the agent dead (one with a position open), and four legal signals went stale through chained waits. Since 09-02, with the watcher, there has been 0 RTH loss.
   - **Value:** it protects the tail rather than adding $/trade. At this sample's rate (2 dead-agent RTH days and 4 missed signals in 21 sessions), roughly 1 missed or unmanaged trade per 5 sessions is avoided.
   - **Test:** compare the watcher's exit log with the ledger each day (exit parity already exists in the 09-08 ledger). Count missed signals.

## DISCARD

- Loosening the spread cap to 1–2%, or "wait for the open" for premarket refusals. Refusals lose at every spread level, and deferring to the open still lost −2.5%.
- Treating the halal-refused top movers as lost profit and chasing them now that halal is ignored. First-seen → close was −12.7% (n=8). Pool gross at +35–100% gain is −$64 to −$90 per $10k.
- A $-volume floor to rescue R4. It is R4-tail-specific; on the random legs it goes the other way.
- Tuning the −8% stop width from the ledger. On the live tickets 8% / 12% / 20% / none are within 0.15 pp. Champion-replay already prices the stop on 965 legs: removing it gains +$22.60/ticket.
- The C37 coil+pressure rank and the large-cap news-gapper entries (9 tickets, −$3,175). Both are already retired.
- Re-measuring live slippage. `live-cost-truth.md` already covers it: 8 bps/side RTH liquid, 12–18 for gappers.

Caveats:
- Small n. 33 counterfactual names over 13 sessions. The movers sample is 8 days, and only 8 of those names have bars.
- After 09-01 the refused names have no bars, so the September refusals (PHVS, INBX, AMCI, BSEM, RNXT, TRAX) are not scored.
- The bar-model cost (TapeCost, Y=1) over-charges impact (see PESSIMISM-AUDIT), so the "net@measured" figures from the scripts are pessimistic. The plausible net quoted here is gross − 30 bps round trip.
