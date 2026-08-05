import io, json
from pathlib import Path

parts = json.loads(Path("data/massive/_rebuild_parts.json").read_text())

STYLE = """<title>Trading Campaigns — Best Results</title>
<style>
  :root{--paper:#fafaf7; --ink:#1c2420; --muted:#6b7370; --grid:#dcdbd0;
    --head:#eeede4; --band:#f3f2ea; --accent:#0e6b4f; --gain:#167a52;
    --gain-ink:#0d5c3d; --loss:#b3382e; --chipbg:#e8efe9; --goldbg:#f5eed3;}
  @media (prefers-color-scheme: dark){:root{--paper:#141816; --ink:#e6e4d9;
    --muted:#93998f; --grid:#2c322e; --head:#1d2320; --band:#191e1b;
    --accent:#4fc394; --gain:#57c795; --gain-ink:#6fd3a6; --loss:#e07b6d;
    --chipbg:#1e2a24; --goldbg:#2d2716;}}
  :root[data-theme="dark"]{--paper:#141816; --ink:#e6e4d9; --muted:#93998f;
    --grid:#2c322e; --head:#1d2320; --band:#191e1b; --accent:#4fc394;
    --gain:#57c795; --gain-ink:#6fd3a6; --loss:#e07b6d; --chipbg:#1e2a24;
    --goldbg:#2d2716;}
  :root[data-theme="light"]{--paper:#fafaf7; --ink:#1c2420; --muted:#6b7370;
    --grid:#dcdbd0; --head:#eeede4; --band:#f3f2ea; --accent:#0e6b4f;
    --gain:#167a52; --gain-ink:#0d5c3d; --loss:#b3382e; --chipbg:#e8efe9;
    --goldbg:#f5eed3;}
  body{background:var(--paper); color:var(--ink);
    font:15px/1.5 "Segoe UI", system-ui, sans-serif; margin:0;
    padding:2.2rem 1.4rem 3.5rem;}
  .wrap{max-width:1180px; margin:0 auto; display:flex; flex-direction:column; gap:2rem;}
  header h1{font-size:1.45rem; font-weight:650; margin:0 0 .2rem; text-wrap:balance;}
  header p{margin:0; color:var(--muted); max-width:78ch;}
  .stats{display:flex; flex-wrap:wrap; gap:.8rem; margin-top:1.1rem;}
  .chip{background:var(--chipbg); border:1px solid var(--grid); border-radius:6px; padding:.55rem .95rem;}
  .chip .l{font-size:.68rem; text-transform:uppercase; letter-spacing:.09em; color:var(--muted);}
  .chip .v{font-size:1.25rem; font-weight:650; font-variant-numeric:tabular-nums; color:var(--gain-ink);}
  h2{font-size:1.02rem; font-weight:650; margin:0 0 .6rem;}
  .scroll{overflow-x:auto; border:1px solid var(--grid); border-radius:6px;}
  table{border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; white-space:nowrap;}
  th,td{border:1px solid var(--grid); padding:.34rem .6rem; font-size:.85rem; text-align:right;}
  th{background:var(--head); font-weight:600;}
  td.l, th.l{text-align:left;}
  tbody tr:nth-child(even) td{background:var(--band);}
  td.pos{color:var(--gain-ink);}
  td.neg{color:var(--loss); font-weight:600;}
  tr.champ td{background:var(--goldbg) !important; font-weight:650;}
  tfoot td{background:var(--head) !important; font-weight:700;}
  .note{color:var(--muted); font-size:.82rem; max-width:90ch; margin:.55rem 0 0;}
  .divider{border-left:3px double var(--muted) !important;}
  td.rl{text-align:left; white-space:normal;}
  td.stage{color:var(--accent); font-weight:650; font-size:.72rem; text-transform:uppercase; letter-spacing:.07em;}
</style>
"""

RULES = """<section>
  <h2>The rulebook of champion C21 (one line each; ⭐ = C21-era additions)</h2>
  <div class="scroll"><table><tbody>
    <tr><td>1</td><td class="stage">Universe</td><td class="rl">Any US common stock ≥ $2 — no upper price cap (no warrants/units/rights/preferred/ETFs)</td></tr>
    <tr><td>2</td><td class="stage">Universe</td><td class="rl">Symbol must have ≥ 50 prior trading sessions of history</td></tr>
    <tr><td>3</td><td class="stage">Qualify</td><td class="rl">Day's high ≥ +10% over previous close (gap or intraday gain both count)</td></tr>
    <tr><td>4</td><td class="stage">Qualify</td><td class="rl">Day's volume ≥ 5× its trailing 50-session average</td></tr>
    <tr><td>5</td><td class="stage">Qualify</td><td class="rl">Rank the day's qualifiers by gain; consider only the top 8</td></tr>
    <tr><td>6</td><td class="stage">Gate</td><td class="rl">Candidate needs ≥ 20 one-minute bars in the window</td></tr>
    <tr><td>7</td><td class="stage">Gate</td><td class="rl">Skip if already up more than +20% at 7:00 AM vs previous close (calm-gap)</td></tr>
    <tr><td>8</td><td class="stage">Gate</td><td class="rl">Halal point-in-time: clean industry; loans/mcap ≤ 10%; cash/mcap ≤ 10%; combined ≤ 20%; haram revenue &lt; 5%</td></tr>
    <tr><td>9</td><td class="stage">Trade</td><td class="rl">One stock/day, $15,000, 7AM–NOON ET, everything sold by noon, nothing overnight</td></tr>
    <tr><td>10</td><td class="stage">Trade</td><td class="rl">Enter on 5-minute opening-range breakout or bullish candlestick pattern</td></tr>
    <tr><td>11</td><td class="stage">Trade</td><td class="rl">Extra trigger: one-shot stop-buy on a break of the premarket high</td></tr>
    <tr><td>12</td><td class="stage">Trade</td><td class="rl">Enter only while price ≥ +10% above previous close at the moment of entry</td></tr>
    <tr><td>13</td><td class="stage">Trade</td><td class="rl">Position ≤ 20% of trailing 10-minute volume</td></tr>
    <tr><td>14</td><td class="stage">Exit</td><td class="rl">⭐ Sell ⅓ at +25% — UNLESS 10-min buy pressure ≥ +0.3 (keep riding while buyers dominate)</td></tr>
    <tr><td>15</td><td class="stage">Exit</td><td class="rl">⭐ Pressure-modulated trail: 20% base; TIGHTEN to 10% when sell pressure ≤ −0.3; WIDEN to 40% when buy pressure ≥ +0.3</td></tr>
    <tr><td>16</td><td class="stage">Exit</td><td class="rl">Hard stop −8% from entry</td></tr>
    <tr><td>17</td><td class="stage">Hygiene</td><td class="rl">⭐ Ignore lone one-bar wicks &gt; 3× surrounding closes in peak/scale/trail tracking</td></tr>
  </tbody></table></div>
</section>"""

DIFFS = """<section>
  <h2>How other configs differ from champion C21 (one rule per line)</h2>
  <div class="scroll"><table>
    <thead><tr><th class="l">Config</th><th class="l">Differences vs C21</th></tr></thead>
    <tbody>
    <tr><td class="l">C20</td><td class="rl">Rule 14: always banks the ⅓ at +25% (no pressure skip)</td></tr>
    <tr><td class="l">C10</td><td class="rl">Rule 14: always banks ⅓<br>Rule 15: trail widths 12%/30% (older, milder)<br>Rule 17: no wick guard</td></tr>
    <tr><td class="l">C11 (withdrawn)</td><td class="rl">= C10 + exits allowed to 1PM — window extension withdrawn by user</td></tr>
    <tr><td class="l">C02</td><td class="rl">Rule 14: always banks ⅓<br>Rule 15: fixed 20% trail (no pressure modulation)<br>Rule 17: no wick guard</td></tr>
    <tr><td class="l">AX20</td><td class="rl">All of C02's diffs, plus:<br>Rule 10: 15-minute opening range (slower)<br>Rule 11: no premarket-high trigger<br>Rule 13: size ≤ 10% of 5-minute volume</td></tr>
    <tr><td class="l">C04 / X086</td><td class="rl">Rule 13 DELETED — size uncapped (theoretical ceilings; fill-realism caveat, never adoptable)</td></tr>
    <tr><td class="l">C22 / C07</td><td class="rl">Identical rules to C21 / C02 + a 10bps-per-side trading-cost assumption (stress tests)</td></tr>
    <tr><td class="l">C03</td><td class="rl">Rule 5: top-8 pool re-ordered by premarket dollar volume (causal rank)</td></tr>
  </tbody></table></div>
</section>"""

ANATOMY = """<section>
  <h2>Win anatomy — what the rules can't show (C11: 2,839 positions; AX20: 2,235)</h2>
  <div class="scroll"><table>
    <thead><tr><th>#</th><th class="l">Finding</th><th class="l">Evidence</th></tr></thead>
    <tbody>
    <tr><td>1</td><td class="rl"><b>Monsters are the whole business</b></td><td class="rl">~10% of days = 45–47% of all profit; days ≥$5k = 82%; the rest net ≈ zero</td></tr>
    <tr><td>2</td><td class="rl"><b>Golden hour = the 9:30 open</b></td><td class="rl">9–10AM entries avg +$567/position; post-noon entries were churn — now excluded by the strict window</td></tr>
    <tr><td>3</td><td class="rl"><b>Gap sweet spot is 10–20%, not calm</b></td><td class="rl">Richest band in both configs (+$5,325/day); −5..0% is the worst; calmer-is-better is false below the ceiling</td></tr>
    <tr><td>4</td><td class="rl"><b>Rank carries everything</b></td><td class="rl">Ranks 0–2 = $762k of $927k; walk-3 test confirmed the tail is still worth ~$165k — keep walk-8</td></tr>
    <tr><td>5</td><td class="rl"><b>Re-entry grinder</b></td><td class="rl">Per-position edge decays (+$1,141 → +$137) but the 4th+ tail = 31% of profit; monster days are 12–25-position ladders</td></tr>
    <tr><td>6</td><td class="rl"><b>Forced-close truncation</b></td><td class="rl">73–79% of winners still holding at the flatten at every window tried; user kept noon — C21's smarter trail recovered ~98% of the tested 1PM premium instead</td></tr>
    <tr><td>7</td><td class="rl"><b>Pressure belongs in exits</b></td><td class="rl">Entry pressure gates catastrophic (−$450k+); the pressure TRAIL wins; shuffled control −$114k proves the signal is real</td></tr>
    <tr><td>8</td><td class="rl"><b>Description ≠ rule</b></td><td class="rl">Post-hoc picks died on contact: drop-worst-gap-band −$121k, rvol-boost −$47k</td></tr>
    <tr><td>9</td><td class="rl"><b>Threshold geometry</b></td><td class="rl">Trail threshold 0.30 sits at the curve peak with a cliff above (0.45 = −$52k); scale-skip threshold flat 0.15–0.45</td></tr>
    <tr><td>10</td><td class="rl"><b>Phantom wicks are real</b></td><td class="rl">One CIIT minute printed 50× and faked +$334k in wide-gate rows; the 3× wick guard costs $0.00 and immunizes everything</td></tr>
  </tbody></table></div>
  <p class="note">C21 timing profile (both years, 270 traded days): first buy of the day median 9:00 AM
  (IQR 7:50–10:02); all buys median 10:05 AM; median hold 9 minutes per position; 236 of 270 days end on
  the noon flatten. Typical buy happens at +52% above the previous close (IQR +27%..+98%); winning
  positions exit at median +5.3% above entry (mean +11.3%; the top-50 winners average +68%) — many small
  wins funding a few enormous rides.</p>
</section>"""

DEAD = """<section>
  <h2>What lost — the map of dead ends (196 experiments)</h2>
  <div class="scroll"><table><thead><tr><th class="l">Family</th><th class="l">Verdict</th></tr></thead><tbody>
    <tr><td class="l">Mild-gapper bands (10–25%)</td><td class="rl neg">Catastrophic — the alpha lives in the big movers</td></tr>
    <tr><td class="l">Trade caps, early cutoffs, tight stops</td><td class="rl neg">All negative — never cap the re-entry stream or cut runners early</td></tr>
    <tr><td class="l">Calm-gap removal / wide gates</td><td class="rl neg">Y1 mirage, Y2 loss (one 50× data-glitch day faked the sweep)</td></tr>
    <tr><td class="l">Pressure entry gates</td><td class="rl neg">−$450k+ — breakouts fire before pressure turns</td></tr>
    <tr><td class="l">Capital recycling / earliest-entry picking</td><td class="rl neg">Displaces the top pick's own re-entries / collapses pick quality</td></tr>
    <tr><td class="l">Alternative rankings (rvol, blends, turnover)</td><td class="rl neg">Simple gain ranking is near-optimal</td></tr>
  </tbody></table></div>
</section>"""

THEAD = (
    '      <tr><th class="l" rowspan="2">Config</th>\n'
    '        <th colspan="9" style="text-align:center">AVERAGE PER YEAR · (Y1 + Y2) / 2</th>\n'
    '        <th class="divider" colspan="9" style="text-align:center">Year 1 · Aug 25 – Jul 26 (yearly | per month)</th>\n'
    '        <th class="divider" colspan="9" style="text-align:center">Year 2 · Oct 24 – Jul 25 (yearly | per month)</th>\n'
    '        <th class="divider" colspan="5" style="text-align:center">RISK (Y1 → Y2)</th></tr>\n'
    '      <tr><th>Tot Avg /day</th><th>Tot Trades</th><th>Tot Prof</th><th>Tot Loss</th>'
    '<th>Tot P&amp;L</th><th>% Tot Avg /day</th><th>% Tot Prof</th><th>% Tot Loss</th><th>% Tot P&amp;L</th>'
    '<th class="divider">P&amp;L</th><th>Profits / Losses</th><th>Avg /day</th><th>Trades</th><th>Neg trades</th>'
    '<th>% P&amp;L</th><th>% Profits / Losses</th><th>Profits / Losses /mo</th><th>% gain /mo</th>'
    '<th class="divider">P&amp;L</th><th>Profits / Losses</th><th>Avg /day</th><th>Trades</th><th>Neg trades</th>'
    '<th>% P&amp;L</th><th>% Profits / Losses</th><th>Profits / Losses /mo</th><th>% gain /mo</th>'
    '<th class="divider">Win %</th><th>Profit factor</th><th>Max DD</th><th>Best / Worst day</th>'
    '<th>Max lose streak</th></tr>')

html = (STYLE + '\n<div class="wrap">\n<header>\n'
  '  <h1>X100 + X200 + X300 — 196 Experiments, Champion C21 (strict noon)</h1>\n'
  '  <p>Every experiment changes exactly one thing, runs on both backtest years, and must beat\n'
  '     shuffled/random control noise to count. Constraints never touched: $15k max at risk, same-day\n'
  '     close, halal (point-in-time), 7AM–noon ET.</p>\n'
  '  <div class="stats">\n'
  '    <div class="chip"><div class="l">Champion C21 — Y1</div><div class="v">+$395,243</div></div>\n'
  '    <div class="chip"><div class="l">C21 — Y2</div><div class="v">+$519,641</div></div>\n'
  '    <div class="chip"><div class="l">Negative months (22)</div><div class="v">0</div></div>\n'
  '    <div class="chip"><div class="l">Avg per trading day</div><div class="v">+22.6% of $15k</div></div>\n'
  '  </div>\n</header>\n\n<section>\n'
  '  <h2>Full P&amp;L breakdown — sorted by Tot Avg/day = (Prof − Loss) / Trades</h2>\n'
  '  <div class="scroll">\n  <table>\n    <thead>\n' + THEAD + '\n    </thead>\n    <tbody>\n'
  + parts["table1"] + '\n    </tbody>\n  </table>\n  </div>\n'
  '  <p class="note">All % on the fixed $15,000 working capital. "Tot" columns are per-year averages;\n'
  '  Tot Avg/day = (Tot Prof − Tot Loss) ÷ Tot Trades. C04/X086 assume uncapped fills (ceilings, not\n'
  '  adoptable). Risk cells read Year 1 → Year 2.</p>\n</section>\n\n<section>\n'
  '  <h2>Monthly P&amp;L — every config, every month</h2>\n'
  + parts["g1"] + '\n' + parts["g2"] + '\n'
  '  <p class="note">Red cells are losing months. C21 has none in either year.</p>\n</section>\n\n'
  + RULES + '\n\n' + DIFFS + '\n\n' + ANATOMY + '\n\n' + DEAD + '\n</div>\n')

out = Path(r"C:\Users\MYPC~1\AppData\Local\Temp\claude\C--cornell-stocks-automation\20a29bc8-aa0d-497e-a600-4db3499b8240\scratchpad\x100-results.html")
out.write_text(html, encoding="utf-8")
print("rebuilt:", len(html), "chars")
