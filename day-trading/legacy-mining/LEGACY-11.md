# LEGACY-11: the pressure metric, measured on honest data

Pressure = `Candles.pressure`: volume-weighted close location over the last n printed bars,
`sum v*(2(c-l)-(h-l))/(h-l) / sum v`, in [-1,1], with None (untrusted) below 20k shares.
The champions used it three ways: (1) as a ranking key (coil bucket, then P30), (2) to set the
trail width (P10 <= -0.3 gives a 10% trail, P10 >= +0.3 gives 40%, otherwise none) via `pressure_trail=(10,.3,.3,10,40)`,
and (3) as a pressure-flip exit.

**Frame (honest):** `cp_panel`, 466 sessions (2024-10-22 to 2026-08). Universe = names whose regular-session
CLOSE has crossed +10% by minute m (the live-scanner rule; coverage is complete per `cp_lib`),
price >= $2, NASDAQ test symbols removed, reverse-split artefacts removed (first RTH open > 3x prev close). Every feature uses bars <= m. Every
forward return starts at the **open of bar m+1**, so the close-location bounce is excluded. Stops
fill at `min(stop, open)`, which is honest when the price gaps through. t-stats are clustered by day, and Y1/Y2 are the two halves of the sample.
Scripts: `plan/lm11_pressure.py` (panel pass), `lm11_analyze.py`, `lm11_fixA.py`, `lm11_stateC.py`,
`lm11_exit2.py`, `lm11_exit3.py`, `lm11_an2.py`. All saved outputs are in the session scratchpad. They are reproducible in about 15 minutes per pass.

## A. What pressure predicts (1.85M name-minutes, 09:45-14:30 every 5 min)

**Direction: almost nothing, and the sign is slightly backwards.** Cross-sectional rank IC, day-clustered:

| feature | f1 | f5 | f15 | f30 |
|---|---|---|---|---|
| P30 | +0.003 (t+3.7) | -0.007 (t-8.1) | -0.011 (t-8.0) | -0.012 (t-7.3) |
| P10 | -0.004 | -0.015 (t-14.5) | -0.014 | -0.015 (t-10.9) |
| P30 after removing ret30 | +0.007 | +0.004 | +0.003 | +0.003 (t+2.1) |
| ret5 (reference) | -0.016 | -0.037 | -0.032 | -0.026 |

- Raw pressure mostly stands in for recent return, and recent return **mean-reverts** on this universe (ret5 IC -0.03).
  Once ret30 is removed, the P30 effect that remains is +0.003. The break-even IC from the CP study is 0.188, so this is about 60x too small.
- Pooled buckets: the spread in mean forward 30-min return across all five P30 buckets is about **4 bps**, with the
  neutral bucket worst (-4.4 bps) and both extremes about -1 bps. The round-trip cost is 30 bps.
- **Continuation does not exist.** Splitting names into terciles by ret30, the f30 difference between P30 >= +0.3 and P30 <= -0.3 is
  +2.6 bps (t 0.6) in the down tercile, +0.7 (t 0.3) in the middle, and -3.7 (t -0.6) in the up tercile. A trend that is already
  under way is **not** extended by buying pressure.
- **Volatility is the one thing it forecasts.** The IC of **|P30|** against forward range30 divided by past range30 is **-0.090 (t -62, Y1 -0.086 / Y2 -0.094)**. A one-sided
  tape (either sign) is followed by **contracting** range, and a balanced tape (P near 0) by expanding range. Pooled forward
  30-min range: 347-413 bps in the extreme buckets versus 433 bps at P near 0. This is a real and stable volatility signal. It is not a direction signal.

## B. Pressure as an EXIT (63,775 first RTH +10% close-crosses; enter at next open, flatten 14:59)

Gross $/trade at a $10k ticket. Every rule pays the same single round trip, so net = gross - $30 at 15 bps/side.

| rule | ALL Δ vs hold | liquid (dv30 >= $1M) Δ | thin (< $1M) Δ |
|---|---|---|---|
| hold (base) | -$10.1 | -$20.5 | +$0.8 |
| plain 10% trail from high (T10) | **+9.3** (t2.7) | **+19.8** (t3.8) | -2.0 |
| champion PT (10% if P<=-.3, 40% if >=+.3) | +4.4 | – | – |
| 10% trail armed ONLY while P10<=-.3 (T10N) | +4.2 | **+0.9** | +7.7 (t3.0) |
| 10% trail SUSPENDED while P10<=-.3 (T10S) | +9.1 | +19.8 | -2.2 |
| PT inverted (10% when P>=+.3) | +7.7 | – | – |
| pressure flip P10<=-.3, next open (PF10) | +1.7 | – | – |
| same delay distribution, random times (20 perms) | +2.1 (-$8.0 vs PF10 -$8.4) | – | – |
| flip only in profit >5% (champion 'profit' mode) | -1.5 | – | – |
| +10% target, close-based (TP10) | +16.8 | +10.6 | +23.3 |
| TP10, skipped while P10<=-.3 (TP10P) | +16.7 | +10.5 | +23.4 |
| TP10 fired ONLY when P10<=-.3 (control) | -0.3 | -9.9 | +9.9 |
| **TP5 + T10 (no pressure)** | +11.6 | **+24.2 (t4.5, 20/23 months, Y1 +37 / Y2 +14, ex-top10 +21.8)** | -1.7 |

Reading:
1. **The pressure trail's leg adds nothing on liquid names.** The champion's "10% only when P10 <= -0.3" is worth
   +$0.9/trade where the plain unconditional 10% trail is worth +$19.8. The conditioning removes 95% of the trail's value.
   This matches the XH finding: once phantom fills were repriced, the "only positive exit" turned out to be fill-model fiction.
2. **The flip exit equals a random exit with the same timing.** PF10 -$8.4 vs control -$8.0 [-13.6..-3.6]. Its median exit
   comes 36 bars in, against a median hold of 285.
3. **Pressure gating of targets is a no-op.** TP10P and TP10 agree within $0.1, because at the moment a target is hit the tape is
   almost never at P10 <= -0.3. The inverse control (sell only into a washout) is clearly worse in every cut.
4. The one place pressure acts as a switch is **thin names (< $1M dollar volume over the prior 30 minutes)**. There, arming the trail only on a sell-tape beats the plain trail
   (+7.7 vs -2.0, t 3.0, 15/23 months), because plain trails get wicked out on thin prints. But even the best thin
   rule (TP15/TP25 at +$29-31 gross) lands at or below zero once you pay the >= 30 bps/side those names actually cost.

## C. The strongest pressure fact: held winners that are being sold keep their drift

This section takes held-position states every 5 printed bars and measures the return from the next open to 14:59. The units are bps, by P10 decile. Y1 and Y2 are shown in brackets.

- Position more than 5% above entry: the lowest decile (P10 < -0.30) gives **+25.3 (+25.0/+25.5)**. Deciles 3-9 give -26 to -48.
- Position more than 15% above entry: the lowest decile gives **-3.9**. Every other decile gives **-68 to -150** (both halves).
- Across all states, the difference between negative pressure and the rest is +18 bps (t 6.9). In deep drawdowns (more than 10% off the peak) it is +51 bps (t 5.3).

So a negative-pressure tape on a stock that is already up is **a washout that recovers, not the start of a reversal**.
That is the opposite of the champions' logic, and it explains why the inverted controls (TC20 in 2026-08, PTinv here)
keep beating the real rules. Being extended is what predicts the giveback. Pressure only tells you when **not**
to sell. Because targets almost never trigger during a washout (B3), this does not convert into trade-level dollars.

## TAKEAWAYS

1. **Drop pressure from the exit logic and keep a plain trail plus a small target, applied to liquid names only.**
   Rule: after entry, exit at next open on the first close >= entry x 1.05. Otherwise hold a stop at 0.90 x (highest high since entry),
   filled at min(stop, open). Flatten at 14:59. Apply this only when dollar volume over the prior 30 minutes is >= $1M.
   Measured on 32,825 honest liquid crosses: **+$24.2/trade vs hold (t 4.5, 20/23 months, both halves positive,
   ex-top-10 +$21.8)**. It is an add-on to whatever entry you use, not an entry on its own. On this all-crossers entry the result is still
   +$3.8 gross, which is **-$26/trade net at 15 bps/side**. At 1-2 trades/day under the one-position rule, it is worth about +$500-1,000/month
   relative to holding, on top of any entry with a positive edge.
   Test: run it as the exit on the current live candidate's own entry legs (`cp_r4_legs.json`/RS_CROSS harness), with a
   30-seed random-entry control, and check that the Δ vs hold survives at that entry's sample size.
2. **If pressure is kept at all, keep it only as a "don't sell into a washout" veto, and only on thin names.** Rule: on
   names with dv30 < $1M, arm the 10% trail only while P10 <= -0.3 (the champion's leg, without the 40% leg). This gives +$7.7 vs
   the plain trail's -$2.0 (t 3.0). It is net-negative at thin-name costs, so treat it as a damage limiter, not a profit source.
   Test: the same harness restricted to thin legs, priced with the measured `cp_cost` toll.
3. **Use |pressure| as a volatility forecast, not a direction forecast.** A balanced tape (|P30| < 0.1) is followed by about 5-25% more
   forward range than a one-sided tape (IC -0.09, t -62). That is causal and stable. It could set trail width or
   size (wider stop and smaller size when |P| is near 0), or pick which names a breakout/target rule should watch. Expected $ is
   unknown. Test: re-run TP5+T10 with the trail width set by the |P30| tercile, comparing the 20 Δ$ against fixed 10% on the liquid set.

## DISCARD

- Pressure as a **ranking key** (champion IC -0.043; "rank: pressure only" -$78/tkt; IC +0.003 after removing ret30).
- Pressure as a **continuation/trend-confirmation** signal (no effect in any ret30 tercile).
- The **pressure flip exit** in any mode (PF10 equals a random-time exit; profit mode -$1.5; P30 flip -$0.1).
- The **10%/40% pressure-modulated trail** (its 10% leg alone is worth +$0.9 vs +$19.8 for a plain 10% trail on liquid names; the 40% leg adds +$0.3 overall: PT +4.4 vs PT10only +4.2).
- **Pressure-conditioned time stops and pressure sizing** (already rejected: TC20 inverted control won; S018 showed sizing is leverage, not signal).
