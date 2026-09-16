# RL-SERIES (2026-09-16) — online RL for portfolio management and stock trading, tested against the halal universe

**Status: survey complete; environment built and adversarially checked; training runs in flight on the Cornell cluster.**
Results table and verdict are at the bottom and are filled in from
`plan/rl/out/results/*.json` + `plan/rl/out/baselines.json`.

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

*(filled in below from `plan/rl/out/results/` and `plan/rl/out/baselines.json`)*
