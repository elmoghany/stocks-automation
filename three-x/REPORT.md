# $100k to $300k in 12 months: results

Run 2026-11-04. Backtests only, no orders placed. Long-only, cash, one or two stocks. The original 3x campaign used the halal list. The 2x–3x update below dropped it for testing, at the user's request.

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
- Stress and cross-checks: `validate.py`, `lb_check.py`, `ta_to_vibe.py`
- TradingAgents: `claude_bridge.py`, `ta_run.py`, `ta_audit.py`

Repos and virtual environments are in `E:\strategy-repos\`. Key result files are committed in `results/`; curves and logs are not.
