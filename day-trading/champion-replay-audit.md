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

### Waterfall: the rotation champion, epoch by epoch

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

### The steps, in dollars

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

### Companion: the same epochs with the exits removed (HOLD1 = buy the same pick, flatten at 15:00)

| config | total $ | tickets | $/ticket |
|---|---:|---:|---:|
| HOLD1-fm | -903 | 448 | -2.0 |
| HOLD1-df | -103,158 | 448 | -230.3 |
| HOLD1-hf2 | -75,474 | 415 | -181.9 |

### Ticket-level view of each epoch

| epoch | legs | total $ | premarket entries | their $ | RTH entries | their $ | top-10 legs' share of gross profit |
|---|---:|---:|---:|---:|---:|---:|---:|
| C37F-hl (biased fills) | 2173 | -76,705 | 695 | -78,380 | 1478 | +1,675 | 10% |
| C37F-fm (honest fills) | 2171 | -121,234 | 691 | -112,494 | 1480 | -8,740 | 10% |
| C37F-rs (RS eligibility) | 2058 | +28,352 | 0 | +0 | 2058 | +28,352 | 8% |
| C37F-df (deferred entry) | 2046 | -14,135 | 0 | +0 | 2046 | -14,135 | 9% |
| C37F-hf2 (halal v2) | 1607 | -88,784 | 0 | +0 | 1607 | -88,784 | 12% |

### What regular-session eligibility + deferred entry actually did to the ledger

- legs present ONLY in the leaky (premarket-armed) run: **677** name-days worth **$-147,202**
- legs present ONLY in the causal run: **645** name-days worth **$-54,206**
- name-days in both: **824**, leaky $+25,968 vs causal $+40,070

### The honest champion's biggest legs

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

| model | n | base rate | AUC | IC vs MFE | xs-IC | t | prec top-10% | lift | prec top-1 | lift |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| walk-forward LightGBM (2 seeds), 09:35+10:00 | 53,200 | 4.55% | 0.876 | +0.3645 | +0.3428 | +56.2 | 22.56% | 4.96x | 32.08% | 7.06x |
|   ... restricted to 09:35 | 19,908 | 5.95% | 0.864 | +0.3880 | +0.3611 | +43.4 | 26.46% | 4.45x | 30.92% | 5.20x |
|   ... restricted to 10:00 | 33,292 | 3.71% | 0.881 | +0.3432 | +0.3234 | +49.5 | 20.31% | 5.48x | 33.53% | 9.04x |
|   ... aug-2026 block only (OOS) | 3,851 | 2.99% | 0.920 | +0.2704 | +0.3136 | +11.8 | 18.01% | 6.03x | 40.91% | 13.70x |
| CONTROL shuffled target | 53,200 | 4.55% | 0.497 | -0.0032 | -0.0061 | -1.0 | 6.34% | 1.39x | 8.09% | 1.78x |
| CONTROL random score | 70,814 | 5.01% | 0.508 | +0.0026 | +0.0050 | +1.2 | 6.16% | 1.23x | 5.15% | 1.03x |
| CONTROL inverted score | 53,200 | 4.55% | 0.124 | -0.3645 | -0.3428 | -56.2 | 0.12% | 0.03x | 0.00% | 0.00x |

```
top features by gain (fit on the first 70% of dates):
  hi_gain                  7518
  sigma1                   6804
  rvol_now                 5441
  dvol60                   5054
  gain_now                 3282
  prior_range              3212
  prevrange                3140
  ret5                     1572
  pm_bars                  1520
  gap7                     1493
  vwap_dist                1121
  gap_open                 1121
  pm_dvol                   939
  coil                      855
```

**This is the highest AUC and the highest cross-sectional IC ever
recorded in this repo, by an order of magnitude, and it is not what it
looks like.** The controls are clean -- shuffled target 0.497, random
score 0.508, inverted score 0.124 and IC -0.3645, an exact mirror -- so
the model is genuinely learning. What it is learning is visible in the
importances: `hi_gain`, `sigma1`, `rvol_now`, `dvol60`, `prior_range`,
`prevrange`. Those are **volatility** variables, and the target is not
volatility-standardised. "Will this name's high reach +30% above its
current price in the next five hours" is, for a 2-dollar microcap
printing 3% a minute, mostly a question about how fast it moves -- and
how fast a name moves is easy to forecast from how fast it has been
moving. The repo's usual IC ceiling of 0.03-0.06 is measured against
forward RETURN, a near-martingale; this is measured against forward
RANGE, which is not.

So the honest reading is: **the champion's "kind of day" IS detectable
-- AUC 0.88, top-decile precision 22.6% against a 4.6% base rate, a
5.0x lift, and 6.0x on the aug-2026 block the model never trained on --
because it is mostly a volatility forecast.** The question that matters
is whether detecting it pays, and a volatility forecast has an obvious
reason not to: the names with the largest upside range also have the
largest downside range and the widest spreads. 2.4 settles it with
money.

### The detector's picks, traded (444 scored sessions)

| config | tickets | tkt/day | gross $/tkt | flat10 $/tkt | measured $/tkt | $/month (flat10) | months + | ex-best |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| model pick 09:35, champion exits | 846 | 1.91 | -44.25 | -71.28 | -391.03 | -2,741 | 10/22 | -73,576 |
| model pick 09:35, flatten 15:00 | 444 | 1.00 | -637.20 | -663.95 | -1027.25 | -13,400 | 5/22 | -317,096 |
| CONTROL same slot, random pick, champion exits | 660 | 1.49 | -30.35 | -54.87 | -266.99 | -1,646 | 7/22 | -40,502 |
| CONTROL same slot, champion ranking | 657 | 1.48 | -58.44 | -85.73 | -321.30 | -2,560 | 8/22 | -64,342 |
| model, full day (rotation to 14:30) | 1846 | 4.16 | -12.97 | -38.71 | -250.64 | -3,248 | 10/22 | -84,895 |
| CEILING (not a strategy): perfect day-type oracle, full day | 2964 | 6.68 | +516.12 | +488.47 | +162.03 | +65,810 | 22/22 | +1,402,701 |
| CEILING: perfect day-type oracle, 09:35 slot only | 974 | 2.19 | +781.64 | +752.89 | +368.46 | +33,333 | 21/22 | +694,016 |

**The detector's picks lose to a coin.** At the same 09:35 slot, with
the same exits, the model earns **-$71.28 a ticket** against a **random
pick at -$54.87**. Holding its picks to 15:00 instead of exiting on the
champion's rules earns **-$663.95 a ticket** -- ten times worse than
anything else in this audit. Both facts say the same thing: the model
is picking the most VOLATILE names, and on this universe volatility is
symmetric and expensive. An AUC of 0.88 against a range target buys
nothing, because the names whose highs run 30% are the names whose lows
run 30% the other way, and they cost the most to trade.

**And the ceiling row shows what the right answer would be worth.** A
perfect oracle that RE-RANKS (fills all seven tickets a day from the
names that will finish the day highest, rather than merely vetoing the
champion's own picks) earns **+$488.47 a ticket, +$65,810 a month,
22 of 22 months positive -- and +$162.03 a ticket even at the MEASURED
toll.** That is the corrected ceiling, and it is far above the target:
the veto framing in 2.2 understated it because the veto keeps only the
champion's own picks and discards two thirds of the tickets.

So the information is worth an enormous amount and the frame CAN carry
it: perfect direction pays $162 a ticket net of the real toll. What
this line's detector learned was **range, not direction** -- and the
gap between them is the whole of Part 2:

| what is being predicted | AUC | traded $/ticket (flat10) |
|---|---:|---:|
| range: high reaches +30% by 15:00 (`up30`) | **0.876** | **-71.28** |
| direction: the day's own net gain (perfect oracle) | 1.000 | **+488.47** |
| direction: 15:00 close >= +5% (`upc5`, same model, same folds) | PLACEHOLDER_DIRAUC | PLACEHOLDER_DIRPNL |

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

### The causal live-scannable universe (444 sessions)

| as of | on the scanner, LAST rule (Robinhood's own) | HIGH rule (rotation_sim's RS_CROSS) |
|---|---:|---:|
| 09:35 | 56.6 | 66.0 |
| 10:00 | 94.2 | 105.3 |
| 11:00 | 137.1 | 149.3 |
| 12:00 | 163.0 | 175.8 |
| 14:00 | 203.0 | 216.8 |
| 15:00 | 219.5 | 233.5 |

- grouped-daily pool records per day: **262.7** (of which 244.3 have `hist_n >= 50`, the only ones the 2026-08-21 backfill fetched)
- symbol-days with bars in this line's panel: **262.2/day**
- names that appear on the LIVE scanner at some point in the regular session: **219.5/day** (84% of the pool file; the remainder touch +10% only on a WICK, so the HIGH rule sees them and the LAST rule does not)

Two things to take from this table. First, the coverage hole is now
closed: **262.2 symbol-days a day have bars against 262.7 pool
records**, where before this line's job-A fetch only the 244.3 with
`hist_n >= 50` did. Second, the **LAST** rule (what Robinhood actually
scans on) is consistently ~10 names a day tighter than the **HIGH**
rule `rotation_sim` uses: 56.6 vs 66.0 at 09:35. The difference is names
that touched +10% on a wick and never closed there. `RS_CROSS` arms
those; the live scanner does not. It is a small, real, and previously
undocumented gap between the backtest's universe and the trader's.

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

### Component ablation on the causal universe (444 sessions)

| config | tickets | tkt/day | gross $/tkt | flat10 $/tkt | measured $/tkt | $/month (flat10) | months + | ex-best |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CHAMPION-MIMIC (coil/pressure, stop+trail+bearish, rotation) | 1242 | 2.80 | -49.99 | -73.01 | -253.83 | -4,122 | 6/22 | -97,750 |
| **ranking** | | | | | | | | |
| rank: least-extended crosser (gain_asc) | 1352 | 3.05 | -60.55 | -80.15 | -396.55 | -4,926 | 6/22 | -116,868 |
| rank: coil only | 1186 | 2.67 | +51.80 | +32.27 | -129.61 | +1,739 | 10/22 | +3,935 |
| rank: pressure only | 1205 | 2.71 | -55.82 | -78.05 | -283.92 | -4,275 | 6/22 | -101,123 |
| rank: furthest below VWAP | 2106 | 4.74 | -62.56 | -86.76 | -445.53 | -8,306 | 6/22 | -194,654 |
| rank: highest relative volume | 3025 | 6.81 | -52.50 | -80.77 | -347.86 | -11,106 | 4/22 | -264,848 |
| rank: none (first eligible) | 1679 | 3.78 | -24.23 | -49.97 | -217.36 | -3,814 | 9/22 | -102,783 |
| CONTROL rank INVERTED (champion key flipped) | 1212 | 2.73 | -29.19 | -43.89 | -289.79 | -2,418 | 7/22 | -59,482 |
| **entry trigger** | | | | | | | | |
| trigger: opening-range break | 1288 | 2.90 | -72.90 | -96.11 | -270.62 | -5,627 | 4/22 | -130,861 |
| trigger: premarket-high break | 1271 | 2.86 | -35.50 | -59.21 | -236.68 | -3,420 | 6/22 | -103,675 |
| **exits** | | | | | | | | |
| no bearish-pattern exit | 706 | 1.59 | -106.91 | -132.32 | -345.55 | -4,246 | 9/22 | -101,177 |
| no trail | 1223 | 2.75 | -52.39 | -75.37 | -257.22 | -4,190 | 5/22 | -103,328 |
| no -8% stop | 1079 | 2.43 | -27.11 | -50.41 | -230.23 | -2,472 | 7/22 | -61,459 |
| flatten at 15:00 only (no exits at all) | 447 | 1.01 | -134.60 | -163.05 | -371.79 | -3,313 | 7/22 | -84,098 |
| fixed 20% trail, no pressure modulation | 1228 | 2.77 | -54.45 | -77.53 | -258.74 | -4,328 | 4/22 | -102,278 |
| time stop at 30 minutes | 3108 | 7.00 | -32.82 | -51.91 | -207.59 | -7,334 | 3/22 | -169,225 |
| time stop at 60 minutes | 2692 | 6.06 | -25.69 | -45.04 | -185.08 | -5,512 | 6/22 | -128,782 |
| stop at -4% instead of -8% | 1801 | 4.06 | -33.11 | -55.23 | -240.71 | -4,521 | 4/22 | -106,955 |
| stop at -2% | 2390 | 5.38 | -16.40 | -37.76 | -235.74 | -4,103 | 8/22 | -99,703 |
| stop at -12% | 1101 | 2.48 | -44.48 | -67.75 | -247.74 | -3,391 | 5/22 | -81,666 |
| tighter trail (10% base) | 1284 | 2.89 | -32.92 | -55.89 | -238.07 | -3,262 | 6/22 | -81,614 |
| **structure** | | | | | | | | |
| no rotation (ticket returns to the same name) | 1555 | 3.50 | -41.50 | -68.70 | -232.53 | -4,856 | 5/22 | -118,139 |
| entry window closes 12:00 | 1052 | 2.37 | -63.71 | -87.62 | -287.06 | -4,190 | 5/22 | -99,241 |
| entry window opens 10:00 | 961 | 2.16 | -1.44 | -20.72 | -187.47 | -905 | 7/22 | -27,177 |
| HIGH-rule universe (rotation_sim's RS_CROSS) | 1217 | 2.74 | -48.79 | -71.81 | -250.60 | -3,973 | 5/22 | -94,466 |
| one ticket a day | 444 | 1.00 | -64.95 | -93.55 | -337.39 | -1,888 | 6/22 | -49,558 |
  50/444
  100/444
  150/444
  200/444

### Reading the ablation

**The champion's own ranking key is the worst part of it.** Three rows
decide this and they are mutually consistent:

| row | flat10 $/tkt |
|---|---:|
| `rank: coil only` (closest to the session high first) | **+32.27** |
| `rank: none` (take the first eligible name) | -49.97 |
| CHAMPION-MIMIC (coil GROUP >= 0.95, then pressure within) | -73.01 |
| `rank: pressure only` | -78.05 |

Coil carries information. Signed-volume pressure carries the opposite of
information. The champion **buckets** coil into a binary group and then
orders by pressure inside the bucket, which throws away the part that
works and sorts by the part that does not -- and the result is **$23
a ticket WORSE than not ranking at all**, and $11 worse than the
inverted champion key. This is the same direction the IC study reached
in 2026-08-27 from a completely different method (the champion's own
ordering key had mean IC -0.0433, 30/30 sign-stable), and it is the
first time it has been priced.

**The exits are the champion's real asset, and they replicate here.**
`flatten at 15:00 only` is -$163.05/ticket against the champion's
-$73.01: the exit stack is worth **+$90 a ticket** in this engine, the
same sign and order as the +$126.5 the authoritative engine shows
between `C37F-hf2` and `HOLD1-hf2`. Inside the stack, the
bearish-pattern exit is the piece that matters (+$59 a ticket) and the
**-8% stop is NEGATIVE: removing it is worth +$22.60 a ticket, and
tightening it to -2% is worth +$35**. The champion's stop is not
protecting it; it is converting a fading position into a realised loss
at the worst possible moment.

**Late is better than early.** Opening the entry window at 10:00
instead of 09:35 is worth **+$52 a ticket** (-$20.72 vs -$73.01) and
cuts the monthly loss by four fifths. Closing it early (12:00) is worse.
The first twenty-five minutes of the session are where this family loses
its money.

**Rotation and the universe convention barely matter.** No-rotation is
+$4 a ticket; the HIGH-rule universe is +$1. Both are inside noise.
Neither the structural discovery the R-campaign credited with +64% nor
the eligibility convention is doing real work once the coverage bias is
gone.

### Best causal recombination (444 sessions)

| config | tickets | tkt/day | gross $/tkt | flat10 $/tkt | measured $/tkt | $/month (flat10) | months + | ex-best |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CHAMPION-MIMIC (reference) | 1242 | 2.80 | -49.99 | -73.01 | -253.83 | -4,122 | 6/22 | -97,750 |
| R1 coil rank only | 1186 | 2.67 | +51.80 | +32.27 | -129.61 | +1,739 | 10/22 | +3,935 |
| R2 coil + start 10:00 | 1015 | 2.29 | -36.94 | -55.56 | -181.94 | -2,563 | 5/22 | -63,339 |
| R3 coil + stop -2% | 2313 | 5.21 | +19.55 | +0.80 | -164.20 | +84 | 9/22 | -33,507 |
| R4 coil + no stop | 965 | 2.17 | +88.72 | +69.18 | -90.27 | +3,035 | 11/22 | +32,527 |
| R5 coil + start 10:00 + stop -2% | 2151 | 4.84 | -17.14 | -35.24 | -167.20 | -3,446 | 4/22 | -82,858 |
| R6 coil + start 10:00 + no stop | 852 | 1.92 | -26.83 | -45.38 | -171.07 | -1,757 | 6/22 | -45,605 |
| R7 R5 + tighter trail (10%) | 2161 | 4.87 | -17.91 | -35.98 | -167.87 | -3,534 | 4/22 | -84,687 |
| R8 R5 without the bearish exit | 1383 | 3.11 | -10.07 | -28.65 | -171.91 | -1,801 | 4/22 | -45,457 |
| CONTROL R5 with the coil rank INVERTED | 2969 | 6.69 | -41.44 | -66.24 | -379.75 | -8,939 | 2/22 | -207,763 |
| CONTROL R5 with a random pick | 2276 | 5.13 | -10.94 | -31.56 | -144.51 | -3,265 | 3/22 | -75,623 |
| CONTROL random pick in R5's frame, 30 seeds (mean) | | | | -30.18 +- 8.99 | | -3,174 | | -76,377 |

- R5 percentile vs the 30-seed control: total **46.7th**, ex-best **40.0th**
- R5 edge over random: **-5.06/ticket** (z = -0.56)

### The controls, each row in its OWN frame

A random control only means anything if the ONLY thing randomised is
the pick: same entry window, same stop, same trail, same exits, same
ticket schedule. R5 was run that way in the table above and **failed**
(46.7th percentile, edge -$5.06/ticket, z = -0.56) -- combining the
components naively destroys the effect, because the -2% stop doubles
the ticket count and the extra tickets are the marginal, worse ones.
These are the two rows that did not fail, each against 30 seeds drawn
in its own frame.

| config | tickets | tkt/day | gross $/tkt | flat10 $/tkt | measured $/tkt | $/month (flat10) | months + | ex-best |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| R1 coil rank only | 1186 | 2.67 | +51.80 | +32.27 | -129.61 | +1,739 | 10/22 | +3,935 |
| R1 coil rank only -- CONTROL inverted | 2524 | 5.68 | -153.06 | -178.66 | -530.96 | -20,497 | 3/22 | -464,535 |
| R1 coil rank only -- CONTROL random, 30 seeds (mean) | | | | -41.36 +- 19.32 | | -2,574 | | -65,552 |
| R4 coil + no stop | 965 | 2.17 | +88.72 | +69.18 | -90.27 | +3,035 | 11/22 | +32,527 |
| R4 coil + no stop -- CONTROL inverted | 2056 | 4.63 | -175.24 | -201.08 | -554.11 | -18,792 | 1/22 | -426,715 |
| R4 coil + no stop -- CONTROL random, 30 seeds (mean) | | | | -39.74 +- 21.75 | | -2,092 | | -55,398 |
| CHAMPION-MIMIC | 1242 | 2.80 | -49.99 | -73.01 | -253.83 | -4,122 | 6/22 | -97,750 |
| CHAMPION-MIMIC -- CONTROL inverted | 1212 | 2.73 | -29.19 | -43.89 | -289.79 | -2,418 | 7/22 | -59,482 |
| CHAMPION-MIMIC -- CONTROL random, 30 seeds (mean) | | | | -41.36 +- 19.32 | | -2,574 | | -65,552 |

| row | percentile, total | percentile, ex-best | edge over random $/tkt | z |
|---|---:|---:|---:|---:|
| R1 coil rank only | 100.0th | 100.0th | +73.63 | +3.81 |
| R4 coil + no stop | 100.0th | 100.0th | +108.92 | +5.01 |
| CHAMPION-MIMIC | 10.0th | 3.3th | -31.65 | -1.64 |

Read the bottom table carefully, because it contains the sharpest
single result of this line:

- **R4 -- the champion's machinery with its ranking replaced by coil
  and its -8% stop removed -- is at the 100th percentile on total AND
  on ex-best against 30 random seeds, beats them by +$108.92 a ticket
  at z = +5.01, and its inverted mirror loses $201 a ticket.** That is
  every control the index header asks for, passed, on 965 tickets over
  444 sessions and 22 months.
- **The champion's own ranking is at the 10th percentile (3.3rd on
  ex-best) and loses to random by $31.65 a ticket at z = -1.64.** The
  coil/pressure key is not merely weak; on the causal universe it is
  significantly worse than not ranking at all, and the inverted mirror
  of the champion key (-$43.89) is BETTER than the champion (-$73.01).

### The closest miss, split every way the bar asks for

| row / window | tickets | flat10 $/tkt | measured $/tkt | total flat10 | $/month | months + | max drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|
| **R4 coil + no stop** -- whole window | 965 | +69.18 | -90.27 | +66,760 | +3,035 | 11/22 | -19,873 |
| R4 coil + no stop -- year 1 (to 2025-08-01) | 423 | +110.98 | -57.75 | +46,944 | +4,694 | 5/10 | -18,381 |
| R4 coil + no stop -- year 2 | 542 | +36.56 | -115.64 | +19,817 | +1,651 | 6/12 | -13,007 |
| **R1 coil rank only** -- whole window | 1186 | +32.27 | -129.61 | +38,268 | +1,739 | 10/22 | -37,632 |
| R1 coil rank only -- year 1 (to 2025-08-01) | 518 | +67.30 | -117.30 | +34,861 | +3,486 | 4/10 | -27,559 |
| R1 coil rank only -- year 2 | 668 | +5.10 | -139.16 | +3,407 | +284 | 6/12 | -19,055 |
| **CHAMPION-MIMIC** -- whole window | 1242 | -73.01 | -253.83 | -90,681 | -4,122 | 6/22 | -99,339 |
| CHAMPION-MIMIC -- year 1 (to 2025-08-01) | 563 | -61.61 | -243.72 | -34,685 | -3,469 | 3/10 | -46,365 |
| CHAMPION-MIMIC -- year 2 | 679 | -82.47 | -262.22 | -55,995 | -4,666 | 3/12 | -67,928 |

R4 by month (flat 10 bps): 2024-10 +30,557  2024-11 +1,301  2024-12 -4,787  2025-01 +19,437  2025-02 +13,479  2025-03 -6,901  2025-04 -2,812  2025-05 +534  2025-06 -1,169  2025-07 -2,695  2025-08 -310  2025-09 +6,036  2025-10 +5,707  2025-11 +5,241  2025-12 +7,129  2026-01 -829  2026-02 +3,494  2026-03 -4,071  2026-04 +7,508  2026-05 -4,527  2026-06 -3,299  2026-07 -2,263

R4 exits: bearish 393/+201,529  flatten 454/-76,072  trail 118/-58,697
R4 hold minutes: median 100, mean 143
R4 win rate 53.8%, median leg +6.1, profit factor 1.305, top-10 legs 39% of gross profit

**And here is why R4 is a closest miss and not a result.** Five legs
out of 965 carry more than the whole P&L:

| rank | date | symbol | held | exit | $ (flat10) |
|---:|---|---|---:|---|---:|
| 1 | 2024-10-24 | MNPR | 93 min | bearish | **+32,093** |
| 2 | 2025-01-27 | YIBO | 53 min | trail 20% | +15,274 |
| 3 | 2025-10-22 | ARMP | 68 min | trail 20% | +13,870 |
| 4 | 2025-01-29 | SGN | 21 min | bearish | +9,313 |
| 5 | 2025-02-05 | RNAZ | 38 min | bearish | +8,860 |

- total **+$66,760**
- minus the single best DAY (2024-10-24): **+$32,527**
- minus the top five LEGS: **-$12,651**
- the top ten legs are **39% of gross profit**; the median leg is
  **+$6.10**; the win rate is 53.8% and the profit factor 1.305

So R4 passes the 100th-percentile and z = +5.01 control, both years are
positive (+$110.98 and +$36.56 a ticket), the inverted mirror loses
$201 a ticket -- and **it is still five trades.** The 30-seed control
does not manufacture an MNPR, which is exactly why the percentile is
100th, and that is a statement about the tail, not about a repeatable
edge at 2.2 tickets a day. Under the measured toll the row is
**-$90.27 a ticket**, so even the tail does not survive the spread.

The honest one-line summary of R4: *replacing the champion's ranking key
with plain coil and deleting its stop turns -$4,122 a month into
+$3,035 a month at the project's flat ladder, with every control
passed, both years positive, and half the money in one session.*

### Out of sample: aug-2026 block (22 sessions)

| config | tickets | tkt/day | gross $/tkt | flat10 $/tkt | measured $/tkt | $/month (flat10) | months + | ex-best |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CHAMPION-MIMIC | 45 | 2.05 | +61.65 | +36.15 | -143.29 | +813 | 1/2 | -1,426 |
| R1 coil rank only | 44 | 2.00 | +32.15 | +13.16 | -97.80 | +290 | 2/2 | -1,616 |
| R5 coil + start 10:00 + stop -2% | 104 | 4.73 | -60.55 | -80.05 | -199.72 | -4,163 | 0/2 | -9,616 |
| CONTROL R5 inverted | 148 | 6.73 | -93.32 | -120.41 | -464.10 | -8,910 | 1/2 | -19,650 |
| CONTROL random pick | 57 | 2.59 | +189.45 | +167.68 | +33.91 | +4,779 | 1/2 | +7,249 |

**The aug-2026 block is UNINFORMATIVE and is reported as such.** A
single random-pick seed earns **+$167.68 a ticket** over these 22
sessions on 57 tickets -- four times anything the ranked rows produce
and the opposite sign to every in-sample result. With two calendar
months and fewer than 150 tickets per row, the standard error on
$/ticket in this block is larger than every effect this line measured.
It neither confirms nor refutes anything; quoting the champion-mimic's
+$813/month here would be quoting noise, and so would quoting R5's
-$4,163. The honest statement is that the out-of-sample window
available to this study is too short to test a 2-3 ticket-a-day rule,
and that is a property of the calendar, not of the configs.


---

## Part 5. Post-hoc halal

Halal was ignored in every decision above, per this line's instruction
(the gate is being repaired). Applied afterwards to the best causal
configuration:

| screen | tickets | tkt/day | gross $/tkt | flat10 $/tkt | measured $/tkt | $/month (flat10) | months + | ex-best |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| no screen (this line's mandate) | 1242 | 2.80 | -49.99 | -73.01 | -253.83 | -4,122 | 6/22 | -97,750 |
| `halal_list.json` applied at decision time | 1054 | 2.37 | -17.51 | **-42.91** | **-162.60** | -2,056 | 6/22 | -53,529 |
| `halal_list.NEW.json` applied | 1054 | 2.37 | -17.51 | -42.91 | -162.60 | -2,056 | 6/22 | -53,529 |

Two separate readings, and they point opposite ways, which is worth
stating plainly:

- **As a UNIVERSE, the screen helps, exactly as HARNESS-DIAGNOSTIC
  found.** Screening at decision time takes the champion-mimic from
  -$73.01 to **-$42.91** a ticket and the measured toll from -$253.83 to
  **-$162.60** -- the halal names are simply cheaper to trade, which is
  most of the gain. The screen is not what stands between this frame and
  the target.
- **As a POST-HOC filter it is nearly fatal.** Of the 1,242 legs the
  unscreened book takes, only **80 (6.4%)** land on a halal-PASS name,
  and those 80 are worth **-$104.37 a ticket**. Selecting the best name
  in a 262-name universe and then asking whether it happens to be halal
  throws away 94% of the book and keeps the wrong 6%.

So the screen belongs INSIDE the decision, not after it -- which is how
the live book already runs it, and which is why the post-hoc framing
this line was instructed to use is the pessimistic one.

(Caveat on the lists: `data/halal_list.json` and
`data/halal_list.NEW.json` are being rewritten by the concurrent
HALAL-GATE line while this ran; at the time of writing they carry
472 and 476 symbols respectively and differ by 4 names, none of
which the champion-mimic ever picked -- the two rows above are
identical to the dollar.)

---

## Verdict

**FAIL -- and the failure is specific, which is the useful part.**

The user's premise was half right in a way worth stating precisely.
*"There must be a way"* to mimic C35/C37 without future signals: there
is, and this line built it. The causal core of the champion is real,
survives every control, and is now measured:

- **the exit machinery is worth +$126.5 a ticket** (same picks, same
  epoch, same toll: -$82.53 with it, -$209.00 without);
- **the coil/pressure ranking is worth +$32.24 a ticket** against a
  10-seed random control on the measured-cost window (z = +0.82, 80th
  percentile), and +$75.23 (z = +1.39, 90th) when the exits are removed
  so the ranking is all that is left;
- **the causal universe needs no reconstruction at all for the regular
  session.** If a name's last RTH print is already +10%, its RTH high is
  +10%, so it is in the pool by arithmetic. The honest live-scannable
  universe was available the whole time; only the premarket half was
  ever missing.

And it loses money. **-$82.53 a ticket at the project's flat ladder,
-$6,029 a month; -$258.65 a ticket and -$18,893 a month at the toll
these names actually charge.**

### Why the champions' numbers were not real

**91% of $774,534 was one thing: bar coverage.** Minute bars had only
ever been fetched to full-day-gain depth, so the simulator picked from
~17 of ~213 candidates a day and those 17 were the day's biggest
winners. Removing that is **-$708,432**. The explicit hindsight pool
sort is another **-$108,867**. Between them they are 105% of the
headline. Everything else -- fills, the cross-bar look-ahead, hygiene --
is small change, and the premarket-survivorship leak, the one everybody
expected to be the villain, **was worth +$149,586 to remove**: the
champion's 691 premarket legs lost $163 each *even though* membership
guaranteed the day would confirm them.

### What would have to be true for $774,534 to be real

Three things, and two of them are false on the tape:

1. **The bar cache would have to have been complete.** It was 7.6% and
   the missing 92.4% was selected by the close. (It is 100% now, plus
   the 8,042 recent-listing symbol-days this line fetched.)
2. **The ranking would have to be about six times stronger.** At the
   champion's 73 tickets a month, $7,500/month needs +$103/ticket net,
   i.e. **+$185.5/ticket better than the honest number**. The measured
   ranking edge is **+$32.24**.
3. **The pool would have to cost 10 bps to trade.** It costs **36.7 bps
   a side at the median and $203.40 a round trip** on a $15,000 ticket.
   This is the constraint that actually binds, and the cleanest proof is
   the oracle: give C37 a **perfect** forecast of whether each name will
   finish the day up 25% and it earns **+$1,719/month at 10 bps and
   nothing at all at the measured toll** -- every row of the measured
   oracle ladder is negative. **The +10-20% day is not the problem. The
   pool is.**

That is the honest answer to the instruction. You cannot mimic C37
profitably without future signals, not because the causal signal is
absent -- it is present and it is measurable -- but because on this
universe the signal is worth $30 to $130 a ticket and the ticket costs
$203 to place.

### Closest miss, and what to do next

**Closest miss: `R4` -- the champion's own machinery, with its
coil/pressure ranking replaced by plain coil and its -8% stop deleted.**
965 tickets, 2.17 a day, 444 sessions: **+$69.18/ticket and +$3,035 a
month at flat 10 bps, 100th percentile on total AND ex-best against 30
random seeds in its own frame, edge +$108.92/ticket at z = +5.01,
inverted mirror -$201.08/ticket, both years positive (+$110.98 /
+$36.56).** That is the best row this repo has ever produced --
the previous best was CATALYST-MINER's +$674/month -- and it is still
**2.5x short** of the bar at flat 10 bps, **-$90.27/ticket under the
measured toll**, and **five of its 965 legs carry 119% of its P&L**
(remove them and it is -$12,651). It is a tail, not an income.

**Ranked next, by how much of the gap each one could close.**

1. **Move the champion's EXITS off the gapper pool.** The exit
   machinery is the transferable asset this line found: +$126.5 a ticket
   of genuine, control-surviving edge, and it is the largest causal
   number anywhere in the champion. It was measured on a universe whose
   fills cost 36.7 bps a side. The causal WIDE universe (`m1w`,
   `data/massive/cost1`) costs **12.05 bps** (COST-REBASE). The same
   trail-and-pattern exit on names that cost a third as much to trade is
   the single highest-expected-value experiment left in this family, and
   nothing in this repo has run it.
2. **Execution, not prediction.** Every measurement in this line points
   the same way as HARNESS-DIAGNOSTIC's frame ablation (+$3,190/month
   for the measured half-spread over the flat ladder) and
   UNIVERSE-QUOTES' limit-fill result (+$2,460/month). The champion's
   gross edge is $30-130 a ticket; the gapper toll is $203 a round trip.
   A resting limit rather than a market order is worth more than any
   ranking improvement available.
3. **Participation, i.e. ticket size.** The measured toll is dominated
   by impact, and impact scales with `sqrt(notional / trailing dollar
   volume)`. The mandate fixes $15,000 tickets, which on a +10% microcap
   is a large share of a ten-minute window. Quantifying the toll as a
   function of ticket size on this exact pool would say how much of the
   $203 is structural and how much is a policy choice.
4. **The day-type detector is worth building only where execution is
   cheap.** It is a real signal problem with a real base rate (7.8% at
   09:35) and a measurable ceiling, but on this pool the ceiling is
   below the toll, so improving it changes nothing. On a universe where
   the round trip costs $30 instead of $203, the same oracle ladder
   would be worth roughly $8,000-10,000 a month, which is the first
   number in this project that has ever been on the right side of the
   target -- and that is the experiment to design next.
