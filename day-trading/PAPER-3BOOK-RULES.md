# PAPER-3BOOK: the rules of the three live paper books (2026-10-01)

**Paper only, open-ended. Real orders never, unless the user explicitly authorizes them in conversation.**

User decision, 2026-10-01: paper-trade three strategies side by side, with no end date. Run them every market day until the user says stop.

- **R4**: CHAMPION-REPLAY "coil + no stop".
- **R15**: CATALYST-MINER "fresh earnings AND green @09:35, h60".
- **RL**: RL-SCOUT v2 approach-4, seed 0.

C37 is retired from live paper. Its mandate is kept as `plan/paper_day_prompt.C37.txt`.

## The frame, common to all three books

- **Books.** There are three separate books. Each has its own ledger section, its own $100,000 notional account and **$10,000 per trade**.
- **Positions.** Each book holds one position at a time. The books run concurrently, so up to three positions can be open at once. Everything is sold the same day.
- **Session.** RTH only (LEGACY-15). The agent starts at about 09:15 ET (Task Scheduler at 09:10). Nothing is armed premarket. Each book first decides at 09:30 (RL) or 09:35 (R4, R15).
- **Halal.** Halal does **not** gate any book's selection (user: "ignore halal for now"; the research ran without it). Every trade is still **tagged** with the fresh `python plan/live_halal.py SYM --json` verdict. Every EOD reports P&L twice: all trades, and halal-PASS trades only.
  - The RL / R15 *universe* (the rl2 wide universe) was defined with a point-in-time halal screen as one of its membership conditions. That is part of the universe the rules were found on, so it is kept. It is not a live gate.
- **Fills, two of each.**
  - The **official paper fill** is the live quote at the decision minute: the ask for a buy, the bid for a sell. This is what the ledger P&L uses.
  - The **model fill** is the backtest's own convention. It is usually the open of the next printed 1-minute bar.
  - Both are recorded. The quote mid is also recorded at both ends, so every trade carries its **realized cost vs mid**. We need this measurement.
- **Exits belong to the watcher.** From the second of the fill, the separate `plan/paper_watch.py --book NAME --exit-mode NAME` process owns every exit (LEGACY-15).
  - It calls the same function the decision code and the parity test use (`plan/p3_{book}.watch_exit`).
  - Each book has one **safety rung** that fires only if the model never exited: R4 15:05, R15 15:00, RL 15:59. On a 13:00 half day, all three fire at 12:57.
- **No staleness.** No tool call may both read a signal and wait. A signal that first becomes known more than 5 minutes after its decision minute is logged as MISSED, never entered.
- **Dated files only.** Every saved scan, quote or bars file carries the date (and time) in its name. On 2026-09-01, undated files injected the previous day's names.
- **Scoring.** Each book is scored against **its own backtest expectation at realistic cost**, per trade and per day, both raw and **ex-top-5**. It is never scored against C37. The table is below and in `data/paper/p3_expectations.json`.

## R4: CHAMPION-REPLAY "coil + no stop" (gapper scanner)

Source: champion-replay-audit.md Part 4, row R4. Engine: `plan/cp_sim.py`, `default_cfg(rank="coil", stop_pct=None)`. Live code: `plan/p3_r4.py`, which imports cp_sim's ranking, gates, pressure, bearish-pattern and gap-through fill helpers.

**Checklist (minute k = bar [k, k+1); a grid minute t is decided at wall t+1, once bar t is complete):**

1. **Universe at t.** A name qualifies when any regular-session close since 09:30 has printed at or above 1.10 x the previous close. The rule is sticky (Robinhood's +10% scanner rule, "LAST"). The last price must also be at least $2.
   - Live source: the saved scan **"P3 R4 gapper coil"** (`0cc1cab3-408b-40bf-8a76-c6129ed0fed4`). Its filter is Last > $2 AND RTH high >= 1.10 x prev close. Columns are Coil, PriceReg, PrevClose, HighAll. It is sorted by Coil, descending, and returns at most 200 rows.
   - The agent runs it at each grid minute and ingests it with `p3_r4.py --scan`. A name joins the sticky set when a snapshot shows its RTH price at or above 1.10 x prev close.
2. **Decision grid.** Every 5 minutes, 09:35, 09:40 ... up to and excluding 14:30. After an exit, the next decision is the first grid minute at or after max(t+5, exit+1).
3. **Rank.** coil = last / session high, where the high includes premarket. Highest coil first.
   - Live: the scan's Coil column (RTH price / all-session high), observed at wall t+1.
4. **Gate.** gap7 = (last print at or before 07:00) / prev close - 1. The top-ranked name may have gap7 up to 35%; every other name is held to 20%. Try the first 8 in rank order; the first name that passes is taken.
   - Live: the decision prints `need_bars` for the top 8. The agent fetches their minute bars from 04:00 (`bounds=extended`) so gap7, the fill bar and the size cap are exact.
5. **Book veto (LEGACY-15, live only).** Before the entry, check the quote and the price book:
   - Refuse if the inside spread is more than 0.5% of mid.
   - Refuse if the displayed ask depth up to ask x 1.005 is under 25% of the intended shares.
   - A refused leg becomes a **SHADOW leg**: its entry is the ask at the veto minute and its exits are the model's. The agent re-checks every minute while the model leg is open and enters on the first PASS.
   - Never loosen the cap and never "defer to the open".
6. **Entry.**
   - Model: the OPEN of the next printed bar after t, at a price of at least $2.
   - Size: min($10,000 / px, 20% of the share volume of the 5 bars before the fill bar).
   - Official: the ask at wall t+1, with shares = floor($10,000 / ask) capped by the model size cap.
7. **Exits (watcher, `EXIT_MODE r4`).** There is **no hard stop**.
   - **Trail** from the peak bar HIGH: 20% normally. It tightens to 10% when 10-bar pressure is at or below -0.30, and widens to 40% when pressure is at or above +0.30. The model fill is min(level, open), clamped to the bar.
   - **Bearish engulfing** bar while close > entry. The model fill is the **next printed bar's OPEN** (LEGACY-14; see the deviations section).
   - **Flatten**: the last printed bar at or before 15:00, at its close.
8. **Structure.** At most 7 tickets a day, at most $100k a day, rotation on, one position at a time.

## R15: CATALYST-MINER fresh earnings & green @09:35, h60

Source: catalyst-audit.md Part 5. The backtest rows are `data/massive/cat/rule_detail.json` (112 tickets). Live code: `plan/p3_r15.py`.

1. **Universe.** The rl2 causal wide universe (`data/paper/universe_wide.json`), in alphabetical order.
2. **Fresh earnings.** The name's most recent earnings event is at most **18 h** before 09:35.
   - Event clock: `am` is 07:30 ET of the report date; `pm` or unknown is 16:30 ET.
   - So "fresh" means an am report today, or a pm report on the previous **calendar** day. A Friday-pm report is not fresh on Monday.
   - Live source: `get_earnings_calendar(start_date=today, days=-2)`, ingested with `--ingest-calendar`. Rows with no EPS actual are ignored, as the backtest did.
3. **Candidate.** The 09:35 bar printed.
4. **Green.** log(close at 09:35 / forward-filled close at 09:30) > 0.
5. **Pick.** One name: the most recent report first, ties in universe (alphabetical) order. The top name is taken even if it cannot fill; the ticket is spent.
6. **Entry.** Model: the 09:36 bar's OPEN. Size: min($10,000, 20% x volume of the 09:31–09:35 bars x fill). Below $500 there is no trade. Official: the ask at 09:36; after 09:41 the pick is MISSED.
7. **Exit (watcher, `EXIT_MODE r15`).** Model: the OPEN of the first printed bar at or after **10:36**. Official: the bid at 10:36.

## RL: RL-SCOUT v2 approach-4 seed-0 rule (wide universe)

Source: rl2-audit.md §3.3. Rule file: `plan/rl2/results/rules_holdout_s0.json`. Engine: `plan/rl2/sim.py` + `rules.py`. Live code: `plan/p3_rl.py`.

1. **Universe.** 95 names in `data/paper/universe_wide.json`, built with `plan/p3_universe.py --build --asof 2026-10-02` from the rl2 membership rule:
   - prior 60 sessions with median $ volume of at least $2M and median close of at least $3;
   - industry and sector clean;
   - halal-PASS at that date. This is part of the universe definition, not a live gate.

   It is refreshed monthly with `plan/p3_gd_fetch.py` then `p3_universe.py`. The live source is the saved scan **"P3 RL wide universe"** (`2f8e0fb0-197d-406d-a954-db0e4edff2b2`, symbol ANY_OF the 95). It returns 95/95 rows with columns Last, last-trade time, VWAP (all / regular), Open and change vs previous close. The scan's ticker list can only be re-saved from an interactive session (`create_scan` is not on the headless tool list); `p3_universe.py` flags `scan_stale`.
2. **Decision grid.** Every 5 minutes, 09:30 … 15:55. Step m is decided at wall m+1, once bar m is complete.
3. **Entry test**, applied to names whose bar m printed, in alphabetical order. The first name passing all three is taken.
   - `dist_vwap_day = log(mark / VWAP) < -0.00006`, with VWAP = Σ(close·vol) / Σvol from 04:00.
   - `xs_breadth < -0.02379`: the mean, over universe names that printed at m, of log(mark / 09:30-bar close).
   - `log_price < 2.75367`, i.e. mark < ~$15.70.
4. **Entry fill and size.**
   - Model: the OPEN of bar m+1. If that bar does not print, the attempt is spent.
   - Size: floor(min($10,000 / px, 20% of the trailing 5-minute share volume)), with at least $500 notional.
   - Official: the ask at wall m+1.
5. **Book limits (live).** One position at a time and at most 7 entries a day. The published backtest ran up to 7 concurrent $15k tickets, at most 2 new per step.
6. **Exits (watcher, `EXIT_MODE rl`).** Evaluated at each later 5-minute step on the mark (last close at or before the step):
   - +5% take;
   - mark at or below 0.97 x the peak of the marks (trail);
   - 240 minutes (tmax).

   The model fill is the open of the next bar; if that bar does not print, the exit carries to the next step. Anything still open is flattened at the **15:59 bar close (RTH)**; the published backtest held into extended hours. The official exit is the bid at the decision minute.

## Where live execution deviates from the backtest, and why

| book | deviation | reason | parity cost |
|---|---|---|---|
| R4 | **Bearish-engulfing exit fills at the NEXT printed bar's open**; the published backtest used the same bar's close | That close is gone by the time the pattern is known (LEGACY-14). LEGACY-1 shows the next open is slightly *better* per ticket (+$4–6) on the same entries; the rotation path changes, so replay totals move about ±$19/ticket | Mode C below compares against cp_sim with only this fill moved: **952/952 legs identical** |
| R4 | Universe and coil come from the saved scan, observed at wall t+1, not from bar closes. The sticky +10% LAST rule is observed only at snapshots. Coil's high is Robinhood's all-session high (may include the 20:00–04:00 overnight session) | Robinhood MCP is agent-only, and minute bars for ~150 names every 5 minutes are not affordable | Mode B (emulated 5-minute snapshots, top-200 by coil): **53/54, same as exact-bar mode A**. The overnight-high difference is not measurable offline |
| R4 | Spread/depth **veto** (spread > 0.5% or depth < 25%) with SHADOW legs | LEGACY-15: refused names lost about 2.6 pp vs traded ones. The backtest's tail lives in those thin names (255 of 965 legs would be refused) | The SHADOW book (official trades + vetoed legs at the model exit) is the backtest-parity book. Both are reported |
| R4 | cp_sim skips a top-ranked name that does **not print for 60 minutes** after the decision, then takes the next name at its fill minute in the past | A **60-minute look-ahead** in `_try_ticket`/`_next_print`; live cannot know. Live marks such a late leg **MISSED** (it is stale by then) | 1 of 54 legs in the sampled days (2025-08-25 TWIN, behind SPHL); this is the only mode-A/B miss |
| R4 | Tickets are $10,000; the backtest used $15k x 6 + $10k | User's number | Leg timing is identical. Only the size and the 20% volume cap scale |
| R15 | Official entry is the ask at about 09:36; the model is the 09:36 open. After 09:41 the pick is MISSED | Live latency | None in replay (112/112) |
| R15 | Exit is the bid at 10:36. The backtest's fallback (last close of the day if the name never prints again) cannot be known at 10:36 | Causality | Negligible on this universe |
| R15 | "Reported" = the calendar row has an EPS actual; the calendar's am/pm timing is taken as given | The backtest dropped Robinhood rows without an actual | — |
| RL | **One position at a time, $10k** (published: 7 concurrent $15k tickets, at most 2 per step) | User's frame | Rate falls from 1.196 to **0.341 tickets/day**; $/ticket at 6 bps goes from +$24.24 to **+$16.91** |
| RL | **RTH flatten at the 15:59 close; last entry 15:55** (published: entries to 16:00 and exits into extended hours, +50 bps) | At one position and $10k, RTH beats extended hours: +$16.91 vs +$5.32/ticket at 6 bps | Published config RTH vs extended: +$22.44 vs +$24.24 at 6 bps |
| RL | Breadth, the 09:30 reference and marks come from scan snapshots at about m+1:05. VWAP comes from the scan unless 04:00 bars were fetched | Call budget | Snapshot path **86/87 identical** (the miss is a breadth value on the threshold). VWAP start 04:00 vs 07:00 vs 09:30 changes 0 of 87 entries |
| RL | A step whose scan is more than 3 minutes late is a GAP (no entry); an ENTER first seen more than 2 minutes after its step is ENTER-STALE (not traded) | No stale signals (LEGACY-15) | — |
| all | Official fills are quotes (ask in, bid out); model fills are logged alongside | We need a realized-cost measurement | Cost vs mid is reported per trade |
| all | RTH only; the session starts at 09:15 | LEGACY-15: premarket was where most ops failures happened. No book needs the premarket | None: no book decides before 09:30 |

## Parity test results (mandatory before the scheduler is enabled)

Every test drives the **live code**: `p3_r4.run_live`, `p3_r15`, the `p3_rl` engine and each module's `watch_exit`. The historical minute caches (`data/massive/m1`, `m1c`, `m1w`) stand in as the live feed, and at wall minute `now` the arrays are physically truncated after bar now-1.

**R4** (`plan/p3_parity_r4.py` → `data/paper/parity/r4.json`). The reference is `plan/pa_out/cp_r4_legs.json` (965 legs, $66,760.10 at 10 bps).

| test | legs (ref) | matched, identical entry | identical exit | missed | extra | retroactive changes |
|---|---:|---:|---:|---:|---:|---:|
| A: exact-bar universe, minute by minute, 22 days | 54 | 53 (98.1%) | 53 | 1 (60-min look-ahead, see deviations) | 0 | 0 |
| B: emulated scan snapshots every 5 min, 22 days | 54 | 53 (98.1%) | 53 | 1 (same) | 0 | 0 |
| C: LIVE next-open bearish fill vs cp_sim with only that fill moved, 22 days | 50 | 50 (100%) | 50 | 0 | 0 | 0 |
| full-day engine identity, all 444 days, published convention | 965 | 965 | 965 | 0 | 0 | — |
| full-day engine identity, all 444 days, next-open convention | 952 | 952 | 952 | 0 | 0 | — |

A further check, `plan/p3_livepath_r4.py`, ran R4 legs through the real live I/O path: scan files → `--scan` ingest → NEED_DATA → bars → decision. It reproduces 2024-10-22's three legs exactly (MLI bearish next-open 41.15, RITR trail, LOBO flatten).

**R15** (`plan/p3_parity_r15.py` → `data/paper/parity/r15.json`). The full 448-day window was replayed through the live code. The earnings came from the historical corpus, converted to the live calendar's row format.
- **112/112 tickets identical** (sym, entry minute, entry price), with 0 missed and 0 extra.
- Exit prices are identical and the largest P&L difference is $0.00. At $15k / 10 bps it gives +$128.35/ticket, the published figure.

**RL** (`plan/p3_parity_rl.py` → `data/paper/parity/rl.json`). All 255 held-out days were replayed.

| test | result |
|---|---|
| Published config, against `plan/crs_rl2_legs.json` RULE | **305/305 identical round trips** (0 entry or exit time/price differences) |
| Strict physical truncation, minute by minute, 12 busiest days | 84 legs, 0 mismatching days |
| Live scan-snapshot path vs bar path (live config) | 86/87 identical (98.9%); the miss is a breadth value on the threshold |
| `watch_exit` driven minute by minute (live config) | 74/74 exits identical |

**Watcher end-to-end** (`plan/p3_watch_selftest.py`). Historical legs went through `paper_watch.py` EXIT_MODE r4 / r15 / rl, with a quote file each minute and the real `--open` path. **ALL PASS**:
- R4 bearish (next open) and trail;
- R15 h60 x2;
- RL flatten, trail, tmax and take.

In every case the model exit minute and price were exact, the official fill was the quote bid, and the state file was removed. The C37 self-test (`plan/watch_book_selftest.py`) still passes 47/47.

**Verdict: parity passes (≥ 90% identical entries) for all three books.** The irreducible gaps are:
- R4: cp_sim's 60-minute no-print look-ahead (1/54);
- RL: one breadth threshold tie on the scan path (1/87).

## Expectations (score each book against these; never against C37)

`data/paper/p3_expectations.json` is built by `plan/p3_expect.py` from the parity runs. The costs used are the realistic ones:
- R4: 15 bps/side (the gapper middle, LEGACY-14). R4's own-fill estimate of 28.75 bps is shown alongside.
- R15: 9 bps (wide universe at 09:35).
- RL: 6 bps (wide universe, all day).

| book | per trade (realistic cost) | trades / day | per day | backtest per trade ex-top-5 | notes |
|---|---:|---:|---:|---:|---|
| R4 | **+$33.93** (at 28.75 bps: +$14.94) | 2.14 | **+$72.77** (at 28.75: +$32.02) | **−$29.67** | live-code replay, next-open bearish, $10k. Published-close convention: +$53.91/ticket at 10 bps |
| R15 | **+$87.62** | 0.248 | **+$21.71** | +$36.07 | 111 tickets in 448 days |
| RL | **+$16.91** | 0.341 | **+$5.77** | +$18.10 | one position at a time, RTH flatten |

**Read these before the first red week.**

- **R4 is a tail strategy.**
  - LEGACY-14: its five best legs make more than the whole book. The other 960 legs lose about −$701/month at $10k / 15 bps.
  - **Ex-top-5 it is about −$28 to −$30 per $10k ticket** (LEGACY-15: −$28 gross on the legs the spread veto keeps).
  - **R4 lost −$4,392 over the 22 out-of-sample August-2026 sessions.**
  - So a red first week, or a red first month, is *inside* expectation. The test is whether the rare big winner shows up, in the official book or the SHADOW book, and whether the ex-top-5 run rate sits near −$28/ticket rather than far below it.
  - The live spread veto removes most of the thin names where the backtest's tail lives. The SHADOW (backtest-parity) book is what measures whether the edge is real.
- **R15 fires on about one day in four.** Most days are no-trade days. That is a no-loss day, not a miss. 61% of its backtest P&L is five tickets.
- **RL is small.** The user's brief said +$14–16/trade at about 1.2/day; that is the published 7 x $15k concurrent configuration. Under the live frame (one position at a time, $10k, RTH), the replay gives 0.34 trades/day at +$16.91/trade (6 bps), about +$5.77/day.
- **Scoring.** Every EOD reports each book raw and ex-top-5, all trades and halal-PASS only, against these rows (`plan/p3_eod.py`).

## Call budget (Robinhood MCP is agent-only; at most 10 symbols per historicals call)

| when | book | calls |
|---|---|---|
| 09:15, once | R15 | `get_earnings_calendar(start_date=today, days=-2)`: 1 call |
| every 5 min, 09:31–15:56 | RL | `run_scan` "P3 RL wide universe": 78 calls/day, plus a `get_equity_historicals` confirmation (≤ 10 names) on steps where breadth passes (typically 0–20/day) |
| every 5 min, 09:36–14:26 | R4 | `run_scan` "P3 R4 gapper coil": 59 calls/day, plus one `get_equity_historicals` (≤ 10 names, 04:00 → now) when the top 8 include names without bars (typically 1–3 per decision) |
| 09:36 | R15 | 1 `get_equity_historicals` for the fresh names |
| each entry | all | `get_equity_quotes` 1; R4 also `get_equity_price_book` 1 |
| every minute while anything is held | all | 1 `get_equity_historicals` (≤ 10 held/tracked names, last 10 min) + 1 `get_equity_quotes` |

That is about 140 scans, at most about 400 quote/historicals calls on a busy day, and fewer than 200 on a typical one. This is feasible for one headless session.

Full breadth via bars (95 names x 78 steps) would have needed about 750 historicals calls. The scoped scan replaces it at one call per step, at a measured parity cost of 1/87 entries.

## Files

- **Rules / mandate:** `PAPER-3BOOK-RULES.md` (this file) and `plan/paper_3book_prompt.txt`.
- **Launcher / watchdog:** `plan/launch_paper_day.ps1`, which now points at the 3-book prompt and fires at 09:10, and `plan/session_watchdog.ps1`.
- **Live code:**
  - `plan/p3_lib.py`
  - `plan/p3_gd_fetch.py`
  - `plan/p3_expect.py`
  - `plan/p3_r4.py`
  - `plan/p3_r15.py`
  - `plan/p3_rl.py`
  - `plan/p3_universe.py`
  - `plan/p3_eod.py`
- **Watcher:** `plan/paper_watch.py`. Its exit modes r4 / r15 / rl take `--book NAME`. The C37 self-test, `plan/watch_book_selftest.py`, still passes 47/47.
- **Parity:**
  - `plan/p3_parity_r4.py`
  - `plan/p3_parity_r15.py`
  - `plan/p3_parity_rl.py`
  - `plan/p3_watch_selftest.py` (watcher end-to-end on historical legs)
  - Results go to `data/paper/parity/{r4,r15,rl}.json`.
- **Ledger:**
  - `data/paper_days/{date}.3book.json` and `.md`
  - `data/paper_days/{date}.{book}.flatten.json`, `.equity.json` and `.cb.json`
  - `data/paper_days/3book_scoreboard.json`
