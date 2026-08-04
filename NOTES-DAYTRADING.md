# Penny Stocks Trading Notes

Convention: new notes go at the TOP of this file. Each note = a **3-word title**,
then a detailed explanation of what was done and why.
Normal (large-cap wave/value) trading notes live in `NOTES.md`.
**Every configuration ever backtested** (grids, sweeps, cap matrices — ~240
configs with results + the script that reproduces each) is registered in
[`CONFIGS-TESTED.md`](CONFIGS-TESTED.md); re-test any of them from there.

---

## C11 Win Anatomy Study (2026-08-04) -- what the rules can't show

Instrumented every trade (trigger, entry pressure, peak-before-giveback)
across all 280 C11 days / 2,839 positions. FINDINGS:
1. MONSTERS ARE THE BUSINESS: 29 days (10%) = 47% of ALL profit
   ($434k). 74 days >=$5k = 82%. The other 206 days net roughly zero.
   The system is a monster-catching machine with cheap idle running.
2. DISCREPANCY FOUND: the C11 SIM allows entries 12:00-13:00 (the
   harness widened the window without an entry cutoff) -- 551 such
   positions earned only +$23k total (+$42 avg, pure churn). The
   stated rule says entries end at noon. Action: enforce
   entry_cutoff=noon and re-verify (expect ~flat P&L, cleaner rule).
3. GOLDEN HOUR IS THE OPEN, NOT PREMARKET: 9:00-10:00 entries avg
   +$567/position (best of any hour); 7AM entries +$444; after-noon
   +$42. The 9:30 RTH open is where the real money enters.
4. THE GAP SWEET SPOT CONTRADICTS INTUITION: 10-20% gaps are the
   RICHEST band (+$5,325/day avg, 81% win) -- hot-but-calm beats flat.
   Worst band: -5..0%. Deep red gaps (<-5%) win 84% (washed-out
   openings that reverse). The calm-gap CEILING at 20% is right, but
   'calmer is better' below it is FALSE.
5. RANK CARRIES IT: ranks 0-2 = $762k of $927k (avg +$8.1k/+$4.6k/
   +$3.6k); ranks 3-7 avg just +$1.2k. The walk depth mostly adds
   small change -- pick quality remains king.
6. RE-ENTRY GRINDER: per-position edge decays (1st +$1,141, 2nd +$751,
   3rd +$425, 4th+ +$137) BUT the 4th+ tail = 2,101 positions = $287k
   (31% of profit). Monster days are re-entry LADDERS (12-25 positions
   riding one runner). Never cap re-entries (confirms X069-71).
7. 73% OF WINNERS ARE STILL HOLDING AT THE 1PM FLATTEN (155/212) --
   the biggest open question: the edge does not die at 1PM. Testing
   2PM/RTH-close exits is the highest-value follow-up (needs sign-off).
8. PMH-break trigger: rare (83 positions) but highest avg (+$633) --
   currently ONE-SHOT; re-arming it on each new session high is a
   candidate experiment.
9. Entry pressure is NOT predictive (selling-pressure entries win 80%
   -- dip-buys work because the pressure TRAIL protects them). Pressure
   belongs in exits, not entries -- consistent with X207-9 failing.
10. Price level is irrelevant ($1.4 to $1,649 monsters); extreme rvol
    (100x+) is a monster tell.
Candidate X300 experiments: noon entry-cutoff alignment; 2PM/close
exits; PMH re-arm; 12:00-hour pattern-entry suppression. All stats are
in-sample descriptions -- hypotheses, not adopted rules.

## C11 Adopted As Live Default (2026-08-04)

C11 = C02 + pressure-modulated trail (12%/30% at -/+0.3 rolling 10-min
volume pressure, 20k-share floor) + exits extended to 1PM (entries
still end at noon; same-day always; user signed off). Y1 +$390,687 /
Y2 +$536,350 (avg year +$463,519 = +22.1% of the $15k per trading
day); slippage-stressed C12 keeps 92%. Defaults + daytrading-morning
skill + paper_watch.py (1-min watcher now flattens 1PM and applies the
pressure trail guidance) updated. Strict-noon fallback = C10
(+$378,765/+$481,805, 0 negm both years) if the 1PM hour is ever
walked back.

## X200 Campaign: Pressure Trail Wins, Gap Sweep Debunked, C11 Champion (2026-08-04)

97 experiments (8-config x 8-level calm-gap sweep, 30-experiment volume
-pressure family, neighborhoods, C08). HEADLINE MIRAGE CAUGHT: every
gap-gate >=40% row jumped ~+$350k -- forensics traced it to ONE day
(CIIT 2026-03-09: a $1,592.50 one-minute wick vs $31.50 open, 50x for
one bar -- data glitch, untradeable). Excluding it, gate widening is
~neutral: THE 20% CALM-GAP STANDS. TODO hardening: one-bar-wick hygiene
guard in simulate_trades peak/scale-out logic. Controls behaved:
X229 shuffled-pressure showed the same Y1-mirage/Y2-negative signature
(validates the both-years rule); X230 lag = noise. Pressure family:
entry-confirmation gates are CATASTROPHIC (-$450k+; breakouts happen
before pressure turns); pressure EXITS weak; pressure-modulated TRAIL
is the real winner -- X219 (trail 12% when P<=-0.3, 30% when P>=+0.3,
N=10min, 20k-share floor) +$48k/2yr, X218 tighten-only +$31k, both
0 negm. C08 (1PM exits, user signed off) +$62.5k/2yr.
STACKING: C10 = C02+pressure-trail: Y1 +$378,765 / Y2 +$481,805
(0 negm both). C11 = C08+pressure-trail (1PM exits): Y1 +$390,687 /
Y2 +$536,350 (+$927k/2yr, 1 negm Y2); C12 = C11@10bps: +$355,894/
+$501,571 (92% retained). C11 ADOPTED as champion (1PM signed off);
C10 is the strict-noon fallback. Sizing note: vol_frac 0.30 (X236)
+$36k more but realism thins beyond 20% -- not adopted. Avg C11 year
= +$463,519 = 37% of the 5x target ($1.25M/yr); next levers = the
deferred fetch queue (coverage/days) + wick-hygiene + C03-rank combo.

## Paper Day 1: No Trade, Two Real Bugs Fixed (2026-08-04)

First live paper session (C02, 7AM-noon). Result: COMPLIANT NO-TRADE
DAY -- 10 candidates, all rejected for cause (halal 3 incl AMIX which
ran +163% on a $2M mcap with 221% cash ratio; exhausted-gap 1; rvol 3;
leveraged ETN/ETF 3). $0 P&L by rule. LESSONS THAT PAID: (1) the
Robinhood scanner %change filter takes RATIO units -- the saved scan
("10" = +1000%) had NEVER fired; fixed to 0.10. Sanity-check scanners
against a known-gainers source before trusting empty results. (2) rvol
source-of-truth: RH 30-day rvol reads high vs our backtested 50-day
measure (ATPC: 204x vs 1.1x) -- our engine governs. (3) The halal gate
eliminating the day's biggest movers is by design and already priced
into the two-year backtests. Infra added: plan/paper_watch.py (1-min
position checks with C02 exits, run under a Monitor on entry) and
5-min scan cadence. Full log: data/paper/2026-08-04.md.

## C02 Adopted As Live Default (2026-08-04)

C02 = AX20 + three changes: (1) 5-min opening range (orb_bars 5, was
15), (2) size up to 20% of trailing 10-MINUTE volume (was 10%/5min),
(3) premarket-high stop-buy as an extra one-shot entry trigger.
Y1 +$357,311 / Y2 +$455,297, 0 negative months both years, win rate
80%/76%, profit factor 11.2/6.4, max DD -$7.8k/-$13.1k, survives 10bps
slippage (C07 +$330.7k/+$428.8k). Defaults + skill updated.
WHY NOT THE BIGGER NUMBERS: C04 "uncapped" (+$877.8k/2yr) assumes
instant full-size fills at printed prices on thin tape -- its extra
edge comes exactly from the days the liquidity cap used to bind, i.e.
where the zero-market-impact assumption is most false. It is recorded
as a THEORETICAL CEILING, never a plan. C06 "exits to 1PM"
(+$840.0k/2yr, +$482k Y2) is real money but relaxes the user's 7-noon
window rule (entries still <=noon; holds runners to 1PM) and carries
slightly worse risk (1 negm Y2, deeper DDs). It stays on the shelf
PENDING USER SIGN-OFF; if approved, next test = C02+1PM ("C08").
Paper trading with C02 begins live 2026-08-04.

## X100 Campaign: 79 Experiments, New Champion C02 (2026-08-04)

Goal 5x/yr (~$1.25M) at fixed $15k, same-day, halal, 7-noon. Ran 79 of
100 planned single-change experiments (21 fetch-hungry ones deferred);
anchor X091 reproduced AX20 exactly. Guardrails: both-year positive,
combined >= +$30k, beat |X094 random-rank control| (=$36k noise floor).
PASS: X086 uncapped size (+$197.5k, fill-realism caveat), X031 orb5
(+$79.6k), X085 vol_frac 0.20 (+$66.9k), X064 exits-1PM (+$53.1k,
needs sign-off), X087 vol window 10min (+$52.8k), X084 vf 0.15, X032
orb10. KILLED BY Y2: X026 calm-gate removal (Y1 +$201k but Y2 -$53k --
the calm-gap rule is real risk control, not regime luck). Honesty tax
of day-rank vs causal premarket rank: small and Y2-POSITIVE (X001/X092
+$16.9k combined) -- causal ranking is fine to adopt live.
STACKING (all zero negative months both years):
  C01 orb5+vf0.20/10min:      Y1 +$346,496 / Y2 +$427,295
  C02 = C01 + pm-high buy:    Y1 +$357,311 / Y2 +$455,297  <- CHAMPION
  C03 = C01 + pm$vol rank:    Y1 +$344,856 / Y2 +$454,682
  C04 uncapped ceiling:       Y1 +$394,761 / Y2 +$482,998 (fills!)
  C05 C01+10bps slip:         Y1 +$321,761 / Y2 +$400,719 (robust)
  C06 C01+exits-1PM:          Y1 +$357,991 / Y2 +$482,047 (sign-off)
C02 vs AX20: +$112k/+$141k per year; Apr-2025 (only losing month ever)
turns POSITIVE in C01/C02. The whole gain = enter faster (5-min opening
range), size bigger within liquidity (20% of trailing 10-min volume),
buy premarket-high breaks. Path to 5x now runs through the deferred
fetch experiments (deeper walk, fallback re-picks, splits) + possibly
C06's extra hour. C07 = C02 + 10bps slippage: Y1 +$330,650 / Y2 +$428,802,
still 0 negm both years -- champion is robust to costs.

## Renamed + AX20 Made Live Default (2026-08-04)

penny-stocks.py -> day-trading.py and NOTES-PENNY.md ->
NOTES-DAYTRADING.md (universe is no longer penny-capped; the system
trades any stock >= $2). All 22 referencing files updated; backtests
reproduce byte-identically post-rename. AX20 spec is now the module
default: SURGE_WINDOW_MIN 10->50 (1-min-bar granularity, was a
5-min-era relic); price ceiling off, trail 20 / stop 8 / scale-out
1/3@+25%, calm-gap 20, top-1 x $15k, 7-noon. simulate_trades gained 9
default-off kwargs for the X100 campaign (breakeven_at, time_stop_min,
atr_trail, atr_stop, add_at, extra_break_high, slippage_bps,
orb_fill_mode, scale_out_2) -- verified no-op when unset (AX20
reproduces exactly).

## BOTH TARGETS MET -- AX20 Widened Universe (2026-08-04)

AX20 (plan/penny_ax21_recycle.py --pick walk --gapfile gappers2
--trail 20): identical machine to AX11b (pt-halal, calm-gap<=20 walk-8,
top-1 x $15k, 7-noon, ORB15+patterns, trail 20/stop 8/scale-out
1/3@+25%) with ONE change -- the universe. Discovery (penny_ax20_
discover.py) dropped the hidden $75 close cap and the stale
universe.json list: any clean ticker >= $2, day-high >= prev_close
x1.10, rvol >= 5x/50-session. RESULTS:
  Y1 +$244,899  125d  +$1,959/d  0/12 neg months  (target +$200k MET)
  Y2 +$314,057  142d  +$2,212/d  1/10 neg months  (target +$200k MET)
Y2 monthly: Oct +39.3k Nov +43.8k Dec +26.0k Jan +32.9k Feb +28.5k
Mar +21.8k Apr -4.0k May +60.0k Jun +35.3k Jul +30.5k. The Jan-Mar
2025 "desert" (-$2.4k/-$0.3k/+$4.7k in every capped config) became
+$83.2k: mid/large-cap earnings gappers were there all along -- the
$75 discovery cap was silently deleting them. User thesis vindicated:
there was no cold year, only a filtered-out universe. ADOPTED as the
new default spec (AX20): trail fixed at 20% (no thin-supply conditional
needed -- 142/194 sessions traded). Fixed along the way: axb.api()
throttle bypass (halal-cache 429 poisoning risk; audited clean).
Recycling (AX21) confirmed dead and stays out. Next candidates, not
run: AX22 cond-trail or recycling on gappers2 (marginal, both years
already over target).

## Recycling Tested Dead (2026-08-03)

User approved: $15k = max at risk at any MOMENT (recycling allowed),
any price >= $2 (no $75 cap), window stays 7AM-noon. AX21 campaign on
the recycling half (plan/penny_ax21_recycle.py, honest event-ordered
engine; commit-to-top-pick then earliest-next causal event; verified
exact reproduction of AX11b +$211,585/+$105,474 in --pick walk mode).
Results, old universe: earliest-entry picker k=1 collapses to
+$81k/+$57k (pick QUALITY >> entry speed); commit-then-recycle k=0
(unbounded) = Y1 +$210,579 / Y2 +$103,922 -- SLIGHTLY BELOW baseline
both years. Cause: cross-symbol fills occupy capital when the committed
pick's own (profitable) re-entries fire -> displacement. The top pick's
re-entry stream already saturates the morning window. RECYCLING IS A
DEAD LEVER at this window/universe. Remaining lever: AX20 widened
universe (no $75 cap, mid/large-cap earnings gappers; discovery
running, gd responses now cached under data/massive/gd/).

## Target Campaign Verdict (2026-08-03)

Goal: +$200k BOTH years at $15k/day, halal fixed, all else flexible.
AX11 (point-in-time halal, yf coverage): Y1 +$164,855 (88d, +$1,873/d, 0
negm) / Y2 +$89,832 (75d, +$1,198/d) -- HONESTY BOMBSHELL: prior
backtests included picks NOT halal on their trade dates (ratios are
mcap-denominated and prices moved); pt-halal is the correct compliance
AND live screening is already point-in-time-correct (uses today's data).
AX11b (Massive financials conservative-bounds + pt shares, walk-8):
Y1 +$211,585 (135d, +$1,567/d, 0 negm) = Y1 TARGET MET honestly;
Y2 +$105,474 (111d, +$950/d). AX19 family (supply-conditioned trail 30%
when trailing-10-session calm supply thin): walk-12 Y2 +$124,548 (1 negm!)
but Y1 $192k; walk-8 thresh 1.0: Y1 +$199,999 / Y2 +$120,648.
FRONTIER: max-Y1 = AX11b ($211.6k/$105.5k); balanced = AX19c-1.0
($200.0k/$120.6k, two-year best $320.6k). ADOPTED SPEC: AX19c-1.0
(pt-halal, no sector filter, calm-gap<=20 walk-8, top-1 x $15k, 7-noon,
ORB15+patterns, trail 20 (30 when thin supply), stop 8, scale-out
1/3@+25%). HONEST CEILING: Y2 $200k NOT reachable -- the remaining
~$80k gap lives in Jan-May 2025 where morning-gapper alpha was ~zero at
ANY pick quality; closing it at $15k/day long-only same-day would
require curve-fitting noise (the exact overfit the Y1 calibration
episode punished). Recommendations: (1) paper-trade the adopted spec;
(2) productionize Massive-financials halal for backtest parity (live is
already correct); (3) for thin months, a SECOND uncorrelated same-day
strategy (e.g. large-cap halal momentum) is the legitimate path to
smoothing income, not more knobs on this one.

## Round Two Verdict (2026-08-03)

AX round 2 complete: 44 runs, registry section 13. ADOPTED AX18 (stop
5->8% + bank 1/3 at +25%): Y1 +$209,935 / Y2 +$104,174 with the best Y2
consistency yet (2 neg months); both components improved both years
independently. DEFAULT_STOP_PCT=8, DEFAULT_SCALE_OUT_AT=25 now live.
Structural findings: top-N concentration N=1 optimal both years (calm
supply caps ~4/day); afternoon 2-8PM conclusively dead (Y2 -$13k);
indicator entries (VWAP/EMA) rejected 3rd time; sector filter INERT at
top-of-book both years (drop-it and keep-it identical) -- the monster
autopsy's 87% blockage is almost all halal-timing, making AX11
(point-in-time halal) the biggest remaining lever; trail 25-30% beats 20%
in the weak year only (+$108-114k vs $95k) -- regime-conditional trail
width is the second remaining idea. Two-year default now: Y1 +$210k,
Y2 +$104k = +$314k across regimes at $15k/day.

## Adaptation Series Launched (2026-08-03)

User thesis: no such thing as a cold year -- news + hot sectors always
exist; the strategy must adapt. Launched the AX experiment series
(unique permanent IDs AX00-AX10, registry section 12) on BOTH years.
First five runs: AX01 dynamic monthly sector rotation improves Y1
(+$214,849) and Y2 efficiency (+$681/day) but trades fewer Y2 days;
AX03 adaptive-gap, AX05 equity-throttle worse; AX07 day-2 tiny help;
AX09 two-shot never triggers. NONE broke the Jan-May 2025 desert (4
negative months in all). Remaining queued: AX02 supply throttle, AX04
premarket structure scoring, AX06 scale-out ladder, AX08 adaptive trail,
AX10 news-tier gate -- these target the desert via trade quality and
profit-locking rather than day selection.

## Year Two Verdict (2026-08-03)

Year-2 backtest complete (Oct 22 2024 - Aug 1 2025; Massive's 2-year
rolling history forced the late start; 3,992 gapper days -> 664 after
filters). RAW table (old uncorrected sizing) looked barren: best config
+$26k, B3 full-day configs NEGATIVE, worst days -$8.3k..-$10.1k -- 2024-25
was a genuinely cold gapper year. CORRECTED re-sim, $15k/day:
C1 top-1 +$32,015 (+$198/d) but C1+CALM-GAP = +$94,852 (+$597/d) -- the
calm-gap rule TRIPLED the cold year despite being derived 100% from
year-1 data: a clean out-of-sample validation. CAP14+calm-gap +$76,912 <
C1+calm-gap: the no-ceiling choice cross-validates too. TWO-YEAR RECORD
of the live default (C1 top-1 x $15k + calm-gap): Y1 +$206,466
(+$1,007/d, 0 neg months), Y2 +$94,852 (+$597/d, 4 neg months of 10,
worst month -$10,114). ~ +$300k over ~23 months on $15k/day deployed.
Honest caveats: year-2 has survivorship bias (delisted 2024 gappers
absent from universe/verdicts) and current-snapshot halal/sector; worst
months -$10-15k are real -- size for them. The strategy is now validated
across a hot year AND a cold year with every rule earning its place.
Y2 MONTHLY DETAIL (C1+calm-gap): Oct24 +$31,105 in just 6 traded days
(incl. the year's best day +$29,881 -- ONE day = 31% of the annual
profit); Nov +$17.1k; Dec +$20.1k; then a FIVE-MONTH DESERT Jan-May 2025
netting -$22k (worst Apr -$10.1k); Jun +$13.8k; Jul +$34.7k. Median day
-$0.73, 50% win days, 22 days >=+$2k carry the year. Cold-year trading
is: three good quarters of patience, one brutal stretch, and a handful
of monster days you must be present for.

## Four Feature Test (2026-08-03)

Tested the pattern-study features as PROSPECTIVE filters vs both
baselines (full year, $15k/day, monthly avg-daily tables in chat/registry).
BASE1 C1 plain: +$193,783 (+$897/d, 2 neg months). BASE2 C1+calm-gap
(current default): +$206,466 (+$1,007/d, 0 neg months). F1 calm+premarket
$vol>=200k: avg rises to +$1,147/d BUT total falls to +$160,578 with 3
negative months -- the volume minimum cuts quiet-open intraday developers,
i.e. exactly the golden pattern. F2 calm+entry gate 15%: +$164,612,
worse everywhere. F3 all combined: +$122,097, 4 neg months, worst.
VERDICT: high day-gain and high rvol are OUTCOMES of winner days, not
7AM-predictors -- filtering on their real-time proxies removes winners
before they reveal themselves. Only the calm-gap feature is genuinely
predictive. Current default (BASE2) stands: the study's value was the
calm-gap rule + knowing the other features are descriptive only.

## Calm Gap Rule (2026-08-03)

Pattern study of the $2k+ days (52 days summing +$294k vs year total
+$194k -- the other 164 days NET LOSE ~$100k; day records saved to
data/massive/c1_top1_day_records.csv). DISCRIMINATORS: $2k+ days ride
picks whose full-day gain reaches +100-300% (that bucket alone +$124k/65d;
+300% bucket +$64k/8d, median +$8,440/day; while +10-25% gainers NET
NEGATIVE); rvol 28x vs 16x; sector irrelevant. THE tradeable signal:
7AM GAP INVERTS -- winners open CALM (median +3.4% gap) then explode
intraday; days opening +35-60% at 7AM are exhausted overnight moves
(median -$2,111/day, bucket -$12.5k/yr). Real-time-knowable filters
tested: skip gap7>20% -> +$200,116 (+$1,299/day, 0 neg months);
premarket-$vol cap HURTS; raising the 10% entry gate to 20/30% DESTROYS
profit (10% gate is right). ADOPTED: SUBSTITUTE variant (walk top-4 to
the first pick with 7AM gap <= 20%): +$206,466/yr, +$1,007/day, 205
traded days, ZERO negative months (worst Nov +$815; Feb flips -$7k ->
+$18k; Jul +$48k). MAX_GAP_AT_7AM=20 constant + skill day-pick updated.
LESSON FOR $2k/day GOAL: profits come from catching intraday developers
early and riding; avoiding exhausted gaps is worth ~+$100k/yr of
avoided bleed. Threshold is a plateau (20-30% both work), not knife-edge.
Caveat: derived+tested on year-1 only; validate on year-2 when done.

## Fifteen K Constraint (2026-08-03)

User: total deployment is $15k/DAY (not top-2 x $15k). Tested C1 under the
constraint: top-1 x $15k = +$193,783/yr (+$897/day, median +$35, worst
-$5,127, 2 neg months) vs top-2 x $7.5k = +$142,863 (+$608/day, smoother:
0 neg months, worst -$5,669). ADOPTED top-1 x $15k (36% more profit,
shallower worst day than the $30k top-2 version's -$11.5k).
TOP_GAPPERS_PER_DAY=1. The earlier +$259k figure required $30k/day.

## C1 Default Adopted (2026-08-03)

Made C1 the live default per user sign-off: PRICE_MAX = inf (ceiling
REMOVED; $2 floor stays), TOP_GAPPERS_PER_DAY=2 and noon window unchanged,
Robinhood saved scan now Last > $2 (no ceiling), skill updated. Evidence:
full-year corrected backtest C1 +$259,341 (+$1,104/day, 56% win days,
ZERO negative months, worst -$11,543) vs $14-cap +$163,989 (3 negative
months, median day NEGATIVE). Identical buy/sell mechanics -- only the
pick universe changed. Full default now: $2+ any price, no float limit,
upward sectors, halal-first, dual news, 7AM-noon, top-2 x $15k, ORB(15min)
+ all-bullish 1-min patterns, trail 20%/stop 5%, participation cap 10% of
trailing 5-min volume, flat by noon. NOTE: adopted on ONE year of
evidence at user direction; year-2 cross-validation still running and
will be reported against this default.

## C1 Deep Comparison (2026-08-03)

C1 vs A2cap14 vs A2cap16, corrected params, full year, top-2 x $15k.
Mechanics are IDENTICAL (ORB-15min + any bullish pattern, trail 20/stop 5,
7-noon, same gates) -- the ONLY difference is the price universe: C1 has
no ceiling ($2+), A2 restricts to <=$14/<=$16. RESULTS: C1 +$259,341,
cap14 +$163,989, cap16 +$161,392 (cap level $14 vs $16 is nearly
irrelevant, +-$2.6k; the CEILING ITSELF costs ~$95k/yr). Idle days: C1 16
(8 no-candidate + 8 no-trigger) vs cap14 38 (19+19) -- the ceiling
excludes whole days. Loss days: C1 104/235 (44%) vs cap14 109/213 (51%),
cap16 113/216 (52%). Monthly avg-daily: C1 never negative (worst month
Feb +$123/day; best Jul +$2,589/day); cap14 3 negative months (Sep
-$597/day, Dec -$236, Feb -$420); cap16 4 negative months. WHY: in cold
small-cap months the cheap qualifying gappers are junk while pricier
($16-75) movers still trend -- the cap forces trading junk or sitting
out; C1 upgrades to the genuinely strongest movers. Awaiting year-2 to
adopt C1 as default.

## Granularity Bug Fixed (2026-08-03)

User challenged the year's low per-day avg ("we trade hot gappers, should
be ~$1.5k/day") -- and was RIGHT. Diagnostic on identical days (Jun-Jul):
1-min as-run +$930/day, resampled 5-min +$1,968/day, corrected 1-min
+$1,409/day. THREE parameters silently change meaning with bar size; the
year ran 1-min while calibration ran 5-min: (1) liquidity cap 10% of a
1-MIN bar = ~5x smaller positions (the dominant effect); (2) trail-20 on
1-min stops out on noise 5-min smooths (5-min numbers were OPTIMISTIC --
coarse bars flatter trailing exits; live truth is nearer the 1-min path);
(3) ORB 3 bars = 3 min vs 15. FIX: participation cap now measured over a
trailing window (vol_frac_window param; 10% of trailing 5-MIN volume) and
granularity-equivalent ORB/surge (orb_bars=15, SURGE_WINDOW_MIN=50 on
1-min data). CORRECTED FULL YEAR (Aug25-Aug26, $15k, 1-min realism):
C1nocap +$259,341 (+$1,104/day, worst -$11,543); B2cap14 +$174,535
(+$847/day, worst -$5,689); A2cap14 (default) +$163,989 (+$770/day);
CAP14t1 +$141,978; V2a_t1 +$141,207. Top-2 again beats top-1 at noon
(that flip was also a sizing artifact). RECONCILIATION: ~$1.5k/day is the
HOT-month rate (hot window corrected: +$1,409/day); full-year averages
$770-1,104/day because Aug-Mar is genuinely colder -- regime, not bug.
Year-2 cross-validation still running with old settings; will re-sim from
cache with corrected params on completion.

## Full Year Results (2026-08-03)

FULL YEAR Aug 2025 -> Aug 2026 on Massive 1-min bars (5,211 gapper
stock-days discovered, 1,815 symbols, 232 qualifying days after filters,
$15k/pos). RANKING FLIPS the calibration-window conclusions:
C1nocap (NO ceiling, no float, noon, top-2): +$174,134 (+$735/day, worst
-$8,809) -- nearly DOUBLE the reigning champion. B2cap14 (7-2PM top-1):
+$129,759 with the SHALLOWEST tail (-$5,353). CAP14t1/V2a_t1 (top-1 noon):
+$108-112k BEAT the top-2 versions (+$94-96k): the second gapper LOST
money across the full year (cold months). Current default A2cap14 ranked
8th/10 at +$95,925. A2cap10 last (+$60k). Monthly shape (A2cap14): Apr-Jul
2026 made +$111k while Aug 2025-Mar 2026 netted -$15k (5 negative months,
worst day -$8,809 vs -$2,142 seen in calibration) -- the Jun-Jul
calibration window was the hottest stretch of the year and overfit BOTH
the ceiling and top-2 conclusions. LESSONS: (1) 8-week windows are regime
samples, not truth -- every config decision now needs full-year evidence;
(2) the $16 ceiling helped ONLY in the hot window; over a full year the
big-priced gappers carried the cold months; (3) top-2 doubles exposure in
bad regimes. DEFAULT DECISION PENDING year-2 (2024-25) cross-validation
running now -- do not re-default on one year alone.

## Massive Data Integrated (2026-08-03)

User subscribed to Massive (Polygon.io rebrand); key stored in Credential
Manager as MASSIVE_KEY. Probed capabilities: BOTH api.polygon.io and
api.massive.com work; 1-MIN bars confirmed >= 1 year deep (Aug 2025
verified); REAL premarket volume (FCUV Jul 31: 690 bars, 17.8M premarket
shares vs yfinance's zeros); grouped-daily endpoint returns the ENTIRE
market (12,408 tickers) in one call; no rate-limit pushback (paid tier).
New module trading/massive.py (grouped_daily, minute_bars; 429 retry).
This REPLACES the data ceiling that forced 5-min bars and 60-day windows:
full-year 1-min backtests now possible, and the news-era estimates
("Jan-Apr not backtestable") are obsolete. plan/penny_year_backtest.py:
full year Aug 2025 -> Aug 2026, whole-market discovery (~315 grouped-daily
calls incl. 50d warmup), sector+halal filters, top-10 configs from
CONFIGS-TESTED.md simulated on 1-min bars at $15k. Running -- results in
the next note.

## Champion Default Adopted (2026-08-03)

Made top-2 gappers + $14 cap the live default per user sign-off:
PRICE_MAX 16 -> 14, new TOP_GAPPERS_PER_DAY=2 constant, Robinhood saved
scan band updated to $2-14 server-side, skill updated (trade the top TWO
qualifying gappers, $15k each, up to $30k deployed). Full default now:
$2-14 band AT ENTRY, no float limit, upward sectors, halal-first gates,
dual news, 7AM-NOON, ORB + all-bullish entries, trail 20%/stop 5%, 10%
bar-volume cap, flat by noon. Measured +$55,495 over the Jun-Jul window
(+$1,734/traded day, worst -$2,142), annualized ~$333k hot-tape.
ALSO: created CONFIGS-TESTED.md -- registry of ALL ~240 tested
configurations (grids, sweeps, matrices) with results + reproducing
script, so any config can be re-tested; untested queue at the bottom
(A2+cap10 combo, surge 3%, multi-year Polygon validation).

## Price Cap Matrix (2026-08-03)

Tested caps $16/$14/$12/$10 on the top-3 performers (plan/
penny_cap_matrix.py). CHAMPION OVERALL: A2 + cap $14 (noon, no-float,
top-2 gappers, $2-14): +$55,495 total, +$1,734/day, worst -$2,142 --
best total ever tested, near-best avg. A2+cap10: best avg (+$1,780) but
-$4k total. The $12 dip recurs in all three configs (real, not noise:
$10-12 stocks like BIYA/QTTB entries get chopped by a $12 cap while
$12-14 names stay profitable -- cap $14 keeps them, cap $10 trades
cheaper faster movers). Full-day B3 prefers cap $16 (afternoon needs the
pricier names); B2 (7-2PM) also peaks at $14. Pattern: tighter caps help
morning-only configs (cheap gappers move most in the morning), hurt
longer windows. Annualized A2+cap14 ~ $333k hot-tape at $15k/pos x
top-2 (up to $30k deployed). Awaiting user pick for default adoption.

## V2a Adopted Plus (2026-08-03)

DROPPED rule 8 (float<=16M) per user sign-off and made V2a the live
default: MAX_FLOAT=None in day-trading.py (float displayed as info,
rule8 always passes; set a number to re-enable), Robinhood saved scan
updated to 3 filters (float filter removed server-side), skill updated.
Second-generation sweep from the new base (plan/penny_v2a_variants.py),
one change each: A2 top-2 gappers/day = BEST TOTAL +$55,373 (+$1,678/day,
20 days >=+$1k, worst unchanged -$2,142 -- deploys up to $30k);
CAP10 ($2-10 price cap) = BEST EFFICIENCY +$1,748/day (+$47,197 total on
27 days, same worst) -- cheaper gappers move more in %; CAP14 marginally
above base both metrics; CAP12 dip = sample noise (nonmonotonic).
B2 (no-float 7-2PM) +$53,606 but worst -$3,750; B1 (full day, entries
stop at noon) ~= V2a (afternoon confirmed worthless a second time);
A1 (7-11AM), A3 (stop 8%), C3 (11AM entry cutoff) all worse.
Candidate next default: A2 (if capital allows 2x) or CAP10/CAP14 tweak;
combo A2+CAP10 untested (would be 2 changes). Awaiting user pick.

## Nine Variant Sweep (2026-08-03)

Three one-change variants each of V2/V3/V6 (plan/penny_v_variants.py; added
entry_cutoff param to simulate_trades: no NEW entries after a time, exits
continue). RESULTS (days/total/avg/worst): CHAMPION = V2a (noon + NO FLOAT
LIMIT + keep $16 ceiling): 31d +$47,571 +$1,535/day worst -$2,142 -- beats
every prior config on BOTH total and per-day avg at V2-level risk.
V2b (1PM cutoff) +$37,799 (+$1,350) but worst -$2,892; V3a==V6a (band,
no-float, full day) +$44,607 (+$1,174); V6b (no-ceil no-float noon)
+$41,236 (+$1,213); V3c (entries stop at noon, exits to close) +$33,812 ~=
V3 base (afternoon ENTRIES are ~neutral; afternoon is only good for
letting winners run, slightly). Trail 25% hurt in ALL THREE bases (-$11k
to -$12k each) -- third independent confirmation that trail 20% is
optimal. Float-limit removal is the single most valuable relaxation
(+$15k over V2) BUT it drops user rule 8 (float<=16M): bigger-float names
absorb $15k without the vol-cap binding and their halal pass-rate is
higher. Annualized V2a ~ $285k hot-tape at $15k fixed. AWAITING user
sign-off to drop rule 8 and adopt V2a as default.

## Noon Window Default (2026-08-03)

Made 7AM-NOON the default penny trading window per V2 results (user
sign-off): NEWS_END 10:00 -> 12:00 in day-trading.py (the constant defines
the trading window everywhere -- _window_data, backtest, all experiment
commands). All docs/skill updated: buy AND sell inside 7AM-noon, force-flat
at NOON. Skill's entry section also refreshed to the current default
(all-patterns + ORB, trail 20%/stop 5%, ~$15k capped at 10% bar volume).
Measured basis: V2 +$32,453 over 8 weeks (+$1,202/traded day, 14/27 days
>= +$1k) vs 10AM cutoff +$21,084 -- the 10:00-12:00 stretch carries the
morning gappers' second leg. Annualized ~$190k at fixed $15k sizing (hot-
tape assumption; cold-tape floor ~half).

## Expansion Variants Tested (2026-08-03)

Seven rule-relaxation variants + Ross Cameron comparison, all real intraday
data (Jun 4-Jul 30 full-session set; May RH-cache days excluded since the
full-day fetcher can't reach them), $15k/position, 10% vol cap, one top
gapper/day, halal always on (plan/penny_expand_test.py, penny_expand2.py,
ross_cameron_test.py). RESULTS (days/total/avg-per-day/worst):
V0 baseline $2-16 7-10AM: 18d +$21,084 +$1,171 -$1,500
V1 no $16 ceiling 7-10AM: 21d +$19,660 +$936 (WORSE -- pricier gappers
displace better penny picks and move less in %)
V2 $2-16 7-NOON: 27d +$32,453 +$1,202 -$2,142  <-- BEST avg AND +54% total
V3 $2-16 full day: 32d +$35,184 +$1,100 -$2,963 (afternoon chop dilutes)
V4 no-ceil full day: 35d +$31,073 +$888
V5 NO FLOAT $2-16 7-10AM: 22d +$24,313 +$1,105 (more days, diluted avg)
V6 ALL relaxed: 38d +$39,739 +$1,046 -$3,750 (highest total, worst risk)
ROSS-HALAL (documented Warrior playbook: micro-pullback break of prior
candle high after 1-3 bar flag, stop at pullback low, half out at 2R,
breakeven+trail, 7-11:30, $2-20): 19d -$14,988, 5/19 win days, worst
-$4,286 -- LOST badly AS MECHANIZED ON 5-MIN BARS. Fair caveat: his style
is built for 1-min bars + discretionary tape reading; this shows his
mechanics don't transfer to 5-min automation, not that Ross loses.
RECOMMENDATIONS: keep $16 ceiling, keep float<=16M for best $/day (relax
only to scale total $ at more risk), EXTEND window to noon (single best
change: +$1,202/day avg, 14 of 27 days >= +$1k). Awaiting user sign-off to
make 7-12 the default (changes the 'flat by 10AM' rule to 'flat by noon').

## Position Size Scaling (2026-08-03)

User goal: +$1,000/day. Added max_vol_frac liquidity cap to simulate_trades
(shares <= frac of entry-bar volume; used 10%) and plan/penny_scale_test.py:
sizes $1k-$30k x top-1/top-2 gappers over the YTD simulated days with the
ORB-combined default. RESULTS: $15k/trade -> avg +$1,156/TRADED day (12/24
days >= +$1k, worst -$1,500); $30k/trade top-2 -> +$2,088/traded day =
~+$1,044/EVERY trading day incl. no-trade days ($56,379 over ~54 days).
Liquidity cap bites at size: $30k yields 18.8x the $1k profit (not 30x) --
the curve flattens beyond ~$30k, confirming the micro-cap ceiling. Losses
scale identically (worst day -$3,033 at $30k). PDT rule requires $25k
equity for daily trading anyway, matching the sizing floor. Slippage not
modeled -- treat as upper-bound-realistic.

---

## ORB Entry Added (2026-08-02)

Diagnosed all 15 zero-trade days (plan/penny_orb_test.py) and added an
Opening-Range-Breakout entry. Zero-trade root causes: (a) 3 days NEVER in
the $2-16 band during the window (CPHI +2009% ranged $0.81-1.20, TOPP,
BIYA Jun30 -- structurally untradeable, moves happened after 10 AM or
sub-$2); (b) 5 days never printed +10% vs prev close during the window
(INDP, PN, NTHI, WYY, TTRX -- often marginal, e.g. 9.75 vs 10.68 needed);
(c) 7 days had the move but dip-reversal pattern sequencing missed it (HQ,
RTB, NDRA, YDES, EGG, FIEE, YAAS). ORB fixes class (c): OR = first 3
volume-printing 5-min bars, stop-buy on break of OR high (ratcheted after
gated/failed breaks), same gates (band + 10% at entry) and exits (trail
20% / stop 5% / window flatten). RESULTS on the 34 YTD simulated days
(fixed $1000): A dip-reversal only +$1,594 (37t); B ORB only +$1,581
(19t); C COMBINED +$2,224 (42t) = +39% over default. Recovered from $0:
RTB +$288, EGG +$301, NDRA +$36; ATPC Jun18 +$246 vs +$3. ADOPTED:
simulate_trades(orb=True, orb_bars=3) integrated (ORB fires from any flat
state, dip-machine still runs) and is now part of the penny backtest
default; verified integrated == standalone (EGG +$301, RTB +$288). YAAS
+590% still uncaptured (no valid trigger) -- some days stay unplayable.
Classes (a)/(b) are rule-structural, not fixable without changing band/
window/10% rules.

## Upward Sector Expansion (2026-08-02)

Sector trend check via ETFs (1y return > 0 AND price > 200-SMA): UP =
Technology +37%, Energy +44%, Healthcare +26%, Industrials +22%, Basic
Materials +18%, Real Estate +13%, Consumer Defensive +9%; EXCLUDED (below
200SMA) = Consumer Cyclical, Communication, Utilities. plan/
penny_backtest_ytd.py reran discovery Jan 1 -> Aug 2 with the expanded
7-sector keyword list: 2,903 gapper stock-days (1,200 symbols) -> 320
stock-days / 111 symbols after float+halal+upward-sector -> 130
one-gapper-per-day days YTD (~3x the tech+health-only funnel). SIMULATED
(real intraday, compounding, May 15 -> Jul 30, 34 day-sims of which 19
traded): $1,000 -> $3,564.01 (+256.4% in ~2.5 months). New-sector
contributions real: QTTB +$749, ADVB +$887 day, ATPC +$161; new losses
CLRO -$231, AMST -$154. 96 qualifying days (Jan-Apr + thin days) have NO
intraday data anywhere (RH 5-min reaches ~May 5) -- the script's naive
extrapolation ($7.2M) is GARBAGE (uses traded-day-only avg +8.26%/day,
ignores zero-trade days and liquidity) and must not be quoted. Defensible
estimates for Jan 1 -> today: fixed-$1000 sizing ~ +$46/qualifying-day x
130 days ~ +$6,000 (+600%); frictionless compounding math says ~$130k but
is physically impossible -- 0.5-16M float stocks cannot absorb positions
much beyond $10-30k without moving the price, so compounding saturates in
the low tens of thousands. Honest headline: +256% real simulated 2.5
months; YTD-from-Jan estimate several hundred %, capital-capped by
micro-cap liquidity.

## Trail Default Sensitivity (2026-08-02)

Made trail20+all-patterns the penny DEFAULT (DEFAULT_TRAIL_PCT=20,
DEFAULT_STOP_PCT=5; backtest command now uses it; halal + up>=10% held
fixed per user). Then plan/penny_sensitivity.py: one-parameter-at-a-time
sweep over the same 60-day qualifying days (26 variants; note a few May
days aged out of yfinance's rolling 5-min window so the sweep baseline is
+$1,525 not +$1,810 -- comparisons across variants are apples-to-apples).
RESULTS vs baseline: only 2 variants improved: (1) trade top-2 gappers/day
+$130 (+8.5%) -- but that deploys up to $2k/day, it's capital scaling, not
a better strategy per dollar; (2) surge 3% (stricter arming) +$47 -- within
noise. Band ceiling $20/$30: zero effect (no entries above $16 occur).
EVERYTHING else hurts, often badly: trail 10-15% and stop 3% destroy the
edge (-$1,150 to -$1,341: tight exits sell the runners -- the whole edge
is letting winners breathe); max 1 trade/day -$1,256 (first entry often
stops, re-entry carries the day); vol-confirm ON -$354 (blocks explosive
marubozu entries); deeper dips -$196..-$340 (late entries); stricter rvol
day-filters -$413..-$566 (drops profitable days); hammer-only -$66 with
only 15 trades. CONCLUSION: the trail20/stop5/all-pattern baseline sits on
a flat optimum plateau -- keep it; the only real lever is capital (top-2
gappers) which scales P&L ~linearly; consider surge 3% only after more
sample accumulates.

## Robinhood Backfill Results (2026-08-02)

Backfilled the 60-day backtest's missing days with Robinhood 5-min
extended-hours bars (real premarket volume) via MCP -> data/rh_bars CSVs +
plan/penny_backfill_rh.py. Findings per day: MANY "missing" days were dead
in the 7-10 AM window -- LINK/MCRP/SLBT/FIEE/SCYX had near-zero window
volume (their +10-285% daily moves happened AFTER 10 AM), MBAI/QUCY traded
sub-$2 all window, TGHL's +613% run happened from $0.32 BELOW the $2 band
(in-band part was chop, B config -$50). The 6 genuinely tradeable days:
PIII B +$577 (one trailing trade caught the 9:35 explosion $5.23->$7.80),
QTTB B +$476, BIYA B +$63, CPSH +$10, AMST B -$100, TGHL -$50.
Backfill totals: A +$15, B +$977. COMBINED 60-DAY RESULT: A calibrated
default +$308 (+30.8% on $1000); B trail20 all-pattern +$1,810 (+181.0% on
$1000). 7 small-gain days (+16-40%: CPSH 5-18, ARQQ, CHRN, SVCO, CLRO,
INLX, APLM) left unfetched, treated ~$0 -- justified by base rate: 5/5
fetched days in that gain class had dead windows. Lessons: (1) the missing
days DID hold the big money -- B nearly tripled from +83% to +181%; (2) the
7-10 AM window forfeits moves that happen later in the day (FIEE +285%
after 10 AM = $0 for us) -- window discipline costs real upside but is the
rule; (3) sub-$2 launches (TGHL, QUCY) are structurally untradeable under
the band rule -- the band forfeits sub-$2 rockets by design. News rule now
checks BOTH sources: Finnhub first, then Yahoo on no-hit (headline tagged
FH:/YF: to show which source fired).

## Sixty Day Backtest (2026-08-02)

plan/penny_backtest_60d.py: market-wide 60-day backtest of the FULL
methodology. Funnel: 5,400+ US common stocks (nasdaqtrader symbol files,
ETFs/warrants/units excluded) -> 1,218 gapper stock-days / 674 symbols
(band $2-16 reachable, day high >=10% over prev close, volume >=5x 50-day
avg) -> 80 stock-days / 40 symbols after float<=16M + hot sector + HALAL
(~94% of gapper symbols eliminated, mostly by sector+halal) -> 48
one-gapper-per-day days -> 28 days simulated (yfinance 5-min prepost only
reaches ~60 calendar days; 16 earlier days + a few thin-premarket days had
no intraday data -- including monsters TGHL +613%, PIII +256%, AMST +240%,
FIEE +285%: Robinhood 5-min could backfill these, results likely
UNDERSTATED). RESULTS ($1000/trade, 7-10 AM window, same-day flatten):
A calibrated default (hammer+volconfirm+strong_if_profit): 14 trades,
+$293.33 = +29.3% on $1000 in 2 months. B trail20+all-patterns: 30 trades,
+$833.22 = +83.3%. B's big days: ADVB Jul 23 +$325, YAAS Jul 30 +$285,
SLBT Jun 16 +$135, ADVB Jul 22 +$125; worst day only -$100 (CLRO Jul 2) --
trailing exits kept losses tiny while catching runners. A took few trades
(hammer patterns rarer on 5-min bars than the 1-min they were calibrated
on). CPHI's +2009% day: 0 trades both configs (out of band / no signal at
entry) -- even the best day is missable. Caveats: float/sector/halal are
TODAY'S snapshots (survivorship approximation), news rule skipped (not
backtestable), 5-min granularity, yf premarket volume=0 (vol-confirm soft
premarket). Both configs profitable over 28 A+ days: methodology validated;
trail-the-runner remains the clear winner.

## Halal Gate Added (2026-08-02)

UPDATE (later same day): gate order changed to put HALAL immediately
after the free rules (price band + 10% + rvol, all from one call) and
BEFORE float/sector/news -- per user: don't waste any data collection on
non-halal stocks. Order is now: free rules -> halal -> float+sector -> news.

Wired halal compliance into the penny screener as a lazy rule, ordered
cheap rules -> HALAL -> news (news only runs for halal stocks). Same
criteria as plan/full_screen.py + /halal-check skill: loans/mcap <=10%,
deposits/mcap <=10%, combined <=20%, haram revenue <5% (interest income /
annualized quarterly revenue, yfinance quarterly statements), plus a
haram-industry keyword screen (bank/gambling/alcohol/tobacco/defense/
insurance/lending/adult...); market cap from RH fundamentals cache first.
Screen table shows a halal column + NOT HALAL reason row with ratios.
LIVE FINDING: the gate failed BOTH of Friday's tradeable gappers -- SCYX
deposits 123.7% of mcap (biotech cash pile vs $48M mcap), TCX loans 321.9%
of mcap -- confirming that low-mcap gappers frequently breach the ratios
because the denominator (mcap) is tiny. Expect the halal gate to eliminate
many scanner hits; trading list will be much more selective. Note: ratios
use market cap per the user's established criteria (some methodologies use
total assets, which would pass more small caps -- not our rule).

## News Source Comparison (2026-08-02)

Robinhood MCP has NO news feed (all 53 tools checked; `search` resolves
tickers only). What it has instead: EARNINGS data -- get_earnings_calendar
(market-wide, 31-day window, am/pm timing, high-mcap filter) and
get_earnings_results (8 quarters est-vs-actual EPS per symbol; SCYX next
reports 2026-08-17 pm, tentative). Use for scheduled-catalyst discovery
("which penny biotechs report tomorrow morning?") and earnings-risk checks;
Finnhub stays the rule-2 breaking-news source (timestamps to the second:
SCYX GSK catalyst at 08:04:34, Benzinga). KEY CAVEAT from live test:
Finnhub had NO real catalyst headline for FCUV's +836% day -- only generic
"stocks moving" roundups (which technically pass the 18h rule since they
mention the ticker, but are echo coverage, not catalysts). Sub-1M-float
movers often rip on promotions/filings/social buzz that news APIs miss --
treat the news gate as confirmation, not an absolute veto, when float is
ultra-low and rvol is extreme.

## Robinhood Integration Implemented (2026-08-02)

Wired the Robinhood data into day-trading.py + a repeatable workflow:
(1) `data/rh_bars/{SYM}_{DATE}.csv` cache (1-min bars, real premarket
volume, interpolated bars excluded) — _window_data merges them over
yfinance, Robinhood wins on overlapping minutes; (2)
`data/rh_fundamentals.json` cache — float (rule 8 gate, now authoritative:
REPL 77.6M auto-excluded) + sector/industry (rule 4) consulted before
yfinance; (3) RH_SCAN_ID constant = saved server-side scan
5f132877-7730-4a18-9e72-b3f0d2c9df83; (4) rule 1 band now checked AT ENTRY
per bar (like rule 3) instead of at day open — a $1.93 open that runs
through $2+ is tradeable once in band; day filter only requires the band to
be reachable in the window; (5) seeded caches with FCUV Jul 31 premarket
(73 real bars incl. the 8:18-8:30 explosion) + fundamentals for
FCUV/SCYX/TCX/REPL; (6) `.claude/skills/daytrading-morning.md` = full morning
workflow: run_scan -> refresh caches via MCP -> screen (Finnhub news last)
-> livescreen/livebars (E*TRADE) -> LIMIT order. End-to-end test on merged
real-volume data: optimizer full-ruleset best = trail 20-25% + all-pattern
entries -> $1,000 -> $1,926 (+92.6%) on the one qualifying day (FCUV);
hammer+trail took 1 trade +28.5% (real premarket volume makes vol-confirm
meaningful premarket for the first time — with yfinance it silently
passed on zero volume). Cent-target default on FCUV: 1 trade, -1.9% —
confirms fixed targets waste explosive days; trailing exits capture them.

## Robinhood Data Goldmine (2026-08-02)

Connected the robinhood-trading MCP server (53 tools) and it fills EVERY data
gap yfinance/E*TRADE left, verified live: (1) get_equity_historicals returns
TRUE 1-min OHLCV bars with REAL premarket volume -- FCUV Jul 31 premarket
explosion captured minute-by-minute (8:19 84k shares @ $2.58, 8:20 427k @
$4.38, 8:22 725k @ $7.90, 8:30 601k @ $8.88) where yfinance reported
Volume=0; bars carry session (pre/reg) + interpolated flags; explicit RFC3339
ranges, bounds=extended, split-adjusted; DEPTH: 1-min real at >=2 weeks back
(Jul 20 verified; gone by 3 months), 5-min real at >=3 months -- both beat
yfinance's 7 days. Even 15second/30second intervals exist. (2)
get_equity_fundamentals gives FLOAT directly (FCUV 601K -- 0.6M float
explains the +836% day; SCYX 9.5M, TCX 8.8M pass; REPL 77.6M correctly out),
plus sector/industry (rule 4), avg_volume 2wk/30d + extended-hours day volume
(rvol: FCUV = 21.8x), market cap, PE/PB, 52wk range, company profile. (3)
SCANNER (create_scan/run_scan): full server-side screener on Robinhood's
real-time feed -- created scan 5f132877-7730-4a18-9e72-b3f0d2c9df83 with the
complete rule set: Last BETWEEN $2-16, %Change>=10% (1d, plot=Close --
plot is REQUIRED or the filter errors), RelativeVolume>=5x (1d, length
pinned to 30 by server), Float<=16M; sorted %Change desc; 0 matches on
Sunday (evaluates live day data -- populates Monday premarket). Title stays
'Untitled Scan' (rename only in Legend UI). Filter specs also offer GAP,
VWAP, RSI/MACD/EMA/Bollinger, sector -- room for tighter A+ filters.
Replaces yfinance items #1 (intraday history, better depth + real premarket
vol), #3 (float+sector), #4 (market-wide scan), and most of #2/#6. Morning
workflow upgrade: run_scan (Robinhood, all rules server-side) -> news check
(Finnhub) -> livebars/livescreen (E*TRADE) -> order (E*TRADE). Note: MCP
tools are session-level (Claude calls them); day-trading.py python code
still uses yfinance -- for in-script access the robin_stocks python lib with
the same account is the path if needed.

## Etrade Realtime Data (2026-08-02)

Replaced yfinance with E*TRADE real-time data wherever the API allows.
(1) Rules 1/3/5 (price band, up>=10%, rvol>=5x) now compute LIVE from one
batched E*TRADE quote: lastTrade/ExtendedHourQuoteDetail price,
previousClose, totalVolume, averageVolume -- etrade_live_metrics() feeds
screen_symbol(live=...); `screen`/`scan` auto-use it when a token exists
(PROD first, sandbox fallback), yfinance per-symbol fallback otherwise.
Sandbox returns CANNED 2012 data for fixed symbols (ask AMD -> get GOOG),
so sandbox never poisons results (symbols don't match -> fallback).
(2) `livescreen SYMS [--prod]`: full real-time rule table via E*TRADE +
lazy sector/float/news for pre-passers. (3) `livebars SYM [--prod]`: polls
quotes every 10s, assembles LIVE 1-min OHLCV candles (EtradeVolumeFeed.bars),
runs the candlestick engine after each completed minute -- live pattern
detection with true extended-hours volume (fixes yfinance premarket vol=0).
(4) News now Finnhub-first (news_within_18h; FINNHUB_KEY in Credential
Manager; tested live -- caught SCYX's 8:04 AM GSK catalyst headline) with
yfinance fallback, and news is checked LAZILY only after all cheap rules
pass. Float rule <=16M enforced in all commands; E*TRADE quote also returns
sharesOutstanding (float <= sharesOutstanding, usable as sufficient check).
NOT replaceable with E*TRADE: historical intraday bars (no history API --
backtests stay yfinance) and market-wide screening (no screener endpoint --
`scan` stays Yahoo, then livescreen re-verifies real-time). Morning workflow:
scan -> livescreen --prod -> livebars --prod -> place order.

## Two-X Day Hunt (2026-08-02)

Goal: 2x profit in same-day penny trading. Rules consolidated into the sim:
(1) buy AND sell inside the 7-10 AM ET window of the same day -- open
positions force-flattened at the window close (backtest now trades window
bars only); (2) $2-16 band checked PER DAY at the day's window open (was
wrongly using the latest price, which excluded FCUV's monster day because it
ended at $17); (3) up >=10% vs prev close enforced AT ENTRY TIME inside
simulate_trades (prev_close from daily bars); (4) relative volume >=5x the
50-day average required for a day to be tradeable (rvol map in _window_data);
(5) news-within-18h replaces the 7-10AM news rule in the screener
(NEWS_LOOKBACK_HOURS); (6) float <= 16M enforced in ALL trading commands --
_window_data excludes oversized-float symbols before simulating (REPL 59.7M
excluded; unknown float passes best-effort), screener rule8 changed < to <=. Win% columns renamed/changed to Ret% = P&L as % of the
$1000 position. New `optimize` command: trades THE qualifying gapper each day
(biggest gainer meeting 10%+/5x rvol), all-in compounding, grids pct
target/stop AND trailing exits. RESULT (SCYX/TCX/REPL/FCUV, 7d, only Jul 31
FCUV qualified -- +836% window gain): fixed % targets max +6.9%; TRAILING
exits changed everything: trail 20-25% + all-pattern entries -> $1,000 ->
$1,996 (+99.6%) IN ONE DAY == the 2x goal. Key learnings: (a) hammer_family
entries took ZERO trades on the explosive day (marubozu bars, no wicks) --
all-bullish-pattern entry needed on 800% days, hammer calibration was for
normal gappers; (b) yfinance PREMARKET 1-min bars have Volume=0, so the
volume-confirm filter silently passes premarket (avg=0 -> pass) -- volume
confirmation is effectively regular-hours-only; (c) fixed cents/% targets cap
the exact days that can 2x -- ride-the-runner trailing exit is what captures
them; (d) days meeting ALL rules are rare (1 of ~7 days x 4 stocks) -- the 2x
comes from patience for the A+ day, not from daily grinding. Caveat: n=1
qualifying day; thin premarket fills/slippage not modeled; needs live paper
validation.

## Pair Combination Grid (2026-08-02)

Added `pairtest`: every entry signal x every exit signal individually -- 8
bullish candles + rsi_cross_up + macd_cross_up entries, 10 bearish candles +
rsi_cross_down + macd_cross_down exits = 120 combos (target/stop always on,
vol confirm on candles, $1000/trade, 7-10 AM ET, SCYX/TCX/REPL 5d). RSI/MACD
computed on 1-min bars (RSI-14 cross out of 30/70, MACD 12/26/9 signal cross)
in Candles.indicator_bullish/bearish. Findings: (1) exit pattern choice
barely matters -- most exits never fire before target/stop, rows within an
entry table are near-identical; the entry decides the outcome. (2) Profitable
entries: hammer (+$25, only 1 trade), inverted_hammer + bearish_engulfing
exit (+$19.69, 5 trades, 60% -- most robust single pair), dragonfly_doji
(+$5.86 any exit), tweezer_bottom + tweezer_top (+$13). (3) RSI entry lost
(-$19, 10 trades) and MACD entry lost worst (-$75 to -$119, 17 trades) --
oscillator crosses are too slow/noisy for 1-min penny tape; they also never
fire as useful exits. (4) rising_three never formed once (5-candle pattern,
too rare intraday). Conclusion: the hammer FAMILY as a group (+$74) beats
any single pattern -- individual signals are too rare alone; combining the
three wick-rejection candles is what creates enough trades. Defaults stay
hammer_family + vol confirm + strong_if_profit.

## Position Size Grid (2026-08-02)

Changed rule 7 sizing from fixed 1150 shares to POSITION_DOLLARS=$1000 per
trade (shares = $1000 // entry). Added max_trades cap to simulate_trades and
a `gridtest` command: buy-pattern sets x trades/day caps {1,2,3,unlimited},
7-10 AM ET, $1000/trade, sell=strong_if_profit, vol confirm on. Results
(SCYX/TCX/REPL, ~5 days): best = hammer_family with 3/day or unlimited
(identical -- it never fires >3/day): +$74.36 over 8 trades, 62% win,
+$9.29/trade. KEY: capping at 1 trade/day LOSES (-$16, 50% win) -- the
day's first setup is often premature; trades 2-3 carry the profit. Cap 2
= +$41. All non-hammer buy sets lose at every cap. Scaling: P&L is linear
in position size ($1000 -> +$74/wk vs ~$5.5k avg position -> +$713/wk
earlier). At $1000/trade the +$9.29/trade edge is thin vs real frictions
(1-2c spread on ~300 sh = $3-6/round trip) -- needs bigger size or a
tighter-spread stock list to survive costs.

## Candle Window Test (2026-08-01)

Added `candletest` command to day-trading.py: grid-tests 5 buy-pattern sets x
4 sell modes on 1-min bars restricted to the 7-10 AM ET window (premarket +
open, prepost=True), and made simulate_trades() configurable (buy_set,
sell_mode). Also switched rule 6 to risk-ratio form: REWARD_RISK=2.0 -> target
+$0.30 vs stop -$0.15 (note: on regular-hours tests the original fixed +$0.18
target actually made more money -- +$1,093 vs +$364 across FCUV/SCYX/TCX --
high win rate beats fat targets on 1-min scalps; small sample though).
7-10 AM grid result (SCYX/TCX/REPL, 5 days): buy=hammer_family (hammer,
inverted hammer, dragonfly doji) WON in all 4 sell modes (+$437..+$908);
every other buy set lost money. Best combo: hammer_family +
strong_if_profit (exit only on bearish engulfing / evening star / 3 black
crows when profitable): +$908 over 10 trades, 60% win. Interpretation:
single-candle wick-rejection signals catch fast premarket dip-inversions;
multi-candle patterns (morning star, rising three) confirm too late for this
window, engulfing whipsaws on thin tape. Caveats: tiny sample; FCUV excluded
(drifted to $17.05, out of band); SCYX had only 17 premarket bars (illiquid);
real premarket spreads are wide -- paper-test before sizing up.
UPDATE: defaults now set (penny stocks only) to hammer_family +
momentum-volume-reversal confirmation (reversal candle volume >= 1.5x
trailing 20-bar avg, ENTRY_VOL_MULT/VOL_AVG_BARS) + strong_if_profit exits.
With vol confirm, 7-10 AM window: +$713 over 8 trades, 62% win (vs +$908/10
without filter -- same per-trade avg, fewer junk entries; the filter also
lifted all_bullish configs from negative to positive). Regular-hours backtest
with the same defaults LOSES money (SCYX -$213, TCX -$196, REPL -$370) --
this is strictly a 7-10 AM morning strategy, matching the news-window rule.

## Penny Stock Strategy (2026-08-01)

Implemented the Cameron Ross momentum day-trading strategy in `day-trading.py`
(original prompt saved verbatim in `penny-stock.md`). Screener rules: price
$2-$16, breaking news 7-10 AM ET today, up >=10%, hot sector (AI/biotech/
semis via HOT_SECTORS list), relative volume >=5x the 50-day average, float
under 16M. Trading rules: ~1150-share positions, sell at +$0.18-0.20/share,
hard stop -$0.15/share. Entry engine = 1-min candlestick state machine:
SCAN (find +2% surge within 10 min) -> DIPPING (wait for >=5c retrace) ->
ARMED (buy on first bullish reversal candle: hammer, inverted hammer,
dragonfly doji, bullish spinning top, bullish engulfing, tweezer bottom,
morning star, rising three) -> LONG (exit at target/stop or on bearish
pattern: hanging man, shooting star, gravestone doji, bearish spinning top,
bearish engulfing, tweezer top, evening (doji) star, three black crows,
falling three). CLI: `scan` (discover candidates market-wide via Yahoo screener API, then
full rule check), `screen SYMS`, `patterns SYM`, `backtest SYM --days N`.
The $2-16 band is ENFORCED in backtest/patterns — non-penny stocks (e.g. AMD)
are refused, since cent-based targets only make sense at penny prices. News
rule checks the last SESSION date (weekend scans check Friday's 7-10 AM
window). Day-trading rule: buy and sell always happen the SAME day; any open
position is flattened at the last bar (EOD flatten), never held overnight.
First live scan (Fri Jul 31 2026 session) found 25 gappers;
near-perfect setups FCUV ($11.60, +517%, 45x rvol, 0.4M float), SCYX (+29.8%,
41x rvol, 7.7M float), TCX (+59.2%, 12.6x rvol, 5.7M float) — all failed only
the yfinance news check. Backtests on those three: FCUV +$442 (38 trades),
SCYX +$277 (12 trades, 67% win), TCX +$374 (16 trades) — profitable on real
gappers. yfinance limits: news timestamps approximate/incomplete, float
patchy, 1-min history ~7 days — production needs a real-time scanner feed.
