# LEGACY-7 — Anatomy of losers -> causal vetoes (R4 + C37F-hf3, honest data)

Date: 2026-10-01. Analyst LEGACY-7 of 15. Analysis-first; nothing fetched, no
existing file edited. Scripts: `plan/lm7_feat.py` (entry-time feature table),
`plan/lm7_veto.py` (anatomy + veto scan), `plan/lm7_rvol.py` (robustness),
`plan/lm7_engine.py` / `plan/lm7_engine2.py` (vetoes inside the R4 engine,
with replacement legs). Intermediate tables live in the session scratchpad
(rebuild: `python plan/lm7_feat.py <out.pkl>`, ~95 s).

## Inputs (honest only)

| line | source | legs | gross $/tkt @ $10k | net @ 15 bps/side ($30 RT) |
|---|---|---:|---:|---:|
| R4 (CHAMPION-REPLAY coil, no stop; RS_DEFER next-print-open fills, gap-through) | `plan/pa_out/cp_r4_legs.json` | 965 (Y1 423 / Y2 542) | +82.5 (Y1 +113.7, Y2 +58.2) | +52.5 |
| C37F-hf3 (live rules ledger, slip 0 = gross) | `data/massive/rotation_trades_C37F_hf3.json` | 1,839 (y2025 826 / year 1,013) | -19.0 | -49.0 |

Every leg normalised to a $10,000 ticket. Y1 = before 2025-08-01.
Features (all causal): read at the last 5-min `cp_feat` grid point strictly
before the fill minute (gap7, gap_open, pm $vol, pm high, pm bars, price,
dvol60, prior range, ret5, shares/mcap, gain_now, coil, hi_gain, session $vol,
VWAP distance, pressure10/30, ORB distance, print density, sigma1, rvol_now,
vol5, minutes since +10% cross, breadth = # names on the live scanner, gain
rank); half-spread (CS/AR, `cp_cost.TapeCost(coef=0)`) and Amihud on the 30
bars before the fill; fill vs prior close; minute of day; same-day sequence
(only legs already exited); 137 CATALYST-MINER columns (`cat_events.features_for`
at the minute before the fill: 8-K items, 424B, S-1/S-3, Form 4 buys/sells,
144, 13D/G, 10-Q, news classes incl. offering/analyst/legal/delisting/earnings).
2,804/2,804 legs matched to the feature grid.

## 1. What the worst 10% look like

Medians, worst 10% / middle 80% / best 10%:

| feature | R4 worst | R4 mid | R4 best | C37F worst | C37F mid | C37F best |
|---|---:|---:|---:|---:|---:|---:|
| cut ($/tkt) | <= -874 | | >= +665 | <= -800 | | >= +428 |
| minute of day of fill | 7 | 22 | 9 | 30 | 75 | 25 |
| half-spread bps | 20 | 10 | 18 | 34 | 16 | 31 |
| Amihud (bps per $1M) | 19,000 | 7,800 | 20,000 | 5,400 | 1,050 | 5,500 |
| sigma1 (1-min vol) | 1.9% | 1.0% | 2.1% | 1.5% | 0.8% | 1.3% |
| market cap | $169M | $268M | $95M | $514M | $795M | $271M |
| dvol60 (prior avg $vol) | 0.33M | 0.81M | 0.21M | 0.38M | 5.1M | 0.30M |
| breadth (# on scanner) | 60 | 79 | 65 | 70 | 108 | 67 |
| min since cross | 5 | 5 | 5 | 10 | 45 | 15 |
| pressure30 | 0.41 | 0.28 | 0.35 | 0.19 | 0.19 | 0.19 |
| gap at open | 6.1% | 4.3% | 5.5% | 8.7% | 4.7% | 9.1% |
| exit reason | trail 59, flatten 38 | | | stop 197/197 (-$800) | | |

**The central finding: the worst decile and the best decile are the same
kind of trade.** Both are small, thin, wide-spread, high-sigma, early
entries on quieter days; the middle 80% is bigger, more liquid, later. Entry-
time information mostly predicts the SIZE of the outcome, not its SIGN — so
almost every "liquidity / volatility / smallness" veto removes winners in the
same proportion as losers (e.g. `dvol60 < $500k` would remove 453 R4 legs worth
**+$85,770** — R4's whole edge lives in the thin names; `dilution_30d` on R4
is +$285/leg in Y1 and -$198 in Y2). C37F's tail is mechanical: every worst-
decile leg is the fixed -8% stop (gap-through), so its losers are a property of
the stop, not of the names. Catalyst flags are rare in the tails (R4: 98% of
worst legs had no news in 18 h; catalysts are present on 2-20% of legs).

## 2. Veto scan (leg level, first order: vetoed leg simply not taken)

Thresholds for continuous features were fitted on **pooled Y1** (both lines),
then read in all four cells; Y2 is the hold-out. 34 features x 6 quantiles =
204 tested rules (+29 flags) — expect several spurious "hits".

Only rules negative in all four cells (R4 Y1 / R4 Y2 / C37F Y1 / C37F Y2):

| veto (causal) | vetoed n | vetoed mean $/tkt | $ saved (= -sum vetoed) |
|---|---|---|---|
| **rvol_now < 0.07** (session $vol so far < 7% of prior-60d avg daily $vol) | 25 / 52 / 37 / 48 | -204 / -184 / -176 / -158 | +5,106 / +9,573 / +6,529 / +7,565 (total +28,772) |
| rvol_now < 0.05 | 17 / 34 / 28 / 27 | -126 / -192 / -151 / -236 | total +19,273 |
| rvol_now < 0.10 | 34 / 80 / 51 / 66 | -126 / -112 / -105 / -115 | total +26,241 |
| rvol_now < 0.15 | | -95 / **+53** / -134 / -73 | breaks in R4 Y2 |
| time-normalised rvol < 0.5 (fixed U-shape volume prior, not fitted) | 25 / 61 / 34 / 44 | -111 / -168 / -238 / -148 | +27,612 |
| Amihud > 2.5e5 | 22 / 26 / 39 / 21 | -201 / -194 / -282 / -88 | +22,306 (but `> 1e5` and `> 5e4` flip positive on R4) |
| 8-K item 5.02 in 3 d | 2 / 5 / 22 / 18 | -672 / -120 / -183 / -216 | +9,856 (tiny n on R4) |
| `rvol07 OR Amihud>2.5e5` | 41 / 74 / 68 / 67 | -179 / -201 / -201 / -110 | +43,259; hits 20/97 R4 worst-decile ($25.2k) vs 8 best-decile ($8.8k forgone); C37F 32/197 worst ($26.9k) vs 15 best ($13.2k) |

Everything else failed the hold-out or one line (e.g. `dvol_now < $59k`
+$36k Y1 -> -$16k Y2; `pm_bars < 2` +$21.8k -> -$24.8k; `gap7 < -2%` C37F Y1
-$180/leg -> Y2 +$87/leg; half-spread > 47 bps: C37F -$100/-$112 but R4
**+$160/+$153** — spread kills C37F's stops, it pays R4's thin-name edge).

### CATALYST-MINER's composite veto on R4 — it does NOT transfer

`ANY_NEG_3d` = 8-K 5.02 | Form-4 sale | analyst headline in 3 d, or 10-Q in 18 h:

| cell | vetoed | vetoed mean | first-order $ |
|---|---:|---:|---:|
| R4 Y1 | 23 (5.4%) | **+97** | -2,241 |
| R4 Y2 | 26 (4.8%) | **+126** | -3,269 |
| C37F Y1 | 70 (8.5%) | -93 | +6,521 |
| C37F Y2 | 142 (14.0%) | -32 | +4,498 |

In the R4 engine (vetoed name replaced by the next pick): **-$26,785 over 444
days (-$1,266/month)**, 965 -> 957 legs, $/tkt +82.5 -> +55.2. The 10-Q
component is the culprit (R4 legs within 18 h of a 10-Q: +$23 Y1 / +$213 Y2).
The +$21/tkt CATALYST-MINER found was on the 191-name WIDE universe at h60;
on +10% gappers fresh filings are often the reason for the move. Only the
8-K 5.02 piece is consistently negative, and on R4 it touches 7 legs
(engine delta -$1,349, i.e. noise).

## 3. The candidates inside the honest R4 engine (with replacement)

`plan/lm7_engine*.py` wraps `cp_sim._try_ticket` in-process (no file edits):
a vetoed (name, decision) is skipped and the engine takes the next ranked name
/ next decision, exactly as live. Gross, $10k-normalised, 444 days.

| R4 variant | legs | $/tkt gross | net @15 bps | total | delta vs R4 (Y1 / Y2) | ex-best-day |
|---|---:|---:|---:|---:|---|---:|
| R4 baseline | 965 | +82.51 | +52.51 | +79,625 | — | +48,681 |
| rvol_now < 0.03 | 976 | +81.14 | +51.14 | +79,189 | -436 (-4,705 / +4,269) | +48,245 |
| rvol_now < 0.05 | 989 | +81.19 | +51.19 | +80,299 | +674 (-3,917 / +4,592) | +49,355 |
| **rvol_now < 0.07** | 1,010 | **+102.38** | **+72.38** | +103,406 | **+23,782 (+6,216 / +17,566)**; boot P>0 0.96; 14/21 months + | +72,463 |
| rvol_now < 0.10 | 1,007 | +90.22 | +60.22 | +90,855 | +11,230 (+6,191 / +5,040); P>0 0.78 | +59,911 |
| rvol_now < 0.15 | 1,029 | +71.76 | +41.76 | +73,837 | -5,788 | +42,893 |
| rvol_now < 0.20 | 1,057 | +73.29 | +43.29 | +77,464 | -2,161 (+8,768 / -10,929) | +46,520 |
| time-norm rvol < 0.5 | 999 | +81.98 | +51.98 | +81,896 | +2,271 | |
| Amihud > 2.5e5 | 983 | +79.79 | +49.79 | +78,434 | -1,191 | |
| rvtn OR Amihud | 1,018 | +81.46 | +51.46 | +82,924 | +3,299 | |
| ANY_NEG_3d (catalyst) | 957 | +55.21 | +25.21 | +52,840 | **-26,785** | |
| 8-K 5.02 3 d | 959 | +81.62 | +51.62 | +78,275 | -1,349 | |
| rvol<0.07 + 8-K 5.02 | 1,004 | +101.84 | +71.84 | +102,252 | +22,627 | +71,308 |

Same rvol<0.07 veto on R4's frame with a RANDOM ordering (10 seeds): mean
delta +$2,236, positive 6/10 (range -12.7k..+23.0k). A matched-rate random
veto (20.5% of attempts) collapses R4 to +$38k ± 17k — the coil edge is in the
top-ranked pick, so ANY veto that skips it must earn its keep.

**Reading.** At the leg level the low-participation veto is the one clean
signal: vetoed legs lose $160-$200 each in all four cells and at every
threshold 0.03-0.10. In the engine the dollar delta is **threshold-chaotic**
(0.05: +$0.7k; 0.07: +$23.8k; 0.10: +$11.2k; 0.15: -$5.8k): each veto re-routes
the rest of the day's sequence, and the path noise (± ~$10-15k / 444 d) is as
large as the effect; the top-3 day deltas at 0.07 (+7.4k, +5.2k, +4.1k) are 70%
of it. Honest expected value: average of the 0.03-0.10 engine deltas ≈
+$8.9k / 444 d ≈ **+$9/tkt book-wide, +$420/month at $10k**, with the
interval spanning zero. Not a proven edge; the cheapest and most causal
candidate on the board.

## TAKEAWAYS

1. **Low-participation veto (test it, live-shadow first).** Rule: *at the
   decision minute, refuse a +10% name whose regular-session dollar volume so
   far is < 7% (band 5-10%) of its own prior-60-day average daily dollar
   volume.* Causal (prior sessions + bars <= decision). Mechanism: a +10%
   print on almost no participation is a quote-driven/thin move with no
   sponsorship; it bleeds into the flatten/trail (R4 legs hit by the
   rvol-or-Amihud veto: 76 flattens at -$288 each) or the stop (C37F: 44 stops at -$780). Expected: ~+$120 per touched ticket
   (~8% of tickets) = ~+$9/tkt book-wide; R4 net @15 bps +$52.5 -> +$51-72/tkt
   across thresholds, **~+$420/month at $10k (engine range -$21 to +$1,125/month)**. Test: put it
   in the authoritative R4/rotation engine as a gate with th in {0.05, 0.07,
   0.10} pre-registered, report the AVERAGE delta across the three and a
   30-seed paired bootstrap of days; ship only if the average is > 0 in both
   years. Cheap to add to live paper as a logged would-veto flag at no cost.
2. **For any fixed-stop gapper line (C37F family), veto extreme illiquidity:
   Amihud(30 bars) > 2.5e5 bps/$1M, or half-spread > ~45 bps.** C37F legs
   with half-spread > 47 bps lose $100-112 each in both years (186 / 114 legs);
   Amihud > 2.5e5 loses $282 / $88. Mechanism: an 8% stop on a name whose 1-min
   bars move 2%+ on thin tape gets gap-through filled. Expected on C37F
   ≈ +$7-14/tkt on the whole book (first order; it stays negative). Do NOT apply to R4
   (no stop): there the same names are its winners (+$153-160/leg).
3. **8-K item 5.02 (officer/director departure) in the last 3 days -> skip.**
   Negative in all four cells (-$120 to -$672/leg, n = 47 total); in R4 it
   touches <1% of legs, so it is a hygiene rule worth ~$0-50/month, not a
   strategy. Zero-cost to add to the live catalyst check.

## DISCARD

- **CATALYST-MINER's ANY_NEG_3d composite on gapper lines**: -$26.8k on R4 in
  the engine (-$1,266/month); the 10-Q-in-18h leg is R4-positive. Keep it only
  for the wide-universe h60 setting it was found on.
- **Size / liquidity / volatility / spread / time-of-day vetoes on R4**
  (dvol60, mcap, sigma1, half-spread, Amihud > 5e4-1e5, pm_bars, dens, early
  minutes): they remove winners and losers together — R4's edge IS the thin
  high-variance name. `dvol60 < $500k` alone would delete +$85.8k.
- **Dilution / 424B / S-3 / offering flags**: sign flips between years or
  lines (dilution_30d R4 +$285 -> -$198; 424B_10d C37F +$64 Y1); n tiny on R4.
- **Sequence vetoes** (stop after a losing leg, no re-entry in the same
  symbol): prior-loss legs are R4's BEST (+$474 Y1); same-symbol re-entry on
  C37F +$27 / -$7 — nothing.
- **gap7 < -2% / pm_high_gain / pressure / VWAP / ORB / breadth thresholds**:
  fitted-Y1 winners that fail Y2 or one line.
- **Random-veto as a control for R4**: misleading (any skip of the top pick
  hurts); compare vetoes to R4 itself with paired day deltas.
