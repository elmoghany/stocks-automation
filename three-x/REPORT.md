# $100k to $300k in 12 months: results

Run 2026-11-04. Backtests only, no orders placed. Long-only, cash, halal list, one or two stocks.

## Verdict

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

- Sweeps: `sweep.py <singles|pairs|pairs_cash|topk|batch2|overnight>`
- Scoring: `analyze2.py`, `episodes.py`, `meta_wf.py`
- Stress and cross-checks: `validate.py`, `lb_check.py`, `ta_to_vibe.py`
- TradingAgents: `claude_bridge.py`, `ta_run.py`, `ta_audit.py`

Repos and virtual environments are in `E:\strategy-repos\`. Key result files are committed in `results/`; curves and logs are not.
