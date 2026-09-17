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

**Verdict: FAIL — Part 9.** The catalyst block moves the out-of-sample IC
by +0.0008 / −0.0038 / −0.0007 (h30 / h60 / h120), inside seed noise; every
model row is negative; the closest miss is a post-hoc one-name earnings rule
at +$674/month, 11× short; the corpus is worth +$21 ± 5 a ticket as a veto on
one-hour holds and nothing elsewhere.

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
chosen name, moves (Part 8).

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

---

## Part 6 — The model: the same ranker with and without the catalyst block

`plan/cat_model.py` — `plan/wn_model.py`'s LightGBM (same parameters, same
label = net $ of the ticket, same monthly walk-forward refit with early
stopping on the last 10% of train days), run three times per horizon with
three seeds on each of six column sets. Scoring starts at 2025-02 so both
halves get an out-of-sample reading (Y1 = 2025-02 → 2025-07, Y2 = 2025-08 →
2026-07; the aug26 stub is 4 days). IC = mean cross-sectional Spearman over
(date, decision) groups of ≥ 10 eligible names; "ex-15:30" drops the 15:30
slot (see the caveat below the table).

### 6.1 The delta — the whole question of this line

| columns | h | OOS IC, all 6 slots (mean ± sd, 3 seeds) | **OOS IC ex-15:30** | Y1 / Y2 (ex-15:30) | 1/day @09:35 $/tkt (3 seeds) | 7/day @09:35 $/tkt | shuffled-label IC |
|---|---|---|---|---|---|---|---|
| base (32 price/volume) | h30 | +0.0790 ± 0.0015 | **+0.0580 ± 0.0016** | +0.057 / +0.059 | −15.39 [−9.6, −28.1, −8.4] | −22.49 | |
| **base + catalyst (169)** | h30 | +0.0794 ± 0.0008 | **+0.0588 ± 0.0011** | +0.056 / +0.061 | −38.20 [−25.9, −54.1, −34.6] | −21.09 | −0.0013 |
| catalyst only (137) | h30 | +0.0149 ± 0.0015 | +0.0122 ± 0.0020 | +0.002 / +0.017 | −39.62 | −26.52 | |
| base | h60 | +0.0570 ± 0.0008 | **+0.0358 ± 0.0009** | +0.034 / +0.037 | −44.21 [−42.9, −33.0, −56.7] | −21.04 | |
| **base + catalyst** | h60 | +0.0546 ± 0.0016 | **+0.0320 ± 0.0026** | +0.025 / +0.035 | −41.97 [−45.1, −58.0, −22.8] | −23.84 | +0.0021 |
| catalyst only | h60 | +0.0085 ± 0.0022 | +0.0078 ± 0.0023 | +0.005 / +0.009 | −55.94 | −27.12 | |
| base + news only | h60 | +0.0572 ± 0.0007 | +0.0359 ± 0.0007 | +0.035 / +0.037 | −45.15 | −27.65 | |
| base + filings only | h60 | +0.0548 ± 0.0019 | +0.0329 ± 0.0019 | +0.025 / +0.037 | −36.20 | −25.54 | |
| base + earnings only | h60 | +0.0562 ± 0.0012 | +0.0341 ± 0.0014 | +0.028 / +0.037 | −48.14 | −26.95 | |
| base | h120 | +0.0470 ± 0.0011 | **+0.0250 ± 0.0013** | +0.018 / +0.029 | −43.30 | −32.52 | |
| **base + catalyst** | h120 | +0.0468 ± 0.0021 | **+0.0243 ± 0.0026** | +0.021 / +0.026 | −70.50 | −27.84 | −0.0008 |
| catalyst only | h120 | +0.0065 ± 0.0021 | +0.0049 ± 0.0029 | +0.009 / +0.002 | −39.49 | −29.17 | |

**IC delta from the catalyst block (base+cat − base, ex-15:30): +0.0008 at
h30, −0.0038 at h60, −0.0007 at h120** — every one inside the seed-to-seed
spread. What each input class bought at h60: news +0.0001, filings −0.0029,
earnings −0.0017. The honest price-only ceiling on this table is **0.036 at
h60 / 0.058 at h30 / 0.025 at h120**, and the catalyst corpus moves none of
them. The catalyst block *alone* does carry a small, real signal (h30
+0.012; t ≈ 2.7 at h60; the shuffled-label control sits at 0.000 ± 0.002),
but it is a fifth of the price block's and, once the price block is present,
redundant.

Where the trees put it: in the base+cat h60 model the top-16 columns by gain
are all price/volume (`tod`, `sic2`, `xs_breadth`, `bar_range5`, `rvol30`,
`log_dv5`, …); the first catalyst column is `days_since_earn` at #17 and
`hrs_since_fil` at #25. No count column and no surprise column reaches the
top 25 on any seed. Early stopping chose 2–68 rounds per fold with the block
and 1–111 without — the same "label is noise at this resolution" reading
`widenet-audit.md` Part 3.1 recorded.

### 6.2 Per decision time (h60, IC, mean of 3 seeds)

| columns | 09:35 | 10:00 | 10:30 | 11:00 | 13:00 | 15:30 |
|---|---|---|---|---|---|---|
| base | 0.0225 | 0.0187 | 0.0360 | 0.0335 | 0.0680 | 0.1645 |
| base + catalyst | 0.0156 | 0.0134 | 0.0338 | 0.0368 | 0.0606 | 0.1682 |
| catalyst only | 0.0086 | 0.0046 | 0.0095 | 0.0141 | 0.0021 | 0.0124 |

At 09:35 — where 5.5% of the rows have a fresh article and 1.9% a fresh
report — the block *lowers* the IC (0.0225 → 0.0156). The "IC" of 0.16 at
15:30 is not alpha and is excluded from every headline number: at 15:30 a
30-minute horizon already exits after 16:00, so h30 / h60 / h120 there are
all **forced flattens at the day's last print through the extended-hours
ladder** (mean label −$73.63 vs −$15.88 at 13:00 h60), and the ranker is
predicting which names will print after the bell and pay 60 bps — cost,
not return. The mandate's 15:30 slot is therefore only honestly readable at
h15 here (−$24.84 unconditional); CLOSE-MOMENTUM's engine with stated-bar
exits (15:50/15:55/15:59) is the right tool for that slot and its answer
stands.

### 6.3 Every configuration against the bar (flat 10 bps/side)

| config | tickets | total | $/tkt | $/month | Y1 $/tkt (n) | Y2 $/tkt (n) | months + | ex-best | maxDD | pct total / ex-best | random ± sd | inverted | foresight $/tkt · $/mo | aug26 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base h30, 1/day@09:35 | 379 | −3,646 | −9.62 | −202 | −33.23 (124) | +0.42 (251) | 6/19 | −5,591 | −9,218 | 90 / 90 | −28.30 ± 11.2 | −26.55 | +702 · +14,750 | +370 (4) |
| **base+cat h30, 1/day@09:35** | 379 | −9,818 | −25.91 | −544 | −11.74 (124) | −35.78 (251) | 7/19 | −11,354 | −14,359 | 63 / 60 | −28.30 ± 11.2 | −30.04 | +702 · +14,750 | +618 (4) |
| base h30, 7/day@09:35 | 2,653 | −48,212 | −18.17 | −2,671 | −22.58 (868) | −18.46 (1,757) | 6/19 | −50,158 | −53,272 | 93 / 93 | −26.01 ± 4.9 | −30.13 | +360 · +52,849 | +3,819 (28) |
| base+cat h30, 7/day@09:35 | 2,653 | −54,712 | −20.62 | −3,032 | −36.18 (868) | −14.86 (1,757) | 4/19 | −56,658 | −58,472 | 87 / 87 | −26.01 ± 4.9 | −22.69 | +360 · +52,849 | +2,799 (28) |
| base h60, 1/day@09:35 | 379 | −16,266 | −42.92 | −901 | −17.52 (124) | −60.63 (251) | 8/19 | −19,346 | −18,276 | 20 / 20 | −28.75 ± 14.5 | −40.44 | +867 · +18,199 | +1,124 (4) |
| **base+cat h60, 1/day@09:35** | 379 | −17,105 | −45.13 | −948 | −15.52 (124) | −70.19 (251) | 7/19 | −20,185 | −25,632 | 20 / 7 | −28.75 ± 14.5 | −54.67 | +867 · +18,199 | +2,437 (4) |
| base h60, 7/day@09:35 | 2,653 | −55,674 | −20.99 | −3,085 | −10.96 (868) | −33.88 (1,757) | 8/19 | −58,754 | −80,740 | 87 / 87 | −26.94 ± 5.1 | −46.87 | +447 · +65,749 | +13,359 (28) |
| base+cat h60, 7/day@09:35 | 2,653 | −59,571 | −22.45 | −3,301 | −28.43 (868) | −27.92 (1,757) | 7/19 | −62,809 | −81,764 | 83 / 83 | −26.94 ± 5.1 | −41.76 | +447 · +65,749 | +14,169 (28) |
| base h120, 7/day@09:35 | 2,653 | −106,546 | −40.16 | −5,904 | −17.93 (868) | −54.64 (1,757) | 4/19 | −110,275 | −116,061 | 10 / 10 | −32.46 ± 5.6 | −45.25 | +515 · +75,743 | +5,017 (28) |
| base+cat h120, 7/day@09:35 | 2,653 | −68,713 | −25.90 | −3,807 | −6.17 (868) | −40.98 (1,757) | 5/19 | −72,442 | −80,208 | 87 / 87 | −32.46 ± 5.6 | −52.06 | +515 · +75,743 | +8,638 (28) |
| catalyst-only h60, 1/day@09:35 | 379 | −8,884 | −23.44 | −492 | −20.43 (124) | −23.56 (251) | 8/19 | −11,013 | −9,928 | 60 / 60 | −28.75 ± 14.5 | −37.32 | | −438 (4) |
| catalyst-only h60, 7/day@09:35 | 2,653 | −72,635 | −27.38 | −4,025 | −27.18 (868) | −30.62 (1,757) | 4/19 | −75,873 | −81,141 | 47 / 47 | −26.94 ± 5.1 | −30.33 | | +4,758 (28) |
| base+cat h60 **SHUFFLED labels**, 1/day@09:35 | 379 | −8,278 | −21.84 | −459 | −21.87 | −32.51 | 8/19 | −9,955 | −12,169 | 63 / 63 | −28.75 ± 14.5 | −9.54 | | +2,595 (4) |
| base+cat h60 SHUFFLED, 7/day@09:35 | 2,653 | −60,207 | −22.69 | −3,336 | −26.12 | −26.35 | 6/19 | −63,334 | −71,602 | 83 / 83 | −26.94 ± 5.1 | −26.61 | | +8,753 (28) |
| base h60, 1/day@13:00 | 379 | −5,789 | −15.27 | −321 | −12.61 | −17.58 | 6/19 | −6,787 | −6,639 | 47 / 50 | −13.27 ± 6.7 | +8.07 | +356 · +7,468 | +187 (4) |
| base+cat h60, 1/day@13:00 | 379 | −9,250 | −24.41 | −513 | −15.50 | −29.94 | 5/19 | −10,259 | −10,751 | 7 / 3 | −13.27 ± 6.7 | −12.66 | +356 · +7,468 | +187 (4) |

**Not one model row is positive**, with or without the block. The seven-a-day
rows are the only ones that reliably beat their random control (87–93rd
percentile, +$4–8 per ticket, exactly the "real but tiny skill" WIDE-NET
measured) and they lose $2,700–$5,900 a month to the toll. The one-a-day row
swings by $50 per ticket between seeds of the same model (h60: −$42.9,
−$33.0, −$56.7) — at 379 tickets the single pick is noise, which is why the
mandate's "control percentile" on that row is meaningless in both
directions (20th with the block, 90th without at h30, 0th–97th across
seeds). The shuffled-label model lands on the random pick (IC 0.002, −$21.84
vs −$28.75 random, 63rd pct) and the inverted score loses on every row, so
the harness is clean. Foresight at 7/day h60 is **+$447/ticket,
+$65,749/month** — the bar is 11% of omniscience on this table.

### 6.4 The block as a veto (`plan/cat_veto.py`)

The bucket tables' information is on the negative side, so the honest use
of the corpus in a long-only book is refusal. Base (price-only) h60 seed-0
scores, re-picked after dropping every name a flag marks, against a 30-seed
random pick on the SAME vetoed universe:

| veto (trailing) | 1/day@09:35 $/tkt | Δ vs unvetoed | random on vetoed universe | edge vs random | 7/day@09:35 $/tkt | Δ | 1/slot all decs $/tkt | Δ |
|---|---|---|---|---|---|---|---|---|
| none | −42.92 | — | −28.67 | −14.25 | −20.99 | — | −26.15 | — |
| 8-K 5.02 in 3d | −42.36 | +0.56 | −28.70 | −13.66 | −19.82 | +1.17 | −25.57 | +0.58 |
| Form 4 sale in 3d | −40.26 | +2.66 | −28.98 | −11.28 | −18.28 | +2.71 | −24.51 | +1.64 |
| analyst headline in 3d | −36.29 | +6.63 | −29.55 | −6.74 | −23.01 | −2.02 | −25.83 | +0.32 |
| fresh earnings | −40.28 | +2.64 | −28.65 | −11.63 | −17.97 | +3.02 | −23.80 | +2.35 |
| 10-Q/10-K in 18h | −22.71 | +20.21 | −28.32 | +5.61 | −15.83 | +5.16 | −20.69 | +5.46 |
| 8-K 7.01 in 18h | −16.68 | +26.24 | −28.74 | +12.06 | −19.66 | +1.33 | −20.32 | +5.83 |
| dilution filing in 30d | −31.63 | +11.29 | −27.75 | −3.88 | −17.40 | +3.59 | −23.78 | +2.37 |
| any catalyst in 18h | −32.21 | +10.71 | −27.89 | −4.32 | −18.64 | +2.35 | −23.13 | +3.02 |
| earnings scheduled today/tomorrow | −51.91 | −8.99 | −27.33 | −24.58 | −17.79 | +3.20 | −29.83 | −3.68 |
| **any of {5.02, Form 4 sale, analyst, 10-Q} in 3d** | **−15.54** | **+27.38** | −29.96 | +14.42 | **−13.52** | +7.47 | −21.37 | +4.78 |

The composite veto is the largest single improvement the corpus produces:
+$27 per ticket on the one-a-day pick and +$7.47 on seven-a-day (about
+$1,100/month at 7/day), in both years (Y1 −3.6 / Y2 −28.8 vs −17.5 / −60.6).
It is real — the vetoed universe's random pick does not move, so the gain is
selection, not universe shrinkage — and it leaves every row negative: the
best vetoed configuration is **−$13.52/ticket, −$1,988/month**.

**Across seeds and horizons** (`veto.json`, composite veto {8-K 5.02, Form 4 sale, analyst headline, 10-Q in 3d}):

| h | pick | seeds | vetoed $/tkt (mean) | Δ vs unvetoed (mean [per seed]) | edge vs random on vetoed universe | Y1 / Y2 $/tkt |
|---|---|---|---|---|---|---|
| h30 | 1/day@09:35 | 3 | -14.51 | +0.88 [-2.3, +7.6, -2.7] | +10.71 | -27.7 / -11.9 |
| h30 | 7/day@09:35 | 3 | -21.20 | +1.29 [+0.9, +3.0, -0.1] | +2.79 | -26.8 / -20.5 |
| h30 | 1/slot all decs | 3 | -17.36 | -0.07 [-0.5, +1.4, -1.1] | +15.06 | -19.2 / -17.4 |
| h60 | 1/day@09:35 | 3 | -23.11 | +21.10 [+27.4, +16.7, +19.2] | +6.85 | -16.3 / -33.6 |
| h60 | 7/day@09:35 | 3 | -17.66 | +3.38 [+7.5, +1.4, +1.3] | +8.37 | -16.1 / -24.7 |
| h60 | 1/slot all decs | 3 | -17.83 | +5.08 [+4.8, +6.4, +4.1] | +13.92 | -8.2 / -23.7 |
| h120 | 1/day@09:35 | 3 | -47.13 | -3.83 [-1.8, -3.0, -6.7] | -9.95 | -12.2 / -73.3 |
| h120 | 7/day@09:35 | 3 | -35.13 | -2.60 [+0.8, -1.6, -7.0] | -2.90 | -14.6 / -49.7 |
| h120 | 1/slot all decs | 3 | -17.30 | +2.66 [+1.9, +0.4, +5.7] | +14.97 | -17.8 / -18.5 |

**The veto is an h60 result.** At h60 it holds on all three seeds (1/day +$17 to +$27, 7/day +$1 to +$7, 1/slot +$4 to +$6); at h30 it is worth nothing (−$3 to +$8, mean ≈ 0); at h120 it is *negative* on every pick (−$2 to −$7). The bucket table that suggested it was dominated by hold-to-flatten rows, and the flags mark names whose losses arrive in the first hour and mean-revert after — so the refusal helps a one-hour hold and hurts a two-hour one. The s0/h60 numbers quoted above are the best case, not the typical one; the honest summary is **+$21 ± 5 per ticket on the one-a-day h60 pick, +$3 ± 3 on seven-a-day, zero or worse elsewhere.**

---

## Part 7 — The gapper pool arm: run as asked, not a result

`table_gap.npz` (the +10% pool under `RS_CROSS`, 2,836 symbols, 41,908 rows
at 10:00/11:00/13:00/15:30, 24,007 live) with the same block, same
walk-forward, `model_results_gap.json`:

| columns | fill → exit | scored cross-sections (≥ 10 names) | IC | 7/day $/tkt | random 7/day | 1/day $/tkt | foresight 7/day |
|---|---|---|---|---|---|---|---|
| base | 10:00 → 12:00 | 4 | +0.171 | +466 | **+160** | −326 | +2,881 |
| base+cat | 10:00 → 12:00 | 4 | +0.153 | +450 | +160 | +2,116 | |
| base | 11:00 → 13:00 | 8 | +0.143 | +430 | **+262** | +333 | +977 |
| base+cat | 11:00 → 13:00 | 8 | +0.147 | +380 | +262 | +311 | |
| base | 13:00 → 15:00 | 10 | +0.084 | +86 | −64 | +46 | +507 |
| base+cat | 13:00 → 15:00 | 10 | +0.058 | +85 | −64 | +11 | |
| base | 15:30 → 15:59 | 52 | +0.085 | −30 | −75 | −85 | +387 |
| base+cat | 15:30 → 15:59 | 52 | +0.080 | −14 | −75 | −120 | |

Four things make it unreadable, all inherited from CLOSE-MOMENTUM Part 6 and
none fixable by a catalyst column: the **random control is +$160 to +$344 a
ticket** at 10:00–11:00 (membership is conditioned on the day's own high, so
buying anything in the pool "wins"); a walk-forward needs 5,000 training
rows and the pool reaches that only late, so **Y1 has no out-of-sample row**
and only 4–52 cross-sections ever have ten names to rank; the one-a-day
numbers swing from −$1,341 to +$2,645 between column sets on the same slot
(a lottery, not a ranking); and 94% of the pool is not halal-PASS. The
catalyst delta on this arm is noise on top of noise; it is reported because
the mandate asked, and it changes nothing.

---

## Part 8 — The honesty battery

| check | result |
|---|---|
| **poison — bars** (garbage on every 1-minute bar strictly after the cut, price block rebuilt through `rl2.features.compute_day` + `wn_table.day_block`; 12 days × 6 cuts) | **144 array checks, 0 mismatches** on all 32 columns + the causal gate |
| **poison — events** (every article / filing / earnings report / Form 4 / sentiment record after the decision instant deleted and replaced by random-class garbage inside the next 60 days — **1,520,884 events removed, 462,441 added** over the trials; catalyst block rebuilt through `cat_events.features_for`) | **72 block checks, 0 mismatches** on all 137 columns |
| **poison — picks** (top-1 AND top-7 of a fitted base+cat ranker at every decision ≤ the cut, clean vs poisoned) | **504 pick checks, 0 mismatches** |
| **direction** — the label must move (it prices minute m+1 onward) and the catalyst block must move at decisions AFTER the cut (the garbage has to be visible where it is allowed) | label moved **72/72**; catalyst block moved **60/60** |
| **shuffled labels** (permuted within each train day, 300 rounds) | IC −0.0013 / +0.0021 / −0.0008 at h30/h60/h120; 1/day −$21.84 = the random pick (63rd pct) |
| **inverted score** | negative on every model row (e.g. −$54.67 vs −$45.13 at h60 1/day; −$46.87 vs −$20.99 at 7/day) |
| **random, 30 seeds, same slots** | −$26 to −$36/ticket depending on horizon; every configuration's percentile is in 6.3 and `rules.json` |
| **foresight** (score = the ticket's own realised net P&L) | +$447/ticket, +$65,749/month at 7/day h60; +$867 at 1/day — the harness can learn; the bar is 11% of it |
| **identity of fills / labels** | inherited byte-for-byte from `plan/wn_table.day_block` (poison-tested 96/0 and pick-tested 816/0 in WIDE-NET); only the decision grid differs |
| **defects found and recorded** | (1) duplicate column name `earn_fresh` (wide-net RH-calendar flag vs the catalyst flag) — LightGBM refused it; renamed `earn_fresh_ev`, every table rebuilt; (2) exit keys with `:`/`->` are not legal Windows filenames — score files renamed; (3) the 15:30 slot's h30/h60/h120 labels are extended-hours flattens (6.2) — excluded from every headline IC; (4) `num_threads=8` was 7× slower than 1 thread on this 4-core host shared with two other agents' jobs — one thread throughout |

### 8.1 Measured cost (COST-REBASE's module as it stands; not landed)

COST-REBASE has no NOTES section and no index row at the time of this run,
so **the flat 10 bps/side ladder is the headline** and the measured number
is secondary, computed with `plan/cr_cost.CostModel` exactly as the module
stands (per-fill half-spread = max of HL2 / Corwin-Schultz / Abdi-Ranaldo on
trailing windows ending strictly before the fill minute, plus a square-root
impact term at Y = 1.0, floored at 1 bp, legacy 10 bps where the 1-second
tape is absent):

| config | tickets | flat 10 bps $/tkt | **measured $/tkt** | flat $/month | **measured $/month** | mean bps in / out | tape tier mix |
|---|---|---|---|---|---|---|---|
| base h30, 1/day@09:35 | 379 | −9.62 | −76.06 | −202 | −1,597 | 50.0 / 33.6 | win 620 · prior 16 |
| base+cat h30, 1/day@09:35 | 379 | −25.91 | −90.87 | −544 | −1,908 | 48.7 / 34.6 | win 612 · prior 16 |
| base h30, 7/day@09:35 | 2,653 | −18.17 | −65.48 | −2,671 | −9,626 | 43.3 / 31.3 | win 3,883 · prior 91 |
| base+cat h30, 7/day@09:35 | 2,653 | −20.62 | −69.63 | −3,032 | −10,236 | 43.4 / 32.3 | win 3,923 · prior 95 |
| base h60, 1/day@09:35 | 379 | −42.92 | −110.17 | −901 | −2,314 | 50.7 / 23.1 | win 686 · prior 4 |
| base+cat h60, 1/day@09:35 | 379 | −45.13 | −114.65 | −948 | −2,408 | 49.6 / 24.9 | win 679 · prior 7 |
| base h60, 7/day@09:35 | 2,653 | −20.99 | −69.95 | −3,085 | −10,282 | 44.0 / 23.6 | win 4,233 · prior 59 |
| base+cat h60, 7/day@09:35 | 2,653 | −22.45 | −73.76 | −3,301 | −10,843 | 45.2 / 23.9 | win 4,280 · prior 58 |
| R1 beat AND green @09:35 h60 | 95 | +71.24 | **−38.21** | +317 | −170 | 70.2 / 24.3 | win 188 |
| R1b beat AND green @10:00 h60 | 103 | +77.28 | +22.92 | +373 | +111 | 38.1 / 19.3 | win 200 |
| **R15 fresh AND green @09:35 h60** | 112 | **+128.35** | **+0.54** | **+674** | **+3** | **75.8 / 30.5** | win 222 |
| R15 fresh AND green @09:35 h120 | 112 | +139.93 | +16.49 | +735 | +87 | 75.8 / 27.7 | win 222 |
| R15b fresh AND green @10:00 h60 | 122 | +79.15 | +16.95 | +453 | +97 | 41.8 / 23.0 | win 234 |

Every ticket found its 1-second tape ("win" tier; a handful fell back to
the prior session's median, none to the legacy 10 bps). The model rows go
from −$3,000 to −$10,000 a month. **The closest miss goes from +$674 to
+$3 a month**: a name that reported last night and is green at 09:35 is
exactly the name whose first five minutes are the most volatile relative
to its trailing dollar volume, and the impact term charges it 76 bps on
the way in.

At 09:36 the module's impact term reads the first five minutes of tape and
charges **~50 bps on entry** (opening volatility × a small trailing dollar
volume) against ~20 bps on the exit an hour later — i.e. it prices the open
2–5× *above* the flat ladder, the opposite direction from what
UNIVERSE+QUOTES measured for the inside spread (2–6 bps). Whether that
impact calibration is right is COST-REBASE's question; here it only makes
every number worse, so the verdict is conservative under both ladders.

---

## Part 9 — Verdict, the closest miss, what each input bought, and what next

### Verdict: **FAIL.**

The mandate's question was whether a genuinely new input set moves the IC
ceiling. It does not. On the same table, the same ranker, the same fills
and the same toll, **137 causal catalyst columns change the out-of-sample
IC by +0.0008 / −0.0038 / −0.0007 at h30 / h60 / h120** — inside the
seed-to-seed spread of ±0.001–0.003 — and change the $/ticket of the chosen
name by amounts that flip sign between seeds. The block on its own carries
a real but small signal (IC 0.005–0.012, t ≈ 2.7) that is already inside
the price block. Every model configuration is negative; the best of them
(base+cat h30, seven a day) is −$20.62/ticket, −$3,032/month, 87th
percentile against random, i.e. skill worth $5 a ticket against a $30 toll.
Nothing passes; the index bar needs ≥ $7,500/month, both years positive,
≥ 90th percentile on total and ex-best.

The catalyst corpus is not worthless — as a **veto** it is worth **+$21 ± 5
a ticket on the one-a-day h60 pick and +$3 ± 3 on seven-a-day** across
three seeds (6.4; s0 read +$27 / +$7.47), which is the largest single
improvement any input has produced on this universe since the honest
harness landed — but only at the one-hour horizon (≈ 0 at h30, negative at
h120), and a veto cannot make a negative book positive: the best vetoed row
is −$13.52/ticket.

### The closest miss

**`R15 | fresh earnings AND green since the open @09:35 | exit 10:35`**
(Part 5): 112 tickets in 448 days, **+$128.35/ticket, +$14,375 total,
+$674/month**, Y1 +$145 / Y2 +$120, 14 of 22 months positive, Sharpe 2.69,
ex-best +$12,403, 100th percentile on total and on ex-best against 30
random seeds on the same slots (−$35.57 ± 25.92), mirror (fresh AND red)
−$57.59, aug2026 +$397 on 3 tickets. Under the measured cost ladder:
**+$0.54/ticket, +$3/month** (the impact term charges its entries 76 bps; the 10:00 variant keeps +$17/ticket, +$97/month). It needs to be **11× larger** and it cannot be widened —
the second candidate on a firing day is worth −$19 in Y2 (k = 7: +$56.51,
Y2 −$18.6), 10:30 is −$12.67, 11:00 is −$121. It is **post-hoc** (the
pre-registered R1 "beat AND green" is +$71.24/ticket, +$317/month, Y2
+$38.79; the ablation said the beat was the wrong half), half of it is the
ordering among ~1.7 candidates (a coin among the qualifiers earns +$69.82 ±
46.31), five tickets are 61% of it, and the engine is *last night's*
reporters that opened green (+$149.62, n = 93) rather than this morning's
(+$12.14, n = 42). It is recorded as the natural pre-registered candidate for
a paper session — **buy at 09:35 the name that reported after yesterday's
close and is green since the open; sell at 10:35** — to be tested once, as
stated, and not re-searched.

### What each input class bought

| input class | IC delta at h60 (base+X − base, ex-15:30) | best bucket / rule it produced ($/month, k = 1) | as a veto (Δ $/tkt, 1/day h60, seed 0) |
|---|---|---|---|
| news (16 classes, PR flag, sentiment, recency) | **+0.0001** | analyst / M&A / FDA / index / sentiment rules all ≤ random; best +$0 | analyst headline in 3d: +$6.63 |
| EDGAR filings (8-K items, 424B/S-3/S-1, 13D/G, Form 4 direction, 144) | **−0.0029** | 8-K 1.01 in 18h @09:35 h120: +$17/tkt, t = 0.2; R8 (13D) −$689/mo; R6 (dilution) −$498/mo | 8-K 7.01 in 18h: +$26.24; 10-Q in 18h: +$20.21; composite {5.02, Form 4 sale, analyst, 10-Q}: **+$27.38** |
| earnings (RH results + timing, surprise sign/size) | **−0.0017** | **R15 +$674/mo**, R1 +$317/mo (both one-a-day, ~25% of days); every "beat" rule beyond 10:00 negative | fresh earnings: +$2.64 |
| all 137 together | **−0.0038** | — | — |

The surprise itself bought nothing (the largest-surprise ordering is the
worst of six tie-breaks; "beat" is worse than "any report"); the *timing* of
the report bought the closest miss; the filings bought the vetoes; the news
feed bought nothing measurable, which is consistent with 5.5% of decision
rows having any article in the trailing 18 hours and the two largest
press-release wires being absent from it.

### Why this input set cannot do what was asked of it

1. **Sparsity.** A cross-sectional ranker over ~60 names sees a fresh
   catalyst on ~4 of them. The IC is a property of the *whole* cross-section;
   a feature that is zero on 93% of rows can reorder at most the 7% and its
   IC contribution is bounded by that share times its within-subset
   correlation. That bound is ≈ 0.01, which is what `cat`-only measured.
2. **The feed.** Two commentary sites, one of three press-release wires, no
   Reuters/Bloomberg/Dow Jones, and a "legal" class that is mostly law-firm
   solicitation. The catalysts that move small caps at the open — the 07:00
   press release on Business Wire, the pre-market analyst note — are largely
   not in it.
3. **The direction of the information is negative.** Everything with |t| > 2
   says "do not buy this"; a long-only $15k-ticket account can only decline,
   and declining moves a −$21 book to −$13.
4. **The earnings signal is a one-name, one-hour, one-in-four-days event.**
   It is the only thing here that was positive in both years, and at 112
   tickets a year it is 11× short even before its post-hoc discount.

### Ranked next ideas

1. **Paper-test R15 as pre-registered above, once.** Fifteen to twenty live
   firings decide whether the +$150/ticket `pm`-reporter subset is a real
   post-announcement continuation or a 93-draw artefact. Cost: one paper
   session rule, zero new code. It is the only positive, both-years,
   100th-percentile object this line produced.
2. **Use the composite veto in the live rules — for one-hour holds only.**
   Refusing any name with an 8-K 5.02, a Form 4 sale, an analyst headline
   or a 10-Q/10-K in the trailing 3 days is causal, free, and worth +$21 ± 5
   a ticket on the one-a-day h60 pick (three seeds), ≈ 0 at h30 and
   negative at h120. It will not make C37 positive; it will make its
   one-hour tickets less negative, and `data/filings_hist/` +
   `plan/cat_events.features_for` can compute it at 09:34 from EDGAR's live
   submissions feed.
3. **Do not buy a bigger news feed expecting the IC to move.** The corpus
   was thin, but the arithmetic in "why" (1) says even a complete feed
   changes at most the 7% of rows that carry a catalyst; the ceiling of a
   catalyst *count* feature set on a 60-name cross-section is ≈ 0.01–0.02.
   What a full-text feed *could* change is the quality of the one-name
   earnings/PR pick (idea 1), not the ranker.
4. **Stop adding columns to the wide-universe ranker.** Five lines now
   (WIDE-NET 0.033, UNIVERSE+QUOTES 0.033, RL-v2 ~0, CLOSE-MOMENTUM
   0.016–0.024, this line 0.036 at h60 / 0.058 at h30) measure the same
   ceiling with five different input families. The next line that wants to
   move it needs an input that is dense across the cross-section every
   morning — the order book and options flow WIDE-NET named — or a
   different objective than the daily cross-section altogether.
5. **The 15:30 slot needs the CLOSE-MOMENTUM engine, not this table.** Any
   horizon ≥ 30 minutes from 15:30 is an extended-hours flatten here, and a
   ranker will happily "predict" the 60 bps toll (IC 0.16). Nothing in
   6.2's 15:30 column should ever be quoted as alpha.

### Files

| | |
|---|---|
| `plan/cat_lib.py` | paths, symbol lists, taxonomy, event clock |
| `plan/cat_news.py` · `plan/cat_edgar.py` | resumable corpus fetchers (Polygon news; EDGAR submissions + Form 4 XML) |
| `plan/cat_events.py` | event corpus, coverage report, `features_for` (the causal feature function) |
| `plan/cat_table.py` | the 163,254-row ticket table (+ gapper arm) on `wn_table.day_block` |
| `plan/cat_buckets.py` | 2,768 bucket rows; 14 pre-registered rules + the R15 family |
| `plan/cat_model.py` | walk-forward LightGBM on six column sets, IC, picks, controls; gapper arm |
| `plan/cat_veto.py` | the block as a veto; R1/R15 ticket-level detail, tie-break and set ablations |
| `plan/cat_poison.py` | bars + events + picks poison test |
| `plan/cat_cost.py` | measured-cost repricing (COST-REBASE module, not landed) |
| `data/news_hist/`, `data/filings_hist/` | the caches (gitignored) |
| `data/massive/cat/` | `events.pkl`, `table*.npz`, every JSON/NPY/log quoted here |
