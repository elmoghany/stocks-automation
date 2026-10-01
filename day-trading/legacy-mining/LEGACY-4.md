# LEGACY-4: premarket (as an entry, and as a filter for regular-session entries)

**Question.** CHAMPION-REPLAY found that a live premarket entry on the honest scanner list averages about −4.1% (−$615 on a $15k ticket). Does any causal premarket subset make money? Candidate cuts: premarket dollar volume compared with the name's own history, a news or earnings catalyst, large cap, holding above premarket VWAP, and the time of the first cross. Separately, does anything a name does premarket predict a good **regular-session** entry later?

**Short answer.**
1. **As an entry, premarket is a near-uniform loser.** I cut the honest 12-day census (1,132 premarket +10% crossers, PM-ONLY names included) by time of first cross, relative and absolute premarket dollar volume, price, premarket VWAP, bar count and catalyst. Every bucket with n ≥ 50 is negative gross at every exit, from "sell at the 09:30 open" to "hold to 15:00". Exactly one slice is positive: **market cap ≥ $2B** (n = 41, 11 days). It is too small to act on, so I re-measured it over 444 sessions in Part D.
   Part D checks it over 444 sessions with the survivorship bias measured. There is one lead: true large caps (≥$2B) whose first +10% premarket print comes after 07:00, sold at 10:00. The corrected estimate is ≈ +70..+180 bps gross. The market-cap field it depends on is contaminated, so this is not tradeable yet.
2. **As a pre-open filter, premarket behaviour holds two small, stable vetoes and one weak band. None of them turns a losing book into a winning one.** The vetoes are "opened >20% below its premarket high" and "faded >5% between 07:00 and 09:29". The band is premarket $-volume between ~10% and 100% of the name's normal day. Each moves the average random-pick leg by roughly 5 to 15 bps. The break-even is 30 bps round trip.

## Data and method (honest only; nothing fetched; no existing file edited)

- **Premarket entries (Part A):** `data/massive/cp/premkt_census.json`. These are the 12 whole-market census days from CHAMPION-REPLAY §3.2, with bars from `data/massive/m1` and `m1c`. They include the PM-ONLY names (27%) that the pool never had. Every feature is measured **at the cross minute**:
  - `dvol_x` is dollar volume up to the cross, not the full premarket. The census `pm_dvol` covers the whole premarket and would leak.
  - `rel_x` = `dvol_x` / the prior-60-session median daily $-volume.
  - mcap = point-in-time shares × previous close.
  - premarket VWAP up to the cross.
  - catalyst = any timestamped news, EDGAR or earnings event (`data/massive/cat/events.pkl`) between the previous 16:00 close and the cross.

  Entry is the OPEN of the next printed bar after the cross. Exits are the open of the first print at or after 09:30, 09:45 or 10:00; a −8% stop with a gap-through fill at `min(stop, open)`; or the last close at or before 15:00.
- **Pre-open filter (Parts B, C):**
  - Every honest RTH leg in `plan/pa_out/cp_r4_legs.json` is joined to that name-day's premarket features, all fixed by 09:29 (static columns of `data/massive/cp/rows.npz`). That file holds R4 (coil rank, 961 legs) and **30 random-pick seeds (34,848 legs)**. The random seeds are the clean test, because a ranker's own preferences cannot confound them.
  - Fills are cp_sim post-retraction: next-printed-bar open, gap-through stops, and an RS_CROSS LAST-scanner universe.
  - Part C repeats the buckets on the panel's exit-agnostic forward returns. These are r60 and r1500 for every eligible name at 09:35 and at 10:00.
- **Units.** Everything is per **$10k ticket**. Costs:
  - RTH legs: **15 bps/side**, i.e. $30 per round trip (gapper central, pessimism-audit).
  - Premarket fills: **25 bps/side**. I picked this to reflect the wider pre-open spreads; I did not measure it. Gross is always shown so you can reprice.
  - Bucket thresholds are fixed round numbers, not sample quantiles.
  - "Halves" means the first 222 sessions vs the last 222. t(day) is the t-statistic on day-clustered means.
- **Scripts:** `plan/lm4_premkt.py` (Parts A, B, C) and `plan/lm4_largecap.py` (Part D).

## Part A — live premarket entries on the honest list (12 census days, n = 1,132)

Mean gross bps per entry (medians in brackets):

| class | n | →09:30 open | →09:45 | →10:00 | −8% stop, 15:00 | →15:00 |
|---|---:|---:|---:|---:|---:|---:|
| ALL | 1132 | −232 (−143) | −271 | −290 | −346 | −417 (−366) |
| PM-AND-RTH (73%) | 821 | −47 (−31) | −26 | −29 | −215 | −158 |
| PM-ONLY (27%) | 311 | **−719** (−535) | −916 | −979 | −691 | −1100 |

The cheapest version is "buy the cross, sell the 09:30 open". It is still **−$232 gross, about −$282 net per $10k**. The census figure of −4.1% to 15:00 is −$417 gross per $10k. No stop or exit choice rescues it.

**The cross is usually a thin print.** 918 of 1,132 crosses (81%) happen with fewer than 10 printed bars in the premarket so far, and 638 (56%) happen between 04:00 and 05:59. The "+10% premarket" scanner line is mostly an artefact of a few odd-lot prints at a stale open.

Results by causal cut. Each cell shows the best exit's gross bps, net $/ticket at 25 bps/side, days positive and t(day).

| cut | bucket (n) | best gross bps | net $/tkt | days + | t |
|---|---|---:|---:|---:|---:|
| time of first cross | 04:00–05:59 (638) | −201 | −251 | 2/12 | −4.6 |
| | 06:00–06:59 (83) | −311 | −361 | 3/12 | −3.0 |
| | 08:00–08:59 (212) | −122 | −172 | 3/12 | −0.6 |
| | 09:00–09:29 (67) | −215 | −265 | 1/12 | −2.4 |
| $-vol to cross vs own 60d median | <5% (829) | −131 | −181 | 1/12 | −4.4 |
| | 5–20% (161) | −333 | −383 | 3/12 | −2.2 |
| | 1–3× (32) | −94 | −144 | 2/10 | +0.2 |
| | >3× (17) | −214 | −264 | 1/7 | −0.4 |
| $-vol to cross | $2–10M (48) | +156 | +106 | 7/11 | +1.3 |
| | >$10M (23) | −154 | −204 | 2/10 | −1.5 |
| cross price vs premarket VWAP | 0–3% above (722) | −250 | −300 | 0/12 | −5.1 |
| | >8% above (189) | −19 | −69 | 3/12 | +0.2 |
| catalyst since prior close | none (633) | −319 | −369 | 0/12 | −5.4 |
| | yes (141) | +16 | −34 | 4/12 | +0.3 |
| price | >$100 (357) | −62 | −112 | 5/12 | −0.5 |
| **market cap** | 300M–2B (45) | −95 | −145 | 5/11 | −0.1 |
| | **2–10B (25)** | +212 | +162 | 6/11 | +1.5 |
| | **>10B (16)** | +883 | +833 | 6/10 | +1.8 |

Notes on the table:
- The market-cap rows cover only the 170 crossers with point-in-time shares on disk.
- The ≥$2B slice has a PM-ONLY share of just **5%**, against 27% overall. Combined (n = 41), it scores +230 / +474 / +257 / +73 / +151 bps at the five exits.
- A catalyst plus ≥$2B (n = 13) scores +582 / +830 / +565 / −2 / −84.

Two things stand out:
- **A catalyst helps but does not make a winner.** The no-event set is the worst set (−319 bps to the open, 0/12 days positive). The event set is roughly flat (+16 at 10:00, −34 net).
- **High relative premarket volume does NOT help.** Names already trading 50%–300% of a normal day before the open lost −700 to −1,200 bps. Chasing "unusual premarket volume" is the classic small-cap pump signature, and it fades.

## Part B — premarket behaviour as a filter for regular-session entries (444 sessions)

**Random-pick legs (30 seeds, 34,848 legs; base −8 bps gross = −$38/ticket net).** Buckets with ≥ 1,000 legs. "Net" = per $10k at 15 bps/side.

| premarket feature (known at 09:29) | bucket | legs | gross bps | net $/tkt | H1 / H2 net | t(day) |
|---|---|---:|---:|---:|---:|---:|
| open vs premarket high | **opened >20% below PM high** | 1829 | **−62** | **−92** | −106 / −75 | −2.5 |
| | −20..−10% | 3026 | +15 | −15 | −15 / −16 | −0.9 |
| | within 3% of PM high | 18821 | −8 | −38 | −42 / −33 | −6.4 |
| 07:00→09:29 drift | **faded >5%** | 710 | **−64** | **−94** | −101 / −87 | −2.3 |
| | flat ±5% | 18066 | −9 | −39 | −47 / −32 | −6.9 |
| | built >5% | 7609 | −13 | −43 | −62 / −22 | −3.6 |
| PM $-vol / own 60d median | <2% | 7067 | −20 | −50 | −62 / −36 | −4.9 |
| | 2–10% | 8292 | −9 | −39 | −48 / −32 | −4.1 |
| | **10–30%** | 6629 | **+7** | −23 | −11 / −33 | −1.9 |
| | **30–100%** | 4905 | −1 | −31 | −33 / −29 | −2.4 |
| | ≥1× | 7955 | −14 | −44 | −58 / −27 | −3.1 |
| gap at 09:29 | 5–10% | 9129 | +21 | −9 | −17 / −1 | −0.9 |
| | 0–5% | 8786 | −19 | −49 | −49 / −49 | −6.3 |
| | 10–20% | 8758 | −18 | −48 | −51 / −45 | −4.1 |
| price | <$5 | 9865 | +30 | +0 | −11 / +12 | −0.2 |
| | >$20 | 11838 | −34 | −64 | −82 / −46 | −7.9 |
| market cap | <50M | 2167 | +59 | +29 | −16 / +61 | +0.8 |
| | ≥2B | 2329 | −19 | −49 | −57 / −39 | −3.0 |
| premarket +10% print? | yes / no | 17346 / 17502 | −9 / −8 | −39 / −38 | — | — |

**Part C (exit-agnostic panel, every eligible name; mean r1500 gross bps, at 09:35 / at 10:00) agrees on the same three shapes:**
- Opened >20% below the PM high: −281 / −134 (base −52 / −6).
- Faded >5% from 07:00: −197 / −87.
- PM $-vol / 60d median:

| ratio | at 09:35 | at 10:00 |
|---|---:|---:|
| <2% | −118 | −47 |
| 2–10% | −1 | +12 |
| 10–30% | +10 | +37 |
| 30–100% | +9 | +65 |
| ≥1× | −119 | −56 |

This is an inverted U. Too little premarket interest means a gap nobody is trading. Too much means the move was spent before the open.

**The coil ranker (R4) already avoids the vetoed names.** Fewer than 20 of its 961 legs fall in either veto bucket, so the vetoes add about $0 to R4. Its other premarket buckets flip sign between halves (rel_pm ≥1×: +548 / −189; PM-crosser: +343 / −78). That is lottery noise, the same caveat LEGACY-5 raises: R4 lives on a few legs.

How much the filters are worth on random picks (net per $10k, before → after):
- Drop "opened >20% below PM high": −$38.4 → −$35.4 (+$3/ticket; 5% of legs removed).
- Drop "faded >5% since 07:00": +$1.2/ticket.
- Keep only the PM $-vol band 10–100%: −$38 → −$26 (+$12/ticket, but 67% of legs discarded).

None of these clears the 30 bps round trip.

## Part D — the large-cap premarket slice over 444 sessions

**Universe.** Every panel name-day whose premarket high reached +10% (25,830 name-days; 8,698 have point-in-time shares). The panel only contains names that later printed +10% in the regular session, so this set is **survivorship-conditioned**. I measured the size of that bias on the 12 census days instead of assuming it (`plan/lm4_check.py`). Entry is the first premarket close ≥ +10%; fill = open of the next print. Mean gross bps, medians in brackets:

| slice (444 sessions, PANEL = biased upward) | n | →09:30 | →10:00 | →10:30 | →15:00 | best exit: H1 / H2, t(day) |
|---|---:|---:|---:|---:|---:|---|
| all with shares | 8055 | +42 (−146) | +184 | +196 | +247 (−77) | H1 +229 / H2 +267, t +6.4 |
| mcap ≥ 2B | 1462 | +27 (−83) | +64 | +87 | +63 | t +1.0 |
| mcap ≥ 2B, cross < 07:00 | 862 | −92 | −65 | −35 | +1 | t −0.1 |
| **mcap ≥ 2B, first cross 07:00–09:29** | 600 | +204 (−14) | **+248 (+1)** | +261 (+17) | +153 | **H1 +279 / H2 +238, t +2.7, win 51%** |
| mcap ≥ 2B and any catalyst | 537 | +145 (+42) | +162 | +161 | +127 | t +1.8 |
| mcap ≥ 2B and earnings ≤ 24h | 116 | +99 (+54) | +78 | +111 | +66 | t +0.7 |

The same names bought the RS_CROSS way (next print after the first regular-session +10% close) are negative everywhere: ≥2B −52 at 10:00 and −143 at 15:00. Whatever edge large caps carry is **spent in the premarket**, which matches the PEAD-style earnings-gap story.

**Bias check on the 12 census days** (honest census set, PM-ONLY included, vs the panel-drawn set; gross bps to open / 09:45 / 10:00 / 15:00):

| slice | census (honest) | panel (biased) | bias |
|---|---|---|---|
| all | −232 / −271 / −290 / −417 (27% PM-ONLY) | −74 / +59 / +73 / −54 | +160..+360 |
| cross ≥ 07:00 | −262 / −269 / −233 / −397 (33%) | −73 / +129 / +145 / −32 | +190..+400 |
| mcap ≥ 2B | +230 / +474 / +257 / +151 (5%) | +302 / +562 / +438 / +149 | ~0..+180 |
| mcap ≥ 2B, cross ≥ 07:00 | +314 / +762 / +500 / +56 (n = 17, 6%) | +371 / +823 / +570 / +104 | +50..+70 |

Reading the bias check:
- For small caps, the panel's survivorship bias is worth several hundred bps. That is why the 444-session "all" row looks positive and the honest list does not.
- For the large-cap slice, the bias is small (PM-ONLY is only 5–6% of it). So **an honest estimate for "mcap ≥ 2B, first cross 07:00–09:29, sell 10:00" is roughly +250 − (70..180) ≈ +70..+180 bps gross.**

**But the market-cap field is contaminated.** Point-in-time shares × prev close is broken around reverse splits and odd share classes:
- Wrong values in the 17 census rows: NIVF "27.9B", WHLR "724B", KALA "17.3B", BCTX "4.3B".
- These are micro-caps, and they include the slice's two worst and one of its best trades.
- The real large caps in the census slice were MNDY, MBLY, PAY, XMTR, IBRX, AEHR, NN, CECO, LW and DAVE: mostly earnings gaps, 7 of 10 positive by 10:00.

So the lead is real enough to test properly and not real enough to trade.

At $10k, with large-cap premarket cost of ~10–15 bps/side: **≈ +$40..+150 per ticket, about 1.35 a day (≈ 28/month), ≈ +$1k..+4k/month if it holds.** Treat this as an upper bound until the market-cap field is fixed.

## TAKEAWAYS

1. **Pre-open veto ("broken premarket") for every regular-session gapper book.**
   - **Rule:** do not arm a name at or after 09:30 if, at 09:29, either (a) last < 0.80 × premarket high, or (b) last < 0.95 × the 07:00 price.
   - **Why it should work (causal):** the premarket buyers are already trapped above the open, so every bounce meets supply.
   - **Evidence:** random-pick legs in the veto buckets lose −62 / −64 bps gross (−$92 / −$94 net per $10k). Both halves agree (−106/−75 and −101/−87), and the exit-agnostic panel agrees too (r1500 −281 / −197 at 09:35).
   - **Expected value:** about **+$3 per ticket over the whole book, ≈ +$150–250/month** at ~2.8 tickets a day. For the coil ranker it is ≈ $0, because coil already avoids these names. It is a safety rail, not an edge.
   - **Test:** a shadow-veto in cp_sim under RS_CROSS/RS_DEFER, with the 30-seed random control, in both halves.
2. **Premarket-participation band as a gate or rank feature.**
   - **Rule:** prefer names whose premarket $-volume (known at 09:29) is **10%–100% of their own prior-60-session median daily $-volume**. Avoid <2% (nobody is trading the gap) and ≥1× (the move was spent before the open).
   - **Evidence:**
     - Random legs: inside the band +3.6 bps gross vs about −15 outside, i.e. **+$12/ticket vs base**.
     - Panel r1500 at 10:00: +37 / +65 inside the band vs −47 / −56 at the two ends. The panel at 09:35 shows the same shape.
   - **Limits:** it does not clear costs on its own. Its value is as a feature combined with LEGACY-5's minutes-since-cross.
   - **Expected value:** **+$10–20/ticket ≈ +$600–1,200/month** relative improvement at ~59 tickets/month. The sign of the book's total is unchanged.
   - **Test:** walk-forward gate on R4/R5 and the random seeds. Report both halves and ex-best-5.
3. **(Lead only; needs clean data) Large-cap, post-07:00 premarket gap, out by 10:00–10:30.**
   - **Rule:** true market cap ≥ $2B, first premarket close ≥ +10% between 07:00 and 09:29 (in practice an earnings or news gap). Buy at the next print and sell at the first print at or after 10:00.
   - **Evidence:** survivorship-corrected estimate ≈ **+70..+180 bps gross → ≈ +$40..+150/ticket net, ~28 tickets/month → ≈ +$1k..+4k/month**. The panel was t = 2.7 with both halves positive, and the bias was measured on the census days (Part D).
   - **Blocker:** the shares field is broken (micro-caps show up as "$17–724B"). Without a reliable market cap the number cannot be trusted.
   - **Test:** (i) rebuild market cap from split-adjusted shares and drop names with price < $10 as a sanity guard; (ii) fetch whole-market premarket bars (job B) on ≥ 60 more dates so PM-ONLY large caps are counted; (iii) shadow-log it live in paper from 07:00. Fetching is outside this line's rules.

## DISCARD

- **Premarket entries on small/micro-caps, under any filter tried.** This covers time of cross, relative or absolute premarket volume, premarket VWAP, catalyst, price, bar count, a −8% stop, and selling at the open. Every n ≥ 50 bucket is negative gross, and the PM-ONLY names (27% of the live list, −719 bps to the open) cannot be told apart at the cross.
- **"Unusual premarket volume" as a buy signal.** In the census, a ratio ≥ 50% of the normal day loses −700 to −1,200 bps. In the RTH panel, a ratio ≥ 1× is the worst bucket next to <2%.
- **The "premarket-high break" trigger and "PM crosser" flags as entry or rank keys.** The CHAMPION-REPLAY ablation already shows −$59/ticket at flat 10 bps/side. Here, "PM crosser yes/no" is −9 vs −8 bps on random legs: no information.
- **Using the census `pm_dvol` (full-premarket total) as a feature for an entry made before 09:30.** It is lookahead. Only `dvol_x` (volume up to the decision minute) is causal.
- **Buying large-cap gappers after the open (RS_CROSS entry).** ≥$2B names that gapped +10% premarket lose −39 / −52 / −143 bps gross at 09:45 / 10:00 / 15:00 when bought on the regular-session cross. Their move happens before 09:30.
- **The 444-session panel's "premarket entry is positive" rows (+247 bps "all").** This is pure survivorship: the same method on the census days overstates by +160..+400 bps for small caps.
