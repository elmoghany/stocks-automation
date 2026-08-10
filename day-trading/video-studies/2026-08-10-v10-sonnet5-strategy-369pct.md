# Video study: "Sonnet 5 + Claude Code strategy makes 369%"

- **Watched**: 2026-08-10 · index `b45755dcbb0eea26` (17:38)
- **Instrument/approach**: Claude-generated trend-following system —
  Bollinger Bands + trend EMA + ATR entries, long AND short, 3% risk
  per trade, backtested for the video.

## HALAL VERDICT (first)
Method is instrument-agnostic; as shown it includes shorting
(excluded). Long-only BB/EMA/ATR on halal shares would be compatible
— but see below.

## Overlap with our set
- We ALREADY have a Bollinger book (bollinger-trading/) and the
  S/BB-family campaigns measured BB entries on our market: rejected
  for 10x parameter scatter (the adjacency guardrail exists because
  of them).
- Trend-EMA + ATR stops: tested (atr_stop variants) — never beat the
  champion machinery.
- The 369% headline: single backtest, no controls, no walk-forward,
  no causality audit — the exact failure modes our guardrails exist
  to catch. Meta-lesson identical to the $102k video: Claude
  DISCRETION or Claude ONE-SHOT backtests are not evidence; our
  pipeline (controls, adjacency, both-year, identity gates) is the
  difference between a video number and an adoptable number.

## Experiments
None new — every component already measured on our market.
