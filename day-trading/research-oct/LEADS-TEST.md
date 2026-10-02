# LEADS-TEST: the three LEGACY-MINING leads, tested with the hygiene stack (2026-10-01)

**Brief.** Test the three leads from `legacy-mining/SUMMARY.md` properly, each with the hygiene stack, on the
honest harness. Also re-score the live R15 and RL books with the stack. Same-day trading only.

**Answer in one line.** No lead is ready for paper trading.
- **Lead 1 (TC regime): FAIL.** Once the hygiene stack is on and ties are broken causally, nothing is positive at central cost.
- **Lead 2 ("quiet near the high"): FAIL**, for the same reason.
- **Lead 3 (large-cap premarket gap, sell at 10:00): NOT PROVEN.**
  - On the 466-date panel it looks strong: +$100/trade, ~31 trades/month, both years positive, 30/30 random seeds beaten on the census days.
  - But a targeted fetch of the names the panel cannot see shows the panel is survivorship-inflated by about **+$183/trade**. About 18% of large-cap premarket crossers never reach +10% in the session, and those average −$786.
  - The honest samples disagree. On the whole-market dates (census + targeted fetch, 55 trades) it is **+$111/trade, 90% CI [−$59, +$279], ex-top-5 negative**. The survivorship-corrected panel is **about −$30 gross (−$55 net)**.
- **Verdict:** add none to paper. Finish the 120-date whole-market fetch for lead 3; the script is written and resumable, but the API key was rate-limited all session.
- **R15:** do not put the hygiene stack on it (it cuts R15 from +$75 to +$4–20/trade).
- **RL:** the entry screens look helpful, but on 56 trades only. Shadow-log them; change nothing.

All $ are per **$10k ticket** (1e4 × leg return, LEGACY-10 convention) unless marked "actual notional".
- **Central cost** per side = 0.5 × est. half-spread + 4.4 bps before 10:30 (3.1 after) (LEGACY-9). The half-spread is max(CS, AR)/2 on the 30 one-minute bars before the fill.
- **Stress row:** flat 12 bps per side.
- **Splits:** Y1 = 2024-10-22..2025-07-31 (193 sessions), Y2 = 2025-08..2026-07 (251), OOS = 2026-08-03..2026-09-01 (22). That is everything on the panel; there are no minute bars for Sep 2026.
- **Halal** was ignored for selection. Halal-PASS lines use the present-day list `data/halal_list.json` (472 names), applied after the fact.

## 0. Harness and its checks

`plan/lt_sim.py` is a copy-and-modify of cp_sim's `run_day`. cp_sim itself is not edited; only its helpers are imported.
- **Universe:** the live scanner (LAST: an RTH close ≥ 1.10 × prev close, last ≥ $2).
- **Decisions and fills:** 5-minute grid; RS_DEFER fill at the OPEN of the next printed bar; gap-through sells.
- **Book:** one position at a time; ≤ 7 tickets/day; $10k tickets capped at 20% of trailing 5-minute volume; flat by 15:00.

- **Causal tie-break.** Every rank is `lexsort((seeded crc32(seed|date|t|sym), -volume 04:00..t, key))`. Pool-file order is never used.
  - Check: shuffling the panel's row order gives **identical legs** for coil, quiet, ret15 and random.
  - The random control was first order-dependent. It now hashes the symbol, so it passes too.
- **Anchor.** Coil rank, no hygiene, R4 exits (bearish exit filled at the next open), causal ties, 444 in-sample days: **1,173 legs**. That is exactly the leg count of PAPER-3BOOK's "live config" full-day identity. +$29.6 gross/ticket in-sample (the published live-config figure is +$23.27 on vol-capped notional).
  - On 2024-10-22 it reproduces the live-path picks MLI (bearish), RITR (10% trail), HRI.
- **Hygiene stack.** The candidate screens are applied at the decision minute t, before ranking. Exits apply to every name: after the $5M dvol60 floor, all names count as liquid.

| screen | rule |
|---|---|
| pool hygiene | type CS/ADRC; not a test symbol; first printed open / prev close in [0.5, 2] |
| spread | max(CS, AR)/2 over the 30 bars ending at t ≤ 10 bps |
| liquidity floor | dvol60 ≥ $5M |
| range screen | sigma1 at t defined and ≤ 0.017 |

| exit rule | detail |
|---|---|
| no fixed stop | — |
| +5% target | the first close ≥ 1.05 × entry sells at the next open |
| 10% trail | trail from the highest high since entry; the level comes only from bars before the current one; fill = min(level, open) |
| bearish engulfing | only when close ≥ 1.01 × entry; sells at the next open |
| flatten | 15:00 |

## 1. Lead 1: TC regime (LEGACY-10, pre-registered, not re-tuned)

**Rule as LEGACY-10 stated it** (`lt_lib.tc_labels`, the `lm10_feat` formulas verbatim). TC(D) = SPY_ma20 > 0 & QQQ_ma20 > 0 & SPY_volratio < 1.
- ma20 = close(D-1) / mean of the last 20 closes − 1.
- volratio = sd of the last 5 daily log returns / sd of the last 20.
- Everything is as of the D-1 close.
- TC is true on 238 of 466 sessions: Y1 113, Y2 111, OOS 14.

Trade gapper longs only on TC days. Central $/trade per split. "pct" = percentile of the line's total against the
30 random-pick seeds in the same frame, also restricted to TC days.

| line (TC days only) | Y1 | Y2 | OOS | ALL $/tr (flat12) | tr/mo | $/mo central | ex-top-5 $/mo | pct Y1/Y2/OOS/ALL |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| random pick + hygiene stack (mean of 30) | +7.9 | −0.3 | −23.5 | **+2.6** (−7.9) | 48.9 | +135 | −196 | — |
| coil + hygiene stack | −2.5 | −18.9 | −100.1 | **−15.7** (−26.4) | 46.8 | −732 | −1,146 | 23 / 13 / 0 / 0 |
| quiet + hygiene stack | −34.0 | +19.6 | −4.2 | **−4.7** (−16.0) | 39.7 | −186 | −447 | 23 / 67 / 10 / 20 |
| *no hygiene:* R4 ref (coil, R4 exits) | +58.2 | +43.4 | **−263.2** | +33.3 (+40.5) | 58.2 | +1,938 | **−2,778** | — |
| *no hygiene:* quiet, R4 exits | +48.1 | +50.0 | **−170.7** | +36.7 (+36.3) | 44.2 | +1,622 | +419 | 90 / 60 / 0 / 90 |

TC minus not-TC, central $/trade:
- **Random + hygiene stack:** +$20; 93% of seeds are above 0. So the market effect LEGACY-10 saw is real in direction: gapper longs are less bad on TC days.
- **The two hygiene-stack strategy lines:** coil −$13; quiet +$6, 90% CI [−25, +38].
- **The two no-hygiene lines (in-sample, day bootstrap):**
  - R4 ref: +$111, CI [−14, +238], P(≤ 0) = 7.5%.
  - quiet literal: +$63, CI [+4, +122].

**LEGACY-10's own pre-registered test fails on the only unseen data.** The rule was: "TC-minus-not-TC > 0 and TC-only net-positive."
- On the 22 Aug-2026 sessions, R4 scores TC **−$263** vs not-TC **−$30** per trade.
- Quiet literal scores −$171 vs +$38.
- 22 sessions is fewer than the 60 the test asked for, but both conditions fail with large margins.

Compared with random day subsets of the same size, R4-ref's TC-only total ranks at the 69th / 97th / 16th percentile (Y1 / Y2 / OOS).

**Verdict: FAIL.**
- On the hygiene-stack lines, TC does not turn anything positive at central cost. Random TC-only is +$2.6 per trade, and −$7.9 at 12 bps.
- On the no-hygiene R4 frame, the TC-only gain is tail-driven: ex-top-5 is −$2.8k/month.
- The holdout reverses for the third time; LEGACY-10 had already seen Aug reversed on C37F.

What to keep: log the TC label in the paper EOD as a free shadow feature. Do not gate on it.

## 2. Lead 2: "quiet near the high" rank (LEGACY-2)

**Rule** (causal at decision minute t):
- score = pct_rank(coil) − pct_rank(ret15b) within the scanner set; ret15b = last(t) / last(t−15) − 1.
- Require gain_now ≤ 40%; decisions from 09:50.
- Ties: volume so far, then a seeded hash.

**Controls** (same frame):
- 30-seed random pick;
- a ret15-only rank (lowest 15-minute return first).

| line (all days) | Y1 $/tr (pct) | Y2 $/tr (pct) | OOS $/tr (pct) | ALL $/tr central / flat12 | tr/mo | $/mo central | ex-top-5 $/mo |
|---|---:|---:|---:|---:|---:|---:|---:|
| **quiet + hygiene stack** | −21.3 (53) | +1.2 (57) | +3.9 (10) | **−7.4 / −18.7** (60) | 41.1 | −305 | −447 |
| CTRL ret15-only + hygiene stack | −10.7 (80) | +0.5 (53) | +43.4 (93) | −1.5 / −12.2 (80) | 43.8 | −64 | −212 |
| CTRL random + hygiene stack, 09:50, gain ≤ 40% (mean of 30) | −19.9 | −1.3 | +23.1 | −7.6 / −18.5 | 42.2 | −319 (seed sd 259) | −466 |
| quiet + hygiene screens + R4 exits | −23.9 (7) | −2.2 (33) | −15.5 (3) | −11.0 / −22.4 (3) | 64.2 | −708 | −876 |
| quiet, no screens, stack exits | −3.9 | −33.9 | −42.5 | −21.7 / −22.0 | 41.2 | −893 | −1,142 |
| **LEGACY-2 literal**: quiet, no hygiene, R4 exits | +35.1 (90) | +5.0 (100) | −94.8 (10) | +13.1 / +12.2 (90) | 43.5 | +572 | **−360** |
| CTRL ret15-only, no hygiene, R4 exits | −112.5 (0) | −108.3 (0) | +41.7 (90) | −104.5 / −72.0 (0) | 65.8 | −6,874 | −7,751 |
| CTRL random, no hygiene, R4 exits (mean of 10) | −22.5 | −23.9 | −1.5 | −22.0 / −15.2 | 50.8 | −1,121 | −2,349 |

**Adversarial audit of the literal row** (the only positive one):
1. **The tail carries it.** Y1's top 5 legs are +$16.0k against a +$14.3k total. Y2 ex-top-5 is −$10.9k.
2. **The best legs are thin names whose fills were tiny.** GRAN (notional $211), ARMG ($275), CLIK ($271), AIRG ($198). The $10k normalisation inflates them.
   - At actual notional, the line is **Y1 +$42.8, Y2 −$8.2, OOS −$23.0 per trade**: a Y1-only effect.
3. **OOS is −$95/trade** (10th percentile).
4. Beating random at the 90th percentile over all days falls short of the brief's bar, which is to beat **both** controls in Y1 **and** Y2. It also fails against ret15-only once the hygiene screens are on.

**Halal-PASS only** (present-day list, post-hoc filter, all days, central $/trade):
- quiet + hygiene stack: −$23.1 on 155 trades (7.0/month);
- coil + hygiene stack: −$6.4 on 174 trades;
- quiet literal: −$14.1 on 69 trades;
- R4 ref: −$73.6 on 69 trades.

**Verdict: FAIL.**
- With the hygiene stack, the rank is indistinguishable from random (53rd / 57th / 10th percentile).
- The plain ret15 reversal key is no better than random either.
- The short-horizon reversal IC LEGACY-2 measured (t ≈ −30) does not survive as a one-pick-at-a-time rank after costs.

## 3. Lead 3: large-cap (≥ $2B) premarket +10% gap after 07:00, sell 10:00 (LEGACY-4)

**The fetch was blocked.**
- The brief asked for whole-market premarket bars on ≥ 120 dates. `plan/lt_pmfetch.py` is written and resumable: 120 dates (40 Y1 / 40 Y2 / 40 OOS through 2026-09-30), D-1 15:00..D 10:31 adjusted bars, so the gap is split-safe.
- The shared Polygon key answered **HTTP 429 "You've exceeded the maximum requests per minute, please wait or upgrade your subscription"** to about 75–90% of calls all evening, with 3–4 other agents fetching on the same key. **No full date completed.** I stopped it to stop starving the other agents.
- Possible cause: the paid tier lapsed. Please check the Massive subscription; this message is the free-tier text.

What I used instead, all honest:
1. **The 12 whole-market CENSUS dates** (`m1c`; every name with prev close ≥ $1.82 and dvol60 ≥ $100k). No survivorship: names that never confirm +10% in the session are included.
2. **The 466-date panel** (gapper pool = names whose RTH high reached +10%; survivors only). Its large-cap survivorship bias is measured twice: on the census days, and by a targeted fetch of the missing names on 20 of 60 planned dates (§3.4).

**Split-safe point-in-time market cap** (`lt_lead3.mcap_check`):
- **Shares:** PIT shares from `data/pt_shares/{sym}_{D}.json` (read for date D).
- **Fallback:** present-day market cap (`data/halal_universe.json`, about 2026-09-16) ÷ the unadjusted close that day × the prev close at D, divided by the cumulative split factor of every split in (D, now] (`data/research_oct/splits.json`).
- **Split check:** if the symbol had any split in [D−120 d, today], mcap is recomputed under every alternative adjustment. The record is **rejected unless every version falls on the same side of $2B** (1,420 of 9,879 crossers rejected).
- **Data-error guards:** prev close ≥ $5; dvol60/mcap ≥ 0.0005 (a $2B company trades ≥ $1M/day); mcap ≤ $5T.
  - These remove the "micro-cap shown as $17B–$11T" records: LRHC, SVRE, PAVS, HSDT, ASST, WHLR, NIVF, KALA, BCTX.
  - The census large-cap set is now the real one: MNDY, MBLY, AXSM, LW, DHI, INSP, XMTR, DAVE, PAY, PRAX, IBRX, AEHR, NN, ONTO, CECO, CHRN, VCX.

**Rule tested (exactly):**
- **Universe, from 07:00 to 09:29 ET:** names with split-safe mcap ≥ $2B, prev close ≥ $5, dvol60 ≥ $5M (the hygiene floor), type CS/ADRC.
- **Signal:** a name's first 1-minute close ≥ 1.10 × prev close (and ≥ $2) lands in [07:00, 09:29], and the name never printed ≥ +10% before 07:00.
- **Entry:** buy $10k at the OPEN of the next printed bar.
- **Exit:** sell at the OPEN of the first print at or after 10:00.
- **No stop and no target.** At most 10 positions a day ($100k cap), taken in cross order.

### 3.1 Results (panel rows are SURVIVORSHIP-INFLATED by about +$183/trade, see §3.4)

| line | Y1 $/tr | Y2 $/tr | OOS $/tr | ALL $/tr central / flat12 / PM 25 bps | tr/mo | $/mo central | ex-top-5 $/mo | t |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **guarded, all events (≤ 10/day)** | **+130.6** | **+93.9** | +25.8 | **+100.5 / +101.7 / +88.7** | **31.1** | **+3,124** | +2,485 (OOS −4,982) | 5.2 |
| guarded, FIRST event of the day only (one position) | +183.7 | +80.7 | −31.0 | +113.6 / +114.9 / +101.9 | 13.2 | +1,505 | +895 | 3.4 |
| guarded, PIT shares only (no present-day info) | +196.4 | +175.1 | −294.0 (n 16) | +157.0 / +159.7 | 13.8 | +2,173 | +1,544 | 4.5 |
| guarded, present-scaled shares only | +82.1 | +73.9 | +176.3 (n 34) | +84.6 / +84.7 | 19.0 | +1,605 | +1,169 | 4.0 |
| + spread ≤ 10 bps | +111.7 | +111.0 | +23.8 | +104.8 / +102.7 | 24.9 | +2,611 | +1,971 | 4.6 |
| + spread + sigma1 ≤ 0.017 (full screen stack) | +51.2 | +135.5 | +74.7 | +107.4 / +103.3 | 14.0 | +1,501 | +1,088 | 4.1 |
| full screen stack + stack EXITS (instead of 10:00) | −65.1 | +54.2 | +157.5 | +27.3 / +23.2 | 14.0 | +382 | +199 | 1.7 |
| halal-PASS only (present list) | +149.9 | +155.0 | +43.4 | +143.4 / +144.6 | 11.6 | +1,660 | +1,115 | 4.4 |
| **HONEST census days only** (whole market; n = 17; 2 never confirm a +10% close in RTH) | +560.5 | +285.7 | — | +366.6 / +372.1 | — | — | — | 3.0 |
| *reference:* all post-07:00 premarket crossers, census, any cap (n 344) | −277.9 | −412.6 | — | −346.4 | — | — | — | −2.2 |

Notes on the table:
- Trades per month on the all-events row: Y1 23.6, Y2 35.4, OOS 47.7.
- Months positive: 19 of 23.
- Cross-time buckets (post hoc, not used): 07:00–08:00 +$223 gross (n 293); 08:00–09:00 +$145 (231); 09:00–09:30 +$16 (204).

### 3.2 Controls and checks

- **30-seed random large-cap control on the census days** (whole market; same classification and guards; a name with no premarket +10% close, bought at the same minute and sold at 10:00):
  - control mean +$540 in total on 17 trades (sd $979);
  - lead +$6,742;
  - **percentile 100: 30 of 30 seeds below.**
- **Market beta.** Minus SPY over the same entry→10:00 window, gross is **+$145.5/trade (t 6.05)**: Y1 +162, Y2 +143, OOS +49. It is not a market-drift artefact.
- **Clustering.** Day-clustered t (sum per day): Y1 3.8, Y2 2.7, OOS 0.5, ALL 3.85. Without the 3 best days it is still +$102 gross/trade overall; OOS without its best 3 days is −$81.
  - The busiest day is 2026-07-30: 37 large caps gapped ≥ +10% premarket; mean +$545.
- **The hygiene screens add nothing here.** The spread / sigma screens cut trades by 20–55% at an unchanged $/trade.
  - The stack exits cost about −$80/trade against the plain 10:00 exit, so keep the time exit.
  - "No premarket entries" (LEGACY-4/15) was derived on small caps. This lead is the measured exception.

### 3.3 Survivorship (census measurement)

On the 12 census days, the panel subset vs the whole market for large caps:
- 16 vs 17 events; one PM-only name (VCX, −97 bps) is missing from the panel.
- The bias is **+$31/trade gross** (n is small).

### 3.4 Survivorship (targeted fetch on non-census panel dates): this is what breaks the lead

`plan/lt_pmgap_fetch.py` fetches the names the panel cannot see: guarded mcap ≥ $2B, dvol60 ≥ $5M, NOT in the gapper pool, grouped-daily open ≥ 1.03 × prev close.
- **The prefilter is safe.** All 17 census large-cap events opened at ≥ 1.076 × prev close, and only 1.2% of panel events open below 1.03.
- **Coverage.** The fetch was slow, rate-limited to about 5 calls a minute, single thread. It covered **22 dates spread over Y1/Y2** at the time of writing (293 names, all with bars), and it is resumable.

| on the 22 targeted dates | n | gross $/trade at 10:00 |
|---|---:|---:|
| panel (survivor) events | 31 | +205.7 |
| **missing large-cap crossers** (+10% premarket after 07:00, never +10% in RTH) | **7 (18%)** | **−786** (RRC −489, HALO −735, BIRK −522, TMC −736, GWRE −1,134, SHOP −1,506, FPS −381) |
| all, honest | 38 | **+23.0** (survivorship bias **+$183**) |

This is mechanical. A name bought at ≥ +10% that never trades at +10% again in the session must be down by 10:00, and the pool, defined by the RTH high, keeps only the ones that did trade there again.

Estimates once the bias is accounted for:

| estimate | n | gross $/tr | central $/tr | 90% day-bootstrap CI (central) | ex-top-5 $/tr | tr/mo |
|---|---:|---:|---:|---|---:|---:|
| **HONEST pooled** (12 census dates + 22 targeted dates, whole market) | 55 | +138.4 | **+110.8** | **[−59, +279]** | **−29.2** | 34.0 |
| pooled Y1 / Y2 | 19 / 36 | +194.9 / +108.7 | +168.1 / +80.6 | [−159, +536] / [−103, +261] | −228 / −82 | — |
| panel all days, corrected by the measured missing share (18%) and mean (−$786) | ≈ 890 | **≈ −30** | **≈ −55** | — | — | — |

The census days were unusually kind: 1 missing name of 17. The targeted dates gave 7 of 38. The pooled honest sample is positive but wide, and the corrected full panel is negative, so the estimate is **somewhere between −$55 and +$111 per trade, with zero inside every interval.**

### 3.5 Adversarial audit of lead 3 (why it might still be wrong)

1. **Survivorship: decisive (§3.4).** The panel misses about 18% of the events, and they average −$786. The census days alone suggested only +$31 of bias. They were a lucky sample.
2. **Present-day information in 58% of the market caps** (present-scaled shares). It shifts the $2B line by roughly ±20% through later issuance or buybacks, and present lists drop since-delisted names, e.g. acquired companies that gapped on the deal.
   - The PIT-only subset avoids both and is *stronger* in-sample (+$157), but its 16 OOS trades are −$294. The present-scaled OOS (34 trades) is +$176.
   - Read the OOS as one month of noise in either direction.
3. **Premarket fills.** The entry is a premarket print, and the CS/AR half-spread on thin premarket bars is noisy. With a flat 25 bps on the premarket side it is still +$89/trade.
   - Live, Robinhood extended-hours orders are limit-only. A marketable limit at the ask, capped at ask × 1.005, is the realistic order. Measure the realized cost in paper.
4. **Small honest-census n (17).** It agrees in sign and is larger (+$367), but that is 17 trades.
5. **OOS is the weak part:** +$26/trade on 50 trades, ex-top-5 negative, t 0.5. Not a refutation, not a confirmation.
6. **Operations.** It needs an agent awake from 07:00 ET, against the 3-book's RTH-only frame (LEGACY-15 ops failures were premarket). That is a cost to weigh, not a statistic.

**Expected, honest: −$55 to +$111 per trade at central cost.** That is −$1.8k to +$3.7k a month at about 33 trades/month on a $100k account with $10k tickets. Zero sits inside every interval, and ex-top-5 is negative.

**Verdict: NOT PROVEN. Do not add to paper yet.** The test that decides it is cheap once the API allows:
- Resume `python plan/lt_pmgap_fetch.py --ndates 60`, then `python plan/lt_pmgap_ana.py`. Better still, `plan/lt_pmfetch.py`: 120 whole-market dates, including Sep 2026.
- Pre-registered pass: honest pooled central > $0 with the 90% CI above −$20, Y1 and Y2 both positive, and SPY-excess > 0 on ≥ 60 dates.
- If it passes, paper it as a fourth book with an agent awake from 07:00. Use limit orders (ask, capped at ask × 1.005), first 10 events a day, sell at 10:00.

**The best honest rule, written exactly** (for that re-test):
- From 07:00 to 09:29 ET, take names with market cap ≥ $2B (point-in-time shares × prior close, split-safe), prior close ≥ $5, 60-day median $-volume ≥ $5M, type CS/ADRC.
- Signal: a name's first 1-minute close ≥ 1.10 × prior close prints in that window, and it never printed ≥ +10% before 07:00.
- Buy $10k at the next print. Sell at the first print at or after 10:00.
- No stop, no target, no other screens.

## 4. R15 and RL with the hygiene stack (does it help or hurt?)

Legs: the live-code parity replays (`data/paper/parity/r15.json` 111 fills; `rl.json` live config, 87 trades; RL is on the 255 held-out Y2 days only).
- **F** = entry screens at the decision minute (spread ≤ 10, dvol60 ≥ $5M, sigma1 ≤ 0.017; skip and stay flat).
- **X** = stack exits instead of the book's own.
- **O** = own exit or stack exit, whichever comes first.

| book | variant | n | gross $/tr | central $/tr | flat12 $/tr | tr/mo | ex-top-5 $/mo |
|---|---|---:|---:|---:|---:|---:|---:|
| R15 | own (09:36 → 10:36) | 111 | +105.2 | **+74.6** | +81.0 | 5.2 | +112 |
| R15 | F | 23 | +34.8 | +19.9 | +10.8 | 1.1 | −141 |
| R15 | X | 111 | +39.4 | +6.3 | +15.3 | 5.2 | −116 |
| R15 | O | 111 | +38.0 | +3.9 | +14.0 | 5.2 | −128 |
| RL | own | 87 | +32.1 | **+19.9** | +8.0 | 7.2 | −86 |
| RL | F | 56 | +50.3 | **+39.5** | +26.2 | 4.6 | −42 |
| RL | X | 87 | +16.6 | +4.8 | −7.5 | 7.2 | −167 |
| RL | FX | 56 | +77.3 | +66.5 | +53.2 | 4.6 | +103 |
| RL | FO | 56 | +52.4 | +41.6 | +28.3 | 4.6 | −10 |

- **R15: the stack hurts. Do not apply it.**
  - The spread screen at 09:35 refuses 80 of 111 earnings opens: CS/AR is wide in the first minutes for everyone. The filtered remainder is worse (Y2 −$75).
  - The stack exits cut the edge from +$75 to +$4–6, because the +5% target caps the earnings drift R15 lives on.
- **RL: the entry screens help (+$20/trade, 56 of 87 kept), and the stack exits hurt on their own (−$15).**
  - FX looks best, but X hurts on all legs and helps only on the filtered ones: that is inconsistent, 56-trade noise.
  - Recommendation: shadow-log "would F-veto" on RL legs, and change nothing until about 60 live legs exist.

## 5. What the hygiene stack does to the gapper lines (for the record)

| frame | no hygiene | hygiene stack |
|---|---|---|
| coil rank (R4) | −$9.5 central/tr, ex-top-5 **−$3,800/mo**, OOS −$192/tr | −$9.1 central/tr, ex-top-5 **−$665/mo**, OOS −$41/tr |
| random pick, 09:50, gain ≤ 40% | −$22.0 central/tr (seed sd $1,032/mo) | −$7.6 central/tr (seed sd $259/mo) |

The stack does what LEGACY-9/12/13 said it would. It removes most of the losses and the variance, and with them the lottery tail. No gapper rank tested here is positive on top of it.

## Files

- **Code:** `plan/lt_sim.py` (engine), `lt_lib.py` (TC label, summaries), `lt_run.py` (leads 1/2, 76 jobs, about 6 minutes), `lt_report.py`, `lt_audit.py`, `lt_books.py` (R15/RL), `lt_lead3.py` (events + split-safe mcap), `lt_lead3_report.py`, `lt_lead3_ctl.py` (guards, SPY excess, random control), `lt_lead3_final.py`, `lt_pmfetch.py` (the blocked 120-date fetch, resumable), `lt_pmgap_fetch.py` + `lt_pmgap_ana.py` (targeted survivorship fetch).
- **Outputs:** `data/research_oct/lt_*.txt|json`, not committed.
- To rebuild: `lt_run` → `lt_report` / `lt_audit`; `lt_lead3` → `lt_lead3_ctl` / `lt_lead3_final`; `lt_books`.
