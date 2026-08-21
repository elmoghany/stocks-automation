# Trader-Mimicry Feasibility Survey (W-campaign Phase 3.4)

**Date:** 2026-08-21 · **Status:** SURVEY ONLY — nothing runs until the user approves names.
**Question:** can we follow famous day-traders' public calls in real time (paper only), run their
entries under OUR rules, and measure whether their signal survives our constraints?

**Our constraints (fixed, non-negotiable):**
- Halal gate first: debt/mcap ≤10%, cash/mcap ≤10%, combined ≤20%, haram revenue <5%, no haram industry.
- Cash account: **long only — no shorting**, no options, no futures, no margin.
- One position at a time, flat $15k tickets ($10k last), $100k/day cap, our stops, 15:00 ET flatten.
- Public feeds only: no scraping behind paywalls/logins, no signups, no contact.

**Calibration note:** our whole strategy family descends from the Ross Cameron morning workflow
(gap scanners, 7:00–12:00 momentum, small-cap gappers). Mimicking Cameron therefore tests our
*execution and latency* against the source, not new alpha. Mimicking anyone else tests whether a
different eye on the same tape adds names our scanner misses.

---

## 1. Ranked shortlist

### Top 5 (recommended for consideration)

| # | Trader / feed | Feed & latency | Cost | Instruments | Verifiability | Halal-pass estimate | Backtest archive |
|---|---|---|---|---|---|---|---|
| 1 | **Ross Cameron** (Warrior Trading) | YouTube live morning show ~9:00 ET + daily recap VODs; screen shows entries as they happen (stream latency 10–30s) | Free (full-day room is paid — off-limits) | Shares, small-cap momo | **Best in class**: CPA-audited $583→$18.8M (2017–2025), broker statements reviewed (SingerLewak) | **Low (~10–25%)** — cash-shell gappers mostly fail our ratios | Deep: years of daily recap VODs + YouTube live archives, replayable at 1-sec granularity |
| 2 | **TraderTV Live** (prop desk, Toronto) | Free YouTube live 8:00–16:00 ET, real-money trades called on stream by multiple traders | Free | Shares; mix of **large-cap news plays** + small-cap momo | Real-money on screen, but no third-party audit | **Best of the group (~40–60%)** — large-cap names pass our gate far more often | Deep: full-day VODs archived daily, replayable |
| 3 | **Madaz** (Max, @madaznfootballr) | X posts + daily "session highlights" video; real-time only inside paid room (off-limits) | Free (X/YouTube tier) | Shares, small-cap scalps, long+short | Screenshots/recaps, no independent audit | Low (~10–20%) | Moderate: X archive + YouTube recaps reconstructable 3–6 months back, but scalp entries are seconds-precision only on video |
| 4 | **Jack Kellogg** (@Jackaroo_Trades) | X posts, mostly after-fill same-day; occasional live commentary | Free | Shares, penny/small-cap, long+short | Profit.ly-verified ~$20M cumulative (May 2025); ecosystem tied to Sykes (conflict-of-interest discount) | Low (~10–20%) | Moderate: X archive reconstructable; timestamps minute-level at best, prices often stated |
| 5 | **Tim Grittani** (@kroyrunner89) | X posts + occasional recap videos; low frequency now | Free | Shares, penny/small-cap, long+short | Profit.ly-verified $1.5k→$13.5M — among the most credible records in the niche | Low (~10–20%) | Shallow for our purpose: too few 2025–26 calls to build 3–6 months of signal |

### Surveyed and set aside

| Trader | Why not |
|---|---|
| **Patrick Wieland** | Pivoted to **Nasdaq futures** — haram instrument. Excluded. |
| **Matt Kohrs** | Options + futures streams — haram. Excluded. |
| **Umar Ashraf / TradeZella TV** | Now primarily **futures** (haram); profits unverified; 2026 reviews report refund/course controversies. Excluded. |
| **Sang Lucci** | Options-centric — haram. Excluded. |
| **Alex Temiz / AllDayFaders (@team3dstocks)** | ~$16M verified, but **short-seller** — our cash account cannot short. Real-time is paid Zoom room (off-limits). Directionally unfollowable. |
| **Steven Dux** | Kinfo-verified 8-figure record, but short-biased penny strategy + real-time alerts are paywalled. Unfollowable. |
| **Tim Sykes** | Profit.ly log is public and verified (~$7.6M) but **post-fill, day-level granularity** — cannot reconstruct 1-min fills; real-time alerts paywalled; heavy promotional apparatus. Archive useful for *pattern* study only. |
| **Humbled Trader (Shay)** | Education-first; real-time is a $1,290/yr Discord (off-limits); free YouTube is weekly recaps — not followable. |
| **Kris Verma** | Data-driven small-cap, credible interviews ($3k→$2.1M claim), but real-time is a paid Whop room; free X feed is commentary, not timestamped entries. |
| **Bao / Modern Rock** | 20-yr veteran, MIC co-founder; content is mostly education/interviews now, no free real-time feed. |
| **SMB Capital** | Institutional education channel — no real-time calls at all. |
| **Bear Bull Traders / free Discords generally** | Free tiers exist but the free layer is watchlists + chatter; the actual entries live behind $99+/mo tiers. The freebies are top-of-funnel marketing, not a signal feed. |

---

## 2. Per-trader feasibility notes (top 5)

### 1. Ross Cameron — the calibration reference
- **Feed:** YouTube `@DaytradeWarrior` live morning show (~9:00 ET) most weekdays + a daily recap
  video; Twitch mirror `warrior_trading`. His platform shows tickers, position, and P&L on screen
  in real time. The full 7:00–16:00 room is Warrior Pro (paid) — we do NOT touch it.
- **Latency:** stream delay 10–30s, plus our OCR/extraction time. His bread-and-butter scalps run
  1–10 minutes; entries at +60–120s after his fill are a *different trade* — that's exactly what the
  pilot measures.
- **Verifiability:** the only name here with a **CPA-audited** multi-year record ($18.8M cumulative
  2017–2025, published on Warrior Trading's verified-earnings page). VODs are timestamped and
  replayable — watch-skill can reconstruct entries at 1-sec granularity from screen OCR.
- **Style fit:** identical universe to ours by construction (we descend from his workflow). Expect
  heavy overlap with names our scanner already finds — the marginal value is *entry timing*, not
  discovery.
- **Halal estimate:** low. Repo history is blunt: "the halal gate kills the monsters" — his best
  names (cash-shell biotechs, reverse-split lottery tickets) mostly fail cash/mcap or debt/mcap.
  Expect ~1–3 followable calls per week after the gate.
- **Backtest:** yes — months of recap VODs + live archives. This is the strongest backtest asset
  of any candidate.

### 2. TraderTV Live — the halal-friendliest feed
- **Feed:** free YouTube live, 8:00–16:00 ET daily, multi-trader real-money desk; trades and
  reasoning called out loud as they happen.
- **Latency:** same 10–30s stream delay; their large-cap news plays (earnings, Fed, CPI reactions)
  run 10–60 min — far more survivable at +60–120s than small-cap scalps.
- **Verifiability:** real money on screen, no third-party audit. Treat as unverified but observable.
- **Style fit:** partial — large/mid-cap news momentum is NOT our current universe, which is
  exactly why it's interesting: it tests whether mimicry can *widen* our thin halal universe
  instead of inheriting it.
- **Halal estimate:** the best surveyed (~40–60% of large-cap tech/consumer names plausibly pass;
  banks/levered names fail). This is the only feed where the gate isn't a near-total filter.
- **Backtest:** full-day VODs archived daily — 3–6 months reconstructable via watch-skill, though
  processing 8h/day of video is compute-heavy; sample the 9:30–11:00 window.

### 3. Madaz — small-cap scalper, backtest-only realistic
- **Feed:** X `@madaznfootballr` (free) + daily session-highlight videos. True real-time is his
  paid room — off-limits. X posts are typically during/after the move, minute-stamped.
- **Latency:** his edge is seconds-scale scalps at the open; by the time a post is up, the move is
  usually over. **Real-time following is infeasible**; value is (a) historical signal-quality
  backtest, (b) a second attention scanner (which tickers he's on).
- **Verifiability:** recap screenshots, no audit. Style is transparent (he narrates fills in
  highlight videos with timestamps visible).
- **Halal estimate:** low (~10–20%) — same cash-shell gapper universe as ours.
- **Backtest:** X archive + YouTube recaps support a 3–6 month reconstruction at ~minute
  granularity. Doable but noisy.

### 4. Jack Kellogg — active, verified-adjacent, post-fill
- **Feed:** X `@Jackaroo_Trades` (~78k followers), same-day trade posts, occasional big-P&L
  screenshots. No free real-time room.
- **Latency:** post-after-fill; entries not followable live. Suitable for backtest + overlap
  analysis only.
- **Verifiability:** ~$20M cumulative on profit.ly (crossed May 2025); note the verification
  platform belongs to his mentor's ecosystem — apply a discount.
- **Halal estimate:** low; penny/small-cap universe, plus he shorts (those calls are dead to us).
- **Backtest:** X archive reconstructable; prices often stated, timestamps minute-level.

### 5. Tim Grittani — highest credibility, lowest frequency
- **Feed:** X `@kroyrunner89`, sporadic; recap videos occasionally.
- **Verifiability:** $1.5k→$13.5M with profit.ly verification over 12+ years — the most credible
  organic record surveyed.
- **Why only #5:** frequency. A mimic ledger needs a call stream; he no longer produces one.
  Keep as a study reference (his Trading Tickers material) rather than a live feed.

---

## 3. Aggregators and platforms (surveyed honestly)

| Source | What it is | Verdict for us |
|---|---|---|
| **Quiver Quantitative** | Congress/insider/lobbying trackers + API | Shares (halal-filterable), but STOCK Act filings lag up to **45 days** — useless for day-trade mimicry; API paid. Not mimicry; possible future swing-campaign input. |
| **Unusual Whales** | Options-flow alerts + congress tracker | Core product is **options flow — haram** instrument signals; congress data same 45-day lag. Excluded. |
| **OpenInsider / SEC Form 4** | Free insider-trade filings | Shares, free, but 2-business-day filing lag → swing horizon, not day trading. Out of scope here; noted for a possible separate campaign. |
| **eToro CopyTrader / ZuluTrade / Dub / Autopilot / Collective2** | Real-money auto-copy platforms | Out of scope: they execute with real money in their wrapper (often CFDs/margin), cannot apply our halal gate or risk rules, and defeat the point (we want *signal measurement*, not delegation). |
| **StockTwits / ApeWisdom / WSB trackers** | Free sentiment/mention APIs | Not trade calls — crowd attention. Could feed our scanner someday; not mimicry. |
| **Free alert Discords (Bear Bull Traders, Hercules, etc.)** | Free tiers of paid rooms | Free layer is watchlists/chatter; entries are behind paywalls. Watchlists could seed our scanner but are not timestamped entries. |

---

## 4. Recommended pilot design (paper only — needs user approval)

**Pilot roster (2–3 feeds):**
1. **Ross Cameron morning show** — calibration arm. Does the source workflow, followed at +60s,
   survive our gate and our exits?
2. **TraderTV Live (9:30–11:00 window)** — universe-expansion arm. Do large-cap news plays give
   the halal gate something to pass?
3. **Madaz X feed (backtest-only arm)** — reconstruct 3 months of calls offline first; no live
   following unless the backtest clears the bar.

**Mechanics:**
- Ledger at `data/paper_mimic/<trader>/` — one row per call: `call_ts, ticker, side, their_px
  (if stated), our_fill_ts (+60s and +120s variants), halal_verdict, size, exit_ts, exit_reason, pnl`.
- Extraction: watch-skill on live-stream VODs (OCR of on-screen positions + transcript); X posts
  via public pages. No logins, no paid rooms, no scraping behind auth.
- **Their entry, our everything else:** halal gate first (point-in-time, 45-day filing lag as in
  C37); long-only — short calls logged but never taken (measure how much of the feed dies here);
  $15k ticket ($10k last), $100k/day cap; our stops and trails; 15:00 flatten (moot for
  morning-scalp feeds).
- **Measured, not assumed:** halal pass-rate per feed; signal decay (entry at +0/+60/+300s);
  win-rate and $/trade vs. the C37 baseline on the same days; overlap % with our own scanner picks
  (if overlap is high, mimicry adds nothing).
- **Kill criteria (pre-registered):** after 20 sessions per feed — fewer than 2 halal-passing calls
  per week, or +60s entry edge ≤ 0 after slippage model, or >80% scanner overlap → kill that arm.

**Sequencing:** backtest before live. Each arm runs 3 months of VOD/archive reconstruction first;
only arms with positive reconstructed edge graduate to the live paper ledger.

---

## 5. Risks — the honest section

1. **Survivorship + selection bias.** We found these names *because* they won. For every audited
   Cameron there are thousands of blown-up accounts running the same playbook; a famous trader's
   record is closer to a lottery-winner interview than a sampling distribution. Public recaps
   (all non-audited names) additionally over-post winners. Only Cameron's CPA audit and
   Grittani/Sykes' profit.ly logs even attempt completeness — and profit.ly is self-connected
   verification inside the guru's own ecosystem.
2. **Latency makes scalps unfollowable.** Small-cap momentum edges live at seconds scale. Stream
   delay (10–30s) + extraction + our order path means we enter a different trade. On thin gappers,
   spread + slippage at +60s can exceed the trader's entire captured edge. The pilot's +0/+60/+300s
   decay measurement exists precisely to prove or kill this — expect it to kill the scalp arms.
3. **The halal gate inherits our thin universe.** Repo history: "the halal gate kills the
   monsters." Small-cap gappers fail on cash/mcap (post-IPO cash shells) or debt/mcap routinely;
   past screens rejected 10/10 candidates on some days. A mimic feed of 20 calls/week may yield
   2–3 followable ones. TraderTV's large-cap arm is the only feed where this isn't near-fatal.
4. **We'd be their exit liquidity.** In thin names, a famous trader's visible entry *is* part of
   the pump. Following at +60s means buying into their scale-out. This is a structural adverse-
   selection cost, not a tuning problem.
5. **No shorting.** Half the credible small-cap field (Temiz, Dux, much of Kellogg/Grittani) is
   short-biased. Our cash account takes long calls only; the surviving feed is a biased subsample
   of each trader's actual strategy.
6. **Guru economics.** Every surveyed name earns more from subscriptions than we could earn from
   their calls; incentives favor exciting calls over followable ones. Audited ≠ replicable.
7. **TOS/legality.** Watching public YouTube/X is fine; VOD processing via yt-dlp sits in a
   YouTube-TOS gray zone (already accepted repo-wide for watch-skill); paid rooms, member Discords,
   and profit.ly alert feeds stay untouched. Nothing here constitutes investment advice intake —
   it's public-information research.
8. **Expected outcome, stated up front:** the most likely result is that mimicry adds *attention*
   (tickers we'd have missed) rather than *entries* (their timing at our latency). If the pilot
   confirms that, the deliverable is a better scanner input, not a copy-trader — and that would
   still be a win.

---

## Sources

- Warrior Trading — [verified earnings](https://www.warriortrading.com/ross-camerons-verified-day-trading-earnings/), [live sessions FAQ](https://support.warriortrading.com/support/solutions/articles/19000114764-live-trading-sessions-what-did-ross-and-the-warrior-trading-team-trade-today-what-is-on-your-watch-), [YouTube @DaytradeWarrior](https://www.youtube.com/@DaytradeWarrior), [Twitch](https://www.twitch.tv/warrior_trading), [audit coverage](https://www.financialtechwiz.com/post/ross-cameron-net-worth/)
- TraderTV Live — [site](https://tradertv.live/), [YouTube streams](https://www.youtube.com/@TraderTVLive/streams), [Real Trading profile](https://realtrading.com/trader-tv-live/)
- Madaz — [site](https://www.madazmoney.com/), [X @madaznfootballr](https://x.com/madaznfootballr), [review](https://stockalertsreviewed.com/madaz-money-review/)
- Jack Kellogg — [X @Jackaroo_Trades](https://x.com/Jackaroo_Trades), [$20M milestone](https://www.timothysykes.com/blog/how-jack-crossed-20-million/)
- Tim Grittani — [X @kroyrunner89](https://x.com/kroyrunner89), [Trade the Ticker](https://tradetheticker.blogspot.com/), [profile](https://timothysykes.com/blog/timothy-grittani/)
- Tim Sykes / profit.ly — [TimChallenge](https://profit.ly/newsletter/TimChallenge), [Profitly review](https://www.thestockdork.com/profitly-review/), [Bullish Bears review](https://bullishbears.com/profit-ly-review/)
- Steven Dux — [Kinfo verified performance](https://kinfo.com/portfolio/11253/performance), [review](https://stockalertsreviewed.com/steven-dux-review-skeptical-dont-miss-this/)
- Alex Temiz / MIC — [profile](https://myinvestingclub.com/alex-temiz/), [Chat With Traders ep. 323](https://chatwithtraders.com/episode/323-alex-temiz)
- Umar Ashraf — [TradeZella TV event](https://luma.com/xyhrv63h), [2026 review w/ controversy](https://beststockstrategy.com/umar-ashraf-review-scam/), [Fast Company on TradeZella](https://www.fastcompany.com/91212604/built-by-one-of-their-own-tradezella-lets-day-traders-track-and-plan-transactions)
- Patrick Wieland — [YouTube streams (futures)](https://www.youtube.com/@PatrickWieland/streams)
- Matt Kohrs — [YouTube streams (options/futures)](https://www.youtube.com/@TheMattKohrsShow/streams)
- Sang Lucci — [The Lucci Method](https://sacredtraders.com/product/the-lucci-method-by-sang-lucci/)
- Humbled Trader — [community pricing](https://www.humbledtrader.com/our-community/)
- Kris Verma — [site](http://krisverma.com/), [Whop room](https://whop.com/discover/krisverma/), [TradingSim interview](https://www.tradingsim.com/simcast/tag/kris-verma)
- Bao / Modern Rock — [site](https://bao.io/)
- Aggregators — [Quiver API](https://www.quiverquant.com/api/), [congress-tracker comparison](https://meridianfin.io/knowledge/congress-tracker-comparison-2026), [Unusual Whales vs Quiver](https://unusualwhales.com/vs/quiver-quantitative), [eToro CopyTrader review](https://www.wallstreetzen.com/blog/etoro-copy-trading-review/), [Dub](https://www.dubapp.com/blog/best-real-time-copy-trading-apps), [copy-platform comparison](https://fortraders.com/blog/copy-trading-platforms-comparison)
- Discord landscape — [tradereview.app 2026 guide](https://tradereview.app/blog/day-trading-discord/), [For Traders guide](https://fortraders.com/blog/trading-discords-communities)
