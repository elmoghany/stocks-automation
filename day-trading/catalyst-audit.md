# CATALYST-MINER (2026-09-16) — a timestamped catalyst corpus (news, EDGAR
# filings, earnings) added to the causal wide universe: does a NEW INPUT
# SET move the IC ceiling that four price-and-volume lines measured at ≈ 0.03?

**Mandate.** Every prior line on the causal wide universe (WIDE-NET,
UNIVERSE+QUOTES, RL-v2, CLOSE-MOMENTUM) ended at the same number: a
walk-forward ranker built from price and volume reaches a cross-sectional
IC of ≈ 0.03 against a break-even of 0.126–0.15. Their shared ranked idea #1
was *change the information set, not the model*. This line builds the
cheapest genuinely new information set the account can reach — a
**timestamped catalyst corpus** (Polygon news, SEC EDGAR filings with
acceptance datetimes, Robinhood earnings results) — and asks the one
question that matters: **does adding it to the same ranker, on the same
table, with the same fills and costs, move the out-of-sample IC and the
$/ticket of the chosen name?**

**Verdict: FAIL — see Part 8.** The headline numbers are filled in below as
each stage of the run lands; the corpus, the method, the bucket tables and
the rules are final.

Read `widenet-audit.md` first: the ticket table, the fills, the cost ladder,
the walk-forward protocol and the honest-harness conventions are inherited
from it unchanged (`plan/wn_table.day_block`, `plan/wn_lib.single_pick`,
`plan/wn_lib.summarize`). Nothing in `plan/rl2/`, `plan/wn_*.py`,
`plan/cm_*.py`, `plan/cr_*.py` or `shared/massive.py` was modified.

---

## Part 0 — What was run, and where it lives

| stage | code | output |
|---|---|---|
| Polygon news corpus, one JSON per symbol-month | `plan/cat_news.py` | `data/news_hist/{SYM}/{YYYY-MM}.json` + `_done.json` |
| EDGAR filings with acceptance datetimes + 8-K items; Form 4 XML parsed | `plan/cat_edgar.py` | `data/filings_hist/{SYM}.json`, `data/filings_hist/form4/{SYM}.json` |
| Robinhood `get_earnings_results` (191 names, 8 trailing quarters) | MCP calls, saved by hand | `data/filings_hist/earnings_rh.tsv` → `earnings_rh.json` |
| taxonomy, event clock, shared paths | `plan/cat_lib.py` | — |
| event corpus + causal feature function | `plan/cat_events.py` | `data/massive/cat/events.pkl`, `corpus_report.json` |
| labelled ticket table (32 wide-net + 137 catalyst columns) | `plan/cat_table.py` | `data/massive/cat/table.npz`, `table_gap.npz` |
| bucket tables + pre-registered rules | `plan/cat_buckets.py` | `buckets.json`, `rules.json` |
| walk-forward LightGBM with / without the block, all controls | `plan/cat_model.py` | `model_results.json`, `model_results_gap.json`, `scores_*.npy` |
| the catalyst block as a veto; closest-miss rule in detail | `plan/cat_veto.py` | `veto.json`, `rule_detail.json` |
| poison test (bars AND events, at the level of the picks) | `plan/cat_poison.py` | `poison.json` |
| measured-cost repricing (COST-REBASE module as it stands) | `plan/cat_cost.py` | `cost_reprice.json` |

`data/news_hist/` and `data/filings_hist/` are new caches (gitignored with
the rest of `data/`, like every other bulk cache in this repo); the code
that rebuilds them is resumable and committed.

### The causal contract, stated once

An event may be used at decision minute *m* on date *D* only if its
**public timestamp ≤ (D, m)** in New York time:

* **news** — Polygon's `published_utc` (the publisher's own clock);
* **filings** — EDGAR's `acceptanceDateTime` (the SEC's clock, to the
  second). Filings accepted after 17:30 ET are disseminated at 06:00 ET the
  next business day; no decision minute in this line lies between 17:30 and
  06:00, so the acceptance instant is exactly the causal instant for every
  decision made here;
* **earnings** — Robinhood carries only a date and an `am`/`pm` slot. `am`
  is placed at 07:30 ET of the report date (usable from 09:35), `pm` at
  16:30 ET (usable from the next session's open). An unknown slot is
  treated as `pm`, i.e. later.

Every catalyst feature is a function of events with ts ≤ the decision
instant — trailing windows of 18h / 3d / 10d / 30d, hours-since-last-event,
the most recent surprise — and `plan/cat_poison.py` mutates every event
after the decision instant and asserts that not one feature, and not one
chosen name, moves (Part 7).

**The engine's own convention is inherited, not re-derived:** a decision at
minute *m* fills at the open of minute *m*+1, 10 bps a side (+50 bps outside
09:30–16:00), notional = min($15,000, 20% of the trailing 5-minute volume ×
fill), the candidate gate is *bar m printed*. The decision grid is the
mandate's six times — 09:35, 10:00, 10:30, 11:00, 13:00, **15:30** (the last
is new; `plan/wn_table` stopped at 15:00).

---

## Part 1 — The corpus

### 1.1 Polygon news — two years of history exist, but the feed is thin

`/v2/reference/news` on the paid Starter tier, `ticker=SYM`,
`published_utc` window 2024-08-01 → 2026-09-01, paged with `next_url`.
**The history does not stop short: an unwindowed query for AAOI returns
articles from 2021-04-29**, so the two-year window is fully covered.

| | all 2,850 symbols (191 wide + 2,659 gapper-pool) | the 191 wide names |
|---|---|---|
| symbols with ≥ 1 article | 2,410 | **191 / 191** |
| articles (2024-08 → 2026-08) | 57,013 | **9,546** |
| per symbol-year | — | **24.0** (≈ 2 a month) |
| per calendar day, whole universe | — | **18.2** |
| "solo" articles (≤ 3 tickers listed) | 38,761 | 6,431 |
| publishers (wide) | | The Motley Fool 4,001 · **GlobeNewswire 3,486** · Benzinga 1,370 · Investing.com 609 · Zacks 78 · MarketWatch 2 |

**What the feed is:** Motley Fool and Benzinga commentary, GlobeNewswire
press releases, Investing.com re-writes. **What it is not:** PR Newswire and
Business Wire are absent — the two wires that carry roughly half of all
company press releases — so the *primary* catalyst source (the company's
own release) is present only for GlobeNewswire clients. Polygon also
attaches an `insights` sentiment label per ticker; it is kept as a
secondary feature and flagged as such (it is generated at ingestion, but its
generation time is not exposed, so it is the one column whose causality
rests on the vendor's word).

**How often a decision actually sees a catalyst** (eligible rows at 09:35,
wide universe):

| feature | share of rows > 0 |
|---|---|
| any article in the trailing 18h | **5.5%** |
| a press release in the trailing 18h | 2.1% |
| any article in the trailing 10d | 33.5% |
| any filing in the trailing 18h | 15.6% |
| a fresh earnings report (≤ 18h) | **1.9%** |
| an 8-K item 2.02 in the trailing 18h | 2.1% |
| a 424B in the trailing 3d | 0.9% |
| a dilution filing (424B / S-3 / S-1 / 8-K 3.02) in the trailing 30d | 11.2% |
| an insider open-market purchase in the trailing 30d | 2.7% |
| any of {offering, FDA, contract, earnings, M&A, analyst, legal, 8-K 1.01/2.02/3.02/8.01, 424B, PR} in 18h | 7.3% |

On a typical morning ~4 of the ~60 eligible names carry anything fresh.
That is the first structural fact about this information set: it is
**sparse**, and a cross-sectional ranker sees it on one name in fourteen.

### 1.2 EDGAR — acceptance datetimes and 8-K items, straight from the SEC

`https://data.sec.gov/submissions/CIK##########.json` (free, no key,
User-Agent required, paced at 7 req/s) lists every filing of the issuer with
`acceptanceDateTime` and, for 8-Ks, the `items` string ("1.01,2.03,9.01").
This is strictly better than the daily index `form.idx` the mandate named,
which carries only the filing *date*; nothing had to be parsed to get item
codes. 2,612 of 2,850 symbols map to a CIK via `data/edgar/company_tickers.json`;
the 238 without are leveraged/ETF-style tickers of the gapper pool (AALG,
AMZU, AVGX …) and are not companies.

| | all 2,612 | the 191 wide names |
|---|---|---|
| filings 2024-08 → 2026-09 | 468,578 | **37,187** (93.6 per symbol-year) |
| 8-K item 2.02 (results) | 15,497 | 1,692 |
| 8-K 7.01 (Reg FD) | 14,387 | 1,384 |
| 8-K 5.02 (officer / director change) | 9,638 | 957 |
| 8-K 8.01 (other events) | 12,741 | 950 |
| 8-K 1.01 (material agreement) | 9,352 | 704 |
| 8-K 3.02 (unregistered sales = dilution) | 3,682 | 247 |
| 424B (prospectus / offering) | 74,404 | 456 |
| S-3 / F-3 shelf | 2,909 | 146 |
| S-1 / F-1 | 3,404 | 103 |
| SC 13D | 5,803 | 333 |
| SC 13G | 24,153 | 2,174 |
| Form 144 | 34,109 | 6,170 |
| Form 4 | 130,981 | **17,262** |

**Form 4 direction** needs the filing's own XML (transaction code `P` =
open-market purchase, `S` = sale, with the A/D flag). All 17,262 Form 4s of
the 191 wide names were fetched and parsed (`data/filings_hist/form4/`, 0
errors): **282 contain an open-market purchase, 2,415 a sale**. Insider
*buying* on this universe is a 1.6%-of-Form-4s event — 1.4 per name per
year.

### 1.3 Earnings — three sources, merged by report date

* **Robinhood `get_earnings_results`**, 191 calls by hand, 1,488 rows,
  **1,295 reported quarters with `eps_actual`, 1,153 with an estimate**,
  am/pm slot on every row. It returns only the trailing 8 quarters, so its
  history starts at **2025-02** for most names (median first report
  2025-02-25). Coverage inside the study window: 1,227 reported events.
* the older yfinance pull (`data/earnings_yf.json`, 78 of the 191 names, a
  clock and a surprise %) fills 2024-10 → 2025-02;
* `data/earnings_dates.json` (date, `bmo`/`amc`, `beat` flag) fills the rest
  with sign only.

Result: **3,145 earnings events on the wide universe** (all 2,850: 23,658;
sources 22,222 yf / 1,295 RH / 141 dates-only). Surprise = (actual −
estimate) / max(|estimate|, 0.01), clipped ±100%, sign carried separately.

### 1.4 Catalyst classification — rule-based, and what it actually finds

`plan/cat_lib.TAXONOMY`: 16 classes, ~230 lower-case patterns over headline
+ description. An article can carry several classes. Distribution on the
wide universe's 9,546 articles:

| class | articles | note |
|---|---|---|
| earnings | 3,700 | results / guidance / quarter language |
| crypto_ai | 2,846 | over-triggers on " ai " — treated as a theme flag, not a catalyst |
| legal | 2,214 | **dominated by law-firm "shareholder alert" releases** (Pomerantz, Rosen, Levi & Korsinsky …) |
| analyst | 1,361 | upgrades / downgrades / price targets / Zacks rank |
| contract | 1,307 | award / partnership / launch |
| mna | 721 | |
| index | 508 | Russell / S&P inclusion language |
| fda | 494 | |
| macro_list | 400 | "stocks that hit 52-week …", "why X is soaring today" |
| management | 228 | |
| offering | 224 | pricing / registered direct / ATM / warrants / reverse split |
| insider | 83 | |
| delisting | 42 · halt 33 · guidance_up 23 · guidance_down 4 | |

Two things follow. **Guidance changes are almost never headlined** in this
feed (27 in two years); the information lives inside the earnings articles
and in 8-K 2.02. And the loudest "catalyst" class by volume is the
securities-litigation solicitation industry, which files a release for
every name that has dropped — a *consequence* of moves, not a cause. The
EDGAR 8-K item codes are cleaner labels than any headline pattern, which is
why the filing classes are carried as separate columns rather than folded
into the taxonomy.

An embedding classifier was not built: with 9,546 articles on 191 names
over two years the headline taxonomy is not the binding constraint — the
sparsity of 1.1 is.

---

## Part 2 — The table

`data/massive/cat/table.npz` — **163,254 rows** (448 dates × 6 decision times
× the day's universe), **131,772 causally eligible**, **169 columns**: the 32
wide-net columns (26 of `plan/rl2/features.py` + `dow`, `sic2`, `earn_prox`,
`coil`, `earn_rh`, `earn_fresh`) followed by **137 catalyst columns**:

* `n_{class}_{18h,3d,10d}` for 39 classes (16 news, 19 filing families,
  `news_all`, `news_solo`, `pr`, `fil_all`) = 117 counts;
* `hrs_since_{news,pr,fil,earn}` (capped at 720h);
* `sent_mean_3d`, `sent_mean_10d`, `sent_n_10d` (solo articles only);
* `earn_fresh_ev`, `earn_surp_pct`, `earn_surp_sign`, `days_since_earn`,
  `earn_surp_fresh_pct`, `earn_surp_fresh_sign`;
* `dilution_30d`, `offer_news_30d`, `insider_buy_30d`,
  `insider_buy_usd_30d`, `insider_sell_30d`, `f13d_30d`, `any_catalyst_18h`.

Labels = the realised **net dollar P&L** of the $15,000 ticket at h15 / h30 /
h60 / h120 / flatten, byte-identical to `plan/wn_table` (same `day_block`,
different decision grid). `data/massive/cat/table_gap.npz` — the +10% gapper
pool under `RS_CROSS` (`plan/cm_rows.py`'s rows): 41,908 rows at 10:00 /
11:00 / 13:00 / 15:30, 24,007 live, priced from `px_in` / `px_out` at 10 bps
a side exactly as `plan/cm_lib.trade_day` does, with the same 137 catalyst
columns evaluated one minute before the fill label.

One defect found and fixed before any model ran: the wide-net block already
had a column named `earn_fresh` (the Robinhood-calendar flag), and the first
catalyst block reused the name; LightGBM refused the duplicate. The
catalyst version is `earn_fresh_ev` throughout.

---

## Part 3 — Bucket tables: what each catalyst class is worth, unconditionally

`plan/cat_buckets.py` — 55 boolean flags × 6 decision times × 4 horizons =
**2,768 buckets** with n ≥ 30 (n ≥ 100 for anything quoted below), each with
its complement, split Y1 (< 2025-08) / Y2. No fitting.

**The shape of the whole table:**

| | count |
|---|---|
| buckets | 2,768 |
| with a positive mean $/ticket | 164 (5.9%) |
| with t > +2 | **1** |
| with t < −2 | 1,831 |
| positive, n ≥ 100, positive in BOTH years | **19** — best t = +1.19 |

The universe's unconditional expectancy is ≈ −$30/ticket (the toll), so
"significantly negative" is the default; the question is the *delta*
between a bucket and its complement. The best-looking positive buckets are
all the same thing — a **424B / S-3 in the last 3–10 days, held to the
flatten** (+$46, +$35, +$28 per ticket at 10:00 / 09:35 / 11:00 flat, t =
0.9 / 0.5 / 0.6) — i.e. a freshly-diluted name bought and held all day.
None clears t = 1.2; the sign is not stable across horizons (the same flag
at h30 is −$20 to −$48); and it is exactly the family the mandate said to
treat as a **negative** prior. Recorded as noise.

**The information is on the negative side.** Both-years-consistent, n ≥ 100,
|t| ≥ 2 (a selection of the 1,660 such buckets, the strongest by delta):

| flag (trailing) | dec | h | n | $/ticket in | t | Y1 | Y2 | complement | delta |
|---|---|---|---|---|---|---|---|---|---|
| 8-K 5.02 (officer/director change) in 3d | 13:00 | flat | 306 | **−143.81** | −7.0 | −199.8 | −111.9 | −72.3 | **−71.5** |
| analyst headline in 3d | 09:35 | flat | 819 | −149.50 | −6.7 | −127.4 | −156.6 | −79.9 | −69.6 |
| Form 4 sale in 3d | 10:00 | flat | 253 | −149.24 | −4.7 | −177.6 | −143.4 | −79.9 | −69.4 |
| fresh earnings (any) | 10:30 | flat | 376 | −168.73 | −4.5 | −238.3 | −145.2 | −77.2 | −91.5 |
| fresh earnings **beat** | 10:30 | flat | 279 | −159.79 | −4.0 | −197.7 | −147.6 | −77.8 | −82.0 |
| 10-Q/10-K accepted in 18h | 10:30 | flat | 175 | −183.09 | −3.9 | −329.9 | −138.2 | −78.1 | −105.0 |
| legal (law-firm) headline in 18h | 09:35 | flat | 210 | −100.21 | −2.0 | −134.9 | −85.7 | −82.8 | −17.4 |
| analyst headline in 18h | 10:00 | h120 | 211 | −56.50 | −2.0 | −85.3 | −45.8 | −34.0 | −22.5 |
| 424B in 10d | 09:35 | h60 | 520 | −43.60 | −2.0 | −56.5 | −39.1 | −33.2 | −10.4 |

Read as a long-only trader: a name that just changed an officer, whose
insiders just sold, that the sell side is talking about, or that reported
this morning and is being *held to the close*, loses $60–$100 more per
ticket than the rest of the universe. These are vetoes, and Part 6 prices
them as vetoes. They are not longs.

**The one bucket that matters for the rest of this document** is not in the
table above because it is a *conjunction*: fresh earnings AND green since
the open. It surfaces in the rules.

---

## Part 4 — The pre-registered rules, and the family the ablation opened

`plan/cat_buckets.rules()` — 14 rules written before any bucket was read
(R1–R14), each a set; at every (date, decision) slot the qualifying names
are taken (tie-break = the most recent catalyst), k = 1 or 7. The matched
control draws k random *eligible* names on the same slots (30 seeds); the
mirror takes the complement set. Both years, ex-best, months positive and
the percentile on total AND ex-best are reported for every row in
`data/massive/cat/rules.json`; the k = 1 rows:

| rule | h | tickets | $/tkt | $/month | Y1 | Y2 | random ± sd | pct total/ex-best | mirror |
|---|---|---|---|---|---|---|---|---|---|
| **R1 pre-open beat AND green @09:35** | h60 | 95 | **+71.24** | **+317** | +137.0 | +38.8 | −46.2 ± 28 | 100 / 100 | −125.6 |
| R1 | h120 | 95 | +60.63 | +270 | +184.2 | +1.5 | −43.9 ± 40 | 100 / 100 | −122.7 |
| R1b beat AND green @10:00 | h60 | 103 | +77.28 | +373 | +193.3 | +50.7 | −21.0 ± 21 | 100 / 100 | −64.9 |
| R2 beat (any colour) @09:35 | h60 | 149 | −21.95 | −153 | +140.9 | −96.2 | −48.1 ± 24 | 93 / 90 | −121.4 |
| R2c beat @13:00 | h60 | 50 | +102.92 | +241 | −33.1 | +130.9 | +1.8 ± 20 | 100 / 100 | +6.9 |
| R3 miss @10:30 (contrarian) | h120 | 57 | −113.84 | −304 | −145.3 | −72.3 | −19.5 ± 36 | 0 / 0 | −124.1 |
| R4 fresh PR/contract/FDA/8-K 1.01, no dilution @09:35 | h60 | 297 | −22.96 | −320 | −49.1 | −17.8 | −27.1 ± 19 | 57 / 53 | −11.6 |
| R4b same AND green | h60 | 197 | −15.71 | −145 | −77.1 | +6.1 | −29.9 ± 24 | 77 / 80 | −35.6 |
| R5 insider buy in 30d, no dilution @09:35 | h120 | 283 | −26.87 | −356 | −22.9 | −29.4 | −23.0 ± 25 | 50 / 53 | −22.8 |
| R6 offering / 424B / 8-K 3.02 in 3d @09:35 (expected negative) | h60 | 214 | −49.66 | −498 | −120.2 | −9.2 | −32.9 ± 23 | 27 / 20 | −23.1 |
| R7 8-K 2.02 in 18h AND green @09:35 | h60 | 127 | −4.46 | −27 | +11.8 | −35.6 | −38.3 ± 24 | 93 / 83 | −34.6 |
| R8 SC 13D in 10d @09:35 | h120 | 218 | −67.41 | −689 | −1.0 | −107.7 | −26.3 ± 34 | 7 / 10 | −11.5 |
| R9 analyst headline 18h @09:35 | h60 | 155 | −33.24 | −241 | −24.7 | −40.2 | −31.6 ± 35 | 43 / 33 | −26.4 |
| R10 index-inclusion headline 10d @15:30 | h30 | 364 | −92.30 | −1,593 | −92.5 | −90.7 | −79.6 ± 10 | 7 / 10 | −53.8 |
| R11 M&A headline 18h @09:35 | h60 | 89 | −16.17 | −67 | −56.8 | −22.5 | −25.1 ± 32 | 70 / 73 | −109.1 |
| R12 FDA headline 18h @09:35 | h60 | 55 | −63.47 | −164 | +100.8 | −115.3 | −11.6 ± 50 | 13 / 13 | +0.8 |
| R13 no news / filing in 10d (quiet) @09:35 | h60 | 447 | −36.21 | −759 | −10.3 | −61.5 | −24.3 ± 17 | 20 / 23 | −12.4 |
| R14 positive vendor sentiment 3d AND green @09:35 | h60 | 326 | −43.25 | −661 | −3.8 | −69.7 | −28.6 ± 21 | 20 / 20 | −48.7 |

**Twelve of fourteen pre-registered rules are negative**, and the ones built
on the classes the mandate named as catalysts — FDA, contract, M&A,
insider buying, 13D, index inclusion, positive sentiment, "no dilution" —
sit *at or below* their random controls. R10 (buy an index-inclusion name
at 15:30) is the worst configuration in the study at −$1,593/month; R12 (FDA
headline) flips sign between the years. **The catalyst classes a retail
trader watches do not pay on this universe at $15,000 a ticket.**

R1 is the only pre-registered rule that is positive in both years and at
the 100th percentile on total *and* ex-best, and its ablation
(`plan/cat_veto.py --detail`) said something the rule did not: dropping the
*beat* condition made it better. "Fresh earnings AND green" (R15, added
after that reading and so **post-hoc, not pre-registered**) at 09:35:

| rule (post-hoc) | h | tickets | $/tkt | $/month | Y1 | Y2 | random ± sd | pct | mirror | ex-best | months + |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **R15 fresh earnings AND green @09:35** | **h60** | 112 | **+128.35** | **+674** | +145.3 | **+120.2** | −35.6 ± 26 | 100 / 100 | −57.6 | +12,403 | 14/22 |
| R15 | h120 | 112 | +139.93 | +735 | +270.2 | +77.8 | −30.9 ± 36 | 100 / 100 | −53.6 | +12,461 | 14/22 |
| R15 | h30 | 112 | +36.44 | +191 | +115.1 | −5.9 | −38.2 ± 22 | 100 / 100 | −45.5 | +2,035 | 13/22 |
| R15 | flat | 112 | +130.04 | +683 | +123.7 | +151.3 | | | | +9,352 | 13/22 |
| R15b @10:00 | h60 | 122 | +79.15 | +453 | +97.1 | +76.4 | −16.6 ± 19 | 100 / 100 | −33.1 | +8,095 | 13/23 |
| R15b @10:00 | h30 | 122 | +52.21 | +299 | +16.0 | +74.5 | −19.7 ± 19 | 100 / 100 | −25.4 | +4,697 | 15/23 |
| R15c @10:30 | h60 | 115 | −12.67 | −68 | +51.9 | −46.5 | −17.8 ± 21 | 60 / 50 | +12.2 | −2,617 | 10/23 |
| R15d @11:00 | h60 | 40 | −121.14 | −227 | +54.1 | −174.2 | −50.1 ± 31 | 0 / 0 | −54.0 | −6,042 | 6/15 |
| R15e fresh earnings AND **red** @10:00 (the mirror) | h60 | 109 | −61.00 | −312 | −43.9 | −76.7 | −13.4 ± 26 | 0 / 0 | | −7,649 | 8/23 |
| R15, k = 7 | h60 | 192 | +56.51 | +509 | +222.0 | **−18.6** | −37.0 ± 26 | 100 / 100 | −41.4 | +8,360 | |

This is the closest miss, and Part 5 takes it apart.

---

## Part 5 — The closest miss: `R15 | fresh earnings AND green @09:35 | h60`

> At 09:35, among the eligible names that **reported earnings since the
> previous close** (an `am` report today or a `pm` report last night) and
> are **up since the open**, buy the one whose report is most recent; sell
> 60 minutes later.

| | |
|---|---|
| tickets | **112** in 448 days (fires on 25% of days; 1.7 candidates on a firing day) |
| $/ticket · total · $/month | **+128.35 · +14,375 · +674** |
| Y1 / Y2 (per ticket, n) | **+145.25 (35) / +120.20 (74)** — both positive |
| aug2026 stub | +397 on 3 tickets |
| months positive · max drawdown · Sharpe | 14 of 22 · −4,657 · 2.69 |
| win rate · median ticket | 55.4% · +$40 |
| best ticket · ex-best total · top-5 share | +1,972 (OSS 2026-08-05) · **+12,403** · 61% |
| distinct names | 73 |
| random on the same slots (30 seeds) | −35.57 ± 25.92 → **100th percentile on total and on ex-best** |
| mirror (fresh AND red) | −57.59 |
| **random among the qualifiers only** (30 seeds, same set, tie-break replaced by a coin) | **+69.82 ± 46.31** |
| monthly | +1,820 −240 +356 +2,932 −1,149 +1,321 +2,045 −1,334 −667 +3,904 −2,027 +28 −1,262 +2,256 −2,949 +3,923 +361 +2,710 +2,784 +410 −1,245 (+397) |

**What is in it, and what is not** (`rule_detail.json`, all at 09:35 h60,
k = 1):

| variant | tickets | $/tkt | Y1 | Y2 |
|---|---|---|---|---|
| fresh earnings only, any colour | 165 | +37.52 | +28.8 | +47.0 |
| **fresh AND green** (the rule) | 112 | **+128.35** | +145.3 | +120.2 |
| fresh AND red | 116 | −29.41 | −91.0 | −2.1 |
| beat AND green (R1) | 95 | +71.24 | +137.0 | +38.8 |
| miss AND green | 33 | +149.44 | +410.3 | −8.6 |
| fresh AND green, `pm` report last night (≥ 4h old) | 93 | **+149.62** | +327.7 | +75.7 |
| fresh AND green, `am` report this morning (< 4h old) | 42 | +12.14 | −201.7 | +40.1 |
| fresh AND green, gap > 0 | 77 | +95.91 | +217.3 | +60.4 |
| fresh AND green, gap ≤ 0 | 58 | +150.59 | +257.5 | +75.8 |
| fresh AND green, ret_since_open > 2% | 74 | +142.24 | +337.6 | +54.1 |
| fresh AND green, ret_since_open ≤ 2% | 63 | +11.51 | +136.1 | −28.0 |
| fresh AND green, no dilution filing in 30d | 111 | +114.27 | +80.2 | +112.6 |

| tie-break among qualifiers (same set, same slots) | $/tkt | Y1 | Y2 | ex-best |
|---|---|---|---|---|
| **most recent report (the rule)** | **+128.35** | +145.3 | +120.2 | +12,403 |
| largest ret_since_open | +101.80 | +212.6 | +65.0 | +8,912 |
| largest gap | +94.17 | +258.6 | +12.4 | +8,419 |
| largest rvol30 | +78.01 | +268.7 | +2.4 | +6,247 |
| largest surprise | +50.98 | +194.5 | −3.4 | +3,582 |
| smallest ret_since_open | +40.97 | +171.8 | −14.1 | +2,461 |
| a coin (30 seeds) | +69.82 ± 46.31 | | | |

And by horizon (same 112 tickets): h15 +52.95 · h30 +36.44 · **h60 +128.35 ·
h120 +139.93 · flatten +130.04** — the money is made between minute 30 and
minute 120, and is *kept* into the close (flat Y2 +151), which is the
opposite of every other configuration in this repo (hold-to-flatten is the
worst exit everywhere else).

**Reading.** The set itself — "reported since the last close and green five
minutes in" — carries ≈ +$70 a ticket over a coin flip among its own members
and ≈ +$105 over the universe; the *surprise* adds nothing (the beat/miss
split goes the wrong way, and the largest-surprise tie-break is the worst
ordering); the engine is **last night's reporters that opened green and are
still green at 09:35**, i.e. a post-announcement intraday continuation that
the 30-minute horizon does not capture and the 60–120-minute horizon does.
It is the only configuration in this line that is positive in both years
on both the total and the ex-best.

**Why it is recorded as the closest miss and not believed as a strategy:**

1. **It is post-hoc.** R1 (beat AND green) was pre-registered; R15 was the
   ablation's suggestion, read after ~100 rule rows had been seen. One
   family reading of that size on 112 draws whose random-control sd is $26
   is a 6.3-sd event on its face, but the family was chosen by the data.
2. **The ordering is worth half of it.** A coin among the qualifiers earns
   +$70 ± 46; the "most recent report" tie-break adds +$58 — 1.3 sd of the
   coin. The set is real; the extra is inside the noise.
3. **It does not scale.** k = 7 (which mostly means "take the second and
   third candidates") drops to +$56.51 with **Y2 −$18.6**; at 10:30 it is
   −$12.67; at 11:00 −$121. The edge lives in one name on one in four
   mornings.
4. **61% of the P&L is five tickets**, the median ticket is $40, and the
   monthly series flips sign 12 times in 22 months.
5. **Against the bar it is 11× short**: +$674/month vs $7,500, and there is
   no breadth to buy — at 112 tickets a year the account is idle three days
   in four.

The `pm`-report subset (+$150/ticket, 93 tickets, Y1 +328 / Y2 +76) is the
natural pre-registered candidate for a paper session: *bought at 09:35 on a
name that reported after yesterday's close and is green since the open,
sold at 10:35*. It is written here so that it is tested once, as stated,
and not re-searched.

