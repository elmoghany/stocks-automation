# CHAMPION-REPLAY (2026-09-17)

**The user's instruction.** *"Try to mimic C37, C31, C36, C35 but without
future signals. There must be a way."*

This line takes that literally: not "find a new edge", but **re-derive the
champions' economics causally, component by component**, and say exactly
which parts of $774,534 were information the trader could have had and
which were information only the tape knew afterwards. Halal is ignored in
the decisions and applied post-hoc at the end (Part 5), as instructed.

Files: `plan/cp_panel.py`, `plan/cp_prior.py`, `plan/cp_lib.py`,
`plan/cp_feat.py`, `plan/cp_scan.py`, `plan/cp_cost.py`, `plan/cp_sim.py`,
`plan/cp_fetch.py`, `plan/cp_premkt.py`, `plan/cp_detect.py`,
`plan/cp_run.py`, `plan/cp_waterfall.py`; new caches
`data/massive/cp_panel` (444 sessions of the whole gapper tape on a fixed
minute grid), `data/massive/cp_prior` (542 sessions of prior-only context
for every US ticker), `data/massive/cp_feat`, `data/massive/m1c`
(8,042 symbol-days of NEW bars + the premarket census fetch),
`data/massive/cp/`.

---

## Part 0. What the champions actually were

**First correction, and it matters for reading anything else.** The
registry has no `C31` and no `C36`. `grep -rn '"C31"' plan/*.py` and the
same for C36 return nothing; `C36` appears exactly once in the whole repo
(`CONFIGS-TESTED.md:1601`) as a never-built placeholder label in the
Z-campaign plan. The sequential-rotation family that posted the numbers is:

| name in the notes | registry id | what it was | posted |
|---|---|---|---|
| C34 | `S093` | C23 rules, flat ticket ladder, exits to 15:00 | $1,019,966 |
| **C35** | `S095` | C34 + **front-load the day's cash into entry #1** ($25k first ticket) | **$1,163,538** |
| W109 | — | C35 with three look-ahead signals removed | $872,790 |
| Z104 | `Z104` | coil-group / 30-bar-pressure ranking, causal walk-12, static (one name per day) | $646,581 |
| **C37** | `R061` | Z104 machinery + **sequential ticket ROTATION**, 14:30 window, 10:00 stale-pick escape, one position at a time, $15k x 6 + $10k, $100k/day | **$774,534** |

So the family the user named is really **C34 -> C35 -> W109 -> Z104 -> C37**,
and everything below replays C37, because C37 is the one that was adopted,
the one the live book runs, and the one every later epoch row is keyed to.

**What was future-conditioned, verified from the code rather than from the
notes.** Five things, not four:

1. **Bar coverage.** Minute bars were only ever fetched to full-day-gain
   depth, so the simulator chose from ~17 of ~213 candidates a day, and
   that sliver was selected by how much the name gained *by the close*.
   Fixed by `plan/backfill_m1_full.py` (7.6% -> 100% coverage).
2. **The explicit pool cut.** `day_candidates(..., causal_pool=False)`
   sorted the day's candidates by `gain_pct` -- the **day-high** gain --
   and kept the top 16.
3. **Pool membership.** `gappers_novol_*.json` membership is
   `grouped-daily high / prev_close - 1 >= 10%`, and grouped-daily `h` is
   the **regular-session** high (verified again here: on 160 sampled
   symbol-days the gd high matches the 09:30-16:00 minute-bar high to
   0.0000% median, and the gd open matches the 09:30 open to 0.0000%).
   A name is in the file **iff it will print +10% later that day**, so
   every **premarket** entry made against that file was drawn from a set
   conditioned on the rest of the day. Fixed by `RS_CROSS`/`RS_DEFER`.
4. **Fills.** A stop or trail whose level was gapped through filled *at
   the level*, a price that never traded. Fixed by the gap-through /
   clamp / bad-print-peak-guard patch.
5. **NOT IN THE STANDING LIST, found here: the rvol filter.** The
   original pool (`penny_ax20_discover.py`) also required
   `full-day volume >= 5 x the trailing 50-session average`. That is a
   16:00 statistic. It was removed when `gappers_novol_*` was built for a
   different reason ("when paper trading, you do not know the volume of
   the whole day"), and every post-2026-08-07 row uses the novol pool --
   so the leak is already out of the numbers below, but it belongs on the
   ladder, because **C35's $1,163,538 and C34's $1,019,966 were measured
   on the rvol-filtered pool** and are therefore not comparable to
   anything after it.
6. **Also not in the standing list: a listing-age coverage cut.** The
   full-breadth backfill fetched the pool **with `hist_n >= 50`** only, so
   8,042 candidate symbol-days -- recent listings, exactly the names that
   print +100% sessions -- had no bars at all. This line fetched them
   (`plan/cp_fetch.py --job A`: 7,954 with bars, 88 empty, 0 failures) and
   they are in every causal universe measured here.

---

## Part 1. The waterfall: where $774,534 went

Every row is a real run that exists in `data/massive/rotation_results*.json`;
`plan/cp_waterfall.py` assembles them and then attributes the decisive
steps ticket by ticket from the saved ledgers. The ladder is historical and
therefore path-dependent -- read the deltas as "what removing this leak
cost **at that point in the ladder**", not as an orthogonal decomposition.

## Waterfall: the rotation champion, epoch by epoch

| step | config | total $ | traded days | tickets | $/ticket | neg months | hyg/rs/df/halal |
|---|---|---:|---:|---:|---:|---:|---|
| C37 as adopted | VOLD | +774,534 | 396 | - | +nan | 0/23 | 0/0/0/0 |
| C37H | C37H | +665,667 | 432 | - | +nan | 0/23 | 0/0/0/0 |
| C37S | C37S | +405,826 | 298 | - | +nan | 3/22 | 0/0/0/0 |
| C37E | C37E | +635,759 | 419 | - | +nan | 1/22 | 0/0/0/0 |
| C37F | C37F | -72,673 | 445 | - | +nan | 18/23 | 0/0/0/0 |
| C37F-hl | C37F | -76,705 | 445 | 2150 | -35.7 | 16/23 | 1/0/0/1 |
| C37F-fm | C37F | -121,234 | 445 | 2148 | -56.4 | 17/23 | 1/0/0/1 |
| C37F-rs | C37F | +28,352 | 445 | 2048 | +13.8 | 12/23 | 1/1/0/1 |
| C37F-df | C37F | -14,135 | 445 | 2038 | -6.9 | 10/23 | 1/1/1/1 |
| C37F-hf2 | C37F | -88,784 | 414 | 1602 | -55.4 | 17/22 | 1/1/1/1 |

## The steps, in dollars

| step | delta total $ | what was removed |
|---|---:|---|
| -> C37H | -108,867 | drop the hindsight top-16 sort (causal pool = every candidate WITH BARS); the biased CACHE is still underneath |
| -> C37S | -259,841 | live halal gate semantics (HALAL_STRICT) |
| -> C37E | +229,933 | + EDGAR filed-date cache so the strict gate can verify real quarterlies (still the biased cache) |
| -> C37F | -708,432 | FULL-COVERAGE minute cache (backfill_m1_full): the pool becomes every candidate/day (~213) instead of the ~17 with gain-selected bars |
| -> C37F-hl | -4,032 | + pool hygiene (test symbols, split/relist artifacts, non-equity) |
| -> C37F-fm | -44,529 | + honest fills: gap-through stops fill at the bar OPEN, every sell clamped into [Low, High], causal bad-print peak guard |
| -> C37F-rs | +149,586 | + regular-session eligibility (RS_CROSS): a name is armable only after an IN-SESSION +10% print, so no premarket entry can be made on membership the day had not yet proved |
| -> C37F-df | -42,487 | + deferred entry (RS_DEFER): the cross bar itself is not fillable, because its own high is what proved eligibility |
| -> C37F-hf2 | -74,649 | + the repaired halal gate (415 armable names, 2026-09-16 v2) |

## Companion: the same epochs with the exits removed (HOLD1 = buy the same pick, flatten at 15:00)

| config | total $ | tickets | $/ticket |
|---|---:|---:|---:|
| HOLD1-fm | -903 | 448 | -2.0 |
| HOLD1-df | -103,158 | 448 | -230.3 |
| HOLD1-hf2 | -75,474 | 415 | -181.9 |

## Ticket-level view of each epoch

| epoch | legs | total $ | premarket entries | their $ | RTH entries | their $ | top-10 legs' share of gross profit |
|---|---:|---:|---:|---:|---:|---:|---:|
| C37F-hl (biased fills) | 2173 | -76,705 | 695 | -78,380 | 1478 | +1,675 | 10% |
| C37F-fm (honest fills) | 2171 | -121,234 | 691 | -112,494 | 1480 | -8,740 | 10% |
| C37F-rs (RS eligibility) | 2058 | +28,352 | 0 | +0 | 2058 | +28,352 | 8% |
| C37F-df (deferred entry) | 2046 | -14,135 | 0 | +0 | 2046 | -14,135 | 9% |
| C37F-hf2 (halal v2) | 1607 | -88,784 | 0 | +0 | 1607 | -88,784 | 12% |

## What regular-session eligibility + deferred entry actually did to the ledger

- legs present ONLY in the leaky (premarket-armed) run: **677** name-days worth **$-147,202**
- legs present ONLY in the causal run: **645** name-days worth **$-54,206**
- name-days in both: **824**, leaky $+25,968 vs causal $+40,070

## The honest champion's biggest legs

| # | date | symbol | entry | exit | reason | $ |
|---:|---|---|---|---|---|---:|
| 1 | 2025-02-10 | BNAI | 09:35 | 10:10 | bearish bearish_engulfing | +12,865 |
| 2 | 2024-12-30 | BNGO | 13:20 | 13:37 | bearish bearish_engulfing | +3,280 |
| 3 | 2025-09-08 | AIRE | 09:31 | 09:54 | bearish bearish_engulfing | +2,959 |
| 4 | 2024-12-17 | RIME | 09:31 | 10:04 | bearish bearish_engulfing | +2,278 |
| 5 | 2026-07-16 | VEEE | 09:31 | 09:58 | bearish bearish_engulfing | +2,259 |
| 6 | 2025-03-20 | ELAB | 09:31 | 09:41 | bearish bearish_engulfing | +2,245 |
| 7 | 2025-09-03 | IPDN | 09:31 | 09:56 | stop +1.34 | +2,238 |
| 8 | 2025-12-01 | VEEE | 11:28 | 11:41 | bearish bearish_engulfing | +2,086 |
| -5 | 2025-03-27 | CPHI | 13:40 | 13:41 | stop -0.28 | -1,335 |
| -4 | 2024-12-20 | INUV | 09:50 | 11:33 | stop -0.41 | -1,372 |
| -3 | 2026-03-02 | MXC | 09:49 | 12:22 | stop -1.20 | -1,455 |
| -2 | 2025-06-23 | LINK | 10:05 | 10:28 | stop -0.41 | -1,570 |
| -1 | 2025-09-08 | HOUR | 10:15 | 10:30 | stop halt-reopen -0.86 | -2,044 |

total -88,784 over 1607 legs

### Reading the waterfall

The ladder in one sentence: **of the $774,534, about $708k was a
coverage artefact, about $109k was an explicit hindsight sort, the
remaining leaks roughly cancel, and what is left is a loss.**

**1. Coverage is 91% of the headline.** `C37E -> C37F` is
**-$708,432** and nothing else on the ladder is within an order of
magnitude of it. The champion was not choosing among the day's ~213
+10% names; it was choosing among the ~17 for which somebody had
already fetched bars, and the reason those 17 had bars is that they
finished the day up the most. Every ranking rule looked skilful against
that pool because every member of it was a winner. This is the single
fact that explains why a config that posted +$1,956 a traded day has
run at -$221 a day live.

**2. The hindsight pool sort is worth -$108,867** on its own
(`VOLD -> C37H`), i.e. 14% of the headline, and it is the leak that was
easiest to see in the code: `sorted(cs, key=lambda x: -x["gain_pct"])[:16]`
where `gain_pct` is the day-high gain.

**3. The premarket-survivorship leak cost the champion money, not made
it.** This is the result that inverts the story everyone expected, and
it is visible at the ticket level. In the leaky run (`C37F-fm`), the
**691 premarket entries earned -$112,494 (-$163/leg)** while the 1,480
regular-session entries earned **-$8,740 (-$6/leg)**. Forbidding
premarket entries (`RS_CROSS`) therefore *added* **+$149,586**. The
survivorship condition -- "this name will print +10% in the session" --
was real, and it still was not enough: buying a name at 07:00 because it
is up 10% premarket loses about 1% a ticket even when you are guaranteed
the day will confirm it. **A causal champion is not a worse version of
the leaky champion; on this axis it is a better one.**

**4. There was a fifth leak, one bar wide, worth -$42,487.** Under
`RS_CROSS` the champion could still fill *inside* the bar whose high had
just proved eligibility. That bar's high is the thing that armed the
name, so a fill inside it is hindsight. Deferring to the next bar
(`RS_DEFER`) costs **-$21 a ticket** -- which is, to within a couple of
dollars, the whole round-trip toll. One bar of look-ahead is worth the
entire cost of trading.

**5. The honest champion, priced three ways.** 1,607 legs, 414 traded
days, 22 months:

| toll | $/ticket | total | $/month |
|---|---:|---:|---:|
| none (what `C37F` actually charges -- see COST-REBASE) | **-$55.25** | -$88,784 | -$4,036 |
| flat 10 bps/side (the project ladder), applied to the ledger here | **-$82.53** | -$132,633 | **-$6,029** |
| measured per-fill (COST-REBASE, gapper fills 31.9 bps/side median) | **-$246.93** | -$404,012 | **-$18,037** |

**6. What IS causal in the champion, and what it is worth.** Two
components survive every honesty fix and both are real:

- **the exit machinery: +$126.5/ticket.** Same universe, same picks,
  same epoch, same toll: `C37F-hf2` -$82.53/tkt (flat10) against
  `HOLD1-hf2` (buy the identical pick, flatten at 15:00) -$209.00/tkt.
  The mechanism is visible in the ledger: the **bearish-pattern exit
  fires 1,050 times for +$276,087 (+$263 a leg)**, against **281 stops
  for -$279,956 (-$996 a leg)** and 271 window-close flattens for
  -$88,241 (-$326 a leg). The champion wins **68.6% of its legs** with a
  **median leg of +$54.6** and still loses, because the -8% stop's mean
  loss is nineteen times the median win. Its profit factor is **0.768**.
  And the wins are *not* a tail: the top 10 legs are only 12% of gross
  profit, the top 50 are 30%.
- **the ranking: +$32/ticket.** On COST-REBASE's matched 74-day
  measured-cost window, ranked `C37F` is **-$209.99/ticket** against a
  10-seed random-pick control at **-$242.23 +- 39.46** -- an edge of
  **+$32.24/ticket, z = +0.82, 80th percentile**. `HOLD1` shows the same
  sign and more of it: -$266.67 vs -$341.89 +- 54.29, **+$75.23/ticket,
  z = +1.39, 90th percentile**. Coil-plus-pressure is not noise. It is
  just an order of magnitude smaller than what this pool costs to trade.

**7. So the honest decomposition of the $774,534 is:**

| component | $ | what it was |
|---|---:|---|
| bar-coverage selection | **-$708,432** | hindsight, the dominant term |
| explicit full-day-gain pool cut | **-$108,867** | hindsight |
| fill model (levels that never traded) | -$44,529 | hindsight |
| one-bar cross look-ahead | -$42,487 | hindsight |
| pool hygiene | -$4,032 | housekeeping |
| premarket survivorship | **+$149,586** | a leak that COST money |
| halal gate repaired | -$74,649 | a constraint, not a leak |
| **genuine same-day ranking edge** | **+$32/ticket (+$75 with no exits)** | real, and 6.5x too small |
| **genuine exit edge** | **+$126/ticket** | real, and it only halves the loss |
| **what is left** | **-$82.53/ticket, -$6,029/month at flat 10 bps** | the honest champion |

---

## Part 2. What the champions actually captured, and whether it is detectable

### 2.1 The champion's P&L, cut by the day's full-day move

The user's intuition -- "their winning trades were mostly names up
+50-300% intraday" -- is testable directly: join the honest ledger to
each name's **full-day gain** (a 16:00 fact, used here only as a
LABEL, never as an input) and see where the money is.

| the day's full-day gain (HINDSIGHT) | legs | total $ | mean $/leg | win % |
|---|---:|---:|---:|---:|
| +10% to +20% | 807 | **-138,600** | **-171.7** | 61% |
| +20% to +35% | 548 | +15,949 | +29.1 | 78% |
| +35% to +50% | 109 | +24,392 | +223.8 | 83% |
| +50% to +100% | 112 | -5,557 | -49.6 | 68% |
| +100% to +300% | 31 | +15,031 | +484.9 | 68% |

(`C37F-hf2`, 1,607 legs. The pre-RS leaky ledger `C37F-fm` splits the
same way -- +10-20% is -$277,163 while every bucket above it is
positive.)

**The whole loss is one bucket.** Half the champion's tickets are on
names that end the day up only +10-20%, and those tickets are the entire
deficit. Every bucket above +20% is profitable. The user's reading of
what the champions captured is right, and it converts into an exact
research question: *can the +10-20% day be recognised at 09:35?*

### 2.2 The ceiling, before building anything

Before asking whether a model can do it, ask what a PERFECT one would be
worth. Keep only the champion's own legs whose day will finish above a
threshold -- a pure oracle veto, no re-ranking, no extra tickets:

`plan/cp_reprice.py` walks all 1,607 stored legs back to the minute
panel and charges each fill three ways (0 of 1,607 failed to match):

| oracle veto | legs kept | gross $/tkt | flat10 $/tkt | **measured** $/tkt | $/month flat10 | **$/month measured** |
|---|---:|---:|---:|---:|---:|---:|
| none (the honest champion) | 1,607 | -55.25 | -82.53 | **-258.65** | -6,029 | **-18,893** |
| day-gain >= +15% | 1,258 (78%) | +19.67 | -7.63 | -199.07 | -436 | -11,383 |
| day-gain >= +20% | 800 (50%) | +62.27 | +35.04 | -188.37 | +1,274 | -6,850 |
| **day-gain >= +25%** | 514 (32%) | +100.76 | **+73.58** | -192.39 | **+1,719** | -4,495 |
| day-gain >= +30% | 328 (20%) | +107.98 | +80.76 | -219.47 | +1,204 | -3,272 |
| day-gain >= +40% | 206 (13%) | +122.62 | +95.57 | -234.76 | +895 | -2,198 |
| day-gain >= +50% | 143 (9%) | +66.26 | +39.23 | -288.79 | +255 | -1,877 |

(The measured column is `plan/cp_cost.py`, an estimator built from the
1-MINUTE tape, and it independently reproduces COST-REBASE's 1-SECOND
number for the same ledger: -$258.65/ticket here against their
-$246.93, 4.7% apart and on the expensive side. Median measured toll on
these fills **36.7 bps a side**, mean 86.8, p90 221.3, above 10 bps on
**86%** of them, **$203.40 a round trip** on a $15,000 ticket.)

**Two ceilings, and they disagree about whether the idea is alive.**

- **At the project's flat 10 bps ladder, a perfect oracle is worth
  +$1,719/month** -- real money, and **4.4x short** of the target. It is
  worth pausing on that: it is not a statement about any model, it is a
  statement about the champion's machinery. Hand C37 a flawless answer
  to "will this name run today" and it still cannot pay $7,500 a month
  at the account's ticket size, because the veto also removes two thirds
  of the tickets and the survivors average +$74 against a $27 toll.
- **At the toll these names actually charge, the perfect oracle never
  turns positive at all.** Every row of the measured column is negative,
  the best of them **-$1,877/month**. The +10-20% bucket is not the
  problem; **the pool is.** A $15,000 ticket in a +10% microcap costs
  about $203 to round-trip, and the champion's gross edge -- even
  conditioned on a perfect forecast of the day type -- is $100 to $123.

That is the honest answer to "there must be a way": on **this
universe**, with **this ticket size**, there is not, and the binding
constraint is execution, not prediction. (The oracle's *re-ranking*
version -- filling all seven tickets a day from the oracle-approved set
instead of merely vetoing the champion's own picks -- is run as a
control row in 2.4; it raises ticket count, not $/ticket.)

### 2.3 The causal detector

Target: **`up30`** -- does this name's high reach +30% ABOVE ITS PRICE AT
THE DECISION MINUTE before 15:00? Measured strictly after the decision,
never an input. Base rates on the causal universe: **7.80% at 09:35**,
4.83% at 10:00, 0.33% at 14:00 (`up50` 3.64% / 2.09%, `up100` 1.06% /
0.61% at 09:35 / 10:00).

Inputs (`plan/cp_feat.py`, every one verified causal by `--verify`
against the slow path: 41,132 cell checks, worst relative difference
6.0e-08): premarket dollar volume and its ratio to the name's OWN prior
60-session median dollar volume, the gap at 07:00 and at the open,
premarket bar count and premarket high, session-so-far dollar volume and
relative volume, tape density, realised 1-minute volatility, distance
from VWAP, distance from the opening-range high, coil, 30- and 10-bar
signed-volume pressure, prior-session range and prior 60-session median
range, listing age, point-in-time shares outstanding and the implied
market cap and turnover.

Walk-forward LightGBM, 10 expanding folds (minimum 120 training
sessions), 3 seeds, scoring only rows strictly after its training block.

PLACEHOLDER_DETECT

PLACEHOLDER_MODEL

---

## Part 3. The causal live-scannable universe

### 3.1 The one structural fact that makes an honest replay possible

The live scanner's rule (`run_scan`: `Last > $2`, `%Change > 10%`) and
the pool file's rule (grouped-daily regular-session high >= +10% over
prev close) are not independent. **If a name's last regular-session
print at minute t is already >= +10%, then its regular-session HIGH is
>= +10% too, so it is necessarily in the pool file and necessarily has
bars.** Membership is implied by the very print that puts the name on
the scanner.

That means the set

    U(t) = { name : last printed close in [09:30, t] >= 1.10 x prev_close
                    and that close >= $2 }

is **complete and survivorship-free inside `data/massive/m1`** for every
regular-session minute t -- no fetch required, no inference, no
approximation. The same argument holds for the HIGH convention, which is
what `rotation_sim`'s `RS_CROSS` already implements. So the honest
regular-session universe was already available; what was missing was
only the *premarket* half, and the recognition that the RTH half is
exact. `plan/cp_lib.py` encodes both conventions and `cp_run --universe`
measures them.

PLACEHOLDER_UNIV

### 3.2 The premarket half, measured rather than assumed

A name whose premarket last crosses +10% and whose regular session never
does is **invisible to the pool file and has no bars anywhere on disk**.
That is the set every premarket entry in the C31..C37 family was
implicitly excluding. `plan/cp_fetch.py --job B` fetches the entire
scannable market (clean ticker, prev close >= $1.82 so a +10% cross
prints >= $2, prior-60-session median dollar volume >= $100k, traded
that day) on evenly spaced sample dates, so the missing set can be
counted and priced instead of argued about.

PLACEHOLDER_PREMKT

---

## Part 4. Keep what is causal, drop what is not

### How these rows were produced, and what they are not

The authoritative engine for anything labelled C31..C37 is
`plan/rotation_sim.py` + `day-trading.py`, and Part 1 is built entirely
from its stored runs. This line added thirteen ablation configs to its
`CFGS` (`_cp_cfgs()`, additions only, nothing existing touched) and
proved the wiring with an identity row: under
`HALAL_STRICT=1 PT_FILED=1 POOL_HYGIENE=1 RS_CROSS=1 RS_DEFER=1`,
**`CPID` reproduces `C37F` to the dollar** -- 25 sessions, -$6,649, 117
tickets, -$56.8/ticket, and an identical exit decomposition
(bearish 79 / +$20,073, stop 24 / -$24,385, window-close 14 / -$2,337).
Running that batch over the full 445-session window was not affordable
in this session's machine state (the engine costs ~65 s per session per
config with the halal gate live, and the box is running five other
research lines), so **the ablation below is measured in
`plan/cp_sim.py`, a documented re-implementation on the same tape**, and
its champion-mimic row is anchored against the real engine's number in
Part 5. The configs are registered and will reproduce on a quiet box.

`cp_sim` mimics: the live-scanner universe, the causal coil/pressure
rank, the symmetric 35%/20% 07:00-gap allowance, one position at a time,
$15,000 x 6 + $10,000, <= $100k/day, the 20%-of-trailing-5-minute-volume
size cap, the -8% stop, the pressure-modulated 20/10/40 trail, the
bearish-engulfing profit exit, rotation, the 14:30 window and the 15:00
flatten. It does **not** carry the other eight candlestick shapes, the
RSI/MACD exits, the halt logic or the wick guard; it therefore runs
slightly *worse* than the real engine, which is the safe direction.

Fills are the post-retraction convention throughout: a decision at
minute m first fills at the OPEN of the next PRINTED bar, sells clamp
into `[Low, High]`, and a gapped-through level fills at `min(level,
Open)`.

PLACEHOLDER_ABL

PLACEHOLDER_CTRL

---

## Part 5. Post-hoc halal

Halal was ignored in every decision above, per this line's instruction
(the gate is being repaired). Applied afterwards to the best causal
configuration:

PLACEHOLDER_HALAL

---

PLACEHOLDER_VERDICT
