# HALAL-GATE-REVIEW — 2026-09-17

**User question:** *"our halal gate is too extreme — 415 armable names is too few,
something must be wrong. Let's analyze it."*

**Short answer: the instinct is right, but only about a third of the shortfall is
a defect.** The 415 is not 415-out-of-10,761. It is **415 out of 4,590 actual
common stocks** — the other 6,171 symbols in the "universe" are ETFs, closed-end
funds, structured products, preferreds and ETNs that `clean_ticker` lets in on
ticker shape alone and that of course have no company statements. Against the
real denominator the gate arms **9.0%** of US common equity, not 3.9%.

Of the remainder, three causes account for essentially everything:

| cause | names | is it what the user asked for? |
|---|---|---|
| **strict 10/10/20** (the user's own choice, 3× stricter than AAOIFI) | **2,693** refused on a ratio leg | **YES — deliberate.** 210 of the 456 names professional screens pass are refused *only* because a leg sits in the 10–33 band those screens allow |
| **"a missing row is never a zero"** applied to ONE table | **376** refused as `unverified` | **NO — over-applied.** The gate read the newest yfinance quarterly column and nothing else. AAPL, LLY, ISRG, ANET, MRVL were refused for rows that are in the annual statement, in an older column, or in EDGAR |
| **the 5% interest leg with no interest tag** | 238 of those 376 | **NO — provable.** 15 of the 16 large names in that bucket tag **no interest concept in any EDGAR period**, because the line is immaterial. Immaterial is provable, not unverifiable |

**A doctrinal change was ruled and landed the same day** (user, 2026-09-17: *"For
the missing statement, use the last available statement or check the Zoya
website. Do not just reject it. Same for data drift."*). Results in §6.

Read-only tools written for this review: `plan/hgr_meta.py`, `plan/hgr_funnel.py`,
`plan/hgr_bench.py`, `plan/hgr_screeners.py` (and the one-shot source patches
`plan/hgr_patch1.py`, `hgr_patch2.py`, `hgr_patch3.py`, kept for provenance).

---

## 1. THE DENOMINATOR — what is actually being screened

`plan/build_halal_universe.py::universe()` takes the latest grouped-daily tape,
keeps every symbol that is alphabetic, ≤5 characters, does not end in W/U/R, and
closed ≥ $2. That is a filter on **ticker shape and price, not on what the
listing IS.** Polygon's reference endpoint (`plan/hgr_meta.py`, 10,718 of the
10,761 symbols resolved) says what they are:

| Polygon `type` | n | in the halal universe? |
|---|---:|---|
| **ETF** | 5,266 | should never have been |
| **CS** (common stock) | 4,294 | yes |
| FUND (closed-end) | 329 | should never have been |
| **ADRC** | 296 | yes |
| SP (structured product) | 122 | no |
| ETS / ETV / ETN | 236 | no |
| PFD (preferred) | 63 | no |
| UNIT / WARRANT | 7 | no |
| (unresolved) | 148 | — |

> **COMMON EQUITY = CS + ADRC = 4,590. Everything else = 6,171 symbols, 57% of
> the "universe", that no company-fundamentals gate can ever evaluate.**

### The funnel (the gate's own return order — the first test to fire wins)

| step | ALL 10,761 | CS+ADRC only (4,590) | rule or data? |
|---|---:|---:|---|
| haram-industry keyword | 700 | 695 | **RULE** |
| SIC 6000–6999 | 97 | 92 | **RULE** |
| user / external FAIL ruling | 35 | 29 | **RULE** |
| market cap missing | 7 | 7 | DATA |
| **no fundamentals at all** | **6,068** | **150** | DATA |
| missing statement row (`unverified`) | 376 | 286 | DATA → made a RULE |
| revenue-mix unverifiable (alcohol/grocer/hotel…) | 317 | 314 | DATA → made a RULE |
| ratio `LOAN>10` | 1,993 | 1,861 | **RULE** |
| ratio `CASH>10` | 700 | 695 | **RULE** |
| `HARAM>=5%` TTM | 53 | 52 | **RULE** |
| **ARMABLE** | **415** | **409** | |

**This is the single most important row in the review:** of the 6,068 "NO
FUNDAMENTALS DATA" refusals, **5,918 are not common stock** (5,259 ETFs, 136
closed-end funds, 121 structured products, 105 ETS, 85 ETV, 63 preferreds, 41
ETNs). Only **150 are common equity**, and 148 of those do have an EDGAR extract
on disk. The "56% of the universe is refused for lack of data" headline from the
2026-09-16 audit is, to ~97%, the universe containing things that are not
companies.

**Rule vs data, honestly split, on the 4,590 common stocks:**

* **3,444 refused by a RULE** (industry 695 + SIC 92 + rulings 29 + ratios 2,608
  + 5% leg 52 + revenue-mix 314 — counting revenue-mix as a rule because
  "unverified is haram" is the user's 2026-08-22 ruling).
* **443 refused for a DATA REASON** (no fundamentals 150 + missing row 286 +
  no market cap 7).
* **415 pass.**

So: **the gate is not mostly starving for data on real companies. It is doing
exactly what the 10/10/20 rule says, on 2,608 of them.**

### One caveat the funnel must carry

2,231 of those ratio refusals still hold a **PRE-FIX verdict string**
(`LOAN>10+COMBINED>20`, `CASH>10+COMBINED>20`) from the 2026-09-01 build: the
2026-09-16 rebuilds only re-screened names that could still PASS. They all fail
`combined ≤ 20` under both gates, so the verdict is safe, but the universe file
is a **mixture of two gate epochs** and any count taken from it inherits that.

---

## 2. WHICH RULE BITES MOST — and is it the user's intent?

The 1,260 → 415 removals, from `data/halal_flips_2026-09-16.json`
(v1, 867 names) as re-counted after the interest-leg refinement (845):

| cause | v1 | v2 (final) | verdict on intent |
|---|---:|---:|---|
| missing-row refusal | 337 | 338 | **over-applied — fixed today** |
| strict-10 (`LOAN>10` or `CASH>10`) | 275 | 365 | **intended** |
| SIC 6000–6999 | 86 | 86 | **mostly intended, 4 false positives** |
| TTM 5% haram | 79 | 43 | intended |
| strict-10, also fails the OLD gate on today's data (drift) | 75 | — | **data drift, not doctrine** |
| no fundamentals / no market cap | 11 | 11 | data |
| user ruling (TPCS, CTW) | 2 | 2 | intended |

### (a) The missing-interest-row refusal — the largest defect

The rule "an absent statement row is never a zero" is right. **Applying it to one
table was not.** `halal_check` read the newest columns of
`t.quarterly_balance_sheet` / `t.quarterly_income_stmt` and refused on anything
absent there — never consulting the annual statement, an older quarterly column,
or EDGAR (except for the interest leg, which got its ladder on 2026-09-16).

30 largest names removed under `missing-row` (market caps from Polygon):

| SYM | mcap | what was "missing" | is the company actually unverifiable? |
|---|---:|---|---|
| AAPL | $4,851bn | interest income | no — restored 2026-09-16 by the non-operating bound |
| LLY | $1,014bn | interest income | no — same |
| **ANET** | $249bn | **debt** | **no — Arista tags no debt concept because it has none** |
| BHP | $214bn | revenue | no — 20-F filer, revenue is in the annual table |
| RIO | $156bn | revenue | no — same |
| **ISRG** | $135bn | **debt** | **no — same class as ANET** |
| UL | $134bn | revenue | no — 20-F filer |
| SYK | $109bn | interest income | no |
| **MNST** | $87bn | debt/cash (no recent period carries both) | **no — a column-alignment artifact** |
| RELX | $60bn | revenue | no — 20-F filer |
| **FNV** | $50bn | debt | no |
| VEEV | $43bn | interest income | July-quarter filer, see §4 |
| TWLO / CRDO / RDDT / FFIV / NBIX / MANH / CGNX / HNGE | $10–37bn | interest income | no — restored 2026-09-16 |
| UTHR / NXT / MBLY | $7–21bn | debt or debt/cash pair | no |

Quantified for the coordinator's question (a): of the **238 names still refused
for the interest leg** after the 2026-09-16 refinement,

* **86 are not common equity at all** (closed-end bond funds ADX NEA GDV NZF RVT
  CLM TY …, commodity trusts). **Refusing them is the rule working.**
* **16 are common equity ≥ $1bn** — MRVL WELL VEEV SMMT AUR GSAT PRAX URBN MMED
  KNSA TR PAYO EMAT TY AMBQ DMLP.
* **15 of those 16 tag NO interest concept in ANY EDGAR period.** That is not
  an unverifiable company; that is an immaterial line nobody tags.
* 136 are common equity under $1bn.

**Both bounds the coordinator proposed work, and the revenue-denominated one is
the correct one.** The 5% test's denominator is revenue, so
`8%/yr × (cash + securities) < 5% × TTM revenue` **proves** the leg clear whatever
the filer tagged — the same 8%/yr premise the plausibility cap already rests on,
read in the other direction, and generous in the safe direction (a bigger assumed
yield makes the ceiling *higher*, i.e. harder to clear). The mcap-denominated
variant ("cash < 10% of mcap ⇒ interest < 0.8% of mcap") is true but answers a
question the rule does not ask. **Implemented as rung 4, §6.**

### (b) Strict 10/10/20 — which leg binds, and the AAOIFI gap

Across the whole universe, of the names that reach the ratio legs:

| | n |
|---|---:|
| fails only the LOAN leg | 1,114 |
| fails only the CASH leg | 700 |
| fails both | 879 |
| **fails only the cash leg with cash in 10–20%, loan ≤ 10, haram < 5** | **174** |

That 174 is the cash-rich-tech bucket the question asks about: REGN, SE, STM,
ONC, ALNY, ZS, CPRT, RYAAY, INCY, NTNX, LOGI, MLI, CSGP, FIG, ONTO, HUBS, ALGN,
DECK, PINS, ONON, AG, ESTC, MP, GTLB, PATH … Zoya and Musaffa pass all of them;
AAOIFI's line is 33%, not 10%.

**Counterfactual on the cached ratios (ratio legs only, every other screen
unchanged):**

| thresholds | armable |
|---|---:|
| **user 10 / 10 / 20 (today)** | **415** |
| 10 / 10, no combined cap | 415 *(combined ≤ 20 never binds alone)* |
| 20 / 20 / 40 | **884** |
| **AAOIFI 33 / 33 (no combined cap)** | **1,426** |
| 33 / 33 / 66 | 1,426 |

So the user's own ratio choice, and nothing else, costs **1,011 names** versus
the AAOIFI numbers every professional screener uses. **This is a doctrinal
decision, not a bug**, and it is the single biggest lever on the count.

### (c) SIC 6000–6999 — who is caught, and should they be?

104 names in the universe currently fail on the sector screen:

| SIC | description | n | names |
|---|---|---:|---|
| 6199 | Finance Services | 31 | MSTR SOFI CRCL BMNR CHYM RIOT DAVE IOND SII ASST … |
| 6282 | Investment Advice | 20 | BAM TROW PS EVR HLI TPG MAAS VCTR HLNE MC FHI PJT CNS AB |
| 6798 | REITs | 11 | PSA AHR EGP CTRE JAN EARN CMCT … |
| 6211 | Brokers/Dealers | 11 | SCHW BLK IBKR RJF SEIC SF MKTX BULL MIAX … |
| 6792 | Oil Royalty Traders | 8 | **TPL** LB PBT SBR EROK NRT CRT MARPS |
| 6221 | Commodity Contracts | 6 | PHYS PSLV CEF UROY SPPP AAAU |
| 6200 | Exchanges | 5 | CME CBOE TW TOP WTF |
| 6795 | Mineral Royalty Traders | 3 | **RGLD TFPM** VMET |
| 6500 / 6531 | Real Estate | 3 | **TRNO** CHCI AGNT |
| **6794** | **Patent Owners & Lessors** | **2** | **IDCC** RMCO |
| 6324 | Hospital & Medical Service Plans | 1 | CLOV |
| 6022 / 6099 / 6163 | bank / depository NEC / loan brokers | 3 | DAAQ (a SPAC) USIO (payments) NFJ (a fund) |

The user's rule named "banks, lenders, insurers, asset managers, brokers,
REITs, funds". **97 of the 104 are exactly that.** The genuine false positives —
companies that are not financial institutions at all but carry a 6xxx code — are:

* **IDCC (InterDigital)** — SIC 6794 "Patent Owners & Lessors". A wireless-R&D
  licensing company. Not a lender, not an asset manager, not a fund.
* **RGLD / TFPM (Royal Gold, Triple Flag)** — SIC 6795 "Mineral Royalty Traders".
  They buy streams on mines; the income is a share of metal, not interest. HLAL
  and SPUS hold royalty names.
* **TPL (Texas Pacific Land)** — SIC 6792 "Oil Royalty Traders", but ~60% of its
  revenue is water services and surface leasing from land it owns outright.
* **USIO** — SIC 6099, a payment processor, not a depository.
* Arguably **TRNO / CHCI** (SIC 6500/6531, real-estate operators rather than
  REIT trusts) — but a real-estate rental business is a doctrinal question of its
  own, not an obvious mis-code.

Everything else — SOFI, DAVE, CHYM (consumer lending / neobank), MSTR, BMNR,
RIOT, CRCL (treasury/crypto balance-sheet vehicles), SCHW, BLK, IBKR, the
exchanges, the REITs, CLOV — is caught correctly and would be caught by the
user's own words.

**Cost of the false positives: 4–6 names.** The SIC screen is not why 415 is
415.

---

## 3. BENCHMARK AGAINST PROFESSIONAL SCREENS

Sources: `data/halal_external/screener_verdicts.json` (Zoya 6,558 rows, Musaffa
696, 2026-08-22), refreshed today for the sanity list into
`screener_verdicts.2026-09-17.json` (`plan/hgr_screeners.py`), plus US
Shariah-ETF holdings (HLAL, SPUS, SPTE, SPRE — 311 distinct US tickets).
SPWO/UMMA are excluded from the affirming set: they hold non-US listings whose
local tickers collide with US symbols (SOURCES.md's collision guard).

**6,799 symbols in our universe carry external evidence. 456 of them are PASSED
by at least one professional screen.** Our verdicts on those 456:

| our cause | n | reading |
|---|---:|---|
| **PASS** | 133 | agreement |
| **RATIO, leg inside the 10–33 band** | **210** | **intended divergence — the user's stricter number** |
| RATIO, blown past 33 | 38 | we and they should agree; see the note below |
| CLASS revenue-mix (alcohol/grocer/hotel keyword) | 40 | doctrine + an unverifiable revenue split |
| DATA missing-row | 9 | **defect — fixed today** |
| DATA no-data | 8 | **defect for the common stocks among them** |
| CLASS industry keyword | 8 | doctrine (entertainment/defense) |
| CLASS ruling | 5 | doctrine |
| CLASS SIC 6xxx | 4 | doctrine |
| HARAM 5% | 1 | measurement |

> **65% of every disagreement with a professional screen is the 10/10/20 choice
> itself. 17 of 323 (5%) are a data defect.**

The 38 "blown past 33" deserve a flag of their own: several are **market-cap
artifacts on ADRs** — TSM shows `cash 162.98%` of market cap because the cap is
the ADR line, not the whole company. That is a denominator bug in the mcap
source, not a compliance finding, and it is worth its own pass (proposal 7).

**The compliance direction is clean: of the 402 names both screeners refuse,
we pass ZERO.** The gate has no leaks against the professional screens.

**"What would our count be under AAOIFI 33/33/5, everything else unchanged?"
→ 1,426** (from §2b; the 5% haram leg is already AAOIFI's number).

---

## 4. POINT-IN-TIME vs SNAPSHOT — was the zip stale?

`data/edgar/companyfacts.zip` was dated **2026-08-14** while yfinance is live.
Refreshed today (free, no key, 1.41 GB, ~8 min) and re-extracted over 12,532
symbols:

| | before (2026-08-14) | after (2026-09-17) |
|---|---:|---:|
| zip members | 20,225 | 20,373 |
| symbols with ≥1 complete quarter | 3,677 (2026-09-16 merge) | **4,416** |
| **symbols whose latest filed quarter moved forward** | — | **663** |
| …of those, latest period end now **after 2026-06-30** (true July/August-quarter filers) | — | **202** |

Crossed against the refusals:

* of the **376 missing-row refusals**, **72 got a newer filed quarter** — but
  only **5 are strictly July-quarter filers**;
* of the **238 still-refused-for-interest**, **52 got a newer quarter**, **5**
  July-quarter filers;
* of the 6,068 no-data refusals, **21** now have EDGAR quarters.

**So the stale zip is a real but minor cause: it explains ~19% of the missing-row
bucket by "newer data now exists", and only ~1.3% by the specific July-quarter
story.** The refresh was worth doing and is now in place; it is not the
explanation for 415.

---

## 5. SANITY LIST — 40 names most Muslim investors consider halal

Our verdict BEFORE today's change, against Zoya / Musaffa / US Shariah-ETF
membership (`plan/hgr_bench.py --sanity`; screener verdicts fetched 2026-09-17):

| SYM | ours | Zoya | Musaffa | in a US Shariah ETF | our reason | explanation of the disagreement |
|---|---|---|---|---|---|---|
| AAPL | PASS | compliant | halal | yes | — | agree |
| MSFT | PASS | *questionable* | *not halal* | yes | — | **we are LOOSER than both.** Their objection is business-activity (gaming/Xbox, advertising), which our interest-only 5% test cannot see. Worth a user ruling |
| GOOGL | PASS | *questionable* | *doubtful* | yes | — | same class as MSFT (advertising revenue mix) |
| NVDA | PASS | compliant | halal | yes | — | agree |
| AMD | PASS | compliant | halal | yes | — | agree (the AMD ruling holds) |
| TSLA | PASS | compliant | halal | yes | — | agree |
| ADBE | PASS | compliant | halal | yes | — | agree |
| CRM | FAIL | compliant | halal | yes | `LOAN>10+COMBINED>20` (loan 19.76, cash 5.58, comb 25.35) | **10/10/20 vs 33** — intended |
| INTU | PASS | compliant | not halal | — | — | we agree with Zoya |
| ISRG | **FAIL** | compliant | halal | yes | `unverified: missing debt` | **DEFECT** — Intuitive tags no debt concept because it has none |
| LLY | PASS | compliant | halal | yes | — | agree (restored 2026-09-16 by the non-operating bound) |
| JNJ | PASS | compliant | halal | yes | — | agree |
| PG | FAIL | compliant | halal | yes | `LOAN>10` (10.22) | **10/10/20** — 0.22pp over the line |
| KO | FAIL | compliant | halal | — | `LOAN>10` (11.42) | **10/10/20** |
| PEP | FAIL | compliant | doubtful | yes | `LOAN>10` (28.82) | 10/10/20; also fails at 33 on combined |
| COST | FAIL | questionable | not halal | — | revenue-mix (liquor, grocer) | **agree with both** |
| NKE | FAIL | compliant | halal | yes | `LOAN>10+COMBINED>20` | 10/10/20 |
| ORCL | FAIL | compliant | not halal | yes | `LOAN>10+COMBINED>20` (loan 37.6) | fails at 33 too — we agree with Musaffa |
| CSCO | PASS | compliant | halal | yes | — | agree |
| QCOM | PASS | compliant | halal | yes | — | agree |
| AVGO | PASS | compliant | halal | yes | — | agree |
| TXN | PASS | compliant | halal | yes | — | agree |
| AMAT | PASS | compliant | halal | yes | — | agree (restored by the plausibility cap, 2026-09-16) |
| LRCX | PASS | compliant | halal | yes | — | agree |
| KLAC | PASS | compliant | halal | yes | — | agree |
| ASML | PASS | compliant | halal | — | — | agree |
| NFLX | FAIL | questionable | not halal | — | `HARAM INDUSTRY (entertainment)` | **agree** — and the user's entertainment ruling is stricter than Zoya's "questionable" |
| PFE | FAIL | **not compliant** | not halal | yes | `LOAN>10+COMBINED>20` | agree on the verdict; note the ETF still holds it (holdings are 2026-02-28) |
| MRK | FAIL | compliant | halal | yes | `LOAN>10` (15.12) | 10/10/20 |
| TMO | FAIL | compliant | halal | yes | `LOAN>10+COMBINED>20` (19.02) | 10/10/20 |
| ABT | FAIL | compliant | halal | yes | `LOAN>10` (19.25) | 10/10/20 |
| DHR | FAIL | compliant | halal | yes | `LOAN>10+COMBINED>20` | 10/10/20 |
| UNH | FAIL | not compliant | not halal | — | `LOAN>10+COMBINED>20` | **agree on the verdict, for the wrong reason.** UNH is a health insurer; its SIC is 6324's sibling and it should be failing on the sector screen, not on a debt ratio |
| HD | FAIL | compliant | halal | yes | `LOAN>10` (20.31) | 10/10/20 |
| LOW | FAIL | not compliant | halal | yes | `LOAN>10+COMBINED>20` (37.04) | fails at 33 too — agree with Zoya |
| WMT | FAIL | questionable | doubtful | — | revenue-mix (alcohol, beverage, grocer) | **agree** |
| CAT | FAIL | compliant | not halal | — | `LOAN>10` (12.53) | 10/10/20; Musaffa agrees on the verdict |
| DE | FAIL | not compliant | not halal | — | `LOAN>10+COMBINED>20` | agree (Deere Financial is a captive lender) |
| HON | FAIL | not compliant | not halal | — | `LOAN>10+COMBINED>20` | agree |
| LIN | FAIL | compliant | halal | yes | `LOAN>10` (13.07) | 10/10/20 |

**Tally: 19 PASS, 21 FAIL. Of the 21 FAILs, 15 are the 10/10/20 ratio choice, 3
are agreements with both screeners (COST, WMT, NFLX), 2 are agreements on the
verdict via a different route (UNH, DE/HON), and exactly ONE — ISRG — is a
defect.** MSFT and GOOGL are the only two names where *we are looser than the
professionals*, and both for a business-activity reason our interest-only 5% test
structurally cannot see (documented limitation, not a bug).

---
