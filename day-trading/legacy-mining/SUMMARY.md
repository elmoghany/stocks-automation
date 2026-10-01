# LEGACY-MINING — what the old champions still teach (2026-10-01)

Fifteen parallel analysts mined C37 and its predecessors (C34/C35/S095/Z104/W109/R-series),
each on one aspect, using honest-harness trades only (R4 legs, C37F-hf3 ledger, 30-seed
random controls, cp_panel, live paper ledgers). Reports: `LEGACY-1..15.md` (LEGACY-7 is
`lm7-losers-vetoes.md`). $ are per $10k ticket; "net" = after ~15 bps/side unless stated.

## The headline: R4 is weaker than it looked

Four independent findings, all pointing the same way:

1. **Tie-break leak (LEGACY-2).** R4 ranks with a stable sort on `-coil`; ~5 names tie at
   coil = 1.0 at a typical decision, and ties fall to pool-file order, which correlates with
   FULL-DAY volume (Spearman −0.40…−0.53). Random tie-break: +81 → +37 bps gross, ≈ +$7 net
   (break-even). CHAMPION-REPLAY's "coil +$109 vs random, z≈5" and every index-ordered row
   (R1, "first eligible") are contaminated.
2. **Tail dependence (LEGACY-6/10/12/14).** 5 trades (MNPR, YIBO, ARMP, HUIZ/SGN, FLYE/RNAZ)
   = 100–134% of R4's P&L; ex-top-5 R4 is −$500…−$1,350/month.
3. **The tail lives in untradeable names (LEGACY-6/12/15).** All of it is in names with
   < $1M/day typical dollar volume (a $10k order fills ~$5k; spread 40–65 bps RT); a live 0.5%
   spread veto refuses 255/965 R4 legs incl. the whole tail.
4. **Out of sample (LEGACY-1/14).** Aug 2026 (22 sessions): R4 −$4.4k; every exit variant
   −$41…−$175/ticket.

Realistic live expectation for R4: ≈ break-even, plus occasional lottery winners. It stays
in paper (user standing order 2026-10-01) with a causal tie-break and a shadow-leg log.

## Things that genuinely transfer (hygiene: they cut losses, they don't create edge)

| rule | source | value (est.) | status |
|---|---|---|---|
| Spread filter: skip if est. half-spread (max CS/AR, 30 bars ≤ t) > 10 bps | LEGACY-9 | random picks −$36 → −$4.5/tkt; 29/30 seeds; OOS ✓ | test in rotation_sim |
| Live 0.5% spread / 25% depth veto (keep) | LEGACY-15 | refused names lost ~2.6 pts more than traded | keep live |
| Liquidity floor dvol60 ≥ $5M / prior-day $vol ≥ $1M / prior-day vol ≥ 0.5× | LEGACY-12 | ~+$40/tkt of cost avoided | test |
| Range screen: skip sigma1 undefined or > 0.017 | LEGACY-13 | random −$17.6 → ~0/tkt | test on next entry line |
| No buying before 09:35; no premarket entries | LEGACY-4/8/15 | premarket ≈ −$280…−$615/tkt every subset | adopted for 3-book |
| Don't buy names that opened +10% with heavy $vol before noon | LEGACY-8 | −154 bp fade 09:31–11:00, both years + Aug OOS | guard for future lines |
| Scanner-age gate: skip names that crossed ≤ 10 min ago | LEGACY-5 | R4 +$400…+$1,000/mo (mostly fees) | test with causal tie-break |
| Pre-open veto: 09:29 < 0.80×PM high or < 0.95×07:00 price | LEGACY-4 | +$150–250/mo | shadow veto |
| No news in prior 18 h (gappers) | LEGACY-6 | +$290–600/mo on C37F | test |
| Low-participation veto: $vol so far < 7% of 60-d ADV | LEGACY-7 | ≈ +$420/mo, fragile | log as would-veto |
| Buy immediately once chosen; never "wait for a pullback" | LEGACY-3 | random-minute delay −$69/tkt | rule |

## Exits (apply to any entry that already has gross edge)

* No fixed % stop on gapper entries (−8% stop ≈ −$14…−$39/tkt) (LEGACY-1/12/14).
* Bearish-engulfing exit when ≥ +1% in profit, filled at NEXT bar open — the next-open fill
  is +$4–6/tkt BETTER than same-bar close on paired entries (LEGACY-1; LEGACY-14's −$586/mo
  was replay-sequence noise).
* Liquid names: +5% target (next open) + plain 10% trail from high: +$24/trade vs hold
  (20/23 months) (LEGACY-11). Skip the target where profit is tail-driven (LEGACY-1).
* Selling pressure on a winner is a washout that recovers (+25 bp vs −26…−48 otherwise) —
  the old "pressure-flip exit" logic is backwards (LEGACY-11).
* Keep 15:00 flatten; time stops, VWAP-loss, ATR trails, breakeven stops all ≤ 0.

## Leads worth a proper test (speculative)

* **TC regime** (prior close: SPY & QQQ > 20-d MA and SPY 5-d vol < 20-d vol): gapper longs
  +$130…+$176/tkt on TC days vs −$48…−$62 otherwise, both years, random picks too; but Aug
  OOS reversed and ex-top-3 shrinks to +$4…+$19 (LEGACY-10).
* **"Quiet near the high" rank** = rank(coil) − rank(15-min return), gain ≤ 40%, from 09:50;
  short-term reversal IC −0.05…−0.11, t −30…−45 both years (LEGACY-2).
* **Large-cap (≥ $2B) premarket gap after 07:00, sell 10:00**: +70…+180 bps gross est.;
  blocked by a broken market-cap field around reverse splits (LEGACY-4).

## Discard (tested, no value on honest data)

Candle/indicator entry triggers and the "ORB"/PMH stop-buy (it was a market order); time-of-day
and ticket-order rules; scale-outs, front-loaded tickets, stop-after-loss; pressure as rank /
flip exit / sizing; volatility trails, equal-risk sizing; price, float, market-cap buckets;
catalyst composite veto on gappers; prior-P&L regime switches; afternoon breakouts (one day,
2025-04-09); close-momentum on gappers; premarket entries of any kind.

## Bugs found

* Stable-sort tie-break over pool order (cp_sim; check rotation_sim + live ranker) — lookahead.
* Bearish exit filled at the signal bar's close in cp_sim and day-trading.py — fix to next open.
* Market-cap field broken across reverse splits (micro-caps shown as $17B–$724B).
