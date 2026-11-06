# $100k to $300k in 12 months: results

Run 2026-11-04. Backtests only, no orders placed. Long-only, cash, one or two stocks. The original 3x campaign used the halal list. The 2x–3x update below dropped it for testing, at the user's request.

## Update 2026-11-06: forward paper test started

Five AMD methods now run as separate $100,000 paper books, from the November 5 close, in `paper/`. Fills are simulated at the next open plus 5 bp with Robinhood prices; no real orders are possible from this setup. Rules are frozen, so results from here on are the first ones not chosen with hindsight. `paper/status.md` shows the current values against AMD bought at the first open.

## Update 2026-11-06: better buy signals

`amd_buy_search.py` tested 1,142 buy rules with one fixed sell: after stochastic above 90 and RSI above 60, sell on a close 8% below the peak. The rules were a second low, the day after earnings, and the earlier zone, each with or without a market filter. The sell was chosen earlier on the same data, so the buy results are not a clean test. `amd_buy_verify.py` re-ran the best in both backtesters.

```
Buy rule                       From $100k  Worst  Lumibot    Buys right     Buys right    Table lows
                               Aug 2023           to Nov 4   before May 25  after May 25  caught
Plain zone                     $578,183    -44%   6.34x      44% of 16      88% of 8      80%
Zone, QQQ below 100-day avg    $819,499    -35%   8.91x      86% of 7       80% of 5      50%
Second low                     $708,270    -42%   6.90x      50% of 10      100% of 6     70%
Day 13, AMD above 200-day avg  $563,484    -21%   5.84x      75% of 4       100% of 5     30%
AMD held                       $338,000   about -63%
```

"Right" means AMD closed 15% up before 15% down; on every day it was 50% before May 2025 and 72% after. Zone: stochastic below 25 and RSI below 40. Second low: an oversold low, a 3% bounce, then back within 10% of that low inside 60 days with RSI 5 higher.

- **The 75% bar for buys:** 58 of the 1,142 settings pass it in both parts, 30 of them distinct. Sliding the signals along the dates gave a median of 12 passes and beat the real count once in 40, though one slide reached 115. The stricter test, 10% up before 5% down, had no passes.
- **Fragile:** zone with QQQ below its 100-day average passes on only 12 signals, and moving stochastic from 25 to 20 drops the later part to 67% of 6.
- **Fair test:** chosen on money before May 2025, that rule made 2.21x, then 3.71x against 4.15x held, with buys right 67% of 6. The 3.71x relies on already holding from April 2025. Starting fresh in May 2025 it made $216,578.
- **Starting fresh in May 2025, against $415,000 held:** day 13 $419,242, second low $389,132, plain zone $329,161, zone with QQQ $216,578.
- **The November 5 fall:** second low and day 13 were in cash for it, which flatters them. Both zone rules still hold from October 16, down 23.5%.

## Update 2026-11-06: indicator signals for the buy and sell table

The table in `AMD_QUARTERS.md` has 10 buys at lows and 10 sells at highs, known only afterwards. `amd_zone_search.py` screened 17,280 buy and sell zone rules against those dates (`results/amd_zone_search.csv`), counting a signal within 10 trading days as a catch. Winners were re-run in Vibe-Trading and Lumibot. AMD held since August 2023 made 3.38x: 0.81x before May 2025, 4.15x after.

```
Rule                    Value from $100k  Worst   Buys caught  Buys right  Sells caught  Sells right
Best money              $578,183          -44%    20%          18%         70%           70%
Closest to the table    $381,051          -38%    40%          57%         60%           86%
```

- **Best money:** buy on stochastic below 25 and RSI below 40. Sell after stochastic above 90 and RSI above 60, on a close 8% below the peak since then. Hold at least 15 days, no stop. Lumibot 6.34x through November 4; Vibe-Trading through that date would be about $699k, and the gap was not traced.
- **Closest to the table:** buy on stochastic below 25, RSI below 40, at least 25% below the 63-day high, then a close 5% above the low since. Sell after stochastic above 80 and RSI above 65, on a close 8% below the peak. 25% stop. Lumibot 4.26x.
- **The 75% bar:** sells can reach it (86%, on 7 signals, on the data used to pick the rule). Buys do not. Oversold readings often come weeks before the low.
- **Fair test, corrected 2026-11-06:** the first version credited a trade to the part where it was bought, so April 2025's rebound counted before May 2025. Measured from daily value, held made 0.81x then 4.15x. Picks on the first part made 1.57x in the last, and picks on the last part made 0.89x in the first. 6,956 settings beat holding in the first part, 2,232 in the last, and 974 in both. The earlier "none in both" was wrong.
- **Selling on a fall works better than selling on the reading:** median 3.30x for an 8% fall from the peak, 1.80x for selling at once.

Earlier searches for the same bar, same conclusion. `amd_ta_rules.py` (312 rules): none beat the buy day 12, sell 7 days before rule in 2025–26. `amd_ta_brainstorm.py` (722 buy and 702 sell signals, singles and pairs): signals passing in both 2025–26 and 2024 do not clearly beat rotated data. `amd_tv_indicators.py` (TradingView-style ideas from 12 repos, re-coded in Python, 34 buy and 33 sell signals, none looking ahead): buys pass 4 against a rotated median of 6; sells pass 2 against a rotated median of 0, beating 32 of 40 rotations, the only result here that beats its luck check. Those two sells are Volatility Ratio down close with QQQ above its 100-day average (83% of 6, 75% of 8), and Weis Wave down wave below the 200-day average (80% of 5, 80% of 5). Neither has been backtested for money yet.

## Update 2026-11-05: wider buy and sell day grid

All 1,335 combinations from January 30, 2024 (`amd_wide_grid.py`). The best is buy on day 2, sell 7 days before: $459,778, +74% a year, worst −51%, against AMD held at $243,752 ($294,759 through November 4). It lost in the weak period and made its gain in the strong one, and the best sell day flips between them: earlier in the weak period, later in the strong one. Perfect timing would have made +43% a quarter.

## Update 2026-11-05: buy days 10–20, sell 5–15 days before the next report

All 121 combinations, $100k, time only, in Vibe-Trading through 2026-11-05 (`amd_time_grid.py`, `results/amd_time_grid.csv`). AMD held made $361,160 over 3 years with a worst fall of −63%, and $239,504 since October 2025. Of the 121, 79 beat holding over 3 years and 15 since October 2025. The best is buy on day 12, sell 7 days before: $573,321 over 3 years, worst fall −59%, $263,740 since October 2025, and Lumibot gives 5.58x against 5.73x in Vibe-Trading.

- **The sell day matters more than the buy day.** Nine of the best 10 sell 7 or 8 days before, and selling 12–15 days before was weakest.
- **Bumpy results.** Moving from 7 days to 6 days before cuts the best buy day's value from $573,321 to $466,458, and buy day 16 makes $436k at 7 days before while day 17 makes $539k. A few trades carry much of these differences, so the exact best cell is partly luck.
- **Today flatters every rule against holding.** The rules were in cash through today's fall (close $404.40). Holding through the November 4 close would be about $437,000.
- **Check on later quarters.** Ranked on the first 8 quarters, the top pick was buy day 18, sell 5 days before: 2.29x, then 2.15x in the last 4. AMD held made 1.94x from the Nov 2025 report to the Nov 2026 report. This range was narrowed after seeing earlier results over the same 3 years, so it is not a clean test.

## Update 2026-11-05: strategy built from the six patterns in `AMD_QUARTERS.md`

**The strategy made much less than holding AMD, and less than the simple time-only rules.** Backtest only, no orders. Run in Vibe-Trading with $100k, data through 2026-11-05 (`amd_strategy.py`). Settings were fixed before any backtest, and every addition stayed in. Today's price kept moving, so AMD held is $361,160 here against $366,795 above. All of this is in-sample, because the patterns were read from these same 3 years.

| Version | Addition | Since Oct 2025 | 3 years | Worst fall (3 years) | Trades |
|---|---|---|---|---|---|
| AMD held | | $239,504 | $361,160 | −63% | |
| v3.0 | Pattern 1: buy the second low | $258,222 | $110,622 | −44% | 7 |
| v3.1 | + pattern 2: half size unless lows are rising | $189,468 | $106,935 | −28% | 7 |
| v3.2 | + pattern 3: 10% trail on days 26–53 | $131,698 | $133,078 | −18% | 7 |
| v3.3 | + pattern 4: sell half at +28% | $136,934 | $138,370 | −18% | 8 |
| v3.4 | + pattern 6: day after the report | $172,216 | $201,236 | −23% | 18 |
| v3.5 | + pattern 5: stay out of bad shapes | $113,748 | $216,392 | −23% | 16 |

- **Mostly in cash.** v3.5 was invested 22% of the time on average, and reached 2x or 3x in none of the 12-month periods. It reached 20% in 3 of 12 quarters.
- **Large misses.** In v3.4, the Aug 2025 quarter made −2.5% against AMD's +43.5%, and Feb 2026 made −3.9% against +46.7%.
- **Depends on the start date.** v3.0 beats holding since October 2025 but makes $110,622 over 3 years.
- **Nearby settings.** None of 81 variations of v3.4 beat holding, with 3-year values from $165,720 to $263,996.
- **Simple rules did better.** Buying on day 13 and selling 15 days before the next report made $370,505 and $179,828. Buying on day 10 and selling 5 days before made $488,920 and $223,683. Those were also fitted to these years.
- **Lumibot:** v3.4 1.74x and 1.98x against 1.72x and 2.01x in Vibe-Trading. v3.5 1.13x and 2.15x against 1.14x and 2.16x.

### How a quarter usually behaves

All 13 quarters were stretched onto one timeline by interpolation (`amd_typical_quarter.py`). The median falls to about −10% around day 21, rises to about +15% around day 48, and ends at −3%. But the middle half at the end runs from −13% to +46%, so the median describes few quarters. Each quarter's fit with the typical shape of the others averages −0.02, against +0.02 for random stretches of AMD, and 59% of random sets did at least as well. So there is no reliable single "usual quarter".

### Pattern 5 as it unfolds

Typical paths for each shape were compared with the quarter so far (`amd_shapes_live.py`). Shapes are labels I gave after the fact. Judged with later quarters allowed, the shape was right 46–62% of the time against about 25% by chance. Judged only from earlier quarters, which is what could really be done, it was right 45–55%. Either way it did not help with money: at day 20, quarters judged good then made +16% on average (3 quarters) and quarters judged bad +14% (8 quarters). It wrongly judged Aug 2025 (+54.2% afterward) and Feb 2026 (+75.8%) as bad.

## Update 2026-11-05: 20% every quarter, timed from earnings dates

**No rule made 20% every quarter.** Across 204 rules and 12 quarters, the best reached 20% in 7 quarters, and every rule lost money in at least 2. Even perfect timing reaches 20% in only 11 of 12: the most available after the October 2024 report was +9%. No rule beat AMD held since October 2025, and 56 of 204 beat it over 3 years. Run in Vibe-Trading with $100k and data through 2026-11-05 (`amd_quarters.py`). Today's bar moved between runs, so AMD held is $243,119 here against $245,915 above.

| Rule | Since Oct 2025 | 3 years | Quarters at 20%+ | Losing quarters | Worst fall (3 years) |
|---|---|---|---|---|---|
| AMD held | $243,119 | $366,795 | | | −63% |
| Time only, set in advance: buy day 13, sell 15 days before the next report | $179,828 | $370,505 | 5 | 3 | −41% |
| Set in advance: same, also buy next day after a 10%+ jump, and sell at +20% | $188,804 | $436,654 | 6 | 2 | −41% |
| Most quarters at 20%: buy day 10, sell 15 days before | $186,774 | $382,083 | 7 | 4 | −44% |
| Highest time-only without the extra trade: buy day 10, sell 5 days before | $223,683 | $488,920 | 4 | 4 | −57% |

- **Selling earlier cost money.** Buying on day 10, 3-year value falls from $489k selling 5 days before the next report to $382k at 15 days and $172k at 30 days. Since October 2025 it falls from $224k to $187k to $135k. So dodging the usual pre-report fall did not pay.
- **Buy day matters less.** Selling 5 days before, days 10–20 made $423–489k against $354–402k for days 1–5, with no smooth trend.
- **The two weak quarters:** November 2025 went from −2.1% to +4% and stayed below 20%. Its best trade needed a buy on December 17, later than the pattern's low. May 2026 went from +5.1% to +15% with time only, and +25% with the jump rule.
- **Losing quarters:** the October 2024 and February 2025 quarters lost 15% and 12% in both set-in-advance rules.
- **The extra 3-day trade before reports:** median $292k with it, $283k without, so little difference.
- **Fair test:** ranked on the first 8 quarters, the top time-only rule made 1.59x in the last 4, and the top rule overall made 1.75x. AMD held made 1.94x. Each reached 20% in 1 of those 4 quarters.
- **Lumibot:** eight runs on four rules, within about 0.11x of Vibe-Trading.

## Update 2026-11-05: AMD's earnings pattern, and what it would have made

Read from the last 12 reports (`amd_pattern.py`). All figures are medians of highs and lows picked afterwards.

1. **Falls before the report:** starts about 3 weeks before and bottoms about 2 days before, −12%, in 12 of 12.
2. **Small bounce into the report:** +4% from that low, in 10 of 12. The final 2 days alone rose in only 6 of 12.
3. **Falls after the report:** −4% the next day, lowest close about 13 trading days after at −10%, in 10 of 12.
4. **Big rise:** +34% from that low, peaking about 48 trading days after the report, in 11 of 11.

Against fake dates 3–9 weeks from the reports, the fall before and the rise after look much the same (−11.2% and +29%). What differs is the next day (−4.4% vs +0.1%), the drop after (−10.4% vs −6.9%, and later), and the full cycle (6 of 11, 55%, vs 36%).

Backtest in Vibe-Trading, $100k, cash between trades, through 2026-11-05 (`amd_pattern_test.py`). Today's bar moved during the run, so it may not be final.

| Rule | From 2025-10-01 | Worst fall | Last 3 years | Worst fall |
|---|---|---|---|---|
| AMD held | $245,915 | −36% | $370,975 | −63% |
| Buy on day 13, sell on day 48 | $170,957 | −17% | $371,476 | −41% |
| Buy 10% below the report-day close, else on day 13, sell on day 48 | $160,544 | −17% | $326,166 | −43% |
| Same, but skip the report if no 10% fall within 20 days | $152,946 | −15% | $110,083 | −41% |

The pattern lost to holding from October 2025 mainly because it sold at $255 in April 2026 and rebought at $485 in May, after a +19% report. Lumibot gives 1.57x against 1.61x for the third row, but stops at the 2026-11-04 close, so its 2.92x for AMD held is not comparable. The pattern was read from these same reports, so these results flatter it.

`amd_fallcycle.py` (buy each fall, sell the rebound) was stopped at the user's request before finishing, and it has no results yet. `amd_falls.py` lists the falls: 10 of 15% or more and 8 of 25% or more, including 36% from 2026-10-06 to today.

## Update 2026-11-05: AMD alone, last 3 years, weekly or monthly decisions

Window: 2023-11-06 to 2026-11-04, $100k, cash allowed, 12 earnings reports, run in Vibe-Trading with next-open fills and 5 bp slippage. The user's scope was the last 3 years only, so earlier years were not tested. AMD held made 4.37x (1.30x, 1.64x, 2.06x by year), with a worst fall of −63%.

**Best result: staying out around earnings beat holding, but it does not reach 3x a year, and its lead did not show up in the one fair year test.** Trying to buy lows and sell highs from readings or falls did worse than holding.

| Rule | 3 years | By year | Worst fall | In market | 2x / 3x share of 12-month periods |
|---|---|---|---|---|---|
| AMD held | 4.37x | 1.30 / 1.64 / 2.06 | −63% | 100% | 29% / 17% |
| Buy at the first month-end after a report, sell two month-ends later | 6.10x | 1.45 / 2.06 / 2.04 | −47% | 67% | 50% / 25% |
| Weekly: sell 2 Fridays before a report, rebuy the first Friday after | 5.86x | 1.60 / 1.66 / 2.22 | −46% | 84% | 38% / 29% |
| Best wait-for-25%-fall rule | 4.81x | 1.00 / 2.34 / 2.06 | −32% | 56% | 50% / 17% |
| Study rule, set in advance | 0.97x | 0.98 / 0.99 / 1.00 | −57% | 39% | 0% / 0% |

### The earnings cycle

| Step | Average | Went the expected way | Ordinary AMD period |
|---|---|---|---|
| Dip, 4 weeks to 1 week before | +7.0% | Down in 6 of 12 | +4.2% |
| Rise, last week before | +1.1% | Up in 7 of 12 | +1.3% |
| Reaction, the day after | −2.6% (median −4.4%) | Down in 7 of 12 | +0.3% |
| Drop, first 2 weeks after | +0.8% | Down in 5 of 11 | +2.4% |
| Recovery, weeks 3–8 after | +6.7% | Up in 7 of 11 | +9.2% |

Only the reaction day stands out (p = 0.013, before allowing for five tested steps). All five steps happened together in 0 of 11 reports. Moves that day are large, about 6% against 2% on an ordinary day, and go both ways: −17% in February 2026 and +19% in May 2026.

### Study of lows and highs

Swings of 20% or more come about every 2.7 months. Buying every low and selling every high would have made 66x, a ceiling known only afterwards.

| | Lows (6) | Highs (7) | Normal day |
|---|---|---|---|
| 14-day RSI | 23–38 | 65–76 | 52 |
| Against the 50-day average | 13–26% below | 14–41% above | 1% above |
| Fall from the 1-year high | 25–57% | 0–18% | 19% |

No high came within 4 weeks after a report, and most came 8–11 weeks after. Half the lows came within 2 weeks after a report.

### Results

- **Run 1, earnings timing (48 rules):** 11 beat holding. In the "skip the report" group, 8 of 18 beat it, with a median of 4.22x. Holding only the run-up never beat it (0 of 8).
- **Run 2, wait for a fall:** 2 of 48 rules beat holding at a 20% fall and 3 of 48 at 25%, with few trades, mostly carried by April 2025.
- **Run 3, from the study (324 rules):** none beat holding, and the median was 1.00x. The rule set in advance bought in April 2024 at 146.64, sat through the fall to 78, sold in June 2025 at 143.81, and was then in cash while AMD rose past 600. The readings describe turns, but they also appear on ordinary days and can be absent in a long rise.

### Checks on the two best rules

- **Fair test:** ranked on the first 2 years, the top pick was the month-end rule: 2.99x against 2.12x for AMD held, then 2.04x against 2.06x in year 3. So no lead in the one unseen year. Ranked backwards on the last 2 years, the top pick made 1.08x in year 1 against AMD's 1.30x.
- **Shifted report dates:** real dates ranked 1st of 13 for both rules. Moved by up to 6 weeks either way, the medians were 2.34x and 3.10x. This supports timing around reports, but the rules were chosen by their results, and 1 of 13 is weak evidence by itself.
- **Lumibot:** month-end rule 5.81x vs 6.10x in Vibe-Trading, weekly rule 6.07x vs 5.86x, AMD held 4.50x vs 4.32x.
- **Limits:** 12 reports in one strong 3-year rise. The two rules were picked from those same 3 years. Report dates come from Yahoo and are assumed to be known in advance. Taxes on the extra trades are not modelled.

## Update 2026-11-05: 2x–3x with AMD first and a second stock

**Nothing reaches the goal.** The target was 3x in at least 50% of 12-month periods, and for 2x the same 50% bar. Across 8,452 setups and 26 cumulative additions:

- The best 3x share on unseen data was 17% among kept versions and 20% for v1.7, which was not kept. For most versions it came from one rally starting in 2025.
- The best rule chosen in advance reached 2x in 27% of periods, the same as holding AMD (27%), with a lower typical year (1.43x vs 1.65x).

### The ladder: one strategy, one new addition per version

v1.0 is AMD first with a second stock chosen each January from earlier data. It enters on positive 126-day momentum above the 200-day average, and exits on a 25% trailing stop. It was picked on data through 2020.

An addition stayed only if it raised the train score (share reaching 2x + share reaching 3x, periods starting 2013–2020) by at least 0.02. Periods starting in 2022 or later ("unseen") were never used to choose. Each row averages six ways of choosing the second stock. Periods are 12 months, restarted monthly.

| Version | Addition kept | Train 2x / 3x | Unseen 2x / 3x | Unseen median | Unseen worst | Last 12 months |
|---|---|---|---|---|---|---|
| Reference 1 | AMD held | 31% / 8% | 22% / 9% | 1.43x | 0.43x | 1.89x |
| Reference 2 | Half AMD, half second stock, held | 22% / 4% | 12% / 0% | 1.43x | 0.36x | not computed |
| v1.0 | Base rule | 25% / 8% | 13% / 0% | 1.10x | 0.16x | 1.58x |
| v1.6 | Tighter 15% stop after a +100% gain | 30% / 12% | 20% / 16% | 1.15x | 0.18x | 2.31x |
| v1.19 | Let the second stock run unless AMD is clearly stronger | 37% / 11% | 26% / 17% | 1.24x | 0.16x | 2.17x |
| v1.21 | Second stock must rise through many small gains | 40% / 15% | 23% / 15% | 1.28x | 0.29x | 2.17x |
| v1.23 | Skip the second stock after an 8% one-day jump | 43% / 16% | 2% / 0% | 1.15x | 0.38x | 0.87x |
| v1.25 | Buy AMD when VIX fades from above 40 to below 30 | 44% / 18% | 2% / 0% | 1.21x | 0.43x | 0.87x |

Tested and not kept: market filter, sector filter, gap entry, trend-strength sizing, pyramiding, choosing the second stock when selling, rebound entry, buying in steps, volatility-scaled stop, longer hold, rebuy on new high, above-50-day entry, relative strength, volatility cap, half size in the second stock, cooldown after losses, drawdown brake, early hard stop, overnight-trend gate, steadiest-climb ranking and earnings veto. All rows are in `results/ladder.csv`.

- **It overfits.** The train score keeps rising while the unseen score collapses at v1.23.
- **The stricter v2 ladder did not fix it.** v2 also required no fall in either half of train (2013–16 and 2017–20). It kept three additions and ended at 4% / 0.4%, with a 1.09x median (`results/ladder_v2.csv`).
- **Results are fragile.** Changing only the VIX setting from 40/30 to 30/25 moves v1.25's unseen 2x share from 2% to 30%, and its last 12 months from 0.87x to 2.11x. The train data preferred 40/30.
- **Few real episodes.** v1.6 and v1.21's 3x hits are all one run of start dates in 2025. v1.19's are two, starting from January 2023 and in 2025.
- **Costly in bad years.** The versions up to v1.19 turned the 2024 start dates into a chain of whipsaws between AMD, COIN and APP, with a worst period of 0.16–0.18x. AMD held had a worst of 0.43x.

### Every setup, chosen in advance

Each cell is the best of three ways of choosing, on 118 periods from 2016. AMD held scored 27% with a 1.65x median in the same periods.

| Pool | Reached 2x | Median | Lost money | Worst |
|---|---|---|---|---|
| Second stock from growth | 25% | 1.37x | 25% | 0.40x |
| From biotech and health | 19% | 1.48x | 19% | 0.28x |
| From energy | 14% | 1.45x | 15% | 0.43x |
| From materials | 14% | 1.35x | 20% | 0.44x |
| From consumer and industrial | 13% | 1.25x | 27% | 0.47x |
| AMD-first, $100k | 20% | 1.32x | 21% | 0.57x |
| AMD-first, $50k | 0% | 1.18x | 18% | 0.68x |
| AMD-first, 3 steps on falls | 12% | 1.19x | 22% | 0.64x |
| AMD-first, 4 steps on falls | 8% | 1.20x | 21% | 0.71x |
| AMD-first, half in each | 7% | 1.13x | 38% | 0.55x |
| Hold a stock or cash for 21 or 42 days at a time | 21% | 1.25x | 24% | 0.58x |

The strongest group overall was stocks on the project's halal list, at 27% and a 1.43x median. The holdout test (chosen through 2021, scored 2022 on) was weaker, with a best of 15%.

### With hindsight, it looks solved

- **37 of 8,452 setups pass the 50% bar in hindsight.** All use APP, IONQ, CEG, HOOD, CVNA or PLTR, picked knowing they won, and they cover 45–102 periods rather than the full history.
- **The CEG example is the best of them.** AMD+CEG with monthly 10-day momentum reached 2x in 67% of periods, with a 2.35x median and a 0.82x worst. It covers only 45 periods, since CEG listed in 2022, and only 4 of 188 AMD+CEG setups pass, with a median setup at 2%.
- **The ceiling shows what is missing.** With the winner picked after each period, some setup reached 2x from 95% of start dates and 3x from 71%. The average setup did so from 10% and 2.4%. The returns existed, but nothing here identified the winning setup in advance.

### Checks

- **Independent replay.** A separate replay of the weights matched Vibe-Trading to a 1.00 ratio in every year for v1.0 and v1.6.
- **Base rule.** With no additions, the ladder gives weights identical to the original AMD-first rule on 288 setups.
- **Vibe-Trading vs Lumibot.** Lumibot was run on `broad_vol30_12m` for the worst and best stretches:

| Version | March 2024–March 2025 | June 2025–June 2026 |
|---|---|---|
| v1.6 | 0.18x / 0.21x | 4.37x / 4.77x |
| v1.19 | 0.17x / 0.20x | 3.95x / 4.62x |
| v1.25 | 0.52x / 0.50x | 1.14x / 1.19x |

  Lumibot runs higher in the big year, by up to 0.67x. That is above the earlier 0.34x maximum, and I did not trace the cause. It does not change the conclusion.
- **Cost stress at 5/15/30 bp was not run,** because no version passed.

### Bug fixed

"Half in each" on the yearly second-stock rules gave every name 1/N of the money, not 50%. I fixed it and re-ran those 144 curves before scoring. Named two-stock runs were not affected.

### What each repo contributed to this update

- **Vibe-Trading:** ran every backtest. Its skills supplied the regime and ATR ideas.
- **Lumibot:** the independent cross-check above. Its Bensdorp example strategies supplied entries for the base grid.
- **pysystemtrade:** trend-strength sizing (v1.4) and buffering (v1.19).
- **freqtrade:** position adjustment, DCA and protections (v1.5, v1.9, v1.17, v1.18).
- **Published rules and papers:** Minervini, Turtle and Darvas, O'Neil, Clenow, and four papers proposed by a helper. It reported most of that evidence as portfolio-level or read only in summary.
- **Surveyed for ideas only, not run:** Lean, vectorbt, backtesting.py, Qlib and RD-Agent, FinRL, ai-hedge-fund, backtrader, NautilusTrader.
- **TradingAgents:** not used here. It issues ratings for single dates, and about 13 years of periods would need far more model runs than the 51 decisions it made earlier.

### Limits of this update

- **The unseen data is no longer clean.** From v1.10 on, additions were designed after I saw the 2022–25 trades, and v2 after I saw the collapse. These numbers are not a clean test. Rows above v1.10 had their order fixed in advance.
- **Halal.** It was dropped for testing only. Second stocks here include names off the project's list and names with no ruling, so check any name before acting on it.
- **Survivorship.** The stock lists are today's, so companies that later vanished are missing.
- **Growth.** Past price return stands in for growth, because point-in-time revenue growth was not available.
- **Reference 2.** It uses the same second stock as the rule. Fortune 500 membership was not verified.
- **Earnings dates.** They come from Yahoo and may include errors.
- **Not modelled.** T+1 settlement and taxes. All multiples are pre-tax.
- **Overlap.** Monthly starts overlap heavily, so the percentages rest on few independent years.

### Why adding versions is paused

Each further version can be chosen only on data that has already shaped the ladder, and the ladder's scores on older data rise whether or not the addition works. More versions would keep improving the train column without showing anything new. A test that means something now needs data none of this has seen, such as a forward paper run. That has not been started and needs the user's go-ahead.

## Verdict (original 3x campaign)

**No strategy reliably makes 3x in a year.** Picked fairly, the best methods reached 3x in about 1 of every 14 twelve-month periods. The typical result was about 1.4x, and roughly 1 period in 7 lost money.

Some runs did reach 3x, and a few exceeded 4x. Nearly all of them fall into a few market stretches, so they don't show a repeatable edge.

## The fair test

At each monthly start, the rule could only use earlier data to choose both the method and the settings. It then held that choice for 12 months.

| Pool | Periods | Reached 3x | Reached 2x | Lost money | Median | Worst |
|---|---|---|---|---|---|---|
| Any one top-50 halal stock, bought and held (base rate) | all | 0.8% | 3.7% | | 1.19x | |
| Top-50 rotation, no AMD assumed (2019 on) | 82 | 0–7% | 17–30% | 12–16% | 1.33–1.42x | 0.66x |
| AMD plus one other stock (2016 on) | 118 | 6–8% | 20–27% | 14–20% | 1.34–1.54x | 0.40x |
| All methods together (2016 on) | 118 | 3–7% | 14–25% | 11–23% | 1.27–1.55x | 0.40x |

Each range covers four ways of choosing the method. Drawdowns inside these holds reached -73%.

- **Few independent episodes.** Monthly starts overlap heavily. With the 3x-seeking selection score, the AMD-pair hits fall in 2016, 2017, 2019 and 2025. The rotation hits all fall between December 2023 and June 2025.
- **AMD and the pair list carry some hindsight.** AMD was named today, and the list of partner stocks is present-day. Only the rotation row avoids assuming AMD, although its halal screen is also present-day.

## Candidates in two backtesters

Each cell shows Vibe-Trading / Lumibot, with $100k, 5 bp slippage and next-open fills.

| Strategy | 2023 | 2024 | 2025 | Last 12 months | Max drawdown |
|---|---|---|---|---|---|
| AMD+PLTR, monthly, 63-day momentum | 2.99 / 2.96 | 3.95 / 4.01 | 2.67 / 2.58 | 1.91 / 2.12 | -80% |
| AMD+PLTR, daily, 10-day momentum | 2.01 / 1.87 | 2.76 / 3.06 | 2.61 / 2.52 | 2.50 / 2.70 | -80% |
| Strongest top-50 stock or AMD, monthly, 126-day momentum | 1.70 / 1.73 | 1.80 / 2.01 | 2.71 / 2.55 | 2.16 / 2.19 | -49% |
| AMD+NVDA, monthly, 126-day momentum | 3.46 / 3.41 | 2.45 / 2.28 | 1.64 / 1.66 | 1.86 / 1.95 | -69% |
| AMD+MU, monthly, 126-day momentum | 1.70 / 1.69 | 0.75 / 0.70 | 2.66 / 2.32 | 3.94 / 4.14 | -72% |
| AMD bought and held (baseline) | 2.30 / not run | 0.87 / not run | 1.78 / not run | 1.86 / 1.95 | -80% |

- **These are mostly hindsight.** The AMD+PLTR, AMD+NVDA and AMD+MU rows use settings or partners known to have worked. PLTR only enters the approximate top-50 list in 2025 and MU in 2026, so the rule couldn't have traded those pairs in earlier years.
- **The two engines agree.** Differences are mostly within 0.2x; the largest is 0.34x (AMD+MU in 2025). Only the last 12 months of AMD buy-and-hold were cross-checked.
- **Costs don't change the picture.** At 30 bp, the monthly strategies lose about 0.01–0.06x a year. The daily one loses 0.2–0.4x.
- **Vibe's validation is mostly favourable but not decisive.** Bootstrapped Sharpe was above zero in every case, and 4 or 5 of 5 sub-periods were profitable. Trade-shuffling p-values ran from 0.00 to 0.10. None of this corrects for choosing among about 3,300 configurations.

## What each repo contributed

- **Vibe-Trading:** 3,325 daily and 23 hourly configurations, and the main simulator.
- **Lumibot:** an independent re-run of the candidates and the TradingAgents positions.
- **Vibe's research agent:** its two picks were tested on later years and trailed buy-and-hold in most of them. AMD with a 50-day trend and volatility filter made 1.94 / 0.98 / 1.61 / 1.00x, against 2.23 / 0.84 / 1.75 / 1.86x for AMD held. Over the same periods (2023, 2024, 2025, last 12 months), AMD+NVDA above the 100-day average made 2.37 / 1.54 / 1.57 / 1.11x, against 2.78 / 1.78 / 1.56 / 1.43x for the pair held. Its multi-agent swarm did not finish, because it hit a token limit at about 3.5M tokens.
- **TradingAgents:** weekly decisions from 2026-07-06 to 2026-10-26, which is after the model's knowledge cutoff.

| Stock | Ratings over 17 weeks | Fixed mapping (Vibe / Lumibot) | Trim mapping, added after seeing ratings (Vibe / Lumibot) | Bought and held (Vibe / Lumibot) |
|---|---|---|---|---|
| AMD | 11 Hold, 6 Underweight | 1.00 (never bought) / not run | 0.99 / 1.04 | 0.94 / 0.95 |
| NVDA | 9 Hold, 8 Overweight | 1.00 / 1.01 | 1.07 / 1.08 | 1.07 / 1.07 |
| MU | 13 Hold, 4 Underweight | 1.00 (never bought) / not run | 0.89 / 0.92 | 0.93 / 0.88 |

Seventeen weeks can't test a 12-month target, and it was a weak stretch for AMD and MU. So this neither supports nor rules out TradingAgents as a way to reach 3x. It rated AMD and MU no higher than Hold in all 17 weeks, though, so a strong rally in those stocks would likely have been missed under the fixed mapping.

**Ideas that failed:** gap drift, 52-week highs, volatility squeezes, down-day buying and relative-strength leaders had a median 12-month result of about 1.0x across 460 runs. Holding only overnight over 23 months lost money on 17 of 23 stocks. MU was the best, at 3.18x across the whole 23 months.

## What the rules select today

The answer depends on the lookback, which shows how unsettled the choice is. "Signal" is what each setting would choose if it re-picked on 2026-11-03.

| Pool | 1-year | 2-year | 3-year | 5-year |
|---|---|---|---|---|
| Rotation, no AMD assumed | MU | LLY | MU | LLY |
| AMD plus one stock | AMD (AMD+MU) | AMD (AMD+PLTR) | PLTR (AMD+PLTR) | PLTR (AMD+PLTR) |

This isn't a recommendation. Check the halal status of any name before acting on it.

## Limits of these results

- **Survivorship:** the top-50 list is approximate, built from price times shares. Companies that disappeared through mergers are missing, and the halal list is today's.
- **Not modelled:** cash-account T+1 settlement and taxes. A daily rotation could trigger good-faith violations in a cash account. All multiples are pre-tax.
- **Market period:** 2023–26 was an exceptional stretch for AI and chip stocks, and it supplies many of the hits.
- **TradingAgents data:**
  - FRED macro data wasn't available because there is no key.
  - Yahoo fundamentals are withheld on past dates.
  - News came from the Massive feed, filtered by date.
  - Each decision is one model sample, on Claude Haiku and Sonnet.
  - The helper's context still shows the real date, and a replay rule tells it to ignore that. An audit of all 51 decisions found no mention of the real date. Later dates appear in 8 decisions, and all are scheduled events or planned review dates, such as earnings and FOMC meetings.
  - SEC requests use TradingAgents' default placeholder contact.

## Bugs found and fixed

- **Rotation never went to cash.** The pair rotation kept its last pick when momentum was negative, instead of going flat. Those runs are valid but test a different rule. I added the intended version as `cash1` (484 runs), and both versions competed in the final tests. The AMD pair runs in the tables above are the original version.
- **Lumibot adapter.** It re-picked on the wrong dates and failed on Vibe's `NVDA.US` ticker format. Both are fixed, and the affected checks were re-run.
- **First TradingAgents runs.** They were invalid because the helper saw the real date and called all data stale. They are archived in `results/invalid_date_leak/` and not used here.

## Why I stopped

You asked me not to stop until reaching 3x. Testing more variants would eventually produce a strategy that shows 3x by chance, and that result wouldn't hold up with real money. A real test now needs new data, not more searching.

## How to reproduce

Run from `three-x/`:

- Sweeps: `sweep.py <singles|pairs|pairs_cash|topk|batch2|overnight|first|auto|switch|sectors>`
- Ladder: `build_growth_partner.py`, `build_growth_pool.py`, `build_earnings.py`, then `ladder.py 4 v1` or `ladder.py 4 v2`
- Scoring: `analyze2.py`, `episodes.py`, `meta_wf.py`, `sector_score.py`, `ceiling.py`
- AMD study: `amd_earnings.py`, `amd_turns.py`, `amd_cycle.py`, `amd_placebo.py`, `amd_falls.py`, `amd_fallcycle.py`, `amd_pattern.py`, `amd_pattern_test.py`, `amd_quarters.py`
- Stress and cross-checks: `validate.py`, `lb_check.py`, `ta_to_vibe.py`
- TradingAgents: `claude_bridge.py`, `ta_run.py`, `ta_audit.py`

Repos and virtual environments are in `E:\strategy-repos\`. Key result files are committed in `results/`; curves and logs are not.
