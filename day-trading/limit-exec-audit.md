# LIMIT-EXEC (2026-09-17) — end-to-end limit execution: can execution alone move the frame's baseline from −$28/ticket to ≈ $0?

**Mandate.** *HARNESS-DIAGNOSTIC control 5 found the market-order / immediacy
assumption to be the largest lever in the frame (+$3,190/month on the measured
half-spread). UNIVERSE-QUOTES modelled the ENTRY side only and found that a
limit entry is worth exactly the entry-side fee and not one bp more — price
improvement and adverse selection cancel. COST-REBASE found three wide-universe
rankers were partly selecting names the flat toll under-charged. Build an
END-TO-END limit execution policy (limit entries AND limit exits, sized to the
book, causal cancel/replace) on the entitled 1-second tape; measure whether it
moves the zero-information baseline from −$28.6 toward $0, so that the small
demonstrated skill (+$9…+$26/ticket over random) becomes net positive; apply it
to the random policy (30 seeds), WIDE-NET's model (rank-for-the-fill refit),
CLOSE-MOMENTUM's REV 15:30 composite, the catalyst veto, and C37's ORB entry;
add a flag-gated `entry_mode="limit_bid"` / `exit_mode="limit_ask"` to
`simulate_trades`; write the live-feasibility design note.* The halal filter is
ignored per the user's direction (it is being repaired; applied post-hoc later).

Files: `plan/lx_engine.py` (the engine), `plan/lx_frame.py` (the frame),
`plan/lx_tables.py` (the policies), `plan/lx_orb.py` (C37's ORB entry),
`plan/lx_poison.py` (honesty battery), `plan/lx_ident.py` (engine identity),
`plan/lx_out/*.json` (every number below). Engine change: `day-trading.py
::simulate_trades` gained `exit_mode` / `limit_entry` / `limit_exit`
(`entry_mode="limit_bid"` and `exit_mode="limit_ask"` as sugar), inert with the
flags off.

---

## Verdict, in one table

RESULTS_TABLE_PLACEHOLDER

---

## Part 0 — The instrument, and what it can and cannot say

The NBBO is not entitled on this account (`/v3/quotes`, `/v3/trades`,
`/v2/last/nbbo` all 403 — `plan/uq_out/entitlement_probe.json`). What is
entitled, and cached for all 27,197 symbol-days of the causal wide universe
plus 45,404 gapper-pool symbol-days, is the 1-second aggregate tape
(`data/massive/trades/{SYM}_{DATE}.json.gz`, rows `[t_ms, o, h, l, c, v, n]`,
09:30–16:05 ET). A second's `l` is the minimum **trade** price in that second,
`h` the maximum, `v` the shares traded. So:

* *"does a buy limit at L fill within N minutes"* is answered exactly by
  `min(l)` over the seconds after the post — no tick feed required;
* *"how much of it fills"* is bounded by the volume that printed at or below
  L in those seconds — a ceiling on our share, not a queue model;
* *"the bid" and "the ask"* are **not observed**. They are the last print
  ± a causal half-spread estimate (`plan/cr_cost.py`: max of the HL2 / Corwin–
  Schultz / Abdi–Ranaldo estimators over bars strictly before the posting
  minute; median 2.8 bps on this universe, validated against 176 real books in
  COST-REBASE Part 2.1). Every "at the bid" below means "one estimated
  half-spread below the last print".

Two caches had to agree for the pool arm to be priced: the m1 csv bars and the
tape. A **consistency guard** in `lx_engine.Day` drops any symbol-day whose
tape prints sit outside its own minute bar's `[low·0.97, high·1.03]` (a
split-adjustment disagreement between two caches). It drops **0** symbol-days
on the wide universe and caught the one pool symbol-day that produced a
+31,699 bps "price improvement" in the smoke test.

## Part 1 — The engine, and the fill rule stated before it was tested

`plan/lx_engine.py`. One ticket = an entry ladder, a hold, an exit ladder, a
hard flatten, three cost conventions and its own market counterfactual.

**Buy limit at L, posted at the START of minute m+1** (information ≤ m):

* fills from 1-second bars **strictly after the post second** whose `l ≤ L`;
* fill **price**: `L` if the second opened above L (the price came down to a
  resting order), else `min(L, open)` — marketable on arrival, never worse
  than its own limit (UNIVERSE-QUOTES' `fill_at`, the convention that fixed
  that line's one bug);
* fill **size**: a second with `v` shares can fill at most
  `part · v · share(L)`, where `share(L)` is the fraction of the second's
  `[l, h]` range at or below L (1 when the whole second printed at or below
  L) and `part` is our assumed share of that volume (1.0 headline; 0.5 = half
  of it was ahead of us). Fills accumulate across seconds until full or the
  rung expires — the mandate's "volume in that second ≥ our size, else
  partial", made continuous. `through` cents = require `l ≤ L − through`
  (queue-position sensitivity, as UNIVERSE-QUOTES 3.2);
* **ladders** (a list of rungs, each known at its own minute boundary):
  `rest` (post once, wait N), `tick` (raise one cent per minute, anchored at
  the decision quote, until the estimated ask, then hold), `chase`
  (re-anchor to that minute's own last print − half-spread every minute),
  `mid` (rest at the last print itself);
* **timeout** with shares unfilled: `cancel` (keep any partial; zero filled
  = no trade, attempt spent, next decision after the window) or `market`
  (the remainder crosses at the open of the next printed minute, charged the
  marketable cost).

**Sell limit** — mirrored: post at the ask (last print + half-spread) at the
exit decision minute, step **down** one cent per minute for M minutes, then
marketable; and always marketable at the hard flatten minute, where the
forced sale is at that bar's **close** exactly as `plan/hd_foresight.py` and
`plan/cm_lib.py` price it.

**Sizing.** The limit ticket sizes on `mark(m)` (the last print at the
decision — causal); the incumbent market ticket sizes on the fill open (the
non-causal convention of `hd_foresight`, `wn_table`, `uq_strat`, reproduced so
their rows come back to the cent).

**Cost conventions, all carried on every ticket:**

| key | passive leg | marketable leg |
|---|---|---|
| `flat` | 0 bps | 10 bps (+50 outside RTH) — UNIVERSE-QUOTES' convention |
| `meas` | measured **impact only** (`cr_cost`, Y = 1.0) | measured half-spread + impact — COST-REBASE's convention |
| `zero` | 0 | 0 — the gross path |
| `mkt` | — | the same name and decision under market fills both sides at flat 10: the incumbent frame's own number |

**Adverse-selection bookkeeping per passive leg:** `pi` = price improvement
vs the market reference (buy: open of m+1; sell: open of the minute after the
exit decision), `mo` = 5-minute markout of the last print vs the fill, signed
so negative = the price kept going against us after filling us. "Came to us
then reverted" = `mo ≥ 0`; "filled on the way down" = `mo < 0`.

**Cost lookup.** `FastCost` computes `cr_cost.CostModel.parts` for the ONE
posting minute from the same per-minute statistics (`data/massive/cost1`) with
the same scalar estimators (`cr_cost.cs_bps` / `ar_bps`). It is identical to
`CostModel` on tier `win` (**432 random checks, 0 mismatches, worst
9e-14 bps**; and 963/963 inside the poison battery). Its prior-session
fallback — used only when no trailing window exists yet, i.e. posts in the
first minutes — is the prior day's `max(median HL2, whole-day CS, whole-day
AR)` rather than CostModel's median of per-minute maxima: **+2.3 bps wider on
average (sd 4.5)** over 93 such checks, i.e. more conservative, stated here.

## Part 2 — Identity gates (the incumbent numbers come back first)

| gate | result |
|---|---|
| frame: market ticket through `lx_engine` vs `hd_foresight.run_day`, 30 random seeds + foresight + anti-foresight, per ticket | **256 day-policy checks over 8 days, 0 mismatches, worst $0.0006** (`plan/lx_out/frame_ident.json`) |
| tables: the wn MARKET walk (post 3, first fill wins, one position at a time) vs `uq_strat.simulate_day(market=True)`, ticket for ticket | **12 OOS days, 0 mismatches, worst $0.0000** (`tables_ident.json`) |
| engine hook, flags OFF vs the pre-edit `day-trading.py` on the REAL C37F / HOLD1 / W8RSd kwargs | **169/169, 169/169, 169/169 symbol-days byte-identical** (`engine_identity.json`) |
| `plan/idgate.py --rot` after the edit | **rotation anchors: ALL EXACT** |

## Part 3 — The frame: the zero-information baseline under every ladder

`plan/lx_frame.py --stage ladder --seeds 30` (pass A, the 12 headline
configurations; pass B carries the other 26 at 10 seeds, Part 3.2). 448 dates
2024-10-22..2026-08-06, hold 30, one position at a time, <= 7 tickets/day,
$15,000 tickets, 20 %-of-5-minute-volume cap, flat 15:00. Every row is the
mean over 30 random seeds; "market CF" is the same random names and decisions
priced under market fills on both sides at flat 10 bps (each limit ticket's
own counterfactual). `flat` = passive legs free, marketable legs 10 bps;
`measured` = passive legs charged the square-root impact term, marketable
legs half-spread + impact (COST-REBASE, Y = 1.0); `zero` = gross.

| config (entry / exit) | fill rate | tkts/day | **flat $/tkt** (±seed sd) | $/month @flat | measured $/tkt | zero-cost $/tkt | market CF (same names) | entry passive share | exit passive share | months + | ex-best | aug2026 | foresight $/tkt | anti |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| `mkt/mkt` | 0.997 | 7.00 | **-27.36** ± 2.7 | -4,021.40 | -43.67 | -0.15 | -27.36 | 0.00 | 0.00 | 0/23 | -102,109.69 | 28 tk -1,874.53 | +399.53 | -432.03 |
| `bid-rest1-cancel/mkt` | 0.487 | 7.00 | **-12.18** ± 2.9 | -1,789.40 | -24.33 | +0.13 | -35.92 | 1.00 | 0.00 | 2/23 | -58,610.84 | 28 tk +439.69 | +349.08 | -358.02 |
| `bid-rest3-cancel/mkt` | 0.678 | 7.00 | **-12.66** ± 2.7 | -1,860.40 | -28.71 | +0.25 | -37.98 | 1.00 | 0.00 | 6/23 | -41,817.29 | 28 tk -732.83 | +370.30 | -378.33 |
| `bid-rest3-mkt/mkt` | 0.998 | 7.00 | **-18.91** ± 3.2 | -2,780.30 | -38.96 | -0.39 | -27.67 | 0.62 | 0.00 | 2/23 | -70,976.26 | 28 tk -1,169.41 | +370.89 | -398.36 |
| `tick5-cancel/mkt` | 0.804 | 7.00 | **-12.08** ± 2.2 | -1,774.80 | -30.16 | +0.97 | -36.64 | 1.00 | 0.00 | 5/23 | -37,376.22 | 28 tk -1,343.71 | +370.62 | -380.46 |
| `tick5-mkt/mkt` | 0.998 | 7.00 | **-16.47** ± 2.3 | -2,421.10 | -37.36 | +0.25 | -27.32 | 0.76 | 0.00 | 4/23 | -56,201.45 | 28 tk -1,231.82 | +366.81 | -391.53 |
| `mkt/ask-rest3` | 0.998 | 7.00 | **-18.59** ± 2.5 | -2,732.30 | -38.23 | +0.13 | -26.92 | 0.00 | 0.60 | 2/23 | -69,356.18 | 28 tk -1,166.62 | +396.89 | -407.69 |
| `mkt/tick5` | 0.997 | 7.00 | **-17.16** ± 2.8 | -2,521.40 | -37.39 | -0.32 | -27.31 | 0.00 | 0.75 | 1/23 | -66,910.73 | 28 tk -1,228.07 | +397.67 | -405.30 |
| `bid-rest3-cancel/ask-rest3` | 0.676 | 6.99 | **-3.50** ± 2.9 | -513.90 | -23.62 | +0.82 | -37.05 | 1.00 | 0.65 | 11/23 | -16,373.62 | 28 tk -1,119.74 | +364.35 | -358.32 |
| `bid-rest3-mkt/tick3` | 0.997 | 6.99 | **-8.94** ± 2.4 | -1,312.70 | -32.82 | +0.42 | -26.58 | 0.62 | 0.66 | 7/23 | -35,588.40 | 28 tk +110.75 | +373.08 | -376.92 |
| `tick5-cancel/tick5` | 0.801 | 6.99 | **-1.91** ± 2.6 | -280.90 | -24.65 | +0.96 | -35.90 | 1.00 | 0.77 | 11/23 | +3,500.59 | 28 tk -960.85 | +369.53 | -360.62 |
| `tick5-mkt/tick5` | 0.997 | 6.99 | **-6.00** ± 3.2 | -881.40 | -31.00 | +0.34 | -27.07 | 0.76 | 0.75 | 3/23 | -26,985.26 | 28 tk -801.14 | +368.47 | -368.88 |

**Read it in four steps.**

1. **The market row reproduces the diagnostic.** `mkt/mkt` = −$27.36 ± 2.7
   against HARNESS-DIAGNOSTIC's −$28.62 ± 2.4 for the same frame (the $1
   difference is the availability rule: this engine requires a cached tape
   and never peeks at the fill bar; the per-ticket identity against
   `hd_foresight.run_day` is exact when the same rule is used, Part 2). At
   zero cost it is −$0.15: the toll, and nothing else.
2. **One leg alone is worth its own fee, as UNIVERSE-QUOTES found.** Every
   entry-only ladder lands at −$12…−$19 and every exit-only ladder at
   −$17…−$19. Resting entries fill 49 % (1 min) to 80 % (5-minute tick
   ladder) of the time; the `cancel` variants take 7 tickets a day anyway
   because the day has more decisions than tickets.
3. **Both legs together take the baseline to within one seed-sd of zero.**
   `bid-rest3-cancel/ask-rest3` = **−$3.50 ± 2.9/ticket, −$514/month,
   11/23 months positive**; `tick5-cancel/tick5` = **−$1.91 ± 2.6,
   −$281/month, ex-best-day total +$3,500**. The zero-cost column is +$0.8
   … +$1.0 — the resting ticket has *no* gross drift of its own — so the
   whole move from −$27 to −$2…−$3.5 is the toll not paid plus price
   improvement net of adverse selection (Part 4). The mandate's first
   question is answered: **yes, execution alone moves the zero-information
   baseline from −$28 to ≈ $0 — but only if BOTH legs rest, and only under
   the convention that a passive fill pays no impact.**
4. **The measured convention says −$24.** COST-REBASE charges a passive fill
   the square-root impact of its size (median 9 bps a side on a $15,000
   ticket). Under that rule the same ladders sit at −$23.6…−$24.7. The
   5-minute markouts in Part 4 (+2.6 bps after a passive buy, −0.2 bps after
   a passive sell) are the tape's own evidence on which convention is closer
   to the truth for *resting* fills: a resting order that is hit does not
   show the post-fill drift the impact term is meant to price. Both
   conventions are carried through every table below; the honest answer
   lives between them and a live campaign is the only instrument that can
   place it (Part 8, item 6).

**The foresight ceiling is unchanged in sign and monotone in the ladder**
(perfect 30-minute foresight +$364…+$400 a ticket under every fill rule,
anti-foresight −$358…−$432), so the engine still finds money when
information is present. Note the direction: foresight *falls* from +$400
(market) to +$364 (both legs resting) because a winner that runs away from
the bid is never bought — UNIVERSE-QUOTES' "the limit helps at low ρ and
hurts at high ρ", now with the exit included.

### 3.2 Pass B — the other 26 configurations (10 seeds)

PASSB_PLACEHOLDER


## Part 4 — Adverse selection, both legs

Per passive leg over the 30 seeds of pass A: `pi` = price improvement vs
the market reference (buy: the open of m+1; sell: the open of the minute
after the exit decision); `mo` = 5-minute markout of the last print vs the
fill, negative = the price kept moving against us. "Reverted" = markout ≥ 0.

| frame config | leg | n passive fills | price improvement (bps) | 5-min markout (bps) | **net** (bps) | share reverted | reverted: pi / mo | way-down: pi / mo | partial share | median wait (s) |
|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|
| `bid-rest1-cancel/mkt` | entry (buy at bid) | 94,043 | +7.38 | +2.55 | **+9.93** | 0.527 | +7.6 / +40.5 | +7.2 / -39.8 | 0.000 | 14 |
| `bid-rest3-cancel/mkt` | entry (buy at bid) | 94,039 | +9.75 | +3.02 | **+12.77** | 0.531 | +9.9 / +39.5 | +9.5 / -38.3 | 0.000 | 25 |
| `bid-rest3-mkt/mkt` | entry (buy at bid) | 63,622 | +7.55 | +1.01 | **+8.56** | 0.517 | +6.7 / +38.8 | +8.5 / -39.4 | 0.162 | 25 |
| `tick5-cancel/mkt` | entry (buy at bid) | 94,052 | +9.59 | +3.02 | **+12.61** | 0.531 | +9.6 / +38.6 | +9.6 / -37.2 | 0.000 | 37 |
| `tick5-mkt/mkt` | entry (buy at bid) | 75,709 | +7.29 | +0.95 | **+8.24** | 0.522 | +6.0 / +36.3 | +8.7 / -37.7 | 0.113 | 37 |
| `mkt/ask-rest3` | exit (sell at ask) | 62,341 | +6.02 | -0.51 | **+5.51** | 0.511 | +5.6 / +27.1 | +6.4 / -29.3 | 0.172 | 27 |
| `mkt/tick5` | exit (sell at ask) | 74,968 | +5.53 | -0.24 | **+5.29** | 0.517 | +4.7 / +26.0 | +6.4 / -28.4 | 0.119 | 41 |
| `bid-rest3-cancel/ask-rest3` | entry (buy at bid) | 93,954 | +9.52 | +2.61 | **+12.14** | 0.529 | +9.6 / +38.5 | +9.4 / -37.6 | 0.000 | 25 |
| `bid-rest3-cancel/ask-rest3` | exit (sell at ask) | 65,501 | +6.08 | -0.20 | **+5.88** | 0.516 | +5.7 / +27.5 | +6.5 / -29.7 | 0.135 | 24 |
| `bid-rest3-mkt/tick3` | entry (buy at bid) | 63,536 | +7.35 | +0.92 | **+8.27** | 0.516 | +6.5 / +38.2 | +8.3 / -38.7 | 0.165 | 25 |
| `bid-rest3-mkt/tick3` | exit (sell at ask) | 67,860 | +5.13 | -0.40 | **+4.72** | 0.515 | +4.6 / +26.4 | +5.7 / -28.9 | 0.170 | 32 |
| `tick5-cancel/tick5` | entry (buy at bid) | 93,950 | +9.31 | +2.55 | **+11.86** | 0.528 | +9.3 / +37.6 | +9.3 / -36.6 | 0.000 | 38 |
| `tick5-cancel/tick5` | exit (sell at ask) | 76,352 | +5.51 | +0.10 | **+5.61** | 0.521 | +4.8 / +26.5 | +6.3 / -28.6 | 0.101 | 38 |
| `tick5-mkt/tick5` | entry (buy at bid) | 75,604 | +7.01 | +0.64 | **+7.66** | 0.519 | +5.8 / +35.4 | +8.4 / -36.8 | 0.114 | 37 |
| `tick5-mkt/tick5` | exit (sell at ask) | 75,308 | +5.50 | +0.18 | **+5.69** | 0.524 | +4.8 / +25.7 | +6.3 / -27.8 | 0.120 | 41 |

**Entry side.** A resting bid fills 9.3–9.8 bps below the open it would
have paid (rest / tick ladders; 7.3–7.6 for the ladders that time out into
the market, whose passive fills are the easier half), and the 5-minute
markout after the fill is **positive** (+2.5…+3.0 bps): on average the price
comes back after hitting us. The split is even — 53 % "came to us then
reverted" (markout +38…+40 bps), 47 % "filled on the way down" (−37…−40
bps) — the two halves are mirror images and the mean is a small positive.
The longer-horizon adverse selection is in the frame table's **market CF**
column: the names whose bid gets hit go on to earn −$37 under market fills
against −$27 for an unconditional pick, i.e. **≈ −$10 a ticket (≈ −6.5
bps) of selection at the 30-minute horizon**. Against +9.5 bps of price
improvement that leaves ≈ +3 bps net — UNIVERSE-QUOTES' "cancels to within
a basis point or two" is **refuted in direction but confirmed in size**: the
entry-side net is small and positive, not zero, once the resting order is
sized to the tape and cancelled after three minutes instead of filled at
any depth.

**Exit side — the leg UNIVERSE-QUOTES did not model.** A resting ask sells
5.1–6.1 bps above the open a market sell would have got, the markout is
≈ 0 (−0.5…+0.2 bps), and 51–52 % of fills revert. **Net +4.7…+5.9 bps,
with no adverse-selection term to subtract**: the exit is decided by the
clock, not by the price, so the names are not selected by their own path.
That is why the exit leg is worth as much as the entry leg in Part 3 even
though its fill rate is lower (60–77 % passive): it is pure spread capture.

**Partial fills** (the size rule): 0 % of `cancel`-entry fills are partial
(the volume-share rule only bites when a rung expires with shares left,
which is the cancel case counted as unfilled), 11–17 % of exit fills and
of market-timeout entries are. Sensitivities on the headline shape (pass B,
Part 3.2): `part = 0.5` (half the printed volume was ahead of us),
`through = 1 cent` (the book at L had to clear), `touch` (size-blind fill),
and `+5 bps` deeper.


## Part 5 — The demonstrated-skill policies, account-legal

`plan/lx_tables.py` — one position at a time, ≤ 7 tickets a day, $15,000,
post the top `post_k` and take the first fill; the exit ladder starts at
fill + H. Every policy is first reproduced under market fills through this
walker (Part 2), then run under the ladders with its own controls.

### 5.1 WIDE-NET's walk-forward model and UNIVERSE-QUOTES' relabelled refit

Held-out year 2025-08-01..2026-07-31, post 3, h30, `open_next` exit
convention. `model` = `data/massive/wn/model_scores_h30_s0.npy`; `relabel` =
UNIVERSE-QUOTES' refit on the entry-limit label; `*_shuf` = the shuffled-label
refits; `*_inv` = the sign flipped. The `mkt/mkt` block reproduces
`universe-quotes-audit.md` §4.2 to the cent (random −$30.45 ± 4.05, model
−$13.26, inverted −$37.01, shuffled −$24.23, 5.98 tickets/day).

**WIDE-NET / UQ relabel / LX refit (OOS year, post 3, h30)** — 251 days, 30 random seeds

| ladder | policy | tickets | tkts/day | fill rate | **flat $/tkt** | $/month | edge vs random | pct | measured $/tkt | edge (meas) | pct (meas) | zero | months + | ex-best | y1 / y2 $/tkt | aug2026 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| `mkt/mkt` | random ×30 | | 5.98 | | -30.45 ± 4.0 | -3,821.60 | — | — | -42.91 | — | — | -2.37 | | | | |
| | model | 1500 | 5.98 | 0.333 | **-13.26** | -1,664.30 | +17.19 | 100 | -45.70 | -2.79 | 27 | +4.62 | 3/12 | -22,008.23 | +0.00 / -13.26 | 0 tk +0.00 |
| | relabel | 1500 | 5.98 | 0.333 | **-17.92** | -2,249.20 | +12.53 | 100 | -73.54 | -30.63 | 0 | +8.94 | 3/12 | -28,999.89 | +0.00 / -17.92 | 0 tk +0.00 |
| | relabel_shuf | 1502 | 5.98 | 0.333 | **-33.02** | -4,149.30 | -2.57 | 23 | -56.05 | -13.14 | 0 | -5.45 | 0/12 | -51,101.53 | +0.00 / -33.02 | 0 tk +0.00 |
| | model_shuf | 1500 | 5.98 | 0.333 | **-24.23** | -3,041.00 | +6.22 | 93 | -46.56 | -3.65 | 17 | +3.35 | 2/12 | -38,502.79 | +0.00 / -24.23 | 0 tk +0.00 |
| | model_inv | 1500 | 5.98 | 0.333 | **-37.01** | -4,644.30 | -6.56 | 3 | -82.98 | -40.07 | 0 | -7.05 | 1/12 | -56,982.00 | +0.00 / -37.01 | 0 tk +0.00 |
| | relabel_inv | 1502 | 5.98 | 0.333 | **-31.71** | -3,984.40 | -1.26 | 30 | -58.33 | -15.42 | 0 | -2.19 | 1/12 | -49,326.08 | +0.00 / -31.71 | 0 tk +0.00 |
| `bid-rest3-cancel/mkt` | random ×30 | | 5.83 | | -14.95 ± 4.2 | -1,832.10 | — | — | -27.02 | — | — | -1.32 | | | | |
| | model | 1427 | 5.68 | 0.314 | **-9.80** | -1,170.60 | +5.15 | 87 | -31.44 | -4.42 | 23 | -0.75 | 3/12 | -16,099.16 | +0.00 / -9.80 | 0 tk +0.00 |
| | relabel | 1454 | 5.79 | 0.319 | **-7.09** | -862.00 | +7.86 | 100 | -35.88 | -8.86 | 0 | +5.48 | 4/12 | -11,611.72 | +0.00 / -7.09 | 0 tk +0.00 |
| | relabel_shuf | 1440 | 5.74 | 0.315 | **-14.70** | -1,771.00 | +0.25 | 57 | -31.41 | -4.39 | 23 | -1.40 | 2/12 | -22,368.52 | +0.00 / -14.70 | 0 tk +0.00 |
| | model_shuf | 1471 | 5.86 | 0.325 | **-18.71** | -2,302.40 | -3.76 | 23 | -34.32 | -7.30 | 3 | -5.33 | 1/12 | -29,893.94 | +0.00 / -18.71 | 0 tk +0.00 |
| | model_inv | 1467 | 5.84 | 0.323 | **-23.48** | -2,881.80 | -8.53 | 0 | -47.68 | -20.66 | 0 | -9.41 | 1/12 | -36,412.76 | +0.00 / -23.48 | 0 tk +0.00 |
| | relabel_inv | 1482 | 5.90 | 0.328 | **-19.86** | -2,462.00 | -4.91 | 17 | -35.18 | -8.16 | 0 | -5.56 | 3/12 | -31,320.49 | +0.00 / -19.86 | 0 tk +0.00 |
| `bid-rest3-mkt/tick3` | random ×30 | | 5.97 | | -16.97 ± 4.2 | -2,129.20 | — | — | -38.01 | — | — | -4.61 | | | | |
| | model | 1500 | 5.98 | 0.333 | **-5.21** | -653.40 | +11.76 | 100 | -37.69 | +0.32 | 57 | +2.63 | 6/12 | -9,994.08 | +0.00 / -5.21 | 0 tk +0.00 |
| | relabel | 1499 | 5.97 | 0.333 | **-15.24** | -1,910.80 | +1.73 | 67 | -68.17 | -30.16 | 0 | -2.16 | 3/12 | -24,475.03 | +0.00 / -15.24 | 0 tk +0.00 |
| | relabel_shuf | 1500 | 5.98 | 0.333 | **-21.49** | -2,696.90 | -4.52 | 10 | -51.64 | -13.63 | 0 | -8.31 | 1/12 | -34,237.55 | +0.00 / -21.49 | 0 tk +0.00 |
| | model_shuf | 1500 | 5.98 | 0.333 | **-16.08** | -2,017.60 | +0.89 | 60 | -42.69 | -4.68 | 17 | -3.70 | 2/12 | -26,603.59 | +0.00 / -16.08 | 0 tk +0.00 |
| | model_inv | 1499 | 5.97 | 0.333 | **-23.07** | -2,893.30 | -6.10 | 3 | -65.78 | -27.77 | 0 | -10.28 | 0/12 | -36,728.97 | +0.00 / -23.07 | 0 tk +0.00 |
| | relabel_inv | 1502 | 5.98 | 0.333 | **-21.93** | -2,756.20 | -4.96 | 10 | -51.78 | -13.77 | 0 | -11.05 | 3/12 | -34,602.18 | +0.00 / -21.93 | 0 tk +0.00 |
| `bid-rest3-cancel/ask-rest3` | random ×30 | | 5.83 | | -6.15 ± 3.9 | -753.80 | — | — | -23.39 | — | — | -2.06 | | | | |
| | model | 1427 | 5.68 | 0.314 | **-4.95** | -590.40 | +1.20 | 60 | -27.57 | -4.18 | 17 | -2.07 | 5/12 | -9,242.16 | +0.00 / -4.95 | 0 tk +0.00 |
| | relabel | 1454 | 5.79 | 0.319 | **-2.75** | -334.50 | +3.40 | 83 | -33.63 | -10.24 | 0 | +1.48 | 5/12 | -5,495.93 | +0.00 / -2.75 | 0 tk +0.00 |
| | relabel_shuf | 1440 | 5.74 | 0.315 | **-6.00** | -722.50 | +0.15 | 50 | -27.26 | -3.87 | 20 | -1.96 | 3/12 | -9,845.63 | +0.00 / -6.00 | 0 tk +0.00 |
| | model_shuf | 1471 | 5.86 | 0.325 | **-9.53** | -1,173.40 | -3.38 | 20 | -29.67 | -6.28 | 10 | -5.55 | 3/12 | -16,513.30 | +0.00 / -9.53 | 0 tk +0.00 |
| | model_inv | 1467 | 5.84 | 0.323 | **-13.24** | -1,624.60 | -7.09 | 3 | -40.47 | -17.08 | 0 | -9.50 | 3/12 | -21,579.34 | +0.00 / -13.24 | 0 tk +0.00 |
| | relabel_inv | 1482 | 5.90 | 0.328 | **-8.37** | -1,037.40 | -2.22 | 27 | -27.72 | -4.33 | 13 | -5.13 | 4/12 | -14,549.42 | +0.00 / -8.37 | 0 tk +0.00 |

**What the resting ladders do to a ranker.** The random control moves from
−$30.45 to −$6.15 under `bid-rest3-cancel/ask-rest3` (the account-legal
version of Part 3's move), and the ranking's edge over it goes from **+$17.19
(100th percentile) to +$1.20 (60th)** for the market-labelled model and from
+$12.53 to **+$3.40 (83rd)** for the entry-limit relabel; the inverted
controls fall to the 3rd percentile and the shuffled ones sit on the random
mean, so the harness is clean and the conclusion is UNIVERSE-QUOTES' §4.1
again with the exit included: **a ranker fitted on market fills does not
survive a resting-order execution** — the names it likes most are the names
that run away from the bid. Under `bid-rest3-mkt/tick3` (rest, then cross)
the market-labelled model keeps +$11.76 (100th pct) at −$5.21/ticket,
−$653/month — the best row of this block and the account-legal closest miss
before the refit. The `measured` columns are −$28…−$38 for every row and
every percentile collapses under them, as in COST-REBASE §4.4.

### 5.2 Rank for the END-TO-END fill (`plan/lx_relabel.py`)

REFIT_PLACEHOLDER

### 5.3 CLOSE-MOMENTUM's REV 15:30 → 15:59 composite, k = 7

REV_PLACEHOLDER

### 5.4 The catalyst veto (ANY_NEG_3d), 1/day at 09:35, h60

VETO_PLACEHOLDER


## Part 6 — C37's ORB entry (wide universe and the gapper pool)

`plan/lx_orb.py`. The opening range is the first five regular-session bars
(09:30–09:34, `DEFAULT_ORB_BARS = 5`); a name breaks when a later bar's high
exceeds the range high, the decision is that completed bar, the market fill
is the next open and the ladders post at the same instant. One position at a
time, ≤ 7 a day, hold 30, flat 15:00, entries cut at 14:30 (C37's
`entry_cutoff`). `strength` buys the breaker with the largest gain since the
09:30 open (the live rule's instinct), `weak` the smallest, `fore` the
perfect-foresight breaker. OPEN-UNIVERSE's `data/massive/m1o` had no
MANIFEST when this ran, so the two universes are the mandate's fallback.

## FRAME

_(frame pass not landed)_

## ADVERSE (frame)

_(not landed)_

## WIDE-NET / UQ relabel / LX refit (OOS year, post 3, h30)

_(WIDE-NET / UQ relabel / LX refit (OOS year, post 3, h30): not landed)_

## CLOSE-MOMENTUM REV 15:30→15:59, k = 7

_(CLOSE-MOMENTUM REV 15:30→15:59, k = 7: not landed)_

## CATALYST veto ANY_NEG_3d, 1/day @09:35, h60 (random on the vetoed universe)

_(CATALYST veto ANY_NEG_3d, 1/day @09:35, h60 (random on the vetoed universe): not landed)_

**ORB / wide** — 448 days (stride 1), 23.7 breakers/day of 60.7 names, 30 seeds

| ladder | tkts/day | fill | random flat $/tkt | random meas | random zero | market CF | strength $/tkt (pct) | weak (pct) | foresight | entry pi / mo | exit pi / mo |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| `mkt/mkt` | 3.61 | 1.000 | **-32.53** ± 4.0 | -57.16 | -3.38 | -32.53 | -34.11 (33) | -31.52 (73) | +55.89 | — | — |
| `bid-rest3-cancel/mkt` | 3.19 | 0.777 | **-14.55** ± 3.2 | -35.69 | -0.87 | -45.61 | -20.43 (0) | -12.83 (73) | +52.00 | +13.1 / +0.8 | — |
| `bid-rest3-mkt/tick3` | 3.44 | 1.000 | **-12.60** ± 4.1 | -43.27 | -4.20 | -34.54 | -12.03 (63) | -12.97 (60) | +72.20 | +9.9 / -3.6 | +6.2 / -0.1 |
| `tick5-mkt/tick5` | 3.41 | 1.000 | **-9.20** ± 3.7 | -40.32 | -3.67 | -34.92 | -9.90 (53) | -8.96 (60) | +74.64 | +9.7 / -2.8 | +6.7 / +0.5 |
| `bid-rest3-cancel/ask-rest3` | 3.09 | 0.776 | **-8.48** ± 3.2 | -33.20 | -3.89 | -46.76 | -13.81 (0) | -6.18 (77) | +60.93 | +12.8 / -0.1 | +7.0 / +0.1 |

**Wide universe (causal, 23.7 breakers a day).** A random ORB breaker is
−$32.5 under market fills (worse than the frame's −$27.4: a fresh breaker is
bought at a local high) and **−$8.5 ± 3.2 with both legs resting** — the
same $24 of execution as the frame, and the same −$33 under the measured
convention. "Buy the runner" is the instructive row: −$34.1 under market
fills (33rd percentile) and **−$13.8 with a resting bid (0th percentile,
i.e. worse than every one of 30 random seeds)** — the strongest breaker is
the one that does not come back to the bid, so what fills is the fade.
The weakest breaker is the mirror (77th percentile, −$6.2). Foresight among
breakers is only +$56…+$75 a ticket: the ORB minute carries little
30-minute information on this universe.

**Gapper pool (the retracted +10 % screen; execution comparison only, 111
strided days, 42 breakers a day).** Same names, market vs resting fills —
the pool's median tradeable book is 28.5 bps wide (COST-REBASE §2.1), so the
resting ladders recover more per ticket here in dollars and the measured
convention charges more. The numbers are in the table; they are not an edge
claim because the membership is outcome-conditioned (MX-SERIES RETRACTION
#2), and the tape/bar consistency guard drops the symbol-days whose two
caches disagree (`n_tape_dropped`, Part 0).


## Part 7 — The engine hook (`day-trading.py::simulate_trades`)

`exit_mode: str = "market"`, `limit_entry: tuple | None`, `limit_exit: tuple
| None`; `entry_mode="limit_bid"` ≡ `entry_mode="triggers"` +
`limit_entry=(0, 3, "cancel")`; `exit_mode="limit_ask"` ≡ `limit_exit=(0, 3)`.

* **Entry.** The trigger machinery (ORB / PMH break / dip-reversal patterns /
  VS2 triggers / `market_at_start`) *decides* exactly as before; with
  `limit_entry=(bps, wait, on_timeout)` the decision posts a resting bid at
  `trigger × (1 − bps/1e4)` instead of paying the marketable price. On a later
  bar j it fills iff `Low[j] ≤ L`, at `min(L, Open[j])` (the tape rule on
  minute bars). After `wait` bars: `cancel` (no trade; the machinery may
  trigger again) or `market` (cross at the next open). A resting order blocks
  new triggers. The three entry sites route the fill through the trigger
  site's own bookkeeping with the gates already passed at post time;
  `market_at_start` posts once per window (an unfilled attempt is spent, as
  in the research).
* **Exit.** Every non-stop exit decision (target, bearish, pressure-flip,
  VWAP/RSI/MACD/EMA crosses, rand-exit) posts a resting ask at
  `price × (1 + bps/1e4)` for `wait` bars: fills iff `High[j] ≥ L` at
  `max(L, Open[j])`; on expiry it crosses at the next open. **Stops,
  time-stops and the window-close flatten stay marketable** — a stop that
  rests is not a stop. A passive fill pays no `_slip` (the flat-convention
  passive cost); the marketable remainder pays it.
* **Identity.** With both flags off `pend_buy` / `pend_sell` /
  `_lim_fill_now` stay `None` and every new branch is dead: Part 2.
  With the flags on the hook is live: on the 169 C37F symbol-days it produced
  164 legs, **114 passive exits** and changed 163 days; on HOLD1 (stops and
  flatten only) 0 passive exits, as designed.
* **What it is not.** A minute-bar fill rule is the tape rule's superset
  (a bar whose low touched L may have printed there for one lot); it is the
  research engine's convention, not the live one. The dollar numbers in this
  audit come from `plan/lx_*` on the 1-second tape; the hook is the flag the
  rotation harnesses can turn on.

## Part 8 — Live feasibility: what the watcher would need (design note, not code)

The mechanism this audit prices is *resting* orders, and the live paper
campaign has never rested one: every entry is a marketable stop-limit sweep
(Part 3 of `harness-diagnostic.md`: the live book paid **$83 more per entry
than the bar open** the harness fills at). What would have to change:

1. **Quote polling at the decision cadence, not the bar cadence.** The watcher
   reads `get_equity_quotes` (bid/ask/size) once per minute for the armed
   names. Posting at the bid needs the bid at the post second and again at
   every cancel/replace boundary — the `chase` ladder is one quote per name
   per minute; `tick` and `rest` are one quote at the post. Robinhood's paper
   quote is the real NBBO, which this audit never had: the first live week
   would also *measure* the half-spread estimator (COST-REBASE validated it on
   17 tradeable books; that is the whole sample).
2. **Order types.** Entry = a **limit buy, day, at bid** (or bid − k); exit =
   a **limit sell at ask** stepped down by cancel/replace; timeout = cancel
   and re-issue as marketable (a marketable limit at ask + 2 ticks, never a
   pure market order on a gapper). Stops stay stop-limit as today. Robinhood
   supports limit/stop-limit; cancel/replace is cancel + new order (two
   round trips, ~1–2 s each on the paper API), so the one-cent-per-minute
   ladder is feasible and a one-cent-per-second ladder is not.
3. **Partial fills are the normal case, not the exception.** The engine
   above fills against printed volume; live, a $15,000 order at the bid of a
   thin name fills in pieces over minutes. The watcher must (a) size on the
   quoted bid size and the trailing-minute volume (the 20 % cap), (b) accept
   a partial as the position when the window closes (cancel the remainder,
   do not chase), and (c) keep the exit ladder for the *filled* quantity only.
   The ledger needs per-fill rows (time, price, qty), not one entry price.
4. **The clock.** Every decision must be stamped with the quote it saw and
   the second it was posted; the fill rule's causality (P1/P2 in Part 9) is
   what a live audit will test against the broker's fill timestamps.
5. **Cash-account rules unchanged**: one position at a time, ≤ 7 tickets, ≤
   $100k/day. A resting order that has not filled does not consume cash but
   does consume the *slot* — the watcher may not post a second name while one
   rests (the `busy_until` of `lx_tables.walk_day`).
6. **What to log to close the loop.** For every posted order: quote at post,
   limit, size, every fill (t, px, qty), cancel time and reason, the 5-minute
   markout. Thirty days of that is the dataset that turns the estimated
   half-spread and the assumed `part = 1.0` into measurements — the two
   numbers in this audit that no amount of aggregate data can settle.

## Part 9 — The honesty battery

HONESTY_PLACEHOLDER

## Part 10 — Conclusions

CONCLUSIONS_PLACEHOLDER
