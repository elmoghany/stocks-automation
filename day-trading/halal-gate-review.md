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
| **strict 10/10/20** (the user's own choice, 3× stricter than AAOIFI) | **2,693** refused on a ratio leg | **YES — deliberate.** 210 of the 456 names professional screens pass (217 of 524 after today's rebuild) are refused *only* because a leg sits in the 10–33 band those screens allow |
| **"a missing row is never a zero"** applied to ONE table | **376** refused as `unverified` | **NO — over-applied.** The gate read the newest yfinance quarterly column and nothing else. AAPL, LLY, ISRG, ANET, MRVL were refused for rows that are in the annual statement, in an older column, or in EDGAR |
| **the 5% interest leg with no interest tag** | 238 of those 376 | **NO — provable.** 15 of the 16 large names in that bucket tag **no interest concept in any EDGAR period**, because the line is immaterial. Immaterial is provable, not unverifiable |

**A doctrinal change was ruled and landed the same day** (user, 2026-09-17: *"For
the missing statement, use the last available statement or check the Zoya
website. Do not just reject it. Same for data drift."*):

> **ARMABLE 415 → 463 on the rebuilt gate, → 476 with 13 Class-B Zoya/Musaffa
> rulings. 52 names restored, 4 lost to price drift. MRVL comes back MEASURED.**
> The rebuilt list is parked at `data/halal_list.NEW.json`;
> `data/halal_list.json` (415) was not touched.

Full results in §6; the ranked list of what else the user could change, each with
its doctrinal question and its resulting count, is §8. **The largest lever by far
is the user's own 10/10/20: at AAOIFI's 33/33 the same universe arms 1,363.**

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
| SIC 6000–6999 | 86 | 86 | **mostly intended — 97 of 104 are exactly what the rule named; 5 mis-codes** |
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

## 6. THE CHANGE THAT LANDED — "use the last available statement"

**User ruling, 2026-09-17:** *"For the missing statement, use the last available
statement or check the Zoya website. Do not just reject it. Same for data
drift."*

### What changed (and what deliberately did not)

Decision 4 of the halal-fix epoch — *a missing row is never a zero* — **stands
unchanged**. What changed is **where the gate looks before it says the row is
missing**. Per field, in order, bounded by `LAST_AVAIL_MAX_AGE_DAYS = 460`
(~15 months) and **named on the verdict** in a new `last_available` field:

1. **yfinance quarterly** — the newest column that carries the row (this alone
   fixes *"no recent period carries BOTH debt and cash"*: each leg is now read
   from its own last filed column instead of the pair being refused);
2. **yfinance ANNUAL** — a filed 10-K is a statement, not an absence. Revenue
   taken this way brings the interest row from the same annual column, so both
   sides of the 5% test come from one filed year;
3. **EDGAR companyfacts** (`data/edgar/extracted`), honoring the extractor's own
   `miss` list so an untagged line is still never offered as a zero.

**A real bug was found on the way:** `_bs_pair` returns **both** legs as `None`
whenever **either** row is absent, so a name whose cash row was missing also
arrived with its perfectly readable debt row unread, and fell through to the
belt-and-braces refusal *"debt, combined could not be computed"* — a refusal for
a row that was right there. Fixed.

**New interest rung 4 — THE CASH CEILING.** The 8%/yr premise the plausibility
cap already rests on is a *proof* read the other way: interest income cannot
exceed 8%/yr × (cash + interest-bearing securities), so a ceiling under 5% of TTM
revenue clears the leg whatever the filer tagged. It is guarded twice, because
the first version of it passed a closed-end fund: it never fires on the `info`
tier (a vendor summary is not a statement), and the ceiling base now includes the
long-dated investments line, so a fund with **no cash row and $3.0bn of
"Investments And Advances" against $34M of revenue (ADX)** is refused, not
cleared. Among the armable names the bounds it produces are strong, not marginal:
median 2.26%, p90 2.8%, one name at ≥4%.

Unchanged, as briefed: strict 10/10/20, SIC 6000–6999 (6770 exempt), the 5%
threshold, the keyword screen. Mirrored into `halal_pt` (the backtest gate) with
the same semantics, plus one fix of the same family: `_ttm_pt` no longer sums a
leading untagged-revenue quarter in as `0.0`.

### EDGAR refreshed first

`companyfacts.zip` **2026-08-14 → 2026-09-17** (old kept as
`companyfacts.2026-08-14.zip`), re-extracted over 12,532 symbols (**4,416 with
≥1 complete quarter**, was 3,677) and re-merged into `data/pt_halal` (31 created,
4,444 updated, 41,367 EDGAR-side quarters). See §4 for what the refresh was
worth.

### RESULT: 415 → 476

| step | armable |
|---|---:|
| 2026-09-16 interest-leg state | **415** |
| + `--last-available` rescreen (2,439 candidates) | **463** (52 restored, 4 lost) |
| + 13 Class-B Zoya/Musaffa rulings | **476** |

**Restored, by the rung that answered**
(`data/halal_flips_2026-09-17.last-available.json`):

| rung | n | largest names |
|---|---:|---|
| vendor row on fresher data (drift, not the change) | 13 | REGN $80bn, IMO $63bn, MSM, XMTR, BRC, NRP, ODC, ITRN |
| **upper-bound (max yield on cash)** — the new rung 4 | **16** | **MRVL $206bn**, KNSA $6bn, DMLP, GFR, PLBL, ACCL |
| **last-available statement** | **17** | GFI $37bn (yf-annual revenue+interest), ANGO (EDGAR debt + yf cash), MCFT (EDGAR debt), MGRT, NBTX, SLBT, ADSE, ELVR |
| upper-bound (nonoperating income) | 3 | MMED $6bn, POWI, GYRE, CHRN |
| *of which the plausibility cap had to rescue first* | *12* | MRVL, CHRN, PLBL, MESO, BRAI, GFR, BLZE, MKDW, WSHP, EUDA, NOMA, ATCX |

**MRVL comes back MEASURED at 2.90%** on the cash ceiling — the name this whole
interest-leg saga was about, now cleared by a proof instead of refused for a row
Marvell does not tag.

**The 13 Class-B rulings** (`plan/hgr_screeners.py` → `plan/hgr_rulings.py`,
public Zoya/Musaffa pages, no login): ANET $249bn, ISRG $135bn, NXT $12bn,
BMI $3.7bn, ELMD, BUUU, NNNN, ARCL, FTHA, VECA, ENGS, QXL, SOWG. Written under
**four guards stricter than the bare Class-B rule**, because a Class-B PASS
bypasses our ratio legs entirely and those screeners use 33/33:

1. common equity only (a closed-end bond fund is not "a company whose finances
   we could not find");
2. ≥1 affirmation **and** no conflicting verdict from the other source;
3. **every leg we can still compute must clear the house 10/10/20** — external
   evidence is admitted only for the leg that is genuinely missing, never to
   launder a leg our own data already failed;
4. never overwrite an existing ruling, and never write a FAIL (a bare external
   non-compliant leaves the default FAIL standing, per SOURCES.md rule 2).

Skipped for those reasons: 213 no affirmation, 181 not common equity, 12
conflicting, 10 already ruled, 9 whose own computable legs fail.

### "SAME FOR DATA DRIFT" — answered, and the answer is *there is nothing to correct*

All **4** names lost in this rebuild are strict-10 drift, and every one of them
crossed the line by ≤ 0.6pp **because the market cap fell, on statements that did
not move**:

| SYM | was | now | leg |
|---|---|---|---|
| INTU | loan 9.77 | **10.06** | LOAN>10 |
| NPO | loan 9.61 | **10.17** | LOAN>10 |
| STE | loan 9.84 | **10.08** | LOAN>10 |
| Z | cash 9.50 | **10.08** | CASH>10 |

Recomputing these from the last available statement gives the **same answer** —
the statement is the current one and it is complete. **This is not a vendor
artifact; it is the 10% line being a cliff.** The only remedies are doctrinal: a
looser threshold (§8, proposal 1), or a tolerance band / hysteresis so a name that is 0.1pp
over does not flip in and out week to week. That is a question for the user, not
a bug to fix.

### The funnel, after

| step | ALL 10,761 | CS+ADRC (4,597) |
|---|---:|---:|
| haram-industry keyword | 759 | 725 |
| SIC 6000–6999 | 412 | 149 |
| user / external FAIL ruling | 35 | 29 |
| **market cap missing** | **133** | **47** |
| no fundamentals at all | 5,492 | **12** *(was 150)* |
| missing statement row | 421 | 240 *(was 286)* |
| leg uncomputable | 4 | 4 |
| revenue-mix unverifiable | 318 | 315 |
| ratio `LOAN>10` | 1,973 | 1,872 |
| ratio `CASH>10` | 678 | 674 |
| `HARAM>=5%` | 60 | 59 |
| **ARMABLE** | **476** | **471** |

Two rows moved for reasons that are **not** the doctrine change and must be read
as bookkeeping: `SIC 6000–6999` jumped 97 → 412 and `no fundamentals` fell
6,068 → 5,492 because the rescreen re-evaluated 591 names that still carried
**2026-09-01 pre-fix verdicts** — the SIC screen fires before the no-data check,
so those names simply moved from one bucket to the correct one.

**`MARKET CAP MISSING` 7 → 133 (47 of them common stock) is a new, real and
fixable gap**: the gate can now READ statements for names whose market cap
yfinance will not give it, so it refuses loudly for want of a denominator instead
of quietly for want of data. **Polygon already has a market cap for 19 of those
47 common stocks** — GILD $183bn, AZO $47bn, EHC, DCI, EDU, ASR, CMC, DAC, GSL,
CYD, EDN, GSM, GAIN, EBF, CHW … That is proposal 8 and it is nearly free.

### Sanity list, after

`ISRG` **FAIL → PASS** (Class-B ruling). `INTU` **PASS → FAIL** (loan 9.77 →
10.06, the drift above). Everything else in §5 is unchanged, so the tally is now
**19 PASS / 21 FAIL, with 15 of the FAILs being the 10/10/20 choice and ZERO
remaining defects.** The 13-name doctrine probe:

    AMD   PASS  loan 0.48 cash 1.47 comb 1.95 haram 0.16 (yfinance)
    SWKS  PASS  loan 4.96 cash 5.82 comb 10.77 haram 0.66 (yfinance)
    QCOM  PASS  loan 8.61 cash 4.68 comb 13.30 haram 1.11 (edgar-interest, edgar window)
    MRVL  PASS  loan 2.44 cash 1.82 comb 4.26 haram 2.90 (upper-bound, max yield on cash)  <- WAS "unverified"
    HLIT  FAIL  CASH>10 (17.81)
    ASST  FAIL  FINANCIAL SECTOR (SIC 6199)
    LMT/NFLX/SAM/CMG  FAIL  HARAM INDUSTRY
    RRGB/RETO/NDLS    FAIL  user rulings
    KO    FAIL  LOAN>10 in the cache; the ad-hoc probe hit a transient yfinance
                `info` failure and answered MARKET CAP MISSING -- see the mcap
                fragility note above

### Benchmark, after

| our cause on the 524 names a professional screen passes | n |
|---|---:|
| **PASS** | **173** *(was 133)* |
| RATIO inside the 10–33 band | 217 |
| RATIO blown past 33 | 41 |
| CLASS revenue-mix | 40 |
| **DATA missing-row** | **25** |
| CLASS sic-6xxx / industry / ruling | 22 |
| DATA no-data | 4 |
| HARAM 5% | 2 |

Agreement with the professionals rose from 29% to 33% of the names they pass,
and the direction that matters is still clean: **of the names both screeners
refuse, we pass zero.**

---

## 7. THE REPORTING-CURRENCY BUG — found on the way, real, and SMALLER than it looks

`halal_check` divides a yfinance statement value by a market cap in USD.
**yfinance publishes statements in the FILER's OWN reporting currency**
(`info["financialCurrency"]`). Every foreign private issuer that reports in
rupiah, won, yen, rupee, yuan or peso therefore has its debt and cash legs
multiplied by the FX rate before being compared with a 10% limit.

The cached numbers say it plainly:

| SYM | company | `financialCurrency` | cached loan/mcap | cached cash/mcap |
|---|---|---|---:|---:|
| TLK | Telkom Indonesia | **IDR** | 554,387% | 387,136% |
| GRVY | Gravity Co. | **KRW** | 0% | 128,010% |
| VFS | VinFast | **VND** | 1,264,773% | 108,412% |
| PKX | POSCO | **KRW** | 171,662% | 80,736% |
| KT | KT Corp | **KRW** | 115,616% | 52,967% |
| HMC | Honda | **JPY** | 0% | 13,266% |
| CEPU | Central Puerto | **ARS** | 36,475% | 10,042% |

Measured on a stratified random sample (60 names per band, seed 20260917),
share of ratio-refused names whose statements are NOT in USD:

| cached `combined` | names in band | sampled non-USD | rate |
|---|---:|---:|---:|
| 20–50% | 1,402 | 3 / 60 | 5% |
| 50–100% | 592 | 4 / 60 | 7% |
| 100–1,000% | 609 | 9 / 60 | 15% |
| **> 1,000%** | **90** | **41 / 60** | **68%** |

**≈ 260 of the 2,693 ratio refusals are unit-mismatched, not over-levered.**
The 5% haram leg is unaffected (interest and revenue are both in the filer's
currency, so their ratio is already unit-free); only the two legs divided by
market cap are wrong. The exact restorable count is measured by
`plan/hgr_fx.py` (§8, proposal 2) — a EUR filer at combined 25% is still a
FAIL after conversion, but an INR filer at 600% is a clean PASS.

**MEASURED, AND THE HEADLINE DEFLATES** (`plan/hgr_fx.py`, run after the
rebuild). Of 2,318 ratio refusals with combined ≥ 20%, yfinance answered a
reporting currency for 1,056 (a 401 "Invalid Crumb" storm left 1,262 unresolved
and it is stated rather than papered over): **88 non-USD** — CNY 20, CAD 19,
BRL 9, EUR 9, HKD 4, TWD 3, GBP 3, and one each of KRW/ARS/COP/TRY. Converting
their legs at the live Polygon USD cross:

| SYM | cur | loan was → is | cash was → is |
|---|---|---|---|
| BIDU | CNY | 291.3% → **43.4%** | 361.7% → **53.9%** |
| BILI | CNY | 141.5% → 21.1% | 357.7% → 53.4% |
| GGB | BRL | 167.7% → 32.6% | 60.2% → 11.7% |
| ENB | CAD | 101.6% → 72.6% | 1.9% → 1.4% |
| BCE | CAD | 189.9% → 135.8% | 2.2% → 1.6% |
| CP | CAD | 30.9% → 22.1% | 0.5% → 0.3% |

> **Only 2 of the 59 names with a resolvable FX rate would PASS the unchanged
> 10/10/20 after conversion (DSC, HSAI).** The big foreign issuers are genuinely
> levered — Enbridge at 72.6% of market cap in debt fails at 33 too.

So: **the numbers the gate prints for ~260 foreign filers are wrong and should be
fixed, but fixing them buys the armable list roughly 2–10 names, not hundreds.**
It is a correctness and reporting defect, not the reason 476 is 476. Not changed
today — it needs an FX rate per reporting currency inside the gate and another
full re-screen, and the brief was one doctrinal change.

---

## 8. PROPOSED CHANGES, RANKED — each with its doctrinal question and its count

Counts are priced by `plan/hgr_props.py` against **today's rebuilt 476-name
universe** (`--before` re-prices them against the 2026-09-16 415-name state, and
both are given where they differ). **Nothing below is implemented** — §6's change
is the only one that landed. The ranking is by size of effect, not by
confidence: #1 is a doctrinal choice only the user can make, #2–#9 are defects or
hygiene.

### 1. Relax the ratio thresholds toward AAOIFI — **the single biggest lever**

* **Doctrinal question for the user:** *your 10/10/20 is roughly 3× stricter than
  the 33/33 that AAOIFI, Zoya, Musaffa, HLAL, SPUS and the Dow Jones Islamic
  indices all use. Do you want your own number, or the scholarly consensus
  number? There is no middle position that is "more correct" — both are
  defensible ijtihad, and the 10% line is the stricter, safer one.*
* **Effect on the count** (ratio legs only, every other screen untouched):

  | thresholds | armable (today's universe) | (on the 2026-09-16 universe) |
  |---|---:|---:|
  | 10 / 10 / 20 — today | **476** | 415 |
  | 12 / 12 / 24 | 578 | 510 |
  | 15 / 15 / 30 | 724 | 655 |
  | 20 / 20 / 40 | 930 | 884 |
  | 25 / 25 / 50 | 1,076 | 1,112 |
  | 33 / 33 / 66 — AAOIFI | **1,363** | 1,426 |

  (The two columns are not monotone against each other at the loose end because
  the rebuild also re-read 2,439 names' statements; the 33/33 row moved down for
  data reasons, not rule reasons.)

* **What it changes live:** every household name the user named in the sanity
  list — PG (loan 10.22), KO (11.42), MRK, ABT, TMO, DHR, HD, LIN, CAT, NKE, CRM
  — arms at 20/20/40 or lower. The scanner's daily armable pool roughly triples,
  which is the difference between 1 ticket a day and 3–5.
* **Risk:** none doctrinally (it is *looser*, and matches the professionals), but
  it changes every backtest baseline in the repo.

### 2. Fix the reporting-currency bug (§7) — **a bug, not a choice**

* **Doctrinal question:** none. A ratio whose numerator is in rupiah and whose
  denominator is in dollars is not a ratio.
* **Effect on the count: SMALL — 2 measured, ~10 at the outside** (§7). The
  numbers printed for ~260 foreign filers are wrong; the names behind them are
  genuinely levered. Fix it for correctness, not for the count.
* **What it changes live:** removes a class of false refusals that is invisible
  today because the numbers look like "obviously over-levered".
* **Cost:** one FX lookup per reporting currency, cached like `sic_codes.json`,
  plus a full re-screen.

### 3. Screen only COMMON EQUITY at universe build

* **Doctrinal question:** *should an ETF, a closed-end bond fund, a commodity
  trust, a preferred share or an ETN ever be armable?* (Today three Shariah ETFs
  — HLAL, SPUS, MNZL — **are** armable, and so is **JPO, a YieldMax covered-call
  option-income ETF**.)
* **Effect on the count:** **476 → 471.** It does not make the list bigger; it
  makes the *denominator* honest and removes four things that should never have
  been tradeable here.
* **What it changes live:** the monthly refresh screens 4,590 symbols instead of
  10,761 — **57% less yfinance time**, which is the difference between an
  overnight run and an afternoon one — and the "56% of the universe has no data"
  statistic disappears because it was never about companies.

### 4. An absent DEBT line on an otherwise-complete filed balance sheet reads as ZERO

* **Doctrinal question:** *a company files a complete balance sheet and it
  contains no debt line at all. Is that "we cannot verify the debt" (today's
  answer) or "the company has no debt" (what the filing means)?* The EDGAR
  extractor already takes the second view for its own quarters
  (`plan/edgar_backfill.py`: "an absent balance-sheet LINE IS zero on that
  statement — unlike a missing statement, which stays absent"); the live gate
  takes the first. **They should agree.**
* **Effect on the count:** **476 → 480** — and that number is small ONLY because
  the four biggest names in the class (ANET, ISRG, NXT, BMI) were already
  restored today by the Zoya/Musaffa route. The four it adds are **MNST $87bn,
  FNV $50bn, SYM $5.6bn, PRT** — all with the cash leg and the 5% leg already
  clear and a loan leg that would read 0.
* **Why it is still worth doing:** it resolves the class **from the filing**
  instead of from a third-party verdict, which is strictly better evidence, and
  it removes the need for a Class-B ruling on every future debt-free company.
* **Risk:** a filer that tags debt under an unusual concept would read as
  debt-free. Mitigate by requiring BOTH yfinance and EDGAR to carry no debt
  concept in any period.

### 5. Restore the SIC 6xxx false positives by explicit PASS rulings

* **Doctrinal question:** *your rule named "banks, lenders, insurers, asset
  managers, brokers, REITs, funds". SEC SIC 6794 is "Patent Owners & Lessors"
  and 6795 is "Mineral Royalty Traders". Is a patent licensor or a gold-stream
  royalty company a financial institution to you?*
* **Effect on the count:** **476 → 481** (RGLD $21bn, TPL $24bn, TFPM $6.6bn,
  USIO, RMCO clear every ratio leg today; IDCC, TRNO, CHCI, VMET, AGNT still fail
  one and would stay refused).
* The mechanism already exists and needs no code: a PASS ruling **with a basis**
  in `data/halal_rulings.json` restores a quirk-coded name.
* 97 of the 104 SIC refusals are exactly what the rule named. **This is not why
  415 is 415.**

### 6. Revenue-mix keyword → review queue instead of automatic FAIL

* **Doctrinal question:** *"unverified is haram" (your 2026-08-22 ruling) is
  applied today to any company whose business summary contains "beverage",
  "grocer", "hotel" or "restaurant" — 317 names, including BABA. Should a
  keyword hit refuse the name outright, or send it to the review queue where a
  10-K segment note or a Zoya verdict can answer it?*
* **Effect on the count:** **476 → up to 494** (18 of the 318 already clear every
  ratio leg; the rest fail a ratio anyway). Triggers: hospitality 5, resort 2,
  grocer 2, restaurant 2, alcohol 1, beverage 1 …
* **What it changes live:** small, and it is the most labour-intensive proposal.

### 7. The two names where WE are LOOSER than the professionals

* **MSFT** (Zoya *questionable*, Musaffa *not halal*) and **GOOGL** (Zoya
  *questionable*, Musaffa *doubtful*) both PASS here.
* **Doctrinal question:** *their objection is business activity — Xbox/gaming
  revenue at Microsoft, advertising at Alphabet — which our 5% test structurally
  cannot see because it measures interest income only. Do you want a ruling on
  advertising and game revenue?*
* **Effect on the count:** −2 at most, but it is the only direction in which the
  gate is currently *permissive* relative to the professionals, and the user has
  asked for the stricter reading in every comparable case (entertainment,
  defense-by-trade).

### 8. Add Polygon's market cap as a third denominator source — nearly free

* **Doctrinal question:** none. A name we can read the statements for but not the
  market cap is refused as `MARKET CAP MISSING`, which is correct and loud — but
  the cap is one cached API call away.
* **Effect on the count:** **19 of the 47 common stocks now in that bucket have a
  Polygon market cap on file already** (GILD $183bn, AZO $47bn, EHC, DCI, EDU,
  ASR, CMC, DAC, GSL, CYD, EDN, GSM, GAIN, EBF, CHW …). They would be *screened*,
  not necessarily armed.
* **Also fixes a live fragility this review tripped over:** a transient yfinance
  `info` failure makes the gate answer `MARKET CAP MISSING` for AAPL-class names
  (it did so for KO, ANET and ISRG during the 13-name probe, minutes after the
  same names screened fine). `load_rh_fundamentals()` → yfinance `info` →
  **Polygon `/v3/reference/tickers`** would make the denominator three-deep
  instead of two-deep.

### 9. A tolerance band on the 10% cliff (raised by the drift question)

* **Doctrinal question:** *INTU at loan 9.77% was armable and at 10.06% is not,
  on statements that did not change. Do you want a name to flip in and out on a
  0.3pp move in its market cap, or should a name inside (say) 10–10.5% keep its
  previous verdict until it is decisively over?*
* **Effect on the count:** 4 names this week; it is a stability question, not a
  size question. It matters more for the backtest (traded-day counts moved 360 →
  414 across the last two epochs for exactly this kind of reason) than for the
  live list.

### 10. Not proposed, recorded as standing limitations

* **Market cap is a present-day snapshot** against quarter-old statements; a name
  that halved since filing doubles both ratios. 495 names show cash > 60% of
  market cap and 140 of those are ADRs (see §7 — most are the currency bug, the
  rest are the ADR-line-vs-whole-company denominator).
* **`haram_pct` is interest-income-only** and is blind to alcohol, pork, gaming
  and tobacco *revenue*; `REVENUE_SENSITIVE_WORDS` is the compensating screen.
* **The industry keyword screen has essentially no false positives** — checked
  against EDGAR SIC: bank 340/340 correct, mortgage 41/41, insurance 107/108
  (XZO, an insurtech software spin-off, is the only arguable one), and every
  "defense/aerospace" and "entertainment" hit with a non-matching SIC is still a
  real defense prime (GE Aerospace, GD, NOC, LHX, HII, BWXT, DRS) or a real
  broadcaster/studio (WBD, FOXA, PSKY, SIRI, ROKU). **Leave it alone.**
* **The universe file mixes two gate epochs** (§1) and should be rebuilt whole
  once the thresholds are settled.

