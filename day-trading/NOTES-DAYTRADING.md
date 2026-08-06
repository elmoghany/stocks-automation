# Penny Stocks Trading Notes

Convention: new notes go at the TOP of this file. Each note = a **3-word title**,
then a detailed explanation of what was done and why.
Normal (large-cap wave/value) trading notes live in `NOTES.md`.
**Every configuration ever backtested** (grids, sweeps, cap matrices — ~240
configs with results + the script that reproduces each) is registered in
[`CONFIGS-TESTED.md`](CONFIGS-TESTED.md); re-test any of them from there.

---

## Code Review of day-trading.py (2026-08-05)

Full review of Candles + simulate_trades after the X100-X300 additions.
FIXED: pressure_reentry consumed its re-entry budget at TRIGGER even
when the fill was rejected by entry/pressure gates -- now consumed only
on a successful fill (affects only the non-adopted X221/X222 configs;
champion identity verified unchanged: AX20 Y1 +$244,899 and C21 Y1
+$395,243 reproduce exactly post-fix). DOCUMENTED (deliberate
trade-offs, now in code comments):
1. wick_guard references the NEXT bar's close (1 bar of hindsight);
   it only ever CAPS peaks so cannot add phantom profit; live
   equivalent = trust spikes with a 1-bar delay. Adopted at $0.00
   delta with this definition.
2. LOWS are not wick-guarded: a phantom low can hit the stop, but
   fills at the stop level, so damage is bounded to a normal stop-out.
3. Scale-out skip is PERMANENT per position: the +25% touch is a
   one-time decision -- if buyers dominate at the touch, the position
   never banks later (C21 semantics as backtested).
4. monster_mode tell uses realized pnl only (causal); kept for
   research completeness though verdict was neutral.
Reviewed clean: pressure prefix sums, entry-gate causality (i-1),
exit-fill causality (i), slippage on all fill paths, ATR windows,
dyn trail/stop reset per entry, ORB/PMH trigger precedence, shuffle
control seeding, flag resets across positions.

## Coverage Family Complete: The Last Axis Closes (2026-08-05)

The deferred fetch-queue experiments (20 runs on the AX20 base) are
done. VERDICTS:
- FALLBACK RE-PICKS: catastrophic (-$60k to -$243k). Abandoning a
  committed candidate that hasn't entered by 8:30/9:00 quits right
  before the 9-10AM golden hour -- the 'stalled' pick is usually
  warming up. Patience with the commitment IS the edge.
- SECOND-PICK REDEPLOY: zero effect -- 87% of days still hold at the
  flatten, so 'fully exited early' almost never happens.
- CONDITIONAL SPLITS: all negative (-$41k to -$154k) even when gated
  on candidate supply/quality. Halving the eventual monster's position
  can't be rescued by conditioning. Concentration is structurally
  correct.
- MIN-HIST RELAXATIONS: negative. WALK 12/16: the lone positive
  (+$12.1k/+$12.6k both-year) but far below the $30k floor -- ranks
  9-16 add 40-80 trading days of pocket change; shelf item.
- X095 lag-rank control: fails as designed.
RESEARCH PROGRAM STATUS after ~210 experiments: every family is now
adopted, empty, or shelf-marginal. C21 stands as a tight machine; the
next information gain is live paper data (Day 2 today) and eventually
a third backtest year when data ages in.

## News-Tier Experiment: Nothing There (2026-08-04)

X340/X341 on Finnhub company-news (Y1-ONLY evidence -- free tier has
no Y2 history; could not be adopted under the both-year rule
regardless). Cache: 2,008 candidate-days, 69% had headlines in the 18h
pre-7AM window. RESULTS vs C21:
- X340 news-priority rank: Y1 +$2,608 (noise). Gain ranking already
  surfaces the news-driven movers -- a +50% gapper on 5x volume has a
  catalyst almost by definition.
- X341 news REQUIRED: Y1 -$68,388 (drops 26 trading days) -- the
  no-headline 31% still contains real winners (unindexed catalysts,
  social momentum). Requiring news destroys value.
VERDICT: do NOT buy deeper news history; the signal isn't there even
in-sample. News stays where it belongs in the live flow: as a
confirmation input for the human, not a ranking rule.

## Earnings-Drift Hypothesis: REJECTED (2026-08-04)

User idea: buy before earnings when the stock is 5y-strong/uptrending
AND its own history shows positive post-earnings reactions. Probe:
161 liquid names, 3,844 earnings events back to ~2014, point-in-time
gates, $15k/event, window Oct24-Jul26 (plan/earnings_probe.py).
RESULT: the edge does not exist in this universe.
- Baseline (no gates, 1,214 events): avg -0.02%/event, 50% win --
  post-earnings reactions are zero-mean coin flips in liquid names.
- User gates (>=60% historical hit + 5y>=100% + >200SMA): n=58,
  -0.27% avg (close exit, -$2,308 total); tighter gates get worse
  (70%: -0.93%; 75%: -3.91%). Historical reaction hit-rate is NOT
  sticky -- expectations are priced, and strong-momentum names carry
  the highest expectations, so even beats get sold.
- Structural problems regardless of stats: holding THROUGH a release
  is uncapped overnight gap risk (worst event -15.6% = no stop can
  save you), and it breaks the same-day rule.
CONTRAST: the day system trades AFTER the catalyst is public, riding
realized momentum WITH stops -- structurally and empirically superior
(~+22.6%/day on deployed capital vs -0.02%/event here). Verdict:
earnings anticipation rejected; earnings REACTIONS are already our
bread and butter (the widened universe catches earnings gappers the
morning after).

## Monster Mode Redundant; Edge Is Market-Neutral (2026-08-04)

X335-X338 tested the '$2k-banked-by-9:30' monster tell as an explicit
rule (stop banking / floor trail 40% for the rest of the day; tells at
$1k/$2k/$3k). ALL NEUTRAL (-$2.6k to +$3.2k, X336 Y1-negative): C21's
PRESSURE mechanics already implement monster mode better -- when a
monster runs, buy pressure is high, so the scale-out is already
skipped and the trail is already 40%, per-bar rather than per-day. The
tell DESCRIBES monsters; the pressure trail already MONETIZES them.
No rule change. Remaining open questions answered:
- MARKET-NEUTRAL: corr(day P&L, SPY daily return) = -0.006 over 270
  days; SPY-up days avg +$3,428 vs SPY-down +$3,336. The edge needs
  individual-stock news catalysts, not a hot tape. (Good: no hidden
  beta; bad markets don't starve it.)
- DAY-OF-WEEK: flat-ish (Mon +$4,355 best, Thu +$2,761 worst, all
  win% 75-84) -- spread is within noise; no weekday rule warranted.
- STILL OPEN (needs live data): real fill slippage vs sim -- the
  purpose of the paper sessions.

## Concentration Study: You Cannot Skip the Quiet 90% (2026-08-04)

C21 concentration: 28 monster days (10%) = 43% of profit; 80 mid days
($3-10k) = 52%; the quiet 162 days (60% of days) = only 5% ($45k).
STRATEGIC ANSWER to 'trade less, mimic the 10%': the quiet days cannot
be skipped EX-ANTE -- every filter that tried (gap bands, rvol boost,
walk-3, entry gates) lost money, because every monster begins the
morning looking exactly like an ordinary qualifying day. But the quiet
days also cost almost nothing (+$45k net, tiny drawdowns) -- they are
the price of the lottery tickets. The edge is IN-FLIGHT amplification,
not ex-ante selection; C21's scale-skip and pressure-widened trail
already are that engine. NEW ANSWERS:
- Q(first trade): a losing FIRST position does NOT spoil the day --
  rest-of-day averages +$2,851 after an opening loss and 62% of those
  days still end green. NEVER stand down after an early stop (kills
  circuit-breakers again).
- Q(monster tell): '+$2k banked by 9:30' is real -- 3x the monster
  base rate (30% vs 10%), those 44 days avg +$7,150 and hold 34% of
  profit. Actionable causally: X-candidate 'monster mode' = once the
  tell fires, disable further scale-outs / force widest trail for the
  rest of the day.
- Q(flatten quality): noon-flatten give-back from peak is small
  (median 3.6pp) -- truncation costs future upside, not bad fills.
- Q(hangover): day-after-monster is ~normal (+$2,786 vs +$3,388 avg).
Still open: market-tape correlation (needs SPY series); live slippage
(paper days).

## Pressure-Threshold Sweeps: 0.30 Validated (2026-08-04)

User-requested sweep of the +-0.30 pressure threshold at the champion's
N=10 window, separately for the trail modulation and the scale-out
skip (X321-X334; anchor exact). TRAIL threshold: curve peaks at
0.25-0.30 (0.25 = +$5.2k, noise); DEGRADES HARD above 0.30 (0.35
-$14.3k, 0.40 -$35.0k, 0.45 -$51.9k) -- the trail must react to
moderate seller pressure; waiting for extreme pressure gives back
runners. Do NOT raise it. SCALE-SKIP threshold: essentially FLAT
0.15-0.45 (total spread ~$6k, best 0.45 +$6.8k, all noise) -- the
skip-banking mechanism is robust to its threshold. VERDICT: C21's
0.30/0.30 confirmed; no change (all deltas below the $36k noise
floor). The sweep buys confidence, not profit -- exactly what a
parameter sweep should do when the champion is well-placed.

## Paper Day 2 Scheduled: C21 Live Test (2026-08-05)

Session armed for tomorrow 6:58 AM ET (session-local cron): full C21
spec inside 7AM-noon, fixed scanner (ratio units), 5-min scan cadence,
1-min position watcher on entry, push notifications on every paper
entry/exit, log at data/paper/2026-08-05.md. Day-1 lessons applied:
sanity-check empty scans against the gainers preset; our 50-day rvol
governs over RH's 30-day; expect halal to kill micro-mcap movers.
NOTE: the trigger only fires if this Claude session stays open
overnight.

## X300 Verdict: C21 Champion Inside Strict Noon (2026-08-04)

20 anatomy-driven experiments on the C10 base. Controls behaved:
shuffled-pressure trail -$114k (the pressure signal is real), walk-3
-$165k (walk-8 tail confirmed). Post-hoc pick hypotheses correctly
died (drop-gap-band -$121k, rvol-boost -$47k) -- description != rule.
Wick-guard costs $0.00 exactly -> adopted as free insurance. The trail
neighborhood pointed tighter-tighten/wider-widen; stacked with the
pressure-conditioned scale-out skip:
C21 = C02 + pressure-trail(10, 0.30, 0.30, 10, 40) + skip 1/3-bank
when P>=+0.3 + wick-guard 3x, ALL INSIDE 7AM-NOON:
  Y1 +$395,243 / Y2 +$519,641 (+$914,884/2yr), 0 negm BOTH years,
  holdouts +$89.8k/+$100.5k, C22@10bps keeps 93%.
C21 recovers ~98% of the withdrawn 1PM premium without the extra hour.
ADOPTED as champion; defaults + skill updated. Avg year +$457,442 =
37% of the 5x target.

## 1PM Window WITHDRAWN -- C10 Is Champion (2026-08-04)

User reverted the exit window to STRICT NOON. C11 (1PM exits,
+$927k/2yr) is archived as reference; the live champion is C10 = C02 +
pressure-trail(10, 0.30, 0.30, 12, 30) inside 7AM-noon: Y1 +$378,765 /
Y2 +$481,805, ZERO negative months both years, avg +21.2%/day of the
$15k. Defaults, skill, and paper watcher reverted. X300 campaign runs
anatomy-driven refinements on the C10 base (pressure-trail sweep,
monster amplification, PMH re-arm, pattern surgery, pick hypotheses,
wick-hygiene guard).

## AX20 Win Anatomy (2026-08-04) -- cross-config comparison

Same instrumentation on AX20 (2,235 positions, 267 days). The SKELETON
IS STRUCTURAL (holds in both configs): monsters = 45% of profit from 20
days; 10-20% gap band richest (+$3,214/day); ranks 0-2 dominate (rank0
+$6,053 vs rank3-7 ~$500); ordinal decay with a fat re-entry tail; ORB
~3x pattern entries per position (+$390 vs +$140); 9AM = best entry
hour in BOTH configs. DIFFERENCES THAT TEACH:
1. 79% of AX20 winners were still holding at the NOON flatten (C11:
   73% at 1PM) -- the forced close truncates winners at EVERY window
   length tried so far. Each extension has been worth real money
   (noon->1PM = +$62.5k). The signal persists -> test 2PM/close (X300).
2. 7AM entries: AX20 avg +$70/position vs C11 +$444 -- early entries
   only became profitable when the triggers got FAST (5-bar ORB +
   premarket-high stop-buy). Slow triggers waste the premarket.
3. Winner peaks: AX20 avg +42% vs C11 +60% -- bigger size + pressure
   trail + extra hour let the same winners stretch further.
Conclusion: C11's gains came from amplifying the structural skeleton
(faster in, bigger, longer, smarter trail), not from changing what
wins. The skeleton's remaining unmonetized signal: the close-time
truncation and the noon-entry churn.

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

## Earnings-Trading Book (2026-08-05)

New separate book: trade the earnings REACTION on halal large/mid caps
(user: "amd news yesterday... some companys fall during earnings").
Scripts: plan/earnings_trading.py (backtest ET01-ET09),
plan/earnings_timing.py (entry-hour sweep ET10/ET11),
plan/earnings_upcoming.py (live watchlist: halal names reporting in the
next N days + historical reaction stats). Universe: 164 large/mid caps
-> 88 halal (halal_check, cached data/earnings_halal.json; current
fundamentals = point-in-time approximation). Window: LAST YEAR ONLY
(Aug 2025-Jul 2026) per user directive. $15k/event. No shorting (not
halal) -- fallers are played as next-morning dip-buys.

Results (data/earnings_trading_results.json):
- ET03 dip-buy gap<=-3% (buy post-news open, sell close): n=46,
  54.3% win, +0.75%/event, +$5,182. PASS (also +$7,358 prior year).
- ET04 dip-buy gap<=-5%: n=24, 62.5%, +$1,917 PASS.
- ET06 dip-buy + 5y-strong: n=18, 66.7%, +1.18%/event, +$3,177 PASS
  (best avg; small n).
- ET02 gap-up>=+5% continuation: +$1,782 (was -$156 prior year --
  regime-shaky, not adopted). ET01 gap>=+3%: -$696 fail.
- ET07 control |gap|<3%: -$6,108 (filter matters -- good).
- ET08 OVERNIGHT gap-up drift (post close -> next close): +$9,900
  (+$10,302 prior year, both positive) -- flagged, overnight book needs
  separate sign-off. ET09 overnight dip: -$6,202 fail.
- ET10/ET11 entry-timing sweep ("best time to buy BEFORE earnings"):
  NONE. Every entry hour 09:30-15:30 loses, both exits: sell-at-close-
  before-release -0.4..-0.9%/event (win% degrades toward the close:
  38%->25% pm, 32%->14% am -- de-risking drift into the report);
  hold-through-release -0.4..-0.85% at every hour. Confirms the
  earnings_probe rejection with hour resolution.
- VERDICT: the edge is AFTER the news, not before. Adopted watchlist
  play: morning dip-buy on halal names gapping <=-3% on results
  (ET03/ET04/ET06). AMD 2026-08-05 (beat, -9% open on outlook) is the
  live archetype. News readability verified: Finnhub company-news (180
  AMD headlines/3d) + Robinhood get_earnings_results (EPS est/actual,
  report date, am/pm timing).

### CORRECTION (2026-08-05, later same day)

The ET01-ET09 results above were computed with a WRONG reaction-day
convention: yfinance report timestamps were normalized to midnight, so
pm (after-close) reporters had their "reaction" measured on the report
day itself instead of the NEXT session (e.g. AMD reported 8/4 pm; the
-9% reaction was 8/5, but the old code scored 8/4). Fixed in
plan/earnings_trading.py using the announcement hour (pm -> next
session, am -> same day, mid-day stamps skipped). Corrected last-year
numbers (n roughly doubles because real reaction days move more):
- ET03 dip<=-3%: +$2,787 (n=111, 51.4% win, +0.17%/ev) -- thin, not
  the +$5.2k previously reported.
- ET04 dip<=-5%: -$782 FAIL (was +$1.9k). ET06 dip+strong: +$138 ~zero.
- ET02 gap>=+5%: +$1,268 thin. ET01: -$1,804 fail.
- ET07 |gap|<3% "control": +$10,377 -- the LARGEST positive, i.e. last
  year's bull tape drifted quiet reaction days up. Market beta, not an
  earnings edge. Treat all raw ET numbers with that lens.
- ET08 overnight drift: +$1,704 (was +$9.9k -- artifact).
LESSON: the naive post-earnings dip-buy has at best a thin edge; the
gated variants are being tested properly in plan/earnings_x2.py
(ET12-ET31: beat + 5y-strong + profitable-quarter + volume-pressure,
S&P500+400 halal universe, after-hours entries, +8/10/15% targets,
pre-earnings run-up ladder). Results to follow.

## Paper Day 2 (2026-08-05): compliant no-trade day + repo reorg

0 trades, $0. 13 scan hits all rejected: 4 haram (incl. ZYBT +177% --
passed every technical gate, zero news, blocked only by halal), 2
calm-gap (OESX/JLHL opened >+20%), 5 our-rvol, 1 leveraged ETF. Live
lesson: halal is the binding constraint on gapper tape (5 monsters in
2 days). Ops: single-timer agent stalled twice -> Day 3 runs dual
timers + watchdog + day JSON + same-day news capture (paper_news.py).
REPO REORG (user): three strategy dirs -- day-trading/ (penny C21 book:
day-trading.py, plan/, data/, notes), earnings-trading/ (ET book:
plan/, data/), bollinger-trading/ (old buy-low-sell-high wave/value
system: trading/ pkg, E*TRADE client+docs, sandbox scripts), shared/
(win_cred, massive). All scripts path-fixed and smoke-tested.

## Earnings-X2 verdicts (2026-08-05, full 305-name halal universe, 1,227 events)

STRATEGY A -- post-earnings dip-buy on BEATS (same-day, fits all rules):
- ET12 dip<=-3% + beat, buy next-morning open, sell close: +$28,642
  (n=246, 52.0% win, +0.78%/ev). ET31 control (same trade on MISSES):
  +$453 ~zero -> the beat gate is REAL. ADOPTED as the earnings play.
- ET13 + 5y-strong + profitable qtr: +0.95%/ev, 55.1% win (n=89) --
  quality gates raise the average; use when candidates are plentiful.
- Profit targets DO NOT help: +8/+10/+15% targets all return less than
  simply selling at the close (ET14-16 vs ET13). 2-day cap: no gain.
- After-hours same-evening entries are HARMFUL: ET18/19 -1.6%/ev, 37%
  win. The evening dip keeps falling into the morning; buy the OPEN.
- First-hour pressure gate: n=2, no evidence (hourly pressure >=0.2 is
  too rare on large caps; retest intraday when live).
STRATEGY B -- pre-earnings run-up: KILLED BY CONTROLS.
- Raw ladder looked huge (lag7 +$146k, lag5 +$101k, ET28 lag5+strong+
  fin +$109k at +2.12%/ev, 63.7% win). But: SPY-adjustment removes
  ~half the all-names return (+0.551 -> +0.288%/ev); and the PLACEBO
  (same names, same 5-session hold, mid-quarter, no earnings): +1.73%
  raw / +1.26% SPY-excess vs ET28's +2.12% raw / +1.73% excess. The
  placebo reproduces ~73% of the excess return -> ET28 is mostly
  "strong halal momentum names drift up in a bull year", not an
  earnings effect. Earnings-specific increment ~+0.47%/ev (~1.5 SE,
  not significant). Also violates the 1-2-day hold cap (edge only in
  5-7-day holds; 1-2-day versions ET25/26/29 are thin).
- Consistent with ET10/11: the report DAY itself drifts down; the
  week-before drift is momentum beta, not anticipation.
(controls script label note: 'ET22' rows in earnings_x2_controls
output use the lag-5 window, i.e. ET23's numbers.)
PLAYBOOK ADOPTED: morning-after dip-buy on halal BEATS gapping <=-3%
(quality gates optional), sell at same-day close. No pre-earnings
buying, no after-hours entries, no profit targets. Live tool:
python earnings-trading/plan/earnings_upcoming.py each evening.

## Earnings-X3 verdicts (2026-08-05, $50k/slot, four improvement strategies)

S1 MINUTE-LEVEL MECHANICS (ET40-45, 246 reaction days, 1-min Massive):
- ET40 anchor open->close +0.772%/ev = daily ET12 (+0.776%) -- data OK.
- Penny-book mechanics DO NOT transfer to large-cap earnings dips:
  bounce-confirm entry +0.52% (worse -- you pay up for confirmation),
  2%/4% pressure trail +0.16% (shaken out), both combined -0.04%,
  -3% hard stop +0.58% (stops out days that recover). Large-cap dip
  bounces are grinding mean-reversion, not momentum surges. REJECT:
  blind buy-the-open / sell-the-close IS the optimal simple form.
S2 SMALL CAPS (ET50-53, S&P600, 184/603 halal, 702 events):
- ET50 dip<=-3%+beat: +0.57%/ev (+$26.4k). ET51 dip<=-5%: 58.5% win,
  +1.28%/ev (+$41.6k) -- deeper small-cap dips bounce harder.
- ET52 combined-universe one-slot deepest: +$117,164 (n=111) vs
  big-only +$117,755 (n=99): more active days, SAME total. Small caps
  broaden selection but do not lift the one-slot ceiling.
S3 SYMPATHY (ET60-62, 13,700 peer-days): ALL NEGATIVE (-0.03..-0.09%/
  ev, ~49% win). No tradable daily-granularity sympathy edge. REJECT.
S4 COMPOUNDING (ET70): the real lever. One slot/day deepest dip at
  flat $50k: +$117,755/yr. COMPOUNDING full equity: $50k -> $433,593
  (+767%/yr), max drawdown -21.9%, worst trade -10.7% (IESC).
  Caveats: single bull year, no slippage, position = full equity.
FINAL EARNINGS PLAYBOOK: one $50k slot/day, deepest halal dip <=-3%
on a confirmed BEAT (combined S&P900+600 universe), buy 9:30 open,
sell at close, compound if drawdown tolerance allows. Deepest-dip
slot rule + compounding are post-hoc choices -- confirm next earnings
season before treating as settled.

## E01 -- EARNINGS CHAMPION (registered 2026-08-05)

Permanent ID: **E01** (earnings book champion; cf. C21 in the day book).
Spec: each morning, among HALAL names (S&P900+600 universe, price >$2)
that BEAT EPS estimates and open <=-3% below prior close: buy the
DEEPEST dip at the 9:30 open with the full slot, sell at that day's
close. One slot/day. No pre-earnings buying, no after-hours entries,
no targets/stops/trails (all tested worse). Sizing: $50k flat
(+$117,755/yr backtested Aug25-Jul26, 99 trades, 62.6% win) or
compounded (E01c: $50k -> $433,593, +767%, max dd -21.9%).
Status: backtested one bull year; needs a paper season. Deepest-dip
slot rule + compounding chosen post-hoc -- revalidate next season.
Receipts: ET12/13 (edge + beat gate), ET31 (miss control ~0),
ET40-45 (mechanics reject), ET50-53 (small caps), ET60-62 (sympathy
reject), ET70 (sizing), ET32/33 (B-family beta controls).

## BL-family: buy-low/sell-high day trading vs E01 (2026-08-05, $50k/event)

bollinger-trading/plan/blsh_intraday.py -- limit-buy 2-3% below the
open on 5y-uptrend halal names (S&P900+600, 489 names), sell same-day
close; volume gates from prior-day pressure/rvol. Window Aug25-Jul26.
- BL01 dip2 strong: n=12,855 fills, 54.5% win, +0.116%/ev (+$745k
  ONLY if you fund every fill -- routinely 50+ concurrent $50k slots,
  $5M+ deployed; per-event edge is inside slippage noise).
- BL02 dip3: +0.163%/ev. BL04 +pressure>=0: +0.161%/ev (mild help).
- BL03 "recovery to open" exit: INVALID -- High >= Open is true by
  definition (the open is inside the day's range), so the target
  always "fills"; textbook OHLC look-ahead artifact. Discarded.
- BL05 NOT-strong control: +0.111%/ev ~= BL01's +0.116% -> the 5-year
  uptrend gate adds ~NOTHING to intraday dip-buying. (It was also
  beta, not edge, in ET28/ET33.)
- BL06 one $50k slot/day (rank by prior-day rvol): -$33,153. BL07
  (same, excluding earnings reaction days): -$11,334.
VERDICT vs E01: at equal capital (one slot/day) BL LOSES (-$33k vs
E01 +$117,755). Generic dips lack the catalyst; E01's edge needs the
earnings-beat information, not just "a strong stock dipped". No
rank-mining for a better BL06 picker -- 251 days would overfit.
BL book stays research-only; E01 remains the champion.

## C11 notes + 1PM re-adoption -> C23 DEFAULT (2026-08-05)

USER DECISION: "make c11 the default" -- the 1PM exit window (withdrawn
during X300 planning) is RE-ADOPTED.

What C11 is: C02 (orb5 + 20%/10-min sizing + PMH trigger) + two-sided
pressure trail (10, 0.30, 0.30, 12, 30) + exits extended to 1PM
(entries still end at noon). Born from the X219 trail family + C08's
signed-off 1PM window. Record: Y1 +$390,687 (133d, 0 negm), Y2
+$536,350 (147d, 1 negm). History: champion 2026-08-04, archived same
week when the user chose strict noon ("keep noon"), re-adopted
2026-08-05. Its 2,839 positions were the win-anatomy dataset (monsters
= 10% of days = ~47% of profit; golden hour 9-10AM; re-entry tail 31%).

C23 test (user: "ok test it"): the X300 improvements (trail widths
10/40, scale-out pressure-skip 0.30, wick guard) had never been
measured inside the 1PM window (X300 ran strict-noon). Result:
- C23 Y1 +$412,879 (0 negm) / Y2 +$579,988 (0 negm)
- vs C11: +$22,192 / +$43,638, dComb +$65,830 (>= $30k floor), negm
  improves (C11's one Y2 negative month disappears). C24 = C23@10bps:
  +$377,509 / +$539,670 (~91-93% kept).
ADOPTED DEFAULT: **C23** -- C11's window, X300's machinery. Reverting
to literal C11 = trail (12,30) + scale_out_pressure_skip None.
day-trading.py defaults + paper_watch (1PM flatten) + skill updated;
Paper Day 3 (2026-08-06) runs C23; E01 papers in parallel, separate
reporting.

## Half-profit reinvestment sizing (R50 policy, 2026-08-05)

USER DIRECTIVE: both books re-invest HALF of profits. slot = base +
0.5 x max(0, cumulative P&L); base never shrinks (losses only eat the
profit buffer). State: {book}/data/paper/slot_state.json, updated at
every close-out. Bases: C23 $15k, E01 $50k.
- E01 backtest under R50: +$208,787/yr vs +$117,755 flat (final slot
  $154k -- trivially fillable on S&P names). ADOPTED.
- C23 under R50: naive math explodes (avg +23.6%/day compounds to
  absurdity) -- NOT REAL: rule 13 (<= 20% of trailing 10-min volume)
  caps fills on penny gappers. Budget-scaling runs (15k/30k/60k/120k,
  plan/c23_budget_scaling.py) quantify the saturation; results to be
  registered when complete. Paper sessions apply R50 with rule 13
  intact, so live slots grow only as far as liquidity allows.

### C23 budget scaling + R50 trajectory (2026-08-05, follow-up)

Measured (plan/c23_budget_scaling.py; capture = share of linear scaling
retained under the 20%-of-10-min-volume cap):
- $30k: +$718k Y1 / +$1,078k Y2 (87% / 93% capture)
- $60k: +$1,198k / +$1,936k (73% / 83%)
- $120k: +$1,873k / +$3,328k (57% / 72%)
Sublinear but no hard wall through $120k. Note: Y2 gains 1 negative
month at every scaled budget (0 at $15k) -- size costs smoothness.
R50 simulation (day P&L interpolated across measured tiers, slot
FROZEN at the $120k measurement ceiling -- no extrapolation): the slot
reaches $120k within ~5 weeks, then rides there; 2-year total
+$4,964,801 vs +$992,866 flat-$15k. Practical reading: R50 on C23 =
"grow to max fillable size in ~a month, then earn ~$1.9-3.3M/yr at
that size" -- with growing fill-realism strain: the backtest assumes
clean fills inside the volume cap; at $120k slots that assumption is
doing heavy lifting. Slippage stress at scale untested (next: C24-style
10bps at $120k). Paper sessions enforce R50 + rule 13 naturally.

### C23 dynamic R50 backtest (true per-day compounding, 2026-08-05)

User: slot = $15k + half of cumulative profits, every day simulated AT
its actual slot (plan/c23_r50_dynamic.py; curve in
data/massive/c23_r50_curve.json).
RAW RESULT: +$37,443,510 over 2 years; slot $15k -> $19.4M (>=$120k in
5 weeks, >=$1M by month 3). NOT CREDIBLE AT SIZE:
- negative days 55% (vs ~21% at $15k); max DD -$11.9M; worst day
  -$2.1M -- the zero-negm character is destroyed;
- beyond ~$120k the fill model (trigger-price fills, zero market
  impact, 20% of 10-min volume) becomes fiction -- at $15M slots the
  strategy IS the market in these names.
RECOMMENDATION (pending user sign-off): adopt R50 WITH A SLOT CAP at
the measured-credible tier: slot = min($120k, $15k + 0.5 x cum). At
that cap the defensible 2-year figure is ~+$4.96M (tier-validated),
reached-cap in ~5 weeks, accepting 1 negative month in Y2 and the
$120k-tier fill caveats. Paper R50 runs uncapped for now ($15k base;
months away from the cap) -- decision needed only when cum profits
approach +$210k.

## C30 -- ADOPTED (2026-08-05): C23 strategy under capped half-reinvest sizing

Permanent ID: **C30** = C23 rules unchanged + R50-capped sizing:
  slot = min($120,000, $15,000 + 0.5 x max(0, cumulative P&L))
Base never shrinks; losses only eat the profit buffer; cap sits at the
highest liquidity-measured tier. Backtest (2yr, dynamic-at-tier):
~+$4,964,801 vs +$992,866 flat; cap reached in ~5 weeks; accepts 1
negative month in Y2 at scale; $120k-tier fill realism is THE thing
paper trading must validate (60s-later price recordings). C30 is the
live paper config from 2026-08-06 (slot state:
day-trading/data/paper/slot_state.json). E01 keeps uncapped R50
(large caps; no liquidity issue at these sizes).

## TD-family: halal big-tech 15%-dip buying, multi-day holds (2026-08-05)

bollinger-trading/plan/tech_dip.py -- user directive: buy 15% dips on
top-trend halal big tech, $50k/position, multi-day holds ALLOWED
(explicit same-day waiver for this book). Universe: 111 halal
Tech/Comm-Services names (S&P900 halal x sector map). Trigger: close
>= 15% below trailing 60-session high AND 5y return >= +100%
point-in-time; entry next open; one position per symbol. Entries
Aug 2021-Jun 2026 (includes the 2022 bear).
Results ($50k/position, ALL signals funded):
- TD01 +10% tgt/60s cap: n=207, 87.0% win, +6.58%/tr, 17d holds, +$681k
- TD02 +15% tgt: 80.6%, +8.56%, 24d, +$749k
- TD03 +20% tgt: 78.3%, +11.16%, 29d, +$876k
- TD04 recover-to-high/90s: 78.0%, +12.52%, 36d, +$882k
- TD05 20-session time exit: 65.2%, +7.97%, +$745k
- TD06 60-session time exit: 70.7%, +29.33%/trade, 55d, +$1,803,571 (best)
- TD07 20%-dip entry: 84.8%, +10.31%, +$474k (rarer, cleaner)
- TD08 +15%/-10% stop: 64.1%, +5.67%, +$654k (stop hurts -- dips wobble)
- TD09 +200SMA gate: 81.3%, +8.83%, +$614k (filters little)
- TD10 capitulation-volume gate: 71.9%, +$267k (over-filters)
CONTROL (no-dip monthly 60s holds, same names/window): +10.21%/hold,
61.3% win -> TD06's +29.33% is ~3x beta. REAL ALPHA -- unlike the BL
and pre-earnings families, the 15%-dip signal genuinely times these
names (deep dips on strong big tech mean-revert hard).
CAPITAL REALITY: signals cluster in crashes -- funding ALL signals
needs ~37-42 concurrent slots (~$2M). Constrained greedy sims:
- TD02: 1 slot +$44k / 4 slots +$145k / 8 slots +$255k (per ~5yr)
- TD06: 1 slot +$51k / 4 slots +$207k / 8 slots +$255k
i.e. ~$10-13k/yr per $50k slot at practical scale. Stop-losses hurt
(TD08); no exit variant beats simply holding 60 sessions.
STATUS: shelf/opportunistic -- strongest per-event stats in the
bollinger book; adoption needs a slot-count decision (capital beyond
the day/earnings books) and clustering tolerance (worst trade -46%,
2022-style periods tie up all slots at once).

## BB-family: Bollinger-Band mean-reversion + single-slot R50 (2026-08-05)

bollinger-trading/plan/bollinger_bands.py -- 12 variants on 479 halal
names (Aug 2021-Jun 2026): entry %B <= 0/0.20/0.30, exits %B >=
0.50/0.80/0.90/1.00, MA200/MA50 gates, 5-day volume-pressure reversal
confirm (buy side) and pressure-flip exit accel (sell side). $50k;
user portfolio rule: ONE slot at a time, R50 compounding, deepest %B
wins same-day ties.
- Per-event: all variants +1.3..+2.9%/trade, 64-71% win, ~13-38d
  holds. CONTROL (no-signal monthly 30-session holds): +2.79%/hold,
  55.6% win. Per-DAY efficiency: BB ~0.085%/day vs control 0.093%/day
  -> NO per-event alpha; the higher win% is just shorter holds. Unlike
  TD (3x control), band-touch timing adds nothing on this universe.
- Single-slot R50 outcomes SCATTER WILDLY across adjacent variants:
  BB01 (sell 0.80) +$1,053,172 but BB02 (sell 0.90) +$96,952 and BB03
  (sell 1.00) +$38,930; BB04 +$5k; BB12 (mid-band) -$32k. A result
  that flips 10x on a 0.1 threshold change is sequence luck, not
  edge (deepest-%B picking grabs falling knives: DAVE -88%, CVNA -79%
  events sit in every variant's tail). FAILS the adjacency guardrail.
- MA gates raise win% (BB08 83% slot win) but shrink totals; volume
  confirm (BB09/10) similar. Nothing beats its own neighbors robustly.
VERDICT: REJECT for adoption. Bands describe volatility, they do not
predict reversal here; the TD 15%-dip trigger (3x control) remains the
only validated buy-low signal in this book.

### TD-family under the user's single-slot R50 rule (same date)
One $50k slot, no new buy until exit, half-profit compounding,
~5-year window: TD06 +$59,886 (4 trades, 100% win), TD02 +$52,188
(8 trades, 88%), TD09 +$49,393, TD01 +$44,341 (13 trades, 85%),
others +$14k..+$39k. Reading: the single-slot constraint throttles TD
hard (4-13 trades in 5 years vs 123-231 signals) -- TD's value needs
multiple slots; at one slot it's ~$9-12k/yr, comparable to E01's base
year but far below C30. Slot scaling for TD = the open decision.

## BD-family: band-gated dip entries (2026-08-05)

bollinger-trading/plan/dip_band.py -- %B entry thresholds ON TOP of
the validated -15%-dip trigger, vs the TD06 benchmark (dip only,
60-session hold: +29.33%/trade, n=123).
- BD01 %B<=0.20: +28.95%, n=102 | BD02 %B<=0: +28.70%, n=66 |
  BD03 %B<=0.30: +30.62%, n=108 -- all within ~1pp of TD06 with FEWER
  events. Band geometry adds NOTHING to the dip trigger (noise).
- BD04/05 band exits (%B>=0.80/0.90): +8.5-9.2%/trade -- exits way too
  early; nothing beats the plain 60-session hold (3rd confirmation).
- BD06 + volume confirm: +30.31% but n=24 -- over-filtered.
- BD07 all-halal universe: +16.94% (n=324) -- tech bounces ~2x harder.
- BD08 NO 5y-strong gate: +8.53%, 57.6% win -- THE ISOLATION RESULT:
  the 5-year-strength gate is the alpha (29% vs 8.5%); the edge is
  "quality name knocked down 15%", not "price touched a band".
VERDICT: bands rejected as entry timing too (matches BB-family). The
book's validated recipe stays: halal big tech + 5y-strong + 15% dip +
60-session hold. Nothing else earns its complexity.

## MC-family: $400B+ halal mega caps (2026-08-06)

bollinger-trading/plan/megacap.py + megacap2.py. Universe: 18 halal
names >= $400B (AAPL ABBV AMAT AMZN AVGO COST CSCO GOOG GOOGL INTC
JNJ MA META MSFT NVDA TSLA V WMT; mcaps as-of-today, cached).
ARM A -- earnings variants (last yr, $50k/event): E01 DOES NOT
TRANSFER. MC01 (beat dip<=-3% open->close): +0.46%/ev, 36.4% win,
slot +$592. Any-red/-2% variants similar; gap-up continuation
-1.06%/ev; 5-session drift -1.18%/ev; miss-control n=6 inconclusive.
Mega-cap reactions are efficient -- the E01 edge lives in mid/small
caps. REJECT earnings arm on megas.
ARM B -- dip-from-top (any cause incl. crashes), uptrend 5y>=+50%,
60-session holds, entries Aug21-Jun26 vs CTRL +6.29%/hold (60.6% win):
- Depth sweep: 8% +5.91%/ev (62%) | 10% +6.91% (72.5%) | 12.5%
  +10.14% (74.2%) | 15% +11.80% (75.0%) | 20% +11.42% (n=11).
  Alpha starts at ~12%; below that it's control-level.
- Band sweep (user "12 to 20%... test different numbers"): 12-20%
  band +8.98%/ev n=33; 15-20% +11.79% n=23; upper 25 ~identical
  (few >20% dips in megas). Adjacent bands consistent (no BB-style
  scatter) -- the signal is robust to the exact numbers.
- FLEXIBLE-CAUSE decomposition:
  MC15 market-trigger only (QQQ >=10% off): +18.06%/hold, 78.6% win
  (n=14) -- buying ALL uptrend megas in a correction works with NO
  stock-level signal. QQQ>=8%: +15.0%. QQQ>=12%: never fired.
  MC16 CRASH OVERLAP (stock>=12% AND QQQ>=10%): +23.37%/hold, 87.5%
  win (n=8) -- the best per-event stats in the entire research
  program. Panic dips in quality megas are the premium buy.
  MC17 idiosyncratic (stock>=12%, QQQ near high): +9.96%/ev, 74.2%
  (n=31) -- single-name dips work too, about half as hard.
- Slot R50 (one-at-a-time): $15-47k per ~5yr -- like TD, slot-starved;
  the play is opportunistic deployment when the signal fires, not an
  always-on book.
VERDICT: adopt as the bollinger book's watchlist play alongside TD:
halal mega cap + 5y>=+50% + >=12% off the 60d high -> buy, hold 60
sessions; deploy hardest when the MARKET is also >=10% off its high
(crash overlap: 87.5% win, +23%/hold historically). Small n on the
crash rows (2022 + Apr'25 episodes) -- sizing judgment required.

## SCANNER AUDIT + FIX (2026-08-06, intraday)

User: "did the day trading buy anything? if not, check the code" -->
audit (day-trading/plan/scanner_audit.py) rebuilt the BACKTEST's
full-market discovery (Massive grouped-daily + our 50d rvol >= 5 +
high >= +10%, clean tickers, prev_close >= $2) for the paper days and
diffed it against every symbol the live RH scanner surfaced:
- Aug 4: backtest pool 20; scanner missed 6 OF THE TOP 8, including
  MOVE: +75.6% high, our-rvol 156, $7.4M volume, HALAL (comb 13.1%),
  CALM at 7AM (+6.9%) -- a full C23 qualifier, the backtest's #1 pick
  after halal-blocked AMIX, ~+69% from its 7AM price. A missed monster.
- Aug 5: scanner missed 2 of top 8 (SHPU +49%, BLMN +42%).
- ROOT CAUSE: the scan's RH 30-DAY rvol>5 filter disagrees with our
  50-day source-of-truth in both directions (showed DBGI noise, hid
  MOVE). Secondary: live protocol measured calm-gap at the 9:30 open
  instead of the backtest's 7AM (no missed trades from this in 3 days
  -- all rejects were pre-7AM-exhausted -- but corrected).
FIXES (all live as of 10:30 ET):
1. Scan 5f132877 filters reduced to Last>$2 + %change>+10% ONLY (139
   rows vs 7): the scanner is a FEED; every gate (our-50d rvol, 7AM
   calm-gap, halal, +10% at entry) is computed locally.
2. NO-SILENT-FALLBACKS policy (user directive): any stale/errored
   source or unmet intent => loud "ERROR:" line in the day log +
   day-JSON note; silent workarounds forbidden. Stale E*TRADE quote
   path: RH-bars recompute is now the authoritative rvol method.
3. Calm-gap measured at 7:00 AM ET everywhere (skill updated earlier).
Verdict on "is something wrong": the STRATEGY was fine; the FEED was
blind. 3-day no-trade streak was part tape (5 haram, 8 exhausted),
part scanner blindness (MOVE should have been traded Aug 4).

## Bar-granularity policy (2026-08-06)

E*TRADE has no history API (entitlement-locked chart endpoint; see
bollinger NOTES). Standard: RH 5-minute bars for all historical
lookups (~3mo reach; volume checks don't need 1-min); 1-minute bars
ONLY for Massive backtests and live moment-of-decision checks.

## Regression check after the 2026-08-06 fixes: FULL PASS

Fresh replays after the scanner fix, 7AM calm-gap alignment, bar-
granularity policy, and all default flips (C21->C11->C23):
- C23: Y1 +$412,879 (133d, 1,262 trades), Y2 +$579,988 (147d, 1,902
  trades) -- EXACT to the dollar vs the registered champion numbers.
- E01: +$117,755 (n=99) -- exact; ET12/13/31 rows identical.
The live-protocol bugs never touched the backtest path; code churn
introduced no drift. Paper Day 3 confirmed running the fixed protocol
(feed-only scan, local gates, 7AM calm-gap, loud-error policy) with
prior rejects re-evaluated under the corrected rule.
