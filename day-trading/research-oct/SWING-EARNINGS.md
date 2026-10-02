# SWING-EARNINGS — post-earnings drift beyond one hour (2026-10-01)

Research only. Nothing here touches the live R4 / R15 / RL paper books.

## Verdict

**No. Don't paper-trade any multi-day earnings hold from this study.**

Holding liquid earnings names for 1–10 days earns about what the market earns over the same days. It does not earn more.

- **Rules vs SPY.** Every rule that is positive in both years is at or below SPY held over the same window in at least one year.
- **Rules vs the random-day control.** Every such rule is also at or below a random-day control (same names, same hold, a non-earnings day) in at least one year.
- **Portfolio vs plain SPY.** The best portfolio version earns about **$1,150/month** on $100k over Y1+Y2 combined. Buying and holding SPY earned **$1,330/month** over the same period.
- **Last two months (OOS).** The best rule is negative in the out-of-sample split, Aug–Sep 2026. But the sample there is tiny: 10 trades in the portfolio.

What does hold up:
- **R15's 60-minute exit is about right.** Run on R15's own universe with EDGAR earnings timestamps, the 60-minute hold replicates: +73 / +53 bps net per trade at 6 bps, Y1 / Y2. Holding to the close of day 1, or to day 5 or day 10, is unstable from year to year.
- **One extension looked better and failed the checks.** Holding to the next day's close (C1) showed +99 / +77 bps. But its t-statistic is below 1, it is negative in both years once the top 5 trades are removed, and its 10 OOS trades lose −395 bps.

## The best honest rule, written out exactly

This is the rule chosen by the stated protocol: rank on Y1 only, require n ≥ 100 in each year, and prefer the variant that holds up best in both years. It is written out so it can be checked, **not** recommended.

> **GD-GREEN-10.** Universe on day D: an operating common stock or ADR in the **causal top-600**. That means the highest prior-60-session median dollar volume among names that pass the point-in-time liquidity screen (median $vol ≥ $5M, median close ≥ $5, ≥ 40 of the prior 60 sessions present).
>
> **Event.** An SEC 8-K carrying item 2.02 was accepted **before 09:30 ET on D** (a morning report), or after 16:00 on the previous session or on a non-trading day (an evening report). Releases between 09:30 and 16:00 are skipped.
>
> **Entry conditions, both required.**
> - **Gap down:** D's 09:30 open is below the previous close.
> - **Green at 09:35:** the 09:35 one-minute bar closes above D's open.
>
> **Entry.** Buy at the **open of the 09:36 bar**: the first print between 09:36 and 09:40, otherwise the trade is skipped.
>
> **Exit.** Sell at the **close of session D+10**. There is no stop.
>
> **Ties.** When there are more candidates than slots, they are taken in seeded-random order.
>
> **Sizing.** Fixed $10k tickets, at most 10 open at once, settled cash only (T+1).

### Results on a $100k cash account

All numbers are fixed tickets in a portfolio simulation, averaged over 10 tie-break seeds. "Base cost" is per side, and the square-root impact term is added on top. "Ex-top-5" is the split's total P&L after removing its five best trades.

| size × max open | base cost | split | trades | trades/mo | $/trade | $/month | win | max DD | ex-top-5 total |
|---|---|---|---|---|---|---|---|---|---|
| $10k × 10 | 6 bps | Y1 | 118 | 13.1 | +$17 | +$220 | 51% | −$14,612 | −$9,385 |
| $10k × 10 | 6 bps | Y2 | 171 | 14.2 | +$130 | +$1,855 | 52% | −$8,446 | +$8,899 |
| $10k × 10 | 6 bps | OOS | 10 | 5.0 | −$359 | −$1,793 | 55% | −$4,395 | −$6,390 |
| $10k × 10 | 12 bps | Y1 | 117 | 13.0 | +$2 | +$27 | 50% | −$15,200 | −$11,091 |
| $10k × 10 | 12 bps | Y2 | 171 | 14.2 | +$119 | +$1,694 | 52% | −$8,724 | +$7,052 |
| $10k × 10 | 12 bps | OOS | 10 | 5.0 | −$370 | −$1,851 | 55% | −$4,485 | −$6,442 |
| $25k × 4 | 6 bps | Y1 | 54 | 6.0 | +$87 | +$550 | 49% | −$21,687 | −$17,970 |
| $25k × 4 | 6 bps | Y2 | 78 | 6.5 | +$358 | +$2,318 | 55% | −$16,043 | +$4,498 |
| $25k × 4 | 6 bps | OOS | 4 | 2.0 | −$888 | −$1,775 | 65% | −$5,311 | n/a |
| $25k × 4 | 12 bps | Y1 / Y2 / OOS | 54 / 78 / 4 | | +$36 / +$341 / −$916 | +$237 / +$2,199 / −$1,833 | | −$23,066 / −$16,316 / −$5,386 | |
| $50k × 2 | 6 bps | Y1 | 26 | 2.9 | +$88 | +$498 | 49% | −$24,563 | −$21,589 |
| $50k × 2 | 6 bps | Y2 | 38 | 3.1 | +$793 | +$2,495 | 56% | −$21,388 | −$9,086 |
| $50k × 2 | 6 bps | OOS | 2 | 1.0 | −$1,614 | −$1,614 | 65% | −$6,773 | n/a |
| $50k × 2 | 12 bps | Y1 / Y2 / OOS | 26 / 38 / 2 | | +$44 / +$732 / −$1,672 | +$409 / +$2,303 / −$1,672 | | −$24,865 / −$21,752 / −$6,851 | |
| $10k × 5 | 6 bps | Y1 / Y2 / OOS | 70 / 97 / 5 | 7.8 / 8.1 / 2.5 | +$41 / +$118 / −$328 | +$322 / +$953 / −$820 | | −$10,006 / −$7,500 / −$2,483 | |
| **SPY buy & hold, $100k** | — | Y1 / Y2 / OOS | — | — | — | **+$971 / +$1,606 / +$880** | — | −$20,033 / −$10,142 / −$3,180 | — |

**Halal-PASS only.** Note that `data/halal_list.json` is a **present-day** list, so this line has look-ahead in its name selection. At $10k × 10 and 6 bps: Y1 +$768/month (64 trades), Y2 +$2,275 (96 trades), OOS +$2,623 (8 trades). Y1 is still below SPY buy & hold, and the subsample is small.

### Why it is not an edge (event level, every qualifying event, $10k, 6 bps)

| split | n | rule net | SPY over the same window | random-day control (30 seeds) | rule percentile vs control | ex-top-5 mean |
|---|---|---|---|---|---|---|
| Y1 | 428 | +153.6 bp | **+161.7 bp** | +15.2 bp | 100 | +101.6 bp |
| Y2 | 529 | +92.4 bp | +71.5 bp | **+100.6 bp** | **43** | +55.5 bp |
| OOS | 32 | +62.5 bp | −47.5 bp | −168.8 bp | 97 | **−351.7 bp** |

- **Y1:** the rule is below SPY over the same days.
- **Y2:** the rule is below a random non-earnings day for the same names.
- **OOS:** depends on its top few trades.

This rule was also picked out of about 1,140 rules tried (see part (b)), so its t = 3.35 / 2.33 is a selection artifact until shown otherwise.

## (a) R15's entry, held longer

Entry: green at 09:35, buy at the 09:36 open. Mean net bps per trade, at base costs 0 / 6 / 12 bps per side.

**R15's own universe.** This is the rl2 wide halal set, using point-in-time membership on day 1, with EDGAR timestamps (179 events; the set ends 2026-08-06). All events are traded here, not R15's one-a-day pick.

| exit | Y1 (n≈60) @0 / 6 / 12 | Y2 (n≈109) @0 / 6 / 12 | OOS (n≈10) @6 |
|---|---|---|---|
| **H60** (R15) | +86 / **+73** / +61 | +65 / **+53** / +41 | +49 |
| close of day 1 | +59 / +47 / +35 | +6 / −6 / −18 | −249 |
| next close (C1) | +111 / +99 / +87 | +89 / +77 / +65 | −395 |
| close day 3 | −5 / −17 / −29 | +128 / +115 / +103 | −51 |
| close day 5 | −81 / −93 / −105 | +52 / +40 / +28 | +68 |
| close day 10 | −78 / −90 / −102 | +152 / +140 / +128 | −690 |

C1 under controls: random-day control percentile 97 (Y1) and 93 (Y2). But t is below 1, ex-top-5 is −57 / −47 bps, and OOS is −395 bps on 10 trades.

**The causal top-600 set** (1,997 green events):

| exit | Y1 @6 | Y2 @6 | OOS @6 |
|---|---|---|---|
| H60 | −6 | −25 | +2 |
| close day 1 | +2 | −25 | −25 |
| close day 5 | +82 | +15 | +204 |
| close day 10 | +127 | +34 | +83 |

Here R15's edge does not appear at all. The longer holds track SPY drift.

**Reading (a):** the 60-minute exit is R15's sweet spot, and it is specific to R15's mid-cap halal set. Holding longer adds market beta and variance, not drift.

## (b) Wider universe and entry conditions

**Universe.** Every liquid earnings reporter, defined point in time from grouped-daily data:
- Polygon type CS or ADRC, SIC not 6726.
- Prior-60-session median dollar volume ≥ $5M and median close ≥ $5.
- About 2,570 names a day.
- **16,144 events** across 2,458 symbols, from 2024-10-30 to 2026-09-30.

**Event clock.** The SEC acceptance time of an 8-K with item 2.02. The acceptance hours cluster at 06–08 ET and 16 ET, which confirms the UTC-to-ET conversion. Intraday releases (553) and follow-up 2.02 filings within 10 days (458) are dropped. Events whose window spans a split (105) are dropped using the split calendar only.

**Entries.**
- **O:** the 09:30 open. Only pre-open conditions are allowed.
- **C:** day-1 close (MOC). The day-1 bar is observable, per the mandate.
- **N:** day-2 open. Fully causal.
- **O1 / M5 / M30:** 09:31 / 09:36 / 10:01. Minute-tape entries, on the causal top-600 and R15 sets only (see the audit).

**Conditions tested:**
- gap sign and size
- green or red at 09:35 / 10:00, or over day 1
- day-1 move beyond ±3% and ±7%
- early volume vs ADV20 (day-1 volume vs ADV20 for close/next-open entries)
- 20-day trend
- SPY above its 20-day moving average
- EPS surprise (RH or yfinance, on a 1,987-event subset)

**Exits:** day-1 close, and the open or close of D+1, D+2, D+3, D+5 and D+10.

**Grid size.** 1,140 rules have n ≥ 40 in both years, and 247 of them are positive in both at 6 bps. That is what beta plus noise produces in a period when SPY rose 8.7% and 19.3%.

### Notable rows

Net bps, per split, at 6 bps / 12 bps base cost.

| rule | Y1 | Y2 | OOS |
|---|---|---|---|
| classic PEAD: C, day-1 > +3%, close D+10 | +76 / +64 | **−33 / −45** | −12 / −24 |
| PEAD next-open: N, day-1 > +3%, close D+10 | +59 / +47 | −43 / −54 | −22 / −34 |
| big winners: C, day-1 > +7%, close D+5 | +42 / +30 | −46 / −58 | +38 / +26 |
| EPS beat: O, surprise > 0, close D+10 | −32 / −44 | +60 / +48 | −134 / −146 |
| all events, C, close D+5 | +44 / +32 | +8 / −5 | +44 / +32 |
| earnings-day open→close (O → day-1 close) | **−36** | **−36** | +10 |
| C, 20-day trend < 0, close D+5 | +33 / +21 | +23 / +11 | +67 / +55 |
| C, day-1 down, close D+5 | +28 / +16 | +22 / +10 | +30 / +18 |
| M5, green & gap < 0, close D+10 (GD-GREEN-10) | +154 / +141 | +92 / +80 | +63 / +50 |

The two daily-bar survivors fail their controls:

- **C, 20-day trend < 0, close D+5.** Event-level SPY over the same window is +65 / +62 bps (Y1 / Y2), against the rule's +33 / +23. The random-day control percentile in Y2 is 70. As a $10k × 10 portfolio it makes +$93 / +$1,351 / +$1,110 per month at 6 bps, and −$426 / +$958 / +$740 at 12 bps. Max drawdown is about −$25.7k.
- **C, day-1 down, close D+5.** The random-day control percentile in Y2 is **0**: the control earns +42.5 bps against the rule's +22.3.

The surprise splits flip sign from year to year, and the EPS-surprise data covers only a 1,987-event subset.

## (c) Sizing

The impact term charged is Y = 0.5 · σ20 · √(notional / ADV20), on top of the base cost.

| | ADV20 median | impact per side at $10k | at $25k | at $50k |
|---|---|---|---|---|
| GD-GREEN-10 (top-600) | $382M | 0.5 bp | 0.7 bp | 1.0 bp |
| broad daily rules | $52M | 1.6 bp | 2.6 bp | 3.7 bp |

Size does not move the cost. It moves concentration: fewer, bigger bets, so a higher monthly standard deviation and a deeper drawdown (−$22k to −$25k at $25k/$50k, against −$9k to −$15k at $10k). It never changes the sign of an edge.

## (d) Capital and settlement

The simulation is a cash account with $100k:
- Sale proceeds settle the next session (T+1). Only settled cash buys, so there are no good-faith violations.
- At most N positions are open at once.
- Positions are marked to market at each close.

During earnings season the candidate flow (about 47 a month for GD-GREEN-10, thousands for the broad daily rules) far exceeds 10 slots × about 2 turnovers a month. So the portfolio is a **random subsample** of the event list, and its $/month has a seed standard deviation of $400–$900. That alone is the size of most of the "edges".

## Adversarial self-audit (code path, done before reporting)

1. **LEAK FOUND AND FIXED: minute-tape coverage was outcome-selected.**
   - The first pass took day-1 minute bars from whatever existing cache had them: m1o, m1w and the gapper cache m1.
   - Events with a tape returned **+71 bps open→close; events without one returned −110 bps**. The gapper-era caches were filled for days that moved.
   - Using "has a tape" as a filter produced fake 09:31-entry edges, with t = 6–8 on every hold.
   - Fix: minute-tape rules run only on sets whose membership is causal **and** whose coverage is 100%:
     - the top-600 set, by prior-60 median dollar volume (Y1 1,677 / 1,677 events, Y2 2,186 / 2,186);
     - R15's per-date wide universe (129 / 129, 243 / 243).
   - The OOS minute rows are cut at 2026-08-06, the end of the outcome-blind m1o cache. Fetching the rest was blocked by the shared Polygon key's per-minute 429s, because other agents were saturating it.
   - **Lesson for every line:** never let "data exists" act as a universe filter.
2. **Price units.** The minute caches and gd were split-adjusted on different dates. APH, MNST and IESC showed exact 2× gaps. The fix rescales the tape when the day-1 gd close and the last minute close differ by more than 2%.
   - 20 tapes were rescaled. 15 were at exact split ratios.
   - The 5 odd ratios (AIRE, PMI, HLIT, KURA, MH) are outside the top-600 and R15 sets, so no reported minute rule touches them.
3. **Earnings clock.** It comes from EDGAR acceptance times, not report dates. Releases between 09:30 and 16:00 are excluded. An 8-K filed later than its press release only delays the clock, which is conservative.
4. **Universe.** Membership uses prior sessions only. Two parts are present-day and lean toward survivors:
   - Polygon type metadata, via `ou_lib.is_operating`;
   - the EDGAR ticker→CIK map (247 liquid symbols had no CIK and are excluded).
5. **Ties.** Seeded random, the same seeds across costs. A causal ranking exists as an option in `portfolio()`, but no reported table uses it.
6. **Close entries** read the day-1 close and fill at that same close. The mandate allows this. In live trading an MOC order is decided about 10 minutes earlier.
7. **Exits.** A name that stops printing is flattened at its last close; there is no survivorship drop. Holds that run past 2026-09-30 are censored, which is why OOS counts fall for D+10.

## Files

- **Code:**
  - `plan/se_panel.py`: daily panel and PIT universe.
  - `plan/se_edgar.py`: 8-K item 2.02 acceptance times.
  - `plan/se_splits.py`: split calendar.
  - `plan/se_events.py`: event table.
  - `plan/se_mcache.py`: tapes taken from existing caches.
  - `plan/se_minute.py`: Polygon fetcher.
  - `plan/se_top600.py`: causal top-600 set.
  - `plan/se_study.py`: `grid`, `r15`, and `rule ENTRY COND EXIT`, with env `SE_UNI=t600|r15`.
- **Caches** (about 61 MB) in `data/research_oct/se_*`:
  - `se_panel.npz`, `se_edgar_202.json`, `se_splits.json`, `se_events.json`, `se_m1/`, `se_top600.json`;
  - the grid as `se_grid.json` (0 / 6 / 12 bps);
  - text outputs `se_grid_v2.txt`, `se_r15ext.txt`, and `se_rule_{A,B,GD,r15C1}.txt`.
