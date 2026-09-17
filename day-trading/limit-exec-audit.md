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

POLICIES_PLACEHOLDER

## Part 6 — C37's ORB entry (wide universe and the gapper pool)

ORB_PLACEHOLDER

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
