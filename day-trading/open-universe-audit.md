# OPEN-UNIVERSE (2026-09-17)

**The direction.** "Work on the agents but IGNORE whether the stock is halal for now" — the halal gate is being repaired separately, so the edge search runs on the full liquid US universe and the halal filter is applied afterwards (Part 7). Everything else in the loop mandate is unchanged: net ≥ $7,500/month, $15k same-day tickets (≤ $100k/day, ≤ 7/day), long-only, and never future or end-of-day information at decision time.

**The question the mandate puts first.** "Does breadth change the ceiling?" — the zero-cost ceiling and the random baseline on 1,500+ names against the 64 and 283 measured before.

**The answer, in one line.** **Breadth does not change the ceiling; it lowers it. DEPTH raises it — and not by enough.** Going from 64 halal names a day to 2,532 open ones drops the zero-cost ceiling from **+$1,980 to +$1,015/month** and the flat-toll number from −$2,432 to −$3,396. Going the other way — to the *most liquid* 600 names — raises the zero-cost ceiling to **+$3,732/month**, and because the measured toll on those books is **4.30 bps/side against the incumbent 10 and against COST-REBASE's 12.05**, the net turns positive for the first time on this instrument: **+$981/month under the account's own $100k/day ladder**. That is the best honest number this line produced and it is **7.6× short of the bar**, with Y1 negative, 11 of 22 months positive, and 64% of the total in one day. **FAIL.**

**One leak caught, and it mattered.** The first cut sliced the universe on `market_cap` from `data/hgr_ticker_meta.json` — a *2026-09 snapshot*. On that slice the mid-cap bucket printed **+$4,942/month at zero cost and +$527 net**, the best numbers this project has seen. They are an artefact: a name is in the "> $2B" bucket partly *because* it rose during the study window, which is the same outcome-conditioned membership that retracted the MX series. Re-running with market cap computed causally (present-day share count × the **previous session's** close) collapses it to **+$896/month at zero cost and −$3,515 net**, and removes the size effect entirely — once membership is causal, **market cap adds nothing beyond liquidity**. The finding that survives is the liquidity one, because prior-60-session median dollar volume was causal from the start.

Files: `plan/ou_lib.py`, `plan/ou_universe.py`, `plan/ou_meta.py`, `plan/ou_backfill.py`, `plan/ou_cost.py`, `plan/ou_frame.py`, `plan/ou_table.py`, `plan/ou_rank.py`, `plan/ou_model.py`, `plan/ou_poison.py`, `plan/ou_halal.py`. Outputs in `plan/ou_out/`, caches in `data/massive/m1o/` and `data/massive/cost1o/`.

---

## 0. The universe, and what a "type gate" had to replace

The halal screen was the only filter in this repo that also, incidentally, excluded non-operating listings. Removing it exposes the fact that `plan/rl2/out/screen.json.gz` — the `liquid` universe every prior line used as its no-halal comparison — is **30% exchange-traded products**: on this study's 448 dates its per-day set of 4,575 names contains 411,667 ETF symbol-days, 18,732 ETV, 10,524 FUND, 5,529 ETS, 3,251 ETN, 2,076 PFD, 1,963 SP, 137 WARRANT and 92 UNIT. Buying SPY seven times is not a stock-picking strategy, and an ETF's open-to-close behaviour is a different object from a company's.

So the open universe adds a type gate in the halal screen's place. Per date **D**, with nothing about D's own session allowed in:

| rule | value |
|---|---|
| security type | Polygon `type` ∈ {CS, ADRC}; SIC 6726 (closed-end funds / investment offices) excluded. **Financials and every other sector are KEPT** — the mandate says operating companies of every sector, and the halal screen's blanket SIC-6xxx removal is not reproduced here. |
| liquidity | over the **prior 60 trading sessions** (≥ 40 present, all with date < D): median dollar volume ≥ **$5,000,000** and median close ≥ **$5.00** |
| minute subset | the top **600** per date by that same prior-60-session median dollar volume |

| | value |
|---|---:|
| dates | 448 (2024-10-22 … 2026-08-06) |
| names/day after liquidity only | 3,573 (3,097 … 4,011) |
| **names/day after the type gate** | **2,532** (2,275 … 2,747) |
| symbol-days | 1,134,288 |
| distinct symbols | 3,298 |
| minute subset | 268,800 symbol-days, **867 distinct symbols** |
| dropped for having no reference row at all | 12,580 symbol-days (~28/day) — excluded, not assumed |

The top of the liquidity distribution barely turns over, which is why 268,800 symbol-days of minute bars need only 867 symbols. `plan/ou_backfill.py` exploits that: it walks the **range** endpoint per symbol in 62-day chunks with `next_url` pagination instead of making one call per symbol-day, so the cache cost **≈ 7,000 API calls rather than 268,800**, finished in ~70 minutes, and came back with **0 failures** and 1.7 GB (`data/massive/m1o/{SYM}.npz`, the 04:00–20:00 ET 960-minute grid for every date the symbol printed on). A vectorised rewrite of the ET-grid mapping was checked byte-for-byte against the naive per-bar `zoneinfo` version on AAPL: 339,009 bars, every OHLC value identical.

---

## 1. The measurement had to be rebuilt before it could be used

The mandate says to use `cost_model="measured"` everywhere. COST-REBASE's `plan/cr_cost.py` measures the toll per (name, minute) from the **1-second tape**, which exists for 71,713 symbol-days of the *causal wide halal* universe and for essentially none of the open universe. Fed this universe it would fall through to its own "legacy" tier — a flat 10 bps — on nearly every fill, and would therefore answer the mandate's question by assumption.

Two models were built, both with cr_cost's functional form and cr_cost's own conservative coefficient (Y = 1.0, the top of the published square-root-law range).

**`MinuteCost`** — for the 600-name minute subset. It builds cr_cost's per-minute statistics out of the **1-minute** bars, with the `hl2` (per-second bid-ask-bounce) channel absent, so the spread reduces to max(Corwin-Schultz, Abdi-Ranaldo) on trailing 1-minute bars and the impact term is untouched. A vectorised implementation reproduces `cr_cost.CostModel._rolling` element-for-element:

| channel | worst relative difference vs `cr_cost` (120 symbol-days) |
|---|---:|
| `spread` | 3.6e-16 |
| `sig_win` | 7.1e-12 |
| `dv_win` | 5.2e-08 (cr_cost stores this one as float32) |

Two real bugs were caught by that selftest before any result was produced: the batched Abdi-Ranaldo estimator was reading Corwin-Schultz's *overnight-adjusted* second-leg highs and lows, and the σ window kept one return whose left leg lay outside the window.

**`DailyCost`** — for the other ~1,900 names a day, which have no minute bars. **The first cut of it was wrong and is reported because the error is instructive.** Corwin-Schultz and Abdi-Ranaldo were written for *daily* bars, so they were run on daily bars — and produced a **50 bps median half-spread**, a $0.20 spread on a $20 stock, roughly 15× the truth. At daily frequency the high-low range of a US equity is dominated by intraday drift and the overnight gap, and both estimators read that variance as spread. The *same* estimators on *1-minute* bars land at 1–6 bps, in line with UNIVERSE-QUOTES' 2–6 and COST-REBASE's 2.77 median. The estimator was right; the frequency was wrong.

The half-spread is therefore read off a **table measured on the two ground truths this repo has**, bucketed by the only liquidity variable available for every name on every date (12,853 symbol-day observations):

| prior-60d median $ volume | n | from the 1-second tape | from 1-minute bars | **used** (the more expensive) | p25 | p75 |
|---|---:|---:|---:|---:|---:|---:|
| < $10M | 1,635 | 6.21 | 4.92 | **6.21** | 2.74 | 12.74 |
| $10–20M | 869 | 4.00 | 3.38 | **4.00** | 2.10 | 6.46 |
| $20–50M | 1,395 | 4.12 | 3.47 | **4.12** | 2.18 | 6.63 |
| $50–100M | 1,388 | 4.22 | 2.00 | **4.22** | 1.81 | 5.41 |
| $100–200M | 2,670 | 3.13 | 1.38 | **3.13** | 0.95 | 2.72 |
| $200–500M | 2,918 | 2.83 | 1.43 | **2.83** | 1.00 | 2.58 |
| $500M–1B | 1,181 | 2.17 | 1.40 | **2.17** | 1.08 | 2.44 |
| $1–5B | 698 | 3.92 | 1.52 | **3.92** | 1.18 | 3.39 |
| $5–20B | 82 | — | 1.29 | **1.29** | 1.08 | 2.55 |
| > $20B | 17 | — | 2.04 | **2.04** | 1.77 | 2.89 |

Stated rather than buried: this maps *liquidity* to spread, so two names with the same dollar volume get the same half-spread. It is a bucket median, not an identity, and where both sources speak the **more expensive** one is taken. The impact term is per name and per date and uses cr_cost's own formula; the square-root law is horizon-invariant (σ_T ∝ √T and V_T ∝ T, so σ_T·√(Q/V_T) is the same number at T = 10 minutes and T = 1 day), which is what makes a daily estimate of an intraday impact legitimate.

### What the toll actually is, by slice

| universe | half-spread | impact | **total bps/side** | fraction of fills > 10 bps | round trip on $15k |
|---|---:|---:|---:|---:|---:|
| **incumbent assumption** (every row in the index) | — | — | **10.00** | — | **$30.00** |
| COST-REBASE, causal wide halal universe | 2.77 | 9.21 | **12.05** | 63% | $36.15 |
| open universe, all 2,532 names/day | 4.12 | 4.03 | **8.05** | 36% | $24.15 |
| open universe, **mcap $2–10B** | 4.12 | 4.52 | **8.58** | 34% | $25.74 |
| open universe, **mcap > $10B** | 3.13 | 1.62 | **4.77** | 4.3% | **$14.31** |
| open universe, **top 600 by dollar volume** | 2.83 | 1.29 | **4.30** | **0.6%** | **$12.90** |

The impact term is the whole story: it is **9.21 bps on the halal wide universe and 1.29 bps on the top 600**, because a $15,000 ticket is 2.6% of the trailing 10-minute dollar volume in the first and a rounding error in the second. COST-REBASE's conclusion — that the flat 10 bps is *optimistic*, not conservative — is correct **on the universe it measured** and inverts on this one.

---

## 2. TEST 1 — frame ablation on the open universe

The instrument is HARNESS-DIAGNOSTIC's (`plan/hd_frame.py`), reused so the two studies are comparable line for line: the grouped-daily tape (whose `o` matches the 09:30 minute-bar open to 0.0000% median), buy at O[t], flatten at C[t], twenty deliberately tiny policies — rank the day's eligible names on **one** feature built only from sessions strictly before t, both signs, ten features — take the top 7 at $15,000. `gap` is excluded by construction: a policy that buys at the open cannot have observed the open. The best-of-twenty is an **in-sample maximum** and is labelled as one; the 30-seed random control under the identical setting is printed beside it.

### Identity gate

Before anything new, the reimplementation was pointed at HARNESS-DIAGNOSTIC's own three universes:

| universe | this line | `harness-diagnostic.md` |
|---|---:|---:|
| halal_strict, flat 10 bps | **−$2,432/mo** | −$2,432/mo |
| halal_strict, zero cost | **+$1,980/mo** | +$1,980/mo |
| halal_wide, flat 10 bps | **−$2,616/mo** | −$2,616/mo |
| liquid (rl2 screen), flat 10 bps | **−$3,141/mo** | −$3,141/mo |

To the dollar, including the winning policy's identity. The instrument has not drifted.

### 2.1 The breadth question — the answer is "no", and the gradient runs the other way

All rows: 448 dates, top 7 at $15,000 (HARNESS-DIAGNOSTIC's ladder, $105k/day — the account-legal $100k ladder is §2.3), best of the same 20 policies, 30-seed random control under the identical setting. `edge/tkt` is the best policy minus the random mean, and is the one column that is not an in-sample maximum of a *level*.

| universe | names/day | flat 10 bps | **zero cost** | **measured** | edge/tkt vs random | pct |
|---|---:|---:|---:|---:|---:|---:|
| halal_strict (the index's universe) | 61 | −$2,432 | **+$1,980** | −$3,320 | +$16.84 | 100 |
| halal_wide | 278 | −$2,616 | +$1,796 | +$399 | +$11.94 | 100 |
| rl2 `liquid` ($2M/$3, **30% ETFs**) | 4,575 | −$3,141 | +$1,270 | +$403 | +$7.27 | 80.0 |
| **open universe (all of it)** | **2,532** | **−$3,396** | **+$1,015** | +$186 | +$4.14 | 76.7 |
| open, top 100 by $ volume | 100 | −$1,612 | +$2,801 | +$812 | +$17.64 | 100 |
| open, top 300 | 300 | −$1,169 | +$3,244 | +$1,026 | +$20.31 | 100 |
| **open, top 600** | **600** | **−$682** | **+$3,732** | **+$1,215** | **+$25.14** | 100 |
| open, top 1200 | 1,200 | −$1,961 | +$2,452 | +$186 | +$15.35 | 100 |
| open, rank 601+ | 1,932 | −$3,586 | +$825 | −$2,002 | +$2.02 | 63.3 |
| open, rank 1201+ | 1,332 | −$4,164 | +$246 | −$2,269 | **−$1.52** | 43.3 |

Read down the last two columns. **The edge a simple pre-open ordering can extract is monotone in book depth and dies at the tail**: +$25/ticket over random on the 600 deepest books, +$2 on everything below them, and −$1.52 — i.e. nothing, 43rd percentile, the best of twenty policies indistinguishable from a coin — on the 1,332 thinnest names in a universe that is already screened at $5M a day. Adding those names is what taking the universe from 600 to 2,532 does, and it is why breadth *lowers* the ceiling: **+$3,732 → +$1,015/month at zero cost.**

The comparison against `rl2_liquid` is the other half of it. That universe is the one every prior line used as its "no halal screen" reference, and 30% of its symbol-days are exchange-traded products; it is both broader and thinner, and it is the worst cell in the table on every column.

### 2.2 The size question (mandate Test 4) — it was survivorship

| slice | membership | flat 10 bps | zero cost | measured |
|---|---|---:|---:|---:|
| mcap > $10B | **present-day** snapshot | +$198 | +$4,612 | — |
| mcap $2–10B | **present-day** snapshot | **+$527** | **+$4,942** | — |
| mcap < $2B | **present-day** snapshot | −$4,626 | −$216 | — |
| mcap > $10B | **causal** (shares × prev close) | −$2,922 | +$1,489 | +$186 |
| mcap $2–10B | **causal** | −$3,515 | +$896 | −$1,626 |
| mcap < $2B | **causal** | −$2,297 | +$2,116 | −$2,987 |

The top three rows are what a present-day market-cap field buys you: a bucket whose membership knows which names rose. The bottom three are the same slices with the price leg taken from the *previous* session. The size ordering reverses, the effect disappears, and the sector-neutral variant (one ticket per 2-digit SIC) is worse than unconstrained on every cost column (−$3,979 flat, +$431 zero, edge/ticket **+$0.30**, 50th percentile) — ranking within SIC groups destroys what little ordering skill there is.

### 2.3 The account's own ladder, and the ablation

Every hd_frame row in `EXPERIMENTS-INDEX.md`, and every row above, buys 7 × $15,000 = **$105,000** a day. The cash account's rule is $100,000 (`memory: cash-account-ticket-rules`), i.e. 6 × $15,000 + 1 × $10,000. Charging the real ladder:

| universe | flat 10 bps | **measured** | zero cost | Y1 | Y2 | months + | ex-best-day | maxDD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **open, top 600** (`ovn_prev+L`) | −$823 | **+$981** | +$3,380 | −$1,728 | +$1,876 | 11/22 | +$7,165 | −$57,146 |
| open, top 300 (`r1+L`) | −$1,019 | **+$1,063** | +$3,184 | −$4,682 | +$4,321 | 9/22 | +$11,659 | −$48,997 |
| open, mcap > $10B causal | −$2,847 | +$257 | +$1,354 | +$895 | −$890 | 8/22 | −$10,255 | −$25,694 |
| halal_strict | −$2,503 | −$2,975 | +$1,698 | −$2,985 | +$4,523 | 13/22 | +$20,807 | −$37,949 |

**The best account-legal row in this whole test is +$1,063/month.** It is 7.1× short of the bar, Y1 is −$4,682, 9 of 22 months are positive, and it is the best of twenty policies searched in sample. In the top-600 cell the runner-up is +$257 and the other eighteen policies are negative down to −$5,993, so +$981 is a draw from a distribution centred near −$1,500.

The one-constraint-at-a-time table, anchored on the open universe:

| constraint | ON $/month (random) | OFF $/month (random) | Δ best | Δ random |
|---|---:|---:|---:|---:|
| same-day only | −$3,396 (−$4,004) | −$1,154 (−$3,238) | +$2,242 | +$766 |
| long-only | −$3,396 (−$4,004) | **+$14,964** (−$4,004) | **+$18,360** | **$0** |
| costs charged | −$3,396 (−$4,004) | +$1,015 (+$407) | +$4,411 | +$4,411 |
| market orders → 2.77 bps | −$3,396 (−$4,004) | −$206 (−$815) | +$3,190 | +$3,189 |
| **flat 10 bps → MEASURED** | −$3,396 (−$4,004) | **+$186** (−$4,081) | **+$3,582** | −$77 |

Two rows differ from HARNESS-DIAGNOSTIC's and both are about this universe, not about the frame.

**The measured-toll row is new and is the real result of this line.** Replacing the flat ladder with a per-name measured toll is worth **+$3,582/month to the best policy while moving the random control by −$77**. On the halal wide universe COST-REBASE found the opposite sign, because there the flat 10 bps *under*-charges (measured 12.05). Here it over-charges by more than 2× on the deep books — and, unlike every other row in the table, the gain is **not** shared with the random picker. That is because the winning ordering is `ldv+L`: buy the seven highest-dollar-volume names. The policy is selecting on the cost model. COST-REBASE's warning ("every ranker that looked skilled under a flat toll was partly selecting names whose execution the flat toll under-charged") applies here with the sign reversed, and it is why the honest number for this line is the **measured** column and not the flat one.

**Long-only OFF is +$18,360/month above the base**, on a best-of-forty whose random control does not move at all — on halal_strict HARNESS-DIAGNOSTIC measured the same ablation at +$880. The winner is `rng_prev+S`: short the names with the largest previous-day high-low range, Y1 +$23,438, Y2 +$9,977, aug-2026 −$5,338, and one day is $284,790 of the total. It is **outside the mandate** (long-only is a hard constraint), it is an in-sample maximum over forty policies, and it is recorded here only because it is the largest single ablation number this project has produced and somebody will eventually ask.

*(Sections 3–8 land as each run completes.)*
