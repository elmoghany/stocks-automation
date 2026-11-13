# Why the AMD rules fell short of 2x of holding, and whether 2x is realistic

Written 2026-11-12. Research only: no orders, no Robinhood tools, nothing in `paper/` or `amd_paper.py` was changed. All new code is in `three-x/diag/`, and every number below can be regenerated from it (list at the end).

The new target: a long-only, cash-when-out loop that ends with twice the money that buying and holding AMD would have made over the same period. "If hold makes 300%, we want 600%." Read literally as "final value twice that of holding", the target is 2 times the held multiple (held $100,000 growing to $400,000 means the loop must reach $800,000, which is 8x). If it is read as twice the gain (300% and 600%, so 4x against 7x), the bar is a little lower: in 2023-2026 it would be 8.7x instead of 9.67x. I use the first reading throughout; the conclusions do not change under the second.

Labels used throughout. **HINDSIGHT** means the number uses the whole window to find the best trades or the falls; it is a ceiling or a description, not something a rule could do. **Causal** means a signal uses only data up to the decision close, and fills at the next open, 5 bp per side.

## The short answer

1. Hold turned $100,000 into $483,654 from the Aug 1 2023 open to the Nov 11 2026 close (4.84x). Twice that is $967,308 (9.67x). Over 2013 to Jul 2023, hold turned $100,000 into $4.48 million (44.8x); twice that is $8.97 million.
2. To reach 2x of hold, the days a rule spends in cash must add up to a fall in AMD of about 50% (AMD's price halving, counting only the cash days), and a rule that is out of AMD half the time has to find that fall while giving up about half of AMD's own rise. In 2023 to 2026 AMD rose 383%, so cash days cost about 0.19% per day (about 3.9% per 20 days).
3. In hindsight it is possible, by a lot: with perfect foresight, 4 round trips in 3.3 years would have made 36x ($3.6 million). To get 2x of hold you need only about 34% of that edge (in log terms). But with real timing the margin is thin: dodging all eleven 15%+ falls with each exit and re-entry 5 sessions late gives 3.7x of hold; 10 sessions late gives 1.46x, which is below 2x. One 20-session false alarm for each correct dodge, with exits only 3 sessions late, drops the result to 1.36x.
4. Of the 13 rules re-created from the earlier studies, one reached 2x of hold in 2023 to 2026 (the zone rule with the QQQ filter, 2.32x of hold, $1.12 million), and it is the best of more than a thousand settings searched on that same window. In 2013 to Jul 2023, none of the 13 even matched hold: the best was 0.86x of hold; that same zone rule made 0.08x of hold.
5. I found no predictive signal in AMD's daily data that is both stable across 2013-2023 and 2023-2026 and large enough. The stable facts are about size, not direction: AMD moves about 9% on report day against 2.5% on an ordinary day, it has a beta of 1.4 to 2.1 to QQQ, and volatility clusters (correlation 0.15 to 0.18). None of those says when to be in or out.
6. Verdict: 2x of held is not realistic for a single-stock, long/cash, daily-bar loop. Nothing measured here gives a reason to expect it out of sample. Details and ranked directions are at the end.

## 1. What 2x of held requires

### 1a. The ceiling: best possible round trips (HINDSIGHT)

Best total result from $100,000 with at most K round trips, found by dynamic programming over every open, with 5 bp per side, exiting at the last close if still in. Window A is Aug 2023 to Nov 11 2026 (3.27 years). Window B is 2013 to Jul 2023 (10.56 years); its K values are scaled up to the longer window.

```
Window A (3.27 yrs), held 4.84x ($483,654), target 9.67x ($967,308)
Round trips   Ceiling        Ceiling / held   Share of the log ceiling needed   Share of the log EDGE over hold needed
4             36.1x          7.5x             63%                               34%
8             92.2x          19.1x            50%                               24%
12            177.6x         36.7x            44%                               19%
20            475x           98x              37%                               15%
40            2,831x         585x             29%                               11%
no limit      106,126x       21,942x          20%                                7%

Window B (10.56 yrs), held 44.8x, target 89.7x
Round trips   Ceiling         Ceiling / held   Share of the log edge over hold needed
4             982x            21.9x            22%
14            47,877x         1,068x           10%
28            1,269,869x      28,320x           7%
no limit      2.4e15x         5e13x             2%
```

"Share of the log edge needed" is ln(2) divided by ln(ceiling / held): the fraction of the available outperformance, counted as compounding growth, that a rule must capture. The ceilings are enormous because AMD swings a lot. The 4-trip ceiling in window A is: buy Oct 27 2023 at $95.80, sell Mar 8 2024 at $213.41 (+123%); buy Aug 5 2024 at $122.16, sell Oct 9 2024 at $174.05 (+43%); buy Apr 9 2025 at $79.22, sell Oct 29 2025 at $264.19 (+234%); buy Mar 9 2026 at $189.36, sell Oct 6 2026 at $648.04 (+242%). The lists for 8 and 12 trips are in `diag/out/d1_ceiling.txt`.

A big ceiling does not mean 2x is close. It means that a perfect timer would have done far better than 2x, and that the gap between perfect and real timing is where the answer lies (section 1c).

### 1b. The falls that can be avoided (HINDSIGHT labels)

A fall is a drop of at least the stated size from a closing peak to a closing trough, found by a zigzag on closes.

```
                      Window A (Aug 2023 - Nov 2026)              Window B (2013 - Jul 2023)
Fall size   Falls   Sum of fall sizes   Avg fall   Median      Falls   Sum of fall sizes   Avg fall   Median
                    (log points)                   sessions            (log points)                   sessions
10%+        20      4.80                -21%       12          76      16.50               -19%       10
15%+        11      3.68                -28%       22          35      11.26               -27%       20
20%+        8       3.13                -32%       30          20      8.44                -34%       27
25%+        7       2.90                -33%       26          16      7.43                -37%       36
```

The 15%+ falls come at a steady rate in both windows (3.4 per year in A, 3.3 in B) and are about equally deep. The eleven in window A:

```
Aug 01 2023 $117.60 -> Oct 26 2023 $93.67   -20.3%   61 sessions
Mar 07 2024 $211.38 -> May 01 2024 $144.27  -31.7%   38
Jul 10 2024 $183.96 -> Aug 07 2024 $128.67  -30.1%   20
Oct 08 2024 $172.80 -> Mar 10 2025 $96.63   -44.1%   103
Mar 25 2025 $114.81 -> Apr 08 2025 $78.21   -31.9%   10
Aug 13 2025 $184.42 -> Sep 05 2025 $151.14  -18.0%   16
Oct 29 2025 $264.33 -> Dec 17 2025 $198.11  -25.1%   34
Jan 23 2026 $259.68 -> Mar 03 2026 $190.95  -26.5%   26
Jun 03 2026 $542.52 -> Jun 10 2026 $452.40  -16.6%   5
Jun 30 2026 $580.91 -> Jul 29 2026 $429.56  -26.1%   20
Oct 06 2026 $649.42 -> Nov 05 2026 $404.40  -37.7%   22
```

What this means for 2x. The sum of the eleven falls is 3.68 log points, and 2x needs 0.693. So a rule needs to keep the equivalent of 19% of the total size of those falls, and give back nothing in missed rises, false alarms or costs. Perfect timing on every one of the eleven would have turned $100,000 into $12.3 million (25.5x of hold).

### 1c. How precise must the timing be?

Everything in this section is HINDSIGHT: the falls are known in advance, and the table shows what happens when the exit and re-entry are late, when only some falls are caught, and when there are false alarms (a 20-session stretch in cash while AMD is not in one of the falls). Result is the median over 300 random draws divided by held; 2.0 is the target. Window A, 15%+ falls (11 falls).

```
Both exit and re-entry late by N sessions, every fall caught, no false alarms
Sessions late     0      1      2      3      5      7      10     15     20
Result / held     25.5   11.3   8.8    6.0    3.7    2.8    1.46   1.54   0.70
(2.0 needed)

Share of falls caught (at 3, 5 and 10 sessions late both ends), no false alarms
Share caught        30%    40%    50%    60%    80%    100%
3 sessions late     1.62   1.97   2.52   3.08   4.48   6.02
5 sessions late     1.46   1.67   1.91   2.22   2.95   3.68
10 sessions late    1.09   1.17   1.20   1.27   1.39   1.46

One 20-session false alarm per fall correctly caught
Share caught        30%    40%    50%    60%    80%    100%
0 sessions late     1.44   1.73   2.12   2.52   3.80   5.59
3 sessions late     1.00   1.04   1.05   1.08   1.21   1.36
5 sessions late     0.90   0.82   0.82   0.80   0.76   0.81
```

Dodging only the biggest falls (HINDSIGHT, perfect labels):

```
Falls dodged (biggest first)      Late 0   Late 3   Late 5   Late 10     (result / held, window A)
Biggest 1 (-44%)                  1.80     1.68     1.52     1.35
Biggest 2 (+ Oct 2026 -38%)       2.56     1.86     1.62     1.33
Biggest 3                         3.69     1.91     1.88     1.15
Biggest 5                         7.53     3.16     2.58     1.15
All 11                            25.48    6.02     3.68     1.46
```

Translated into a requirement, for a rule judged on window A:

- With perfect timing, catching 2 of 11 falls would do it (2.56x of hold).
- With exits and re-entries each about 3 sessions late, it needs about 5 of 11 (45%) and no more than a few false alarms; with 5 sessions late, 6 of 11 (about 50% to 55%); with 10 sessions late it cannot be done even by catching all 11.
- A false alarm is expensive because AMD's rise while you are out is large: about 3.9% for a 20-session stretch at the 2023-2026 pace. One false alarm per correct dodge ends 2x at any lag of 3 sessions or more.
- Window B has 35 falls, so the same lateness is a little more forgiving: 3.1x of hold at 10 sessions late both ends if every fall is caught and there are no false alarms, 1.05x at 15 sessions late; at 5 sessions late with one false alarm per correct dodge it is 1.65x, again below 2x.

In short: about half or more of the roughly 3.4 big falls a year caught within about 5 sessions at both the top and the bottom, and fewer than about one false alarm for every two correct dodges, held steadily for years.

## 2. Where each tried method lost it

The 13 rules were re-created from the original code (`diag/rules.py`), run over the same windows, and the daily difference against hold was split into exact parts that add up to the total (log points; 1.0 is a factor of 2.7). They reproduce the earlier results: through the Nov 5 2026 close, the zone with QQQ, second low, day 13, plain zone and closest-to-table zone gave 8.20x, 7.08x, 5.64x, 5.79x and 3.81x, matching $819,499, $708,270, $563,484, $578,183 and $381,051 in REPORT.md, and the rebound, thrust, trend and breakout rules gave 2.70x, 6.39x, 5.14x and 1.77x, matching the surge study. The month-end and day-12 paper rules and the two earnings rules were not compared with earlier dollar figures.

```
Window A, Aug 2023 - Nov 11 2026. Held 4.84x. Log points against hold.
                                          Rule   Over hold  In AMD  Trades  Falls    Late    Early  Gaps   AMD return
                                          (x)    of time    avoided entry   exit   &costs  on cash days
Paper: day 13 + AMD above 200d            5.63   1.17       45%     8       +2.66    -1.87   -0.37  -0.25  -0.42
Paper: month-end after report             5.62   1.16       66%     11      +1.37    -0.46   -0.73  -0.00  -0.18
Paper: zone + QQQ below 100d             11.21   2.32       57%     10      +2.58    -0.81   -0.73  -0.18  -1.04
Paper: second low                         7.08   1.46       64%     9       +2.38    -0.84   -0.98  -0.15  -0.56
Paper: buy day 12, sell 7 before          5.64   1.17       69%     13      +1.58    -0.90   -0.56  +0.07  -0.12
Zone: plain (best money)                  7.91   1.64       77%     11      +1.77    -0.25   -0.73  -0.26  -0.78
Zone: closest to table                    4.45   0.92       48%     8       +2.56    -2.20   -0.34  -0.08  -0.03
Surge: rebound 8% off post-report low     3.15   0.65       30%     6       +2.81    -2.71   -0.50  +0.00  +0.41
Surge: breakout above 20-day high         1.77   0.37       23%     5       +2.83    -3.41   -0.50  +0.10  +1.08
Surge: +15% in 5 days                     7.03   1.45       51%     8       +2.41    -1.53   -0.68  +0.20  -0.20
Surge: in-AMD-by-default trend            5.14   1.06       50%     17      +2.11    -1.83   -0.24  +0.06  -0.03
Earnings: day 13, sell 15 before          3.80   0.79       55%     13      +2.25    -0.94   -1.30  -0.23  -0.02
Earnings: weekly, out 2 Fridays before    6.23   1.29       84%     14      +1.17    -0.45   -0.44  +0.00  -0.29
Average                                                                       +2.19    -1.40   -0.62
```

```
Window B, 2013 - Jul 2023. Held 44.8x. Log points against hold.
                                          Rule   Over hold  In AMD  Trades  Falls    Late    Early  AMD return
                                          (x)    of time    avoided entry   exit   on cash days
Paper: day 13 + AMD above 200d            10.78  0.24       40%     23      +7.53    -7.32   -1.63  +1.42
Paper: month-end after report             11.36  0.25       66%     40      +4.81    -2.69   -3.02  +0.90
Paper: zone + QQQ below 100d               3.59  0.08       35%     14      +7.07    -5.20   -4.32  +2.45
Paper: second low                         21.22  0.47       58%     29      +4.68    -1.44   -3.89  +0.65
Paper: buy day 12, sell 7 before           4.95  0.11       70%     42      +4.17    -2.33   -3.80  +1.97
Zone: plain (best money)                  28.96  0.65       66%     29      +3.54    -0.51   -3.78  +0.75
Zone: closest to table                     3.05  0.07       32%     16      +6.62    -5.89   -3.48  +2.75
Surge: rebound 8% off post-report low      5.34  0.12       30%     16      +7.38    -5.67   -3.75  +2.03
Surge: breakout above 20-day high          7.77  0.17       25%     18      +9.44   -10.28   -0.62  +1.46
Surge: +15% in 5 days                      2.47  0.06       59%     26      +3.40    -3.35   -2.80  +2.74
Surge: in-AMD-by-default trend             6.74  0.15       47%     55      +7.07    -6.90   -2.00  +1.83
Earnings: day 13, sell 15 before           8.17  0.18       55%     42      +5.73    -3.53   -3.96  +1.76
Earnings: weekly, out 2 Fridays before    38.56  0.86       84%     43      +3.22    -0.75   -2.40  -0.06
Average                                                                       +5.74    -4.30   -3.00
```

How to read the columns. "Falls avoided" is the gain from being in cash on days inside a 15%+ fall. "Late entry" is the loss from being in cash during the early part of a rise, before the rule's first day in AMD in that rise. "Early exit" is the loss from being in cash during a rise after the rule had already been in AMD in that same rise. "Gaps and costs" is the open-versus-close gap on trade days plus 5 bp per trade side (costs alone were -0.01 to -0.06 over the whole window, so they are not the problem). The last column is the sum of AMD's daily log returns on the rule's cash days: for 2x, in window A it needs to be about -0.69 plus costs. The labels of falls and rises use the whole window (HINDSIGHT), so this describes what happened and is not used by any rule.

What dominates:

- **Gains missed while in cash, mainly entering a rise late.** In window B the missed gains beat the falls avoided for every one of the 13 rules (average +5.74 against -7.30). In window A, 9 of 13 rules came out ahead of hold, but the average rule still gave back 2.0 of the 2.2 log points it earned from falls (late entry -1.40, early exit -0.62). The four that lost to hold, the closest-to-table zone, the rebound, the breakout and the day-13-sell-15 rules, all lost mainly through late entry (-2.20, -2.71, -3.41; and early exit -1.30 for the last).
- **False alarms eat most of what correct dodges earn.** Counting each stretch from a sell to the next buy (the wait at the start counts too): in window A the rules had 1 to 10 stretches where AMD fell during the stretch and 2 to 8 where it rose (breakout: 1 and 5). The log points avoided in good stretches (0.01 to 1.28) were more than the log points missed in false alarms (0.29 to 1.14) for 9 of 13 rules, and the four that lost to hold missed more than they avoided. In window B, with 3 to 22 good stretches and 8 to 39 false alarms, false alarms cost more than they saved in all 13 rules (`diag/out/d6_timing.csv`).
- **Concentration: AMD's return sits in a handful of days.** In window A the best 10 days contain 89% of the total log return and the best 20 days contain 144%: without its best 20 days, AMD would have ended at 0.50x, not 4.84x. The best 10 days are +23.8% (Apr 9 2025), +23.7% (Oct 6 2025), +18.6% (May 6 2026), +13.9%, +13.3% (Nov 9 2026), +13.0%, +11.4%, +11.4%, +11.0% (Nov 6 2026) and +10.7%. In window B the best 10 days hold 46% and the best 20 hold 77%. The rules were fully in AMD for 3 to 8 of the best 10 days in window A (median 5) and for 0 to 7 in window B (median 2), and 5 to 14 of the best 20 in A (median 11) and 1 to 14 in B (median 4). Only 5 of the 20 best days in either window came within 10 sessions after a 15% trough: most come in the middle of rises, which is why buying 10 sessions late still catches many of them, and why being in cash for long stretches loses so much.
- **Timing of exits was not the main problem; staying out was.** Against the 11 falls in window A, the rules were already in cash at the peak for 2 to 8 of them, exited before the trough in 2 to 6 (a median of 4 to 11.5 sessions after the peak) and rode 0 to 4 all the way down. But after exits, median re-entry came 0 to 21 sessions after the trough, and 0 to 5 of the 10 rises were never joined at all (`d6_timing.txt`).
- **Costs:** under 0.06 log points in every rule. Not a factor at this trade count.

## 3. Overfitting audit

### 3a. Winners on one part against the other part

`diag/d3_overfit.py` reads each search's result file and compares the two parts that search used. "Over held" divides each result by AMD held in that same part.

```
Search                      Settings  Held A / B   Best on A:   Best on A     Best on B:   Best on B     Rank corr   Beat held  Beat in both
                                                   result on A  scored on B   result on B  scored on A   A vs B      in A/B     (expected if unrelated)
Surge, 2013-23 (A) vs       3,900     45.2x/3.44x  32.7x        2.93x         6.65x        12.3x         +0.53       0 / 132    0 (0)
  Aug 2023-Nov 5 2026 (B)                                       (0.85 of                  (0.27 of
                                                                held)                     held)
Zone, to Apr 2025 (A) vs    17,280    0.83x/4.18x  1.55x        1.57x         5.64x        0.90x         -0.01       6,432 /    910 (825)
  May 2025 on (B)                                               (0.38 of                  (1.08 of                  2,216
                                                                held)                     held)
Buy signals, same split     1,142     0.83x/4.18x  2.21x        3.71x         6.74x        0.99x         +0.28       947 / 63   59 (52)
                                                                (0.89 of                  (1.20 of
                                                                held)                     held)
Earnings rules (204): first 8 quarters vs last 4: top pick 2.46x then 1.73x; rank correlation +0.71 (rules overlap heavily)
Buy day / sell days before (121): top pick 2.29x then 2.15x; rank correlation +0.08
```

Reading: the typical setting (median over all settings) is below hold in nearly every part (for example the surge rules' median is 0.03 of hold in the 2013-23 part and 0.33 in 2023-26). Of the six winners picked on one part and scored on the other, four fell short of hold on the unseen part (0.85, 0.27, 0.38 and 0.89 of held). The two that beat hold were picked on the strong last part and scored on the first part, where hold itself lost money (0.83x), which is an easy bar. The number of settings that beat hold in both parts is close to what chance gives if the two parts were unrelated (zone: 910 against 825 expected; buy signals: 59 against 52; surge rules: 0 against 0).

### 3b. Random schedules with the same trade count and the same stays

For each rule: 200,000 random in/out schedules, each with the same number of trades and the same lengths of stay in AMD (so the same time in market), placed at random in the same window. This gives the chance that luck alone makes a result this good.

```
Window A (held 4.84x)                       Trades  In AMD  Rule    Random median  Rule's place    Share of random    Equivalent number of
                                                    time    result  (matched)      among random    reaching 2x of     random tries whose best
                                                                                    schedules       held (9.67x)       would equal the rule
Paper: day 13 + AMD above 200d              8       45%     5.63x   2.11x          96th percentile 0.0%               19
Paper: month-end after report               11      66%     5.62x   3.00x          90th            0.0%                7
Paper: zone + QQQ below 100d                10      57%     11.21x  2.55x          99.88th         0.0%               570
Paper: second low                           9       64%     7.08x   2.90x          96th            0.0%               20
Paper: buy day 12, sell 7 before            13      69%     5.64x   3.14x          89th            0.0%                6
Zone: plain (best money)                    11      77%     7.91x   3.45x          98th            0.0%               36
Zone: closest to table                      8       48%     4.45x   2.25x          89th            0.0%                6
Surge: rebound                              6       30%     3.15x   1.64x          88th            0.0%                6
Surge: breakout                             5       23%     1.77x   1.44x          66th            0.0%                2
Surge: +15% in 5 days                       8       51%     7.03x   2.36x          98th            0.0%               36
Surge: trend                                17      50%     5.14x   2.16x          95th            0.0%               15
Earnings: day 13, sell 15 before            13      55%     3.80x   2.39x          81st            0.0%                4
Earnings: weekly, out 2 Fridays before      14      84%     6.23x   3.83x          92nd            0.0%                9
```

"Equivalent number of random tries" is how many random matched schedules you would need to draw before the best of them did as well as the rule, half the time (it is the natural size of the selection that produces such a result). The rules sit between the 66th and 98th percentile of random schedules, except the zone-with-QQQ rule (99.88th percentile), which is better than all but about 1 in 800 random schedules. That equals the best of about 570 random schedules, and that rule was the best of 1,142 buy settings (each run with seven market filters) on this same window. The best of 100 random matched schedules reaches 5 to 10x and the best of 1,000 reaches 7 to 14x in window A, so a result of 11x from a search is what selection alone produces. Reaching 2x of hold (9.67x) happens for 0.0% to about 1% of random schedules in window A and 0.0% to 2% in window B, depending on the rule.

Window B (hold 44.8x): rule results sit between the 7th and 92nd percentile (median 58th); the equivalent number of random tries is 0.7 to 8.9. In other words, in window B the rules were no better than random schedules with their own trade counts and times in market, and all were far below hold, because random schedules also lose the drift.

### 3c. Do the winners in one window win in the other?

The 13 rules' results divided by held, in each window:

```
Rule                                      Window A (2023-26)   Window B (2013-23)
Paper: zone + QQQ below 100d              2.32                 0.08
Zone: plain (best money)                  1.64                 0.65
Paper: second low                         1.46                 0.47
Surge: +15% in 5 days                     1.45                 0.06
Earnings: weekly, out 2 Fridays before    1.29                 0.86
Paper: buy day 12, sell 7 before          1.17                 0.11
Paper: day 13 + AMD above 200d            1.17                 0.24
Paper: month-end after report             1.16                 0.25
Surge: in-AMD-by-default trend            1.06                 0.15
Zone: closest to table                    0.92                 0.07
Earnings: day 13, sell 15 before          0.79                 0.18
Surge: rebound                            0.65                 0.12
Surge: breakout                           0.37                 0.17
Rank correlation between the two windows: +0.15
```

The rule at the top of window A is near the bottom in window B. The ranking in one window says almost nothing about the other (correlation 0.15). Window B was not used to pick the five paper rules, but earlier searches did use both parts (the surge search ran on both and picked rules by whether they were right 75% of the time in both).

### 3d. What the audit says about the hindsight results

- $819,499 and $578,183 (REPORT) are results of the best setting out of searches of 1,142 and 17,280 settings on one 3-year window. The rank correlation between parts of the same search is -0.01 for the 17,280 zone settings and +0.28 for the 1,142 buy settings.
- The five paper rules had no forward test before Nov 5 2026. Since then all five sat in cash while AMD rose 45% (Nov 5 to Nov 12), and the hold book is at $131,643 against $100,000 in each of the five.
- Even the most flattering reading (the best hindsight rule) is the best of a set of random-schedule size, and none of the 13 rules beat hold in 2013 to Jul 2023.

## 4. What predictive signal exists

Everything is split into 2013 to Jul 2023 (early) and Aug 2023 to Nov 11 2026 (recent). Outcomes are the forward return from the next open; signals use data up to the close. Stated effects are differences from the ordinary average, with Newey-West t-statistics that allow for overlapping windows. About 40 statistics were tested, so a lone t of 2 is not evidence. Detail is in `diag/out/d4_signals.txt` and the CSVs.

**Momentum and reversal: none.**

```
Daily return autocorrelation, lag 1:   early -0.031   recent -0.028
Lag 2, 3, 5:                           early +0.052, -0.044, -0.028   recent -0.014, +0.019, -0.047
Past h-day return vs next h-day return (non-overlapping blocks), early / recent:
  5 days  -0.04 / -0.09     10 days -0.06 / +0.09     21 days -0.09 / +0.03
  42 days -0.03 / +0.02     63 days +0.01 / -0.33     126 days -0.02 / 0.00
  none with |t| above 1.2
```

**Trend states (mean next-21-session return, state on minus off, percent; t in brackets), early / recent:**

```
Close above 50-day average       -1.02 (-0.58) / -1.32 (-0.35)
Close above 100-day average      +0.06 (+0.03) / +2.07 (+0.57)
Close above 200-day average      +1.33 (+0.58) / +3.97 (+0.92)
126-day return above zero        +1.40 (+0.67) / +3.68 (+0.88)
252-day return above zero        +1.03 (+0.44) / -1.68 (-0.33)
More than 30% below 1-year high  +0.25 (+0.10) / -2.72 (-0.61)
```

Nothing is significant, and the sign flips for several. The next-day effects of these trend states are all within +/-0.25%.

**After big days (events at least 21 sessions apart; excess over ordinary, percent, with number of events), early / recent:**

```
Day down 8%+, next day:   -0.53 (n 31) / -2.33 (n 8; t -2.16)
Day down 8%+, next 21d:   -0.56 / -5.33
Day down 5%+, next 5d:    +0.09 (n 67) / +2.77 (n 19)
5-day fall of 15%+, next 5d:  -0.83 (n 22) / +7.67 (n 7; t +2.10)
5-day fall of 15%+, next 21d: -4.42 (n 22; t -2.15) / +2.70 (n 6)
Day up 5%+, next 21d:     -0.65 / +3.96
```

The only same-sign pieces are a weakly negative next day after an 8% drop (-0.5% and -2.3%) and weakly negative 21-day return after 5-day 15% falls in the early window that flips sign in the recent one. Mostly the sign flips between the periods.

**Reports:**

```
                                             Early (40 reports)   Recent (12 reports)
Reaction day, mean / median                  +0.08% / -1.46%      -2.28% / -4.42%
Reaction day moved down                      57%                  58%
Reaction-day move, average size              9.5%                 8.1%        (ordinary day: 2.5% / 2.6%)
Next 21 sessions after reaction close        +5.44% (ordinary +2.89%)   +1.54% (ordinary +3.97%)
Correlation, reaction vs next 21 sessions    +0.12                +0.35
After a reaction of +5% or more, next 21d    +9.0% (n 13)         +11.5% (n 2)
After a reaction of -5% or worse, next 21d   +1.6% (n 13)         -3.5% (n 6)
Run-up, 10 sessions before the report        +0.03% (t -0.8)      +2.45% (t +0.15)
```

The size of the report-day move is stable and large; its direction is not (57% down, mean about zero). A mild continuation after a strong up reaction has the same sign in both periods, but rests on 15 events and is about +6% over 21 sessions, once or twice a year.

**Relative to QQQ and SMH:**

```
Beta of AMD to QQQ:             early 1.44   recent 2.07
Beta of AMD to SMH:             early 1.21   recent 1.23
Same-day correlation AMD-SMH:   0.60         0.78
Today's QQQ or SMH return vs AMD's next-day return: -0.03 to -0.06 in both periods (nothing)
QQQ above its 200-day average, next 63 sessions:  -4.2% (t -0.5) / -34.3% (t -3.7)
QQQ 10%+ below its 1-year high, next 63 sessions: +0.3% / +31.8%
AMD's 63-day return beats SMH's, next 21 sessions: -0.68% / +4.89%
```

The market-weakness link (AMD does better after QQQ was weak) has the same sign but in the recent window it is essentially one episode, April 2025, and in 2013-2023 it is zero.

**Volatility:**

```
Correlation of 21-day volatility now vs the next 21 days:   +0.18 early / +0.15 recent
Next-21-day volatility, after top-20%-of-year readings:      0.62 / 0.56 (after bottom-20% readings: 0.49 / 0.54)
Next 21 sessions return, top-20% volatility vs the rest:     -3.51% (t -1.33) / -2.40% (t -0.61)
Next 63 sessions:                                            -8.53% (t -1.41) / +0.50% (t +0.05)
```

Volatility is persistent in both periods. High volatility is followed by weaker returns in both periods, but not significantly, and the 63-day effect flips.

**After a stop-style trigger (first close X below the highest close of the last 126 sessions), causal:**

```
Trigger   Period   Events   Next 21d   (ordinary)   Next 63d   Fell a further 10%   Back at old high
                                                                 within 63 sessions   within 63 sessions
10% down  early    39       +2.2%      (+2.8%)      +12.6%     38%                  54%
10% down  recent   11       -6.7%      (+4.0%)      +7.5%      82%                  64%
15% down  early    27       +4.4%      (+2.8%)      +9.5%      48%                  41%
15% down  recent   8        +0.2%      (+4.0%)      +9.1%      50%                  50%
20% down  early    15       -1.6%      (+2.8%)      +4.8%      53%                   7%
20% down  recent   6        -2.0%      (+4.0%)      +17.0%     33%                  33%
```

A trailing-stop style exit sells into a point from which the next 63 sessions have a positive mean return in all six rows. There is no consistent extra weakness after the trigger.

**Plain in/out rules built from these signals, not tuned (the whole list, decided before looking):**

```
                                                Window A (2023-26)                         Window B (2013-23)
Rule                                            x of $100k  Over hold  Worst fall  Trades/yr   x      Over hold  Worst fall  Trades/yr
Held                                            4.84x       1.00       -63%        0           44.8x  1.00       -65%        0
In while above 50-day average                   2.93        0.61       -40%        9.5         12.3   0.27       -62%        8.3
In while above 100-day average                  2.93        0.61       -38%        5.5         7.9    0.18       -71%        6.5
In while above 200-day average                  3.80        0.78       -44%        2.8         16.9   0.38       -56%        3.8
In while 63-day return above 0                  2.44        0.51       -53%        7.9         6.9    0.15       -67%        6.6
In while 126-day return above 0                 3.79        0.78       -40%        3.1         14.2   0.32       -72%        4.3
In while 252-day return above 0                 3.67        0.76       -42%        0.9         16.7   0.37       -61%        3.0
In unless 21-day volatility in top 20%          3.34        0.69       -49%        5.8         54.7   1.22       -63%        3.6
In unless 63-day return below -15%              4.60        0.95       -46%        5.8         9.1    0.20       -74%        4.1
In while QQQ above its 200-day average          2.88        0.60       -57%        1.5         14.5   0.32       -66%        2.6
In while SMH above its 200-day average          3.94        0.81       -51%        2.1         35.9   0.80       -59%        2.8
In while above 200-day AND SMH above 200-day    3.51        0.73       -44%        2.4         29.1   0.65       -44%        4.3
In unless more than 30% below 1-year high       3.87        0.80       -43%        2.8         11.8   0.26       -57%        2.8
```

All twelve lose to hold in window A (0.51 to 0.95 of hold), and eleven of twelve lose in window B too (the one exception, the volatility filter, made 1.22x of hold in B and 0.69x in A). None approaches 2x. Some cut the worst fall from -63% to about -40%, at a cost of 5% to 49% of hold's return in window A.

**Net, which effects are stable and big enough?** The stable ones are about size, not direction: the rate and depth of 15% falls (3.3 to 3.4 a year, -27% to -28% on average), report-day move size (8 to 10%), beta (1.2 to 2.1), and volatility persistence (0.15 to 0.18). The weak same-sign direction effects (high volatility followed by lower returns; a continuation after strong up reactions; next-day weakness after an 8% drop) are each worth a few percent a year at most. The target needs about 21 log points a year on top of hold in window A (ln 2 over 3.27 years), against 5 bp per side costs that are not an issue. If the high-volatility effect were real (-3.5% and -2.4% per 21 sessions, on about 20% of days) it would be worth about 6 to 8 log points a year, against the 21 needed; it is not statistically distinguishable from zero, and the plain rule built on it lost to hold in window A (0.69x).

## 5. Verdict and directions

### Is 2x of held realistic?

No, not for a single-stock, long/cash loop on daily bars, with the evidence available.

- The arithmetic: to double hold's result in 2023-2026, cash days must hold a cumulative AMD fall of about 50% (price halving) while the rule is in AMD for the +383% rise. A rule has to catch about half of the eleven 15%+ falls with exits and re-entries within about 5 sessions, and keep false alarms to under one for every two correct dodges (Section 1c). With 10-session lateness it is impossible even if every fall is caught.
- What the tried rules did: in window A their exits were already near 5 sessions after the peak (median 4 to 11.5), and they were out for 2 to 6 of the 11 falls, but re-entry was late (median 0 to 21 sessions after the trough), 0 to 5 of 10 rises were never joined, and false alarms cost almost as much as correct dodges earned. Average over the 13 rules: +2.19 log points from falls, -2.02 from missed rises, and about -0.1 from trade-day gaps and costs, net +0.08 (1.09x of hold). Only 1 of 13 reached 2x, and it is the best of a thousand-plus settings. In 2013 to Jul 2023, 0 of 13 even matched hold, the best being 0.86x of hold; falls avoided (+5.7 on average) were less than gains missed (-7.3).
- Selection explains the best result: the best rule in 2023-2026 sits where the best of about 570 random schedules would; the others sit where the best of 2 to 36 would. Of random schedules with a rule's own trade count and stay lengths, 0.0% to about 1% reach 2x of hold in window A.
- No signal: autocorrelation is -0.03; momentum correlations are under 0.1 for most horizons (-0.33 at 63 days in the recent window, on 13 non-overlapping pairs); trend, volatility, report, market and sector states produce effects that either flip sign between the periods or are a few percent a year, and the twelve plain rules lose to hold in both windows except one in one window.
- The one fair out-of-sample evidence so far: the five paper rules were in cash during AMD's +45% week (Nov 5 to Nov 12); the hold book is at $131,643.

What would change this verdict: 2x of held needs either a timing signal with a catch rate of about half of the big falls within a few sessions and few false alarms, stable across both windows, or a different object than AMD alone. Nothing in 13 rules, more than 22,000 searched settings, or about 40 signal tests shows the first.

### Ranked directions

None of these is sufficient on current evidence. They are ranked by how much of the gap the measurements suggest each could close.

1. **Change what is picked, not when to trade: widen from AMD to a pool of stocks and pick the leader (cross-section), keeping the long/cash rules.** Timing one stock has an edge of 0 to 1.2 log points a window; the spread between stocks' holds is much larger. Buy-and-hold results 2023-08-01 to 2026-11-11 for a list of well-known names (survivors, picked by me, so HINDSIGHT): AMD 4.84x, MU 11.56x (2.4x AMD), AVGO 3.99x, TSM 4.36x, SMH 3.22x, GOOGL 2.27x, others 1.4x to 2.0x. For 2013 to Jul 2023: AMD 44.9x, TSLA 114.6x (2.6x AMD), AVGO 36.9x, NFLX 32.3x, MSFT 15.0x, META 11.6x, AAPL 11.6x, SMH 11.0x, MU 11.0x, QQQ 6.3x. NVDA did not download (the data source reported no data), so it is missing and could change the picture. Of the 15 other names with data, only 1 in each window beat 2x of AMD's hold. This direction has the largest pool but a large hurdle: the earlier ladder work found hindsight winners only (REPORT: 37 of 8,452 setups passed, all using names picked knowing they won). Not re-measured here.
2. **Treat the five paper books as the only clean test, and add frozen versions of the most plausible families, running at least a full year of reports (4 or more).** Evidence: every backtest number in REPORT is selected, and the cross-window rank correlation is +0.15. One forward quarter has shown the books missing the largest week. Do not read it as a direction that closes the gap; it is what makes the next result believable. Add benchmarks: the matched-random-schedule band from `d3_overfit.py`, so a good paper result can be judged against luck.
3. **Be in AMD by default and leave only for the few cheapest events (a "mostly in" rule).** Evidence: the weekly out-around-reports rule is the only one with a ratio near hold in both windows (1.29 and 0.86), because it is in AMD 84% of the time, and the in-unless-high-volatility rule made 1.22 in B and 0.69 in A. Mostly-in rules give up little drift. But their gains over hold in the recent window (about +0.15 to +0.25 log points) are about one third of the 0.69 needed, and the early window gives the opposite sign, so the expected result is about 0.8x to 1.3x of hold with somewhat lower variance, not 2x.
4. **Condition entries on market stress and on strong up reactions to reports, with small positions' worth of expected gain.** Evidence (weak): after a strong up reaction (5% or more), the next 21 sessions averaged +9.0% and +11.5% against +2.9% and +4.0% ordinary, in both periods but on only 15 events; AMD has done better after QQQ weakness (+31.8% over 63 sessions in the recent window, +0.3% early), in essentially one episode. Each is worth at most a few log points a year, an order of magnitude short of the 21 a year needed, and the t-statistics are below 2 in the early window.
5. **Lower the target to what the evidence supports: roughly matching hold with a shallower worst fall.** Evidence: trend and volatility rules cut the worst fall from -63% to about -40% to -50% (table in section 4) at a cost of 5% to 50% of hold's return in the recent window, and more in the early window (the 200-day rule: 0.78x of hold and -44% in A, 0.38x and -56% in B). If the aim is not to lose 60% in a fall, this has support; if the aim is 2x of hold, it does not.

Honest summary of the ranking: only direction 1 has a pool of potential gains of the right size, and nothing measured shows a way to find those gains in advance. Directions 3 to 5 each address a small fraction of the gap.

## Limits and things not verified

- All windows end at the Nov 11 2026 close, because the cached AMD file ends there; the Nov 12 close of $585.30 (paper status) is not in the data. With it, hold would be about 5.12x rather than 4.84x for window A. Rule results shift correspondingly; conclusions do not change.
- Hold is measured by buying at the first open of the window with 5 bp slippage and marking at the last close without a sell cost. The earlier reports measured hold from a close (3.44x through Nov 5, against 3.54x here through Nov 5), so numbers differ slightly from the REPORT's multiples of hold.
- Rule re-creation: the five paper rules, both zone rules and the four surge rules were rebuilt from the original code; through Nov 5 2026 the five zone and paper results match the REPORT's dollar values to the dollar for the cases checked (5 of 5), and surge results (trend 5.14x, breakout 1.77x, thrust and rebound apart from the extra November days) match. The two earnings rules (day 13 sell 15 before, weekly out 2 Fridays before) were run through the original `_amdcycle` code with my reading of the parameters; I did not compare them to the earlier $ numbers. For 2013 to Jul 2023 the rules were given only data up to the end of that window, with warmup from 2012.
- Report dates are used in advance, as in the earlier studies (AMD announces dates weeks ahead). Report dates before 2022 come from Yahoo and may contain errors.
- The leg labels for falls and rises (section 2 and 5) and the ceilings use the whole window. They describe, they do not predict. The random-schedule benchmark matches trade count and stay lengths but not timing quality, so a rule with real skill would also rank high there; here it shows what selection looks like, not that no skill exists.
- The "equivalent number of random tries" treats the searches' settings as independent, which they are not (many settings overlap), so it overstates the effective number of tries a search made. Even at the smaller range it shows selection can explain these results.
- Statistics in section 4 are on one stock over 13.8 years, 52 reports in total, and 12 in the recent window. Effects there cannot be pinned down more finely than shown.
- The dispersion table (direction 1) uses survivor names I chose and is hindsight; NVDA did not download.
- Not measured: partial position sizes, multi-stock rotation (cited from REPORT only), intraday timing, taxes, T+1 settlement in a cash account.
- Look-ahead check of my own code: signals in `d4_signals.py` use only data up to the close of day t, and forward returns start at the open of t+1; report statistics after the reaction day start from that day's close; the rules reuse the original code, which uses closes known at the decision, and report dates known in advance. The zigzag labels and DP ceilings, `d2` leg labels and `d6` falls and rises use the full window and are labelled hindsight.

## Files

All in `three-x/diag/`; outputs in `diag/out/`. Run with `/e/strategy-repos/venvs/vt/Scripts/python -W ignore <script>`.

```
common.py          shared fill/equity code (next open, 5 bp per side), windows, data loading (QQQ and SMH cached in diag/data)
rules.py           re-creates the 13 rules' positions for both windows from the original code; prints their results
d1_ceiling.py      ceilings by dynamic programming, falls, lateness and hit-rate tables        -> d1_*.csv, d1_ceiling.txt
d2_decompose.py    exact split of each rule's result against hold, best-days overlap            -> d2_*.csv, d2_decompose.txt
d3_overfit.py      winners on one part vs the other; matched random schedules                   -> d3_*.csv, d3_overfit.txt
d4_signals.py      autocorrelation, trend, vol, event, report and market statistics; plain rules -> d4_*.csv, d4_signals.txt
d5_best_days.py    where the best and worst days sit relative to 15% turning points             -> d5_best_days.csv
d6_timing.py       cash stretches, exits and entries against the 15% falls and rises            -> d6_timing.csv, d6_timing.txt
d7_extra.py        dodging only the k biggest falls; trailing-stop trigger base rates           -> d7_*.csv, d7_extra.txt
d8_dispersion.py   buy-and-hold results of well-known stocks over both windows (hindsight)      -> d8_dispersion.csv
```
