# LEGACY-1 — what the old champions' EXIT stack is worth on honest data

Analyst LEGACY-1 of 15, 2026-10-01. Analysis only: saved dumps plus the
causal cp_panel minute cache, read-only. No live code was touched.

## What was measured

**Entry sets.** Every exit is tested on three fixed sets of entries:

| set | source | legs | what it is |
|---|---|---:|---|
| **R4** | `plan/pa_out/cp_r4_legs.json` | 965 | CHAMPION-REPLAY R4: coil rank, no -8% stop, RS_DEFER next-print-open entry, 444 days |
| **RND** | same file, RND0–4 | 5,678 | R4's frame with a random pick (the control entries) |
| **HF3** | `data/massive/rotation_trades_C37F_hf3.json` | 1,839 | the honest C37F champion's own entries, from the authoritative engine (post-2026-09-16 harness) |

**Exit engine.** `plan/lm1_walk.py` is one bar-by-bar exit walker.

- It uses cp_sim's honest fills: a stop that is gapped through fills at
  min(level, open), clamped to the bar's [Low, High]; a take-profit
  (TP) limit fills at max(level, open).
- Its base setting reproduces cp_sim's R4 exits exactly (40/40 legs
  checked).
- Close-based signals can fill in two ways. **close** is the old
  convention: fill at the close of the signal bar. **next** is the
  stricter one: fill at the open of the next printed bar.

**Costs.** Every leg is re-priced to a $10k ticket from its return.

- Net is quoted at **15 bps/side**, the central cost for +10% gappers.
- It is also quoted at 28.75 bps/side, R4's own fill cost from
  cost-rescore.md.
- Months = 22 (in-sample, 2024-10 to 2026-07).

**Two modes.**

- **Mode B (fixed entries).** The same entry gets every exit, so the
  exit is the only thing that changes. Scripts: `lm1_fixed.py`,
  `lm1_report.py`, `lm1_paired.py`, `lm1_mfe.py`, `lm1_combo.py`.
- **Mode A (sequential).** The full cp_sim R4 frame, with the exit
  walker monkey-patched in. Tickets depend on when the previous one
  exited. Each variant also runs 10 random-pick seeds in its own frame,
  plus the 22-day OOS window (2026-08-03 to 09-01). Scripts:
  `lm1_seq.py`, `lm1_seqrep.py`.

Outputs are in `plan/pa_out/lm1_*.json` and `lm1_*.md`.

## 1. Which exit legs make the money and which lose it

Exit stack: base, with the next-open fill. MFE = the best price reached
(maximum favourable excursion); MAE = the worst (maximum adverse
excursion). Both are measured from entry to the exit bar.

| set | reason | n | mean % | sum $ ($10k tkts) | median hold (min) | median MFE | median MAE | P&L / MFE (mean) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| R4 | **bearish engulfing** | 393 | **+4.84** | **+190,074** | 32 | +4.17 | -1.43 | 0.61 |
| R4 | flatten 15:00 | 454 | -1.80 | -81,689 | 278 | +1.92 | -4.40 | -0.52 |
| R4 | trail at 10% (low pressure) | 72 | **-5.92** | -42,603 | 26 | +3.46 | -10.06 | -0.94 |
| R4 | trail at 20% | 46 | +3.85 | +17,725 | 24 | +11.87 | -13.57 | 0.12 |
| RND | bearish | 2,797 | +3.45 | +965,764 | 29 | +3.67 | -1.26 | 0.58 |
| RND | flatten | 2,124 | -1.67 | -355,490 | 270 | +1.62 | -4.49 | -0.56 |
| RND | trail 10% | 592 | -7.63 | -451,631 | 40 | +2.12 | -10.11 | -1.84 |
| HF3 | bearish | 1,113 | +2.81 | +313,182 | 27 | +3.26 | -1.45 | 0.55 |
| HF3 | flatten | 483 | -3.15 | -152,301 | 212 | +1.07 | -5.55 | -1.76 |
| HF3 | trail 10% | 194 | -7.01 | -135,982 | 32 | +2.47 | -9.90 | -1.45 |

- **The bearish-engulfing profit exit captures the winners.** It only
  fires when the bar closes above entry, so it wins by construction.
  It is still informative, not just "selling when green": holding to
  15:00 after it fires would have lost a further **$68 (R4), $17 (RND)
  and $30 (HF3) per ticket on average**. It takes about 55–61% of the
  move's MFE.
- **Two legs lose the money.**
  - **flatten.** These are names that never got going: median MFE is
    only +1–2%, and they are held for 3.5–4.5 h and finish at -1.7% to
    -3.2%.
  - **The pressure-narrowed 10% trail.** It behaves like a -10% stop,
    averaging -6% to -7.6% a leg.
- On the C37F-hf3 ledger itself, the old **-8% stop** is the bleeding
  leg: 364 legs, -7.18% mean, -$261k at $10k tickets. That almost
  exactly cancels the bearish exit's +$273k.
- **P&L by hold time** (hf3, as dumped):
  - 15–30 min holds: +1.44%/leg
  - holds under 5 min: -2.03%
  - 60–120 min: -0.99%
  - over 120 min: -2.41%
- **Give-back** grows with MFE. Legs that reached +10–20% kept +6.5%;
  legs that reached over 20% kept +17% of a +30% median. Only 9–15% of
  flatten legs were ever up 3% and then finished red. Most of the
  losers simply never worked, so a profit-lock cannot rescue them (see
  lock3 below).

## 2. Alternative exits on the SAME entries (Mode B, paired against base-next)

Each cell is the change in $ per $10k ticket, gross. The day-clustered
bootstrap standard error is in brackets. Cost per ticket does not
change, so the net change is the same.

| exit change | R4 (871) | RND (5,174) | HF3 (1,614) | verdict |
|---|---:|---:|---:|---|
| fill the bearish exit at the signal CLOSE instead of the next open | -4.0 (2.2) | -6.0 (0.7) | -6.0 (1.1) | the next-open fill is **better**, so the old exit's edge is not a fill artefact |
| **add the -8% hard stop** (C37's) | **-39.3 (14.1)** | **-11.9 (4.5)** | **-13.9 (5.8)** | the stop destroys value on all 3 sets |
| -3% stop | -30.4 (21.5) | +0.3 (7.1) | -3.0 (12.9) | no |
| remove the trail | -16.4 (29.6) | -1.1 (20.4) | -21.6 (13.4) | keep the trail |
| remove the bearish exit | -3.3 (20.8) | +10.2 (7.9) | -5.9 (15.7) | mixed |
| **bearish exit only when the close is ≥ entry +1% ("bm1")** | +1.0 (4.6) | +2.0 (2.5) | **+10.7 (4.0)** | positive on all 3, small |
| bearish exit even when red | +7.2 (8.3) | +0.2 (5.5) | -7.7 (8.1) | mixed |
| TP limit +3% | -54.2 (45.9) | -9.5 (16.9) | **+29.8 (11.4)** | helps on HF3, hurts R4 (cuts its tail) |
| TP limit +10% (no bearish exit) | -60.5 (42.8) | +1.4 (16.1) | **+35.8 (15.1)** | same; trimmed mean +4 / +18 / +39 |
| time stop 60 min | -9.7 | -5.3 | -5.0 | no |
| exit if red at 90 min | -2.4 | -3.6 | -4.4 | no |
| VWAP-loss exit (close < RTH VWAP, after 5 bars) | -23.3 | -5.3 | -6.7 | no |
| ATR(14) chandelier at 3x | -25.6 | -10.7 | -12.9 | no (ATR-only stacks: -55 to -96) |
| breakeven lock (+3% → +0.5%) | -18.5 | -15.2 | +5.5 | no |
| hold to 15:00 (no exits at all) | -114.1 | -16.8 | -36.9 | the exit stack is worth +$17 to +$114 a ticket |

**Absolute levels on the same entries** (gross / net at 15 bps / net
at 28.75 bps, $ per ticket):

| set | base-next exit stack | best alternative |
|---|---|---|
| R4 | **+78.1 / +48.0 / +20.4** | bear_any: +86.1 / +56.0 / +28.4 |
| RND | +16.3 / -13.7 / -41.2 | nobear: +26.0 / -4.0 / -31.5 |
| HF3 | -16.4 / -46.4 / -73.8 | TP10: +19.1 / -10.9 / -38.5 |

On the random-pick entries, **no exit makes them net-positive at
15 bps**. The best is -$4 a ticket.

## 3. Sequential frame (Mode A: the exit also changes which tickets you get)

R4 frame, net at 15 bps, $10k tickets:

| exit | n | gross | net@15 | Y1 | Y2 | $/mo | months positive | ex-best-day | 10-seed random net@15 | z | **OOS 22 d net@15** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base-close (= R4 as published) | 965 | +82.5 | +52.4 | +83.5 | +28.1 | +2,298 | 13/22 | +19,778 | -23.4±23.5 | +3.22 | **-174.7** (41) |
| base-next (honest bearish fill) | 952 | +63.4 | +33.3 | +48.4 | +21.7 | +1,441 | 12/22 | +956 | -19.1±22.3 | +2.35 | -151.3 (43) |
| bm1 | 871 | +61.6 | +31.5 | +49.0 | +18.7 | +1,249 | 12/22 | -3,282 | -16.9±31.7 | +1.53 | -162.9 (40) |
| bm1 + TP10 | 948 | +38.4 | +8.4 | -14.5 | +26.1 | +360 | 11/22 | +2,900 | -23.8±20.0 | +1.60 | -75.4 (45) |
| C37-style -8% stop | 1,186 | +54.9 | +24.8 | +65.2 | -6.4 | +1,339 | 10/22 | -1,328 | -36.6±16.6 | +3.71 | -40.9 (44) |
| no exits (hold to 15:00) | 474 | -82.6 | -112.5 | | | -2,424 | 7/22 | -67,228 | | | -413.9 |

- **A one-bar change to the exit fill moves R4's sequential total by
  $19 a ticket**, and its ex-best-day result from +$19.8k to +$1k. In
  Mode B the same change was +$4.5. The difference is path: an earlier
  or later exit changes which name the next ticket buys, and R4's
  result is carried by five tail legs (MNPR, YIBO, ARMP, …). **Any
  exit "improvement" under about ±$20 a ticket is inside the
  re-sequencing noise**; the random-seed standard deviation is
  ±20–30 a ticket.
- **OOS (2026-08-03 to 09-01): every R4-frame exit variant loses $41
  to $175 a ticket at 15 bps.** R4 does not survive its first unseen
  month, whatever the exit.

## 4. Combined stacks on fixed entries

These rows are the merged R4 / RND / HF3 table from `lm1_combo.md`.

All legs of each set, gross / net at 15 bps / net at 28.75 bps, $ per $10k ticket (`plan/pa_out/lm1_combo.md`).

| stack | R4 (965) | RND (5,678) | HF3 (1,839) | HF3 months positive @15 |
|---|---|---|---|---:|
| base-next (no stop) | **+86.5 / +56.4 / +28.8** | +16.2 / -13.9 / -41.4 | -9.5 / -39.4 / -66.9 | 7/22 |
| C37-style -8% stop, close fill | +47.2 / +17.2 / -10.4 | +4.3 / -25.7 / -53.2 | -23.4 / -53.3 / -80.8 | 1/22 |
| bm1 | **+87.5 / +57.4 / +29.8** | **+18.2 / -11.9 / -39.4** | +1.3 / -28.7 / -56.2 | 9/22 |
| bm1 + TP +10% | +16.9 / -13.1 / -40.6 | +6.3 / -23.7 / -51.2 | +15.5 / -14.5 / -42.0 | 9/22 |
| bm1 + TP +15% | +17.3 / -12.8 / -40.3 | +2.3 / -27.7 / -55.2 | **+18.7 / -11.3 / -38.9** | 10/22 |
| bm1 + TP10 + -15% stop | +9.0 / -21.0 / -48.5 | +3.7 / -26.4 / -53.9 | +10.2 / -19.8 / -47.3 | 9/22 |
| bm1 + TP10 + -8% stop | -12.7 / -42.7 / -70.2 | -0.0 / -30.0 / -57.5 | +4.3 / -25.7 / -53.2 | 6/22 |

- On the champion's own entries (HF3), going from the C37 stack to
  bm1 + TP15 with no stop moves the result **-$23.4 → +$18.7 gross,
  +$42 a ticket**. Net at 15 bps it is still -$11.3.
- A far -15% stop is **not free**: it costs $3–8 a ticket. Without any
  stop, the worst single leg in 8,482 is -$2,926 on $10k (-29%), so
  the stop is insurance against a halt or blow-up, priced at about $5
  a ticket.
- **On R4 every TP costs ~$70 a ticket.** The R4 frame is a tail
  catcher, and a TP removes the tail.

## TAKEAWAYS

1. **Never use a hard percentage stop on gapper entries; exit losers by
   the clock and the trail instead.**
   - **Rule:** no -8% (or -3% / -5%) fixed stop. Keep the champion's
     20% trail (10% when 10-bar pressure ≤ -0.30, 40% when ≥ +0.30)
     and flatten at 15:00. For catastrophe risk a far stop (-15%) costs
     about $5 a ticket (§4); it is optional insurance.
   - **Evidence:** on the same entries the -8% stop costs **$39, $12
     and $14 a ticket** on R4 / RND / HF3 (bootstrap SE 14 / 4.5 /
     5.8). A gapper's -8% is noise; it gets hit and then recovers. On
     the C37F-hf3 ledger, stops are -$261k against bearish exits'
     +$273k.
   - **Expected value:** about +$14 a ticket on champion-style entries.
     At about 2.5 tickets a day and 20 days a month that is about
     **+$700 a month** at $10k tickets. It is a loss-reducer, not a
     profit source.
   - **Test:** paper-trade or replay on the live engine's next entries,
     paired, with and without the stop. Accept the change if the paired
     difference stays above 0 with SE under half of it after 300 legs.

2. **Keep the bearish-engulfing profit exit, but fire it only when the
   close is at least 1% above entry, and fill at the next bar's open.**
   - **Rule:** sell at the open of the next bar after a bearish
     engulfing bar closes at or above entry ×1.01. Sell at the next
     open, not at a guessed close.
   - **Evidence:** this is the only causal exit that is positive on all
     three entry sets. The next-open fill adds **+$4 to +$6 a ticket**
     (SE 0.7–2.2). The +1% filter adds +$1, +$2 and +$10.7 (SE 4.0 on
     HF3); on all legs (§4) it is +$1.0, +$2.0 and +$10.8. In the
     sequential R4 frame, both changes sit inside the ±$20
     re-sequencing noise, so judge them on a paired test only.
   - **Why it works:** the bar after an engulfing bar tends to open a
     little higher, so a market sell at the open beats a sell at the
     close. Engulfing bars only 0–1% green are mostly noise: they cut
     winners that had barely started.
   - **Expected value:** about **+$8 to +$15 a ticket**, about **+$400
     to +$750 a month** at 2.5 tickets a day.
   - **Test:** paired replay of the exit on whatever entries the new
     line produces. Report the gap-fill difference separately.

3. **A take-profit target only helps entry sets with no fat right
   tail. Choose it per line, by checking whether that line's profit is
   concentrated in a few legs.**
   - **Rule:** add a resting limit at entry +10% *if and only if* the
     entry set's top-5 legs make up less than about 15% of gross
     profit.
   - **Evidence:** on the C37F champion's own entries, TP+10% is worth
     **+$35.8 a ticket** (SE 15.1; trimmed +39). That turns HF3 from
     -$16 to +$19 gross. On R4's tail-carried entries it costs $60
     (all of it MNPR-type legs), but it is +$4 trimmed. In §4, bm1 +
     TP+15% on HF3 is +$18.7 gross against bm1's +$1.3, and 10/22
     months are positive.
   - **Expected value:** +$20 to +$35 a ticket on non-tail entries,
     about **+$1,000 to +$1,750 a month**. That is still not enough to
     make HF3 net-positive at 15 bps (-$11 a ticket).
   - **Test:** compute the top-5 share on the new line's
     walk-forward-ranked entries *before* choosing; then run the paired
     comparison. Do not pick by in-sample result.

**Bottom line for "earn more per month".**

- Exits are worth real money relative to holding: +$17 to +$114 a
  ticket against no exits.
- Exits cannot create an edge the entries lack. On random gapper
  entries the best exit is still **-$4 a ticket net at 15 bps**.
- R4 (the best old frame) is +$33 to +$52 a ticket in-sample but
  **-$151 to -$175 a ticket OOS**.
- Use the exit lessons on whatever entry signal the other analysts
  find. None of these exits is a monthly-income line on its own.

## DISCARD

- **Time stops** (30/60/90/120 min, and "red at 30/60/90"). They are
  neutral to negative on every set; t30 is -$12 to -$41 a ticket. This
  matches the old S033–S036 result.
- **VWAP-loss exits and ATR chandelier trails**, alone or added to the
  stack: -$5 to -$26 a ticket stacked, -$10 to -$113 alone.
- **Breakeven / profit-lock stops**: -$15 to -$19 a ticket on R4/RND.
  The old S019–S027 "catastrophic" finding replicates.
- **Tighter hard stops** (-3%, -5%): never better than no stop.
- **Small fixed take-profits** (+2% to +5%): they win 66–75% of the
  time and are still ≤ base on R4/RND.
- **Early flatten** (12:00 / 13:00): worse than 15:00 on R4.
- **Re-tuning the pressure-modulated trail**: the 10% leg bleeds
  (-6% to -7.6%), but removing the trail is worse, and every candidate
  change is inside the ±$20/ticket re-sequencing noise.
- **Any "exit improvement" judged on a sequential total under about
  $20 a ticket.** Judge exits paired, on fixed entries.
