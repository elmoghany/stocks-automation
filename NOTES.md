# Normal Trading Notes

Convention: new notes go at the TOP of this file. Each note = a **3-word title**,
then a detailed explanation of what was done and why.
Penny-stock day-trading notes live in `NOTES-DAYTRADING.md`.

---

## Chart Endpoint Hunt (2026-08-02)

Investigated whether E*TRADE can serve HISTORICAL intraday bars. The local
API documentation (all 5 files, all 31 endpoint URLs enumerated) contains
no candles/chart/history endpoint -- market API is quote, lookup,
optionchains, optionexpiredate only; detailFlag=INTRADAY is a current-quote
snapshot, not bars. BUT live probing found /v1/market/chart/{symbol} (and
/charts/) EXISTS on the gateway: returns 401 "Unauthorized request" while
fake paths return 404 "Resource not found" -- an undocumented,
entitlement-gated endpoint. Tested with BOTH sandbox and PROD keys
(prod token obtained via manual two-phase exchange; note
test_extended_order.py --verifier path auto-runs an order preview and has
a bug: ETradeSession.__new__ skips __init__ so self.sandbox is unset ->
_save_token crashes; exchanged manually instead): still 401 on prod.
Also ruled out market-closed/Sunday as the cause: historical date params
(MMDDYYYY + ISO ranges for Fri Jul 31), interval params, and the
consumerkey header all return the same 401 on the working prod token --
an entitlement rejection happens before any date/market-hours logic.
Conclusion: endpoint exists but is not granted to developer keys --
likely internal to E*TRADE's own apps or needs a special entitlement; ask
E*TRADE API support (developer@etrade.com) to enable "chart" for the key.
Online research confirms: the maintained community wrapper (etrader R
package, exploringfinance) exposes only etrd_market_quote() and
etrd_option_chain() for market data -- no history/candles function exists
in any public E*TRADE wrapper; developer.etrade.com blocks scraping (403)
but its documented API list matches our local docs. Until then: historical
bars stay yfinance; LIVE bars via quote polling (penny livebars). PROD validation same session: real AMD quote OK, and
penny livescreen --prod returned REAL data (SCYX +26%, TCX +56% 6.9x rvol
-> passed live rules, FCUV +807% correctly out of band at $17.05).

## Sandbox Order Test (2026-08-01)

Full E*TRADE sandbox chain verified end-to-end: two-phase OAuth via
`plan/sandbox_auth.py` (--auth opens browser, --verifier CODE saves token to
`data/.etrade_access_token_sandbox.pkl`), smoke test returned 3 sandbox
accounts, then `plan/sandbox_place_test.py` previewed and PLACED a LIMIT BUY
1 x AMD @ $100 on account 823145980 -> orderId 529, "Normal: order created".
Fixed a rauth 0.7.3 bug hit on the way: GET calls without a `params` argument
crash inside rauth (`TypeError: NoneType is not iterable`) — added `params={}`
to `renew_token`, `get_account_list`, `get_portfolio` in api_wrapper.py; this
would also have crashed the 90-min renew loop in live trading. Sandbox quirks:
quotes/estimated totals come back None or canned — it validates plumbing
(auth, XML payloads, preview->place), not prices or fills. AMD wave params
also recalibrated in wave_config.py to dip 8% / sell +20% / lookback 3d per
the walk-forward backtest.

## Secure Key Storage (2026-08-01)

E*TRADE API keys (PROD + SANDBOX, key + secret for each) moved into the Windows
Credential Manager, DPAPI-encrypted at rest and tied to the Windows login. Access
is through the new zero-dependency module `trading/win_cred.py` (stdlib `ctypes`
calling `advapi32` CredRead/CredWrite — no pip packages). Stored names:
`ETRADE_PROD_KEY`, `ETRADE_PROD_SECRET`, `ETRADE_SANDBOX_KEY`, `ETRADE_SANDBOX_SECRET`.
`trading/api_wrapper.py` and `test_extended_order.py` now resolve keys in this
order: Credential Manager → env vars (`SANDBOX_API`/`SANDBOX_SECRET_API`) →
`etrade_python_client/config.ini`. The plaintext keys were redacted from
`trading-stocks-prompts.md` so nothing secret remains in the repo. CLI:
`python -m trading.win_cred set|get|list|delete NAME`. Note honestly: nothing a
script can read unattended is absolutely theft-proof — this protects against git
leaks, registry/env snooping, and other user accounts, not malware running as
the same user.

## Reduce SMS Verification (2026-08-01)

For automated trading, only ONE SMS-verified browser login per day is needed:
E*TRADE access tokens live until midnight US Eastern and go dormant after 2h of
inactivity, but `renew_access_token` revives them without login — `trading/main.py`
already renews every 90 min. To cut login SMS further: tick "Remember this
device" on the 2FA screen and reuse the same browser profile (incognito forces
SMS every time), and/or switch 2FA from SMS to an authenticator app (TOTP) in
the Security Center — the TOTP seed can be stored in Credential Manager so the
daily re-auth is fully automatable. Never disable 2FA outright on a brokerage
account. Sandbox uses the same OAuth login flow. E*TRADE tokens hard-expire at
midnight ET daily (server-side, cannot extend to weekly); for 1 login/week or
zero-login APIs consider Schwab (7-day refresh token), Alpaca (permanent API
keys), or IBKR gateway.

## AMD Walkforward Backtest (2026-08-01)

Built `plan/amd_oos_backtest_2026.py`: trains on Aug 2015–Jul 2025 ONLY (10
years), then tests frozen parameters out-of-sample on Aug 2025–Jul 2026 with
$100K all-in per trade, limit-style fills, no leverage. 8 strategy families,
~7,700 parameter combos; for each family kept the best-10y-compound pick
("max") and best-median-train-year pick ("robust"). Results: Buy & Hold =
$279,616 (+179.6%). Only ONE strategy beat it: Never-Lose dip/rip robust —
buy 8% dip from 3-day high, sell +20% — $301,108 (+201.1%), 5/5 winning closed
trades. The current `wave_config.py` AMD params (dip 2.5%, sell +10%) made only
+142.9% ($36.7K behind B&H) because the tight +10% target sold the rally too
early and it re-bought near the top ($557.53 on Jul 1, still −14.6% open).
Big lessons: (1) train performance did NOT predict test performance — every
"max" pick (113x–155x on train) underperformed its "robust" sibling OOS, clear
overfitting; (2) stop-losses and indicator strategies (SMA cross, RSI,
Bollinger) all badly lagged in a strong uptrend; (3) wider dips + bigger
targets is the direction that works on AMD. Results JSON in session scratchpad
(`amd_oos_results.json`).

## Etrade Prod Wiring (2026-06-15)

Wired up the E*TRADE production API using the user's PROD consumer key to
analyze a 29-stock watchlist (LLY, TSM, LRCX, COST, AMD, ARM, INTC, ANET, ISRG,
VRT, PH, CDNS, TT, CEG, SNPS, SHW, ROST, REGN, MPWR, FIX, GWW, JBL, MLM, IR,
RMD, HUBB, IOT, LII, MLI, PNR) for a buy-and-hold pick, factoring in news
(e.g. Iran–US deal). Two-phase auth flow lives in `test_extended_order.py`
(`--auth` opens browser, `--verifier CODE` completes). Keys kept out of git;
live brokerage selected for later buy/sell automation.

## Wave Never Lose (2026-06-11 → 2026-06-13)

Developed the wave trading system (`trading/wave_*.py`): buy when price dips X%
from the recent N-day high, sell at +Y%, never sell at a loss, 100% capital per
trade, compound. Goal evolved from 400% ROI → 600–1000% → "5x buy-and-hold" for
Jun 2025–Jun 2026, no leverage, 2+ trades/month, large-cap stocks only (AMD,
NVDA, ARM, LRCX, INTC, MU class). Ran ~1000 parameter-sweep backtests (dip,
sell, lookback grids) on AMD/AVGO/MRVL and later ARM/AMD/LRCX/NVDA, using
2023–2025 history plus S&P500/SPY cross-signals. Calibrated result stored in
`trading/wave_config.py`: default dip 2.5%/sell +11%/lookback 5d; per-stock
optimized params for top-6 (FIX, VRT, LRCX, AMD, TDW, TSM); backtest showed
$100K → $361K–$384K across 6 stocks, beats B&H on 20/21 stocks. Learnings from
the ~96 research agents captured in learnings.md (separate session).

## Value Trading System (2026-06-11)

Built the original 13-module value-based system under `trading/` on top of the
E*TRADE Python client: fundamentals scoring 0–100 (PE, EPS growth, revenue
growth, margins, debt/equity, fair-value gap), 10% price windows around a
60-day median, inverse sector rotation across 50 stocks in 3 sectors
(tech/energy/minerals), wash-sale + T+1 settlement tracking, SIM vs REAL
executors (LIMIT orders only), 10-minute polling loop in `trading/main.py`.
Architecture documented in `system-arch.md`.

## Etrade Client Setup (2026-06-11)

Started from E*TRADE's official Python client (`etrade_python_client/`,
untouched SDK) plus API documentation. Established repo rules: never commit
`config.ini` or `data/` (both gitignored), sandbox keys via env vars,
production keys via config.ini (later superseded — see Secure Key Storage).
