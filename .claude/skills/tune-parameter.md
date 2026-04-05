---
description: Adjust a trading parameter (scoring weights, thresholds, position limits) in config.py with validation
---

All tunable parameters live in `trading/config.py`. The main parameter groups:

**Scoring weights** (must sum to 1.0):
SCORE_WEIGHT_PE, SCORE_WEIGHT_EPS_GROWTH, SCORE_WEIGHT_REVENUE_GROWTH, SCORE_WEIGHT_PROFIT_MARGIN, SCORE_WEIGHT_DEBT_EQUITY, SCORE_WEIGHT_FAIR_VALUE_GAP

**Window position thresholds** (0.0-1.0, must stay in ascending order):
STRONG_BUY_THRESHOLD < BUY_THRESHOLD < SELL_THRESHOLD < STRONG_SELL_THRESHOLD

**Signal score thresholds** (separate from window thresholds):
COLLAPSE_SCORE_THRESHOLD < FUNDAMENTAL_GATE_THRESHOLD < SELL_SCORE_THRESHOLD < BUY_SCORE_THRESHOLD < STRONG_BUY_SCORE_THRESHOLD

**Portfolio/risk**: MAX_POSITIONS, MAX_POSITION_PCT, WASH_SALE_LOSS_THRESHOLD, WASH_SALE_BLOCK_DAYS

**Sector rotation**: SECTOR_MIN_ALLOCATION, SECTOR_MAX_ALLOCATION (must have min < max, both 0-1)

**Timing**: POLL_INTERVAL_SECONDS, TOKEN_RENEW_MINUTES, WINDOW_LOOKBACK_DAYS, SECTOR_PERF_PERIOD_DAYS

Steps:
1. Ask which parameter to change and the new value if not already specified.
2. Read `trading/config.py` to find the current value.
3. Validate:
   - Scoring weights: verify all 6 still sum to 1.0. If not, show the discrepancy and suggest adjustments to other weights.
   - Window thresholds: verify ascending order is maintained.
   - Signal score thresholds: verify COLLAPSE < GATE < SELL_SCORE < BUY_SCORE < STRONG_BUY_SCORE.
   - MAX_POSITION_PCT: warn if > 0.10 (concentrated).
   - SECTOR_MIN/MAX: verify min < max.
4. Make the change.
5. Run `python -m py_compile trading/config.py`.
6. Show before/after summary.
