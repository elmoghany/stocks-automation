---
description: Penny-stock morning workflow — Robinhood scan, cache refresh, screen, live watch, order (7AM-noon ET)
---

The full Cameron Ross morning workflow. Data sources: Robinhood MCP
(scanner, 1-min bars with real premarket volume, float/sector), Finnhub
(news 18h), E*TRADE (live quotes/volume + orders). Run during 7AM-noon ET.

## Step 1 — Run the saved Robinhood scan (all rules server-side)

Call MCP tool `run_scan` with scan_id `5f132877-7730-4a18-9e72-b3f0d2c9df83`
(filters: Last >$2 NO CEILING, %Change>=10% 1d, RelVolume>=5x 30d,
sorted %Change desc; C1 adopted 2026-08-03: ceiling+float removed). Results are live. If empty: no A+ gapper today — DO
NOT force a trade; the edge comes from patience (see NOTES-DAYTRADING.md).

## Step 2 — Refresh the Robinhood caches for the candidates

DAY PICK (calm-gap rule, $15k/day total): among qualifying gappers,
trade the HIGHEST-GAIN one whose 7AM price is <= prev_close x 1.20 --
if the leader gapped hotter than +20% at 7AM it is an exhausted
overnight move (they bleed); walk down to the next calm one (check top
4), else skip the day. The $2k+ days are intraday developers: modest
7AM gap, then a +100-300% session run our trail rides. For each scan hit (top 3 max for cache refresh):
1. `get_equity_fundamentals` (bounds=extended) → update
   `data/rh_fundamentals.json`: keys float, shares_outstanding, market_cap,
   sector, industry, avg_volume_30d, avg_volume_2wk, fetched, source.
2. `get_equity_historicals` symbols=[SYM], interval=minute, bounds=extended,
   start_time=TODAY 11:00Z, end_time=now (window 7AM-NOON ET; 7AM = 11:00 UTC summer,
   12:00 UTC in winter) → write `data/rh_bars/{SYM}_{YYYY-MM-DD}.csv` with
   header `begins_at,open,high,low,close,volume` — SKIP bars where
   interpolated=true. day-trading.py merges these over yfinance
   automatically (Robinhood wins on overlapping minutes).

## Step 3 — Verify rules + news (python, uses the caches)

```bash
python day-trading/day-trading.py screen SYM1 SYM2 ...   # 6-rule table; news via
                                              # Finnhub (lazy, last gate)
python day-trading/day-trading.py livescreen SYMS --prod # E*TRADE real-time cross-check
```

Trade only symbols passing ALL rules including news-within-18h.

## Step 4 — Watch for the entry, then order

```bash
python day-trading/day-trading.py livebars PICK --prod   # live 1-min candles + patterns
```

Entry per current calibration (NOTES-DAYTRADING.md, 2026-08-04, C02 spec):
DEFAULT = any bullish reversal pattern OR 5-minute opening-range breakout
(break of the first-5-volume-bars high) OR premarket-high stop-buy (break
of the premarket high, one-shot), no volume gate, entry only while price
>= prev_close x1.10. Size up to 20% of trailing 10-MINUTE volume (was
10%/5min). RIDE with a PRESSURE-MODULATED trail (C21): base 20% from peak, TIGHTEN
to 10% when rolling 10-min sell pressure <= -0.3, WIDEN to 40% when buy
pressure >= +0.3 (pressure = volume-weighted close position in bar
range, 20k-share floor); -8% hard stop; bank 1/3 at +25% UNLESS buyers
still dominate (P >= +0.3) -- then keep the full position riding.
Ignore lone 1-bar wicks >3x surrounding closes when tracking peaks. EVERYTHING flat
by NOON same day (1PM extension tested and withdrawn by user).
(C21: Y1 +$395,243 / Y2 +$519,641, ZERO negative months both years;
avg +22.6% of capital per trading day; 93% survives 10bps slippage.)
UNIVERSE: any clean ticker >= $2 -- NO price ceiling (the $75 cap
silently deleted the mid/large-cap earnings gappers that carried
Jan-Mar 2025; scanner must not cap price). Live halal via current
data IS point-in-time correct; walk up to 8 calm candidates for the
first compliant one. Position ~$15k (capped at 20% of trailing 10-min volume; PDT needs
$25k+ equity). Expect roughly: half of qualifying days trade, ~3 of 4
traded days win, losses capped ~-$1,500, profit concentrated in a few
big trailing winners. ALWAYS flat by NOON.

UNFILLED-BUY RULE (1 minute): place LIMIT at trigger +0.5%; if not
filled in 60s, CANCEL. If price ran <= +2% above trigger, re-place at
market price once; beyond +2% DO NOT CHASE -- the ORB ratchet re-arms
at each new high and will produce the next trigger. If price fell back
below the trigger, cancel and wait (pullback often gives a pattern
entry). In paper sessions log both the assumed trigger fill AND the
price 60s later -- that spread is the live slippage measurement.

UNFILLED-SELL RULES (asymmetric: sells are NEVER abandoned):
- Stop/trail exits: limit at stop level -1% (marketable); unfilled in
  60s -> escalate to bid -2%, repeat every 60s until flat. Position
  size <= 20% of 10-min volume guarantees exit liquidity exists.
- Scale-out +25%: NOT a resting limit (the C21 skip decides at the
  touch using pressure) -- the 1-min watcher sells with a marketable
  limit when banking is chosen.
- Pressure-flip/bearish exits: marketable limit -0.5%, same 60s
  escalation.
- NOON FLATTEN: start 11:57 at bid -1%, escalate 11:59 to bid -2%;
  flat by 12:00 without exception.
- Known residual: halt/gap-throughs fill at the reopen, not the stop
  (sim behaves the same; the backtest's worst day was exactly this).

Orders go through E*TRADE (LIMIT only):
```bash
python bollinger-trading/test_extended_order.py --session EXTENDED --account 0   # preview
# add --confirm to place; needs daily prod token (--auth / --verifier)
```

## Backtesting note

Backtests run offline against merged Robinhood-CSV + yfinance data:
`python day-trading/day-trading.py backtest SYM --days 7` (also candletest / gridtest /
pairtest / optimize). To backtest a past gapper day properly, fetch its
1-min bars via `get_equity_historicals` for that date (bounds=extended) and
write the CSV first — Robinhood 1-min history reaches ~2+ weeks back,
5minute reaches ~3+ months (write 5-min caches for older dates).

## Rules recap (all enforced in day-trading.py)

Gate ORDER (lazy -- each stage only runs if the prior passed):
1. FREE: price $2+ (no ceiling) + up >=10% + rvol >=5x (one quote/history call)
2. HALAL: loans/mcap <=10%, deposits/mcap <=10%, combined <=20%, haram
   revenue <5%, no haram industry (see /halal-check) -- FIRST expensive
   gate so no time is wasted on non-halal stocks
3. hot sector (float rule DROPPED 2026-08-03 -- float shown as info only)
4. news within 18h (Finnhub first, Yahoo second -- FH:/YF: tags)
Trading: buy inside 7AM-noon, exits until 1PM, force-flat at 1PM (C23, re-adopted 2026-08-05); $2 floor and +10% re-checked AT ENTRY per bar (NO price ceiling);
trade top-2 qualifying gappers/day.
WARNING from live testing: low-mcap gappers frequently fail halal on the
cash or debt ratio (small mcap denominator) -- expect the halal gate to
eliminate many scanner hits; that is by design.

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
HOLIDAYS in that file. Half days close at 13:00 -- C30's flatten
already matches; E01 uses the official close regardless.

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
