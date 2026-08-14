---
description: C37 halal day-trading session — sequential ticket rotation, one position at a time, paper only (7:00–15:00 ET)
---

# C37 — THE ONLY PROTOCOL. Everything below the HISTORY divider is
# background; nothing there overrides this section.

Champion: **C37** sequential ticket rotation.
**Benchmark is an INTERVAL (2026-08-14): $1,362–$1,541 per traded day.**
Upper: $665,667/2yr over 432 days under the old backtest gate. Lower:
**C37S $405,826/2yr over 298 days = $1,362/day under the LIVE halal
gate** (HALAL_STRICT=1) — a lower bound, because strict refuses names
whose filed quarterlies our historical cache lacks while live sees real
filings. Under the honest gate the negative-month record is **3/22, not
0/23**, and ~31% of former traded days have NO eligible pick — an
all-veto day is the modelled norm about one day in three, not a
failure. Judge weeks, not days.
(History: $1,956/day was a hindsight pool cut, fixed 2026-08-13;
$1,541/day was the corrected pool but the WRONG halal gate, fixed
2026-08-14. Paper Days 5–9 were scored against those older figures.)

HARD CONSTRAINTS, never negotiable:
* **NO REAL ORDERS, EVER.** Paper ledger only, one file per day.
* **ONE POSITION AT A TIME.** Never a second ticket while one is open.
* Flat **$15,000** tickets, the 7th/last **$10,000**, **$100,000/day**
  cap, T+1 cash.
* Halal gate before any arming. Missing verdict → live screen. A real
  FAIL is never re-litigated.

**THE HALAL TEST** — TWO independent questions. Both must pass, and
only `verdict == "PASS"` is armable.

***1. Is it FINANCED permissibly?*** (ratios, filed-quarter statements)
loans / market cap and deposits (cash) / market cap each ≤ 10%,
**EXCEPT that ONE side may exceed 10% provided combined ≤ 20%**
(this is what `halal_check` actually implements; corrected 2026-08-13
after HLIT at loan 10.07 / combined 18.44 and ANGX at 9.94 / 16.14
both sat in that zone). Market cap is REQUIRED — a missing mcap once
silently PASSED two names at ~900% loans/mcap, so a missing
denominator is a FAIL, never a pass.

***2. Does it EARN permissibly?*** — **THE 5% RULE.** Haram revenue
must be **under 5% of total revenue**; if it is the main line or ~50%,
the name is haram. Three verdicts:
 * **FAIL** — the company's OWN business is haram, so proportion is not
   in question: brewery / distillery / winery, casino / sportsbook /
   lottery / betting, bank / lending / mortgage / insurance, tobacco,
   defense / aerospace, adult, pork, and **entertainment** — film,
   cinema, streaming (user ruling 2026-08-13).
 * **CANNOT-VERIFY** — exposure is plausible but the SHARE is unknown:
   restaurants, hotels, grocers, food / beverage, or any summary
   mentioning alcohol. `haram_pct` in the code is **interest income
   only** and cannot see product revenue, so the 5% test has NOT been
   run. NOT tradeable until segment revenue is checked by hand. This is
   a refusal to guess, not a compliance failure.
 * **PASS** — neither applies and the ratios clear.

Plain **retail is permissible** and is not a revenue-sensitive term.
On Paper Day 8 a film studio (ANGX) was armed because the screen
answered question 1 and never asked question 2; that trade is recorded
as VOID in `data/paper_days/2026-08-13.md`.

**THE SCREEN HAS THREE BLIND SPOTS (2026-08-13). Do not treat a
`halal=True` as final without a sanity check:**
* `haram_pct` is *interest income / revenue* only — it is
  STRUCTURALLY BLIND to alcohol and pork revenue. A casual-dining
  chain scores ~0%. RRGB was refused on this basis.
* The industry keyword screen missed **gambling** (AIFA runs poker
  venues, labelled `Movies/Entertainment`).
* RH sector labels are unreliable (AZ makes shopping carts, labelled
  `Financial Conglomerates`).
If a `True` rests on an implausible input — e.g. `loan_pct 0.00` on a
company with negative book value — record **CANNOT VERIFY → refusing**,
which is distinct from a compliance FAIL. Low-mcap gappers fail these
ratios constantly (small denominator); that is by design and is the
single largest determinant of what we can trade.

## Pre-open (from 6:40)

1. Trading-day guard. Verify `data/halal_list.json` age < 35 days.
2. Confirm no paper agent is already running for today.
3. Start the persistent Monitor tick clock (UTC-armed, 300s). One-shot
   sleep timers get reaped — see *Paper-session ops hardening*.

## The cycle

**Scan cadence is state-dependent** (see *SCAN ECONOMY*): full 5-minute
rank only while FLAT with tickets left; a light bench refresh every
~20 min while holding; a full fresh re-rank AT the exit; nothing after
the 14:30 entry cutoff.

1. `run_scan` scan_id `5f132877-7730-4a18-9e72-b3f0d2c9df83`. Verified
   2026-08-13: exactly two filters, Last > $2 and %Change > 10%
   (includes premarket). Relative volume is a COLUMN, not a filter —
   **never add a volume gate**, the champion's pool is `novol`.
2. Maintain a **day-long CROSSED SET**. The scan is a snapshot; the
   champion's +10% cross is a **latch**. A name that prints +12% and
   fades to +8% drops off the scan but stays eligible all day.
3. Fetch bars: batched `get_equity_historicals`, **≤10 symbols per
   call**, and **assert the returned symbol set equals the request** —
   it silently truncates. Write `data/rh_bars/{SYM}_{YYYY-MM-DD}.csv`,
   skipping `interpolated=true` bars.
4. **Rank with the command, never by hand:**
   ```bash
   python day-trading/day-trading.py rank SYM:PREVCLOSE ... --as-of HH:MM
   ```
   It returns coil, 30-bar pressure, 7AM gap, calm-gap verdict, halal
   status, exclusions and the armable TOP in one call. Its ordering is
   parity-tested against the backtest's ranker (180 rankings, 0
   mismatches). **If a hand-ranking disagrees, the command is right.**
   Eligibility: price ≥ $2, +10% cross has printed, common stock, ≥50
   sessions, on the halal list. NO volume gate.
   Ranking: COILED first (price / premarket high ≥ 0.95), by 30-bar
   buy pressure (20k-share floor) within group. Calm-gap ≤ 20% gates
   entry, 35% grace for the top name only.
5. Halal-screen **lazily**, only at candidacy (top-3 + coil + calm
   gap). Pass the day's PASS/FAIL sets into every delegated scan —
   FAILs must never re-enter the candidate pool.

## Entry — exactly three triggers, nothing else

**5-minute ORB break**, **premarket-high stop-buy**, or a **reversal
signal from the champion's eight-member set**:
`bullish_engulfing, bullish_spinning_top, hammer, morning_star,
rising_three, tweezer_bottom, macd_cross_up, rsi_cross_up`.
`dragonfly_doji` (−$1,186) and `inverted_hammer` (below transaction
cost) are **excluded** — "any bullish reversal pattern" is wrong.
**There is no retest entry** — the G-series rejected the whole family
(a nonsense-level control beat every real level).

Before arming, every time:
* **FILL-ARMING RULE** — re-quote first. Never arm a stop whose trigger
  is already met (it is a market order and sweeps the top). Use a
  marketable limit capped at trigger +0.5%, or veto and wait.
* **Thin-book veto** — skip if the L2 spread exceeds the 0.5% cap.
  **Log the veto rate every session**: modelling says the optimum
  blocks ~50–65% of would-be entries and our premarket rate is
  ~90–100%, i.e. too aggressive. Calibrate by rate, premarket and
  post-open separately.
* Size ≤ 20% of the trailing 10 completed minutes' volume.
* Use resting orders — see *RESTING-ORDER ARCHITECTURE*. They are what
  make a monitoring outage settleable.

## In position

Watch **1-minute** bars; the position watch always outranks the scan
loop. Trail 20% from peak, tightening to 10% when 10-bar pressure
≤ −0.3 and widening to 40% when ≥ +0.3. Hard stop −8%. Bank 1/3 at
+25% unless pressure ≥ +0.3. Wick guard. Halt protocol: never enter on
a reopen bar.

**Do not add a profit-take.** Banking early was rejected five times,
most recently the B-series under rotation itself: banking at +6% costs
−$366,602 over two years and the ladder is monotonic (4 < 5 < 6 < 8 <
10 < 15 < 25 < none). The give-back is the premium paid for the tail.

## Rotation and exits

When a ticket exits, the next goes to whatever ranks best **now** —
same name only if it still ranks first. Late crossers are first-class:
a 13:40 crosser is a legitimate 13:45 pick. New tickets until **14:30**.
If the pick has not entered by **10:00**, re-rank and switch.
**All exits by 15:00**, flatten ladder from 14:57. Same day, always.

## Reporting

Material events to main as they happen (fills, exits, rotations, stop
tests, veto saves, halts). EOD: trade record, veto ledger both ways,
halal rejects, fill-realism vs the +60s mark, P&L vs **$1,541/day**,
coverage gaps, process notes. Write `data/paper_days/{date}.json` and
`.md`, update notes, commit and push.

If monitoring dies, follow *OUTAGE / DEAD-MONITOR SETTLEMENT*: settle
open positions from already-armed rules, never backfill entries.

## Where the detail lives (all below the divider)

`SCAN ECONOMY` · `API HYGIENE` · `THE rank COMMAND` ·
`LIVE-vs-BACKTEST PARITY AUDIT` · `FILL-ARMING RULE` ·
`OUTAGE / DEAD-MONITOR SETTLEMENT` · `RESTING-ORDER ARCHITECTURE` ·
`Real-time execution: L2 depth + fill protocol` ·
`HALAL UNIVERSE PRE-SCREEN` · `MARKET CAP IS REQUIRED FOR THE HALAL
GATE` · `Bar-granularity policy` · `Trading-day guard` ·
`Paper-session ops hardening` · `SESSION START TIMING` ·
`LOOK-AHEAD PARITY FIXES`

Backtests: `python day-trading/day-trading.py backtest SYM --days 7`
(also candletest / gridtest / pairtest / optimize). Rotation configs
live in `day-trading/plan/rotation_sim.py`.
Real orders would go through E*TRADE limit-only
(`bollinger-trading/test_extended_order.py`) — **not used in paper
sessions**.

---

# ================= HISTORY / RATIONALE BELOW THIS LINE =================
# Dated working notes, kept for the reasoning behind the rules above.
# Where any of it conflicts with the C37 section, the C37 section wins.
# Known-dead: noon and 1PM flatten times, "top-2 gappers per day",
# "any bullish reversal pattern", news-within-18h as a hard gate, the
# $25k opening ticket, and the Z300/Z104 protocol block.

## Paper-session ops hardening (2026-08-05, after the Day-2 timer stall)

The Day-2 background agent's single 5-min background timer silently
died 10:34-11:42 ET (78-min coverage gap). Mandatory pattern for every
future paper session:

1. DUAL TIMERS: every cycle the agent arms TWO staggered background
   timers (300s scan timer + 600s backup). On wake it checks the log's
   last-cycle timestamp: if the cycle already ran, the backup exits
   quietly; if not, it runs the cycle. Never rely on a single timer.
2. MAIN-SESSION WATCHDOG: the coordinating session keeps a ~25-min
   ScheduleWakeup loop that checks day-trading/data/paper/{date}.md mtime; if
   stale >10 min during session hours, SendMessage-nudge the agent
   (it died once already: "no active task" on nudge = it was dead).
3. STRUCTURED DAY FILES (user directive): every session produces, in
   the repo, alongside the markdown log:
   - day-trading/data/paper/{date}.md      -- narrative log (existing format)
   - day-trading/data/paper/{date}.json    -- machine-readable: config, trades
     (entry/exit px, times, sizes, P&L), every candidate with per-gate
     decisions (rvol ours-vs-RH, halal ratios, calm-gap open vs
     prev_close, instrument-type), coverage_gaps, lessons
   - day-trading/data/paper/news/{date}/{SYM}.json -- Finnhub headlines for EVERY
     symbol that appeared on the scan that day (script:
     python day-trading/plan/paper_news.py DATE SYM SYM ...), fetched same day
     (free tier only reaches back ~1 year; same-day capture is cheap
     and permanent)
   All three are committed+pushed at close-out with the day's verdict.

## Scanner = FEED ONLY + no-silent-fallbacks (2026-08-06 audit)

The RH scan (5f132877...) now filters ONLY Last>$2 and %change>+10%
(the 30d-rvol filter HID valid candidates: MOVE +75.6%/halal/calm/
rvol-156 on Aug 4 -- 6 of the backtest's top 8 that day). Protocol:
take the top 8 rows by %change each cycle and apply ALL gates locally
-- our-50d rvol (RH daily bars are the authoritative source), 7AM
calm-gap, halal, +10%-at-entry. NO SILENT FALLBACKS: any stale feed,
source disagreement, or unmet intent must produce a loud "ERROR:"
line in the session log and the day JSON -- never a quiet workaround.
Nightly hygiene: rerun day-trading/plan/scanner_audit.py after the
close to verify the day's feed missed nothing (top-8 diff = NONE).

## Bar-granularity policy (user directive 2026-08-06)

- DEFAULT for any historical lookup (rvol recompute from RH daily/
  intraday, 7AM calm-gap checks, day-shape reviews, post-hoc
  analysis): Robinhood 5-MINUTE bars (~3 months reach). Volume
  comparisons never need finer granularity.
- 1-MINUTE bars are reserved for exactly two uses:
  (a) BACKTESTS via Massive/Polygon (the simulator's native feed);
  (b) LIVE same-day decisions -- "do we buy or sell at this moment"
      (entry-trigger crosses, the paper_watch exit loop).
Everything else that requests 1-min data outside those two cases is a
protocol violation -- log an ERROR line, use 5-min.

## Trading-day guard (2026-08-06)

Run `python day-trading/plan/market_calendar.py` before ANY scheduled
paper session. TRADING -> proceed; NO-TRADE (weekend/holiday) -> abort
silently; ERROR (year outside the calendar) -> abort LOUDLY and extend
HOLIDAYS in that file. Half days close at 13:00.
*** STALE-NOTE CORRECTION 2026-08-13: this line used to say "C30's
flatten already matches", which was true when we flattened at NOON.
C37 does NOT match -- it takes new tickets until 14:30 and exits at
15:00, BOTH AFTER a 13:00 close. On a half day, C37 must scale to the
official close: last new ticket 60 min before it (12:00), all exits by
the close (13:00), flatten ladder from 12:57. The sim degrades safely
on its own (bars simply end and the window-close flatten fires), so
this is a LIVE-ONLY hazard: an agent following the 14:30/15:00 clock
would arm orders into a closed market. Next US half days: 2026-11-27
and 2026-12-24. ***

## Real-time execution: L2 depth + fill protocol (2026-08-07)

DATA AVAILABILITY (tested directly, not assumed):
- ROBINHOOD **DOES** provide Level 2. `get_equity_price_book` returns a
  full bid/ask ladder with resting share size per level (max 4 symbols
  per call). Probed at 03:07 ET it returned empty arrays -- that is the
  book being closed, not a missing feature; the tool guide states
  unavailable-because-closed explicitly. MUST be re-verified during RTH
  on the next paper session before relying on it.
- E*TRADE does **NOT** provide Level 2. Its market API exposes only
  bidSize/askSize -- top of book (L1). The only "Level 2" strings in the
  docs refer to OPTIONS APPROVAL LEVELS, which are unrelated. E*TRADE
  also has no historical-bars endpoint (see bollinger NOTES).
  => ARCHITECTURE: Robinhood for market data and depth, E*TRADE for
  execution (or Robinhood for both). Never source depth from E*TRADE.

WHY FILLS ARE THE REAL RISK: the backtest assumes we transact at the
trigger price. Live, three things break that -- slippage on thin
gappers, partial fills, and no fill at all. The 20%-of-10-min-volume
rule is the primary defence (it sizes us to a fraction of what is
actually trading), and L2 is the secondary one.

PRE-ENTRY DEPTH CHECK (new, uses L2):
Before arming any trigger, pull the price book and sum ask-side size
from the inside ask up to trigger x 1.005. If that cumulative size is
< the shares we intend to buy, REDUCE the ticket to what the book can
absorb; if it is < 25% of intended, SKIP the entry and log
"ERROR: thin book". A wall on the ask just above the trigger is a
reason to expect a failed breakout, not a reason to size up.

ENTRY ORDERS:
- ORB / premarket-high triggers are stop-BUY by nature. Use a
  STOP-LIMIT with the limit at trigger + 0.5% so slippage is bounded;
  accept the occasional no-fill instead of an unbounded market fill.
- Pattern entries fire on a 1-minute close, so send a marketable limit
  at ask + 0.3% immediately on that close.
- If unfilled after 60s: CANCEL. Re-place ONCE, and only while price is
  still within 2% of the trigger. NEVER chase beyond that -- the ORB
  ratchet will re-arm at the next session high anyway.

EXIT ORDERS (asymmetric on purpose -- an unfilled exit is dangerous, an
unfilled entry is merely a missed opportunity):
- NEVER rest a plain limit for a stop. Use marketable limits and
  escalate: bid -1%, then bid -2% after 60s, repeat until filled.
- Scale-out at +25% is decided at the touch (pressure decides), so it
  is not a resting order either.
- 15:00 FLATTEN LADDER (C35): begin 14:57 at bid -1%; 14:59 drop to
  bid -2%; must be flat by 15:00.
- Known residual: halts and gap-throughs fill at the reopen, not at the
  stop. The simulator behaves the same way, so this is modelled, not
  hidden.

FILL-REALISM MEASUREMENT (already running): every paper entry records
the assumed fill AND the price 60 seconds later. First live data point
(E01, LZ 2026-08-06): the 9:30 open fill was 1.7% BETTER than the price
60s later -- i.e. on gapped names the open print can favour us, the
opposite of the usual assumption. One observation is not a finding;
keep collecting.

## RESTING-ORDER ARCHITECTURE (2026-08-07) -- supersedes the earlier
## "unfilled buy/sell" section for anything time-critical

USER CONSTRAINT: "every second or minute matters." A Claude loop cannot
be the execution layer -- scan cycles are minutes apart and each tool
call costs seconds. So the work splits by SPEED REQUIREMENT, not by
convenience:

BROKER LAYER -- resting orders, fill in microseconds, nothing awake:
  1. ENTRY TRIGGERS. Place the ORB-high and premarket-high triggers as
     resting STOP-LIMIT buys (limit = trigger x 1.005 to bound
     slippage). They fill the instant price touches them, whether or
     not the agent is mid-cycle. As the ORB ratchet moves to each new
     session high, CANCEL/REPLACE the resting order -- that re-arming
     is a slow-layer job, but the order itself always rests.
  2. PROTECTIVE STOP. The moment an entry fills, place a resting
     stop-limit at max(entry x0.92, peak x0.60). This is the -8%
     disaster backstop and it is NEVER absent while a position is open.
     Re-place it upward as the peak rises.
Everything above is what genuinely needs sub-second reaction, and all
of it CAN be pre-placed. That is the whole point.

LOOP LAYER -- once per minute, judgment not speed:
  * pressure-modulated trail tightening (10% when sellers dominate)
  * the 1/3 scale-out at +25% and its pressure-skip decision
  * bearish-pattern exits while profitable
  * the 14:57 / 14:59 flatten ladder into the 15:00 close
These are all evaluated on 1-MINUTE CLOSES in the backtest, so a
once-a-minute loop is the CORRECT granularity for them, not a
compromise.

CRITICAL PAPER-SIM SEMANTIC (implemented in paper_watch.py): a resting
stop fills INTRABAR, so it must be tested against each 1-minute bar's
LOW -- not against whatever price the poll happens to see. Testing on
the polled price would silently skip a fast spike down that recovers
before the next poll, making the paper record better than reality.
Loop-layer exits are tested on the bar CLOSE, matching the backtest.

WHAT THIS FIXES: previously the -8% stop was a POLLED condition, so a
fast drop could be seen a minute late. Now it is a resting order with
intrabar semantics in the sim and a real broker order when live.

## L2 assessment -- what it can and cannot do (2026-08-07)

Robinhood's get_equity_price_book is real Level 2 (ladder + resting
size). It will NOT make fills precise, and the protocol must not imply
that it does. Limits, stated plainly:
1. DISPLAYED SIZE ONLY. Hidden/iceberg orders and dark pools are
   invisible, so the book UNDERSTATES real liquidity -- a book that
   looks thin may fill fine.
2. STALE ON ARRIVAL. Fetch + parse + act costs hundreds of ms; on a
   name moving 20% in a session the ladder read is not the ladder the
   order meets.
3. SPOOFING IS COMMON in exactly this class of stock -- displayed
   "walls" get pulled as price approaches.
4. VENUE COVERAGE UNVERIFIED. Retail feeds are often partial views; we
   have not confirmed what RH aggregates. Compare against real fills
   before trusting it.
5. IT CANNOT SEE THE TRIGGER MOMENT. A resting stop fires later, on a
   book unlike the one inspected at arming time.
CORRECT USE: a coarse veto for the obviously untradeable (if the whole
ask side within 0.5% holds 800 shares and we want 5,000 -- shrink or
skip). The REAL protection remains the 20%-of-10-min-VOLUME rule,
which sizes to what actually traded rather than what is advertised.
L2 is the secondary check; volume is the primary one.

## PREMARKET ACTIVITY GATE (replaces the live rvol check, 2026-08-07)

Do NOT compute rvol as partial-day volume over a full-day average --
that is the bug that rejected PN (+$1,333). Do NOT project the full day
from an intraday profile either -- that costs 42% of the edge.

USE: premarket volume / the stock's 50-day average DAILY volume.
  python day-trading/plan/premkt_gate.py PM_VOLUME AVG50_DAILY
  exit 0 = PASS, 1 = FAIL; ERROR lines mean "cannot evaluate" -> WATCH,
  never a permanent reject.
Floor 0.02, deliberately permissive: it exists to exclude names with no
premarket footprint, NOT to select. Backtest keeps 84% of P&L at that
floor and LESS as the floor rises. Real filtering = +10% gain, 7AM
calm-gap <= +20%, halal, price >= prev_close x1.10, 20%-of-10-min-volume
size cap. Log both raw numbers with every decision.

## GATE CORRECTIONS 2026-08-07 (post-close)

PREMARKET GATE = DOLLAR VOLUME, not a share ratio:
  python day-trading/plan/premkt_gate.py PM_VOLUME PM_VWAP
  floor $50,000. Size-neutral -- the share-ratio version rejected TWLO
  (0.016x) on a day it made +$1,267, because that floor was calibrated
  on penny gappers whose premarket dwarfs their normal size.
  NUMERATOR WARNING: the scanner's Volume column is the PRIOR SESSION'S
  volume, NOT today's premarket. Always compute premarket volume by
  summing RH extended minute/5-min bars before 09:30 ET.
HALAL: halal_check now returns halal=False with "NO FUNDAMENTALS DATA"
when mcap<=0 or debt/cash/revenue are all zero. Treat that as
"cannot verify -> do not trade", distinct from a compliance failure.

## MARKET CAP IS REQUIRED FOR THE HALAL GATE (2026-08-07)

halal_check divides by market cap. yfinance returns marketCap=None for
some small caps (SSP, GTN, RMCO), which made every ratio 0.0 and
silently PASSED two names with ~900% loans/mcap.
BEFORE screening any name not already in data/rh_fundamentals.json:
  1. get_equity_fundamentals(symbols=[SYM]) -> market_cap, sector, industry
  2. python day-trading/plan/update_rh_fundamentals.py SYM MARKET_CAP SECTOR INDUSTRY
  3. then python day-trading/day-trading.py screen SYM
A missing market cap now produces "NO FUNDAMENTALS DATA -- cannot
verify, refusing", which is a REFUSAL TO EVALUATE, not a compliance
failure. Do not treat it as a permanent reject -- fetch the cap and
re-screen.


## LOOK-AHEAD PARITY FIXES (2026-08-07 evening) -- the live session must
## behave like the honest backtest, and vice versa. Six fixes, both sides.

1. SCAN CADENCE (leak #5; user 2026-08-08: "the scan cadence will be
   5 min in day trading or backtesting. while if we purchase a stock,
   we need to look each min to know when to sell."):
   * SCANNING (no position): re-scan every 5 MINUTES, 7:00-12:00. A
     name first crossing +10% joins the watchlist at the next 5-min
     scan. Backtested: 30-min cadence cost 25% of P&L (W104); 5-min
     recovers to 90% (W107). Never backfill a late crosser into
     earlier decisions.
   * IN A POSITION: exits are watched on 1-MINUTE bars (pressure trail,
     stop, scale-out) -- unchanged, this is what paper_watch does and
     what the sim does.

2. VOLUME GATE VERDICT (V-sweep, 36 variants): every causal volume floor
   at every decision time LOSES money, monotonically with strictness
   (best gated variant 96% of control, worst 31%). Volume-at-the-moment
   carries no positive selection signal. The premkt_gate call is now a
   DATA-SANITY check only (bars exist, numbers are sane) -- floor 0.0025
   RH-ratio, expected to pass essentially always. Selection is price
   action: +10% crossing, calm-gap, halal, patterns. Pending the W-sweep
   verdict on whether discovery-time volume mattered at all.

3. FEED CALIBRATION (fix #8): NEVER apply a threshold calibrated on
   Massive/Polygon data to Robinhood numbers or vice versa -- same
   symbol-day premarket volume differs ~4x (WDFC 2026-07-10: 25,889 vs
   6,393). Any live threshold must be derived from RH-measured
   distributions. Bar policy unchanged: RH bars for live decisions.

4. SIZING (leak #4): size on COMPLETED minutes only -- 20% of the
   trailing 10 fully-printed 1-min bars' volume. Never count the
   in-progress minute (its volume does not exist yet). Backtest
   equivalent: vol_frac_causal=True.

5. HALTS (fix #7): before any order, get_equity_tradability. If a name
   is halted: leave resting SELL stop-limits in place but EXPECT no fill
   until reopen, and accept that a reopen below the stop fills at the
   reopen print, not the stop (backtest now models this: halt_aware).
   NEVER enter on the reopen bar -- no chasing price discovery. A halt
   while flat = drop the candidate for 30 minutes.

6. PREMARKET SPREADS (fix #9): entries 7:00-9:30 pay the ask on thin
   books. The thin-book veto stays: skip any entry whose L2 spread
   exceeds the 0.5% stop-limit cap. Prefer exits after 9:30 when
   discretionary. Backtest now charges pm_spread_bps on pre-9:30 fills
   (50bps default in the honest stack).

7. HALAL (leak #6): the screen uses the most recent FILED quarterly
   report -- live this is automatic (you can only fetch what is filed);
   the backtest now applies a 45-day filing lag (halal_filing). The
   RH-market-cap requirement above is unchanged.


## HALAL UNIVERSE PRE-SCREEN (2026-08-08) -- scan only halal stocks

The whole listed universe (10,761 clean tickers >= $2) is screened
OFFLINE by plan/build_halal_universe.py using day-trading.py's
halal_check verbatim (latest FILED quarterly -> half-year -> annual
chain). Outputs in day-trading/data/:
  halal_list.json     symbols the scanner is allowed to surface
  halal_universe.json full verdicts + ratios (audit trail)
  needs_mcap.json     unverifiable names: fetch RH market cap via
                      update_rh_fundamentals.py, then re-run the builder
MORNING PROTOCOL: the 5-minute scanner FILTERS ITS RESULTS AGAINST
halal_list.json -- no per-name fundamentals calls at scan time.
WHILE THE UNIVERSE IS INCOMPLETE (check halal_universe.json coverage;
yfinance rate limits stretched the first build over days): a scanner
hit that is MISSING from halal_universe.json gets the old per-name
live screen (RH mcap + halal_check) instead of auto-rejection -- absence
of a verdict is not a verdict. A name with a real FAIL verdict is
rejected without re-checking. Names passed only by "seed-rules_ytd"
(backtest-era statements) MAY trade but re-screen them live first. If halal_list.json is older
than ~35 days, say so loudly and refresh before trading.
REFRESH: Windows Task Scheduler job \Stocks\HalalUniverseRefresh runs
plan/refresh_halal_universe.cmd on the 1st of every month, 6:10 AM
(before the 6:56 paper cron), logging to data/halal_refresh.log. The
first trading morning each month: check the log, backfill needs_mcap
names via Robinhood, and COMMIT the refreshed lists.


## [SUPERSEDED by C37] Z300 RANKING (2026-08-09)
At each 5-minute scan, among names currently >= +10% vs yesterday's
close: rank by COIL = current price / premarket high, DESCENDING
(closest to reclaiming its premarket high first). Walk up to 12
candidates; the first passing calm-gap (<=20%, 35% grace for the
top-ranked) + halal-list check is the day's stock. Benchmark: Z300,
+$706,089/2yr fully causal, ~$1,790/day.


## ===== [SUPERSEDED] Z300/Z104 MORNING PROTOCOL (2026-08-10) =====
## DEAD. Replaced by C37 (one position, flat $15k tickets, rotation,
## 14:30 cutoff, 15:00 exits). Kept only for the reasoning. Its $25k
## opener, 12:00 scan end and Z104 benchmark are all wrong now.

PRE-OPEN (from 6:56):
 1. Trading-day guard; verify halal_list.json age (<35 days) -- else warn.
 2. NO real orders ever. Paper ledger only, one file per day as before.

SCAN LOOP -- every 5 MINUTES, 7:00-12:00 (RH data only):
 3. Candidates: price >= $2, currently >= +10% vs yesterday's close
    (crossing must have HAPPENED -- never anticipate), common stock,
    >= 50 sessions history. NO volume gate of any kind.
 4. HALAL: name must be on data/halal_list.json, or absent-from-universe
    -> live screen (RH mcap + halal_check); real FAIL verdict -> skip.
 5. RANK (Z104, 2026-08-09): COILED names first (current price /
    premarket high >= 0.95), ordered within the group by PREMARKET
    BUY-PRESSURE (30-bar signed-volume pressure, 20k-share trust
    floor); non-coiled after, same pressure order. Walk up to 12;
    first name passing calm-gap (<= +20%; 35% grace for the
    top-ranked name only) is THE stock of the day. Never use any
    full-day quantity in ranking -- that was the last leak.
 6. Late crossers are legitimate: a name first crossing +10% at 10:30
    enters the ranking at the 10:35 scan. Never filter by crossing time.

POSITION (Z300 = C35 mechanics, unchanged):
 7. Entries 7:00-12:00 via resting orders: 5-min ORB break / premarket-
    high stop-buy / bullish reversal candle. First ticket $25k, later
    $15k, $100k/day total, last ticket = remainder if >= $1k.
 8. Size <= 20% of trailing 10 COMPLETED minutes' volume. Thin-book
    veto: skip entry if L2 spread > the 0.5% stop-limit cap.
 9. Watch the open position every 1 MINUTE: 20% trail from peak
    (10% when 10-bar pressure <= -0.3, 40% when >= +0.3), hard stop
    -8%, bank 1/3 at +25% unless pressure >= +0.3, wick guard, halt
    protocol (tradability check; never enter on a reopen bar).
10. All exits by 15:00. Same day, always.

BENCHMARK (updated): Z104 = $646,581/2yr, ~$1,290/traded day, 2/22
neg months. Compare against this, not C35/W109/Z300.
REPORTING: entries/exits relayed to main as they happen + EOD summary.


## C37 MORNING PROTOCOL (2026-08-10) -- original entry, now restated
## in full at the TOP of this file. Benchmark line below is stale.

TICKETS (user cash rules, hard): flat $15,000 each, the 7th/last is
$10,000, total $100,000/day. ONE position at a time -- never a second
ticket while one is open. T+1: today's spend returns tomorrow.

SCAN LOOP every 5 MINUTES, 7:00-14:30 (RH data only):
 1. Eligible: price >= $2, crossing of +10% vs yesterday's close has
    ALREADY printed, common stock, >=50 sessions, on halal_list.json
    (missing verdict -> live screen; real FAIL -> skip). NO volume gate.
 2. RANK the eligible: COILED first (current price / premarket high
    >= 0.95), ordered by 30-bar buy-pressure (20k-share floor);
    non-coiled after, same order. Calm-gap <=20% (35% grace for the
    top name) still gates entry.
 3. WHEN FLAT and tickets remain: watch the top-ranked name for the
    standard triggers (5-min ORB break / premarket-high stop-buy /
    reversal candle). If the pick hasn't ENTERED by 10:00, re-rank and
    switch (stale-pick escape). New tickets allowed until 14:30.
 4. ROTATION: when a ticket exits, the next ticket goes to whatever
    name ranks best NOW -- same name only if it still ranks first.
    Late crossers are first-class candidates (a 13:40 crosser is a
    legitimate 13:45 pick).
 5. IN POSITION: watch 1-MINUTE bars -- trail 20%/10%/40% by pressure,
    hard stop -8%, bank 1/3 at +25% unless pressure >= +0.3, wick
    guard, halt protocol (no entries on reopen bars). ALL EXITS BY
    15:00, same day always.
BENCHMARK (CORRECTED 2026-08-13): C37 = $665,667/2yr over 432 traded
days = ~$1,541/traded day, 0/23 negative months. Judge weeks, not days.
The old $774,534 / $1,956-a-day figure was inflated 14% by a hindsight
pool cut (the sim picked its 16 candidates by DAY-HIGH gain, a full-day
statistic, which quietly pre-removed names that turned out not to run).
Fixed 2026-08-13; the strategy itself is unchanged and still beats both
its no-rotation baseline (+69%) and a random-pick control (+$188,607).
Paper sessions before 2026-08-13 were scored against the inflated
number -- re-read those verdicts with $1,541/day in mind.


## FILL-ARMING RULE (2026-08-10, from Paper Day 5's -1.6% fill miss)

NEVER arm a stop-buy whose trigger level has ALREADY been met. On
2026-08-10 LFST's stop 12.045 was armed after price had traded through
it; a stop with a met trigger is just a market order, and it swept the
book at a local top (fill 12.0710, -1.6% vs the +60s assumption --
the first negative fill-realism data point).

Protocol, checked at EVERY arming:
 1. Re-quote immediately before arming. If last/bid >= trigger, the
    stop conversion is live NOW -- do NOT arm it as a stop.
 2. Instead place a MARKETABLE LIMIT capped at trigger + 0.5% (the
    same cap as the thin-book veto), sized against visible ask depth.
    If the book can't fill inside the cap, treat it as a veto: wait
    for the next 1-min bar and re-evaluate -- a level already taken
    out will usually retest within minutes (and if it doesn't, the
    entry was a chase).
 3. If last < trigger, arm the stop-limit normally (stop trigger,
    limit trigger + 0.5%).
This preserves the backtest's fill assumptions: the sim fills breaks
AT the trigger, not at a post-break sweep.


## OUTAGE / DEAD-MONITOR SETTLEMENT (2026-08-11, from Paper Day 6's
## 4.5-hour internet loss)

On 2026-08-11 an internet outage killed the session agent at 10:35 ET
with FRMI open; monitoring did not resume until 15:01 ET. The record
survived intact because every rule was already specified at arm time.
Follow this whenever monitoring dies -- connectivity loss, agent crash,
harness reap, machine sleep -- for ANY part of the session.

THE LINE: rules armed BEFORE the gap may be settled from the tape.
Decisions not made during the gap stay unmade. Settlement is honest;
backfilling is not.

 1. LOG THE GAP FIRST, in coverage_gaps: exact window (UTC and ET) and
    the cause. Never quietly close a hole in the tick log.
 2. OPEN POSITION -> SETTLE, do not guess. Pull the real minute bars
    for the gap window and replay the ALREADY-ARMED exit rules
    bar-by-bar in time order: hard stop, trail (at the width the
    pressure state had set), scale-out level, wick guard. The FIRST
    rule whose condition is met sets the exit price and time. If none
    fired by 15:00 ET, exit at the 15:00 flatten. Record the settled
    fill plus an optimistic/pessimistic bracket from the bar so the
    P&L's uncertainty is visible.
 3. NO ENTRIES FOR THE GAP. Never credit a rotation pick, a trigger,
    or a re-rank that was not executed live -- with hindsight bars
    every skipped name looks decidable, which is exactly the leak the
    honesty ladder spent $517k measuring. Undeployed tickets simply
    stayed undeployed.
 4. STATE THE DIRECTION OF THE BIAS in the EOD summary: with rotation
    unavailable, the day UNDERSTATES a full C37 session. Say so; do
    not let a truncated day read as a strategy result.
 5. RESUME LIVE if the window is still open: re-rank from current data
    and continue with the tickets that remain. Do not try to "catch
    up" on the day's ticket count.

Why this works, and the standing lesson: C37's orders are fully
specified at arm time (stop, trail law, scale-out, hard 15:00
flatten), so a blackout is deterministically settleable with zero
discretion. That is an argument FOR resting orders over loop-layer
decisions -- and for broker-resident OCO (stop + timed flatten) if
this ever goes live, which would make the settlement step itself
unnecessary.


## SESSION START TIMING (2026-08-12, after three straight late starts)

The launch cron is set for 6:40 ET, NOT 6:55. The scheduler adds up
to 15 min of jitter to a daily job and only fires while the REPL is
idle, so a 6:55 target produced 07:38 / 07:20 / 07:19 actual starts on
Days 5-7 -- each losing the front of the 07:00-14:30 scan window,
which is where the opening coil ranking gets established. 6:40 buys
20 minutes of slack ahead of 07:00.

If the session still opens after 07:00, log the missing minutes as a
coverage gap and start scanning from the current bar. Do NOT reconstruct
the ranking for minutes that were never scanned.


## SCAN ECONOMY (2026-08-12) -- SUPERSEDES "5-minute scans, always"

PARITY FINDING (read this first). The champion's own harness
(plan/rotation_sim.py::run_day) ranks ONLY when a ticket is free:

    while ticket_i < len(TICKETS):
        pool = rank_at(cands, t)     # rank
        ... simulate the whole ticket ...
        t = _step(max(t, exit_t))    # jump straight to the exit

Between entry and exit it performs NO ranking at all. C37's $774,534
was earned by a process that looks at the market only when it can act.
Live has been scanning every 5 minutes regardless -- on Day 7 that was
~40 of 47 cycles spent ranking names we were structurally forbidden to
buy (one-position rule). That is not extra safety; it is pure API and
attention cost, and it starved the position watch (cadence drifted to
5-12 min).

CADENCE RULES:
 1. FLAT and tickets remain -> full 5-minute scan+rank. This is the
    only state where ranking changes what we do.
 2. IN POSITION -> NO ranking duty. Refresh a light BENCH every ~20
    min (names that crossed, price + coil only, no live halal screens)
    so the post-exit re-rank starts warm. The position watch owns the
    1-minute cadence and must never be starved by scan work.
 3. AT EXIT -> immediately run a FULL fresh rank before deploying the
    next ticket. The bench is a warm start, never the decision: the
    champion re-ranks on current data at the moment of deployment.
 4. No tickets left, or past the 14:30 entry cutoff -> stop scanning
    entirely; exit management only.
 5. Log the cadence state per cycle (FLAT-5m / HOLD-20m / EXIT-RERANK)
    so a drift is visible in the ledger instead of inferred later.

QUERY REDUCTIONS (all preserve behaviour exactly):
 a. The +10% crossing is a LATCH. Once a name's cross has printed it
    stays eligible all day -- never re-query to re-confirm it. Track
    the crossed set; only un-crossed names need the threshold check.
 b. Screen halal LAZILY, at the moment of candidacy (top-3 AND coil
    >= 0.95 AND calm-gap OK), not for every new name that appears.
    Day 7 ran 11 live screens for names that were mostly never
    actionable.
 c. Prefer ONE server-side scan for the universe sweep over per-symbol
    quote polling (Step 1 already does this) -- then one batched bars
    call per ranking cycle, not one call per symbol.
 d. Bars, not quotes, are the ranking input: a single batched
    historicals call yields last/high/pressure for up to 10 names at
    once. Quotes are for arming and fills.


## API HYGIENE (2026-08-12, three defects from Paper Day 7)

 1. SILENT TRUNCATION -- get_equity_historicals accepts at most 10
    symbols and DROPS the rest with no error. On Day 7 this removed 9
    eligible names from one cycle's ranking. Batch every call to <= 10
    symbols AND assert the returned symbol set equals the requested
    set; on mismatch emit a loud ERROR line and re-request the missing
    names. Never rank on a partial universe -- a truncated ranking is
    indistinguishable from a complete one in the output.
    Treat every batch API as guilty of this until proven otherwise.
 2. HALAL VERDICTS ARE DAY-SCOPED AND MUST BE INHERITED. A delegated
    scanner twice re-surfaced TC and EXYN as eligible after both had
    FAILED the live screen, because delegates do not see the
    coordinator's verdicts. Pass the day's PASS and FAIL sets into
    EVERY delegated scan, and have the delegate drop FAILs before
    ranking. The coordinator re-checking downstream is a backstop, not
    the mechanism. A FAIL that reappears as a candidate is a
    compliance near-miss even when nothing trades.
 3. ONE AGENT CANNOT DO BOTH JOBS. Managing an open position starves
    the scan loop (Day 7: 5-12 min instead of 5, position polling
    6-10 min midday). Under the cadence rules above the conflict
    mostly disappears -- but when both are live, the POSITION WATCH
    WINS. Exits are time-critical and irreversible; a late scan only
    delays a pick that gets re-ranked at deployment anyway.


## THE `rank` COMMAND (2026-08-13) -- USE IT INSTEAD OF RANKING BY HAND

Measured on Paper Day 7: 47 cycles, 285 tool calls, 9.9 min per cycle
against a 5-min target, 98 SECONDS per tool call. The MCP calls
themselves are ~2s; over 97% of the session's wall clock was the agent
thinking between six sequential round-trips per cycle. Ranking is a
pure function of bars -- stop doing it in conversation.

    python day-trading/day-trading.py rank SYM:PREVCLOSE [SYM:PREVCLOSE ...] \
        [--as-of HH:MM] [--date YYYY-MM-DD] [--top N] [--json]

One call returns the whole cycle: crossed/not, last, gain%, coil,
30-bar pressure (20k floor, "n/a" = UNTRUSTED), 7AM gap, calm-gap
verdict with the 35%-top grace applied, halal PASS vs NEEDS-SCREEN, the
reason every excluded name was excluded, and the armable TOP name.

CYCLE SHAPE (target 2 tool calls, not 6):
 1. batched get_equity_historicals (<=10 symbols/call, assert the
    returned set matches the request) -> write data/rh_bars/{SYM}_{date}.csv
 2. `rank` -> read the TOP line, then arm.
Anything the ranker already computes must NOT be recomputed by hand.

GUARANTEES AND LIMITS:
 * ORDERING IS THE CHAMPION'S, verified: coil-first (last/high >= 0.95),
   30-bar pressure within group, untrusted pressure sorts last. Parity-
   tested against rotation_sim.rank_at on 180 (day, time) rankings --
   0 mismatches. If you ever rank by hand and disagree with this
   command, the command is right and you are drifting (that is the
   Day-6 retest-entry class of error).
 * CAUSAL: only bars at or before --as-of are read.
 * FAILS CONSERVATIVE: a missing 7AM gap reads as CALM-GAP FAIL, and an
   unreadable halal list makes every name NEEDS-SCREEN. NEEDS-SCREEN is
   NOT a pass -- run the live screen before arming.
 * It ranks; it does not arm. Book/L2 depth, the fill-arming rule and
   the thin-book veto are still yours to check at the moment of arming.


## LIVE-vs-BACKTEST PARITY AUDIT (2026-08-13) -- read before every session

Two divergences have already cost real money to discover (the spread
veto, worth $100k+ of modelled edge; ranking-by-conversation, which
produced the Day-6 retest slip). This is the standing list. When you
find a new one, add it here.

### REAL DIVERGENCES (live behaves differently from the champion)
 1. BOOK/SPREAD VETO. Live refuses entries wider than 0.5% inside
    spread. The sim has NO such veto -- it pays a 50bps premarket
    haircut and takes the trade. Modelled (V-series): the optimum
    blocks the widest ~50-65% of would-be entries; live's premarket
    rate is ~90-100% (Day 7 blocked EVERY premarket rank-1). WE ARE
    TOO AGGRESSIVE PREMARKET. Log the veto rate every session so this
    stays measurable; calibrate by RATE, not by threshold, and treat
    premarket and post-open separately (09:30 collapses spreads).
 2. THE CROSS IS A LATCH IN THE SIM, A SNAPSHOT IN THE SCANNER. The
    scan filters on %Change > 10% RIGHT NOW. A name that prints +12%
    and fades to +8% DISAPPEARS from the scan -- but the champion
    still considers it eligible, because its +10% cross has printed.
    Keep a day-long CROSSED SET: once a name appears, it stays a
    candidate for the rest of the session even when it drops off the
    scanner. Dropping it is under-discovery, and it silently makes
    live a different (smaller-universe) strategy.
 3. ENTRY PATTERN SET. The champion's buy_set is EXACTLY eight:
    bullish_engulfing, bullish_spinning_top, hammer, morning_star,
    rising_three, tweezer_bottom, macd_cross_up, rsi_cross_up.
    The engine can also label dragonfly_doji and inverted_hammer --
    the champion DELIBERATELY EXCLUDES BOTH (dragonfly_doji measured
    -$1,186; inverted_hammer +$17/position, below transaction cost).
    "Any bullish reversal pattern" is therefore WRONG as an entry
    rule. Only those eight count as Trigger C.

### CHECKED AND NOT DIVERGENT (do not re-litigate)
 * Relative volume: the saved scan has NO rvol filter (verified via
   get_scans 2026-08-13). Matches the champion's novol pool.
 * News: the C37 protocol has NO news gate, and Day 7 correctly
   applied none. The old "news within 18h" rule in the Rules-recap
   section is SUPERSEDED -- earnings/news flags were measured as
   noise (a shuffled control out-earned the real gate).
 * Ticket schedule: the champion's $25k opener is popped by the
   rotation harness; flat $15k (last $10k) is correct for both.
 * Exit end: 15:00 in both.


## PAPER DAY 8 (2026-08-13) — what the session taught

Result: **1 ticket, ANGX -$29.83**, flat by 15:00, zero real orders. Cumulative -$257.57.
First fully clean session in three (no outage, on-time 06:34 start, zero API truncations).

### 1. THE HALAL GATE AND THE SPREAD VETO PULL IN OPPOSITE DIRECTIONS

103 names crossed +10%; 33 were live-screened; **31 FAILED**. The three tightest books
of the day — **IREN 0.04%, SMCI 0.02%, ABTC 0.26%** — were all halal-ineligible, while
the eligible pick (AZ) sat at 0.41-0.92%. Large liquid names carry the leverage that
fails the ratio test; the names that pass tend to be small and wide.

This is **structural, not bad luck**, and it is the main reason C37 cannot deploy capital
live. BIRK (20.3% LBO debt), AVAH (76%), JACK (694%) and IREN (35% combined) were exactly
the tradeable books the strategy wants. Any future work on "why is live below benchmark"
should start here rather than with the entry logic.

### 2. EXIT DEPTH MODELLING IS WORTH MORE THAN ENTRY DEPTH MODELLING

Selling 3,040 ANGX into a **113-share inside bid** swept the ladder 4.28 → 4.24, VWAP
4.2552. Booking the naive "filled at the inside bid" would have recorded **+$45.60
instead of -$29.83 — a $75.43 self-flattery on one $13k ticket.** Across seven tickets a
day that fabricates an edge that does not exist.

**Rule: always model the exit as a ladder sweep against displayed depth, and record the
optimistic single-price figure only as a bracket.** Entry fills have been fine (2 of 3
favourable); exits are where the fiction creeps in.

### 3. TRIGGER C WAS UNAVAILABLE ALL DAY — TOOLING GAP, HIGHEST-VALUE FIX

The champion's eight-member reversal set was **never mechanically evaluated**.
`day-trading.py patterns` takes a bare symbol and reads *daily* data, so it cannot score
live 1-minute RH bars. Only Trigger A (ORB) and Trigger B (session-high stop-buy) were
usable. **One of three legal entry triggers was missing**, which directly reduces how
many setups qualify on a day when almost nothing passes halal.

TODO: add a `patterns --bars-dir data/rh_bars --as-of HH:MM SYM` path that scores the
eight-member buy_set on cached 1-minute bars, the way `rank` already does.

### 4. VETO RATE FINALLY IN BAND — 3/6 = 50.0%

| phase | decisions | vetoed | rate |
|---|---|---|---|
| premarket | 1 | 1 | 100% |
| post-open | 5 | 2 | 40% |
| **total** | **6** | **3** | **50.0%** |

Modelled optimum is 50-65%; Day 7 ran 90-100%. **All three vetoes were saves; none cost
money.** Post-open at 40% is slightly *below* the band, so the 0.5% cap now looks about
right post-open. Premarket still blocks everything but on a single decision.

**Count the fill-arming/chase veto SEPARATELY from spread vetoes** — only 2 of the 3 were
spread-driven. Mixing them corrupts the threshold calibration.

### 5. THE FILL-ARMING RULE PAID FOR ITSELF, AND "RETEST" IS STILL THE WRONG WORD

ANGX at 10:38: spread was fine (0.24%) but price had run **0.85% past the trigger**, so a
stop would have been a market order and a marketable limit could not fill inside the
+0.5% cap → veto. Six minutes later the **ratchet re-armed** at a new session high
(4.2650) with last back below it, giving a genuine forward stop. It filled at 11:17,
**0.12% better than the +60 s mark**.

Say **"ratchet re-armed at the new high; waited for last < trigger"**. Do **not** say
"retest" — retest entries are a rejected mechanic (G-series: a nonsense-level control
beat every real retest level). This wording slipped on Day 6 and again on Day 8.

### 6. NEW LIVE-ONLY DIVERGENCE: L2 DEPTH TICKET REDUCTION

ANGX was cut from 3,517 sh / $15,000 to **3,040 sh / $12,965.60 (-$2,034.40, -13.6%)**
because displayed ask depth to trigger+0.5% was only 3,040 shares. The sim sizes purely
on 20% of trailing 10-min completed volume and models **no** book depth. Bias is
**conservative** — live deploys less than the champion, so filled-ticket P&L understates
the strategy. Keep it, but price it later the way the spread veto was priced.

### 7. CHEAP NEW DETECTOR: ALL-INTERPOLATED BARS = FAKE GAP

EUDA (+50%), FORTY (+38%) and DAAQ (+13%) each returned **161 interpolated bars and zero
real ones** — they had not traded premarket at all, and their headline scan %Change was a
stale mark. The interpolated-bar count is a one-line detector for scanner artefacts on
illiquid names. `plan/rh_bars_ingest.py` now reports it per symbol.

### 8. OPS THAT WORKED — KEEP DOING THESE

* **Delegate the scan sweep to a subagent** with the day's PASS/FAIL sets passed in.
  Keeps ~6k tokens of raw scan JSON per cycle out of the coordinator AND makes the
  API-HYGIENE #2 inheritance structural. No FAIL re-entered the pool all day.
* **`plan/rh_bars_ingest.py`** (new) asserts the returned symbol set equals the request
  and skips interpolated bars. Zero truncations across ~10 batched calls.
* **`get_equity_quotes` for spread monitoring, `get_equity_price_book` only at the moment
  of arming.** The full L2 ladder is expensive; inside bid/ask for 5-10 symbols is not.
* **Oversized MCP responses spill to a file** — that is a feature. Fetch bars for up to
  10 symbols, let the response overflow, and parse the file. The bars never touch context.
* Foreground `until`-loop waits (10-min cap) are the reliable way to pace a long session.

### 9. ONE POSITION + ONE SLOW NAME = ONE TICKET

ANGX was held 3h40m and moved in a ~2.5% band. The one-position rule meant tickets 2-7
(**$87,034 of the $100,000 budget**) never deployed, and the 14:30 cutoff closed the
window. C37's $1,541/day assumes rotation through several tickets; a day with one quiet
holder cannot reach it by construction. That is a property of the champion, not a bug —
but it means **single-holder days should be judged on process, not P&L.**


## TRIGGER C CADENCE (2026-08-14, from Paper Day 9's 7 fires / 0 takeable)

A pattern entry is valid ONLY on the 1-minute close that produced it.
Day 9 proved a 5-minute rank loop makes every Trigger C signal 1-5 min
stale, so one of the three legal entries had effectively never run live.

RULE: while FLAT with a TOP name selected, poll THAT name's 1-minute
bars EVERY MINUTE (one batched bars call) and run
  python day-trading/day-trading.py trigger TOP --as-of HH:MM
on each close. The command now tags every signal [TAKEABLE NOW] or
[STALE Nm old -- DO NOT ENTER] (default freshness 2 min, --max-age).
NEVER enter on a STALE tag -- the tag does the refusing, not judgement.
The 5-minute cadence still owns the full re-rank; the 1-minute poll is
only for the current TOP name's pattern trigger. Triggers A (ORB) and B
(high stop-buy) are resting orders and need no polling.

## DEPTH VETO and SPREAD VETO ARE DIFFERENT RULES (2026-08-14)

Day 9's LPTH PASSED spread (0.485%) and FAILED depth 4 minutes later on
the same name (200 sh at the inside ask, then a 2.8% air pocket). Log
and count them separately, plus fill-arming/chase vetoes as a third
category. The ~50-65% optimum from the V-series was modelled on a
bar-range proxy and speaks to the SPREAD veto only; the depth veto and
chase veto have never been modelled. A single blended "veto rate" hides
which rule is binding.

## CLOCK RULE (2026-08-14): TZ env is BROKEN on this machine

`TZ=America/New_York date` returns UTC on this box -- it silently cost
Day 9's first clock an hour. Never trust the TZ environment variable.
Compute ET explicitly (UTC-4 in summer / UTC-5 in winter) or via
Python zoneinfo("America/New_York"); arm all Monitor clocks on UTC.
