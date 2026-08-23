# External halal-screening evidence sources (W-campaign, 2026-08-22)

USER DIRECTION (2026-08-22): "no unverified can be both. try to find if
it is halal or not. search zoya or find a way." And the exception rule:
"the only exception for my halal rules: the stocks that are not
verifiable because we could not find its finances. then for these use
zoya and etc."

## How external evidence composes with the house screen

Two classes of unverified names, treated differently:

- **Class A — financials exist, revenue mix unverifiable** (the
  CANNOT-VERIFY population): external evidence clears ONLY the
  business-activity leg (the 5% haram-revenue question). Our own
  10/10/20 financing ratios (loans/mcap <=10, cash/mcap <=10, combined
  <=20) still run on our data — a PASS ruling never bypasses them.
  External "non-compliant" verdicts are NEVER adopted as FAIL rulings
  here, because the public pages do not show the reason and the
  non-compliance may be on THEIR (looser, ~30-33%) financial-ratio
  legs, which our own (stricter) ratio test already covers. A bare
  external non-compliant simply leaves the default FAIL standing.
- **Class B — no financials findable at all** (halal_check's
  "NO FUNDAMENTALS DATA" refusals): the user's explicit exception. The
  external screener's FULL verdict (their AAOIFI financial thresholds
  included) is adopted whole, because our rules cannot run without a
  denominator and a professional screen beats a blind refusal. These
  rulings carry `"class": "B-no-financials"` in
  `data/halal_rulings.json`, and `day-trading.py::halal_check` consults
  the overlay on its no-data branch ONLY for rulings so marked (a
  Class A ruling must never ride the no-data branch — a transient
  yfinance outage would otherwise bypass the ratio gates).

User industry rulings (entertainment 2026-08-13, defense-contractor
2026-08-14, hotel-operator/alcohol-menu precedents CMCT/FBYD/RRGB)
outrank every external verdict where stricter: an external "compliant"
never overrides a house hard-FAIL class.

## Source 1: Zoya (zoya.finance)

- **URL pattern**: `https://zoya.finance/stocks/<ticker-lowercase>`
  (404 = not covered).
- **Public without login**: the verdict only, as an h2 —
  "<SYM> stock is Shariah-compliant" / "not Shariah-compliant" /
  "questionable" — plus the company description. NO reason, NO
  percentages, NO as-of date (the "Last updated" field is
  client-rendered and empty in static HTML).
- **Behind the app/account** (NOT used — user decides on signups): the
  full compliance report — business-activity breakdown, impermissible
  revenue %, debt/securities ratios, purification amounts.
- **Methodology**: AAOIFI rulebook (per their help center): business
  screen impermissible revenue < 5%; financial screens (interest-bearing
  debt, interest-bearing securities) vs ~30% of market cap — LOOSER than
  our 10/10/20, hence the Class A composition rule above.
- **Update cadence** (their claim): reviewed at least quarterly.
- **robots.txt**: no Disallow — public pages crawlable. Sweep paced
  1.6-2.4 s/request with an identified User-Agent.
- **Coverage observed** (sitemap, 2026-08-22): 4,574 stock pages;
  539/634 of our Class A names, 9 of our Class B names.
- **Calibration** (2026-08-22): AMD compliant, KO compliant, NFLX
  questionable, SAM not compliant, RRGB not compliant — matches our
  house verdicts on the knowns (NFLX/SAM/RRGB all non-tradeable here;
  KO's house verdict was the open CV question this campaign resolved).

## Source 2: Musaffa (musaffa.com)

- **URL pattern**: `https://musaffa.com/stock/<TICKER>` (uppercase).
- **Public without login**: verdict sentence "As of <Month Year>,
  <Company> is classified as halal / not halal / doubtful", the
  screening-methodology label ("AAOIFI"), and the as-of month. NO
  reason, NO percentages.
- **Behind the account**: detailed screening report (revenue breakdown,
  ratio values), purification calculator.
- **Methodology**: AAOIFI (same structure/loosenesses as Zoya).
- **robots.txt**: `Disallow: /*?page=` only — stock pages crawlable.
- **Coverage observed** (us-stocks sitemap, 2026-08-22): 23,371 US
  pages (includes OTC); 617/634 Class A, 79/5,923 Class B.
- **Calibration**: AMD halal, NFLX not halal, SAM not halal — agrees
  with Zoya on the knowns except NFLX (Zoya questionable vs Musaffa not
  halal; both non-affirming, no contradiction).

## Source 3: Islamicly (islamicly.com)

- Probed 2026-08-22: **no public per-stock verdict pages** — everything
  per-stock sits behind the app/free-account ("FREE Shariah Compliance
  Report Card" requires signup). A free account would unlock per-stock
  report cards; per the campaign guardrail we STOPPED there — the user
  decides on signups. Not used.

## Source 4: Shariah-screened ETF holdings (data/halal_external/etf_holdings.json)

Membership = a professional screener passed the name under its index
methodology as of the holdings date. Funds ingested 2026-08-22:

| Fund | Index methodology | As-of | Holdings | Source |
|------|-------------------|-------|---------:|--------|
| SPUS | S&P 500 Shariah Industry Exclusions (S&P Shariah, AAOIFI-informed) | 2026-08-21 | 219 | sp-funds.com Tidal daily CSV |
| SPTE | S&P Global Technology Shariah | 2026-08-21 | 104 | sp-funds.com Tidal daily CSV |
| SPRE | S&P Global REIT Shariah | 2026-08-21 | 31 | sp-funds.com Tidal daily CSV |
| SPWO | S&P World ex-US Shariah | 2026-08-21 | 383 | sp-funds.com Tidal daily CSV |
| SPSK | DJ Global Sukuk (bonds — NOT equity evidence, kept for completeness) | 2026-08-21 | 170 | sp-funds.com Tidal daily CSV |
| HLAL | FTSE USA Shariah (Yasaar scholars) | 2026-02-28 | 197 | SEC N-PORT 0000894189-26-012509 |
| UMMA | Dow Jones Islamic Market World | 2026-02-28 | 94 | SEC N-PORT 0000894189-26-012510 |

CSV URLs: `https://www.sp-funds.com/wp-content/uploads/data/TidalFG_Holdings_<TICKER>.csv`.
Wahed publishes no daily holdings file — N-PORT (quarterly, ~2-month
lag) is the public source; tickers parsed from
`<ticker value=.../>` identifiers, equities only (`assetCat` EC).

**Collision guard**: SPWO/UMMA hold non-US listings whose local tickers
can collide with US symbols (e.g. SPWO's "SAR" is not Saratoga
Investment). Global-fund membership alone never affirms a US ticker;
it only corroborates when the holding NAME matches the company.

## Source 5: EDGAR filings (the "find a way" fallback)

For names no screener covers: read the latest 10-K/20-F/S-1 Item 1
(what the company actually sells) and the ASC 606 revenue-
disaggregation note (often quantifies the haram-adjacent line even when
companyfacts has no dimensional tags). Worked examples this campaign:
PUSA (10-K note 9: food-and-beverage $614,997 = 21% of revenue, sold
under two Florida liquor licenses -> RRGB-template FAIL), JMKE (424B4:
every "wine" hit is red-wine VINEGAR; zero alcohol -> PASS), NMAD
(10-K Item 1: clinical-stage biopharma; "resort" trigger false ->
PASS), ENHA (10-K Item 1: blank-check SPAC -> class FAIL).

## Standing pipeline for future names

1. New CV name -> check `zoya.finance/stocks/<sym>` and
   `musaffa.com/stock/<SYM>` (public verdicts).
2. Class A: >=1 affirmation (compliant/halal) and no conflicting
   screener verdict -> PASS ruling (activity leg) citing source +
   as-of; bare non-compliant -> default FAIL stands, no ruling.
   questionable/doubtful never affirm.
3. Class B: adopt the full verdict whole, mark
   `"class": "B-no-financials"`.
4. No coverage -> EDGAR Item 1 + ASC 606 disaggregation read; quantified
   <5% -> PASS with the table cited; >=5% -> FAIL with the number; no
   disaggregation and no haram line named -> AMD-principle PASS if the
   business is clearly permissible, else default FAIL stands recorded as
   "10-K read, no disaggregation".
5. Refresh ETF holdings (URLs above) monthly-ish; membership
   corroborates, US-fund membership can affirm.
6. House-stricter classes always adjudicated by hand before any PASS.

Raw sweep verdicts for this campaign are archived in
`data/halal_external/screener_verdicts.json` (both sources, every
target checked, including explicit NO-COVERAGE records).

## Campaign outcome (2026-08-22)

Sweep totals (1,168 paced public fetches): Zoya 171 compliant / 363
non-compliant / 14 questionable (548 covered targets); Musaffa 152
halal / 410 not halal / 58 doubtful (620 fetched; 100% of covered
Class A; 76 Class B CEF/preferred tail names recorded NOT-CHECKED
after the site slowed to a crawl — FAIL-by-default regardless).

Rulings: 62 -> 236 (+174: 155 Class A PASS, 9 Class A FAIL, 3 Class B
PASS, 7 Class B FAIL; NDLS/USDE/AIAI bases enriched with the
resolution-attempt records). House-stricter overrides where a screener
said compliant: RBLX (game platform), PSN (defense contractor), MUSA
(alcohol+nicotine retail in a 22.2% merchandise superset), BRID (pork
product line); VIK and SOLS excluded from PASS (cruise-operator class;
ticker-collision affirmation).

Armable list: 1,251 -> 1,330 (+83 ratio-passing conversions, -4
compliance leaks ASPC/RDAC/RFAI/USDE removed by the FAIL-finality
fix). ~76 PASS rulings sit dormant on ratio FAILs and convert
automatically when ratios clear. AIAI now has info-tier financials
that screen clean — flagged for the user as a re-litigation candidate
(only the user lifts a FAIL ruling).
