# October research round (2026-10-01): multi-day holds + legacy leads

Four lines, run after the user opened research to overnight and multi-day holds (long-only,
cash account). Per-line reports are in this folder. $ figures are for a $100k account.

| line | best honest rule | result | verdict |
|---|---|---|---|
| SWING-REVERSION | 5 worst 5-day losers among top-500 liquid names, buy next open, hold 3 closes | +$2.8k / +$7.0k / +$12.6k per month (Y1 / Y2 / OOS), but beta 1.7–2.3; 20-year alpha negative in 2 of 4 blocks; 2008/2020 drawdowns −$90…−150k | regime bet; zero-capital shadow at most |
| OVERNIGHT | 20 worst 5-day losers, market-on-close buy → market-on-open sell | +$1,439/mo at 6 bps/side; −$1,081 at 12; ~half that under settled cash; t 0.85 | edge ≈ cost; shadow-log real 15:55 / 09:30 quotes |
| SWING-EARNINGS | top-600 earnings names, gap down then green at 09:35, hold 10 days | ≈ $1,150/mo vs SPY $1,330 over the same span; OOS −$1.8k/mo | no edge over SPY; keep R15 at 1 hour |
| LEADS-TEST | TC regime / quiet-near-high / large-cap premarket gap, each with the hygiene stack | first two fail; large-cap gap −$55…+$111 per trade (survivorship) | nothing added to paper; large-cap gap needs a 60-date whole-market fetch |

Common thread: once holding periods reach overnight or days, every family earns roughly
the market's own return (beta). Stock selection adds no reliable alpha after costs. Buying
recent losers works before costs, but mostly as exposure to high-volatility names.

Data note: the Massive/Polygon key measured exactly 5 requests/min on 2026-10-01 (free-tier cap)
and blocked the large-cap premarket fetch. Check the subscription.
