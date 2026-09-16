# RL-SERIES (2026-09-16) — online RL for portfolio management and stock trading, tested against the halal universe

**Status: COMPLETE. 56 training runs, 4 adversarial controls, 62 baseline
rollouts. VERDICT: nothing beats the baselines after costs, across seeds.**

> Test window 2025-08-01 -> 2026-07-31 (251 days), $/ticket:
> HOLD **0** | DQN −32.8 | CHURN (no information) −37.1 | PPO −37.8 |
> EIIE-Mask −41.5 | MaskablePPO −47.9 | EIIE-PPO −70.2 | RANDOM x30 −101.6 |
> BUYFIRST −289.6. With 30 minutes of foresight the same code makes
> **+526/ticket**, so the harness can see an edge; there is not one here.

Sources: `plan/rl/out/results/*.json`, `plan/rl/out/baselines.json`,
`plan/rl/out/shuffle_control.json`, `plan/rl/out/pool_profile.json`,
`plan/rl/out/report.md`.

Read the verdict before the survey. This project has retracted five
"winners" in a month, the most recent (`NOTES-DAYTRADING.md`, "MX-SERIES
RETRACTION #2") for a leak in the *universe* rather than in the strategy —
so the prior on any positive RL number here is that it is an artifact until
an adversarial check has failed to kill it.

---

## Part 1 — Survey

### Scope constraint that eliminates most of the literature before licensing or leakage

Our position structure is **discrete, capped and same-day-flat**: flat
$15,000 tickets (the 7th and last $10,000), at most 7 per day, at most
$100k deployed, long-only, halal-PASS only, forced flat by 20:00 ET.
Essentially every framework below assumes either (a) continuous portfolio
weights, fully invested, rebalanced daily, or (b) a single asset with an
all-in binary position. Neither is our problem, and the gap is the whole
environment, not a hyperparameter.

### 1. FinRL / FinRL-Meta (AI4Finance)

*What.* Gym-wrapped daily stock-trading MDP plus a thin wrapper over
SB3/ElegantRL/RLlib. Canonical env `finrl/meta/env_stock_trading/env_stocktrading.py`:
state = `[cash, prices(D), holdings(D), tech_indicators(D×K), turbulence]`,
continuous action in `[-1,1]^D` scaled by `hmax` shares, reward = Δ(total assets).
FinRL-Meta adds data processors and a train/validate/trade pipeline.
<https://github.com/AI4Finance-Foundation/FinRL>, <https://arxiv.org/abs/2011.09607>,
<https://arxiv.org/abs/2211.03107>.

*License.* MIT (name/logo trademarked separately).

*Data.* Daily in every published benchmark. Minute bars are plumbed through
the Alpaca processor but no published FinRL result uses them; Sharpe
reporting is hard-coded `252**0.5`.

*Fit.* Poor without a rewrite. No 7-position cap, no fixed-notional
tickets (actions are share counts), no forced EOD flatten, no
session-dependent cost tier; costs are one scalar per side with no
slippage, no impact and unlimited fill size at the bar price.

*Critiques (source-checked).*
- **No "next-day price at action time" bug in current master.** `step()`
  computes `begin_total_asset` at day *t*, fills at *t*'s prices, then
  advances and marks — the ordering is correct.
- What *is* there is **zero-latency execution**: observe the close, fill at
  that same close, in unlimited size. <https://arxiv.org/abs/2605.23959>
  ("When Alpha Disappears") measures same-day-open/post-open execution as one
  of the two largest and most stable sources of metric inflation.
- **`ffill().bfill()` remains in the default preprocessor**, filling leading
  NaNs from the future. Issue #189 reordered it but did not remove it:
  <https://github.com/AI4Finance-LLC/FinRL-Library/issues/189>.
- Turbulence is a *rolling* 252-day covariance and the ensemble threshold is
  a training-period quantile — both clean; specifically checked.
- **Reproducibility failure reported by a user**: with every seed pinned
  (python/numpy/torch/SB3/gym/DummyVecEnv), backtest Sharpe ranged 0.1–2.7
  across re-runs of the identical experiment.
  <https://github.com/AI4Finance-LLC/FinRL-Library/issues/190>.
- **AI4Finance now says it themselves.** FinRL-X (<https://arxiv.org/html/2603.21330v1>):
  "Offline backtesting environments rely on simplified execution assumptions…
  instant fills at bar prices, unrealistic transaction cost modeling, absence
  of market impact simulation… survivorship bias" producing "inflated
  performance metrics and unstable behavior once connected to a trading API."
- Survivorship: the Dow-30 tutorial uses today's constituents over a decade.

*Feasibility on 109k symbol-days of 1-min bars.* Bad as-is — a pandas `.loc`
per step, O(10²–10³) steps/s. AI4Finance's own contest work reports a 1,746×
speedup from 2,048 GPU-resident parallel envs (<https://arxiv.org/abs/2501.10709>),
which is the measure of how far off the default env is.

### 2. Qlib RL / OPD (Microsoft)

*What.* **Order execution**, not alpha: given a decided parent order, learn
the child-order schedule. Ships PPO (Lin & Beling IJCAI 2020), OPDS =
Oracle Policy Distillation (<https://arxiv.org/abs/2103.10860>) and TWAP.
<https://github.com/microsoft/qlib/tree/main/examples/rl_order_execution>.

*License.* MIT. The most actively maintained item in this survey.

*Data.* Intraday native; the shipped example is 5-minute China A-share data
in OPD pickle format. Bar width is a config change; the data is ours to supply.

*Fit.* Fits **half** our problem cleanly. It will not choose the 7 names. It
will learn how to work a $15k ticket into the tape, which is dense-reward and
genuinely learnable — and with 10 bps/side plus a 50 bps extended-hours
penalty, execution quality is plausibly a larger and far more reliable edge
than selection. Same-day-flat and the extended tier are reward/termination
edits, not architecture edits.

*Critiques.* Microsoft's own docs: "A significant gap exists between training
and backtest results due to different simulators" — the training simulator
permits unlimited execution. OPD is *structurally* an oracle-with-future-
information method; the distillation is designed so the student never sees the
future, but a careless reimplementation leaks it directly. Published results
are China A-shares (T+1, price limits) — do not assume transfer.

### 3. TradeMaster (TradeMaster-NTU)

*What.* Six task families (incl. intraday/HFT/order execution), 13+ RL
algorithms, and — the valuable part — **PRUDEX-Compass**
(<https://arxiv.org/pdf/2302.00586>): 6 axes including an explicit
**rEliability** axis that forces seed variance into the reported output.
NeurIPS 2023 D&B.

*License.* Apache-2.0. **Last push 2025-06-04** — ~15 months stale; a 2025
codebase pinned to 2023-era gym/torch. Reference code, not a dependency.

*Fit.* The HFT/intraday families are the closest published structural match
to same-day-flat trading, but the agents are single-asset or continuous-weight.
**Take the evaluation harness, leave the agents.**

### 4. SB3 + gymnasium trading envs

**stable-baselines3** (MIT, actively maintained) — A2C, PPO, DQN, DDPG, TD3,
SAC. For a discrete capped action structure the relevant pieces are PPO and
**sb3-contrib `MaskablePPO`** for invalid-action masking. The only
production-grade component in the survey.

**gym-anytrading** (MIT, last push 2024-03-14) — `Discrete(2)`, all-in
Long/Short toggle, single asset. The observation window includes the current
bar and the trade fills at `prices[current_tick]`, i.e. observe-the-close-
and-fill-at-it. **Decisively: `_calculate_reward` returns raw
`current_price - last_trade_price` with no fee term** — fees live only in
`_update_profit` and never reach the learner. The agent is trained in a
zero-cost world and scored in a 1.5%-round-trip world. Reward also only
credits the Long leg.

**Gym-Trading-Env** (MIT) — better designed (discrete *position* list,
explicit `trading_fees`, borrow interest, multi-dataset sampling) but still
single-asset-at-a-time; cannot express "7 of these 40 candidates, $15k each".

### 5. EIIE / PGPortfolio (Jiang, Xu & Liang 2017)

<https://arxiv.org/abs/1706.10059>, <https://github.com/ZhengyaoJiang/PGPortfolio>.
Ensemble of Identical Independent Evaluators: a shared-weight per-asset
scorer, Portfolio-Vector Memory so the commission term is differentiable,
Online Stochastic Batch Learning, log-return reward net of commission.

*License.* **GPL-3.0** — copyleft. TensorFlow 1.x, last push 2021.

*Fit.* The **weight-sharing idea is the most transferable thing in this
survey**: one shared per-symbol scorer applied across a variable-size
candidate set, then a selection layer — exactly "score N candidates, take 7".
PGPortfolio itself is fully-invested continuous crypto weights with no
position cap and no flatten, and its universe is "top 11 by volume at
backtest time", which is selection conditioned on the future.

*Replication failure (primary source).*
<https://github.com/wassname/rl-portfolio-management> — a public attempt to
reproduce 1706.10059 reports that it **overfit training and did not
generalize** (~8% train growth that disappeared out of sample).

### 6. DeepTrader (AAAI 2021)

<https://ojs.aaai.org/index.php/AAAI/article/view/16144>,
<https://github.com/CMACH508/DeepTrader>. Asset Scoring Unit (spatio-temporal
GCN over an estimated inter-asset graph) + Market Scoring Unit that sets the
**long/short fund ratio** from macro state.

*License.* **No LICENSE file — all rights reserved.** Hard legal blocker.
Default window 13 *weeks*; DJIA daily. Force long-only and the entire
contribution (the long/short ratio) collapses to a constant. The estimated
relation graph is also a classic graph-structure leak surface if the
estimation touches test-period data. **Not usable.**

### 7. Generic PPO/SAC/DDPG/TD3 + the FinRL ensemble strategy (Yang et al. 2020)

Train A2C/PPO/DDPG on rolling windows, trade whichever had the best 63-day
validation Sharpe. <https://openfin.engineering.columbia.edu/sites/default/files/content/publications/ensemble.pdf>.
MIT via FinRL, daily, Dow 30, 2009–2020.

*The mechanism is itself a hazard*: "best of 3 on a 63-day validation
Sharpe" over ~40 rebalances is ~120 implicit selections.

*This is the most-replicated result in the field and it does not survive.*
"Unstable Gains: Multiplicity-Aware Evaluation of Financial Deep
Reinforcement Learning", *The Journal of Finance and Data Science*,
doi:10.1016/j.jfds.2026.100205 — reproduces the Dow-30 ensemble setup at
fixed hyperparameters across many seeds and reports that Sharpe varies
substantially by seed, apparent outperformance frequently disappears under
multi-run evaluation, and algorithm rankings lose significance after
sign-flipping permutation tests with Holm–Bonferroni correction.
**Caveat, flagged: ScienceDirect returned 403; title/journal/DOI/findings
come from consistent search-engine abstract snippets, the author list is
unverified. Verify before relying on it.** Note also the asymmetry: the
framework's own follow-ups (<https://arxiv.org/abs/2501.10709>) report only
positive deltas and no variance analysis.

### 8. Notable 2024–2026 work

**The single most useful paper for this setup.** "Realistic Market Impact
Modeling for Reinforcement Learning Trading Environments", Abbade & Reali
Costa, <https://arxiv.org/abs/2603.29086> (Mar 2026). Almgren–Chriss +
square-root impact, five SB3 algorithms, NASDAQ-100 daily 2010–2026.
Verbatim: *"All agents underperform the QQEW benchmark OOS, although A2C and
PPO outperform IS, suggesting overfitting."* Replacing a flat 10 bps cost
with a realistic impact model moved daily costs from $200k to $8k, turnover
from 19% to 1%, and flipped DDPG's OOS Sharpe from −2.1 to 0.3 — i.e. **the
cost model changes the ranking of the algorithms, not just the level.**

**Leakage benchmarks.** "When Alpha Disappears" (<https://arxiv.org/abs/2605.23959>)
toggles one evaluation convention at a time against a clean *t+1-open*
reference: centered temporal features and same-day-open execution using
post-open bar information dominate the inflation; global normalization and
future-informed graph structure are weaker. "Profit Mirage"
(<https://arxiv.org/abs/2510.07920>) shows LLM-agent backtest returns
evaporate past the model's knowledge cutoff. "Look-Ahead-Freedom as Temporal
Non-Interference" (<https://arxiv.org/abs/2607.04958>) formalizes
look-ahead-freedom as temporal non-interference — useful as design
discipline; per its abstract it does **not** audit FinRL or any named
framework.

**Intraday-specific precedents.** **DeepScalper** (CIKM 2022,
<https://arxiv.org/abs/2201.09058>) is the best-matched published
architecture for a same-day-flat agent: minute-level, dueling Q-network with
**action branching** (decouples direction from size), a hindsight bonus, and
volatility prediction as an auxiliary task. **MacroHFT** (KDD 2024,
<https://arxiv.org/abs/2406.14537>) and **EarnHFT**
(<https://arxiv.org/pdf/2309.12891>) are minute/second-level but **crypto
only** — 24/7 continuity removes the open/close structure that dominates our
problem. **Gym4ReaL** (<https://arxiv.org/abs/2507.00257>) reportedly
contains a TradingEnv that opens at the market open and force-closes at the
close on 390-minute episodes — structurally our setup — but this could not be
confirmed from the arXiv abstract page and is listed as unverified.

**Surveys.** Pricope (<https://arxiv.org/abs/2106.00123>): *"the majority of
the works, despite all showing statistically significant improvements in
performance compared to established baseline strategies, no decent
profitability level was obtained"*, with experiments "conducted in unrealistic
settings". Hoque et al. (<https://arxiv.org/abs/2512.10913>, 167 articles):
*"implementation quality and domain knowledge often outweigh algorithmic
complexity."* Hambly, Xu & Yang, *Mathematical Finance* 33(3):437–503, 2023,
doi:10.1111/mafi.12382 — the standard theory-side survey.

**Offline RL / LLM+RL.** FinRL-DeepSeek (<https://arxiv.org/abs/2502.07393>)
inherits every FinRL env issue *plus* the knowledge-cutoff leak. GIFT
(<https://arxiv.org/abs/2606.08450>) uses the LLM to design the state/reward
interface and then **freezes it** — the safest LLM+RL pattern found, though
it does not discuss cutoff leakage in factor generation.

### Hugging Face Hub: nothing usable

Searched `hf://models`, `hf://datasets`, `hf://spaces` for trading / FinRL /
portfolio / stock RL and filtered by the `reinforcement-learning` task tag.

- The largest trading-RL model is `Adilbai/stock-trading-rl-agent` (MIT, 183
  likes, ~197 downloads): SB3 PPO on **daily** yfinance data for 5 FAANG
  names, 500k steps, **one seed**. Its own card reports **"Max Drawdown:
  164.60%"** and a **7,243% total return on MSFT at Sharpe 0.56**, with a
  GOOGL row of all zeros. A >100% drawdown is impossible for an unlevered
  long book and 7,243% at Sharpe 0.56 is internally inconsistent. Two other
  accounts carry byte-identical forks of the card. This is the Hub's flagship
  trading-RL model.
- The FinRL-tagged repos are almost entirely LoRA adapters on
  DeepSeek-R1/Qwen/Llama from the FinRL-DeepSeek contest — language models,
  not policies.
- No minute-bar intraday US-equity OHLCV dataset on the Hub; the most
  downloaded trading-RL dataset is ~1–10k rows of daily AAPL/MSFT/GOOGL.

**Conclusion: no pre-trained trading policy and no trading-RL dataset on the
Hub is worth downloading for this.**

### Picks

1. **Write our own vectorized gymnasium env encoding the exact ticket rules
   and drive it with SB3 PPO / `MaskablePPO`**, borrowing DeepScalper's
   action factorization and EIIE's shared per-symbol scorer idea. Every
   off-the-shelf env violates at least one *hard* constraint (7-ticket cap,
   fixed $15k notional, EOD flatten, session-dependent cost tier), and
   adapting one costs more than writing code we fully understand — decisively,
   it means the leakage audit is over code we wrote. **This is what Part 2
   does.**
2. **Qlib RL for the execution layer only**, keeping rule-based selection.
   At 10 bps/side + 50 bps extended, fill quality is plausibly a larger and
   far more reliable edge than selection, and it is the only actively
   maintained, intraday-native, permissively licensed option. **Not attempted
   here** — flagged as the highest-value follow-up.
3. **TradeMaster's PRUDEX-Compass as a scoring layer**, for its explicit
   reliability axis. Adopted in spirit (seed spreads are reported for every
   row below), not as a dependency.

**Explicitly not picked:** FinRL/FinRL-Meta as a runtime (daily-shaped, slow,
flat costs, superseded by its own authors' critique); DeepTrader (no license,
long/short by construction, weekly horizon); PGPortfolio (GPL-3, TF1, public
replication failure); gym-anytrading (fee-free reward); anything on Hugging Face.

### Feasibility note that matters more than the compute

- Data volume is a non-issue: ~109k symbol-days × ~960 extended-session
  bars ≈ 10⁸ bars; our halal-gated, eligibility-gated slice is far smaller
  (see Part 2) and fits in RAM.
- **Effective sample size is O(10²), not 10⁵.** One episode = one trading
  day. We have 151 train / 42 val / 251 test / 22 extra days. Deep RL wants
  10⁶–10⁸ env steps, so the same few hundred days are replayed thousands of
  times. **Memorization is the default outcome, not a failure mode.**
- **Cost-to-signal is the binding economic constraint.** A round trip costs
  20 bps regular and up to 120 bps if both legs are extended-hours. Typical
  1-minute moves on these names are tens of bps. Costs are the same order as
  the per-bar signal, which is why the reward here is net of cost **at every
  step**, including the extended tier.

---

## Part 2 — Methodology

### Data and eligibility

| item | value |
|---|---|
| bars | `data/massive/m1/{SYM}_{date}.csv`, 1-min, 04:00–20:00 ET, UTC timestamps |
| pool | `data/massive/gappers_novol_{y2025,year,aug2026}.json` — only `symbol`, `date`, `prev_close` are read |
| halal | `plan/penny_ax11b_massive.halal_pt` under `HALAL_STRICT=1 PT_FILED=1`, network removed (`plan/rl/halal_offline.py`) |
| grid | 960 minutes per day, index = ET minute-of-day − 240, DST via `zoneinfo` |

**Eligibility is the leak-safe rule from the retraction.** A name may be
looked at, ranked or bought at minute *m* only if a **regular-session bar
(≥ 09:30) at or before m** printed `high ≥ 1.10 × prev_close`. Pool
membership is itself conditioned on the regular-session high, so anything
earlier is future-conditioned — that is how +$214k of a previously-claimed
edge was manufactured. Consequence, inherited and intended: **no premarket
entries exist anywhere in this study.** Measured onset distribution: p10 =
09:30, median ≈ 10:19–10:40, p90 ≈ 14:31–15:10; 15–19% of names are already
eligible at 09:30, ~0.1% only after 16:00.

**Per-day universe cap** (memory bound): at most 96 names per day, ranked by
cumulative dollar volume 04:00–09:29 ET — strictly before the first legal
decision minute, so the cap cannot see the day's outcome. It binds on 52 of
7,185 kept y2025 rows (0.7%).

### The honest confound in the universe, stated up front

`halal_pt` needs point-in-time shares outstanding. With the network removed,
`shares_asof` reads `data/pt_shares/{SYM}_{date}.json`, falling back to the
**nearest earlier** cached as-of date (stale, never future) and refusing when
there is none. Both `data/pt_shares` (≈2.0k symbols) and `data/pt_halal`
(1,393 symbols) were **populated by earlier campaigns**, whose rankers were
later shown to be future-conditioned. So *which symbols have cached
fundamentals at all* is an arbitrary, campaign-shaped subset of the gapper
pool. Cache hit split across all three pools: 20,816 exact-date, 34,871
nearest-earlier, 11,489 refusals.

This **inflates or deflates absolute numbers in an unknown direction**. It
does **not** affect the comparison the study turns on, because the random
baseline, the shuffled-label control and every RL agent draw from the *same*
eligible set with the *same* fills. Only the policy differs.

### The environment (`plan/rl/env.py`)

- **Episode = one trading day.** Decisions every 5 minutes from 09:30 to
  19:55 ET → 126 steps/day.
- **Action space `Discrete(18)`**: hold, buy candidate slot *k* (K = 10),
  sell position *p* (P = 7). Slots are filled by a **causal** ranking of the
  eligible set by trailing-30-minute dollar volume (a liquidity proxy, not a
  return predictor); the random baseline uses the identical slotting.
- **Observation (209 dims)**: 10 slots × 15 causal features, 10 availability
  flags, 7 positions × 6 state features, 7 globals (minutes to 16:00, minutes
  to 20:00, extended-session flag, tickets used, positions open, day equity,
  fraction of day elapsed). Every feature at step *m* uses bars with index
  ≤ *m* only.
- **Fills at the NEXT bar's open.** If minute *m+1* has no print, the order
  does not happen. Availability masks read bar *m*, never *m+1* — the agent
  cannot peek at whether the next minute will print.
- **Costs**: 10 bps/side always, **+50 bps** on any fill outside 09:30–16:00
  (the engine's extended/premarket spread haircut). A fill may not exceed
  **20% of the symbol's volume over the trailing 5 minutes**; capped fills are
  sized down and dropped below $500 notional.
- **Tickets**: $15,000 × 6 then $10,000, ≤ 7 concurrent, ≤ $100k/day, one
  open ticket per symbol, long only.
- **Forced flatten** at the day's last printed bar for each held symbol, at
  that bar's close, with the cost ladder applied.
- **Reward** = change in mark-to-market equity in $1,000s, so cost is in the
  learner's signal at every step — the failure mode that makes
  gym-anytrading agents churn.
- **Normalizer** fitted on train days only, handed to val/test/extra
  unchanged, clipped to ±5.

### Splits (date-strict, from different pool files)

| split | pool file | dates | days |
|---|---|---|---|
| train | `y2025` | 2024-10-22 → 2025-05-30 | 151 |
| val | `y2025` | 2025-06-02 → 2025-07-31 | 42 |
| test | `year` | 2025-08-01 → 2026-07-31 | 251 |
| extra | `aug2026` | 2026-08-03 → 2026-08-31 | 22 |

Validation is used **only** for checkpoint selection (10 checkpoints per
run). Test is touched once, at the end.

### Honesty machinery (`plan/rl/honesty.py`)

| check | what it does | why |
|---|---|---|
| **poison test** | replace every bar strictly after minute *m* with garbage; the raw causal arrays, the observation, the action mask and the action a deterministic policy takes at every step ≤ *m* must be **bit-identical** | look-ahead in the state becomes impossible rather than merely unintended |
| **hold-is-zero** | a never-trade policy must return exactly $0 | any reported P&L is attributable to fills, not accounting drift |
| **cost monotonicity** | zero-cost > modelled-cost > 10×-cost for the same fixed policy | the fee/extended ladder is actually live in the reward |
| **shuffled labels** | train *and* test on a panel whose per-symbol intraday log-return sequence is permuted (onset recomputed on the shuffled path) | a positive test result here is proof of leakage in the evaluation |
| **clairvoyant control** | next-step open-to-open return appended to the observation | if the harness cannot make money *with* the future, a null result has no power and means nothing |
| **random × 30 seeds** | uniform over legal actions, identical eligibility/slotting/fills/costs | the baseline that most often ends the conversation |

### Compute

Cluster: `unicorn-login-01.coecis.cornell.edu`, SLURM, workspace
`/share/taylor/me484/stocks-rl`. Env throughput measured there: **4,357
env-steps/s** for a scripted policy. Grid = 32 array tasks (4 CPUs, 24 GB,
6 h each), 14 concurrent. PC was not used for training (4 cores, saturated by
another agent's `rotation_sim` jobs).

---


## Part 3 — Results

56 training runs completed on the cluster (4 CPUs each, ~15–25 min per run).
All numbers below are **dollars on a $100k/day ticket budget**, deterministic
evaluation, and the test split is **251 trading days, 2025-08-01 → 2026-07-31**,
touched once.

### 3.1 The honesty battery — all checks behave

| check | result |
|---|---|
| **poison test, train** | 16 days x 4 cut points = **64 checks, 0 mismatches** in the raw causal arrays, the observation, the action mask and the action |
| **poison test, test** | 16 days x 4 cut points = **64 checks, 0 mismatches** |
| **hold-is-zero** | exactly $0 and 0 tickets on all four splits |
| **cost monotonicity** | zero-cost −15,781 > modelled −24,163 > 10x-cost −98,140 for the identical policy |
| **clairvoyant control (5 min)** | PPO test **+$61,838 (+$35.3/ticket)**, MaskPPO +$28,628, EIIE-Mask +$636,748 — vs random −$101.6/ticket |
| **clairvoyant control (30 min)** | MaskPPO test **+$328,381 (+$186.9/ticket, Sharpe 7.00)**, EIIE-Mask **+$924,964 (+$526.4/ticket, Sharpe 13.19)** |

The 30-minute clairvoyant control is the one that matters: **the same code,
the same costs, the same eligibility and the same fills turn +$187 to +$526
per ticket when the observation carries the future.** The harness is not
blind. A null result from it is therefore informative rather than vacuous.

### 3.2 The shuffled-labels control was mis-specified — and what it actually showed

PPO trained and tested on the time-shuffled panel returned **+$479,687 on
test (+$279.6/ticket, Sharpe 4.26)**. By this study's own rule that is proof
of leakage, so it was chased down before anything else was written.

**It is a defect in the control, not a leak in the environment.**
`DayData.shuffled` *permutes* each symbol-day's 1-minute log returns, and a
permutation preserves their **sum** — the day's terminal price is unchanged
while the path between it and the open is randomized. That is a Brownian
bridge pinned at both ends, and an entry at a randomly-depressed point of
such a path is mechanically dragged back up to the fixed endpoint. Measured
on 60 test days with **no agent and no learning**, one $15k ticket opened at
a random eligible minute and held:

| | real panel | permuted panel |
|---|---|---|
| hold 30 min | −$44.91 | −$2.94 |
| hold 120 min | −$50.19 | **+$96.24** |
| hold to forced flatten | −$44.46 | **+$235.21** |

The correct question is not "is the shuffled agent positive" but **"does it
beat its own panel's baselines"** (`plan/rl/shuffle_control.py`):

| shuffled panel, test split | $/ticket |
|---|---|
| RANDOM x10 on the shuffled panel | +166.0 |
| RANDOM_EAGER x10 on the shuffled panel | +2.3 |
| BUYFIRST on the shuffled panel | **+258.6** |
| PPO-shuffle (3 seeds) | +279.6 |
| EIIE-Mask-shuffle (5 seeds) | +107.5 |
| MaskPPO-shuffle (3 seeds) | +38.3 |

PPO-shuffle sits on top of a scripted buy-and-hold on the same panel
(+279.6 vs +258.6, inside a seed range of +179,685 … +749,724), and the
other two shuffled agents are **below** their panel's random baseline.
**No evidence of leakage.** The control is retained, with the caveat that a
return-permutation null is structurally wrong for a path-dependent env and a
resampling null would be the right redesign.

### 3.3 The main table

Splits: train 151 d, val 42 d, **test 251 d**, extra (aug-2026) 22 d.
"Seed spread" is min … max of total P&L across seeds.

| policy | variant | seeds | split | total P&L | $/ticket | tickets/day | Sharpe (d, ann) | max DD | seed spread |
|---|---|---|---|---|---|---|---|---|---|
| HOLD | – | 1 | test | **0** | 0.0 | 0.00 | 0.00 | 0 | – |
| CHURN (buy, flip 5 min later) | – | 1 | test | −65,114 | −37.1 | 7.00 | −2.46 | −75,149 | – |
| BUYFIRST (buy, hold to flatten) | – | 1 | test | −508,742 | −289.6 | 7.00 | −3.90 | −513,491 | – |
| RANDOM | – | 30 | test | −163,319 | −101.6 | 6.40 | −2.77 | −184,620 | −288,062 … +26,500 |
| RANDOM_EAGER | – | 30 | test | −141,661 | −80.6 | 7.00 | −2.79 | −160,102 | −260,529 … −5,282 |
| **PPO** | real | 5 | test | **−66,016** | **−37.8** | 6.95 | −1.43 | −74,843 | −93,403 … −35,087 |
| **MaskablePPO** | real | 5 | test | **−84,112** | **−47.9** | 7.00 | −2.25 | −129,257 | −199,121 … **+86,100** |
| **EIIE-PPO** | real | 5 | test | **−95,419** | **−70.2** | 4.97 | −2.87 | −103,162 | −145,784 … −8,560 |
| **EIIE-MaskablePPO** | real | 5 | test | **−72,745** | **−41.5** | 7.00 | −1.90 | −85,491 | −190,769 … −24,428 |
| **DQN** | real | 5 | test | **−57,577** | **−32.8** | 6.99 | −0.53 | −147,434 | −168,677 … +14,010 |
| **SAC** (score-vector wrapper) | real | 5 | test | **0** | 0.0 | **0.00** | 0.00 | 0 | degenerate — see 3.6 |
| PPO | leak (5 min) | 3 | test | +61,838 | +35.3 | 6.96 | 1.48 | −49,523 | +19,971 … +92,828 |
| MaskablePPO | leak30 (30 min) | 3 | test | +328,381 | +186.9 | 7.00 | 7.00 | −11,865 | +309,700 … +350,349 |
| EIIE-Mask | leak30 (30 min) | 3 | test | +924,964 | +526.4 | 7.00 | 13.19 | −6,987 | +867,605 … +1,013,791 |

Other splits, `real` variant only (total P&L):

| policy | train (151 d) | val (42 d) | test (251 d) | extra (22 d) |
|---|---|---|---|---|
| PPO | −4,415 | +17,956 | **−66,016** | +6,719 |
| MaskablePPO | +80,435 | +1,766 | **−84,112** | +19,754 |
| EIIE-PPO | −43,535 | +5,545 | **−95,419** | −5,668 |
| EIIE-Mask | −39,019 | +16,572 | **−72,745** | +3,540 |
| DQN | +74,361 | −23,393 | **−57,577** | +6,370 |
| RANDOM x30 | −109,775 | −51,857 | −163,319 | −5,497 |
| HOLD | 0 | 0 | 0 | 0 |

### 3.4 Extended-hours vs regular-session exits (test split, mean over seeds)

This is where the money goes.

| policy | ext exits (n) | ext exit P&L | RTH exits (n) | RTH exit P&L | mean hold | forced flattens |
|---|---|---|---|---|---|---|
| BUYFIRST | 1,741 | **−506,564** | 16 | −2,179 | 572 min | 1,741 |
| RANDOM x30 | 1,117 | **−142,082** | 491 | −21,237 | — | — |
| EIIE-PPO | 926 | −92,430 | 322 | −2,989 | 198 min | 858 |
| PPO | 481 | −57,027 | 1,263 | −8,990 | 171 min | 413 |
| DQN | 596 | −38,078 | 1,157 | −19,499 | 240 min | 530 |
| MaskablePPO | 153 | −72,606 | 1,604 | −11,506 | 83 min | 151 |
| EIIE-Mask | 154 | −110,188 | 1,602 | **+37,444** | 63 min | 148 |
| CHURN | 0 | 0 | 1,757 | −65,114 | 5 min | 0 |

Regular-session exits lose about −$7 per exit for the short-holding agents —
essentially just the 20 bps round trip. **Extended-hours exits lose −$119 to
−$715 each.** The 50 bps extended haircut, applied to a gapper that has
faded and is being flattened into a thin post-16:00 tape, is the single
largest loss term in every row. EIIE-Mask is the only policy whose
regular-session exits are collectively **positive** (+$37,444 over 1,602
exits, +$23/exit) — and it still loses overall because its 154 extended
exits give back −$110,188.

### 3.5 Why no positive row is believable: validation predicts nothing

Across the **25 `real` runs** (5 algorithms x 5 seeds, excluding SAC):

- **corr(validation P&L, test P&L) = −0.126.**
- **16 of 25 runs had positive validation P&L. Zero of those 16 had positive test P&L.**
- Only **2 of 25** runs were positive on test, and **both had negative validation** — the model-selection rule would have thrown them away.
- The best-validation run (PPO seed 4, val +32,322) returned **−$78,709** on test.
- The best-test run (MaskablePPO seed 1, test **+$86,100**) had **validation −$5,681**, the second-worst validation score of its five seeds.

This is the phenomenon Bailey, Borwein, López de Prado & Zhu describe:
selection on a short, noisy performance statistic yields **negative**, not
zero, expected out-of-sample return. The multiple-testing count behind the
single positive row is 6 algorithms x 5 seeds x 10 validation checkpoints,
about **300 looks**; at that count a lone +0.95 Sharpe over 251 days is what
the null distribution produces by itself.

### 3.6 Two mechanical findings worth keeping

**SAC degenerates to abstention.** All five SAC seeds returned exactly $0
with **zero tickets** on every split. The continuous-score to masked-argmax
wrapper lets a near-constant output vector park permanently on the
always-legal "hold" index. This is the "discretized wrapper" failure mode,
not a market result — SAC/TD3 should not be used this way.

**Action masking is worth a lot mechanically.** MaskablePPO and both EIIE
variants record **0 invalid actions**. Unmasked PPO and DQN waste roughly
26,000–28,000 of their 31,626 test decisions (about 84%) on illegal actions
that silently become no-ops. They are therefore not really choosing to hold
— they are missing. This is the strongest practical argument for
`sb3-contrib` MaskablePPO over vanilla SB3 in this setting.

### 3.7 The universe itself, measured (`plan/rl/pool_profile.py`)

No policy, no ranking: buy one $15k ticket at every eligible minute at the
next bar's open, sell H minutes later, same costs and same size cap.

| hold | train | val | test | extra |
|---|---|---|---|---|
| 5 min | −35.07 | −39.02 | −38.56 | −40.00 |
| 15 min | −42.25 | −42.06 | −43.19 | −39.54 |
| 30 min | −48.93 | −46.06 | −47.86 | −41.95 |
| 60 min | −56.43 | −54.15 | −54.26 | −39.74 |
| 120 min | −58.28 | −73.63 | −58.62 | −20.41 |
| 240 min | −70.16 | −137.37 | −53.97 | +35.55 |
| to forced flatten | −88.90 | −99.76 | −74.94 | −22.37 |

$/ticket; n = 161k / 60k / 317k / 18k entries; t-statistics −10 to −85.
**The eligible set has a persistent negative net expectancy at every horizon
on every split.** A 20 bps round trip on $15,000 is $30, so roughly $30 of
the −$38 five-minute figure is pure cost and the rest is real post-onset
fade. Any long-only policy over this universe must either abstain or find
about +$40/ticket of selection alpha just to break even.

### 3.8 Against the project's own re-baselined engine rows

The parallel `rs_cross` (regular-session-cross eligibility) re-baseline
landed while these runs were finishing — `data/massive/rotation_results_rs_bench.json`
and `..._rs_bench_aug.json`:

| row | window | days | tickets | total | $/ticket | win days |
|---|---|---|---|---|---|---|
| C37F-rs | year (= our test window) | 251 | 1,107 | **+21,910** | **+19.8** | 52.6% |
| C37F-rs | y2025 | 194 | 941 | +6,442 | +6.8 | 50.0% |
| C37F-rs | aug2026 | 22 | 94 | −666 | −7.1 | 50.0% |
| HOLD1-rs | year | 251 | 252 | −36,329 | −144.2 | 45.4% |
| HOLD1-rs | y2025 | 194 | 196 | −14,523 | −74.1 | 44.8% |
| HOLD1-rs | aug2026 | 22 | 22 | +927 | +42.1 | 54.5% |

**Not a like-for-like comparison** — C37F runs the engine's own halal gate
(network-backed point-in-time shares), its own pool hygiene, its own ranking
and cut, its own entry windows and its own exit machinery and fill model. It
is reported here because it covers the same dates and the same pool family
under the same leak-safe eligibility rule, and because it is the honest
reference this project already maintains. Read it as: **a hand-built rule
system is at +$19.8/ticket on the test window while every RL agent trained
here is between −$32.8 and −$70.2.** These C37F-rs rows come from a parallel
run and have **not** been independently audited by this study.

---

## Part 4 — Verdict

**Nothing beats the baselines after costs, across seeds. The best policy any
of these agents found is the one that trades least, and the best policy
available on this universe is not to trade at all.**

1. **Every RL algorithm loses money on the 251-day test window.** PPO −$66k,
   MaskablePPO −$84k, EIIE-PPO −$95k, EIIE-Mask −$73k, DQN −$58k. HOLD
   returns exactly $0 and beats all of them.
2. **They beat random, but not by trading better — by trading less badly.**
   Random is −$101.6/ticket. The agents land at −$32.8 to −$70.2/ticket,
   which brackets **CHURN at −$37.1/ticket**, a mechanical buy-and-flip with
   no information whatsoever. PPO's −$37.8 and DQN's −$32.8 are
   indistinguishable from paying the round trip and adding nothing. What the
   agents actually learned is *"exit before 16:00 so you don't pay the 50
   bps"* — a cost-avoidance rule, not alpha.
3. **The harness has power.** With 30 minutes of foresight the identical code
   earns +$187 to +$526 per ticket at Sharpe 7–13 on the same test split.
   The null is a real null.
4. **No leakage was found.** The poison test passes 64/64 on train and 64/64
   on test — observation, action mask and action all bit-identical when every
   future bar is replaced with garbage. The one alarming positive
   (shuffled-labels PPO, +$480k) was traced to the control's own
   Brownian-bridge artifact and shown to be matched by a scripted
   buy-and-hold on the same permuted panel.
5. **Validation is uninformative here**: corr(val, test) = −0.126, 16 of 25
   positive-validation runs were negative on test, and the only seed that
   made money on test is one validation would have rejected.

### The closest miss

**MaskablePPO, seed 1**: test **+$86,100** over 1,757 tickets
(**+$49.0/ticket**, Sharpe 0.95, max DD −$55,588), and **+$26,931** on the
out-of-sample aug-2026 extra split. It is the only row in the study that is
positive on both the test window and the extra window.

It should not be believed, for four reasons:

- its **validation P&L was −$5,681**, so the pre-registered selection rule discards it;
- its four sibling seeds returned −$150,883, −$199,121, −$63,523 and −$93,132;
- 2 of 25 real runs were positive on test, about what 25 draws from a
  −$85k-mean, ±$100k-spread distribution produce;
- the multiple-testing count behind it is about 300 looks, and a deflated
  Sharpe at that trial count is comfortably below zero.

It is recorded as the closest miss, not as a candidate. The only legitimate
next step for it is a **pre-registered** re-run of that exact configuration
on data that did not exist when this was written.

### What would actually be worth trying next

1. **Qlib RL on the execution layer, not the selection layer.** The measured
   cost structure says so: regular-session exits cost about $7 each while
   extended-hours exits cost $119–$715. Execution quality is 10–100x the size
   of anything selection found here. Highest-value follow-up; not attempted.
2. **Make the flatten deadline a decision, not a constant.** Every agent's
   loss is concentrated in its forced flattens. An agent whose action space
   includes "be flat by 15:55" may be the whole result.
3. **Redesign the shuffled-labels control** as a resampling null (i.i.d.
   bootstrap of returns, or a random-walk panel that keeps the real
   eligibility times) so it does not pin the endpoint.
4. **Fix the universe confound**: backfill `data/pt_shares` / `data/pt_halal`
   across the whole gapper pool rather than over whatever earlier campaigns
   happened to query, so the halal universe stops being campaign-shaped.

### Caveats that limit every number above

- **Universe coverage is campaign-shaped** (see "The honest confound" in
  Part 2). The RL-vs-baseline comparison is internally valid — same eligible
  set, same fills — but the absolute levels are not portable.
- **Deterministic evaluation biases toward maximal trading.** An argmax
  policy with any preference for buying spends all 7 tickets every day, which
  is why almost every row shows about 7.0 tickets/day. The stochastic policy
  may trade less; it was not evaluated.
- **Effective sample is 151 training days**, replayed thousands of times over
  400k steps. Memorization is the default; that it did not produce a positive
  test row is the point, but it also means these agents were never going to
  generalize from this much data.
- **One decision every 5 minutes, one action per decision.** A faster or
  multi-action agent was not tested.
- **The forced flatten uses each symbol's last printed bar's close.** For
  names that stop printing mid-afternoon that is a price from earlier in the
  day; neither systematically generous nor punitive, but it is a convention.
- **No market impact model** beyond the 20%-of-trailing-volume cap; per
  arXiv 2603.29086 a square-root impact term can change algorithm *rankings*,
  not just levels.
- **C37F-rs / HOLD1-rs are the parallel run's numbers**, on a different
  universe and engine, and are not audited here.

---

## Reproducing

```
python plan/rl/build_days.py                 # ~10 min, writes plan/rl/out/days/
python plan/rl/honesty.py                    # poison test + sanity checks
python plan/rl/pool_profile.py               # unconditional expectancy
python plan/rl/baselines.py                  # HOLD/BUYFIRST/CHURN/RANDOM x30
python plan/rl/shuffle_control.py            # shuffled-panel baselines
python plan/rl/train.py --algo maskppo --variant real --seed 0 --steps 400000
python plan/rl/report.py                     # the table above
```

Cluster: `/share/taylor/me484/stocks-rl` (`grid.txt`, `grid2.txt`, `grid3.txt`,
`slurm_rl*.sh`). Python: `C:\cornell\venvs\rl` locally (gymnasium 1.3.0,
stable-baselines3 2.9.0, sb3-contrib 2.9.0, torch 2.14 CPU); the engine's
Python was never touched.
