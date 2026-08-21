# Trader-Mimicry Pilot — Backtest/Reconstruction Report (W-campaign Phase 3.4)

**Date:** 2026-08-21 · **Phase:** backtest only, per the approved sequencing (BACKTEST BEFORE LIVE).
**Pre-registration:** `README.md` in this directory, committed BEFORE any data was gathered
(commit 9c61d61). Kill criteria quoted there verbatim from `day-trading/trader-mimicry-survey.md`.
**Firewall:** nothing here touches the C37 ledger. These are someone else's signals under our rules.

## What was reconstructed

| Arm | Window | Sessions | VODs processed | Calls extracted | Extraction quality |
|---|---|---|---|---|---|
| Ross Cameron (recaps) | 2026-08-03 → 08-20 | 13 (+1 no-trade day) | 17 recap videos (all had captions) | 60 distinct entry calls (155 raw events, cross-account/cross-video dupes merged) | All 180 curated quotes audited verbatim vs transcripts, 0 misses |
| TraderTV Live (morning streams) | 2026-08-03 → 08-20 | 14 | 14 morning VODs ~3h each (all had captions) | 120 entry calls (68 long, 52 short) | same audit, 0 misses |
| Madaz | — | 0 | 0 | 0 | arm died at reconstruction (below) |

Method: watch-skill `--transcript-only --no-whisper` (captions-first; no vision model, no VPN).
Zero VODs lacked captions — no coverage gaps from transcription. Coverage gaps that do exist:
Cameron 8/05 session (only a strategy-compilation video that day, excluded); Cameron's live
morning show no longer streams daily on YouTube (his `/streams` tab is specials; daily content
is post-hoc recaps — this matters, see the Cameron verdict).

Clock mapping (TraderTV): stream `release_timestamp` + VOD offset; validated against the 9:30
opening-bell countdown in the 8/19 VOD ("with only 10 seconds to go" at offset 90:38 vs predicted
bell at 90:51) — agreement within ~3 s. Every Cameron session date was verified empirically:
each traded ticker appears in that date's Polygon grouped-daily top-gainer list (all 13/13 dates).
Garbled caption tickers resolved the same way (HuZ/HYZ/HIZ → **HUIZ**, +118% on 8/20; "Jwell" →
JWEL; "DRAM" and SPCX confirmed as real listed instruments). One unresolvable: "SPRC" (8/12) shows
no move on the tape — excluded, flagged in `cameron/calls.json`.

Timestamp standard (pre-registered, binding): recap calls count only with a stated clock time.
Cameron result: **6 of 60 calls timeable** (10%) — SGLY 8/20 7:00, GNPX 8/18 7:05, MB 8/07 7:05,
CLRO 8/07 7:00, NAMI 8/07 8:20, CLRO 8/06 7:01. The other 54 are logged `untimed` and were still
halal-gated, but excluded from decay/sim per the registration. TraderTV: all 120 calls are
`timed-live` via the stream clock.

Simulation: **explicit replay** (documented choice — `simulate_trades` entries are
pattern-triggered; mimic entries are exogenous timestamps). $15k ticket at the +60 s mark
(`p60` = Open of first bar ≥ call+60 s), −8% stop, 20% trail, 15:00 ET flatten, shown raw and at
10 bps/side. Marks per the pre-registered p0/p60/p300 convention.

---

## Arm 1: Ross Cameron — calibration arm → **KILL (all three criteria)**

| Metric | Value | Kill bar | Verdict |
|---|---|---|---|
| Halal-passing timed calls/week | 2 in 2.6 wk = **0.77/wk** | < 2/wk kills | **HIT** |
| +60 s edge after costs | both PASS sims stopped −8% (−$1,199.60, −$1,199.83); −$2,457 total at 10 bps | ≤ 0 kills | **HIT** |
| Scanner overlap (timed calls) | **100%** (6/6 crossed +10% ≤ 14:00; 5/6 crossed BEFORE his call) | > 80% kills | **HIT** |

Verdict distribution, all 60 calls: 47 FAIL / 7 PASS / 5 CANNOT-VERIFY / 1 unresolved.
Unique tickers 29: **2 PASS** (CLRO, RDAC), 24 FAIL, 2 CANNOT-VERIFY. Survey estimated 10–25%
pass-rate; measured 11.7% by call. The gate killed every monster exactly as repo history predicts:
GNPX cash/mcap 557%, NAMI combined 832%, HUIZ (insurance industry), SGLY debt/mcap 114%.

Signal decay (timed calls, n=6): d60 median **+2.33%**, d300 median **+12.53%**. His premarket
gappers keep running — but +60 s of latency costs ~2.3% on entry, and under our −8% stop that
entry tax converts winners into stop-outs: both halal-passing entries (CLRO 8/06, 8/07) stopped
out within 2–3 minutes. The two big would-be winners (GNPX +$2,872, NAMI +$2,486 in sim) are both
gate-FAILs. Nothing survives the stack of gate + latency + our stops.

Calibration answer (the arm's actual question): our scanner already sees everything he trades
(100% overlap, mostly before he acts), so following him adds **zero discovery** and negative
execution. The C37 pipeline IS this workflow, minus his discretionary exits, minus his latency
advantage. There is also a structural finding: **his daily YouTube output is post-hoc recaps, not
the live stream** — only 10% of recap calls are timeable at all, so even a better backtest cannot
be built from this channel, and live-mimicry would require a feed that no longer exists publicly.

## Arm 2: TraderTV Live — universe-widening arm → **KILL (criterion 2), with a salvage finding**

Primary window per the approved pilot roster is 9:30–11:00; full-morning numbers shown too
(they are near-identical — 66 vs 68 counted longs, same 27 PASS sims):

| Metric | 9:30–11:00 | All morning | Kill bar | Verdict |
|---|---|---|---|---|
| Halal-passing long calls/week | 27 in 2.8 wk = **9.6/wk** | 9.6/wk | < 2/wk kills | survives |
| +60 s edge after costs | 27 sims: −$2,238 raw, **−$3,042 at 10 bps** (−$113/trade, 11W/16L) | same | ≤ 0 kills | **HIT** |
| Scanner overlap | **18–19%** (cross-before-call 15–16%) | 19.1% | > 80% kills | survives |

Verdict distribution (68 counted longs): 27 PASS / 24 FAIL / 17 NO-DATA. The NO-DATA block is
their ETF habit — IBIT, SLV, TQQQ, NVDL, "DRAM" — 25% of the long feed is instruments with no
fundamentals to screen, which the gate refuses by design (leveraged ETFs are margin-like anyway).
Of the screenable names the pass-rate is 27/51 = **53%** — squarely inside the survey's 40–60%
estimate, and the halal-friendliest feed surveyed, as predicted.

Signal decay (n=68 longs): d60 median **+0.04%**, d300 median **+0.10%**. No latency tax on
large caps — mimicry is *executable* here, there is just nothing to harvest at the entry: their
edge lives in scalped exits and reloads, which "our everything else" deliberately does not copy.
25 of 27 PASS sims exited at the 15:00 flatten (2 stops) — our −8%/20%-trail machinery, tuned for
+100% gappers, essentially never engages on a −0.5%…+1% large-cap drift. Best sim PLTR 8/04
+$1,140; worst RIOT 8/11 −$1,199 (stop). Sequential one-position replay: 12 trades, −$228.
The gate also removed this feed's monsters: both MRNA longs on the +180% cancer-data day
(sim +$3,788 and +$4,481) FAIL on interest income ≥5%; SPCX, their most-traded name, is
industry-blocked (aerospace/defense).

**Salvage finding (pre-registered expected outcome §5.8 of the survey, confirmed):** 81% of their
halal-passing names never crossed our +10% scanner — TraderTV genuinely widens the halal universe
(NVDA, AAPL, PLTR, INTC, AMZN, RIOT, BMNR, KLAR days). What it does not provide is an entry edge
our machinery can capture. If anything graduates from this pilot it is *attention* (a large-cap
news-name feed as scanner input for a future, differently-exited strategy), not entry mimicry.
That would be a new campaign with its own design — NOT a continuation of this arm.

## Arm 3: Madaz — backtest-only arm → **KILL at reconstruction (arm unreconstructable)**

Three public access paths probed 2026-08-21, all dead inside our guardrails (no logins/signups):
X `@madaznfootballr` returns HTTP 402 without auth (and the syndication endpoint is empty);
YouTube `@madaztrader` is dormant — newest upload 2021-03-12 (GME era), zero VODs within years of
the window; `madazmoney.com/highlights` requires a TradeData account login. Zero timestampable
public calls exist. The survey rated real-time following "infeasible" and the archive "moderate";
reality is worse — there is no free archive at all in 2026. Evidence in `madaz/vods.json`.

---

## Pilot verdict

**All three arms KILLED at the backtest gate. No arm graduates to live paper mimicry.**

| Arm | Kill reason(s) |
|---|---|
| Cameron | <2 passing calls/wk AND no +60s edge after costs AND 100% scanner overlap; recap channel only 10% timeable |
| TraderTV | +60 s entry edge ≤ 0 after slippage under our exit rules (calls/wk and overlap criteria survived) |
| Madaz | no public reconstructable archive within guardrails |

The survey's up-front prediction (§5.8) was exact: mimicry adds *attention*, not *entries*. The
one non-obvious asset produced: a measured, halal-gated large-cap news-name universe from the
TraderTV feed (27 passing names/3 wk at 19% scanner overlap) — parked as a possible future
scanner-input experiment, separate campaign, separate pre-registration.

## Files

- `README.md` — pre-registration (protocol, kill criteria, firewall)
- `<arm>/vods.json` — every VOD processed/skipped, with stream-start clocks
- `<arm>/calls.json` — curated call ledger (verbatim quotes; dropped-duplicate log included)
- `<arm>/calls_priced.json` — halal verdict + p0/p60/p300 + scanner-cross + sim per call
- `<arm>/summary.json` — pre-registered metrics; `halal_verdicts.json` — per-ticker gate output
- Transcripts + extraction intermediates: session scratchpad (not repo material); every quote
  re-verifiable from public VODs via the URLs in `vods.json`

## Honest limitations

1. Halal verdicts are TODAY'S screen applied retroactively (disclosed in the pre-registration;
   acceptable at 2–4 weeks lookback, would not be for a multi-year backtest).
2. Cameron timed-call sample is n=6 — the precision finding (10% timeable) is robust, the decay
   numbers on n=6 are indicative only. This weakens measurement of the arm but not the verdict:
   all three kill criteria would each kill it alone.
3. TraderTV speaker attribution is imperfect (multi-trader desk, no diarization) — a few calls may
   attribute to the wrong trader; ticker/side/time are transcript-verified regardless.
4. Two TTV rows (IBIT 8/03, 8/07-first-long) are in-position confirmations: entry time ≤ callout
   time. For mimicry the callout IS the actionable moment, so marks are computed there — this is
   the honest mimic assumption, not their fill.
5. The 20% trail / −8% stop machinery was never re-tuned for large caps — deliberately (the pilot
   measures THEIR entries under OUR rules, not a new strategy). The TTV kill is therefore a kill
   of "their entries + our exits", which is precisely the question Phase 3.4 asked.
