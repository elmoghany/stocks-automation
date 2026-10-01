# LEGACY-6 — Anatomy of winners (R4 + C37F-hf3, honest data)

Date 2026-10-01. Analyst LEGACY-6 of 15. Aspect: what the top 5% of honest
trades looked like **at entry time**, compared with the median trade, and
whether any causal feature separates them in both years.

Scripts (read-only on every input):

- `plan/lm6_anatomy.py`: joins every leg to entry-time features.
- `plan/lm6_stats.py`: per-source anatomy, AUC and quintiles.
- `plan/lm6_inter.py`: interactions, catalysts, and the winner list.
- `plan/lm6_sim.py` + `plan/lm6_simstats.py`: honest re-sims of R4 with
  feature filters, each with its own 10-seed random control.

Outputs are in `plan/lm6_out/` (`stats.txt`, `inter.txt`, `simstats.txt`).

## Data and method

| source | what | legs | days | Y1 / Y2 legs |
|---|---|---:|---:|---:|
| R4 | CHAMPION-REPLAY R4 (coil rank, no stop), `pa_out/cp_r4_legs.json` | 965 | 444 | 423 / 542 |
| HF3 | C37F-hf3 live rules, `rotation_trades_C37F_hf3.json` | 1,839 | 440 | 822 / 1,017 |
| RND | R4's 30 random-pick seeds, same frame, deduplicated legs | 30,369 | 444 | 13,144 / 17,225 |

- **Y1** runs to 2025-07-31 and **Y2** starts 2025-08-01.
- All three sources come from the post-2026-09-16 honest harness:
  RS_DEFER entry at the next print after the decision, gap-through
  fills, and the causal universe.
- RND is the large-sample base rate: it shows what a random entry in the
  same frame looks like, so it can tell "what winners look like" apart
  from "what R4's selection looks like".

**Features.** Every feature is taken at the last 5-minute grid minute
strictly before the entry minute. These are the `cp_feat` values, built
from bars up to that minute plus prior sessions only. They are:

- **Price and gap:** price, gap at the open, gap at 07:00, premarket
  high gain.
- **Premarket participation:** premarket $vol, and premarket $vol over
  the name's own 60-day average daily $vol (`pm_rel`).
- **Size and history:** 60-day average daily $vol (`dvol60`), shares
  outstanding, market cap, 60-day average range (`prior_range`), prior
  5-day return.
- **Session state:**
  - gain now, and the session-high gain so far;
  - coil (last / running high);
  - VWAP distance;
  - pressure over the last 10 and 30 bars, and ORB distance;
  - realized 1-minute volatility so far today (`sigma1`);
  - session rvol, and $vol so far.
- **Timing:** time of day, and minutes since the name first crossed +10%.
- **Breadth:**
  - number of names eligible (above +10%) at that minute;
  - number of +10% open gappers;
  - the median gain of the eligible names;
  - the name's gain rank among them (`lead_rank`).
- **Catalysts:** `cat_events.features_for` counts news, PR, offering,
  FDA, contract, earnings, 8-K, 424B and S-3 events, plus dilution and
  hours since the last news or filing. Only events with timestamp ≤ the
  decision count.

The hindsight fields `gain_full` and `rvol_pool` are never read. "Top 5%"
means top 5% by return within each source. The top 5% by $ overlaps it
(26/49 in R4, 78/92 in HF3) and gives the same picture.

**$ convention.** Returns are re-based to a $10k ticket. Net figures use
15 bps/side, the gapper central cost ($30 per round trip), unless marked
`netHS`. `netHS` charges the measured half-spread at entry and exit plus
4 bps/side. The measured half-spread is `cp_cost.TapeCost` with impact
off (Corwin-Schultz / Abdi-Ranaldo over the trailing 30 bars, fill
minute excluded).

## 1. Winners are the whole P&L, in every frame

| source | ret p50 | p95 (top-5% cut) | p99 | top 5%: $ at $10k | other 95%: $ total | other 95%: $/trade gross / net15 | all: $/trade gross / net15 |
|---|---:|---:|---:|---:|---:|---:|---:|
| R4 | +0.4% | +12.5% | +43.5% | +188,430 (n 49) | −108,805 | −118.8 / −148.8 | +82.5 / +52.5 |
| HF3 | +0.5% | +7.0% | +18.0% | +125,736 (n 92) | −160,856 | −92.1 / −122.1 | −19.1 / −49.1 |
| RND | +0.5% | +8.3% | +19.4% | +2,554,696 (n 1,519) | −2,832,786 | −98.2 / −128.2 | −9.2 / −39.2 |

- The median trade is a coin flip at about +0.5%. Every frame is a lottery:
  the 95% of ordinary trades lose about $100 gross each, and the top 5%
  pay for them, or fail to.
- R4 differs from random only in that its tail is fatter: p99 is +43.5%,
  against +19% in HF3 and RND.
- Winners are split evenly across the years: R4 26/23, HF3 45/47.
- **Exits.** R4 winners leave on the bearish-engulfing exit (27), at the
  15:00 flatten (12) or on the trail (10). HF3 winners leave on bearish
  (78); 7 are stops and 7 are scale-outs.
- **Holds.** Winners are held no longer than other legs: median 93 vs
  100 min in R4, 22 vs 26 min in HF3, and 51 vs 69 min in RND.

## 2. What the top 5% look like at entry (medians)

RND is the large unbiased sample. R4 and HF3 show the same pattern.

| feature (at entry) | top 5% | median band (p40–60) | bottom 5% | all |
|---|---:|---:|---:|---:|
| realized 1-min vol today `sigma1` | 0.0199 | 0.0073 | 0.0219 | 0.0110 |
| 60-day avg $vol `dvol60` | $243k | $10.4M | $266k | $1.86M |
| shares outstanding | 16.6M | 63M | 16.5M | 37M |
| 60-day avg daily range | 9.7% | 6.9% | 10.0% | 8.3% |
| session-high gain so far | +21% | +15% | +22.5% | +16% |
| price | $9.45 | $15.2 | $13.6 | $12.3 |
| minutes since 09:30 | 15 | 65 | 10 | 40 |
| minutes since the +10% cross | 5 | 35 | 5 | 20 |
| gain rank among eligible names | 29 | 46 | 24 | 40 |
| premarket $vol / own 60-day $vol | 0.33 | 0.10 | 0.41 | 0.13 |
| news in last 18h | 0 | 0 | 0 | 0 |

**The top 5% and the bottom 5% are the same animal.** Both are:

- illiquid (about $250k a day historically) and small-float;
- already volatile today (σ1 about 2% a minute);
- historically wide-ranging;
- early in the session, just after the +10% cross;
- near the top of the day's gainer list.

The median trade is a liquid, calm name entered later in the morning.

### Mann-Whitney AUC, top 5% vs the rest, per source and year

Values are Y1 / Y2. Only features on the same side of 0.5 in all six
source-years are listed.

| feature | R4 | HF3 | RND | reading |
|---|---|---|---|---|
| `sigma1` (high) | .79 / .74 | .62 / .78 | .72 / .75 | strongest, ≥ .62 in all 6 |
| `prior_range` (high) | .70 / .58 | .63 / .59 | .63 / .60 | ≥ .58 in all 6 |
| `hi_gain` (high) | .66 / .62 | .59 / .61 | .62 / .63 | ≥ .59 in all 6 |
| `dvol60` (low) | .31 / .30 | .38 / .22 | .31 / .28 | ≤ .38 in all 6 |
| shares (low) | .23 / .41 | .33 / .31 | .38 / .32 | ≤ .41 in all 6 |
| mcap (low) | .37 / .43 | .38 / .29 | .42 / .36 | ≤ .43 |
| `lead_rank` (low = a day leader) | .35 / .37 | .40 / .35 | .39 / .37 | ≤ .40 |
| `dvol_now`, `tod`, `n_elig` (low); `mkt_gain_med`, `gain_now`, `pm_high_gain` (high) | | | | same side, weaker |
| all catalyst counts | .48–.54 | .47–.52 | .49–.53 | **no information** |

These are **magnitude** features: they predict |return|, not the sign.
The test is the bottom-5% column above, which matches the top 5% on
every one of them. The **mean** $ shows it in the honest base rate. In
RND, the σ1 quintiles (net15, Y1 / Y2) are:

| σ1 quintile | Y1 | Y2 |
|---|---:|---:|
| Q0 (calmest) | +5 | −23 |
| Q1 | −39 | −24 |
| Q2 | −42 | −30 |
| Q3 | −53 | −14 |
| Q4 (most volatile) | −87 | −64 |

So **volatility is where the winners live, and also where the money is
lost**. With random entry, the most volatile quintile is the *worst* in
both years.

**No quintile of any of the 45 features is positive net in both years in
RND.** The best cells are about flat, and only at the calm end:

- `dvol_now` < $327k so far today: −10 / −1;
- σ1 < 0.0057: +5 / −23;
- price < $4.33: −13 / −4.

## 3. Where the shape turns into money: at the high, without a stop

Every R4 leg is a coil ≈ 1 entry: the name is at its running high when
bought. Within R4, the same σ1 that loses under random entry is the
whole edge:

| R4 legs by σ1 at entry | n | days | net15 $/trade | Y1 | Y2 | median | ex-top-5 legs |
|---|---:|---:|---:|---:|---:|---:|---:|
| < 0.009 | 321 | 222 | −44.5 | −64.1 | −30.5 | +34 | −71.2 |
| 0.009–0.0135 | 182 | 141 | −36.2 | −65.2 | −13.4 | +88 | −88.8 |
| 0.0135–0.0215 | 193 | 162 | +75.0 | +117.0 | +43.3 | +79 | −9.1 |
| ≥ 0.0215 | 166 | 143 | **+445.3** | +674.8 | +210.2 | +26 | −32.5 |

- The calm 58% of R4 (σ1 < 0.0135, n 503) **loses in both years**.
- All of R4's profit sits in the volatile 42%. There it is still the tail:
  the top bucket's median is +$26, and it is −$32.5 a trade without its
  top 5 legs.
- **The same at-the-high, high-σ1 entry fails in the other two frames:**
  - RND legs with coil ≥ 0.99 and σ1 ≥ 0.0135 (n 1,377): net15 is
    Y1 +28 / +4 and Y2 −44 / −49 for the σ1 0.0135–0.0215 / ≥ 0.0215
    buckets;
  - HF3 legs (C37F, which has a −8% stop): n 88, **−$160** a trade,
    negative in both years.
- **Mechanism.** A volatile microcap at its high is a fat-tailed lottery
  ticket in both directions.
  - It pays only when the exit gives the tail room (no hard stop, a
    20–40% trail, the bearish-engulfing exit).
  - It also needs the pick to be *the* highest-coil name rather than a
    random at-high one.
  - C37F's −8% stop and its pullback entries (HF3 winners' median coil is
    0.96) cut exactly those tickets off.

### HF3 (the live C37 rules) has a different winner shape

HF3 winners are the **pre-market-heavy, big-gap names bought on a dip**,
early in the session:

| feature | top 5% | bottom 5% |
|---|---:|---:|
| `pm_rel` | 1.23 | 0.38 |
| gap at the open | +9.7% | +6.7% |
| premarket high gain | +16.7% | +12.7% |
| coil | 0.959 | 0.977 |
| median entry | 09:45 | 10:00 |

Their AUCs:

- `pm_rel`: .70 / .76
- premarket high gain: .66 / .66
- gap at the open: .58 / .61
- time of day: .34 / .33
- eligible names: .37 / .27

This *is* a direction separator: it differs between the top and bottom
5%. But it does not turn into a positive mean. The HF3 `pm_rel` top
quintile (> 1.24× own daily $vol traded pre-market) is +35 in Y1 and −65
in Y2 net15.

## 4. Catalysts: the winners are no-news moves

Catalyst coverage: the corpus covers 72% of R4 legs, 100% of HF3 and
70% of RND.

| | news in the 18h before entry: n / net15 $/trade | no news: net15 $/trade |
|---|---|---|
| RND | 1,072 / −66.6 (Y1 −75, Y2 −62) | −38.2 (Y1 −49, Y2 −30) |
| R4 | 25 / −102.3 (Y1 +37, Y2 −212) | +56.6 |
| HF3 | 149 / −88.8 (Y1 −59, Y2 −99) | −45.6 |

- **47 of R4's top 49 legs had no news in the 18 hours before entry.**
  These include MNPR, YIBO, ARMP, SGN and RNAZ.
- A headline the day of the move makes a gapper trade *worse* by about
  $30–45 a trade in RND and HF3, in both years.
- Very few legs are affected (3.5% of RND and 8% of HF3), so the $ at
  stake is small.
- This is consistent with CATALYST-AUDIT, where 12 of 14 pre-registered
  catalyst rules were negative. It is not a new edge, only a small veto.

## 5. Honest re-sim: does a winner feature, used as a gate, keep the edge?

Splitting R4's *own* legs by a feature is conditioning after the fact. A
gate changes which names the rotation takes and when, so I re-ran R4
in `cp_sim` unchanged.

- **Method.** Eligibility is AND-ed with a causal mask from the `cp_feat`
  grid. Each gate is run against **10 random-pick seeds with the same
  gate** (same frame, same exits, random pick).
- **Identity.** The unfiltered re-run matches the saved R4 exactly: 965
  legs, gross $85,615.96.
- **Columns.**
  - `netHS` charges the measured half-spread at entry and exit plus
    4 bps/side.
  - `rtHS` is that round-trip half-spread before the +8.
  - `notl` is the median notional actually filled. The engine caps
    shares at 20% of the trailing 5-minute volume.

| R4 + gate | n | tkt/d | gross $/tkt | net15 (Y1 / Y2) | netHS (Y1 / Y2) | rtHS med / mean | $/mo net15 | ex-top-5 legs $/mo | months + | median filled notional | own random ctrl net15 | pct |
|---|---:|---:|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| none (R4) | 965 | 2.17 | +82.5 | +52.5 (+83.7 / +28.2) | +23.6 (+52.2 / **+1.3**) | 31 / 51 | +2,303 | −1,294 | 13/22 | $14,766 | −23.4 ± 23.6 | 100 |
| dvol60 < $1M or no history (**ILLIQ**) | 847 | 1.91 | +45.9 | +15.9 (+89.9 / **−44.0**) | −26.7 (+42.6 / −82.9) | 40 / 65 | +613 | −2,658 | 8/22 | **$5,054** | −38.2 ± 29.8 | **100** |
| dvol60 ≥ $1M (**LIQ**) | 1193 | 2.69 | −13.3 | −43.3 (−39.6 / −46.6) | −49.6 | 20 / 28 | −2,348 | −2,892 | 7/22 | $14,989 | −42.9 ± 13.4 | **40** |
| σ1 ≥ 0.0135 | 1048 | 2.36 | −6.5 | −36.5 (+51.5 / −105.3) | −93.9 | 61 / 79 | −1,737 | −4,529 | 8/22 | $12,755 | −40.4 ± 26.0 | 60 |
| σ1 < 0.0135 | 926 | 2.09 | −24.7 | −54.7 (−103.3 / −16.8) | −64.9 | 26 / 32 | −2,301 | −3,104 | 7/22 | $14,825 | −39.1 ± 11.3 | 0 |
| ILLIQ and σ1 ≥ 0.0135 | 987 | 2.22 | +8.9 | −21.1 (+75.1 / −100.4) | −87.5 | 71 / 88 | −947 | −4,194 | 9/22 | $8,207 | −22.4 ± 26.1 | 60 |
| LIQ and σ1 ≥ 0.0135 | 1239 | 2.79 | −18.3 | −48.3 (−66.2 / −32.6) | −82.2 | 44 / 56 | −2,722 | −3,566 | 3/22 | $14,988 | −63.8 ± 8.1 | 90 |

What this says:

1. **The σ1 finding from §3 does not survive as a gate.**
   - Restricting R4 to volatile names gives −$36.5 a ticket, at the 60th
     percentile of its own random control.
   - Restricting it to calm names gives −$54.7, at the 0th percentile.
   - **Both halves lose, yet the union wins.** R4's +$52.5 depends on
     the exact rotation path that put it into MNPR, YIBO, ARMP, SGN and
     RNAZ. Change the eligible set and the path, and the tail is missed.
   - So the leg-level σ1 split was selection after the fact. It is not
     a rule.
2. **R4's ranking edge lives entirely in illiquid names.**
   - Among names with < $1M of average daily $vol, coil-at-high beats its
     own random control at the 100th percentile (+15.9 vs −38.2).
   - Among liquid names it is at the 40th percentile: −43.3 vs −42.9,
     no skill at all.
   - But the illiquid half cannot be traded at $10k. The median filled
     ticket is **$5,054** under the 20%-of-volume cap. The measured
     round-trip half-spread is 40 bps median and 65 bps mean. It is
     negative in Y2 (−44 net15, −83 netHS) and −$2,658/month without its
     top 5 legs.
3. **R4 itself, at the measured half-spread** (not the flat 15), is
   +$23.6 a ticket overall and **+$1.3 in Y2**, with ex-top-5 at
   −$1,294/month. At its 2.17 tickets a day it is about +$1,000/month on
   paper and about $0 in the recent year.

## TAKEAWAYS

Each item below is a causal rule that can be tested. All $ figures are
at $10k tickets over 22 months of about 20 sessions.

1. **Liquidity-split acceptance test for every gapper line (a guardrail
   that saves money; it does not make any).**
   - *Rule:* report every gapper strategy split at a prior-60-day average
     daily $vol of $1M. Accept it only if the **≥ $1M half** beats its
     own same-frame random control and is positive at the measured
     half-spread in both years. The < $1M half fills about half the
     ticket at 40–65 bps.
   - *Why it is causal:* `dvol60` is prior-session only.
   - *Evidence:* the gapper "edge" in R4 (the only legacy line that ever
     passed its controls) is entirely the illiquid tail. The tradeable
     half is −$43/ticket, the same as random.
   - *Expected:* it stops the next R4-like tail from being promoted. At
     R4's rate that avoids roughly −$2,300/month of losses.
   - *Test:* re-run the split on any surviving gapper candidate,
     including R15, cat, RL2 and UQ if they touch gappers. Use
     `plan/lm6_sim.py`'s gate wrapper and swap in the line's own cfg.
2. **News-in-18h veto on gapper entries (small, both years, both
   frames).**
   - *Rule:* do not open a gapper ticket if the name had any news article
     in the 18 h before the decision (`cat_events` `n_news_all_18h > 0`).
   - *Evidence (net15, Y1 / Y2):*
     - RND news legs: −75 / −62, against −49 / −30 for no-news legs;
     - HF3 news legs: −59 / −99, against −42 / −49 for no-news legs.
     - 47 of R4's top 49 winners had no news.
   - *Expected:*
     - Each vetoed ticket gains +$43 (against an average ticket) to +$89
       (against no trade).
     - That is 149 vetoed C37F-hf3 tickets in 22 months, so
       **about +$290 to +$600/month**.
     - The live book stays negative.
   - *Test:* add the veto as a gate in `rotation_sim` C37F under the hf3
     harness, and in `cp_sim` R4. Each run needs its own 10-seed control.
     Coverage is 70–100% of legs, so report the uncovered legs separately.
3. **Do not buy volatile names at their high under a hard stop: a veto
   for the live C37 rules.**
   - *Rule:* in C37F, skip an entry where coil ≥ 0.99 (at the running
     high) **and** realized 1-minute σ today is ≥ 0.0135.
   - *Mechanism:* a fat-tailed microcap at its high needs room. A −8%
     stop or a scratch exit takes the left tail and never sees the right
     one. R4, with no stop, is the only frame where these entries make
     money, and there they are a lottery.
   - *Evidence:* HF3 legs in that cell lose **−$160 a ticket** net15
     (Y1 −153 on n 50, Y2 −169 on n 38). The other HF3 cells lose
     −31 to −50.
   - *Expected:* about 88 tickets in 22 months at about +$110 to +$160
     avoided per ticket, so **about +$450 to +$640/month**. That is an
     upper bound: §5 shows gates move the rotation path.
   - *Test:* run it as a gate in `rotation_sim` C37F hf3 with a 10-seed
     control in the same frame, and report the change in total and in
     ex-best-day.

Items 2 and 3 are vetoes on a line that is negative. Together they would
take C37F-hf3 from about −$4,100/month (net15: 1,839 legs × −$49.1 / 22) to about −$3,100. That
is less loss, not profit.

## DISCARD

- **"Find the next MNPR" feature models.** The features that mark big
  winners (σ1, prior range, small float, low dvol60, early session,
  day-leader rank, high-gain-so-far) mark the **big losers equally**.
  Bottom-5% medians equal top-5% medians, and these features predict
  |move|, not direction. In the random frame, the most volatile quintile
  is the *worst* in both years (−87 / −64).
- **σ1 or volatility gates on R4.** The 58% / 42% leg split looked like
  +$445 against −$44 a ticket. As an honest gate, both halves lose
  (−36.5 and −54.7), because the R4 result is path-dependent on five
  legs.
- **Trading R4's illiquid half.** It is 100th percentile against random,
  but fills about $5k and pays 40–65 bps round trip in half-spread, and
  it is negative in Y2.
- **Catalyst classes as entry signals.** All catalyst counts have AUC
  .47–.54 for winners. This agrees with CATALYST-AUDIT; only the
  no-news veto above has a consistent sign.
- **HF3's premarket-participation winner profile** (`pm_rel` > 1.2,
  big gap, early dip). It separates the top 5% from the bottom 5%, but
  its top quintile is +35 in Y1 and −65 in Y2.
- **Using "top 5% winners" as a training target at all.** The top 5%
  are more than 100% of P&L in every frame, and the other 95% lose
  about $100 a trade gross. Any feature study of winners alone re-learns
  volatility.
