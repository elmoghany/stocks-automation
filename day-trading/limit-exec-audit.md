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

FRAME_PLACEHOLDER

## Part 4 — Adverse selection, both legs

ADVERSE_PLACEHOLDER

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
