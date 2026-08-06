# -*- coding: utf-8 -*-
"""Artifact v2: champion C23 (1PM window) + E01 earnings book.
Run from repo root. Reads _rebuild_parts.json (v1 table/grids) and the
C23 day dumps; performs string surgery + adds new sections."""
import io, json, re
from pathlib import Path

REPO = Path(r"C:\cornell\stocks-automation")
parts = json.loads((REPO / "day-trading/data/massive/_rebuild_parts.json")
                   .read_text(encoding="utf-8"))

# ---------- C23 metrics from per-day dumps ----------
def load_days(label):
    return json.loads((REPO / f"day-trading/data/massive/x100_days_C23_{label}.json").read_text())

def year_metrics(label, months_n):
    days = load_days(label)
    pnl = [d["pnl"] for d in days]
    tot = sum(pnl)
    prof = sum(p for p in pnl if p > 0)
    loss = -sum(p for p in pnl if p < 0)
    neg = sum(1 for p in pnl if p < 0)
    n = len(pnl)
    monthly = {}
    for d in days:
        monthly[d["date"][:7]] = monthly.get(d["date"][:7], 0) + d["pnl"]
    eq = peak = dd = 0.0
    streak = worst_streak = 0
    for d in sorted(days, key=lambda r: r["date"]):
        eq += d["pnl"]
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
        streak = streak + 1 if d["pnl"] < 0 else 0
        worst_streak = max(worst_streak, streak)
    return dict(tot=tot, prof=prof, loss=loss, n=n, neg=neg,
                monthly=monthly, dd=dd, best=max(pnl), worst=min(pnl),
                streak=worst_streak, months_n=months_n,
                win=100 * (n - neg) / n, pf=prof / loss if loss else 0)

Y1 = year_metrics("year", 12)
Y2 = year_metrics("y2025", 10)
CAP = 15000.0

def money(v, commas=True):
    s = f"{abs(v):,.0f}" if commas else f"{abs(v):.0f}"
    return ("+" if v >= 0 else "\u2212") + s

def pct(v):
    return ("+" if v >= 0 else "\u2212") + f"{abs(v):.0f}%"

aProf = (Y1["prof"] + Y2["prof"]) / 2
aLoss = (Y1["loss"] + Y2["loss"]) / 2
aTr = (Y1["n"] + Y2["n"]) / 2
aPnl = (Y1["tot"] + Y2["tot"]) / 2
avg_day = (aProf - aLoss) / aTr

def yr_cells(y):
    pl_mo = y["prof"] / y["months_n"], y["loss"] / y["months_n"]
    return (
        f'<td class="pos divider">{money(y["tot"])}</td>'
        f'<td>{money(y["prof"])} / <span class="neg">{money(-y["loss"])}</span></td>'
        f'<td>{money(y["tot"]/y["n"])}</td>'
        f'<td>{y["n"]}</td><td class="neg">{y["neg"]}</td>'
        f'<td>{pct(y["tot"]/CAP*100)}</td>'
        f'<td>{pct(y["prof"]/CAP*100)} / {pct(-y["loss"]/CAP*100)}</td>'
        f'<td>{money(pl_mo[0])} / <span class="neg">{money(-pl_mo[1])}</span></td>'
        f'<td>{pct(y["tot"]/y["months_n"]/CAP*100)}</td>')

c23_row = (
    '<tr class="champ"><td class="l">C23 CHAMPION rules (1PM window) — sized live as C30<br>'
    '<span style="font-weight:400;font-size:.72rem;color:var(--muted)">'
    '= C21 machinery + exits until 1PM (entries still end noon) \u2014 re-adopted 2026-08-05</span></td>'
    f'<td>{money(avg_day, False)}</td><td>{aTr:.0f}</td>'
    f'<td class="pos">{money(aProf, False)}</td><td class="neg">{money(-aLoss, False)}</td>'
    f'<td class="pos">{money(aPnl, False)}</td>'
    f'<td>+{avg_day/CAP*100:.1f}%</td><td>{pct(aProf/CAP*100)}</td>'
    f'<td class="neg">{pct(-aLoss/CAP*100)}</td><td class="pos">{pct(aPnl/CAP*100)}</td>'
    + yr_cells(Y1) + yr_cells(Y2) +
    f'<td class="divider">{Y1["win"]:.0f}% \u2192 {Y2["win"]:.0f}%</td>'
    f'<td>{Y1["pf"]:.1f} \u2192 {Y2["pf"]:.1f}</td>'
    f'<td class="neg">{money(Y1["dd"])} \u2192 {money(Y2["dd"])}</td>'
    f'<td>{money(Y1["best"])} \u2192 {money(Y2["best"])} / '
    f'<span class="neg">{money(Y1["worst"])} \u2192 {money(Y2["worst"])}</span></td>'
    f'<td>{Y1["streak"]} \u2192 {Y2["streak"]}</td></tr>')

# ---------- surgery on v1 parts ----------
t1 = parts["table1"]
t1 = t1.replace('<tr class="champ"><td class="l">C21 CHAMPION (strict noon)',
                '<tr><td class="l">C21 (strict-noon champion)')
t1 = t1.replace('<td class="l">C11 (withdrawn)</td>',
                '<td class="l">C11 (1PM, superseded by C23)</td>')
# insert C23 as the first row
t1 = c23_row + "\n" + t1

def add_grid_col(g, label):
    months = Y1["monthly"] if label == "g1" else Y2["monthly"]
    g = g.replace('<th>C21 (champ)</th>', '<th>C21</th><th>C23 (champ)</th>')
    def repl(m):
        row = m.group(0)
        mo = m.group(1)
        v = months.get(mo)
        cell = ('<td class="pos">' + money(v) + '</td>') if v is not None \
            else '<td>\u2014</td>'
        if v is not None and v < 0:
            cell = '<td class="neg">' + money(v) + '</td>'
        return row[:-5] + cell + '</tr>'
    return re.sub(r'<tr><td class="l">(\d{4}-\d{2})</td>.*?</tr>', repl, g)

g1 = add_grid_col(parts["g1"], "g1")
g2 = add_grid_col(parts["g2"], "g2")

# ---------- static sections ----------
src = io.open(Path(__file__).parent / "rebuild_artifact.py", encoding="utf-8").read()
STYLE = src.split('STYLE = """')[1].split('"""')[0]
STYLE = STYLE.replace("Trading Campaigns \u2014 Best Results",
                      "Trading Campaigns \u2014 Best Results")

RULES = """<section>
  <h2>The rulebook of champion C23 (one line each; \u2b50 = additions newer than C02)</h2>
  <div class="scroll"><table><tbody>
    <tr><td>1</td><td class="stage">Universe</td><td class="rl">Any US common stock \u2265 $2 \u2014 no upper price cap (no warrants/units/rights/preferred/ETFs)</td></tr>
    <tr><td>2</td><td class="stage">Universe</td><td class="rl">Symbol must have \u2265 50 prior trading sessions of history</td></tr>
    <tr><td>3</td><td class="stage">Qualify</td><td class="rl">Day's high \u2265 +10% over previous close (gap or intraday gain both count)</td></tr>
    <tr><td>4</td><td class="stage">Qualify</td><td class="rl">Day's volume \u2265 5\u00d7 its trailing 50-session average</td></tr>
    <tr><td>5</td><td class="stage">Qualify</td><td class="rl">Rank the day's qualifiers by gain; consider only the top 8</td></tr>
    <tr><td>6</td><td class="stage">Gate</td><td class="rl">Candidate needs \u2265 20 one-minute bars in the window</td></tr>
    <tr><td>7</td><td class="stage">Gate</td><td class="rl">Skip if already up more than +20% at 7:00 AM vs previous close (calm-gap)</td></tr>
    <tr><td>8</td><td class="stage">Gate</td><td class="rl">Halal point-in-time: clean industry; loans/mcap \u2264 10%; cash/mcap \u2264 10%; combined \u2264 20%; haram revenue &lt; 5%</td></tr>
    <tr><td>9</td><td class="stage">Trade</td><td class="rl">\u2b50 One stock/day, $15,000; ENTRIES 7AM\u2013noon, EXITS until 1PM ET (re-adopted 2026-08-05); nothing overnight</td></tr>
    <tr><td>10</td><td class="stage">Trade</td><td class="rl">Enter on 5-minute opening-range breakout or bullish candlestick pattern</td></tr>
    <tr><td>11</td><td class="stage">Trade</td><td class="rl">Extra trigger: one-shot stop-buy on a break of the premarket high</td></tr>
    <tr><td>12</td><td class="stage">Trade</td><td class="rl">Enter only while price \u2265 +10% above previous close at the moment of entry</td></tr>
    <tr><td>13</td><td class="stage">Trade</td><td class="rl">Position \u2264 20% of trailing 10-minute volume</td></tr>
    <tr><td>14</td><td class="stage">Exit</td><td class="rl">\u2b50 Sell \u2153 at +25% \u2014 UNLESS 10-min buy pressure \u2265 +0.3 (keep riding while buyers dominate)</td></tr>
    <tr><td>15</td><td class="stage">Exit</td><td class="rl">\u2b50 Pressure-modulated trail: 20% base; TIGHTEN to 10% when sell pressure \u2264 \u22120.3; WIDEN to 40% when buy pressure \u2265 +0.3</td></tr>
    <tr><td>16</td><td class="stage">Exit</td><td class="rl">Hard stop \u22128% from entry</td></tr>
    <tr><td>17</td><td class="stage">Hygiene</td><td class="rl">\u2b50 Ignore lone one-bar wicks &gt; 3\u00d7 surrounding closes in peak/scale/trail tracking</td></tr>
  </tbody></table></div>
  <p class="note">Timing texture (from the full per-trade replay): median hold 10 minutes per position
  (mean 16); winners are held longer than losers (the trail rides, the stop cuts). 27% of positions
  last under 5 minutes; only \u22480.2% run past two hours.</p>
</section>"""

DIFFS = """<section>
  <h2>How other configs differ from champion C23 (one rule per line)</h2>
  <div class="scroll"><table>
    <thead><tr><th class="l">Config</th><th class="l">Differences vs C23</th></tr></thead>
    <tbody>
    <tr><td class="l">C21</td><td class="rl">Rule 9: everything must be sold by NOON (the strict-noon-era champion; identical machinery otherwise)</td></tr>
    <tr><td class="l">C11</td><td class="rl">Same 1PM window, but:<br>Rule 14: always banks the \u2153 at +25% (no pressure skip)<br>Rule 15: trail widths 12%/30% (milder)<br>Rule 17: no wick guard</td></tr>
    <tr><td class="l">C20</td><td class="rl">Rule 9: noon window<br>Rule 14: always banks the \u2153</td></tr>
    <tr><td class="l">C10</td><td class="rl">Rule 9: noon window<br>Rule 14: always banks \u2153<br>Rule 15: trail 12%/30%<br>Rule 17: no wick guard</td></tr>
    <tr><td class="l">C02</td><td class="rl">Rule 9: noon window<br>Rule 14: always banks \u2153<br>Rule 15: fixed 20% trail (no pressure modulation)<br>Rule 17: no wick guard</td></tr>
    <tr><td class="l">AX20</td><td class="rl">All of C02's diffs, plus:<br>Rule 10: 15-minute opening range (slower)<br>Rule 11: no premarket-high trigger<br>Rule 13: size \u2264 10% of 5-minute volume</td></tr>
    <tr><td class="l">C04 / X086</td><td class="rl">Rule 13 DELETED \u2014 size uncapped (theoretical ceilings; fill-realism caveat, never adoptable)</td></tr>
    <tr><td class="l">C22 / C24</td><td class="rl">Identical rules to C21 / C23 + a 10bps-per-side trading-cost assumption (stress tests)</td></tr>
    <tr><td class="l">C03</td><td class="rl">Rule 5: top-8 pool re-ordered by premarket dollar volume (causal rank)</td></tr>
  </tbody></table></div>
</section>"""


C30 = """<section>
  <h2>C30 — the adopted sizing policy: capped half-reinvest on C23</h2>
  <div class="stats" style="margin:.2rem 0 .9rem">
    <div class="chip"><div class="l">Rule</div><div class="v" style="font-size:.95rem">slot = min($120k, $15k + ½·profits)</div></div>
    <div class="chip"><div class="l">2-yr backtest (capped)</div><div class="v">~+$4,964,801</div></div>
    <div class="chip"><div class="l">Cap reached in</div><div class="v">≈ 5 weeks</div></div>
    <div class="chip"><div class="l">Flat-$15k comparison</div><div class="v">+$992,866</div></div>
  </div>
  <div class="scroll"><table>
    <thead><tr><th>Slot</th><th>Y1</th><th>Y2</th><th class="l">Capture vs linear scaling</th></tr></thead>
    <tbody>
    <tr><td>$15k</td><td class="pos">+$412,879</td><td class="pos">+$579,988</td><td class="rl">100% — the validated baseline, 0 negative months</td></tr>
    <tr><td>$30k</td><td class="pos">+$718,026</td><td class="pos">+$1,077,701</td><td class="rl">87% / 93%</td></tr>
    <tr><td>$60k</td><td class="pos">+$1,198,007</td><td class="pos">+$1,935,844</td><td class="rl">73% / 83%</td></tr>
    <tr><td>$120k (cap)</td><td class="pos">+$1,873,247</td><td class="pos">+$3,328,199</td><td class="rl">57% / 72% — Y2 picks up 1 negative month at scale</td></tr>
    </tbody></table></div>
  <p class="note">Why the cap: the 20%-of-10-minute-volume rule makes P&amp;L sublinear in slot size, and an
  UNCAPPED half-reinvest run compounds to a $19M slot (+$37.4M raw) — rejected as fiction: at that size
  the fill model breaks (negative days jump to 55%, drawdown −$11.9M, the strategy IS the market in these
  names). $120k is the largest liquidity-measured tier. Base never shrinks — losses only eat the profit
  buffer. Fill realism at the cap is exactly what the live paper record (entry price vs price 60s later)
  must validate. E01 runs the same half-reinvest policy uncapped — large-cap liquidity makes its slot
  growth ($50k → $154k backtested, +$208,787/yr vs +$117,755 flat) unproblematic.</p>
</section>"""

C30 = """<section>
  <h2>C30 \u2014 the adopted sizing policy: capped half-reinvest on C23</h2>
  <div class="stats" style="margin:.2rem 0 .9rem">
    <div class="chip"><div class="l">Rule</div><div class="v" style="font-size:.95rem">slot = min($120k, $15k + \u00bd\u00b7profits)</div></div>
    <div class="chip"><div class="l">2-yr backtest (capped)</div><div class="v">~+$4,964,801</div></div>
    <div class="chip"><div class="l">Cap reached in</div><div class="v">\u2248 5 weeks</div></div>
    <div class="chip"><div class="l">Flat-$15k comparison</div><div class="v">+$992,866</div></div>
  </div>
  <div class="scroll"><table>
    <thead><tr><th>Slot</th><th>Y1</th><th>Y2</th><th class="l">Capture vs linear scaling</th></tr></thead>
    <tbody>
    <tr><td>$15k</td><td class="pos">+$412,879</td><td class="pos">+$579,988</td><td class="rl">100% \u2014 the validated baseline, 0 negative months</td></tr>
    <tr><td>$30k</td><td class="pos">+$718,026</td><td class="pos">+$1,077,701</td><td class="rl">87% / 93%</td></tr>
    <tr><td>$60k</td><td class="pos">+$1,198,007</td><td class="pos">+$1,935,844</td><td class="rl">73% / 83%</td></tr>
    <tr><td>$120k (cap)</td><td class="pos">+$1,873,247</td><td class="pos">+$3,328,199</td><td class="rl">57% / 72% \u2014 Y2 picks up 1 negative month at scale</td></tr>
    </tbody></table></div>
  <p class="note">Why the cap: the 20%-of-10-minute-volume rule makes P&amp;L sublinear in slot size, and an
  UNCAPPED half-reinvest run compounds to a $19M slot (+$37.4M raw) \u2014 rejected as fiction: at that size
  the fill model breaks (negative days jump to 55%, drawdown \u2212$11.9M \u2014 the strategy IS the market in
  these names). $120k is the largest liquidity-measured tier. The base never shrinks \u2014 losses only eat
  the profit buffer. Fill realism at the cap is exactly what the live paper record (entry price vs price
  60s later) must validate. E01 runs the same half-reinvest policy uncapped \u2014 large-cap liquidity makes
  its slot growth ($50k \u2192 $154k backtested, +$208,787/yr vs +$117,755 flat) unproblematic.</p>
</section>"""

E01 = """<section>
  <h2>E01 \u2014 the earnings-book champion (separate book, separate capital)</h2>
  <div class="stats" style="margin:.2rem 0 .9rem">
    <div class="chip"><div class="l">E01 flat $50k slots \u00b7 last yr</div><div class="v">+$117,755</div></div>
    <div class="chip"><div class="l">E01c compounded from $50k</div><div class="v">$433,593</div></div>
    <div class="chip"><div class="l">Win rate (99 mornings)</div><div class="v">62.6%</div></div>
    <div class="chip"><div class="l">Max drawdown (compounded)</div><div class="v">\u221221.9%</div></div>
  </div>
  <div class="scroll"><table><tbody>
    <tr><td>1</td><td class="stage">When</td><td class="rl">A halal name (S&amp;P 900 + 600 universe, price &gt; $2) reported earnings last night / this morning and BEAT the EPS estimate</td></tr>
    <tr><td>2</td><td class="stage">Signal</td><td class="rl">It opens \u2264 \u22123% below the prior close (the market sold a good report)</td></tr>
    <tr><td>3</td><td class="stage">Pick</td><td class="rl">One slot per day: the DEEPEST qualifying dip</td></tr>
    <tr><td>4</td><td class="stage">Trade</td><td class="rl">Buy the 9:30 open with the full slot; sell at the 4PM close \u2014 same day, no overnight</td></tr>
    <tr><td>5</td><td class="stage">Never</td><td class="rl">No pre-earnings buying (loses at EVERY entry hour), no after-hours entries (\u22121.6%/event), no profit targets or stops (all tested worse than the plain close exit)</td></tr>
  </tbody></table></div>
  <div class="scroll" style="margin-top:.9rem"><table>
    <thead><tr><th class="l">Evidence (33 experiments, ET01\u2013ET70)</th><th class="l">Result</th></tr></thead>
    <tbody>
    <tr><td class="rl">Dip-buy on BEATS (ET12, n=246)</td><td class="rl pos">+0.78%/event \u2014 the edge</td></tr>
    <tr><td class="rl">Same trade on MISSES (ET31 control)</td><td class="rl">\u2248 $0 \u2014 the beat gate is real information</td></tr>
    <tr><td class="rl">Buy before earnings \u2014 any hour, any lead (ET10/11/22\u201330)</td><td class="rl neg">Dead: report-day drift is negative; the week-before \u201crun-up\u201d is momentum beta \u2014 a mid-quarter placebo reproduces ~73% of it</td></tr>
    <tr><td class="rl">After-hours same-evening dip entries (ET18/19)</td><td class="rl neg">\u22121.6%/event \u2014 the evening dip keeps falling; buy the morning open</td></tr>
    <tr><td class="rl">Profit targets +8/10/15%, 2-day holds (ET14\u201317)</td><td class="rl neg">All below the plain sell-at-close</td></tr>
    <tr><td class="rl">Penny-book mechanics on 1-min bars (ET40\u201345)</td><td class="rl neg">Every variant \u2264 blind open\u2192close \u2014 large-cap dip bounces are mean-reversion, not momentum</td></tr>
    <tr><td class="rl">Sympathy peers (ET60\u201362, 13,700 peer-days)</td><td class="rl neg">Negative in all variants</td></tr>
    <tr><td class="rl">Generic buy-low/sell-high, no catalyst (BL06 one-slot)</td><td class="rl neg">\u2212$33k/yr \u2014 a dip needs a REASON; the beat is the reason</td></tr>
    </tbody></table></div>
  <p class="note">Hold profile: exactly 6.5 hours by construction (9:30 \u2192 16:00) \u2014 the opposite rhythm of C23's
  10-minute median scalps. Caveats: one bull-market year, no slippage model, deepest-dip slot rule and
  compounding chosen after seeing results. Paper validation starts 2026-08-06 (reported separately from C23).</p>
</section>"""

ANATOMY = src.split('ANATOMY = """')[1].split('"""')[0]
ANATOMY = ANATOMY.replace(
    "user kept noon \u2014 C21's smarter trail recovered ~98% of the tested 1PM premium instead",
    "1PM window re-adopted 2026-08-05: C23 banks the truncation premium directly (+$65,830/2yr over C11)")

DEAD = src.split('DEAD = """')[1].split('"""')[0]
DEAD = DEAD.replace("196 experiments", "230+ experiments across three books")
DEAD = DEAD.replace("</tbody></table></div>\n</section>",
    """<tr><td class="l">Buy-before-earnings (all lead times)</td><td class="rl neg">Negative at every entry hour; multi-day \u201crun-up\u201d is momentum beta (placebo-proven)</td></tr>
    <tr><td class="l">Earnings sympathy peers</td><td class="rl neg">\u22120.03..\u22120.09%/event across 13,700 peer-days</td></tr>
    <tr><td class="l">After-hours earnings-dip entries</td><td class="rl neg">\u22121.6%/event \u2014 evening dips keep falling</td></tr>
    <tr><td class="l">Catalyst-free dip-buying (BL family)</td><td class="rl neg">One-slot \u2212$33k/yr; 5y-uptrend gate adds nothing intraday</td></tr>
  </tbody></table></div>
</section>""")

THEAD = src.split("THEAD = (")[1].split(")\n")[0]
THEAD = eval("(" + THEAD + ")")

html = (STYLE + '\n<div class="wrap">\n<header>\n'
  '  <h1>Three Books, Two Champions \u2014 C30 (day trading) &amp; E01 (earnings)</h1>\n'
  '  <p>230+ experiments. Every one changes exactly one thing, runs on both backtest years where data\n'
  '     allows, and must beat shuffled / placebo / miss-gate controls to count. Constraints never\n'
  '     touched: halal (point-in-time), same-day close, capped capital per slot.</p>\n'
  '  <div class="stats">\n'
  '    <div class="chip"><div class="l">C23 rules \u2014 Y1 (flat $15k)</div><div class="v">+$412,879</div></div>\n'
  '    <div class="chip"><div class="l">C23 rules \u2014 Y2 (flat $15k)</div><div class="v">+$579,988</div></div>\n'
  '    <div class="chip"><div class="l">Negative months (22)</div><div class="v">0</div></div>\n'
  '    <div class="chip"><div class="l">C30 capped-R50 \u00b7 2yr</div><div class="v">~+$4.96M</div></div>\n'
  '    <div class="chip"><div class="l">E01 R50 earnings / yr</div><div class="v">+$208,787</div></div>\n'
  '  </div>\n</header>\n\n<section>\n'
  '  <h2>Full P&amp;L breakdown \u2014 sorted by Tot Avg/day = (Prof \u2212 Loss) / Trades</h2>\n'
  '  <div class="scroll">\n  <table>\n    <thead>\n' + THEAD + '\n    </thead>\n    <tbody>\n'
  + t1 + '\n    </tbody>\n  </table>\n  </div>\n'
  '  <p class="note">All % on the fixed $15,000 working capital. "Tot" columns are per-year averages;\n'
  '  Tot Avg/day = (Tot Prof \u2212 Tot Loss) \u00f7 Tot Trades. C04/X086 assume uncapped fills (ceilings, not\n'
  '  adoptable). Risk cells read Year 1 \u2192 Year 2.</p>\n</section>\n\n<section>\n'
  '  <h2>Monthly P&amp;L \u2014 every config, every month</h2>\n'
  + g1 + '\n' + g2 + '\n'
  '  <p class="note">Red cells are losing months. C23 has none in either year.</p>\n</section>\n\n'
  + RULES + '\n\n' + DIFFS + '\n\n' + C30 + '\n\n' + E01 + '\n\n' + ANATOMY + '\n\n' + DEAD + '\n</div>\n')

out = Path(__file__).parent / "x100-results.html"
out.write_text(html, encoding="utf-8")
print("rebuilt:", len(html), "chars")
