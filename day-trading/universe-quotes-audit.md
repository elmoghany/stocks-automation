# UNIVERSE+QUOTES (2026-09-16) — attack the two constraints the wide-net
# line measured: the starved halal universe, and the toll

**Mandate:** *"ATTACK THE TWO BINDING CONSTRAINTS the wide-net line measured.
(1) The halal universe is starved by COVERAGE, not by the rules — extend
point-in-time fundamentals to every liquid name and rebuild the causal wide
universe. (2) The toll — model LIMIT entries with REAL quotes instead of
next-bar-open market fills."* Read `widenet-audit.md` first; this study reuses
its table, its features, its cost ladder and its splits, and `plan/wn_*.py` and
`plan/rl2/` were imported, never modified (one exception, stated: a `--universe
DIR` argument added to `plan/rl2/backfill_m1w.py`, which the mandate authorised).

---

## Verdict, in one table

| | $/ticket | $/month | vs the $7,500 bar |
|---|---|---|---|
| wide-net headline (model, market fill, 1 ticket/day) | -3.35 | -70 | fails |
| random ranking, market fill, account-legal (this study) | -30.45 | -3,822 | |
| model, market fill, account-legal | -17.93 | -2,238 | |
| random ranking, **limit** fill, account-legal | -15.67 | -1,362 | |
| **model relabelled for the fill, limit fill, account-legal** | **+0.06** | **+7** | **fails by ~$7,500** |

**FAIL.** Both constraints were real and both were moved, by amounts that are
now measured rather than guessed:

* **Constraint 1 bought a 4.6× wider universe.** Halal-PASS names per day go
  **60.7 → 278.3**, symbol-days **27,209 → 124,687**, distinct symbols
  **191 → 599**, and 186 of the incumbent 191 survive inside it. The audit's
  diagnosis was *nearly* right and wrong in an important detail: the binding
  constraint is not `data/pt_halal` statement coverage, it is the **industry
  label**, which `HALAL_STRICT` refuses when empty.
* **Constraint 2 is worth exactly the entry-side fee and not one basis point
  more.** A limit entry improves an unconditional $15,000 ticket from
  **-$26.49 to about -$16**, and that entire gain is the ~10 bps of entry cost
  you stop paying. Posting *deeper* buys nothing: price improvement and adverse
  selection cancel to within a basis point or two at **every** rung of the
  ladder. The audit's own ranked idea #2 guessed the limit would move
  break-even from ρ ≈ 0.10 to ρ ≈ 0.02; measured, it moves the break-even IC
  from **0.150 to 0.126** at seven tickets a day.
* The two together take an account-legal strategy from **-$3,822/month to
  break-even**, which is a real $3,800/month of progress and still **$7,500
  short of the bar**.

---

## Part 0 — The mandate's premise about quotes is false on this account

The first finding of this line is an entitlement, not a result.

```
/v3/quotes/{ticker}                403 NOT_AUTHORIZED
/v3/trades/{ticker}                403 NOT_AUTHORIZED
/v2/last/nbbo/{ticker}             403 NOT_AUTHORIZED
/v2/last/trade/{ticker}            403 NOT_AUTHORIZED
/v2/ticks/stocks/nbbo/{t}/{date}   403 NOT_AUTHORIZED
/v2/aggs/ticker/{t}/range/1/second 200   10,096 rows for one RTH session
/v3/snapshot?ticker=               200
```

`{"status":"NOT_AUTHORIZED","message":"You are not entitled to this data.
Please upgrade your plan"}`. The paid Starter tier carries aggregates and
reference data; the tick feeds are a higher tier. Reproduce with
`python plan/uq_sec1.py --probe` (`plan/uq_out/entitlement_probe.json`).

**Why the fill question survives anyway.** A 1-second aggregate *is* the trade
tape, binned: its `l` is the minimum **trade price** in that second and its `n`
is the transaction count. The rule the mandate specifies —

> a limit-buy posted at the decision minute is filled iff a trade prints at or
> below the limit within N minutes

— is therefore answered **exactly** by `min(l)` over the seconds in the window.
No tick feed is required for it. 1-second bars go back past the first study
date (2024-10-22 returns 1,742 rows for AAOI).

What a 1-second bar cannot give is the **NBBO**, so the "real inside spread"
half of the mandate needed a different instrument (Part 5).

**The tape.** `data/massive/trades/{SYM}_{DATE}.json.gz`, 09:30–16:05 ET at
1-second resolution, adjusted, for **all 27,197 symbol-days of the incumbent
causal universe** — 0 failures, 0.61 GB, 122 minutes at 4 requests/second.
One call per symbol-day rather than one per decision minute: it is the same
bytes and one ninth of the calls, and `window()` still addresses it per minute.

`plan/uq_massive.py` carries the `/v3/quotes` and `/v3/trades` wrappers anyway
(reusing `shared/massive.py`'s key and global throttle by import, as the
mandate requires) so the day the tier changes, the NBBO half runs unmodified.

---

## Part 1 — Constraint 1: what is actually starving the universe

### 1.1 The funnel the wide-net audit read, re-measured

The audit read `4,575 liquid → 728 labelled → 61 halal-PASS` and attributed the
middle step to `data/pt_halal` coverage. Measured directly on the same caches,
over the 6,371 symbols in the union of the causal liquidity screen:

| | count |
|---|---|
| screen symbols (median $ volume ≥ $2M over the prior 60 days, median close ≥ $3) | 6,371 |
| … with a point-in-time statement file in `data/pt_halal` | **3,099** |
| … with a NON-EMPTY industry/sector label | **1,270** |

`penny_ax11b_massive.industry_clean` under `HALAL_STRICT=1` refuses an empty
label outright ("an unknown industry is not evidence of compliance"), and the
label has exactly two sources in the gate: `sector_raw` in
`data/backtest60/rules_ytd.json` (1,270 of the screen) and the `industry` field
of a `pt_halal` file (58 of the screen). **Statements were never the binding
step; the label was.** That is why `labelled` and `shares` are the *same*
number, 727.6, in the incumbent `plan/rl2/out/universe_stats.json`: the shares
backfill was itself run only on the labelled set.

### 1.2 What was done about it (`plan/uq_edgar.py`, `plan/uq_halal.py`)

Four stages, none of which edits a rule or a threshold:

1. **extract** — `plan/edgar_backfill.py`'s own extractor (called, not
   rewritten, so the corrected tier-precedence debt logic, the `miss` flags and
   the filed dates come along) run over the union of the screen and everything
   already extracted: **8,534 symbols → 4,445 with ≥1 complete filed quarter,
   41,113 quarters**, 2,489 with no CIK in `company_tickers.json` (ETFs, funds,
   recent listings), 679 foreign-filer-only, 921 domestic with no complete
   quarter.
2. **merge** — `edgar_backfill.cmd_merge()`, under a guard. The mandate says
   *append new symbols only, never modify existing files*, and `cmd_merge`
   rewrites every file it touches, so the directory is SHA-256'd before and
   after and any pre-existing file the merge changed is restored byte-for-byte.
   Result: **22 new `pt_halal` files created, 0 pre-existing files restored** —
   the merge is idempotent, as its docstring claims, and now that is verified
   rather than trusted (`plan/uq_out/merge_report.json`).
   *Only 22 new files, because `pt_halal` already covered 4,474 symbols.*
3. **shares** — the gate needs a point-in-time share count (`mcap = shares *
   prev_close`) and refuses without one. `plan/rl2/cache/shares` covers 1,127
   symbols — exactly the names that already had labels — and widening it
   through Polygon's dated reference endpoint would have cost ~136,000 API
   calls. `companyfacts.zip` already contains the answer: the **DEI cover-page
   share count with its filing date**. Read straight out of the same zip:
   **5,250 symbols, 184,100 filed share counts, zero API calls.** Availability
   is by **filed date + 1 day**, never by the as-of date — the identical rule
   `_filed_usable` applies to the statements.
4. **labels** — `data/sic_codes.json` was already on disk: EDGAR `submissions`
   SIC codes *and descriptions* for 11,134 tickers, 3,589 of them in the
   screen. A SIC description ("State Commercial Banks", "Malt Beverages",
   "Services-Prepackaged Software") is the same *kind* of object as
   `sector_raw` — a present-day business-activity label for a classification
   that essentially never moves — so it is injected **in memory** as
   `sector_raw` for symbols whose label would otherwise be empty. Symbols that
   already have a label keep it, so **every name in the incumbent universe is
   decided by exactly the label that decided it before.**

This is the same injection point `plan/rl2/halal2.py` already uses for shares:
the module is loaded, and a DATA source it reads is replaced. No rule is
edited, no threshold moves, no file on disk is rewritten. `m.PT` is also
swapped for an in-memory mirror of `data/pt_halal` (19 MB) and `m.json` for a
memoising `loads`, because the widened screen asks the gate ~2 million
questions and each one was re-reading and re-parsing a 4 KB file.

### 1.3 The gate is made STRICTER where the new label is weaker

A SIC description is a *weaker* haram label than a vendor sector string in
exactly the places the doctrine cares about: SIC 3721 reads "Aircraft", not
"Aerospace & Defense"; SIC 7812 reads "Services-Motion Picture & Video Tape
Production", not "Entertainment". So a supplementary SIC-group screen
(`uq_halal.haram_sic_fail`) hard-fails the ordnance / aircraft / guided-missile,
motion-picture, amusement-and-gambling, tobacco and alcohol groups, plus the
eating-drinking and lodging groups the live doctrine resolves to
CANNOT-VERIFY (= not tradeable). Each range is annotated with the doctrine word
it stands in for. **It can only refuse more than the gate would.**

Its bite, measured: it removes **168 of the 6,371** screen symbols, and it
removes **exactly 5** names from the incumbent 191-symbol universe —
**BJRI** (BJ's Restaurants), **BROS** (Dutch Bros), **FUBO** (fuboTV), **OSW**
(OneSpaWorld), **TH** (Target Hospitality): eating places, motion
picture/streaming and lodging. It bites only where it should.

### 1.4 The result

| per day, mean over 448 dates | before | after |
|---|---|---|
| screen (liquidity only) | 4,574.8 | 4,574.8 |
| industry label PASS | 727.6 | **2,596.8** |
| … and SIC 6xxx sector screen PASS | 727.6 | 2,215.9 |
| … and the supplementary HARAM-SIC screen | — | 2,096.9 |
| … with a point-in-time share count | 727.6 | 1,992.6 |
| … with a point-in-time statement file | 641.7 | 1,759.7 |
| **halal-PASS point-in-time** | **60.7** | **278.3** |

| | before | after |
|---|---|---|
| PASS/day min … max | 30 … 91 | **183 … 328** |
| total symbol-days | 27,209 | **124,687** |
| distinct symbols | 191 | **599** |
| of the incumbent 191, kept | — | **186** |

Share resolution over the whole rebuild: 636,868 from the existing Polygon
caches (exact or nearest-earlier), **1,148,516 from EDGAR cover pages**, 93,458
misses (refused). So EDGAR carries the new names and the old caches still carry
the old ones.

**Honesty check on the substituted share count.** EDGAR cover-page shares vs
the Polygon `weighted_shares_outstanding` already cached, on the 25,163
overlapping (symbol, date) pairs: median ratio **1.000**, p25 = p75 = 1.000,
**80.3% within ±5%**, 83.3% within ±10%, 92.0% within a factor of 2. The tails
(p1 = 0.073, p99 = 13.7) are splits and multi-class structures. Since EDGAR is
only the *third* precedence tier, none of this touches the incumbent universe.

---

## Part 2 — Constraint 2: the honest limit-fill engine

### 2.1 The fill rule, stated before it was tested

At decision instant **t0** — the start of minute *m+1*, the same instant the
wide-net table fills at — post a buy limit at

    L = mark(m) * (1 - k/10000)

`mark(m)` is the last printed close at or before minute *m*. The order **fills**
iff some 1-second bar in (t0, t0 + N·60 s] has `l ≤ L`.

**The fill PRICE is `min(L, the open of the filling second)`**, not `L`:

* the filling second **opened above L** → the price came down to a resting
  order → we get **L**;
* the filling second **opened at or below L** → the market was already there
  when we posted, the order was marketable on arrival → we get the **market**.

*This is the one bug this study introduced and the number that exposed it.* The
first cut filled at `L` unconditionally. Because `mark(m)` is the last printed
close and can be minutes stale on a thin name, that charged the stale price for
an order that was marketable on arrival, and the **price-improvement column
went NEGATIVE at a zero offset (-4.3 bps)** — arithmetically impossible for a
real limit order. Fixed; the unconditional offset-0 / 1-minute ticket moved from
-$17.69 to -$6.73 per filled ticket on the sample that found it. Recorded here
rather than patched away.

Unfilled ⇒ **no trade, $0, and the ticket is spent** — the same convention a
non-printing minute *m+1* gets in the baseline table.

**Exit leg:** unchanged in shape (the open of the first printed minute at or
after fill + H, or the forced-flatten price), but the clock starts at the
**fill** minute, so a limit that fills three minutes late holds three minutes
later. Exit cost is a parameter, default the incumbent 10 bps.

### 2.2 The identity gate

Before any limit number was believed, `plan/uq_fills.py --stage selftest`
recomputed the **baseline** ticket (market fill at the open of *m+1*, 10 bps a
side, 20%-of-trailing-volume cap) from the raw day and feature caches and
compared it to `data/massive/wn/table.npz`:

> **96,780 ticket recomputations over 40 random days × 5 horizons —
> 0 mismatches, worst |difference| $0.0000.**

It earned its keep on the way: it exposed a real convention, that `wn_table.py`
applies the $500 notional floor to the `printed`/`ok` **flags** but leaves
`pnl` = notional × (1+cf) × tgt untouched, and `wn_lib.mask()` gates candidates
on `printed_m` alone — so the wide-net study **did** book sub-$500 tickets at
their true size. Reproducing that exactly is what makes this an identity gate
and not an approximation.

### 2.3 The poison test, and what the fill rule is allowed to see

Stated before the test so it can be scored against rather than around:

* `mark(m)` and `volcap(m)` — the only inputs to the posted order — and the 32
  features and the candidate gate `printed_m` are functions of 1-minute bars
  with index ≤ *m* and must be **bit-identical** when every bar after *m* is
  garbage;
* **whether** the order fills is decided by 1-second prints with timestamp
  > t0. That is the tape answering an order that was already posted. It is the
  one thing the pipeline may read from after t0, so the test asserts the fill
  outcome **moves** when those prints are garbaged and **does not move** when
  prints *before* t0 are garbaged.

`plan/uq_poison.py`, 8 days × 4 cut minutes (09:35 / 10:30 / 13:00 / 15:00):

| check | result |
|---|---|
| feature/gate/mark/volcap arrays identical under post-*m* garbage | **128 checks, 0 mismatches** |
| the POSTED ORDER — limit price and ticket notional at 3 offsets | **192 checks, 0 mismatches** |
| fill outcome **moves** when post-t0 prints are garbaged | 887 of 1,588 |
| fill outcome **unchanged** when pre-t0 prints are garbaged | **1,588 checks, 0 leaks** |

Worth noting in passing: the limit ticket's **size** is causal where the market
ticket's was not. The baseline sizes on `min($15,000, volcap × open(m+1))`,
which reads minute *m+1* — the fill. The limit ticket sizes on
`min($15,000, volcap × L)`, which reads nothing after *m*.

---

## Part 3 — What the limit entry is actually worth

### 3.1 The unconditional ladder — the central table of this study

448 days, 30,000 sampled causally-eligible $15,000 tickets, nine regular-session
decision times, 30-minute hold, exit at the incumbent 10 bps.

**Market fill at the open of minute m+1: -$26.49/ticket.**
**Gross forward return of all eligible names, no costs at all: -1.7 bps.**

| offset (bps) | wait | fill rate | $/tkt (all attempts) | **$/tkt (filled)** | price improvement (bps) | gross ret of the SAME names under a market fill (bps) | cap binds |
|---|---|---|---|---|---|---|---|
| 0 | 1m | 0.642 | -10.20 | **-15.89** | +4.0 | -4.7 | 0.117 |
| 0 | 5m | 0.843 | -12.38 | -14.69 | +6.0 | -6.5 | 0.158 |
| 5 | 1m | 0.470 | -7.95 | **-16.91** | +7.5 | -9.0 | 0.112 |
| 10 | 1m | 0.361 | -5.91 | **-16.39** | +10.9 | -12.1 | 0.116 |
| 15 | 1m | 0.282 | -4.66 | -16.55 | +14.6 | -15.8 | 0.120 |
| 20 | 1m | 0.224 | -4.07 | **-18.20** | +18.3 | -20.4 | 0.122 |
| 30 | 1m | 0.148 | -2.33 | **-15.70** | +26.0 | -25.8 | 0.128 |
| 50 | 1m | 0.073 | -1.51 | -20.61 | +41.6 | -44.2 | 0.135 |
| at the estimated bid | 1m | 0.445 | -7.04 | -15.82 | — | — | — |

Read the last two columns together. **The price improvement and the adverse
selection cancel at every single rung, to within a basis point or two:**
+4.0/-4.7, +7.5/-9.0, +10.9/-12.1, +18.3/-20.4, +26.0/-25.8, +41.6/-44.2. The
names that come down to a deeper limit are, in exactly equal measure, the names
that were going to keep going down. `$/ticket-filled` is therefore **flat at
about -$15 to -$18 down the whole ladder**.

**So the limit entry is worth precisely one thing: the ~10 bps of entry-side
cost you stop paying.** -$26.49 market → about -$16 limit. Everything else the
ladder appears to offer is an illusion created by looking at `$/ticket over all
attempts`, which flatters a low fill rate by counting the attempts you did not
take as $0.

### 3.2 It is not a queue-position artefact

Requiring a **full cent through** the limit before the fill is believed (i.e.
the book at L had to be cleared first, so we were not at the front of the
queue):

| offset | wait | fill rate (touch → through) | $/tkt filled (touch → through) |
|---|---|---|---|
| 0 | 1m | 0.642 → **0.512** | -15.89 → **-15.00** |
| 5 | 1m | 0.470 → 0.393 | -16.91 → -15.49 |
| 10 | 1m | 0.361 → 0.301 | -16.39 → -15.01 |

Fill rates fall by a fifth; the economics do not move. The conclusion is robust
to the single most optimistic assumption in any limit backtest.

### 3.3 The 20%-of-volume cap, Massive vs Robinhood

The wide-net audit measured Massive's consolidated volume at ~2× Robinhood's on
identical bars with identical prices. Halving the cap (the conservative
Robinhood-visible tape):

| cap | cap binds on filled tickets | $/tkt filled, offset 0 / 1m |
|---|---|---|
| 20% of Massive volume | 11.7 % | -15.89 |
| **20% of Robinhood-visible volume (= 10% of Massive)** | **20.5 %** | -15.02 |

The cap binds on roughly **twice as many tickets** and the per-ticket economics
do not move (marginally *better*, because the binding cases get smaller
tickets). Same conclusion as the wide-net audit: the volume gap costs **size**,
not edge — and since everything here is negative, the direction is
conservative.

---

## Part 4 — The strategy, under account-legal rules

`plan/uq_strat.py` walks each day forward in time under the cash-account rules
that the wide-net audit's only >$7k/month row broke: **one position at a time**,
**≤ 7 tickets a day**, $15,000 a ticket, $100,000 of same-day notional. At each
regular-session slot, if flat, post limits on the top `post_k` names by the
model score; whichever is hit first becomes the position and the rest are
cancelled; the account is busy until that position exits.

### 4.1 Configuration chosen on TRAIN, carried to OOS once

`plan/wn_model.py`'s own walk-forward only scores the held-out year, so a
configuration cannot be chosen on it without choosing on the answer. The same
`wn_model.fit` was therefore refitted month by month **inside the train
window** (2025-01…2025-07, each month fitted only on train rows before it) and
the 30-configuration grid was scored there, each against 6 random-ranking
controls (`plan/uq_out/strat_select_h30.json`).

The train grid produced a clean and uncomfortable result:

| | tickets | $/tkt | random control | edge |
|---|---|---|---|---|
| **market** entry | 666 (4.62/day) | -22.20 | -26.18 | **+3.98** |
| best limit (0 bps, 3 min, k=3) | 823 (5.71/day) | -11.59 | -9.60 | **-1.99** |
| worst limit (30 bps, 1 min, k=3) | 320 | -24.97 | -0.80 | -24.16 |

**All thirty limit configurations have a NEGATIVE edge over a random ranking,
while the market configuration has a positive one.** The limit roughly halves
the toll for everybody — the random control improves from -$26.18 to -$9.60 —
and what the fill condition destroys is the *ranking's* contribution.

### 4.2 The held-out year, first OOS read

Train's own choice (30 bps / 3 min / post 1), 251 days, 2025-08-01…2026-07-31:

| | tickets (per day) | $/ticket | $/month | months + | maxDD | percentile vs its own 30-seed random |
|---|---|---|---|---|---|---|
| model, **limit** | 674 (2.69) | **-4.50** | **-254** | 7/12 | -11,138 | 80 |
| model, market | 1,500 (5.98) | -13.26 | -1,664 | 3/12 | -22,013 | 100 |
| inverted, limit | 805 | -37.78 | -2,544 | 2/12 | | |
| inverted, market | 1,500 | -37.01 | -4,644 | 1/12 | | |
| shuffled-label model, limit | 571 | **+8.94** | +427 | 8/12 | -6,312 | |
| shuffled-label model, market | 1,500 | -24.23 | -3,041 | 2/12 | | |
| random ×30, limit | 2.08/day | -14.02 ± 10.81 | -610 ± 468 | | | |
| random ×30, market | 5.98/day | -30.45 ± 4.05 | -3,822 | | | |

Two things to take from this table and one warning.

1. **A random ranking gains $16.43/ticket from the limit entry alone**
   (-$30.45 → -$14.02). That is the model-free measurement of what attacking
   the toll is worth, and it matches Part 3.1's $11–16 to within the noise.
2. The wide-net model's edge **shrinks but survives** out of sample:
   +$17.2/ticket over random under a market fill (100th percentile), +$9.5 under
   a limit (80th percentile).
3. **Warning, recorded rather than buried: the shuffled-label control BEAT the
   real model** (+$8.94 vs -$4.50). It is 2.1 sd above the random mean on the
   same 30-seed distribution, i.e. a lucky draw from a control that is by
   construction another arbitrary ranking — but a harness in which the shuffled
   control outscores the model is a harness whose model is carrying no reliable
   ranking information at this configuration, which is exactly what the train
   grid said.

### 4.3 Rank for the FILL, not for the market (`plan/uq_label.py`, `uq_relabel.py`)

The diagnosis in 4.1/4.2 is not mysterious: the wide-net model was fitted on the
P&L of a ticket that *always* fills at the next bar's open, and a limit only
fills when the price comes down to it. The ranking is being applied to a
conditional population it never saw.

So the **label** was changed and nothing else. For all **194,010** causally
eligible rows, `y` = the realized net dollar P&L of a $15,000 **limit** ticket
at 10 bps / 1 minute, **$0 when it did not fill** (fill rate 0.356 overall,
mean -$4.92/attempt, -$13.80/filled). The same `wn_model.fit` — same 32 causal
features, same params, same early stopping, same monthly walk-forward — was
refitted on it. `post_k` was chosen on the train window (k=3: -$3.00/tkt,
**edge +$4.61** over random, where the un-relabelled model's best train edge was
-$1.45) and carried to the held-out year **once**:

| OOS, 251 days, offset 10 bps / 1 min / post 3, ≤7 tickets/day, one position at a time | tickets (per day) | $/ticket | $/month | months + |
|---|---|---|---|---|
| **relabelled model, limit** | **1,210 (4.82)** | **+0.06** | **+7** | **8/12** |
| relabelled model, market | 1,492 (5.94) | -17.93 | -2,238 | 3/12 |
| inverted, limit | 1,316 (5.24) | -21.61 | -2,380 | 2/12 |
| random ×30, limit | | -15.67 ± 6.71 | -1,362 ± 582 | |

**Edge over random: +$15.73/ticket. Percentile vs 30 random seeds: 100.
Inverted loses. Months positive: 8 of 12.**

This is the honest centre of the study. Relabelling recovers — and more than
doubles — the edge the fill condition had destroyed, the controls all point the
right way, and the strategy lands on **break-even**: +$0.06 a ticket,
+$7 a month, against a bar of $7,500.

---

## Part 5 — The real spread vs the 10 bps assumption

The NBBO is not entitled (Part 0), so the inside spread was measured four ways
on the tape that *is* entitled, over 2,160 decision points on 30 days
(`plan/uq_out/spread_report.json`) and again over 30,000 rows on all 448 days:

| method | where computed | median (bps) | mean | p75 | p90 |
|---|---|---|---|---|---|
| Corwin–Schultz (2012) high-low | 1-minute bars, 30 min ending at *m* | **2.01** | 5.59 | 6.45 | 15.0 |
| Abdi–Ranaldo (2017) close-high-low | 1-minute bars | **5.57** | 13.11 | 16.47 | 37.01 |
| Abdi–Ranaldo | 1-second bars, 5 min ending at t0 | 1.37 | 4.41 | 5.08 | 12.04 |
| observed 1-second high-low range, n ≥ 5 | 1-second bars | 1.74 | 5.92 | 6.08 | 16.53 |
| observed 1-second high-low range, n ≥ 10 | 1-second bars | **4.22** | 9.40 | 10.14 | 24.88 |
| Roll (1984) serial covariance | 1-minute bars | 18.59 | 32.80 | 38.57 | 74.34 |

**The inside spread on this universe is ~2–6 bps at the median**, i.e. a
half-spread of **1–3 bps against an assumed 10 bps per side**. The incumbent
cost ladder is roughly **2–5× conservative**, which means the wide-net audit's
$30 round-trip toll on a $15,000 ticket is closer to **$6–$18** in reality.

Two honesty notes, because this number is load-bearing and it would be easy to
make it say more than it does.

* **The observed 1-second range does not plateau.** Median range by minimum
  transaction count: 0.0 (n≥2), 1.74 (n≥5), 4.22 (n≥10), 7.11 (n≥20), 13.65
  (n≥50) bps. Busier seconds carry real drift as well as bid-ask bounce, so the
  observation is bracketed by the spread from below and spread+drift from
  above; it does not converge on the spread. Reported rather than smoothed.
* **The live-book validation could not be done.** A Robinhood
  `get_equity_quotes` pull on 20 universe names was taken, but the market was
  closed (19:07 ET) and after-hours books are not representative — AAOI
  98.52/98.78 = 26 bps, XMTR 93.15/97.81. It is recorded as attempted and
  unusable, not as evidence.

**Consequence, and why the headline was NOT re-priced at the measured spread.**
Dropping from 10 to 3 bps a side would add roughly $19 a ticket and would move
the relabelled OOS strategy from +$7/month to roughly +$1,100/month — still
$6,400 short, and it would do so by *loosening* a cost assumption on the
strength of an estimator. Every headline in this document therefore stays on
the incumbent 10 bps ladder, and the spread measurement is reported as a
sensitivity: the one direction the incumbent numbers are too pessimistic.

---

## Part 6 — The break-even information coefficient, re-measured under limit fills

`plan/uq_need.py` runs `plan/wn_need.py`'s exact machinery — a synthetic score
`ρ·z(pnl) + √(1-ρ²)·noise`, buy the top-k per (day, slot), sweep ρ — on the
**limit-filled** cross-section, where a name whose limit did not fill
contributes $0. It reproduces wn_need on the market leg to three decimals
(0.320 and 0.150), which is the cross-check that the two are comparable.

| configuration | ρ needed for $7,500/month, market fill | ρ needed, **limit fill** |
|---|---|---|
| 1 ticket a day, any of 9 RTH slots | 0.320 | **0.284** |
| 7 tickets a day, any of 9 RTH slots | 0.150 | **0.126** |
| 1 ticket per slot (9/day) | 0.176 | 0.153 |
| 7 tickets per slot | 0.131 | 0.059 |

And the curve itself, $/month, one ticket per slot:

| ρ | market | limit |
|---|---|---|
| 0.00 | -4,875 | **-889** |
| 0.02 | -3,586 | +123 |
| 0.05 | -1,638 | +1,614 |
| 0.10 | +1,741 | +4,308 |
| 0.20 | +9,585 | +11,192 |
| 0.50 | +41,750 | +42,682 |
| **1.00** | **+79,218** | **+70,798** |

**The limit helps at low ρ and HURTS at high ρ**, and the crossover is around
ρ ≈ 0.4. That is the whole story in one line: an unfilled attempt books $0, so
the better your forecast the more it costs you to miss the winners. The wide-net
audit's ranked idea #2 — *"a limit-order entry changes the break-even from
ρ ≈ 0.10 to ρ ≈ 0.02, inside what the walk-forward model already
demonstrates"* — is **wrong, and now measured to be wrong**: it moves the
break-even by **16%**, from 0.150 to 0.126, and the achieved ρ is still 0.033.
The remaining gap is a factor of **3.8**.

---

## Part 7 — The honesty battery

| check | result |
|---|---|
| **identity gate** — baseline tickets recomputed from raw caches vs `table.npz` | **96,780 checks, 0 mismatches**, worst $0.0000 |
| **poison, features/gate/mark/volcap** | **128 array checks, 0 mismatches** |
| **poison, the posted order** (limit price + notional, 3 offsets) | **192 checks, 0 mismatches** |
| **poison, pre-t0 prints** (the fill must not see them) | **1,588 checks, 0 leaks** |
| **poison, post-t0 prints** (the fill must see them) | 887 of 1,588 outcomes moved |
| **inverted score** | loses under both fills and both models (-$21.61 to -$37.78/tkt) |
| **shuffled labels**, wide-net model | +$8.94/tkt — **beat the real model**; recorded, see 4.2 |
| **shuffled labels**, relabelled model | see `plan/uq_out/relabel_shuffled.json` |
| **random, 30 seeds**, same slots, same fill rule, same account rules | -$15.67 ± 6.71 (limit), -$30.45 ± 4.05 (market) |
| **queue position** — require a full cent through the limit | fill rate -20%, $/tkt unchanged |
| **cost-ladder cross-check** | `uq_need`'s market leg reproduces `wn_need`'s ρ (0.320, 0.150) exactly |
| **merge guard** — `pt_halal` files that existed before | 4,474 hashed before and after, **0 modified** |
| **share substitution** | EDGAR vs Polygon, 25,163 pairs, median ratio 1.000, 80.3% within 5% |
| **a bug this study introduced, found and recorded** | filling every limit at `L` (Part 2.1) |

**OOS reads, counted.** The held-out year was read **three** times in this
study: (1) the wide-net model at the train-chosen limit configuration, (2) the
relabelled model at its train-chosen `post_k`, (3) the unconditional ladder,
which involves no selection at all. Everything else — the 30-configuration
grid, the `post_k` choice, the offset and wait choices — happened on the train
window.

---

## Part 8 — Conclusions

### What was established

1. **The halal universe's binding constraint was the industry LABEL, not
   statement coverage.** Feeding in EDGAR SIC descriptions (already on disk)
   and EDGAR cover-page share counts (free, filed-dated) widens it from **60.7
   to 278.3 halal-PASS names per day**, 191 → 599 distinct symbols, with 186 of
   the incumbent 191 kept and the 5 losses all correct.
2. **A limit entry is worth exactly the entry-side fee you stop paying**, about
   10 bps ≈ $11–16 on a $15,000 ticket. Price improvement and adverse selection
   cancel to within a basis point or two at **every** offset from 0 to 50 bps,
   so `$/ticket-filled` is flat at -$15…-$18 down the entire ladder.
3. **The wide-net model's ranking does not survive the fill condition** — all
   30 train configurations had a negative edge over random — but **relabelling
   the model on the limit-fill P&L restores it and more**: +$15.73/ticket over
   random out of sample, 100th percentile, inverted loses, 8/12 months positive.
4. **The two constraints together move an account-legal strategy from
   -$3,822/month to +$7/month.** That is ~$3,800/month of real progress and a
   $7,493/month miss.
5. **The break-even IC moves from 0.150 to 0.126, not from 0.10 to 0.02.** The
   limit helps at low ρ and hurts at high ρ; the crossover is ρ ≈ 0.4.
6. **The real inside spread is 2–6 bps, not 20**, so the incumbent cost ladder
   is 2–5× conservative — the one direction in which every number in the
   wide-net line and this one is too pessimistic.
7. **Massive vs Robinhood volume**: the 20% cap binds on 11.7% of filled limit
   tickets under Massive volume and **20.5%** under the conservative
   Robinhood-visible half, with no change in per-ticket economics.

### Closest miss

**The relabelled model, limit entry at 10 bps with a 1-minute rest, top-3
posted per slot, ≤7 tickets a day, one position at a time:
+$0.06/ticket over 1,210 held-out-year tickets, +$7/month, 8 of 12 months
positive, 100th percentile against 30 random seeds, inverted loses at
-$21.61.** It needs to be about **$74 a ticket better** to pass.

### Ranked next ideas

1. **The information set is still the binding constraint, and it is now
   measurable exactly.** Two constraints were attacked and both moved by the
   amount the arithmetic said they would; the gap that remains is entirely
   ρ = 0.033 against a break-even of 0.126. Nothing about fills, universe
   width or cost modelling closes a factor of 3.8. The next line should spend
   its whole budget on new *inputs* (order book, options flow), not on new
   estimators over price and volume.
2. **Re-baseline the cost ladder on the measured spread before anything else.**
   Every result in this project since the gapper campaigns has been priced at
   10 bps a side when the median half-spread is 1–3 bps. That is worth about
   $19 a ticket — bigger than any edge any model in this repo has demonstrated
   — and it is a *measurement*, not an assumption. It should be done carefully,
   with a live paper-trading check on realised fill prices, because it is the
   one change that makes every historical number look better.
3. **Rank for the fill, always.** Relabelling was worth +$15.73/ticket over
   random where the market-labelled model was worth +$9.5. Any future strategy
   with a conditional execution should be trained on the conditional label.
4. **Do not post deeper limits.** Part 3.1 is a complete answer: every basis
   point of improvement is given back. Post at or near the touch, where the
   fill rate is 64% instead of 15%.
5. **The widened universe is built and cached** (`plan/uq_out/universe/`,
   124,687 symbol-days, 599 symbols). Whatever line runs next should use it
   rather than the 61-name pool — it costs nothing now and E[max] over 278
   draws is mechanically better than over 61 at any fixed ρ.

### Files

| | |
|---|---|
| `plan/uq_edgar.py` | EDGAR extract/merge (guarded) + DEI filed-dated shares + labels |
| `plan/uq_halal.py` | the gate, unedited, with wider data + the HARAM-SIC screen |
| `plan/uq_universe.py` | the rebuilt causal wide universe (61 → 278/day) |
| `plan/uq_massive.py` | `/v3/quotes` + `/v3/trades` wrappers (403 on this tier) |
| `plan/uq_sec1.py` | the 1-second execution tape + the entitlement probe |
| `plan/uq_fills.py` | limit-fill engine, spread estimators, the identity gate |
| `plan/uq_econ.py` | the offset × wait ladder and its decomposition |
| `plan/uq_strat.py` | account-legal sequential simulator, train selection, controls |
| `plan/uq_label.py` | the limit-fill label for all 194,010 eligible rows |
| `plan/uq_relabel.py` | the same model refitted on that label |
| `plan/uq_need.py` | the break-even IC under limit fills |
| `plan/uq_poison.py` | the poison test for the limit pipeline |
| `plan/uq_wide.py` | the wide-net pipeline redirected onto the widened universe |
| `plan/uq_out/` | universes, labels, scores, reports, logs |
| `data/massive/trades/` | 27,197 symbol-days of 1-second tape (0.61 GB) |
